#!/usr/bin/env python3
"""Read-only Reddit client for the reddit skill. Standard library only.

Commands (JSON out on stdout):
  search QUERY [--sub NAME] [--sort relevance|hot|top|new|comments] [--time T] [--limit N]
  listing SUB  [--sort hot|new|top|rising|controversial] [--time T] [--limit N]
  post ID_OR_URL [--comments N] [--depth D] [--sort confidence|top|new|controversial|old|qa]

T is one of hour|day|week|month|year|all (only used by top/controversial/search).

Auth, picked in this order:
  1. REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET -> app-only OAuth (client_credentials),
     requests go to https://oauth.reddit.com
  2. REDDIT_ACCESS_TOKEN -> used as a bearer token against https://oauth.reddit.com
  3. Nothing set -> unauthenticated public .json endpoints on https://www.reddit.com
     (heavily rate limited and often blocked from cloud IPs)

REDDIT_USER_AGENT overrides the User-Agent. Reddit asks for the form
  <platform>:<app id>:<version> (by /u/<username>)
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_UA = "script:claude-ai-reddit-skill:0.1 (read-only)"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_BASE = "https://oauth.reddit.com"
PUBLIC_BASE = "https://www.reddit.com"
CACHE_PATH = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "reddit-skill",
    "token.json",
)
TIME_CHOICES = ["hour", "day", "week", "month", "year", "all"]


class RedditError(Exception):
    pass


def user_agent():
    return os.environ.get("REDDIT_USER_AGENT") or DEFAULT_UA


def _http(req, timeout=30):
    """Perform a request, retrying once on 429 after the advertised reset."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429 and attempt == 0:
                wait = float(e.headers.get("x-ratelimit-reset") or 5)
                time.sleep(min(wait, 60))
                continue
            raise RedditError(f"HTTP {e.code} from {req.full_url}: {body}")
        except urllib.error.URLError as e:
            raise RedditError(f"Network error reaching {req.full_url}: {e.reason}")
    raise RedditError("Rate limited by Reddit twice in a row")


def _load_cached_token(client_id):
    try:
        with open(CACHE_PATH) as f:
            data = json.load(f)
        if data.get("client_id") == client_id and data.get("expires_at", 0) > time.time() + 60:
            return data["access_token"]
    except (OSError, ValueError, KeyError):
        pass
    return None


def _save_cached_token(client_id, token, expires_in):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        fd = os.open(CACHE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(
                {"client_id": client_id, "access_token": token,
                 "expires_at": time.time() + float(expires_in)},
                f,
            )
    except OSError:
        pass  # caching is a convenience only


def get_token():
    """Return (base_url, bearer_token or None)."""
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if cid and secret:
        cached = _load_cached_token(cid)
        if cached:
            return OAUTH_BASE, cached
        basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        req = urllib.request.Request(
            TOKEN_URL,
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={"Authorization": f"Basic {basic}", "User-Agent": user_agent()},
            method="POST",
        )
        data = _http(req)
        token = data.get("access_token")
        if not token:
            raise RedditError(f"Token request failed: {data}")
        _save_cached_token(cid, token, data.get("expires_in", 3600))
        return OAUTH_BASE, token
    if os.environ.get("REDDIT_ACCESS_TOKEN"):
        return OAUTH_BASE, os.environ["REDDIT_ACCESS_TOKEN"]
    return PUBLIC_BASE, None


def api_get(path, params):
    base, token = get_token()
    if token is None and not path.endswith(".json"):
        path = path.rstrip("/") + ".json"
    params = {k: v for k, v in params.items() if v is not None}
    params["raw_json"] = 1
    url = f"{base}{path}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": user_agent()}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _http(urllib.request.Request(url, headers=headers))


# ---------- shaping ----------

def shape_post(d):
    return {
        "id": d.get("id"),
        "subreddit": d.get("subreddit"),
        "title": d.get("title"),
        "author": d.get("author"),
        "score": d.get("score"),
        "num_comments": d.get("num_comments"),
        "created_utc": d.get("created_utc"),
        "permalink": "https://www.reddit.com" + d.get("permalink", ""),
        "url": d.get("url"),
        "is_self": d.get("is_self"),
        "selftext": (d.get("selftext") or "")[:2000] or None,
        "flair": d.get("link_flair_text"),
        "over_18": d.get("over_18"),
    }


def shape_comments(children, max_depth, depth=0):
    out = []
    for c in children:
        if c.get("kind") != "t1":
            continue  # skip "more" stubs
        d = c["data"]
        item = {
            "id": d.get("id"),
            "author": d.get("author"),
            "score": d.get("score"),
            "created_utc": d.get("created_utc"),
            "body": d.get("body"),
        }
        replies = d.get("replies")
        if depth + 1 < max_depth and isinstance(replies, dict):
            kids = shape_comments(replies["data"]["children"], max_depth, depth + 1)
            if kids:
                item["replies"] = kids
        out.append(item)
    return out


def listing_posts(data):
    return [shape_post(c["data"]) for c in data["data"]["children"] if c.get("kind") == "t3"]


# ---------- commands ----------

def clean_sub(name):
    name = name.strip()
    name = re.sub(r"^/?r/", "", name)
    if not re.fullmatch(r"[A-Za-z0-9_+]{2,64}", name):
        raise RedditError(f"Not a valid subreddit name: {name!r}")
    return name


def parse_post_id(s):
    s = s.strip()
    m = re.search(r"/comments/([a-z0-9]+)", s)
    if m:
        return m.group(1)
    m = re.search(r"redd\.it/([a-z0-9]+)", s)
    if m:
        return m.group(1)
    s = re.sub(r"^t3_", "", s)
    if re.fullmatch(r"[a-z0-9]{3,12}", s):
        return s
    raise RedditError(f"Could not find a post id in {s!r}")


def cmd_search(a):
    params = {"q": a.query, "sort": a.sort, "t": a.time, "limit": a.limit, "type": "link"}
    if a.sub:
        path = f"/r/{clean_sub(a.sub)}/search"
        params["restrict_sr"] = 1
    else:
        path = "/search"
    return {"query": a.query, "subreddit": a.sub, "posts": listing_posts(api_get(path, params))}


def cmd_listing(a):
    sub = clean_sub(a.sub)
    params = {"limit": a.limit}
    if a.sort in ("top", "controversial"):
        params["t"] = a.time
    data = api_get(f"/r/{sub}/{a.sort}", params)
    return {"subreddit": sub, "sort": a.sort, "posts": listing_posts(data)}


def cmd_post(a):
    pid = parse_post_id(a.target)
    data = api_get(f"/comments/{pid}", {"limit": a.comments, "depth": a.depth, "sort": a.sort})
    post = shape_post(data[0]["data"]["children"][0]["data"])
    post["selftext"] = data[0]["data"]["children"][0]["data"].get("selftext") or None
    return {"post": post, "comments": shape_comments(data[1]["data"]["children"], a.depth)}


def build_parser():
    p = argparse.ArgumentParser(description="Read-only Reddit client")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("search", help="search posts")
    s.add_argument("query")
    s.add_argument("--sub")
    s.add_argument("--sort", default="relevance",
                   choices=["relevance", "hot", "top", "new", "comments"])
    s.add_argument("--time", default="all", choices=TIME_CHOICES)
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(fn=cmd_search)

    l = sp.add_parser("listing", help="list a subreddit's posts")
    l.add_argument("sub")
    l.add_argument("--sort", default="hot",
                   choices=["hot", "new", "top", "rising", "controversial"])
    l.add_argument("--time", default="day", choices=TIME_CHOICES)
    l.add_argument("--limit", type=int, default=10)
    l.set_defaults(fn=cmd_listing)

    c = sp.add_parser("post", help="fetch a post and its comments")
    c.add_argument("target", help="post id, t3_ id, or reddit URL")
    c.add_argument("--comments", type=int, default=20)
    c.add_argument("--depth", type=int, default=2)
    c.add_argument("--sort", default="top",
                   choices=["confidence", "top", "new", "controversial", "old", "qa"])
    c.set_defaults(fn=cmd_post)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    if hasattr(a, "limit"):
        a.limit = max(1, min(a.limit, 100))
    try:
        result = a.fn(a)
    except RedditError as e:
        json.dump({"error": str(e)}, sys.stdout)
        print()
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

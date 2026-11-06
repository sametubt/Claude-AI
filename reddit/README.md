# Reddit skill (read-only)

Lets Claude search Reddit, list subreddit posts, and read comment threads. Skill instructions live in `.claude/skills/reddit/SKILL.md`; the client is `reddit/scripts/reddit.py` (Python 3, standard library only).

## Getting credentials

Reddit ended self-service API keys in November 2025. New Data API access now needs approval under Reddit's Responsible Builder Policy, and the approval can take days or longer.

- If you already have a "script" or "web app" registered at https://www.reddit.com/prefs/apps from before that change, its client ID and secret may still work.
- Otherwise, request access through Reddit's developer support/Data API request process, describing this as a personal, non-commercial, read-only tool.

Then set:

```bash
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
export REDDIT_USER_AGENT="script:my-reddit-reader:0.1 (by /u/yourname)"
```

Without credentials the script falls back to Reddit's public `.json` pages, which work from a home connection for light use but are often blocked from cloud servers.

## Usage

```bash
python3 reddit/scripts/reddit.py search "golf swing tips" --sub golf --limit 5
python3 reddit/scripts/reddit.py listing golf --sort new
python3 reddit/scripts/reddit.py post <post id or URL>
```

Or just ask Claude: "What does r/golf think of the Ping G430?"

## Install outside this repo

```bash
mkdir -p ~/.claude/skills/reddit
cp .claude/skills/reddit/SKILL.md ~/.claude/skills/reddit/
cp -r reddit/scripts ~/.claude/skills/reddit/
```

Then change the script path in the copied SKILL.md to `~/.claude/skills/reddit/scripts/reddit.py`.

"""SET100 scanner: fetches price + fundamentals via yfinance and scores each stock."""

from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Optional

import yfinance as yf

from set100 import get_set100

log = logging.getLogger("scanner")


@dataclass
class StockResult:
    ticker: str
    yahoo_ticker: str
    name: str
    sector: str
    price: Optional[float]
    pe: Optional[float]
    pb: Optional[float]
    dividend_yield: Optional[float]   # percent, e.g. 5.4
    week52_high: Optional[float]
    week52_low: Optional[float]
    market_cap: Optional[float]       # THB
    score: int
    signal: str
    thesis: str
    error: Optional[str] = None


def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _score(pe, pb, divy, price, lo52, mcap) -> int:
    pts = 0
    if pe is not None and pe > 0:
        if pe < 10:
            pts += 30
        elif pe < 15:
            pts += 15
    if divy is not None:
        if divy > 6:
            pts += 25
        elif divy >= 4:
            pts += 12
    if pb is not None and pb > 0 and pb < 1.0:
        pts += 20
    if price and lo52 and lo52 > 0:
        if price <= lo52 * 1.10:
            pts += 15
    if mcap is not None and mcap > 100_000_000_000:
        pts += 10
    return min(pts, 100)


def _signal(score: int) -> str:
    if score >= 70:
        return "Strong Buy"
    if score >= 50:
        return "Buy"
    if score >= 30:
        return "Hold"
    return "Avoid"


def _thesis(r: StockResult) -> str:
    bits: list[str] = []
    if r.pe is not None and r.pe > 0:
        if r.pe < 10:
            bits.append(f"Trading at deep-value P/E of {r.pe:.1f}")
        elif r.pe < 15:
            bits.append(f"Reasonable valuation at P/E {r.pe:.1f}")
        else:
            bits.append(f"Premium valuation at P/E {r.pe:.1f}")
    if r.dividend_yield is not None:
        if r.dividend_yield > 6:
            bits.append(f"high {r.dividend_yield:.1f}% dividend yield")
        elif r.dividend_yield >= 4:
            bits.append(f"solid {r.dividend_yield:.1f}% dividend yield")
    if r.pb is not None and r.pb > 0 and r.pb < 1.0:
        bits.append(f"trading below book value (P/B {r.pb:.2f})")
    if r.price and r.week52_low and r.price <= r.week52_low * 1.10:
        bits.append(f"price near 52w low ({r.week52_low:.2f})")
    if r.market_cap and r.market_cap > 100_000_000_000:
        bits.append("large-cap stability")

    if not bits:
        return f"{r.name} shows no strong value signals at current levels — typical SET100 metrics."

    sig_text = {
        "Strong Buy": "Strong Buy candidate:",
        "Buy":        "Buy candidate:",
        "Hold":       "Hold:",
        "Avoid":      "Avoid:",
    }[r.signal]
    return f"{sig_text} {r.name} — " + "; ".join(bits) + "."


def _fetch_one(item: dict) -> StockResult:
    yt = item["yahoo_ticker"]
    try:
        t = yf.Ticker(yt)
        info = t.info or {}

        price = _safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        pe = _safe_float(info.get("trailingPE") or info.get("forwardPE"))
        pb = _safe_float(info.get("priceToBook"))
        raw_divy = _safe_float(info.get("dividendYield"))
        # yfinance sometimes returns yield as 0.054 (frac) and sometimes 5.4 (%).
        divy = None
        if raw_divy is not None:
            divy = raw_divy * 100 if raw_divy < 1 else raw_divy
        hi = _safe_float(info.get("fiftyTwoWeekHigh"))
        lo = _safe_float(info.get("fiftyTwoWeekLow"))
        mcap = _safe_float(info.get("marketCap"))

        score = _score(pe, pb, divy, price, lo, mcap)
        sig = _signal(score)

        result = StockResult(
            ticker=item["ticker"],
            yahoo_ticker=yt,
            name=item["name"],
            sector=item["sector"],
            price=price,
            pe=pe,
            pb=pb,
            dividend_yield=divy,
            week52_high=hi,
            week52_low=lo,
            market_cap=mcap,
            score=score,
            signal=sig,
            thesis="",
        )
        result.thesis = _thesis(result)
        return result
    except Exception as e:  # noqa: BLE001
        log.warning("fetch failed for %s: %s", yt, e)
        return StockResult(
            ticker=item["ticker"],
            yahoo_ticker=yt,
            name=item["name"],
            sector=item["sector"],
            price=None, pe=None, pb=None, dividend_yield=None,
            week52_high=None, week52_low=None, market_cap=None,
            score=0, signal="Avoid",
            thesis=f"Data unavailable for {item['name']}.",
            error=str(e),
        )


def scan_all(max_workers: int = 8) -> list[dict]:
    """Scan all SET100 constituents in parallel and return list of dicts."""
    constituents = get_set100()
    results: list[StockResult] = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_one, c): c for c in constituents}
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r.score, reverse=True)
    log.info("scan complete: %d stocks in %.1fs", len(results), time.time() - start)
    return [asdict(r) for r in results]


def scan_one(ticker: str) -> Optional[dict]:
    """Look up a single ticker (case-insensitive) and fetch fresh data."""
    t = ticker.upper().replace(".BK", "")
    for c in get_set100():
        if c["ticker"] == t:
            r = _fetch_one(c)
            return asdict(r)
    return None

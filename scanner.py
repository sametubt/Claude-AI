"""SET100 scanner v2: sector-aware value+quality scoring with dividend-trap detection.

Scoring buckets (max 100):
  Value (35)     : P/E, P/B, EV/EBITDA  -- sector-weighted
  Quality (30)   : ROE, Debt/Equity, positive earnings
  Yield (25)     : dividend yield gated by payout ratio
  Technical (10) : 52w-low proximity + 1y momentum sanity (no falling knives)

Sector overrides:
  Bank       : skip EV/EBITDA + D/E (interest is product, not financing); double-weight P/B; ROE bonus
  Energy     : half-weight P/E (cyclical earnings noise); EV/EBITDA primary
  Property   : half-weight P/E; relaxed D/E threshold

Flags:
  DIV TRAP      : div yield > 8% AND payout > 100%
  SPECIAL DIV?  : div yield > 15% (likely one-off, capped credit)
  FALLING KNIFE : 1y return < -40% (penalty applied)
  LOSS          : negative TTM earnings
"""

from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
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
    ev_ebitda: Optional[float]
    dividend_yield: Optional[float]    # percent, e.g. 5.4
    payout_ratio: Optional[float]      # percent, e.g. 65.0
    roe: Optional[float]               # percent, e.g. 18.2
    debt_to_equity: Optional[float]    # ratio, e.g. 0.85
    week52_high: Optional[float]
    week52_low: Optional[float]
    return_1y: Optional[float]         # percent
    market_cap: Optional[float]        # THB
    earnings_positive: Optional[bool]
    score: int
    signal: str
    flags: list[str] = field(default_factory=list)
    data_quality: str = "LOW"          # HIGH / MED / LOW
    thesis: str = ""
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


def _norm_pct(v: Optional[float]) -> Optional[float]:
    """yfinance reports some ratios as fraction (0.18) and some as percent (18.0).
    Heuristic: if |v| < 1, treat as fraction and scale to percent; else assume percent."""
    if v is None:
        return None
    return v * 100 if abs(v) < 1 else v


def _norm_ratio(v: Optional[float]) -> Optional[float]:
    """yfinance debtToEquity is reported as percent (e.g. 85 = 0.85). Normalize to ratio."""
    if v is None:
        return None
    return v / 100 if v > 5 else v


def _data_quality(r: dict) -> str:
    fields_present = ["pe", "pb", "ev_ebitda", "dividend_yield",
                      "payout_ratio", "roe", "debt_to_equity"]
    have = sum(1 for f in fields_present if r.get(f) is not None)
    if have >= 6:
        return "HIGH"
    if have >= 4:
        return "MED"
    return "LOW"


def _score(r: dict) -> tuple[int, list[str]]:
    pts = 0
    flags: list[str] = []
    sector = r["sector"]
    is_bank = sector == "Bank"
    is_cyclical = sector in ("Energy", "Property")

    pe = r["pe"]; pb = r["pb"]; ev = r["ev_ebitda"]
    divy = r["dividend_yield"]; payout = r["payout_ratio"]
    roe = r["roe"]; de = r["debt_to_equity"]
    price = r["price"]; lo52 = r["week52_low"]
    ret1y = r["return_1y"]; ep = r["earnings_positive"]

    # ---- VALUE (max 35) ----
    pe_mul = 0.5 if is_cyclical else 1.0
    if pe is not None and pe > 0:
        if pe < 10:
            pts += int(12 * pe_mul)
        elif pe < 15:
            pts += int(6 * pe_mul)

    pb_mul = 2.0 if is_bank else 1.0
    if pb is not None and pb > 0:
        if pb < 1.0:
            pts += int(8 * pb_mul)
        elif pb < 1.5:
            pts += int(4 * pb_mul)

    if not is_bank and ev is not None and ev > 0:
        if ev < 8:
            pts += 15
        elif ev < 12:
            pts += 7

    # ---- QUALITY (max 30) ----
    if roe is not None:
        if roe > 15:
            pts += 15
        elif roe > 10:
            pts += 8
        if is_bank and roe > 12:
            pts += 5  # banks live on ROE

    if not is_bank and de is not None and de >= 0:
        de_threshold_low = 1.5 if sector == "Property" else 1.0
        de_threshold_mid = 2.5 if sector == "Property" else 2.0
        if de < de_threshold_low:
            pts += 10
        elif de < de_threshold_mid:
            pts += 5

    if ep is True:
        pts += 5
    elif ep is False:
        flags.append("LOSS")

    # ---- YIELD (max 25) ----
    if divy is not None and divy > 0:
        if divy > 15:
            pts += 5
            flags.append("SPECIAL DIV?")
        elif divy > 8:
            if payout is not None and payout > 100:
                flags.append("DIV TRAP")
            elif payout is not None and payout < 80:
                pts += 20
            else:
                pts += 12
        elif divy >= 4:
            if payout is None:
                pts += 12
            elif payout < 80:
                pts += 25
            elif payout <= 100:
                pts += 12
            else:
                flags.append("DIV TRAP")

    # ---- TECHNICAL (max 10) ----
    if price and lo52 and lo52 > 0 and price <= lo52 * 1.10:
        pts += 5
    if ret1y is not None:
        if -20 <= ret1y <= 5:
            pts += 5
        elif ret1y < -40:
            pts -= 5
            flags.append("FALLING KNIFE")

    return max(0, min(pts, 100)), flags


def _signal(score: int) -> str:
    if score >= 70:
        return "Strong Buy"
    if score >= 50:
        return "Buy"
    if score >= 30:
        return "Hold"
    return "Avoid"


def _thesis(r: dict) -> str:
    if "DIV TRAP" in r["flags"]:
        py = f"{r['payout_ratio']:.0f}%" if r["payout_ratio"] is not None else "n/a"
        return (f"DIV TRAP: {r['name']} — {r['dividend_yield']:.1f}% yield with payout "
                f"{py} looks unsustainable. Skip unless you have a specific catalyst.")
    if "FALLING KNIFE" in r["flags"] and r["return_1y"] is not None:
        return (f"FALLING KNIFE: {r['name']} — down {abs(r['return_1y']):.0f}% over 1y. "
                f"Value signals present but wait for stabilization.")

    bits: list[str] = []
    s = r["sector"]

    if r["pe"] is not None and r["pe"] > 0:
        if r["pe"] < 10:
            bits.append(f"deep-value P/E {r['pe']:.1f}")
        elif r["pe"] < 15:
            bits.append(f"reasonable P/E {r['pe']:.1f}")

    if s != "Bank" and r["ev_ebitda"] is not None and r["ev_ebitda"] > 0:
        if r["ev_ebitda"] < 8:
            bits.append(f"cheap EV/EBITDA {r['ev_ebitda']:.1f}")
        elif r["ev_ebitda"] < 12:
            bits.append(f"fair EV/EBITDA {r['ev_ebitda']:.1f}")

    if r["pb"] is not None and r["pb"] > 0:
        if r["pb"] < 1.0:
            bits.append(f"below book (P/B {r['pb']:.2f})")
        elif s == "Bank" and r["pb"] < 1.2:
            bits.append(f"P/B {r['pb']:.2f}")

    if r["roe"] is not None:
        if r["roe"] > 15:
            bits.append(f"strong ROE {r['roe']:.1f}%")
        elif r["roe"] > 10:
            bits.append(f"solid ROE {r['roe']:.1f}%")

    if s != "Bank" and r["debt_to_equity"] is not None and r["debt_to_equity"] < 0.5:
        bits.append(f"low leverage (D/E {r['debt_to_equity']:.2f})")

    if r["dividend_yield"] is not None and r["dividend_yield"] >= 4:
        if r["payout_ratio"] is not None and r["payout_ratio"] < 80:
            bits.append(f"sustainable {r['dividend_yield']:.1f}% yield "
                        f"(payout {r['payout_ratio']:.0f}%)")
        else:
            bits.append(f"{r['dividend_yield']:.1f}% yield")

    if r["price"] and r["week52_low"] and r["price"] <= r["week52_low"] * 1.10:
        bits.append(f"near 52w low ({r['week52_low']:.2f})")

    if r["return_1y"] is not None and -20 <= r["return_1y"] <= 5:
        bits.append("range-bound (mean-reversion setup)")

    flag_note = ""
    if r["flags"]:
        flag_note = f" Flags: {', '.join(r['flags'])}."

    if not bits:
        return f"{r['name']} ({s}) shows no strong value/quality signals at current levels.{flag_note}"

    sig = r["signal"]
    return f"{sig} ({s}): {r['name']} — " + ", ".join(bits) + "." + flag_note


def _fetch_one(item: dict) -> StockResult:
    yt = item["yahoo_ticker"]
    err: Optional[str] = None
    info: dict = {}
    try:
        t = yf.Ticker(yt)
        info = t.info or {}
    except Exception as e:  # noqa: BLE001
        log.warning("info fetch failed for %s: %s", yt, e)
        err = str(e)

    price = _safe_float(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    pe = _safe_float(info.get("trailingPE") or info.get("forwardPE"))
    pb = _safe_float(info.get("priceToBook"))
    ev_ebitda = _safe_float(info.get("enterpriseToEbitda"))

    divy = _norm_pct(_safe_float(info.get("dividendYield")))
    payout = _norm_pct(_safe_float(info.get("payoutRatio")))
    roe = _norm_pct(_safe_float(info.get("returnOnEquity")))
    de = _norm_ratio(_safe_float(info.get("debtToEquity")))

    hi = _safe_float(info.get("fiftyTwoWeekHigh"))
    lo = _safe_float(info.get("fiftyTwoWeekLow"))
    mcap = _safe_float(info.get("marketCap"))

    ret1y_raw = _safe_float(info.get("52WeekChange"))
    ret1y = ret1y_raw * 100 if ret1y_raw is not None else None

    eps = _safe_float(info.get("trailingEps"))
    earnings_positive: Optional[bool] = None
    if eps is not None:
        earnings_positive = eps > 0

    raw = {
        "sector": item["sector"],
        "price": price, "pe": pe, "pb": pb, "ev_ebitda": ev_ebitda,
        "dividend_yield": divy, "payout_ratio": payout,
        "roe": roe, "debt_to_equity": de,
        "week52_high": hi, "week52_low": lo,
        "return_1y": ret1y, "market_cap": mcap,
        "earnings_positive": earnings_positive,
    }

    score, flags = _score(raw)
    sig = _signal(score)
    dq = _data_quality(raw)

    result = StockResult(
        ticker=item["ticker"],
        yahoo_ticker=yt,
        name=item["name"],
        sector=item["sector"],
        price=price, pe=pe, pb=pb, ev_ebitda=ev_ebitda,
        dividend_yield=divy, payout_ratio=payout,
        roe=roe, debt_to_equity=de,
        week52_high=hi, week52_low=lo,
        return_1y=ret1y, market_cap=mcap,
        earnings_positive=earnings_positive,
        score=score, signal=sig,
        flags=flags, data_quality=dq,
        thesis="", error=err,
    )
    # Build thesis from the resolved object
    result.thesis = _thesis({**raw, "name": result.name, "signal": sig, "flags": flags})
    return result


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
    t = ticker.upper().replace(".BK", "")
    for c in get_set100():
        if c["ticker"] == t:
            return asdict(_fetch_one(c))
    return None

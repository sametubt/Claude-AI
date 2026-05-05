"""SET100 scanner CLI.

Usage:
    python scan.py                       # ranked table of all SET100
    python scan.py --signal strong-buy   # only Strong Buy picks
    python scan.py --sector Bank         # only banks
    python scan.py --top 20              # top 20 by score
    python scan.py --ticker PTT          # detail card for one stock
    python scan.py --refresh             # force rescan (ignore 15min cache)
    python scan.py --json                # JSON output (pipe-friendly)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scanner import scan_all, scan_one

CACHE_FILE = Path(__file__).parent / ".scan_cache.json"
CACHE_TTL = 15 * 60

console = Console()

SIGNAL_STYLE = {
    "Strong Buy": "bold black on green",
    "Buy":        "green",
    "Hold":       "yellow",
    "Avoid":      "red",
}


def _load_cache() -> list[dict] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        if time.time() - data["ts"] < CACHE_TTL:
            return data
    except Exception:  # noqa: BLE001
        pass
    return None


def _save_cache(results: list[dict]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps({"ts": time.time(), "results": results}))
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]warning: could not write cache: {e}[/yellow]")


def get_results(refresh: bool) -> list[dict]:
    if not refresh:
        cached = _load_cache()
        if cached:
            age = int(time.time() - cached["ts"])
            console.print(f"[dim]> using cached scan ({age}s old; --refresh to update)[/dim]")
            return cached["results"]
    console.print("[bold green]> scanning SET100...[/bold green] [dim](30-60s)[/dim]")
    with console.status("[green]fetching from yahoo finance...[/green]", spinner="dots"):
        results = scan_all()
    _save_cache(results)
    return results


def _num(v, d=2):
    return f"{v:.{d}f}" if v is not None else "—"


def _bn(v):
    return f"{v/1e9:.1f}" if v is not None else "—"


def _score_style(score: int) -> str:
    if score >= 70: return "bold green"
    if score >= 50: return "green"
    if score >= 30: return "yellow"
    return "red"


def render_table(results: list[dict], top: int | None = None) -> None:
    table = Table(
        show_lines=False,
        header_style="bold green",
        border_style="green",
        title_style="bold green",
        row_styles=["", "on grey7"],
    )
    table.add_column("TICKER", style="bold green", no_wrap=True)
    table.add_column("SECTOR", style="dim cyan", no_wrap=True)
    table.add_column("PRICE", justify="right", no_wrap=True)
    table.add_column("P/E", justify="right", no_wrap=True)
    table.add_column("P/B", justify="right", no_wrap=True)
    table.add_column("ROE%", justify="right", no_wrap=True)
    table.add_column("DIV%", justify="right", no_wrap=True)
    table.add_column("MCap(B)", justify="right", no_wrap=True)
    table.add_column("SCORE", justify="right", no_wrap=True)
    table.add_column("SIGNAL", no_wrap=True)
    table.add_column("FLAGS", style="red", no_wrap=False)

    rows = results[:top] if top else results
    for r in rows:
        sig_style = SIGNAL_STYLE.get(r["signal"], "white")
        sig_text = Text(f" {r['signal']} ", style=sig_style)
        score_text = Text(str(r["score"]), style=_score_style(r["score"]))
        flags = " ".join(r.get("flags") or [])
        table.add_row(
            r["ticker"],
            r["sector"],
            _num(r["price"]),
            _num(r["pe"], 1),
            _num(r["pb"], 2),
            _num(r["roe"], 1),
            _num(r["dividend_yield"], 2),
            _bn(r["market_cap"]),
            score_text,
            sig_text,
            flags,
        )
    console.print(table)


def render_detail(r: dict) -> None:
    sig_style = SIGNAL_STYLE.get(r["signal"], "white")
    flags = ", ".join(r.get("flags") or []) or "[dim]none[/dim]"
    div_part = f"{_num(r['dividend_yield'], 2)}%"
    payout_part = f"{_num(r['payout_ratio'], 1)}%"
    roe_part = f"{_num(r['roe'], 1)}%"
    ret1y_part = f"{_num(r['return_1y'], 1)}%"

    body = (
        f"[bold]Price:[/bold] {_num(r['price'])}    "
        f"[bold]52w range:[/bold] {_num(r['week52_low'])} – {_num(r['week52_high'])}\n"
        f"\n"
        f"[bold cyan]VALUATION[/bold cyan]\n"
        f"  P/E         {_num(r['pe'], 1):>10}\n"
        f"  P/B         {_num(r['pb'], 2):>10}\n"
        f"  EV/EBITDA   {_num(r['ev_ebitda'], 1):>10}\n"
        f"\n"
        f"[bold cyan]QUALITY[/bold cyan]\n"
        f"  ROE         {roe_part:>10}\n"
        f"  D/E         {_num(r['debt_to_equity'], 2):>10}\n"
        f"\n"
        f"[bold cyan]YIELD[/bold cyan]\n"
        f"  Div Yield   {div_part:>10}\n"
        f"  Payout      {payout_part:>10}\n"
        f"\n"
        f"[bold cyan]CONTEXT[/bold cyan]\n"
        f"  Market Cap  {_bn(r['market_cap']):>9} B THB\n"
        f"  1y return   {ret1y_part:>10}\n"
        f"  Data        {r.get('data_quality', '—'):>10}\n"
        f"\n"
        f"[bold]Score:[/bold] [{_score_style(r['score'])}]{r['score']}/100[/{_score_style(r['score'])}]    "
        f"[bold]Signal:[/bold] [{sig_style}] {r['signal']} [/{sig_style}]\n"
        f"[bold]Flags:[/bold]  {flags}\n"
        f"\n"
        f"[italic green]{r['thesis']}[/italic green]"
    )
    title = f"[bold green]{r['ticker']}[/bold green]  [white]{r['name']}[/white]  [dim]({r['sector']})[/dim]"
    console.print(Panel(body, title=title, border_style="green", padding=(1, 2)))


def main() -> int:
    p = argparse.ArgumentParser(
        description="SET100 stock scanner — terminal edition.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python scan.py
  python scan.py --signal strong-buy --top 10
  python scan.py --sector Bank
  python scan.py --ticker PTT
  python scan.py --refresh --json > scan.json
""",
    )
    p.add_argument("--signal", choices=["all", "strong-buy", "buy", "hold", "avoid"],
                   default="all", help="filter by signal tier")
    p.add_argument("--sector", help="filter by sector (Bank/Energy/Property/Telecom/Food/Other)")
    p.add_argument("--ticker", help="show full detail card for a single ticker")
    p.add_argument("--top", type=int, help="show only top N results")
    p.add_argument("--refresh", action="store_true", help="force fresh scan, ignore 15min cache")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args()

    if args.ticker:
        result = scan_one(args.ticker)
        if not result:
            console.print(f"[red]ticker '{args.ticker}' not in SET100 list[/red]")
            return 1
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            render_detail(result)
        return 0

    results = get_results(args.refresh)

    sig_map = {"strong-buy": "Strong Buy", "buy": "Buy", "hold": "Hold", "avoid": "Avoid"}
    if args.signal != "all":
        results = [r for r in results if r["signal"] == sig_map[args.signal]]
    if args.sector:
        results = [r for r in results if r["sector"].lower() == args.sector.lower()]

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return 0

    n_strong = sum(1 for r in results if r["signal"] == "Strong Buy")
    n_buy = sum(1 for r in results if r["signal"] == "Buy")
    n_hold = sum(1 for r in results if r["signal"] == "Hold")
    n_avoid = sum(1 for r in results if r["signal"] == "Avoid")

    console.print()
    console.rule("[bold green]SET100 SCANNER[/bold green]", style="green")
    console.print(
        f"[dim]{len(results)} results  ·  "
        f"[bold green]{n_strong}[/bold green] strong buy  ·  "
        f"[green]{n_buy}[/green] buy  ·  "
        f"[yellow]{n_hold}[/yellow] hold  ·  "
        f"[red]{n_avoid}[/red] avoid[/dim]"
    )
    console.print()
    render_table(results, top=args.top)
    console.print()
    console.print("[dim]> tip: python scan.py --ticker <SYMBOL> for detail card[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

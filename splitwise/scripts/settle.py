#!/usr/bin/env python3
"""
settle.py - minimum-transfer expense settlement

Reads a JSON spec from stdin, writes a settlement plan to stdout.

Spec:
{
  "people": ["A", "B", ...],
  "currency": "USD",            // optional, display only
  "expenses": [
    {
      "payer": "A",
      "amount": 100.0,
      "split_among": ["A", "B", "C"] | "all",
      "shares": [1, 1, 2],      // optional, parallel to split_among
      "note": "dinner"          // optional
    },
    ...
  ]
}
"""

import base64
import json
import sys
from decimal import Decimal, ROUND_HALF_UP


DASHBOARD_BASE_URL = "https://sametubt.github.io/Claude-AI/"


def make_share_hash(spec):
    """Build the URL-safe base64 hash used by the dashboard."""
    compact = {
        "t": spec.get("title", ""),
        "c": spec.get("currency", ""),
        "p": list(spec.get("people", [])),
        "e": [],
    }
    for exp in spec.get("expenses", []):
        split_among = exp.get("split_among")
        item = {
            "a": exp.get("payer", ""),
            "m": float(exp.get("amount", 0)),
            "g": split_among if split_among == "all" else list(split_among or []),
            "n": exp.get("note", ""),
        }
        if exp.get("shares") is not None:
            item["s"] = [float(s) for s in exp["shares"]]
        compact["e"].append(item)
    raw = json.dumps(compact, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def to_dec(x):
    return Decimal(str(x))


def round2(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_balances(spec):
    people = spec["people"]
    balances = {p: Decimal("0") for p in people}
    paid = {p: Decimal("0") for p in people}
    owed = {p: Decimal("0") for p in people}

    for exp in spec["expenses"]:
        payer = exp["payer"]
        amount = to_dec(exp["amount"])
        split_among = exp["split_among"]
        if split_among == "all":
            split_among = people
        shares = exp.get("shares")
        if shares is None:
            shares = [1] * len(split_among)
        total_shares = sum(to_dec(s) for s in shares)

        if payer not in balances:
            raise ValueError(f"unknown payer: {payer}")

        paid[payer] += amount
        balances[payer] += amount

        for person, share in zip(split_among, shares):
            if person not in balances:
                raise ValueError(f"unknown person in split: {person}")
            portion = amount * to_dec(share) / total_shares
            balances[person] -= portion
            owed[person] += portion

    return balances, paid, owed


def settle(balances):
    """Greedy minimum-transfer settlement. Returns list of (from, to, amount).

    Works with full Decimal precision internally, rounds transfers at the end,
    and adjusts one transfer to absorb sub-cent rounding residue so totals
    reconcile exactly.
    """
    bal = {p: v for p, v in balances.items()}
    raw_transfers = []

    eps = Decimal("0.005")
    while True:
        creditor = max(bal, key=lambda p: bal[p])
        debtor = min(bal, key=lambda p: bal[p])

        if bal[creditor] <= eps and bal[debtor] >= -eps:
            break

        amount = min(bal[creditor], -bal[debtor])
        if amount <= eps:
            break

        raw_transfers.append((debtor, creditor, amount))
        bal[creditor] -= amount
        bal[debtor] += amount

    transfers = [(f, t, round2(a)) for f, t, a in raw_transfers]

    # Reconcile: each person's original balance plus the net effect of
    # rounded transfers should be zero. If rounding caused drift, absorb it
    # into one transfer involving that person.
    if transfers:
        delta = {p: Decimal("0") for p in balances}
        for f, t, a in transfers:
            delta[f] -= a
            delta[t] += a
        # drift = how much p is still owed (positive) or still owes (negative)
        # after applying rounded transfers
        for p in balances:
            drift = balances[p] - delta[p]
            if abs(drift) >= Decimal("0.005"):
                for i, (f, t, a) in enumerate(transfers):
                    if t == p:
                        # p still owed `drift` more, so bump this incoming transfer
                        transfers[i] = (f, t, round2(a + drift))
                        delta[f] -= drift
                        delta[t] += drift
                        break
                    elif f == p:
                        # p still owes `-drift` more, so bump this outgoing transfer
                        transfers[i] = (f, t, round2(a - drift))
                        delta[f] += drift
                        delta[t] -= drift
                        break

    return transfers


def main():
    try:
        spec = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    currency = spec.get("currency", "")
    cur = f" {currency}" if currency else ""

    balances, paid, owed = compute_balances(spec)
    transfers = settle(balances)

    share_hash = make_share_hash(spec)
    dashboard_url = f"{DASHBOARD_BASE_URL}#{share_hash}"

    # Output
    out = {
        "currency": currency,
        "dashboard_url": dashboard_url,
        "net_positions": [
            {
                "person": p,
                "paid": float(round2(paid[p])),
                "owes": float(round2(owed[p])),
                "net": float(round2(balances[p])),
            }
            for p in spec["people"]
        ],
        "transfers": [
            {"from": f, "to": t, "amount": float(a)}
            for f, t, a in transfers
        ],
        "summary": {
            "total_transfers": len(transfers),
            "people_count": len(spec["people"]),
            "people_who_pay_once_or_zero": sum(
                1 for p in spec["people"]
                if sum(1 for f, t, a in transfers if f == p) <= 1
            ),
            "people_who_receive_once_or_zero": sum(
                1 for p in spec["people"]
                if sum(1 for f, t, a in transfers if t == p) <= 1
            ),
        },
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

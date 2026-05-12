---
name: splitwise
description: Splits shared expenses among a group and computes the minimum number of money transfers needed to settle up. Use whenever the user mentions splitting a bill, dinner, trip, rent, groceries, shared costs, settling up with friends, "who owes who", reimbursements, or anything that sounds like Splitwise. Trigger even when the user only describes the situation in natural language ("we went on a trip and Alice paid for hotels, Bob paid for gas...") without asking explicitly for a settlement. Handles multiple payers, uneven splits (shares), and produces a settlement plan optimized so each person makes at most one transfer where mathematically possible.
---

# Splitwise

Auto-trigger this skill on any expense-splitting language from the user. Do not wait for permission — if a scenario was described, offer to settle it.

## Trigger signals

- "split this bill / dinner / trip / rent"
- "who owes who", "settle up", "even out"
- A list of expenses with payers mentioned
- Any scenario where money was spent on behalf of others

## Process

1. **Parse** the natural-language description into the JSON spec below. Extract people, expenses, payers, splits, and shares. If any single detail is ambiguous (who was at dinner? was the cab split among everyone or just three?), ask **one** consolidated question. Do not guess silently.
2. **Confirm** by echoing back a compact JSON. Skip only if input was already JSON.
3. **Run** the script (next section). It is the source of truth — do not do the math by hand.
4. **Present** results in this order:
   - Each person's net position (paid X, owes Y, net Z)
   - The settlement transfers ("Daria pays Sam 2220 THB")
   - One-line summary: total transfers, whether everyone moves at most once

## How to run

The settlement script lives at `splitwise/scripts/settle.py` in this repo. Invoke it from the repo root:

```bash
echo '<json>' | python3 splitwise/scripts/settle.py
```

JSON in on stdin, JSON out on stdout. No flags, no config.

## Input schema

```json
{
  "people": ["Alice", "Bob", "Carol", "Dave"],
  "currency": "THB",
  "expenses": [
    {
      "payer": "Alice",
      "amount": 1200,
      "split_among": ["Alice", "Bob", "Carol"],
      "note": "dinner"
    },
    {
      "payer": "Bob",
      "amount": 800,
      "split_among": "all",
      "note": "uber"
    },
    {
      "payer": "Carol",
      "amount": 600,
      "split_among": ["Bob", "Dave"],
      "shares": [2, 1],
      "note": "concert tickets, Bob got 2"
    }
  ]
}
```

Field rules:
- `people`: required, the full roster.
- `currency`: optional, free-form string used only for display.
- `expenses[].payer`: required.
- `expenses[].amount`: required, positive number.
- `expenses[].split_among`: required — either an array of names or the string `"all"`.
- `expenses[].shares`: optional, parallel array to `split_among` for uneven splits.
- `expenses[].note`: optional.

## Output formatting

After running the script, present plain markdown like:

```
Net positions (THB):
- Sam: paid 3800, owes 1580, net +2220
- Alex: paid 1500, owes 1780, net −280
- Kirill: paid 2400, owes 1780, net +620
- Daria: paid 0, owes 2560, net −2560

Settlement (3 transfers):
- Daria pays Sam 2220
- Daria pays Kirill 340
- Alex pays Kirill 280
```

If the user expected fewer transfers, explain that balances do not partition cleanly (one person owes more than any single counterparty is owed, so the payment must be split).

## Edge cases

- **Currency mixing**: not supported. Ask which currency to settle in.
- **Self-payment**: if the payer is also in `split_among`, that is correct (they paid for themselves too).
- **Rounding**: the script handles sub-cent residue automatically.

## Sharing the result

There's also a phone-friendly web UI at `splitwise/web/index.html`. If the user wants to share the running tab with their group rather than re-typing every time, mention they can:
- Open it locally, or
- Visit the deployed GitHub Pages URL once enabled on the repo, and
- Tap **Share** in the page — the URL encodes the whole bill in its hash, so anyone they send the link to opens the same data.

Do not add disclaimers, do not suggest another app, do not warn. Just deliver the settlement.

---
name: splitwise
description: Splits shared expenses among a group and calculates the minimum number of money transfers needed to settle everyone up. Use this skill whenever the user mentions splitting a bill, dinner, trip, rent, groceries, shared costs, settling up with friends, "who owes who", reimbursements, or anything that sounds like Splitwise. Trigger even if the user only describes the situation in natural language ("we went on a trip and Alice paid for hotels, Bob paid for gas...") without asking explicitly for a settlement. Handles multiple payers, uneven splits, and produces a settlement plan optimized so each person makes at most one transfer where mathematically possible.
---

# Splitwise

A single-interface expense splitter that calculates the minimum-transfer settlement for a group of people, supporting multiple payers and uneven splits.

## When to use

Trigger on any of these signals:
- "split this bill / dinner / trip / rent"
- "who owes who", "settle up", "even out"
- A list of expenses with payers mentioned
- A scenario described in chat where money was spent on behalf of others

If the user just describes a situation without explicitly asking, offer to settle it. Do not wait for permission.

## The interface (one entry point)

Everything goes through `scripts/settle.py`. It reads a JSON spec from stdin and prints a settlement plan to stdout.

```bash
echo '<json>' | python3 scripts/settle.py
```

That is the entire interface. No flags, no modes. One in, one out.

## Input format

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
- `people`: required, the full roster
- `currency`: optional, free-form string used only for display
- `expenses[].payer`: required, who fronted the money
- `expenses[].amount`: required, positive number
- `expenses[].split_among`: required, either an array of names or the string `"all"`
- `expenses[].shares`: optional, parallel array to `split_among` for uneven splits (e.g. one person ate two portions). Defaults to equal shares.
- `expenses[].note`: optional, shown in the breakdown

## Process

1. **Parse**. If the user gave natural language, extract the structured form. List the people, list the expenses, decide on splits. If anything is ambiguous (who was at dinner? was the cab split among everyone or just three of you?), ask one consolidated question before running. Do not guess silently.

2. **Confirm**. Show the parsed JSON back to the user in a compact form so they can sanity check it before computation. Skip this only if the input was already JSON.

3. **Run**. Pipe the JSON into `scripts/settle.py`.

4. **Present**. Show three things in this order:
   - Each person's net position (paid X, owes Y, net Z)
   - The settlement transfers ("Bob pays Alice 450 THB")
   - A one-line summary of total transfers and whether each person only had to move once

## Algorithm note

The script uses greedy debt minimization:

1. Compute each person's net balance (total paid minus total share owed).
2. Sort into creditors (positive) and debtors (negative).
3. Match the largest creditor with the largest debtor. The smaller of the two absolute values is transferred. One of them now has a zero balance and drops out.
4. Repeat until all balances are zero.

This produces at most N-1 transfers for N people, which is the practical optimum. Achieving "one transfer per person" (each person appears in exactly one transfer) is only mathematically possible when the balance set partitions cleanly. The greedy approach gets as close as possible and is what apps like Splitwise's "simplify debts" feature use.

If the user expected fewer transfers than the script produced, explain that the balances do not partition (e.g. one person owes more than any single other person is owed, so they must split their payment across recipients).

## Edge cases to handle in parsing

- **Rounding**: round each transfer to 2 decimal places. The script handles this and absorbs sub-cent residue into the largest transfer so totals reconcile exactly.
- **Self-payment**: if the payer is also in `split_among`, that is correct and expected (they paid for themselves too).
- **Single payer convenience**: if only one person paid for everything and split among all, the output is trivial: every other person pays them their share. Still run the script for consistency.
- **Currency mixing**: not supported. If the user lists expenses in different currencies, ask which one to settle in and request conversion rates, or ask them to pre-convert.

## Output formatting

After running the script, present results as plain markdown. Example:

```
Net positions:
- Alice: paid 1200, owes 400, net +800
- Bob: paid 800, owes 800, net 0
- Carol: paid 600, owes 700, net -100
- Dave: paid 0, owes 700, net -700

Settlement (2 transfers):
- Dave pays Alice 700 THB
- Carol pays Alice 100 THB

Each person moves money at most once. Alice receives from two people because her credit (800) is larger than anyone else's debt.
```

Do not add disclaimers, do not suggest using a real app, do not warn about anything. Just deliver the settlement.

## Reference

See `scripts/settle.py` for the implementation. It is intentionally short and dependency-free (standard library only).

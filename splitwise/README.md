# Splitwise skill for Claude Code

A single-interface expense splitter. You describe who paid what, Claude figures out the minimum-transfer settlement and tells you who pays who.

## Install

```bash
# Drop the whole folder into your Claude Code skills directory
mkdir -p ~/.claude/skills
cp -r splitwise ~/.claude/skills/
```

That is the only setup. Claude Code auto-discovers SKILL.md files in `~/.claude/skills/` and loads them when relevant.

## Prompts to use

The skill triggers automatically on any expense-splitting language. Just describe the situation:

```
We had dinner last night, I paid 3200 baht for all four of us. Alex paid
1500 for the taxi but I took a Grab separately. Kirill got concert tickets,
2400 total, Daria got 2 tickets and the rest of us got one each. I also
bought coffee for me and Daria, 600. Who owes who?
```

Or be terse:

```
Sam paid 3200 for dinner (4 of us), Alex 1500 taxi (3 of us, no Sam),
Kirill 2400 concert (Daria 2 shares, rest 1), Sam 600 coffee (Sam + Daria).
Settle it.
```

Or hand it the JSON directly if you already have it structured (see `examples/trip.json`).

## Direct CLI use (without Claude)

If you just want to run it manually:

```bash
cat examples/trip.json | python3 scripts/settle.py
```

The script takes JSON on stdin and writes JSON to stdout. No flags, no config, no dependencies beyond Python 3 standard library.

## What you get back

Three things, in order:
1. Each person's net position (paid, owes, net)
2. The list of transfers ("X pays Y amount")
3. A summary line confirming the transfer count

## How the optimization works

The script computes each person's net balance, then runs greedy debt minimization: match the biggest creditor with the biggest debtor, settle the smaller of the two, repeat. This produces at most N-1 transfers for N people, which is the practical optimum.

A person can sometimes appear in more than one transfer when their balance does not match any single counterparty's balance. For example, if you are owed 2220 but the biggest debtor only owes 2560, that debtor pays you 2220 then has to send the remaining 340 to someone else. There is no way around this without splitting the original payment differently.

## File layout

```
splitwise/
├── SKILL.md              # the skill definition Claude Code reads
├── README.md             # this file
├── scripts/
│   └── settle.py         # the algorithm, ~120 lines, stdlib only
└── examples/
    └── trip.json         # sample input you can pipe in to test
```

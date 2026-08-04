# SET Sector Rotation Dashboard

A sector-rotation dashboard for the Thai market (SET), built as two static files
with no build step, no dependencies, and no network calls. Everything — the data
model, the RRG maths, and all four charts — runs in the browser.

Published at `/set-rotation/` by the repo's GitHub Pages workflow.

## What's on it

| Panel | What it answers |
|---|---|
| **Relative Rotation Graph** | Where each group sits on relative strength (x) vs the momentum of that strength (y), with a tail showing how it got there. |
| **Rotation Leaderboard** | Which groups are strongest right now, how each one moved since the last period, and how the universe is spread across the four quadrants. |
| **Quadrant History** | Each group's quadrant over the last 26 periods, so you can see a rotation develop instead of guessing from one snapshot. |
| **Relative Strength vs SET** | Each group's price relative to the benchmark, rebased to 100 — the underlying series the RRG is computed from. |
| **Data table** | Every value at the selected date, sortable. This is the accessible twin for the charts above. |

A date scrubber (with playback) drives all five together, so the numbers always
agree with each other.

## The maths

For each group, against the benchmark:

```
rs        = 100 × price / benchmark
ratioRaw  = 100 × EMA(rs, 10) / EMA(rs, 30)
RS-Ratio  = 100 + rolling z-score(ratioRaw, 60)
momRaw    = 100 × RS-Ratio[t] / RS-Ratio[t−5]
RS-Mom    = 100 + rolling z-score(momRaw, 60)
```

Both axes are centred on 100, so 100/100 is the benchmark itself and the quadrant
is read from the signs of the two deviations:

| Quadrant | RS-Ratio | RS-Mom | Reading |
|---|---|---|---|
| ↗ Leading | > 100 | > 100 | strong and still gaining |
| ↘ Weakening | > 100 | < 100 | strong, losing momentum |
| ↙ Lagging | < 100 | < 100 | weak and still falling behind |
| ↖ Improving | < 100 | > 100 | weak but turning up |

The RRG uses **one shared scale on both axes**, so the heading angle and the
distance from the centre — both reported in the data table — are geometrically
true rather than artefacts of independent axis scaling.

Weekly mode resamples to the last business day of each week before computing.
If a series is too short to carry the standard 10/30/60 windows (a small upload,
or its weekly resample), the windows shrink proportionally and the UI says so;
if even that leaves nothing computable, the dashboard says that instead of
drawing placeholder points.

## Data

Ships with a **deterministic demo series** — roughly seven years of synthetic
business-day closes for the SET benchmark, the 8 industry groups, and 8 key
sectors, generated from a fixed seed so the page looks the same on every load.
It is labelled as demo data throughout. It is not real market data.

To use real prices, click **CSV** and load a wide-format file. The first column
is the date, **the second column is treated as the benchmark**, and every further
column is a group:

```csv
date,SET,BANK,ENERG,ICT,FOOD
2025-01-02,1385.21,412.90,22140.5,178.33,11902.7
2025-01-03,1379.88,410.12,22088.1,179.90,11888.4
```

Up to 24 groups; at least 40 usable rows. The file is read locally and never
leaves the browser.

## Design notes

Colour carries two different jobs here, kept strictly separate:

- **Sector identity** uses 8 fixed categorical slots assigned by position in the
  universe, never by rank — so toggling a series off never repaints the others.
  These appear only in the Relative Strength chart, where a legend and
  end-of-line labels carry identity alongside the colour.
- **Quadrant state** uses a 4-value status palette. Its red↔green pair is not
  separable under deuteranopia (ΔE 4.1), so a quadrant is **never** colour alone:
  every quadrant mark ships a directional arrow (↗ ↘ ↙ ↖) and, wherever there is
  room, the quadrant's name. The arrows also encode position, which is what the
  quadrant means.

Both palettes were checked with a colourblind-safety validator against the actual
light and dark chart surfaces rather than eyeballed. The dark theme is a selected
set of steps for the dark surface, not an inverted light theme.

## Caveats

An RRG measures **relative price and momentum — not fund flow**. It says nothing
about net buying by any investor group, and nothing about valuation. Rotation is
conventionally clockwise but frequently isn't. This is an educational tool, not
investment advice.

## Files

```
set-rotation/
├── index.html   structure, styles, copy
└── app.js       data model, RRG maths, chart rendering, interaction
```

# Use your own design as the dashboard

You don't have to use my HTML. Drop in any design (Claude artifact, Figma export, hand-written, whatever) and it becomes the dashboard. Three steps.

## 1. Replace the HTML

Take your design and save it as `splitwise/web/index.html`, overwriting what's there. Keep `splitwise/web/splitwise.js` next to it.

## 2. Wire up the data

Inside your `<head>` (or end of `<body>`), include one script tag and call `Splitwise.load()`:

```html
<script src="splitwise.js"></script>
<script>
  const bill = Splitwise.load();
  if (!bill) {
    // No data in URL — show an empty state or instructions.
  } else {
    // bill has everything you need to render:
    //   bill.title          → string ("Trip to Bangkok" or "")
    //   bill.currency       → string ("THB" or "")
    //   bill.people         → ["Sam","Alex",...]
    //   bill.expenses       → [{payer, amount, group, shares, note}, ...]
    //                          group is "all" or an array of names
    //                          shares is null (equal split) or an array of weights
    //   bill.paid           → { Sam: 3800, ... }
    //   bill.owed           → { Sam: 1580, ... }
    //   bill.balances       → { Sam: 2220, ... }  (positive = should receive)
    //   bill.transfers      → [{from, to, amount}, ...]  ← the settlement
    //
    // Render however your design wants.
    document.querySelector("#title").textContent = bill.title || "Settlement";
    // ...etc.
  }
</script>
```

That's it. Your design now reads the bill straight from the URL hash that Claude generated.

## 3. Push and let GitHub Pages deploy

Once merged to `main`, your design lives at:

**https://sametubt.github.io/Claude-AI/**

Every settlement Claude produces will append a hash to that URL, so the same page renders any bill.

## Optional — share button

If you want a native phone share sheet (iOS/Android), drop this on any button in your design:

```html
<button onclick="shareBill()">Share</button>
<script>
  async function shareBill() {
    const url = location.href;
    const bill = Splitwise.load();
    const lines = bill && bill.transfers.length
      ? bill.transfers.map(t => `• ${t.from} → ${t.to}: ${t.amount}${bill.currency ? " " + bill.currency : ""}`)
      : ["No transfers needed."];
    const text = [bill?.title || "Settlement", "", ...lines, "", "Full breakdown:"].join("\n");
    if (navigator.share) {
      try { await navigator.share({ title: "Splitwise", text, url }); return; }
      catch(e){ if (e.name === "AbortError") return; }
    }
    await navigator.clipboard.writeText(url);
    alert("Link copied");
  }
</script>
```

## What NOT to change

- The hash format. It's set by `splitwise/scripts/settle.py` and decoded by `splitwise.js`. Touch either and the link Claude hands you will stop loading.
- The file location. The deploy workflow publishes whatever's in `splitwise/web/` to the site root. Keep `index.html` and `splitwise.js` together in that folder.

## Quick test before deploying

```bash
cd splitwise/web && python3 -m http.server 8000
```

Open `http://localhost:8000/#<paste-a-hash-from-claude-here>` and your design should render the bill.

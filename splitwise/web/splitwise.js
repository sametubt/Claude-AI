/* splitwise.js — read the bill from the URL hash and expose it to your page.
 *
 * Drop this into any HTML you want to use as the dashboard:
 *
 *   <script src="splitwise.js"></script>
 *   <script>
 *     const bill = Splitwise.load();
 *     // bill = { title, currency, people, expenses, paid, owed, balances, transfers }
 *     // each expense: { payer, amount, group: "all" | [names], shares: [n] | null, note }
 *     // each transfer: { from, to, amount }
 *     // render however you want.
 *   </script>
 *
 * No frameworks, no dependencies. The hash format is what splitwise/scripts/settle.py emits.
 */
(function (global) {
  function decodeHash() {
    const h = (location.hash || "").replace(/^#/, "");
    if (!h) return null;
    try {
      const b64 = h.replace(/-/g, "+").replace(/_/g, "/");
      const padded = b64 + "===".slice((b64.length + 3) % 4);
      const json = decodeURIComponent(escape(atob(padded)));
      return JSON.parse(json);
    } catch (_) {
      return null;
    }
  }

  function round2(x) { return Math.round(x * 100) / 100; }

  function compute(state) {
    const people = state.p || [];
    const balances = {}, paid = {}, owed = {};
    people.forEach(p => { balances[p] = 0; paid[p] = 0; owed[p] = 0; });

    for (const e of (state.e || [])) {
      const payer = e.a;
      const amount = +e.m;
      if (!people.includes(payer) || !isFinite(amount) || amount <= 0) continue;
      const group = e.g === "all"
        ? people.slice()
        : (Array.isArray(e.g) ? e.g.filter(n => people.includes(n)) : []);
      if (!group.length) continue;
      const shares = Array.isArray(e.s) && e.s.length === group.length
        ? e.s.map(x => +x || 0)
        : group.map(() => 1);
      const total = shares.reduce((a, b) => a + b, 0);
      if (total <= 0) continue;

      paid[payer] += amount;
      balances[payer] += amount;
      group.forEach((p, i) => {
        const portion = amount * shares[i] / total;
        balances[p] -= portion;
        owed[p] += portion;
      });
    }
    return { balances, paid, owed };
  }

  function settleGreedy(people, balances) {
    const bal = { ...balances };
    const raw = [];
    const eps = 0.005;
    let safety = people.length * people.length + 20;
    while (safety-- > 0) {
      let cr = null, db = null, mx = -Infinity, mn = Infinity;
      for (const p of Object.keys(bal)) {
        if (bal[p] > mx) { mx = bal[p]; cr = p; }
        if (bal[p] < mn) { mn = bal[p]; db = p; }
      }
      if (cr == null || db == null) break;
      if (bal[cr] <= eps && bal[db] >= -eps) break;
      const amt = Math.min(bal[cr], -bal[db]);
      if (amt <= eps) break;
      raw.push([db, cr, amt]);
      bal[cr] -= amt;
      bal[db] += amt;
    }
    const transfers = raw.map(([f, t, a]) => [f, t, round2(a)]);

    if (transfers.length) {
      const delta = {};
      people.forEach(p => (delta[p] = 0));
      for (const [f, t, a] of transfers) { delta[f] -= a; delta[t] += a; }
      for (const p of people) {
        const drift = (balances[p] || 0) - delta[p];
        if (Math.abs(drift) >= 0.005) {
          for (let i = 0; i < transfers.length; i++) {
            const [f, t, a] = transfers[i];
            if (t === p) { transfers[i] = [f, t, round2(a + drift)]; delta[f] -= drift; delta[t] += drift; break; }
            if (f === p) { transfers[i] = [f, t, round2(a - drift)]; delta[f] += drift; delta[t] -= drift; break; }
          }
        }
      }
    }
    return transfers.map(([from, to, amount]) => ({ from, to, amount }));
  }

  function load() {
    const raw = decodeHash();
    if (!raw) return null;
    const people = Array.isArray(raw.p) ? raw.p : [];
    const expenses = (raw.e || []).map(e => ({
      payer: e.a || "",
      amount: +e.m || 0,
      group: e.g === "all" ? "all" : (Array.isArray(e.g) ? e.g.slice() : []),
      shares: Array.isArray(e.s) ? e.s.map(x => +x || 0) : null,
      note: e.n || "",
    }));
    const state = { p: people, e: (raw.e || []) };
    const { balances, paid, owed } = compute(state);
    const transfers = settleGreedy(people, balances);
    return {
      title: raw.t || "",
      currency: raw.c || "",
      people,
      expenses,
      paid,
      owed,
      balances,
      transfers,
    };
  }

  global.Splitwise = { load };
})(window);

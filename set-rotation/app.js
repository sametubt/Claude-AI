/* ============================================================================
   SET SECTOR ROTATION DASHBOARD
   Everything runs in the browser: no network calls, no dependencies.

   Colour policy
     · Sector identity  → 8 fixed categorical slots (--s1…--s8), assigned by the
       entity's position in its universe and never by rank, so filtering never
       repaints a survivor. Used only in the Relative Strength line chart, where
       a legend plus end-of-line labels carry identity alongside colour.
     · Quadrant state   → a 4-value status palette. Red↔green is not separable
       under deuteranopia, so a quadrant is NEVER colour alone: every quadrant
       mark ships a directional arrow (↗ ↘ ↙ ↖) and, wherever there is room,
       the quadrant's name.
   ========================================================================== */
'use strict';

/* ── constants ──────────────────────────────────────────────────────────── */

const SLOT_VARS = ['--s1', '--s2', '--s3', '--s4', '--s5', '--s6', '--s7', '--s8'];

const QUADRANTS = {
  lead:    { arrow: '↗', en: 'Leading',   v: '--q-lead' },
  weak:    { arrow: '↘', en: 'Weakening', v: '--q-weak' },
  lag:     { arrow: '↙', en: 'Lagging',   v: '--q-lag' },
  improve: { arrow: '↖', en: 'Improving', v: '--q-improve' }
};
const QUAD_ORDER = ['lead', 'weak', 'lag', 'improve'];

const UNIVERSES = {
  industry: {
    bench: { code: 'SET', en: 'SET Index' },
    members: [
      { code: 'AGRO',    en: 'Agro & Food Industry' },
      { code: 'CONSUMP', en: 'Consumer Products' },
      { code: 'FINCIAL', en: 'Financials' },
      { code: 'INDUS',   en: 'Industrials' },
      { code: 'PROPCON', en: 'Property & Construction' },
      { code: 'RESOURC', en: 'Resources' },
      { code: 'SERVICE', en: 'Services' },
      { code: 'TECH',    en: 'Technology' }
    ]
  },
  sector: {
    bench: { code: 'SET', en: 'SET Index' },
    members: [
      { code: 'BANK',  en: 'Banking' },
      { code: 'ENERG', en: 'Energy & Utilities' },
      { code: 'ICT',   en: 'Info & Comm Technology' },
      { code: 'FOOD',  en: 'Food & Beverage' },
      { code: 'COMM',  en: 'Commerce' },
      { code: 'PROP',  en: 'Property Development' },
      { code: 'HELTH', en: 'Health Care Services' },
      { code: 'TRANS', en: 'Transportation & Logistics' }
    ]
  }
};

const PARAMS = {
  D: { emaShort: 10, emaLong: 30, zWin: 60, momLag: 5,  perLabel: 'days' },
  W: { emaShort: 10, emaLong: 30, zWin: 52, momLag: 4,  perLabel: 'weeks' }
};

const N_DAYS = 1800;          // ≈7 years of business days in the demo series
const MAX_CSV_COLS = 25;      // benchmark + 24 members

/* ── small maths ────────────────────────────────────────────────────────── */

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function gaussFrom(rng) {
  let u = 0, v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
function fnv1a(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function ema(arr, period) {
  const k = 2 / (period + 1);
  const out = new Array(arr.length);
  let prev = arr[0];
  for (let i = 0; i < arr.length; i++) {
    prev = i === 0 ? arr[0] : arr[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

/** Rolling z-score over the trailing `win` values; null until the window fills
 *  (and null wherever an input is null, so a chained z-score stays honest). */
function rollingZ(arr, win, validFrom) {
  const out = new Array(arr.length).fill(null);
  for (let i = 0; i < arr.length; i++) {
    if (i < win - 1 || i < validFrom) continue;
    let sum = 0, ok = true;
    for (let j = i - win + 1; j <= i; j++) {
      const v = arr[j];
      if (v == null || !isFinite(v)) { ok = false; break; }
      sum += v;
    }
    if (!ok) continue;
    const mean = sum / win;
    let ss = 0;
    for (let j = i - win + 1; j <= i; j++) ss += (arr[j] - mean) ** 2;
    const sd = Math.sqrt(ss / win);
    out[i] = sd > 1e-9 ? (arr[i] - mean) / sd : 0;
  }
  return out;
}

function niceStep(rough) {
  if (!(rough > 0)) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(rough)));
  const n = rough / p;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p;
}

/* ── demo series ────────────────────────────────────────────────────────── */

function buildBusinessDates(n) {
  const out = [];
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  while (out.length < n) {
    const dow = d.getDay();
    if (dow !== 0 && dow !== 6) out.push(new Date(d.getTime()));
    d.setDate(d.getDate() - 1);
  }
  return out.reverse();
}

/** Deterministic pseudo-market. Each member is built in log space as
 *  benchmark + beta tilt + two rotation cycles + a mean-reverting wobble,
 *  which is what produces readable RRG loops rather than random scatter. */
function buildDemoSeries() {
  const dates = buildBusinessDates(N_DAYS);
  const mrng = mulberry32(20260804);
  const benchLog = new Array(N_DAYS);
  let lv = Math.log(1180);
  for (let t = 0; t < N_DAYS; t++) {
    const regime = 0.00030 * Math.sin((2 * Math.PI * t) / 620 + 1.1);
    lv += 0.00016 + regime + 0.0091 * gaussFrom(mrng);
    benchLog[t] = lv;
  }
  const bench = benchLog.map(Math.exp);

  const series = {};
  const all = [...UNIVERSES.industry.members, ...UNIVERSES.sector.members];
  for (const m of all) {
    const rng = mulberry32(fnv1a(m.code));
    const beta = 0.72 + 0.95 * rng();
    const alpha = (rng() - 0.48) * 0.00028;
    const p1 = 150 + 260 * rng();
    const p2 = p1 / (2.2 + 1.4 * rng());
    const ph1 = 2 * Math.PI * rng();
    const ph2 = 2 * Math.PI * rng();
    const a1 = 0.11 + 0.20 * rng();
    const a2 = a1 * (0.22 + 0.24 * rng());
    const wobVol = 0.0035 + 0.0035 * rng();
    const base = 80 + 900 * rng();

    let wob = 0;
    const px = new Array(N_DAYS);
    for (let t = 0; t < N_DAYS; t++) {
      wob = 0.988 * wob + wobVol * gaussFrom(rng);
      const cycle = a1 * Math.sin((2 * Math.PI * t) / p1 + ph1) + a2 * Math.sin((2 * Math.PI * t) / p2 + ph2);
      const tilt = (beta - 1) * (benchLog[t] - benchLog[0]);
      px[t] = base * Math.exp(benchLog[t] - benchLog[0] + tilt + alpha * t + cycle + wob);
    }
    series[m.code] = px;
  }
  return { dates, benchCode: 'SET', series: Object.assign({ SET: bench }, series) };
}

/* ── CSV ────────────────────────────────────────────────────────────────── */

function splitCsvLine(line) {
  const out = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQ) {
      if (c === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else inQ = false; }
      else cur += c;
    } else if (c === '"') inQ = true;
    else if (c === ',' || c === ';' || c === '\t') { out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
  if (lines.length < 40) throw new Error('Need at least 40 rows of data to compute an RRG.');
  const header = splitCsvLine(lines[0]);
  if (header.length < 3) throw new Error('Need at least 3 columns: a date, a benchmark, and at least one group.');
  const cols = header.slice(0, MAX_CSV_COLS + 1);
  const codes = cols.slice(1).map((c, i) => (c || 'COL' + (i + 1)).slice(0, 14));

  const dates = [];
  const cells = codes.map(() => []);
  for (let r = 1; r < lines.length; r++) {
    const f = splitCsvLine(lines[r]);
    const d = new Date(f[0]);
    if (isNaN(d.getTime())) continue;
    let ok = true;
    const row = [];
    for (let c = 0; c < codes.length; c++) {
      const v = parseFloat(String(f[c + 1]).replace(/[, ]/g, ''));
      if (!isFinite(v) || v <= 0) { ok = false; break; }
      row.push(v);
    }
    if (!ok) continue;
    dates.push(d);
    row.forEach((v, c) => cells[c].push(v));
  }
  if (dates.length < 40) throw new Error('Fewer than 40 usable rows were read — check the date format and the numbers.');

  // Ascending by date.
  const order = dates.map((d, i) => i).sort((a, b) => dates[a] - dates[b]);
  const sortedDates = order.map((i) => dates[i]);
  const series = {};
  codes.forEach((code, c) => { series[code] = order.map((i) => cells[c][i]); });

  return {
    raw: { dates: sortedDates, benchCode: codes[0], series },
    universe: {
      bench: { code: codes[0], en: codes[0] },
      members: codes.slice(1).map((c) => ({ code: c, en: c }))
    }
  };
}

/* ── pipeline ───────────────────────────────────────────────────────────── */

function resampleWeekly(raw) {
  const keep = [];
  for (let i = 0; i < raw.dates.length; i++) {
    const next = raw.dates[i + 1];
    if (!next || weekKey(next) !== weekKey(raw.dates[i])) keep.push(i);
  }
  const series = {};
  for (const k of Object.keys(raw.series)) series[k] = keep.map((i) => raw.series[k][i]);
  return { dates: keep.map((i) => raw.dates[i]), benchCode: raw.benchCode, series };
}
function weekKey(d) {
  const t = new Date(d.getTime());
  t.setDate(t.getDate() - ((t.getDay() + 6) % 7));   // back to Monday
  return t.getFullYear() * 100 + t.getMonth() * 5 + Math.floor(t.getDate() / 7) + t.getDate();
}

/** Bars consumed before the first RRG point can exist: the EMA warm-up, both
 *  z-score windows, and the momentum lag. */
const warmupCost = (p) => 2 * p.emaLong + 2 * p.zWin + p.momLag;

/** A short upload (or a weekly resample of one) cannot carry the standard
 *  10/30/60 windows. Shrink them proportionally so the chart still means
 *  something, and flag it so the UI can say the windows were shortened. */
function adaptParams(base, n) {
  const usable = n - 20;
  if (warmupCost(base) <= usable) return { ...base, adapted: false };
  const k = Math.max(0.15, usable / warmupCost(base));
  return {
    emaShort: Math.max(3, Math.round(base.emaShort * k)),
    emaLong: Math.max(6, Math.round(base.emaLong * k)),
    zWin: Math.max(10, Math.round(base.zWin * k)),
    momLag: Math.max(2, Math.round(base.momLag * k)),
    perLabel: base.perLabel,
    adapted: true
  };
}

const computeCache = new Map();

function computeModel(universeKey, timeframe) {
  const cacheKey = universeKey + '|' + timeframe + '|' + STATE.dataStamp;
  if (computeCache.has(cacheKey)) return computeCache.get(cacheKey);

  const uni = getUniverse(universeKey);
  const src = timeframe === 'W' ? resampleWeekly(STATE.raw) : STATE.raw;
  const p = adaptParams(PARAMS[timeframe], src.dates.length);
  const bench = src.series[uni.bench.code];

  const entities = [];
  uni.members.forEach((m, i) => {
    const px = src.series[m.code];
    if (!px) return;
    const rs = px.map((v, t) => (100 * v) / bench[t]);
    const s = ema(rs, p.emaShort);
    const l = ema(rs, p.emaLong);
    const raw = rs.map((_, t) => (100 * s[t]) / l[t]);

    const warm = p.emaLong * 2;
    const zr = rollingZ(raw, p.zWin, warm);
    const rsr = zr.map((z) => (z == null ? null : 100 + z));

    const momRaw = rsr.map((v, t) => {
      const prev = rsr[t - p.momLag];
      return v == null || prev == null ? null : (100 * v) / prev;
    });
    const zm = rollingZ(momRaw, p.zWin, 0);
    const rsm = zm.map((z) => (z == null ? null : 100 + z));

    entities.push({ ...m, slot: i % SLOT_VARS.length, rs, rsr, rsm });
  });

  let firstValid = -1;
  for (let t = 0; t < src.dates.length; t++) {
    if (entities.length && entities.every((e) => e.rsr[t] != null && e.rsm[t] != null)) { firstValid = t; break; }
  }
  const model = { dates: src.dates, entities, firstValid, lastIndex: src.dates.length - 1, bench: uni.bench, p };
  computeCache.set(cacheKey, model);
  return model;
}

function getUniverse(key) {
  return key === 'csv' ? STATE.csvUniverse : UNIVERSES[key];
}

function quadrantOf(rsr, rsm) {
  if (rsr >= 100) return rsm >= 100 ? 'lead' : 'weak';
  return rsm >= 100 ? 'improve' : 'lag';
}
function headingOf(rsr, rsm) {
  let a = (Math.atan2(rsm - 100, rsr - 100) * 180) / Math.PI;
  if (a < 0) a += 360;
  return a;
}

/** Snapshot of every entity at the scrubber position, sorted strongest first. */
function snapshot(model, idx) {
  const tail = STATE.tail;
  return model.entities
    .map((e) => {
      const rsr = e.rsr[idx], rsm = e.rsm[idx];
      const pr = e.rsr[idx - 1], pm = e.rsm[idx - 1];
      const rsNow = e.rs[idx], rsPast = e.rs[Math.max(0, idx - tail)];
      return {
        e,
        rsr, rsm,
        dRsr: pr == null ? null : rsr - pr,
        dRsm: pm == null ? null : rsm - pm,
        quad: quadrantOf(rsr, rsm),
        heading: headingOf(rsr, rsm),
        dist: Math.hypot(rsr - 100, rsm - 100),
        rsChg: (rsNow / rsPast - 1) * 100
      };
    })
    .sort((a, b) => b.rsr - a.rsr);
}

/* ── DOM / SVG helpers ──────────────────────────────────────────────────── */

const NS = 'http://www.w3.org/2000/svg';
const $ = (sel) => document.querySelector(sel);

function svgEl(tag, attrs, styles) {
  const n = document.createElementNS(NS, tag);
  if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (styles) for (const k in styles) n.style[k] = styles[k];
  return n;
}
function svgText(str, attrs, styles) {
  const n = svgEl('text', attrs, styles);
  n.textContent = str;                       // labels may come from a CSV header
  return n;
}
function elem(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
const cssVarRef = (v) => `var(${v})`;
const fmt2 = (v) => (v == null || !isFinite(v) ? '–' : v.toFixed(2));
const fmt1 = (v) => (v == null || !isFinite(v) ? '–' : v.toFixed(1));
const signed = (v, d) => (v == null || !isFinite(v) ? '–' : (v > 0 ? '+' : '') + v.toFixed(d));

const dfShort = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short' });
const dfFull = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' });
const dfMonth = new Intl.DateTimeFormat('en-GB', { month: 'short', year: '2-digit' });

/* ── state ──────────────────────────────────────────────────────────────── */

const STATE = {
  universeKey: 'industry',
  timeframe: 'D',
  tail: 8,
  idx: null,
  focus: null,
  selected: new Set(),
  rsWindow: 120,
  playing: false,
  qhTable: false,
  sortKey: 'rsr',
  sortDir: -1,
  dataStamp: 'demo',
  raw: null,
  csvUniverse: null
};

/* ── tooltip ────────────────────────────────────────────────────────────── */

const tipNode = $('#tip');
let tipHideTimer = null;

function showTip(x, y, build) {
  clearTimeout(tipHideTimer);
  tipNode.textContent = '';
  build(tipNode);
  tipNode.classList.add('on');
  const r = tipNode.getBoundingClientRect();
  const px = clamp(x + 16, 8, window.innerWidth - r.width - 8);
  const py = clamp(y - r.height - 14, 8, window.innerHeight - r.height - 8);
  tipNode.style.left = px + 'px';
  tipNode.style.top = py + 'px';
}
function hideTip() {
  tipHideTimer = setTimeout(() => tipNode.classList.remove('on'), 40);
}
function tipHeader(node, code, sub) {
  const h = elem('div', 'tip-head');
  h.appendChild(elem('span', 'tip-code', code));
  if (sub) h.appendChild(elem('span', 'tip-th', sub));
  node.appendChild(h);
}
function tipRow(node, label, value, colorVar) {
  const r = elem('div', 'tip-row');
  if (colorVar) {
    const k = elem('span', 'key');
    k.style.background = cssVarRef(colorVar);
    r.appendChild(k);
  }
  r.appendChild(elem('span', 'k', label));
  r.appendChild(elem('span', 'v', value));
  node.appendChild(r);
}

/* ── chart 1: Relative Rotation Graph ───────────────────────────────────── */

let rrgHeads = [];

function renderRRG(model, idx) {
  const wrap = $('#rrgWrap');
  const W = Math.max(280, wrap.clientWidth || 640);
  const H = clamp(Math.round(W * 0.80), 320, 560);
  const M = { t: 16, r: 16, b: 36, l: 54 };
  const iw = W - M.l - M.r;
  const ih = H - M.t - M.b;

  const start = Math.max(model.firstValid, idx - STATE.tail + 1);
  let maxDev = 0.9;
  for (const e of model.entities) {
    for (let t = start; t <= idx; t++) {
      if (e.rsr[t] == null || e.rsm[t] == null) continue;
      maxDev = Math.max(maxDev, Math.abs(e.rsr[t] - 100), Math.abs(e.rsm[t] - 100));
    }
  }
  const half = maxDev * 1.10;                   // one shared scale: angles stay true
  const x = (v) => M.l + ((v - (100 - half)) / (2 * half)) * iw;
  const y = (v) => M.t + ih - ((v - (100 - half)) / (2 * half)) * ih;

  const svg = svgEl('svg', {
    viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img',
    'aria-label': 'Relative Rotation Graph: RS-Ratio on the horizontal axis, RS-Momentum on the vertical axis. Values are listed in the data table below.'
  });

  // quadrant tints — background regions, kept far below data weight
  const quads = [
    ['lead', x(100), M.t, iw / 2, ih / 2],
    ['weak', x(100), M.t + ih / 2, iw / 2, ih / 2],
    ['lag', M.l, M.t + ih / 2, iw / 2, ih / 2],
    ['improve', M.l, M.t, iw / 2, ih / 2]
  ];
  for (const [k, qx, qy, qw, qh] of quads) {
    svg.appendChild(svgEl('rect', { x: qx, y: qy, width: qw, height: qh },
      { fill: cssVarRef(QUADRANTS[k].v), opacity: '.055' }));
  }

  // recessive hairline grid
  const step = niceStep((half * 2) / 7);
  const gridG = svgEl('g');
  for (let v = Math.ceil((100 - half) / step) * step; v <= 100 + half; v += step) {
    const rv = Math.round(v * 1000) / 1000;
    if (Math.abs(rv - 100) < 1e-9) continue;
    gridG.appendChild(svgEl('line', { x1: x(rv), y1: M.t, x2: x(rv), y2: M.t + ih },
      { stroke: cssVarRef('--grid'), strokeWidth: '1' }));
    gridG.appendChild(svgEl('line', { x1: M.l, y1: y(rv), x2: M.l + iw, y2: y(rv) },
      { stroke: cssVarRef('--grid'), strokeWidth: '1' }));
    gridG.appendChild(svgText(fmt1(rv), { x: x(rv), y: M.t + ih + 15, 'text-anchor': 'middle' },
      { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '10px' }));
    gridG.appendChild(svgText(fmt1(rv), { x: M.l - 8, y: y(rv) + 3.5, 'text-anchor': 'end' },
      { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '10px' }));
  }
  svg.appendChild(gridG);

  // the 100 crosshair
  svg.appendChild(svgEl('line', { x1: x(100), y1: M.t, x2: x(100), y2: M.t + ih },
    { stroke: cssVarRef('--axis'), strokeWidth: '1.5' }));
  svg.appendChild(svgEl('line', { x1: M.l, y1: y(100), x2: M.l + iw, y2: y(100) },
    { stroke: cssVarRef('--axis'), strokeWidth: '1.5' }));

  // corner labels — the quadrant's name where the quadrant is
  const corners = [
    ['lead', M.l + iw - 10, M.t + 16, 'end'],
    ['weak', M.l + iw - 10, M.t + ih - 8, 'end'],
    ['lag', M.l + 10, M.t + ih - 8, 'start'],
    ['improve', M.l + 10, M.t + 16, 'start']
  ];
  for (const [k, cx, cy, anchor] of corners) {
    const q = QUADRANTS[k];
    svg.appendChild(svgText(`${q.arrow} ${q.en}`, { x: cx, y: cy, 'text-anchor': anchor },
      { fill: cssVarRef(q.v), fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: '600', opacity: '.9' }));
  }

  // axis titles
  svg.appendChild(svgText('RS-Ratio →', { x: M.l + iw, y: H - 4, 'text-anchor': 'end' },
    { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '10px', letterSpacing: '.08em' }));
  svg.appendChild(svgText('RS-Momentum →', { x: 13, y: M.t + 4, 'text-anchor': 'end', transform: `rotate(-90 13 ${M.t + 4})` },
    { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '10px', letterSpacing: '.08em' }));

  // tails + heads
  rrgHeads = [];
  const dim = STATE.focus != null;
  const tailsG = svgEl('g');
  const headsG = svgEl('g');

  for (const e of model.entities) {
    const pts = [];
    for (let t = start; t <= idx; t++) {
      if (e.rsr[t] == null || e.rsm[t] == null) continue;
      pts.push({ t, x: x(e.rsr[t]), y: y(e.rsm[t]) });
    }
    if (!pts.length) continue;
    const head = pts[pts.length - 1];
    const quad = quadrantOf(e.rsr[idx], e.rsm[idx]);
    const col = cssVarRef(QUADRANTS[quad].v);
    const focused = STATE.focus === e.code;
    const faded = dim && !focused;

    for (let i = 1; i < pts.length; i++) {
      const f = i / (pts.length - 1);
      tailsG.appendChild(svgEl('line',
        { x1: pts[i - 1].x, y1: pts[i - 1].y, x2: pts[i].x, y2: pts[i].y, 'stroke-linecap': 'round' },
        { stroke: col, strokeWidth: (1.1 + 0.9 * f).toFixed(2), opacity: (faded ? 0.10 : 0.16 + 0.44 * f).toFixed(3) }));
    }
    for (let i = 0; i < pts.length - 1; i++) {
      tailsG.appendChild(svgEl('circle', { cx: pts[i].x, cy: pts[i].y, r: 1.7 },
        { fill: col, opacity: (faded ? 0.12 : 0.22 + 0.4 * (i / Math.max(1, pts.length - 1))).toFixed(3) }));
    }

    const r = focused ? 7 : 6;
    headsG.appendChild(svgEl('circle', { cx: head.x, cy: head.y, r },
      { fill: col, stroke: cssVarRef('--surface-1'), strokeWidth: '2', opacity: faded ? '.3' : '1' }));
    rrgHeads.push({ e, quad, px: head.x, py: head.y, r, col, faded });
  }
  svg.appendChild(tailsG);
  svg.appendChild(headsG);

  // Ticker labels are the identity channel here, so none may be lost to a
  // cluster: place them greedily top-down, push collisions apart, and draw a
  // leader hairline back to the dot for any label that had to move.
  const FS = W < 520 ? 9.5 : 11;
  const LABEL_H = FS + 2.5;
  const charW = FS * 0.62;
  const visible = rrgHeads.filter((h) => !h.faded).slice().sort((a, b) => a.py - b.py);
  const placedByColumn = new Map();

  for (const h of visible) {
    const textW = h.e.code.length * charW;
    const wantRight = h.px + h.r + 5 + textW <= M.l + iw;
    const side = wantRight ? 1 : -1;
    const colKey = side;
    const placed = placedByColumn.get(colKey) || [];
    let ly = h.py + 4;                       // baseline that centres text on the dot
    for (const p of placed) if (Math.abs(ly - p) < LABEL_H) ly = p + LABEL_H;
    if (ly > M.t + ih - 3) {
      ly = h.py + 4;
      for (const p of placed.slice().reverse()) if (Math.abs(ly - p) < LABEL_H) ly = p - LABEL_H;
    }
    ly = clamp(ly, M.t + FS, M.t + ih - 3);
    placed.push(ly);
    placed.sort((a, b) => a - b);
    placedByColumn.set(colKey, placed);

    const lx = side === 1 ? h.px + h.r + 5 : h.px - h.r - 5;
    if (Math.abs(ly - h.py) > 3) {
      headsG.appendChild(svgEl('line',
        { x1: h.px + side * (h.r + 1.5), y1: h.py, x2: lx - side * 1.5, y2: ly - 3.5 },
        { stroke: h.col, strokeWidth: '1', opacity: '.45' }));
    }
    headsG.appendChild(svgText(h.e.code,
      { x: lx, y: ly, 'text-anchor': side === 1 ? 'start' : 'end' }, {
        fill: cssVarRef('--text-primary'), fontFamily: 'var(--font-mono)',
        fontSize: FS + 'px', fontWeight: '600', letterSpacing: '.02em',
        paintOrder: 'stroke', stroke: cssVarRef('--surface-1'), strokeWidth: '3px', strokeLinejoin: 'round'
      }));
  }

  // nearest-point hit layer: the pointer only has to be closest, not dead-centre
  const hit = svgEl('rect', { x: M.l, y: M.t, width: iw, height: ih, fill: 'transparent' });
  hit.style.cursor = 'crosshair';
  svg.appendChild(hit);

  const marker = svgEl('circle', { r: 12, cx: -99, cy: -99 },
    { fill: 'none', stroke: cssVarRef('--text-primary'), strokeWidth: '1.5', opacity: '0' });
  svg.appendChild(marker);

  function nearest(evt) {
    const box = svg.getBoundingClientRect();
    const sx = ((evt.clientX - box.left) / box.width) * W;
    const sy = ((evt.clientY - box.top) / box.height) * H;
    let best = null, bd = Infinity;
    for (const h of rrgHeads) {
      const d = Math.hypot(h.px - sx, h.py - sy);
      if (d < bd) { bd = d; best = h; }
    }
    return bd <= 48 ? best : null;
  }
  hit.addEventListener('pointermove', (evt) => {
    const h = nearest(evt);
    if (!h) { marker.style.opacity = '0'; hideTip(); return; }
    marker.setAttribute('cx', h.px); marker.setAttribute('cy', h.py); marker.style.opacity = '.55';
    const q = QUADRANTS[h.quad];
    showTip(evt.clientX, evt.clientY, (n) => {
      tipHeader(n, h.e.code, h.e.en);
      tipRow(n, `${q.arrow} ${q.en}`, '', q.v);
      tipRow(n, 'RS-Ratio', fmt2(h.e.rsr[idx]));
      tipRow(n, 'RS-Momentum', fmt2(h.e.rsm[idx]));
      tipRow(n, 'Heading', Math.round(headingOf(h.e.rsr[idx], h.e.rsm[idx])) + '°');
    });
  });
  hit.addEventListener('pointerleave', () => { marker.style.opacity = '0'; hideTip(); });
  hit.addEventListener('click', (evt) => {
    const h = nearest(evt);
    setFocus(h && STATE.focus !== h.e.code ? h.e.code : null);
  });

  wrap.textContent = '';
  wrap.appendChild(svg);
  renderQuadLegend();
}

function renderQuadLegend() {
  const box = $('#quadLegend');
  box.textContent = '';
  for (const k of QUAD_ORDER) {
    const q = QUADRANTS[k];
    const item = elem('span', 'qkey');
    const a = elem('span', 'arrow', q.arrow);
    a.style.color = cssVarRef(q.v);
    item.appendChild(a);
    item.appendChild(document.createTextNode(q.en));
    box.appendChild(item);
  }
}

/* ── chart 2: rotation leaderboard ──────────────────────────────────────── */

function renderLeaderboard(rows) {
  const box = $('#leaderboard');
  box.textContent = '';

  const head = elem('div', 'lb-head');
  head.appendChild(elem('span', 'lb-rank', '#'));
  head.appendChild(elem('span', null, 'Sector'));
  head.appendChild(abbrLabel('Quadrant', 'Q'));
  const hr = abbrLabel('RS-Ratio', 'RS-R');
  hr.classList.add('num');
  head.appendChild(hr);
  head.appendChild(elem('span', 'num lb-col-mom', 'RS-Mom'));
  box.appendChild(head);

  rows.forEach((r, i) => {
    const q = QUADRANTS[r.quad];
    const row = elem('button', 'lb-row' + (STATE.focus === r.e.code ? ' is-focus' : ''));
    row.type = 'button';
    row.setAttribute('role', 'listitem');
    row.setAttribute('aria-pressed', String(STATE.focus === r.e.code));

    row.appendChild(elem('span', 'lb-rank', String(i + 1)));

    const name = elem('span', 'lb-name');
    name.appendChild(elem('span', 'lb-code', r.e.code));
    name.appendChild(elem('span', 'lb-sub', r.e.en));
    row.appendChild(name);

    const tag = elem('span', 'qtag');
    const arrow = elem('span', 'arrow', q.arrow);
    arrow.style.color = cssVarRef(q.v);
    tag.appendChild(arrow);
    tag.appendChild(elem('span', 'word', q.en));
    tag.title = q.en;
    row.appendChild(tag);

    row.appendChild(numCell(r.rsr, r.dRsr, ''));
    row.appendChild(numCell(r.rsm, r.dRsm, 'lb-col-mom'));

    row.addEventListener('click', () => setFocus(STATE.focus === r.e.code ? null : r.e.code));
    row.addEventListener('pointerenter', (evt) => {
      showTip(evt.clientX, evt.clientY, (n) => {
        tipHeader(n, r.e.code, r.e.en);
        tipRow(n, `${q.arrow} ${q.en}`, '', q.v);
        tipRow(n, 'RS-Ratio', fmt2(r.rsr));
        tipRow(n, 'RS-Momentum', fmt2(r.rsm));
        tipRow(n, `RS ${STATE.tail}${STATE.timeframe === 'W' ? 'w' : 'd'}`, signed(r.rsChg, 1) + '%');
      });
    });
    row.addEventListener('pointerleave', hideTip);
    box.appendChild(row);
  });
}

/** How the universe is spread across the four quadrants right now — the
 *  one-glance read on whether the market is rotating or crowded. */
function renderBreadth(rows) {
  const foot = $('#lbFoot');
  foot.textContent = '';
  const counts = { lead: 0, weak: 0, lag: 0, improve: 0 };
  for (const r of rows) counts[r.quad]++;

  foot.appendChild(elem('span', 'cap', `Breadth · ${rows.length} groups`));

  const bar = elem('div', 'breadth');
  bar.setAttribute('role', 'img');
  bar.setAttribute('aria-label',
    QUAD_ORDER.map((k) => `${QUADRANTS[k].en} ${counts[k]}`).join(', '));
  for (const k of QUAD_ORDER) {
    if (!counts[k]) continue;
    const seg = elem('span');
    seg.style.flex = String(counts[k]);
    seg.style.background = cssVarRef(QUADRANTS[k].v);
    bar.appendChild(seg);
  }
  foot.appendChild(bar);

  const tally = elem('div', 'tally');
  for (const k of QUAD_ORDER) {
    const q = QUADRANTS[k];
    const cell = elem('div', 'cell');
    const top = elem('div', 'top');
    const a = elem('span', 'arrow', q.arrow);
    a.style.color = cssVarRef(q.v);
    top.appendChild(a);
    top.appendChild(elem('span', 'n', String(counts[k])));
    cell.appendChild(top);
    cell.appendChild(elem('span', 'nm', q.en));
    cell.title = q.en;
    tally.appendChild(cell);
  }
  foot.appendChild(tally);
}

/** Column heading that swaps to a short form once the grid gets narrow. */
function abbrLabel(full, abbr) {
  const s = elem('span');
  s.appendChild(elem('span', 'full', full));
  s.appendChild(elem('span', 'abbr', abbr));
  return s;
}

function numCell(value, delta, extraCls) {
  const c = elem('span', 'lb-num' + (extraCls ? ' ' + extraCls : ''));
  c.appendChild(document.createTextNode(fmt2(value)));
  const d = elem('span', 'delta' + (delta == null ? '' : delta > 0 ? ' up' : delta < 0 ? ' down' : ''));
  d.textContent = delta == null ? '' : (delta > 0 ? '▲' : delta < 0 ? '▼' : '–') + Math.abs(delta).toFixed(2);
  c.appendChild(d);
  return c;
}

/* ── chart 3: relative strength vs benchmark ────────────────────────────── */

function renderRS(model, idx) {
  const wrap = $('#rsWrap');
  const W = Math.max(280, wrap.clientWidth || 720);
  const H = clamp(Math.round(W * 0.32), 210, 300);
  const M = { t: 14, r: 62, b: 26, l: 44 };
  const iw = W - M.l - M.r;
  const ih = H - M.t - M.b;

  const win = STATE.rsWindow;
  const start = win === 0 ? model.firstValid : Math.max(model.firstValid, idx - win + 1);
  const chosen = model.entities.filter((e) => STATE.selected.has(e.code));

  const svg = svgEl('svg', {
    viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img',
    'aria-label': 'Relative strength of each group against the benchmark, rebased to 100 at the start of the window.'
  });

  if (!chosen.length || idx <= start) {
    svg.appendChild(svgText('Select at least one group below',
      { x: W / 2, y: H / 2, 'text-anchor': 'middle' },
      { fill: cssVarRef('--text-muted'), fontSize: '13px', fontFamily: 'var(--font-ui)' }));
    wrap.textContent = ''; wrap.appendChild(svg);
    return;
  }

  const lines = chosen.map((e) => {
    const base = e.rs[start];
    const vals = [];
    for (let t = start; t <= idx; t++) vals.push((100 * e.rs[t]) / base);
    return { e, vals };
  });

  let lo = Infinity, hi = -Infinity;
  for (const l of lines) for (const v of l.vals) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  lo = Math.min(lo, 100); hi = Math.max(hi, 100);
  const pad = (hi - lo) * 0.10 || 1;
  lo -= pad; hi += pad;

  const n = idx - start + 1;
  const x = (i) => M.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v) => M.t + ih - ((v - lo) / (hi - lo)) * ih;

  // grid + y ticks
  const step = niceStep((hi - lo) / 5);
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    const isBase = Math.abs(v - 100) < 1e-9;
    svg.appendChild(svgEl('line', { x1: M.l, y1: y(v), x2: M.l + iw, y2: y(v) },
      { stroke: cssVarRef(isBase ? '--axis' : '--grid'), strokeWidth: isBase ? '1.5' : '1' }));
    svg.appendChild(svgText(v.toFixed(0), { x: M.l - 8, y: y(v) + 3.5, 'text-anchor': 'end' },
      { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '10px' }));
  }

  // x ticks
  const tickEvery = Math.max(1, Math.round(n / 5));
  for (let i = 0; i < n; i += tickEvery) {
    const d = model.dates[start + i];
    svg.appendChild(svgText(n > 90 ? dfMonth.format(d) : dfShort.format(d),
      { x: x(i), y: M.t + ih + 16, 'text-anchor': i === 0 ? 'start' : 'middle' },
      { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '10px' }));
  }

  // lines
  for (const l of lines) {
    const d = l.vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
    const dimmed = STATE.focus != null && STATE.focus !== l.e.code;
    svg.appendChild(svgEl('path', { d, fill: 'none', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' },
      { stroke: cssVarRef(SLOT_VARS[l.e.slot]), strokeWidth: STATE.focus === l.e.code ? '2.6' : '2', opacity: dimmed ? '.22' : '1' }));
  }

  // end labels, pushed apart so none collide (the relief for low-contrast slots)
  const labels = lines.map((l) => ({
    code: l.e.code, slot: l.e.slot,
    yWant: y(l.vals[l.vals.length - 1]),
    dim: STATE.focus != null && STATE.focus !== l.e.code
  })).sort((a, b) => a.yWant - b.yWant);
  const minGap = 13;
  for (let i = 1; i < labels.length; i++) {
    if (labels[i].yWant - labels[i - 1].yWant < minGap) labels[i].yWant = labels[i - 1].yWant + minGap;
  }
  const overflow = labels.length ? labels[labels.length - 1].yWant - (M.t + ih) : 0;
  if (overflow > 0) labels.forEach((l) => { l.yWant -= overflow; });
  for (const l of labels) {
    svg.appendChild(svgText(l.code, { x: M.l + iw + 7, y: clamp(l.yWant, M.t + 8, M.t + ih) + 3.5 },
      { fill: cssVarRef(SLOT_VARS[l.slot]), fontFamily: 'var(--font-mono)', fontSize: '10.5px', fontWeight: '600', opacity: l.dim ? '.35' : '1' }));
  }

  // crosshair: readers aim at a date, never at a 2px line
  const cross = svgEl('line', { x1: -9, y1: M.t, x2: -9, y2: M.t + ih },
    { stroke: cssVarRef('--text-muted'), strokeWidth: '1', opacity: '0' });
  svg.appendChild(cross);
  const dotsG = svgEl('g', null, { opacity: '0' });
  const dots = lines.map((l) => {
    const c = svgEl('circle', { r: 4 }, { fill: cssVarRef(SLOT_VARS[l.e.slot]), stroke: cssVarRef('--surface-1'), strokeWidth: '2' });
    dotsG.appendChild(c);
    return c;
  });
  svg.appendChild(dotsG);

  const hit = svgEl('rect', { x: M.l, y: M.t, width: iw, height: ih, fill: 'transparent' });
  hit.style.cursor = 'crosshair';
  svg.appendChild(hit);

  hit.addEventListener('pointermove', (evt) => {
    const box = svg.getBoundingClientRect();
    const sx = ((evt.clientX - box.left) / box.width) * W;
    const i = clamp(Math.round(((sx - M.l) / iw) * (n - 1)), 0, n - 1);
    cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i));
    cross.style.opacity = '.6';
    dotsG.style.opacity = '1';
    lines.forEach((l, k) => { dots[k].setAttribute('cx', x(i)); dots[k].setAttribute('cy', y(l.vals[i])); });
    const ordered = lines.map((l) => ({ l, v: l.vals[i] })).sort((a, b) => b.v - a.v);
    showTip(evt.clientX, evt.clientY, (node) => {
      tipHeader(node, dfFull.format(model.dates[start + i]), 'rebased 100');
      for (const o of ordered) tipRow(node, o.l.e.code, o.v.toFixed(1), SLOT_VARS[o.l.e.slot]);
    });
  });
  hit.addEventListener('pointerleave', () => { cross.style.opacity = '0'; dotsG.style.opacity = '0'; hideTip(); });

  wrap.textContent = '';
  wrap.appendChild(svg);
}

function renderRSLegend(model) {
  const box = $('#rsLegend');
  box.textContent = '';
  for (const e of model.entities) {
    const on = STATE.selected.has(e.code);
    const b = elem('button');
    b.type = 'button';
    b.setAttribute('aria-pressed', String(on));
    b.style.color = on ? cssVarRef(SLOT_VARS[e.slot]) : '';
    const key = elem('span', 'key');
    key.style.background = cssVarRef(SLOT_VARS[e.slot]);
    b.appendChild(key);
    b.appendChild(elem('span', 'code', e.code));
    b.title = e.en;
    b.addEventListener('click', () => {
      if (STATE.selected.has(e.code)) STATE.selected.delete(e.code);
      else STATE.selected.add(e.code);
      render();
    });
    box.appendChild(b);
  }
}

/* ── chart 4: quadrant history ──────────────────────────────────────────── */

function renderQuadrantHistory(model, idx, rows) {
  const wrap = $('#qhWrap');
  const tableWrap = $('#qhTableWrap');
  const cols = Math.min(26, idx - model.firstValid + 1);
  const startT = idx - cols + 1;

  if (STATE.qhTable) {
    wrap.classList.add('hidden');
    tableWrap.classList.remove('hidden');
    renderQuadrantTable(model, rows, startT, cols, tableWrap);
    return;
  }
  wrap.classList.remove('hidden');
  tableWrap.classList.add('hidden');

  // Cells stretch to fill the card; they only scroll when there is no room.
  const labelW = 88;
  const gap = 2, ch = 22, topH = 20;
  const avail = Math.max(280, wrap.clientWidth || 800);
  const cw = clamp(Math.floor((avail - labelW) / cols) - gap, 20, 46);
  const W = labelW + cols * (cw + gap);
  const H = topH + rows.length * (ch + gap) + 6;

  const svg = svgEl('svg', {
    viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img',
    'aria-label': 'Quadrant of each group over the last periods. The same values are available in the table view.'
  });

  const tickEvery = Math.max(1, Math.ceil(46 / (cw + gap)));
  for (let c = 0; c < cols; c += tickEvery) {
    const d = model.dates[startT + c];
    svg.appendChild(svgText(dfShort.format(d),
      { x: labelW + c * (cw + gap) + cw / 2, y: 12, 'text-anchor': 'middle' },
      { fill: cssVarRef('--text-muted'), fontFamily: 'var(--font-mono)', fontSize: '9.5px' }));
  }

  rows.forEach((r, i) => {
    const ry = topH + i * (ch + gap);
    const faded = STATE.focus != null && STATE.focus !== r.e.code;

    const lbl = svgText(r.e.code, { x: 0, y: ry + ch / 2 + 4 },
      { fill: cssVarRef(faded ? '--text-muted' : '--text-primary'), fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: '600' });
    svg.appendChild(lbl);

    for (let c = 0; c < cols; c++) {
      const t = startT + c;
      const rsr = r.e.rsr[t], rsm = r.e.rsm[t];
      if (rsr == null || rsm == null) continue;
      const k = quadrantOf(rsr, rsm);
      const q = QUADRANTS[k];
      const cx = labelW + c * (cw + gap);
      const g = svgEl('g', { tabindex: '0', role: 'img', 'aria-label': `${r.e.code} ${dfFull.format(model.dates[t])} ${q.en}` });
      g.style.cursor = 'default';
      g.appendChild(svgEl('rect', { x: cx, y: ry, width: cw, height: ch, rx: 4 },
        { fill: cssVarRef(q.v), opacity: faded ? '.06' : '.18', stroke: cssVarRef(q.v), strokeWidth: '1', strokeOpacity: faded ? '.15' : '.5' }));
      g.appendChild(svgText(q.arrow, { x: cx + cw / 2, y: ry + ch / 2 + 4.5, 'text-anchor': 'middle' },
        { fill: cssVarRef(q.v), fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: '600', opacity: faded ? '.35' : '1' }));

      const show = (evt) => {
        const p = evt.touches ? evt.touches[0] : evt;
        const bb = g.getBoundingClientRect();
        showTip(p && p.clientX != null ? p.clientX : bb.left, p && p.clientY != null ? p.clientY : bb.top, (node) => {
          tipHeader(node, r.e.code, dfFull.format(model.dates[t]));
          tipRow(node, `${q.arrow} ${q.en}`, '', q.v);
          tipRow(node, 'RS-Ratio', fmt2(rsr));
          tipRow(node, 'RS-Momentum', fmt2(rsm));
        });
      };
      g.addEventListener('pointerenter', show);
      g.addEventListener('focus', show);
      g.addEventListener('pointerleave', hideTip);
      g.addEventListener('blur', hideTip);
      svg.appendChild(g);
    }
  });

  wrap.textContent = '';
  wrap.appendChild(svg);
}

function renderQuadrantTable(model, rows, startT, cols, host) {
  const table = elem('table', 'data');
  const thead = elem('thead');
  const hr = elem('tr');
  hr.appendChild(elem('th', null, 'Group'));
  const showCols = [];
  for (let c = 0; c < cols; c++) if (c % 4 === 0 || c === cols - 1) showCols.push(c);
  for (const c of showCols) hr.appendChild(elem('th', null, dfFull.format(model.dates[startT + c])));
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = elem('tbody');
  for (const r of rows) {
    const tr = elem('tr');
    const td0 = elem('td');
    td0.appendChild(elem('span', 'code', r.e.code));
    tr.appendChild(td0);
    for (const c of showCols) {
      const t = startT + c;
      const rsr = r.e.rsr[t], rsm = r.e.rsm[t];
      const td = elem('td');
      if (rsr == null || rsm == null) td.textContent = '–';
      else {
        const q = QUADRANTS[quadrantOf(rsr, rsm)];
        td.textContent = `${q.arrow} ${q.en}`;
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  host.textContent = '';
  host.appendChild(table);
}

/* ── data table ─────────────────────────────────────────────────────────── */

const TABLE_COLS = [
  { key: 'rank', label: '#', num: false },
  { key: 'name', label: 'Group', num: false },
  { key: 'quad', label: 'Quadrant' },
  { key: 'rsr', label: 'RS-Ratio' },
  { key: 'rsm', label: 'RS-Mom' },
  { key: 'heading', label: 'Heading' },
  { key: 'dist', label: 'Distance' },
  { key: 'rsChg', label: 'RS Δ%' }
];

function renderTable(rows) {
  const table = $('#dataTable');
  const caption = table.querySelector('caption');
  table.textContent = '';
  if (caption) table.appendChild(caption);

  const sorted = rows.slice().sort((a, b) => {
    const k = STATE.sortKey;
    if (k === 'name') return STATE.sortDir * a.e.code.localeCompare(b.e.code);
    if (k === 'quad') return STATE.sortDir * (QUAD_ORDER.indexOf(a.quad) - QUAD_ORDER.indexOf(b.quad));
    if (k === 'rank') return 0;
    return STATE.sortDir * ((a[k] ?? 0) - (b[k] ?? 0));
  });

  const thead = elem('thead');
  const hr = elem('tr');
  for (const col of TABLE_COLS) {
    const th = elem('th');
    th.scope = 'col';
    const label = col.key === 'rsChg'
      ? `RS Δ% · ${STATE.tail}${STATE.timeframe === 'W' ? 'w' : 'd'}`
      : col.label;
    if (col.key === 'rank') th.textContent = label;
    else {
      const b = elem('button');
      b.type = 'button';
      b.appendChild(document.createTextNode(label));
      const caret = elem('span', null, STATE.sortKey === col.key ? (STATE.sortDir < 0 ? '▾' : '▴') : '');
      b.appendChild(caret);
      b.addEventListener('click', () => {
        if (STATE.sortKey === col.key) STATE.sortDir *= -1;
        else { STATE.sortKey = col.key; STATE.sortDir = col.key === 'name' || col.key === 'quad' ? 1 : -1; }
        render();
      });
      th.appendChild(b);
      if (STATE.sortKey === col.key) th.setAttribute('aria-sort', STATE.sortDir < 0 ? 'descending' : 'ascending');
    }
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = elem('tbody');
  sorted.forEach((r, i) => {
    const q = QUADRANTS[r.quad];
    const tr = elem('tr');

    tr.appendChild(elem('td', 'n', String(i + 1)));

    const tdName = elem('td');
    tdName.appendChild(elem('span', 'code', r.e.code));
    if (r.e.en) tdName.appendChild(elem('span', 'sub-name', r.e.en));
    tr.appendChild(tdName);

    const tdQ = elem('td');
    const arrow = elem('span', null, q.arrow + ' ');
    arrow.style.color = cssVarRef(q.v);
    arrow.style.fontFamily = 'var(--font-mono)';
    arrow.style.fontWeight = '600';
    tdQ.appendChild(arrow);
    tdQ.appendChild(document.createTextNode(q.en));
    tdQ.style.textAlign = 'left';
    tr.appendChild(tdQ);

    tr.appendChild(elem('td', 'n', fmt2(r.rsr)));
    tr.appendChild(elem('td', 'n', fmt2(r.rsm)));
    tr.appendChild(elem('td', 'n', Math.round(r.heading) + '°'));
    tr.appendChild(elem('td', 'n', fmt2(r.dist)));

    const tdChg = elem('td', 'n', signed(r.rsChg, 1) + '%');
    tdChg.style.color = cssVarRef(r.rsChg >= 0 ? '--up' : '--down');
    tr.appendChild(tdChg);

    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
}

/* ── orchestration ──────────────────────────────────────────────────────── */

function render() {
  const model = computeModel(STATE.universeKey, STATE.timeframe);

  if (model.firstValid < 0) {
    showInsufficientData(model);
    return;
  }
  $('#insufficient').classList.add('hidden');
  $('#dashboard').classList.remove('hidden');

  if (STATE.idx == null || STATE.idx < model.firstValid || STATE.idx > model.lastIndex) {
    STATE.idx = model.lastIndex;
  }
  if (!STATE.selected.size) {
    model.entities.slice(0, 4).forEach((e) => STATE.selected.add(e.code));
  }

  const scrub = $('#scrub');
  scrub.min = String(model.firstValid);
  scrub.max = String(model.lastIndex);
  scrub.value = String(STATE.idx);

  const d = model.dates[STATE.idx];
  $('#scrubDate').textContent = dfFull.format(d);
  $('#scrubMeta').textContent =
    `${STATE.idx - model.firstValid + 1} / ${model.lastIndex - model.firstValid + 1} ${model.p.perLabel}` +
    (model.p.adapted ? ` · shortened windows ${model.p.emaShort}/${model.p.emaLong}/${model.p.zWin}` : '');
  $('#benchName').textContent = model.bench.en || model.bench.code;
  $('#rsBench').textContent = model.bench.code;

  const rows = snapshot(model, STATE.idx);

  renderRRG(model, STATE.idx);
  renderLeaderboard(rows);
  renderBreadth(rows);
  renderRS(model, STATE.idx);
  renderRSLegend(model);
  renderQuadrantHistory(model, STATE.idx, rows);
  renderTable(rows);

  $('#clearFocusBtn').classList.toggle('hidden', STATE.focus == null);
}

/** Not enough history to produce a single RRG point — say so plainly rather
 *  than drawing eight dots that all mean "null". */
function showInsufficientData(model) {
  const box = $('#insufficient');
  box.textContent = '';
  const need = warmupCost(model.p) + 20;
  box.appendChild(elem('span', 'mark', '!'));
  const body = elem('div');
  const h = elem('strong', null, 'Not enough history to compute an RRG');
  body.appendChild(h);
  body.appendChild(document.createElement('br'));
  body.appendChild(document.createTextNode(
    `This timeframe has ${model.dates.length} ${model.p.perLabel}; the calculation needs about ${need}. ` +
    `Switch to Daily, or load a file with a longer history.`));
  box.appendChild(body);
  box.classList.remove('hidden');
  $('#dashboard').classList.add('hidden');
  $('#scrubDate').textContent = '—';
  $('#scrubMeta').textContent = '';
}

function setFocus(code) {
  STATE.focus = code;
  render();
}

/* ── controls ───────────────────────────────────────────────────────────── */

function bindSeg(id, attr, apply) {
  const bar = $(id);
  bar.addEventListener('click', (evt) => {
    const btn = evt.target.closest('button[' + attr + ']');
    if (!btn) return;
    [...bar.querySelectorAll('button')].forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
    apply(btn.getAttribute(attr));
  });
}

bindSeg('#universeSeg', 'data-universe', (v) => {
  STATE.universeKey = v;
  STATE.focus = null;
  STATE.selected.clear();
  STATE.idx = null;
  render();
});
bindSeg('#tfSeg', 'data-tf', (v) => { STATE.timeframe = v; STATE.idx = null; render(); });
bindSeg('#tailSeg', 'data-tail', (v) => { STATE.tail = parseInt(v, 10); render(); });
bindSeg('#winSeg', 'data-win', (v) => { STATE.rsWindow = parseInt(v, 10); render(); });

$('#scrub').addEventListener('input', (evt) => {
  STATE.idx = parseInt(evt.target.value, 10);
  stopPlay();
  render();
});

$('#clearFocusBtn').addEventListener('click', () => setFocus(null));

$('#qhModeBtn').addEventListener('click', (evt) => {
  STATE.qhTable = !STATE.qhTable;
  evt.currentTarget.setAttribute('aria-pressed', String(STATE.qhTable));
  evt.currentTarget.textContent = STATE.qhTable ? 'Heatmap' : 'Table view';
  render();
});

/* playback */
let playTimer = null;
function startPlay() {
  const model = computeModel(STATE.universeKey, STATE.timeframe);
  if (STATE.idx >= model.lastIndex) STATE.idx = model.firstValid;
  STATE.playing = true;
  $('#playBtn').setAttribute('aria-pressed', 'true');
  $('#playGlyph').textContent = '⏸';
  $('#playLabel').textContent = 'Pause';
  playTimer = setInterval(() => {
    const m = computeModel(STATE.universeKey, STATE.timeframe);
    if (STATE.idx >= m.lastIndex) { stopPlay(); return; }
    STATE.idx += 1;
    render();
  }, 170);
}
function stopPlay() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
  STATE.playing = false;
  $('#playBtn').setAttribute('aria-pressed', 'false');
  $('#playGlyph').textContent = '▶';
  $('#playLabel').textContent = 'Play';
}
$('#playBtn').addEventListener('click', () => (STATE.playing ? stopPlay() : startPlay()));

/* theme */
function applyTheme(mode) {
  if (mode === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', mode);
  try { localStorage.setItem('set-rrg-theme', mode); } catch (_) { /* private mode */ }
  $('#themeGlyph').textContent = mode === 'light' ? '◑' : mode === 'dark' ? '◐' : '◓';
  $('#themeLabel').textContent = mode === 'auto' ? 'Auto' : mode === 'light' ? 'Light' : 'Dark';
}
$('#themeBtn').addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme') || 'auto';
  applyTheme(cur === 'auto' ? 'light' : cur === 'light' ? 'dark' : 'auto');
});

/* CSV */
$('#csvBtn').addEventListener('click', () => $('#csvInput').click());
$('#csvInput').addEventListener('change', (evt) => {
  const file = evt.target.files && evt.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const { raw, universe } = parseCsv(String(reader.result));
      STATE.raw = raw;
      STATE.csvUniverse = universe;
      STATE.dataStamp = 'csv:' + Date.now();
      STATE.universeKey = 'csv';
      STATE.focus = null;
      STATE.selected.clear();
      STATE.idx = null;
      computeCache.clear();

      const seg = $('#universeSeg');
      [...seg.querySelectorAll('button')].forEach((b) => b.setAttribute('aria-pressed', 'false'));
      let csvBtn = seg.querySelector('button[data-universe="csv"]');
      if (!csvBtn) {
        csvBtn = elem('button', null, 'CSV');
        csvBtn.type = 'button';
        csvBtn.setAttribute('data-universe', 'csv');
        seg.appendChild(csvBtn);
      }
      csvBtn.setAttribute('aria-pressed', 'true');

      const chip = $('#sourceChip');
      chip.classList.remove('is-demo');
      chip.classList.add('is-live');
      $('#sourceLabel').textContent = file.name.slice(0, 28);
      $('#demoNote').classList.add('hidden');
      $('#resetBtn').classList.remove('hidden');
      render();
    } catch (err) {
      alert('Could not read the file:\n\n' + err.message);
    }
    evt.target.value = '';
  };
  reader.readAsText(file);
});

$('#resetBtn').addEventListener('click', () => {
  STATE.raw = DEMO;
  STATE.dataStamp = 'demo';
  STATE.universeKey = 'industry';
  STATE.csvUniverse = null;
  STATE.focus = null;
  STATE.selected.clear();
  STATE.idx = null;
  computeCache.clear();
  const seg = $('#universeSeg');
  const csvBtn = seg.querySelector('button[data-universe="csv"]');
  if (csvBtn) csvBtn.remove();
  [...seg.querySelectorAll('button')].forEach((b) =>
    b.setAttribute('aria-pressed', String(b.getAttribute('data-universe') === 'industry')));
  const chip = $('#sourceChip');
  chip.classList.add('is-demo');
  chip.classList.remove('is-live');
  $('#sourceLabel').textContent = 'Demo data';
  $('#demoNote').classList.remove('hidden');
  $('#resetBtn').classList.add('hidden');
  render();
});

/* resize: charts re-measure, the frame never jumps */
let resizeTimer = null;
let lastWidth = window.innerWidth;
window.addEventListener('resize', () => {
  if (window.innerWidth === lastWidth) return;
  lastWidth = window.innerWidth;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(render, 120);
});

/* keyboard: ← → step the scrubber from anywhere outside a control */
window.addEventListener('keydown', (evt) => {
  if (evt.target.matches('input, textarea, select, button')) return;
  if (evt.key !== 'ArrowLeft' && evt.key !== 'ArrowRight') return;
  const model = computeModel(STATE.universeKey, STATE.timeframe);
  STATE.idx = clamp(STATE.idx + (evt.key === 'ArrowRight' ? 1 : -1), model.firstValid, model.lastIndex);
  stopPlay();
  render();
  evt.preventDefault();
});

/* ── boot ───────────────────────────────────────────────────────────────── */

const DEMO = buildDemoSeries();
STATE.raw = DEMO;

try {
  const saved = localStorage.getItem('set-rrg-theme');
  applyTheme(saved || 'auto');
} catch (_) {
  applyTheme('auto');
}

render();

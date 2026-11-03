// Healthcare Admissions Dashboard: filters, dashboard cards, the chart
// builder ("Visualizer"), and the schema diagram. Plain JS + SVG, no build step.
// Data comes from data.js (pipeline/export_dashboard.py), stats from stats.js.

(function () {
  'use strict';

  const RAW = window.HEALTHCARE_DATA;
  const Stats = window.HCStats;
  if (!RAW || !Stats) {
    document.getElementById('load-error').hidden = false;
    return;
  }

  const ALPHA = 0.05;
  const N = RAW.meta.rows;
  const C = {};
  for (const k in RAW.cols) C[k] = Int32Array.from(RAW.cols[k]);

  // ---------------------------------------------------------------- formats
  const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const MINUS = '−';
  const sign = v => (v < 0 ? MINUS : '');
  const fmtInt = v => sign(v) + nf0.format(Math.abs(v));
  const fmtNum = v => (Number.isInteger(v) ? fmtInt(v) : sign(v) + nf1.format(Math.abs(v)));
  const fmtMoney = v => sign(v) + '$' + nf0.format(Math.abs(v));
  const fmtMoney2 = v => sign(v) + '$' + nf2.format(Math.abs(v));
  const fmtMoneyCompact = v => {
    const a = Math.abs(v), s = sign(v);
    if (a >= 1e9) return s + '$' + nf1.format(a / 1e9) + 'B';
    if (a >= 1e6) return s + '$' + nf1.format(a / 1e6) + 'M';
    if (a >= 1e4) return s + '$' + nf0.format(a / 1e3) + 'K';
    if (a >= 1e3) return s + '$' + nf1.format(a / 1e3) + 'K';
    return s + '$' + nf0.format(a);
  };
  const fmtCompact = v => {
    const a = Math.abs(v), s = sign(v);
    if (a >= 1e6) return s + nf1.format(a / 1e6) + 'M';
    if (a >= 1e4) return s + nf0.format(a / 1e3) + 'K';
    return fmtNum(v);
  };
  const fmtDays = v => nf2.format(v) + ' days';
  const fmtPct = f => nf1.format(f * 100) + '%';                 // f is a fraction
  const fmtPctAxis = f => nf0.format(f * 100) + '%';
  const fmtSignedPct = p => (p > 0 ? '+' : p < 0 ? MINUS : '') + nf2.format(Math.abs(p)) + '%'; // p in percent
  const fmtSignedPctAxis = p => (p > 0 ? '+' : p < 0 ? MINUS : '') + (Math.abs(p) < 1 && p !== 0 ? nf1 : nf0).format(Math.abs(p)) + '%';
  const fmtPts = f => (f > 0 ? '+' : f < 0 ? MINUS : '') + nf1.format(Math.abs(f * 100)) + ' pts';
  const fmtP = p => (p < 0.001 ? 'p < 0.001' : 'p = ' + p.toFixed(3));

  // ---------------------------------------------------------------- derived columns
  const DAY_MS = 86400000;
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [sy, sm, sd] = RAW.meta.start.split('-').map(Number);
  const START = Date.UTC(sy, sm - 1, sd);
  const YEAR = new Int32Array(N), MON = new Int32Array(N), MOY = new Int32Array(N), DOW = new Int32Array(N);
  const LOSI = new Int32Array(N), LOSB = new Int32Array(N), BILLB = new Int32Array(N);
  let maxDay = 0;
  for (let r = 0; r < N; r++) {
    const d = new Date(START + C.day[r] * DAY_MS);
    const y = d.getUTCFullYear(), m = d.getUTCMonth();
    YEAR[r] = y - sy;
    MON[r] = (y - sy) * 12 + m - (sm - 1);
    MOY[r] = m;
    DOW[r] = (d.getUTCDay() + 6) % 7;
    LOSI[r] = C.los[r] - 1;
    LOSB[r] = Math.min(3, Math.floor((C.los[r] - 1) / 7));
    const b = C.billCents[r];
    BILLB[r] = b < 0 ? 0 : Math.min(6, 1 + Math.floor(b / 1e6));
    if (C.day[r] > maxDay) maxDay = C.day[r];
  }
  const lastAdmit = new Date(START + maxDay * DAY_MS);
  const ly = lastAdmit.getUTCFullYear(), lm = lastAdmit.getUTCMonth();
  const years = [];
  for (let y = sy; y <= ly; y++) years.push(String(y));
  const nMonths = (ly - sy) * 12 + lm - (sm - 1) + 1;
  const monthLabels = [], monthIsJan = [];
  for (let i = 0; i < nMonths; i++) {
    const m = (sm - 1 + i) % 12, y = sy + Math.floor((sm - 1 + i) / 12);
    monthLabels.push(MONTHS[m] + ' ' + y);
    monthIsJan.push(m === 0);
  }
  const dash = s => s.replace(/-/g, '–');

  const DIMS = {
    condition: { label: 'Medical condition', values: RAW.dims.condition, arr: C.condition },
    insurer: { label: 'Insurance provider', values: RAW.dims.insurer, arr: C.insurer },
    admType: { label: 'Admission type', values: RAW.dims.admType, arr: C.admType },
    medication: { label: 'Medication', values: RAW.dims.medication, arr: C.medication },
    test: { label: 'Test result', values: RAW.dims.test, arr: C.test },
    gender: { label: 'Gender', values: RAW.dims.gender, arr: C.gender },
    blood: { label: 'Blood type', values: RAW.dims.blood, arr: C.blood },
    ageGroup: { label: 'Age group', values: RAW.dims.ageGroup.map(dash), arr: C.ageGroup, ordered: true },
    year: { label: 'Admission year', values: years, arr: YEAR, ordered: true },
    month: { label: 'Admission month', values: monthLabels, arr: MON, ordered: true, tick: i => i === 0 || monthIsJan[i] },
    moy: { label: 'Month of year', values: MONTHS, arr: MOY, ordered: true },
    dow: { label: 'Day of week admitted', values: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], arr: DOW, ordered: true },
    los: { label: 'Length of stay (days)', values: Array.from({ length: 30 }, (_, i) => String(i + 1)), arr: LOSI, ordered: true },
    losBand: { label: 'Length-of-stay band', values: ['1–7 days', '8–14 days', '15–21 days', '22–30 days'], arr: LOSB, ordered: true },
    billBand: { label: 'Bill size', values: ['Negative (adjustment)', '$0–10K', '$10–20K', '$20–30K', '$30–40K', '$40–50K', '$50K+'], arr: BILLB, ordered: true },
  };
  for (const k in DIMS) DIMS[k].key = k;
  const canSplit = k => DIMS[k].values.length <= 8;

  const METRICS = {
    count: { label: 'Admissions', kind: 'count', fmt: fmtInt, axis: fmtCompact },
    share: { label: 'Share of admissions', kind: 'share', fmt: fmtPct, axis: fmtPctAxis },
    avgBill: { label: 'Average bill', kind: 'bill', stat: 'mean', fmt: fmtMoney, axis: fmtMoneyCompact },
    medBill: { label: 'Median bill', kind: 'bill', stat: 'median', fmt: fmtMoney, axis: fmtMoneyCompact },
    totalBill: { label: 'Total billed', kind: 'bill', stat: 'sum', fmt: fmtMoneyCompact, axis: fmtMoneyCompact },
    avgLos: { label: 'Average length of stay', kind: 'los', stat: 'mean', fmt: fmtDays, axis: fmtNum },
    medLos: { label: 'Median length of stay', kind: 'los', stat: 'median', fmt: fmtDays, axis: fmtNum },
    avgPerDay: { label: 'Average bill per patient-day', kind: 'perday', stat: 'mean', fmt: fmtMoney, axis: fmtMoneyCompact },
    medPerDay: { label: 'Median bill per patient-day', kind: 'perday', stat: 'median', fmt: fmtMoney, axis: fmtMoneyCompact },
  };

  // ---------------------------------------------------------------- state
  const FILTERS = [
    ['year', 'Year'], ['condition', 'Condition'], ['insurer', 'Insurer'], ['admType', 'Admission type'],
    ['gender', 'Gender'], ['ageGroup', 'Age group'], ['medication', 'Medication'], ['test', 'Test result'],
  ];
  const state = {
    f: Object.fromEntries(FILTERS.map(([k]) => [k, -1])),
    excludeAdj: true,
    tab: 'dashboard',
    viz: { x: 'condition', s: '', metric: 'avgBill', chart: 'bars', fitY: false },
  };
  const STORE_KEY = 'hc-dashboard-v1';
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    if (saved) {
      for (const [k] of FILTERS) {
        const v = saved.f && saved.f[k];
        if (Number.isInteger(v) && v >= -1 && v < DIMS[k].values.length) state.f[k] = v;
      }
      if (typeof saved.excludeAdj === 'boolean') state.excludeAdj = saved.excludeAdj;
      if (saved.viz && DIMS[saved.viz.x] && METRICS[saved.viz.metric]) Object.assign(state.viz, saved.viz);
      if (state.viz.s && !DIMS[state.viz.s]) state.viz.s = '';
      if (['dashboard', 'visualizer', 'model'].includes(saved.tab)) state.tab = saved.tab;
    }
  } catch (e) { /* storage unavailable: start from defaults */ }
  const hashTab = (location.hash || '').slice(1);
  if (['dashboard', 'visualizer', 'model'].includes(hashTab)) state.tab = hashTab;
  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }

  // ---------------------------------------------------------------- data engine
  let ROWS = new Int32Array(0);
  const ALL = Int32Array.from({ length: N }, (_, i) => i);

  function filterRows() {
    const active = FILTERS.filter(([k]) => state.f[k] >= 0).map(([k]) => [DIMS[k].arr, state.f[k]]);
    if (!active.length) return ALL;
    const out = new Int32Array(N);
    let n = 0;
    outer: for (let r = 0; r < N; r++) {
      for (const [a, v] of active) if (a[r] !== v) continue outer;
      out[n++] = r;
    }
    return out.subarray(0, n);
  }

  function valuesOf(rows, kind) {
    const out = new Float64Array(rows.length);
    let k = 0;
    const ex = state.excludeAdj;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      if (kind === 'los') { out[k++] = C.los[r]; continue; }
      const b = C.billCents[r];
      if (ex && b < 0) continue;
      out[k++] = kind === 'bill' ? b / 100 : b / 100 / C.los[r];
    }
    return out.subarray(0, k);
  }
  const sum = a => { let s = 0; for (let i = 0; i < a.length; i++) s += a[i]; return s; };
  const mean = a => (a.length ? sum(a) / a.length : null);
  function quantile(sorted, p) {
    if (!sorted.length) return null;
    const h = (sorted.length - 1) * p, lo = Math.floor(h);
    return sorted[lo] + (sorted[Math.min(lo + 1, sorted.length - 1)] - sorted[lo]) * (h - lo);
  }
  const sorted = a => Float64Array.from(a).sort();
  const median = a => quantile(sorted(a), 0.5);

  function aggregate(rows, mk) {
    const m = METRICS[mk];
    if (m.kind === 'count') return rows.length;
    const v = valuesOf(rows, m.kind);
    if (!v.length) return null;
    return m.stat === 'mean' ? mean(v) : m.stat === 'sum' ? sum(v) : median(v);
  }

  // Bucket rows by x (and optionally split) dimension.
  function cube(rows, xKey, sKey) {
    const X = DIMS[xKey], S = sKey ? DIMS[sKey] : null;
    const nx = X.values.length, ns = S ? S.values.length : 1;
    const b = Array.from({ length: nx * ns }, () => []);
    const xa = X.arr, sa = S ? S.arr : null;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      b[xa[r] * ns + (sa ? sa[r] : 0)].push(r);
    }
    const xs = [], ss = [];
    for (let x = 0; x < nx; x++) { for (let s = 0; s < ns; s++) if (b[x * ns + s].length) { xs.push(x); break; } }
    for (let s = 0; s < ns; s++) { for (let x = 0; x < nx; x++) if (b[x * ns + s].length) { ss.push(s); break; } }
    const cell = (x, s) => b[x * ns + (s || 0)];
    const xRows = x => { const out = []; for (let s = 0; s < ns; s++) out.push(...b[x * ns + s]); return out; };
    return { X, S, xs, ss: S ? ss : [0], cell, xRows };
  }

  // Values (and counts) matrix over the x/split values present.
  function matrix(c, mk) {
    const n = c.xs.map(x => c.ss.map(s => c.cell(x, s).length));
    let v;
    if (mk === 'share') {
      if (c.S) v = n.map(row => { const t = row.reduce((a, b) => a + b, 0); return row.map(k => (t ? k / t : null)); });
      else { const t = n.reduce((a, r) => a + r[0], 0); v = n.map(r => [t ? r[0] / t : null]); }
    } else {
      v = c.xs.map(x => c.ss.map(s => (c.cell(x, s).length ? aggregate(c.cell(x, s), mk) : null)));
    }
    return { v, n };
  }

  // ---------------------------------------------------------------- DOM + SVG helpers
  const NS = 'http://www.w3.org/2000/svg';
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function svg(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function label(parent, x, y, str, cls, anchor) {
    const t = svg('text', { x, y, class: cls, 'text-anchor': anchor || 'start' }, parent);
    t.textContent = str;
    return t;
  }
  const mctx = document.createElement('canvas').getContext('2d');
  function tw(str, size, weight) {
    mctx.font = `${weight || 400} ${size || 12}px "IBM Plex Sans", system-ui, sans-serif`;
    return mctx.measureText(str).width;
  }
  function fitText(str, maxW, size) {
    if (tw(str, size) <= maxW) return str;
    let s = str;
    while (s.length > 1 && tw(s + '…', size) > maxW) s = s.slice(0, -1);
    return s.length > 1 ? s + '…' : '';
  }
  const seriesColor = slot => `var(--s${(slot % 8) + 1})`;
  const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  function niceTicks(min, max, count) {
    if (min === max) max = min + 1;
    const raw = (max - min) / Math.max(1, count);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const e = raw / mag;
    const step = (e >= 7.5 ? 10 : e >= 3.5 ? 5 : e >= 1.5 ? 2 : 1) * mag;
    const lo = Math.floor(min / step + 1e-9) * step, hi = Math.ceil(max / step - 1e-9) * step;
    const ticks = [];
    for (let v = lo; v <= hi + step * 1e-6; v += step) ticks.push(Math.round(v / step) * step);
    return { lo, hi, ticks };
  }

  // Colour maths in OKLab, for heatmap ramps.
  function hexToRgb(h) {
    h = h.replace('#', '');
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    const n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const toLin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const toSrgb = c => Math.round(Math.min(1, Math.max(0, c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055)) * 255);
  function oklab(hex) {
    const [r, g, b] = hexToRgb(hex).map(toLin);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
  }
  function fromOklab([L, a, b]) {
    const l = Math.pow(L + 0.3963377774 * a + 0.2158037573 * b, 3);
    const m = Math.pow(L - 0.1055613458 * a - 0.0638541728 * b, 3);
    const s = Math.pow(L - 0.0894841775 * a - 1.291485548 * b, 3);
    const rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
    return '#' + rgb.map(c => toSrgb(c).toString(16).padStart(2, '0')).join('');
  }
  function mix(h1, h2, t) {
    const a = oklab(h1), b = oklab(h2);
    return fromOklab(a.map((v, i) => v + (b[i] - v) * t));
  }
  const luminance = hex => { const [r, g, b] = hexToRgb(hex).map(toLin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const inkOn = hex => (luminance(hex) > 0.33 ? '#0b0b0b' : '#ffffff');
  function sequential(lo, hi) {
    const a = cssVar('--seq-lo'), b = cssVar('--seq-hi');
    return v => mix(a, b, hi > lo ? Math.min(1, Math.max(0, (v - lo) / (hi - lo))) : 0.5);
  }
  function diverging(center, extent) {
    const mid = cssVar('--mid'), neg = cssVar('--neg'), pos = cssVar('--pos');
    return v => {
      const t = Math.max(-1, Math.min(1, (v - center) / extent));
      return t < 0 ? mix(mid, neg, -t * 0.9) : mix(mid, pos, t * 0.9);
    };
  }

  // ---------------------------------------------------------------- tooltip
  const tipEl = document.getElementById('tip');
  function setTip(t) {
    tipEl.replaceChildren(el('div', 'tip-title', t.title));
    for (const r of t.rows) {
      const row = el('div', 'tip-row');
      const key = el('span', 'tip-key' + (r.slot == null && !r.color ? ' none' : ''));
      if (r.color) key.style.background = r.color;
      else if (r.slot != null) key.style.background = seriesColor(r.slot);
      row.append(key, el('strong', '', r.value), el('span', 'tip-label', r.label));
      tipEl.append(row);
    }
    tipEl.hidden = false;
  }
  function placeTip(x, y) {
    const pad = 14, w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    let left = x + pad, top = y + pad;
    if (left + w > innerWidth - 8) left = x - w - pad;
    if (top + h > innerHeight - 8) top = y - h - pad;
    tipEl.style.left = Math.max(8, left) + 'px';
    tipEl.style.top = Math.max(8, top) + 'px';
  }
  function placeTipAt(node) {
    const b = node.getBoundingClientRect();
    placeTip(b.left + Math.min(b.width / 2, 60), b.top + Math.min(b.height / 2, 20));
  }
  const hideTip = () => { tipEl.hidden = true; };
  addEventListener('scroll', hideTip, { passive: true });

  function hitRect(layer, x, y, w, h, getTip, marks) {
    const r = svg('rect', { x, y, width: Math.max(0, w), height: Math.max(0, h), class: 'hit', tabindex: '0' }, layer);
    const t = getTip();
    r.setAttribute('aria-label', t.title + ': ' + t.rows.map(x => `${x.label} ${x.value}`).join(', '));
    const on = () => marks.forEach(m => m.classList.add('hot'));
    const off = () => { marks.forEach(m => m.classList.remove('hot')); hideTip(); };
    r.addEventListener('pointerenter', e => { on(); setTip(getTip()); placeTip(e.clientX, e.clientY); });
    r.addEventListener('pointermove', e => placeTip(e.clientX, e.clientY));
    r.addEventListener('pointerleave', off);
    r.addEventListener('focus', () => { on(); setTip(getTip()); placeTipAt(r); });
    r.addEventListener('blur', off);
    return r;
  }

  function frame(host, H, aria) {
    host.replaceChildren();
    const W = Math.max(260, Math.floor(host.clientWidth || 600));
    const root = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'group', 'aria-label': aria || '' }, host);
    return { root, W };
  }

  // Bar with a 4px rounded data end and a square end at the baseline.
  function hbarPath(x0, x1, y, h) {
    const w = x1 - x0;
    if (Math.abs(w) < 0.5) return `M${x0},${y}h0.5v${h}h-0.5Z`;
    const r = Math.min(4, Math.abs(w), h / 2), d = w > 0 ? 1 : -1;
    return `M${x0},${y}H${x1 - d * r}Q${x1},${y} ${x1},${y + r}V${y + h - r}Q${x1},${y + h} ${x1 - d * r},${y + h}H${x0}Z`;
  }
  function vbarPath(x, w, y0, y1) {
    const h = y0 - y1;
    if (Math.abs(h) < 0.5) return `M${x},${y0}h${w}v-0.5h${-w}Z`;
    const r = Math.min(4, Math.abs(h), w / 2), d = h > 0 ? 1 : -1;
    return `M${x},${y0}V${y1 + d * r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 + d * r}V${y0}Z`;
  }

  // ---------------------------------------------------------------- charts
  // Horizontal bars. sp: cats, series[{label,slot}], values[c][s], fmt, axis,
  // tip(ci), colorOf?(ci,si,v), ref?{value,label}, endLabels?
  function drawHBar(host, sp) {
    const nc = sp.cats.length, ns = sp.series.length;
    const barH = ns === 1 ? 16 : ns <= 2 ? 11 : ns <= 4 ? 8 : 6;
    const groupH = ns * barH + (ns - 1) * 2;
    const band = groupH + 14;
    const top = sp.ref ? 20 : 4, axisH = 24;
    const H = top + nc * band + axisH;
    const { root, W } = frame(host, H, sp.aria);
    let vmin = 0, vmax = 0;
    sp.values.forEach(r => r.forEach(v => { if (v != null) { vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); } }));
    if (vmin === 0 && vmax === 0) vmax = 1;
    const ends = sp.endLabels !== false && ns === 1;
    const endW = ends ? Math.max(0, ...sp.values.map(r => (r[0] == null ? 0 : tw(sp.fmt(r[0]), 12, 500)))) + 10 : 8;
    const labW = Math.min(W * 0.4, Math.max(...sp.cats.map(c => tw(c, 12))) + 14);
    const x0 = labW + (vmin < 0 ? endW : 0), x1 = W - (vmax > 0 ? endW : 8);
    const nt = niceTicks(vmin, vmax, Math.max(2, Math.round((x1 - x0) / 110)));
    const lo = vmin < 0 ? nt.lo : 0, hi = vmax > 0 ? nt.hi : 0;
    const X = v => x0 + (v - lo) / (hi - lo || 1) * (x1 - x0);
    const gGrid = svg('g', {}, root), gMarks = svg('g', {}, root), gText = svg('g', {}, root), gHit = svg('g', {}, root);
    const plotBot = top + nc * band;
    for (const t of nt.ticks) {
      if (t < lo - 1e-9 || t > hi + 1e-9) continue;
      svg('line', { x1: X(t), x2: X(t), y1: top, y2: plotBot, class: 'grid' }, gGrid);
      label(gText, X(t), plotBot + 16, sp.axis(t), 'tick', 'middle');
    }
    svg('line', { x1: X(0), x2: X(0), y1: top, y2: plotBot, class: 'axis' }, gGrid);
    if (sp.ref) {
      svg('line', { x1: X(sp.ref.value), x2: X(sp.ref.value), y1: top - 6, y2: plotBot, class: 'ref' }, gText);
      label(gText, Math.min(W - 4, Math.max(labW, X(sp.ref.value))), top - 9, sp.ref.label, 'ref-label', 'middle');
    }
    sp.cats.forEach((cat, ci) => {
      const by = top + ci * band, gy = by + (band - groupH) / 2;
      label(gText, labW - 10, by + band / 2 + 4, fitText(cat, labW - 12, 12), 'cat', 'end');
      const marks = [];
      sp.series.forEach((se, si) => {
        const v = sp.values[ci][si];
        if (v == null) return;
        const y = gy + si * (barH + 2);
        const p = svg('path', { d: hbarPath(X(0), X(v), y, barH), class: 'mark' }, gMarks);
        p.style.fill = sp.colorOf ? sp.colorOf(ci, si, v) : seriesColor(se.slot);
        marks.push(p);
        if (ends) label(gText, v >= 0 ? X(v) + 6 : X(v) - 6, y + barH / 2 + 4, sp.fmt(v), 'val', v >= 0 ? 'start' : 'end');
      });
      hitRect(gHit, 0, by, W, band, () => sp.tip(ci), marks);
    });
  }

  // Vertical columns. Same spec as drawHBar plus height, tick?(ci).
  function drawVBar(host, sp) {
    const nc = sp.cats.length, ns = sp.series.length;
    const H = sp.height || 240, top = 20, axisH = 26;
    const { root, W } = frame(host, H, sp.aria);
    let vmin = 0, vmax = 0;
    sp.values.forEach(r => r.forEach(v => { if (v != null) { vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); } }));
    if (vmin === 0 && vmax === 0) vmax = 1;
    const nt = niceTicks(vmin, vmax, 4);
    const lo = vmin < 0 ? nt.lo : 0, hi = vmax > 0 ? nt.hi : 0;
    const left = Math.max(...nt.ticks.map(t => tw(sp.axis(t), 11))) + 12, right = 8;
    const bandW = (W - left - right) / nc;
    const barW = Math.max(2, Math.min(24, (bandW * 0.7 - (ns - 1) * 2) / ns));
    const groupW = ns * barW + (ns - 1) * 2;
    const Y = v => top + (1 - (v - lo) / (hi - lo || 1)) * (H - top - axisH);
    const gGrid = svg('g', {}, root), gMarks = svg('g', {}, root), gText = svg('g', {}, root), gHit = svg('g', {}, root);
    for (const t of nt.ticks) {
      if (t < lo - 1e-9 || t > hi + 1e-9) continue;
      svg('line', { x1: left, x2: W - right, y1: Y(t), y2: Y(t), class: t === 0 ? 'axis' : 'grid' }, gGrid);
      label(gText, left - 8, Y(t) + 4, sp.axis(t), 'tick', 'end');
    }
    const maxLab = Math.max(...sp.cats.map(c => tw(c, 11)));
    const every = Math.max(1, Math.ceil((maxLab + 10) / bandW));
    const capLabels = ns === 1 && nc <= 16;
    sp.cats.forEach((cat, ci) => {
      const bx = left + ci * bandW, gx = bx + (bandW - groupW) / 2;
      const showTick = sp.tick ? sp.tick(ci) : ci % every === 0;
      if (showTick) label(gText, bx + bandW / 2, H - axisH + 17, cat, 'tick', 'middle');
      const marks = [];
      sp.series.forEach((se, si) => {
        const v = sp.values[ci][si];
        if (v == null) return;
        const x = gx + si * (barW + 2);
        const p = svg('path', { d: vbarPath(x, barW, Y(0), Y(v)), class: 'mark' }, gMarks);
        p.style.fill = sp.colorOf ? sp.colorOf(ci, si, v) : seriesColor(se.slot);
        marks.push(p);
        if (capLabels) {
          const s = sp.fmt(v);
          if (tw(s, 11, 500) <= bandW - 2) label(gText, x + barW / 2, (v >= 0 ? Y(v) - 6 : Y(v) + 14), s, 'val', 'middle').style.fontSize = '11px';
        }
      });
      hitRect(gHit, bx, top, bandW, H - top - axisH, () => sp.tip(ci), marks);
    });
  }

  // Lines over ordered categories, crosshair + one tooltip for every series.
  // sp: cats, series[{label,slot,values}], fmt, axis, fitY, tick?(i), height
  function drawLine(host, sp) {
    const n = sp.cats.length, H = sp.height || 250, top = 14, axisH = 26;
    const { root, W } = frame(host, H, sp.aria);
    const all = [];
    sp.series.forEach(s => s.values.forEach(v => { if (v != null) all.push(v); }));
    let vmin = all.length ? Math.min(...all) : 0, vmax = all.length ? Math.max(...all) : 1;
    if (!sp.fitY) vmin = Math.min(0, vmin);
    else { const pad = (vmax - vmin) * 0.1 || Math.abs(vmax) * 0.05 || 1; vmin -= pad; vmax += pad; }
    const nt = niceTicks(vmin, vmax, 4);
    const single = sp.series.length === 1;
    const lastVal = single ? sp.series[0].values.slice().reverse().find(v => v != null) : null;
    const left = Math.max(...nt.ticks.map(t => tw(sp.axis(t), 11))) + 12;
    const right = single && lastVal != null ? tw(sp.fmt(lastVal), 12, 500) + 14 : 12;
    const X = i => (n === 1 ? (left + W - right) / 2 : left + i / (n - 1) * (W - left - right));
    const Y = v => top + (1 - (v - nt.lo) / (nt.hi - nt.lo || 1)) * (H - top - axisH);
    const gGrid = svg('g', {}, root), gMarks = svg('g', {}, root), gText = svg('g', {}, root);
    for (const t of nt.ticks) {
      svg('line', { x1: left, x2: W - right, y1: Y(t), y2: Y(t), class: t === 0 ? 'axis' : 'grid' }, gGrid);
      label(gText, left - 8, Y(t) + 4, sp.axis(t), 'tick', 'end');
    }
    const maxLab = Math.max(...sp.cats.map(c => tw(c, 11)));
    const spacing = n > 1 ? (W - left - right) / (n - 1) : W;
    const every = Math.max(1, Math.ceil((maxLab + 12) / spacing));
    sp.cats.forEach((c, i) => {
      const show = sp.tick ? sp.tick(i) : i % every === 0;
      if (show) label(gText, X(i), H - axisH + 17, sp.tick && sp.tickLabel ? sp.tickLabel(i) : c, 'tick', i === 0 && n > 1 ? 'start' : 'middle');
    });
    sp.series.forEach(s => {
      let d = '', pen = false, area = '', firstX = null, lastX = null;
      s.values.forEach((v, i) => {
        if (v == null) { pen = false; return; }
        d += (pen ? 'L' : 'M') + X(i) + ',' + Y(v);
        if (firstX == null) firstX = X(i);
        lastX = X(i);
        pen = true;
      });
      if (single && firstX != null) {
        area = d + `L${lastX},${Y(Math.max(nt.lo, 0))}L${firstX},${Y(Math.max(nt.lo, 0))}Z`;
        const a = svg('path', { d: area, class: 'area' }, gMarks);
        a.style.fill = seriesColor(s.slot);
      }
      const p = svg('path', { d, class: 'line' }, gMarks);
      p.style.stroke = seriesColor(s.slot);
      const li = s.values.map((v, i) => (v == null ? -1 : i)).filter(i => i >= 0).pop();
      if (li != null) {
        const dot = svg('circle', { cx: X(li), cy: Y(s.values[li]), r: 4, class: 'dot' }, gMarks);
        dot.style.fill = seriesColor(s.slot);
      }
    });
    if (single && lastVal != null) {
      const li = sp.series[0].values.map((v, i) => (v == null ? -1 : i)).filter(i => i >= 0).pop();
      label(gText, X(li) + 8, Y(lastVal) + 4, sp.fmt(lastVal), 'val');
    }
    // Crosshair layer
    const cross = svg('line', { y1: top, y2: H - axisH, class: 'crosshair', visibility: 'hidden' }, gText);
    const hot = sp.series.map(s => { const c = svg('circle', { r: 4, class: 'dot', visibility: 'hidden' }, gText); c.style.fill = seriesColor(s.slot); return c; });
    const overlay = svg('rect', { x: left - 6, y: top, width: W - left - right + 12, height: H - top - axisH, class: 'hit', tabindex: '0' }, root);
    overlay.setAttribute('aria-label', (sp.aria || 'Line chart') + '. Use left and right arrow keys to read values.');
    let cur = -1;
    function show(i, evt) {
      cur = Math.max(0, Math.min(n - 1, i));
      cross.setAttribute('x1', X(cur)); cross.setAttribute('x2', X(cur)); cross.setAttribute('visibility', 'visible');
      sp.series.forEach((s, k) => {
        const v = s.values[cur];
        if (v == null) { hot[k].setAttribute('visibility', 'hidden'); return; }
        hot[k].setAttribute('cx', X(cur)); hot[k].setAttribute('cy', Y(v)); hot[k].setAttribute('visibility', 'visible');
      });
      const rows = sp.series.map(s => ({ slot: s.slot, value: s.values[cur] == null ? '–' : sp.fmt(s.values[cur]), label: single ? sp.valueLabel || '' : s.label }));
      if (sp.extraTip) rows.push(...sp.extraTip(cur));
      setTip({ title: sp.cats[cur], rows });
      if (evt) placeTip(evt.clientX, evt.clientY);
      else { const b = overlay.getBoundingClientRect(); placeTip(b.left + X(cur) - left, b.top + 10); }
    }
    function hide() { cross.setAttribute('visibility', 'hidden'); hot.forEach(h => h.setAttribute('visibility', 'hidden')); hideTip(); }
    overlay.addEventListener('pointermove', e => {
      const b = overlay.getBoundingClientRect();
      const px = e.clientX - b.left + left - 6;
      show(n === 1 ? 0 : Math.round((px - left) / ((W - left - right) / (n - 1))), e);
    });
    overlay.addEventListener('pointerleave', hide);
    overlay.addEventListener('blur', hide);
    overlay.addEventListener('focus', () => show(cur < 0 ? n - 1 : cur));
    overlay.addEventListener('keydown', e => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        show((cur < 0 ? n - 1 : cur) + (e.key === 'ArrowRight' ? 1 : -1));
      }
    });
  }

  // Heatmap: rows x cols, 2px surface gap between cells.
  // sp: rows, cols, values[r][c], fmt, color(v), tip(r,c), scale{lo,hi,loLabel,hiLabel,midLabel}
  function drawHeat(host, sp) {
    const nr = sp.rows.length, nc = sp.cols.length;
    host.replaceChildren();
    const Wtmp = Math.max(260, Math.floor(host.clientWidth || 600));
    const labW = Math.min(Wtmp * 0.36, Math.max(...sp.rows.map(r => tw(r, 12))) + 14);
    const cw = (Wtmp - labW) / nc, cellH = nr > 24 ? 22 : 30, headH = 22;
    const H = headH + nr * cellH + 2;
    const { root, W } = frame(host, H, sp.aria);
    const gCells = svg('g', {}, root), gText = svg('g', {}, root), gHit = svg('g', {}, root);
    sp.cols.forEach((c, ci) => label(gText, labW + ci * cw + cw / 2, 14, fitText(c, cw - 6, 11), 'tick', 'middle'));
    sp.rows.forEach((r, ri) => {
      const y = headH + ri * cellH;
      label(gText, labW - 10, y + cellH / 2 + 4, fitText(r, labW - 12, 12), 'cat', 'end');
      sp.cols.forEach((c, ci) => {
        const v = sp.values[ri][ci];
        const x = labW + ci * cw;
        const fill = v == null ? cssVar('--surface-2') : sp.color(v);
        const rect = svg('rect', { x: x + 1, y: y + 1, width: Math.max(0, cw - 2), height: cellH - 2, rx: 2, fill, class: 'cellr' }, gCells);
        if (v != null) {
          const s = sp.fmt(v);
          if (tw(s, 11.5, 500) + 8 <= cw - 2 && cellH >= 22) {
            const t = label(gText, x + cw / 2, y + cellH / 2 + 4, s, 'cell', 'middle');
            t.style.fill = inkOn(fill);
          }
        }
        hitRect(gHit, x, y, cw, cellH, () => sp.tip(ri, ci), [rect]);
      });
    });
    if (sp.scale) host.append(scaleLegend(sp.scale));
  }
  function scaleLegend(sc) {
    const wrap = el('div', 'lg-scale');
    const bar = el('span', 'lg-bar');
    const stops = [0, 0.25, 0.5, 0.75, 1].map(t => sc.color(sc.lo + (sc.hi - sc.lo) * t));
    bar.style.background = `linear-gradient(90deg, ${stops.join(', ')})`;
    wrap.append(el('span', '', sc.loLabel), bar, el('span', '', sc.hiLabel));
    if (sc.midLabel) wrap.append(el('span', 'note', sc.midLabel));
    return wrap;
  }

  // Range strips: 10th-90th hairline, 25th-75th bar, median dot.
  function drawRange(host, sp) {
    const nc = sp.cats.length, band = 34, top = 4, axisH = 24;
    const H = top + nc * band + axisH;
    const { root, W } = frame(host, H, sp.aria);
    const hiV = Math.max(...sp.stats.map(s => s.p90));
    const loV = Math.min(0, ...sp.stats.map(s => s.p10));
    const labW = Math.min(W * 0.4, Math.max(...sp.cats.map(c => tw(c, 12))) + 14);
    const endW = Math.max(...sp.stats.map(s => tw(sp.fmt(s.med), 12, 500))) + 12;
    const x0 = labW, x1 = W - endW;
    const nt = niceTicks(loV, hiV, Math.max(2, Math.round((x1 - x0) / 110)));
    const X = v => x0 + (v - nt.lo) / (nt.hi - nt.lo) * (x1 - x0);
    const gGrid = svg('g', {}, root), gMarks = svg('g', {}, root), gText = svg('g', {}, root), gHit = svg('g', {}, root);
    const plotBot = top + nc * band;
    for (const t of nt.ticks) {
      svg('line', { x1: X(t), x2: X(t), y1: top, y2: plotBot, class: t === 0 ? 'axis' : 'grid' }, gGrid);
      label(gText, X(t), plotBot + 16, sp.axis(t), 'tick', 'middle');
    }
    sp.stats.forEach((s, ci) => {
      const cy = top + ci * band + band / 2;
      label(gText, labW - 10, cy + 4, fitText(sp.cats[ci], labW - 12, 12), 'cat', 'end');
      const whisk = svg('line', { x1: X(s.p10), x2: X(s.p90), y1: cy, y2: cy, class: 'mark' }, gMarks);
      whisk.style.stroke = seriesColor(0); whisk.style.strokeWidth = 2; whisk.style.opacity = 0.45;
      const box = svg('rect', { x: X(s.p25), y: cy - 6, width: Math.max(1, X(s.p75) - X(s.p25)), height: 12, rx: 4, class: 'mark' }, gMarks);
      box.style.fill = seriesColor(0);
      const dot = svg('circle', { cx: X(s.med), cy, r: 5, class: 'dot mark' }, gMarks);
      dot.style.fill = 'var(--ink)';
      label(gText, X(s.p90) + 8, cy + 4, sp.fmt(s.med), 'val');
      hitRect(gHit, 0, cy - band / 2, W, band, () => sp.tip(ci), [box, dot]);
    });
  }

  // 100% stacked horizontal bars with a 2px surface gap between segments.
  function drawStack(host, sp) {
    const nc = sp.cats.length, band = 30, barH = 18, top = 4, axisH = 24;
    const H = top + nc * band + axisH;
    const { root, W } = frame(host, H, sp.aria);
    const labW = Math.min(W * 0.36, Math.max(...sp.cats.map(c => tw(c, 12))) + 14);
    const x0 = labW, x1 = W - 8, X = f => x0 + f * (x1 - x0);
    const gGrid = svg('g', {}, root), gMarks = svg('g', {}, root), gText = svg('g', {}, root), gHit = svg('g', {}, root);
    for (const t of [0, 0.25, 0.5, 0.75, 1]) {
      svg('line', { x1: X(t), x2: X(t), y1: top, y2: top + nc * band, class: t === 0 ? 'axis' : 'grid' }, gGrid);
      label(gText, X(t), top + nc * band + 16, fmtPctAxis(t), 'tick', t === 0 ? 'start' : t === 1 ? 'end' : 'middle');
    }
    sp.cats.forEach((cat, ci) => {
      const y = top + ci * band + (band - barH) / 2;
      label(gText, labW - 10, y + barH / 2 + 4, fitText(cat, labW - 12, 12), 'cat', 'end');
      let acc = 0;
      const marks = [];
      const segs = sp.series.map((se, si) => ({ se, v: sp.values[ci][si] || 0 })).filter(s => s.v > 0);
      segs.forEach((s, k) => {
        const xa = X(acc), xb = X(acc + s.v) - (k < segs.length - 1 ? 2 : 0);
        acc += s.v;
        const r = svg('rect', { x: xa, y, width: Math.max(0.5, xb - xa), height: barH, class: 'mark' }, gMarks);
        const color = cssVar(`--s${(s.se.slot % 8) + 1}`);
        r.style.fill = color;
        marks.push(r);
        const txt = fmtPct(s.v);
        if (tw(txt, 11.5, 500) + 10 <= xb - xa) {
          const t = label(gText, (xa + xb) / 2, y + barH / 2 + 4, txt, 'cell', 'middle');
          t.style.fill = inkOn(color);
        }
      });
      hitRect(gHit, 0, top + ci * band, W, band, () => sp.tip(ci), marks);
    });
  }

  // ---------------------------------------------------------------- card scaffolding
  const cards = [];
  function segmented(options, value, onChange) {
    const g = el('div', 'seg');
    g.setAttribute('role', 'radiogroup');
    options.forEach(([v, text]) => {
      const b = el('button', '', text);
      b.type = 'button';
      b.dataset.value = v;
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', String(v === value));
      b.addEventListener('click', () => {
        g.querySelectorAll('button').forEach(x => x.setAttribute('aria-checked', String(x === b)));
        onChange(v);
      });
      g.append(b);
    });
    return g;
  }

  function makeCard(parent, o) {
    const card = el('article', 'card' + (o.wide ? ' wide' : ''));
    const head = el('div', 'card-head');
    const titles = el('div', 'card-titles');
    if (o.eyebrow) titles.append(el('span', 'eyebrow', o.eyebrow));
    titles.append(el(o.titleTag || 'h3', o.titleClass || '', o.title));
    const question = el('p', 'question', o.question || '');
    if (!o.question) question.hidden = true;
    titles.append(question);
    const tools = el('div', 'card-tools');
    const api = { card, segValue: o.segValue, tableOn: false, dirty: true, lastW: 0, draw: null, update: null, panel: o.panel || 'dashboard' };
    if (o.segments) tools.append(api.seg = segmented(o.segments, o.segValue, v => { api.segValue = v; api.update(); api.redraw(); }));
    const tbtn = el('button', 'ghost-btn', 'Table');
    tbtn.type = 'button';
    tbtn.setAttribute('aria-pressed', 'false');
    if (!o.noTableToggle) tools.append(tbtn);
    head.append(titles, tools);
    api.titleEl = titles.querySelector(o.titleTag || 'h3');
    api.question = question;
    api.reading = el('p', 'reading');
    api.chips = el('div', 'chips');
    api.extra = el('div', '');
    api.extra.hidden = true;
    api.legend = el('div', 'legend');
    api.chart = el('div', 'chart');
    api.tablev = el('div', '');
    api.tablev.hidden = true;
    api.note = el('p', 'note', o.note || '');
    if (!o.note) api.note.hidden = true;
    card.append(head, api.reading, api.chips, api.extra, api.legend, api.chart, api.tablev, api.note);
    parent.append(card);
    tbtn.addEventListener('click', () => {
      api.tableOn = !api.tableOn;
      tbtn.setAttribute('aria-pressed', String(api.tableOn));
      tbtn.textContent = api.tableOn ? 'Chart' : 'Table';
      api.chart.hidden = api.tableOn;
      api.legend.hidden = api.tableOn;
      api.extra.hidden = api.tableOn || !api.extra.childElementCount;
      api.tablev.hidden = !api.tableOn;
      if (!api.tableOn) api.redraw();
    });
    api.redraw = () => {
      if (!api.draw || api.tableOn) return;
      if (api.chart.clientWidth > 0) { api.dirty = false; api.lastW = api.chart.clientWidth; hideTip(); api.draw(); }
      else api.dirty = true;
    };
    new ResizeObserver(() => {
      const w = api.chart.clientWidth;
      if (w > 0 && (w !== api.lastW || api.dirty)) api.redraw();
    }).observe(api.chart);
    cards.push(api);
    return api;
  }

  function setLegend(api, series, kind) {
    api.legend.replaceChildren();
    if (series.length < 2) return;
    for (const s of series) {
      const item = el('span', 'lg');
      const sw = el('span', 'sw' + (kind === 'line' ? ' line' : ''));
      sw.style.background = s.color || seriesColor(s.slot);
      item.append(sw, el('span', '', s.label));
      api.legend.append(item);
    }
  }

  function setReading(api, parts) {
    api.reading.replaceChildren();
    if (!parts) parts = ONE_GROUP;
    for (const p of parts) {
      if (typeof p === 'string') api.reading.append(document.createTextNode(p));
      else api.reading.append(el('b', '', p.b));
    }
  }

  const ICON_CHECK = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 6.2l2.3 2.3 4.7-5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const ICON_DASH = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 6h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  function setTest(api, res, kind) {
    api.chips.replaceChildren();
    if (!res) return;
    const sig = res.p < ALPHA;
    const pill = el('span', 'pill' + (sig ? ' sig' : ''));
    pill.innerHTML = sig ? ICON_CHECK : ICON_DASH;
    const what = kind === 'chi' ? 'association' : kind === 'anova' ? 'difference between groups' : 'correlation';
    pill.append(document.createTextNode(sig ? `Significant ${what} (α = 0.05)` : `No significant ${what} (α = 0.05)`));
    let stat;
    if (kind === 'chi') stat = `χ²(${res.df}) = ${nf2.format(res.chi2)}, ${fmtP(res.p)}, Cramér’s V = ${res.cramersV.toFixed(3)}`;
    else stat = `ANOVA F(${res.df1}, ${nf0.format(res.df2)}) = ${nf2.format(res.f)}, ${fmtP(res.p)}, η² ${res.eta2 < 0.0001 ? '< 0.0001' : '= ' + res.eta2.toFixed(4)}`;
    api.chips.append(pill, el('span', 'stat', stat));
  }

  function renderTable(host, cols, rows) {
    host.replaceChildren();
    const wrap = el('div', 'table-wrap');
    const table = el('table');
    const thead = el('thead'), htr = el('tr');
    cols.forEach(c => htr.append(el('th', c.num ? 'num' : '', c.label)));
    thead.append(htr);
    const tbody = el('tbody');
    rows.forEach(r => {
      const tr = el('tr');
      r.forEach((v, i) => tr.append(el('td', cols[i].num ? 'num' : '', v)));
      tbody.append(tr);
    });
    table.append(thead, tbody);
    wrap.append(table);
    host.append(wrap);
  }

  function extremes(names, vals, fmt) {
    const idx = vals.map((v, i) => i).filter(i => vals[i] != null);
    if (idx.length < 2) return null;
    let hi = idx[0], lo = idx[0];
    for (const i of idx) { if (vals[i] > vals[hi]) hi = i; if (vals[i] < vals[lo]) lo = i; }
    const gap = vals[hi] - vals[lo];
    const rel = vals[lo] !== 0 ? Math.abs(gap / vals[lo]) * 100 : null;
    return [
      'Highest: ', { b: `${names[hi]}, ${fmt(vals[hi])}` }, '. Lowest: ', { b: `${names[lo]}, ${fmt(vals[lo])}` },
      `. Gap: ${fmt(gap)}${rel != null ? ` (${nf1.format(rel)}%)` : ''}.`,
    ];
  }
  const ONE_GROUP = ['Only one group is left in the current filter. Clear a filter to compare groups.'];

  function groupValues(c, kind) { return c.xs.map(x => valuesOf(c.xRows(x), kind)); }

  // ---------------------------------------------------------------- KPIs
  function renderKpis(rows) {
    const host = document.getElementById('kpis');
    const filtered = rows.length < N;
    const losAll = valuesOf(ALL, 'los'), los = valuesOf(rows, 'los');
    const tiles = [
      { label: 'Admissions', v: rows.length, all: N, fmt: fmtInt, share: true },
      { label: 'Patient-days', v: sum(los), all: sum(losAll), fmt: fmtInt, share: true },
      { label: 'Average length of stay', v: mean(los), all: mean(losAll), fmt: v => nf2.format(v), unit: 'days' },
      { label: 'Average bill', v: mean(valuesOf(rows, 'bill')), all: mean(valuesOf(ALL, 'bill')), fmt: fmtMoney },
      { label: 'Median bill per patient-day', v: median(valuesOf(rows, 'perday')), all: median(valuesOf(ALL, 'perday')), fmt: fmtMoney },
      { label: 'Negative bills (flagged)', v: rows.reduce((n, r) => n + (C.billCents[r] < 0 ? 1 : 0), 0), fmt: fmtInt, note: state.excludeAdj ? 'left out of cost figures' : 'included in cost figures' },
    ];
    host.replaceChildren();
    for (const t of tiles) {
      const k = el('div', 'kpi');
      const val = el('div', 'kpi-value', t.v == null ? '–' : t.fmt(t.v));
      if (t.unit) val.append(el('span', 'kpi-unit', t.unit));
      let delta = t.note || '';
      if (!t.note && filtered && t.v != null && t.all) {
        delta = t.share ? `${nf1.format(t.v / t.all * 100)}% of all admissions` : `${fmtSignedPct((t.v - t.all) / t.all * 100)} vs all admissions`;
      }
      if (!t.note && !filtered) delta = 'all admissions';
      k.append(el('div', 'kpi-label', t.label), val, el('div', 'kpi-delta', delta));
      host.append(k);
    }
  }

  // ---------------------------------------------------------------- dashboard cards
  const dashGrid = document.getElementById('dash-grid');

  // Q1: condition mix by gender / age group
  const q1 = makeCard(dashGrid, {
    eyebrow: 'Q1', title: 'Condition mix by patient group',
    question: 'Is there a correlation between gender or age and type of disease?',
    segments: [['gender', 'Gender'], ['ageGroup', 'Age group']], segValue: 'gender',
    note: 'Each row adds to 100%. If gender or age had no link to condition, every cell would sit near an even share. Colour shows how far each cell is from that share.',
  });
  q1.update = () => {
    const dim = q1.segValue, c = cube(ROWS, dim, 'condition');
    const counts = c.xs.map(x => c.ss.map(s => c.cell(x, s).length));
    const tot = counts.map(r => r.reduce((a, b) => a + b, 0));
    const shares = counts.map((r, i) => r.map(v => (tot[i] ? v / tot[i] : null)));
    const even = 1 / c.ss.length;
    let maxDev = 0, best = null;
    shares.forEach((r, i) => r.forEach((v, j) => { const d = Math.abs(v - even); if (d > maxDev) { maxDev = d; best = [i, j]; } }));
    const rowNames = c.xs.map(x => DIMS[dim].values[x]);
    const colNames = c.ss.map(s => DIMS.condition.values[s]);
    const extent = Math.max(0.02, maxDev);
    const flat = shares.flat();
    if (c.ss.length < 2) setReading(q1, ['Only one condition is left in the current filter. Clear the condition filter to compare.']);
    else {
      const parts = [`Shares run from `, { b: fmtPct(Math.min(...flat)) }, ' to ', { b: fmtPct(Math.max(...flat)) }, ` against an even ${fmtPct(even)}. `];
      if (best) {
        const n = tot[best[0]];
        parts.push('Largest gap: ', { b: `${colNames[best[1]]} among ${rowNames[best[0]]}` }, `, ${fmtPts(shares[best[0]][best[1]] - even)}`);
        parts.push(n < 1000 ? ` (only ${fmtInt(n)} admissions, so expect noise).` : '.');
      }
      setReading(q1, parts);
    }
    setTest(q1, Stats.chiSquare(counts), 'chi');
    q1.legend.replaceChildren();
    const spec = {
      aria: 'Heatmap of condition share by ' + DIMS[dim].label,
      rows: rowNames.map((r, i) => `${r} (n=${fmtInt(tot[i])})`), cols: colNames, values: shares, fmt: fmtPct,
      tip: (ri, ci) => ({ title: `${rowNames[ri]} · ${colNames[ci]}`, rows: [
        { value: fmtPct(shares[ri][ci]), label: 'of the group' },
        { value: fmtInt(counts[ri][ci]), label: 'admissions' },
        { value: fmtPts(shares[ri][ci] - even), label: `vs even ${fmtPct(even)}` },
      ] }),
    };
    q1.draw = () => {
      const color = diverging(even, extent);
      drawHeat(q1.chart, Object.assign({}, spec, { color, scale: { lo: even - extent, hi: even + extent, color, loLabel: `Less common (${fmtPct(even - extent)})`, hiLabel: `More common (${fmtPct(even + extent)})` } }));
    };
    renderTable(q1.tablev, [{ label: DIMS[dim].label }, { label: 'Condition' }, { label: 'Admissions', num: true }, { label: 'Share of group', num: true }],
      shares.flatMap((r, i) => r.map((v, j) => [rowNames[i], colNames[j], fmtInt(counts[i][j]), fmtPct(v)])));
  };

  // Q2: implied insurer discount
  const q2 = makeCard(dashGrid, {
    eyebrow: 'Q2', title: 'Implied insurer discount',
    question: 'What is the mean healthcare insurance provider discount?',
    note: 'The data has no discount or amount-paid field. This compares each insurer’s average bill with the average across all insurers in the current filter. A negative value is an implied discount.',
  });
  q2.update = () => {
    const c = cube(ROWS, 'insurer');
    const overall = aggregate(ROWS, 'avgBill');
    const names = c.xs.map(x => DIMS.insurer.values[x]);
    const avg = c.xs.map(x => aggregate(c.cell(x), 'avgBill'));
    const pct = avg.map(a => (a == null || !overall ? null : (a - overall) / overall * 100));
    const order = pct.map((_, i) => i).sort((a, b) => pct[a] - pct[b]);
    if (c.xs.length < 2) setReading(q2, ONE_GROUP);
    else {
      const meanAbs = mean(pct.map(Math.abs));
      const lo = order[0];
      setReading(q2, [
        'Mean gap from the overall average bill (', { b: fmtMoney(overall) }, '): ', { b: nf2.format(meanAbs) + '%' }, '. ',
        pct[lo] < 0 ? 'Largest implied discount: ' : 'No insurer is billed below average. Lowest: ',
        { b: `${names[lo]}, ${fmtSignedPct(pct[lo])}` }, ` (${fmtMoney(avg[lo] - overall)} per admission).`,
      ]);
    }
    setTest(q2, Stats.anova(groupValues(c, 'bill')), 'anova');
    const sp = {
      aria: 'Average bill versus overall, by insurer',
      cats: order.map(i => names[i]), series: [{ label: 'vs overall', slot: 0 }], values: order.map(i => [pct[i]]),
      fmt: fmtSignedPct, axis: fmtSignedPctAxis,
      colorOf: (ci, si, v) => (v < 0 ? 'var(--neg)' : 'var(--pos)'),
      tip: ci => { const i = order[ci]; return { title: names[i], rows: [
        { value: fmtSignedPct(pct[i]), label: 'vs overall average', color: pct[i] < 0 ? 'var(--neg)' : 'var(--pos)' },
        { value: fmtMoney2(avg[i]), label: 'average bill' },
        { value: fmtMoney(avg[i] - overall), label: 'difference per admission' },
        { value: fmtInt(c.cell(c.xs[i]).length), label: 'admissions' },
      ] }; },
    };
    setLegend(q2, [{ label: 'Below average (implied discount)', color: 'var(--neg)' }, { label: 'Above average', color: 'var(--pos)' }]);
    q2.draw = () => drawHBar(q2.chart, sp);
    renderTable(q2.tablev, [{ label: 'Insurer' }, { label: 'Admissions', num: true }, { label: 'Average bill', num: true }, { label: 'vs overall ($)', num: true }, { label: 'vs overall (%)', num: true }],
      order.map(i => [names[i], fmtInt(c.cell(c.xs[i]).length), fmtMoney2(avg[i]), fmtMoney2(avg[i] - overall), fmtSignedPct(pct[i])]));
  };

  // Shared: average length of stay by a dimension
  function losByDim(api, dim) {
    const c = cube(ROWS, dim);
    const names = c.xs.map(x => DIMS[dim].values[x]);
    const avg = c.xs.map(x => aggregate(c.cell(x), 'avgLos'));
    const med = c.xs.map(x => aggregate(c.cell(x), 'medLos'));
    const n = c.xs.map(x => c.cell(x).length);
    const order = names.map((_, i) => i);
    if (!DIMS[dim].ordered) order.sort((a, b) => avg[b] - avg[a]);
    setReading(api, c.xs.length < 2 ? ONE_GROUP : extremes(names, avg, fmtDays));
    setTest(api, Stats.anova(groupValues(c, 'los')), 'anova');
    const sp = {
      aria: 'Average length of stay by ' + DIMS[dim].label,
      cats: order.map(i => names[i]), series: [{ label: 'Average stay', slot: 0 }], values: order.map(i => [avg[i]]),
      fmt: v => nf2.format(v) + ' d', axis: fmtNum,
      tip: ci => { const i = order[ci]; return { title: names[i], rows: [
        { value: fmtDays(avg[i]), label: 'average stay', slot: 0 },
        { value: fmtDays(med[i]), label: 'median stay' },
        { value: fmtInt(n[i]), label: 'admissions' },
      ] }; },
    };
    api.draw = () => drawHBar(api.chart, sp);
    renderTable(api.tablev, [{ label: DIMS[dim].label }, { label: 'Admissions', num: true }, { label: 'Average stay (days)', num: true }, { label: 'Median stay (days)', num: true }],
      order.map(i => [names[i], fmtInt(n[i]), nf2.format(avg[i]), fmtNum(med[i])]));
  }

  // Q3: condition vs length of stay
  const q3 = makeCard(dashGrid, {
    eyebrow: 'Q3', title: 'Length of stay by condition',
    question: 'Is there a correlation between medical condition and treatment length?',
    note: 'Bars start at zero, so small gaps look small. Hover a bar for the median and the number of admissions.',
  });
  q3.update = () => losByDim(q3, 'condition');

  // Q4: billing distribution by insurer
  const q4 = makeCard(dashGrid, {
    eyebrow: 'Q4', title: 'Bills by insurance company',
    question: 'How does the billing amount compare across insurance companies?',
  });
  q4.update = () => {
    const c = cube(ROWS, 'insurer');
    const names = c.xs.map(x => DIMS.insurer.values[x]);
    const stats = c.xs.map(x => {
      const s = sorted(valuesOf(c.cell(x), 'bill'));
      return { p10: quantile(s, 0.1), p25: quantile(s, 0.25), med: quantile(s, 0.5), p75: quantile(s, 0.75), p90: quantile(s, 0.9), mean: mean(s), total: sum(s), n: s.length };
    });
    const order = names.map((_, i) => i).sort((a, b) => stats[b].med - stats[a].med);
    setReading(q4, c.xs.length < 2 ? ONE_GROUP : ['Median bill by insurer. ', ...extremes(names, stats.map(s => s.med), fmtMoney)]);
    setTest(q4, Stats.anova(groupValues(c, 'bill')), 'anova');
    q4.legend.replaceChildren();
    const keys = [['line', '10th–90th percentile'], ['rect', 'Middle half (25th–75th)'], ['dot', 'Median']];
    for (const [k, t] of keys) {
      const item = el('span', 'lg'), sw = el('span', 'sw' + (k === 'line' ? ' line' : ''));
      sw.style.background = k === 'dot' ? 'var(--ink)' : seriesColor(0);
      if (k === 'line') sw.style.opacity = 0.45;
      if (k === 'dot') sw.style.borderRadius = '50%';
      item.append(sw, el('span', '', t));
      q4.legend.append(item);
    }
    const sp = {
      aria: 'Bill distribution by insurer',
      cats: order.map(i => names[i]), stats: order.map(i => stats[i]), fmt: fmtMoney, axis: fmtMoneyCompact,
      tip: ci => { const s = stats[order[ci]]; return { title: names[order[ci]], rows: [
        { value: fmtMoney(s.med), label: 'median' }, { value: fmtMoney(s.mean), label: 'average' },
        { value: `${fmtMoney(s.p25)} – ${fmtMoney(s.p75)}`, label: 'middle half' },
        { value: fmtMoneyCompact(s.total), label: 'total billed' }, { value: fmtInt(s.n), label: 'admissions' },
      ] }; },
    };
    q4.draw = () => drawRange(q4.chart, sp);
    renderTable(q4.tablev, ['Insurer', 'Admissions', 'Total billed', 'Average', 'Median', '25th pct', '75th pct'].map((l, i) => ({ label: l, num: i > 0 })),
      order.map(i => { const s = stats[i]; return [names[i], fmtInt(s.n), fmtMoney(s.total), fmtMoney2(s.mean), fmtMoney2(s.med), fmtMoney(s.p25), fmtMoney(s.p75)]; }));
  };

  // Q5: bill per patient-day by age group and gender
  const q5 = makeCard(dashGrid, {
    eyebrow: 'Q5', title: 'Bill per patient-day by age and gender',
    question: 'How does the billing rate, based on length of stay, compare between age and gender?',
    segments: [['medPerDay', 'Median'], ['avgPerDay', 'Average']], segValue: 'medPerDay',
    note: 'Bill per patient-day is the bill divided by the length of stay. A one-day stay puts the whole bill on a single day, which pulls the average far above the median.',
  });
  q5.update = () => {
    const mk = q5.segValue, c = cube(ROWS, 'ageGroup', 'gender');
    const { v, n } = matrix(c, mk);
    const xn = c.xs.map(x => DIMS.ageGroup.values[x]);
    const series = c.ss.map(s => ({ label: DIMS.gender.values[s], slot: s }));
    const cells = [], cellNames = [];
    v.forEach((r, i) => r.forEach((val, j) => { cells.push(val); cellNames.push(`${series[j].label}, ${xn[i]}`); }));
    setReading(q5, cells.length < 2 ? ONE_GROUP : extremes(cellNames, cells, fmtMoney));
    q5.chips.replaceChildren();
    setLegend(q5, series);
    const sp = {
      aria: METRICS[mk].label + ' by age group and gender', height: 250,
      cats: xn, series, values: v, fmt: fmtMoney, axis: fmtMoneyCompact,
      tip: ci => ({ title: xn[ci], rows: series.map((s, j) => ({ slot: s.slot, value: v[ci][j] == null ? '–' : fmtMoney(v[ci][j]), label: `${s.label} (n=${fmtInt(n[ci][j])})` })) }),
    };
    q5.draw = () => drawVBar(q5.chart, sp);
    renderTable(q5.tablev, [{ label: 'Age group' }, { label: 'Gender' }, { label: 'Admissions', num: true }, { label: METRICS[mk].label, num: true }],
      v.flatMap((r, i) => r.map((val, j) => [xn[i], series[j].label, fmtInt(n[i][j]), val == null ? '–' : fmtMoney2(val)])));
  };

  // Q6: length of stay by condition / age group / admission type
  const q6 = makeCard(dashGrid, {
    eyebrow: 'Q6', title: 'How long patients stay',
    question: 'How long do patients stay, and does it vary by condition, age group, or admission type?',
    segments: [['admType', 'Admission type'], ['ageGroup', 'Age group'], ['condition', 'Condition']], segValue: 'admType',
  });
  q6.update = () => losByDim(q6, q6.segValue);

  // Length-of-stay distribution
  const qd = makeCard(dashGrid, {
    eyebrow: 'Q6', title: 'Distribution of stay length',
    question: 'Admissions by number of days in hospital.',
  });
  qd.update = () => {
    const c = cube(ROWS, 'los');
    const days = DIMS.los.values;
    const counts = days.map((_, i) => c.cell(i).length);
    const los = valuesOf(ROWS, 'los');
    const med = median(los);
    let mode = 0;
    counts.forEach((v, i) => { if (v > counts[mode]) mode = i; });
    setReading(qd, ROWS.length ? ['Median stay: ', { b: fmtDays(med) }, '. Stays run from 1 to 30 days and are spread almost evenly. The most common is ', { b: `${days[mode]} days` }, ` (${fmtInt(counts[mode])} admissions).`] : ['No admissions match the current filter.']);
    const sp = {
      aria: 'Admissions by length of stay', height: 220,
      cats: days, series: [{ label: 'Admissions', slot: 0 }], values: counts.map(v => [v]),
      fmt: fmtInt, axis: fmtCompact, tick: i => i === 0 || (i + 1) % 5 === 0,
      tip: ci => ({ title: `${days[ci]} day${ci ? 's' : ''}`, rows: [{ value: fmtInt(counts[ci]), label: 'admissions', slot: 0 }, { value: ROWS.length ? fmtPct(counts[ci] / ROWS.length) : '–', label: 'of admissions' }] }),
    };
    qd.draw = () => drawVBar(qd.chart, Object.assign({}, sp, { values: sp.values }));
    renderTable(qd.tablev, [{ label: 'Length of stay (days)' }, { label: 'Admissions', num: true }, { label: 'Share', num: true }],
      days.map((d, i) => [d, fmtInt(counts[i]), ROWS.length ? fmtPct(counts[i] / ROWS.length) : '–']));
  };

  // Q7: correlations
  const q7 = makeCard(dashGrid, {
    eyebrow: 'Extra', title: 'Does a longer stay cost more?',
    question: 'Pearson correlation between bill, length of stay, and age. Values near 0 mean no straight-line relationship.',
  });
  q7.update = () => {
    const bill = [], los = [], age = [], losA = [], ageA = [];
    const ex = state.excludeAdj;
    for (let i = 0; i < ROWS.length; i++) {
      const r = ROWS[i];
      losA.push(C.los[r]); ageA.push(C.age[r]);
      if (ex && C.billCents[r] < 0) continue;
      bill.push(C.billCents[r] / 100); los.push(C.los[r]); age.push(C.age[r]);
    }
    const tests = [
      ['Bill vs length of stay', Stats.pearson(bill, los)],
      ['Bill vs age', Stats.pearson(bill, age)],
      ['Length of stay vs age', Stats.pearson(losA, ageA)],
    ];
    q7.extra.className = 'figs';
    q7.extra.replaceChildren();
    for (const [name, res] of tests) {
      const f = el('div', 'fig');
      f.append(el('div', 'fig-label', name), el('div', 'fig-value', res ? 'r = ' + (res.r < 0 ? MINUS : '') + Math.abs(res.r).toFixed(3) : '–'),
        el('div', 'fig-meta', res ? `${fmtP(res.p)} · n = ${fmtInt(res.n)}` : 'not enough data'));
      q7.extra.append(f);
    }
    q7.extra.hidden = q7.tableOn;
    const strongest = Math.max(...tests.map(t => (t[1] ? Math.abs(t[1].r) : 0)));
    setReading(q7, [strongest < 0.1 ? 'No meaningful relationship: every |r| is below 0.1. ' : 'At least one pair shows a weak relationship. ', 'The chart shows the average bill for each stay length.']);
    const c = cube(ROWS, 'los');
    const days = DIMS.los.values;
    const avg = days.map((_, i) => aggregate(c.cell(i), 'avgBill'));
    const sp = {
      aria: 'Average bill by length of stay', height: 200,
      cats: days, series: [{ label: 'Average bill', slot: 0 }], values: avg.map(v => [v]),
      fmt: fmtMoneyCompact, axis: fmtMoneyCompact, tick: i => i === 0 || (i + 1) % 5 === 0,
      tip: ci => ({ title: `${days[ci]}-day stays`, rows: [{ value: avg[ci] == null ? '–' : fmtMoney(avg[ci]), label: 'average bill', slot: 0 }, { value: fmtInt(c.cell(ci).length), label: 'admissions' }] }),
    };
    q7.draw = () => drawVBar(q7.chart, sp);
    renderTable(q7.tablev, [{ label: 'Pair' }, { label: 'r', num: true }, { label: 'p-value', num: true }, { label: 'n', num: true }],
      tests.map(([nm, r]) => [nm, r ? r.r.toFixed(4) : '–', r ? (r.p < 0.001 ? '< 0.001' : r.p.toFixed(3)) : '–', r ? fmtInt(r.n) : '–']));
  };

  // Trend
  const qt = makeCard(dashGrid, {
    eyebrow: 'Trend', title: 'Admissions and bills by month', wide: true,
    question: 'Monthly volume and average bill. Two charts, one scale each.',
    note: `The data starts on ${MONTHS[sm - 1]} ${sd}, ${sy} and the last admission is ${MONTHS[lm]} ${lastAdmit.getUTCDate()}, ${ly}, so the first and last months are partial.`,
  });
  qt.update = () => {
    const c = cube(ROWS, 'month');
    const idx = c.xs.length ? Array.from({ length: c.xs[c.xs.length - 1] - c.xs[0] + 1 }, (_, i) => c.xs[0] + i) : [];
    const cats = idx.map(i => monthLabels[i]);
    const counts = idx.map(i => c.cell(i).length);
    const avg = idx.map(i => (c.cell(i).length ? aggregate(c.cell(i), 'avgBill') : null));
    const inner = counts.slice(1, -1);
    if (inner.length >= 2) {
      const hi = inner.indexOf(Math.max(...inner)) + 1, lo = inner.indexOf(Math.min(...inner)) + 1;
      setReading(qt, ['Full months range from ', { b: `${fmtInt(counts[lo])} admissions (${cats[lo]})` }, ' to ', { b: `${fmtInt(counts[hi])} (${cats[hi]})` }, '. The average bill stays close to ', { b: fmtMoney(mean(avg.filter(v => v != null))) }, '.']);
    } else setReading(qt, ['Too few months in the current filter to show a trend.']);
    const jans = idx.filter(i => monthIsJan[i]).length;
    const tick = jans >= 2 ? i => monthIsJan[idx[i]] : null;
    const tickLabel = i => (monthIsJan[idx[i]] ? monthLabels[idx[i]].slice(4) : monthLabels[idx[i]]);
    qt.draw = () => {
      qt.chart.replaceChildren();
      const pair = el('div', 'chart-pair');
      const a = el('div'), b = el('div');
      const ha = el('div', 'chart'), hb = el('div', 'chart');
      a.append(el('p', 'sub-title', 'Admissions per month'), ha);
      b.append(el('p', 'sub-title', 'Average bill per month'), hb);
      pair.append(a, b);
      qt.chart.append(pair);
      if (!cats.length) return;
      drawLine(ha, { aria: 'Admissions per month', cats, series: [{ label: 'Admissions', slot: 0, values: counts }], fmt: fmtInt, axis: fmtCompact, tick, tickLabel, valueLabel: 'admissions', height: 220 });
      drawLine(hb, { aria: 'Average bill per month', cats, series: [{ label: 'Average bill', slot: 0, values: avg }], fmt: fmtMoney, axis: fmtMoneyCompact, tick, tickLabel, valueLabel: 'average bill', height: 220 });
    };
    renderTable(qt.tablev, [{ label: 'Month' }, { label: 'Admissions', num: true }, { label: 'Average bill', num: true }],
      cats.map((m, i) => [m, fmtInt(counts[i]), avg[i] == null ? '–' : fmtMoney2(avg[i])]));
  };

  // ---------------------------------------------------------------- visualizer
  const PRESETS = [
    ['Q1', 'Condition by gender', { x: 'condition', s: 'gender', metric: 'share', chart: 'bars' }],
    ['Q1', 'Condition by age group', { x: 'ageGroup', s: 'condition', metric: 'share', chart: 'heatmap' }],
    ['Q2', 'Average bill by insurer', { x: 'insurer', s: '', metric: 'avgBill', chart: 'bars' }],
    ['Q3', 'Stay length by condition', { x: 'condition', s: '', metric: 'avgLos', chart: 'bars' }],
    ['Q4', 'Bill size mix by insurer', { x: 'insurer', s: 'billBand', metric: 'share', chart: 'stacked' }],
    ['Q5', 'Bill per patient-day, age × gender', { x: 'ageGroup', s: 'gender', metric: 'medPerDay', chart: 'bars' }],
    ['Q6', 'Stay length by admission type', { x: 'admType', s: '', metric: 'avgLos', chart: 'bars' }],
    ['Trend', 'Monthly admissions by type', { x: 'month', s: 'admType', metric: 'count', chart: 'lines' }],
  ];
  const presetHost = document.getElementById('presets');
  for (const [tag, text, cfg] of PRESETS) {
    const b = el('button', 'preset');
    b.type = 'button';
    b.append(el('b', '', tag), document.createTextNode(text));
    b.addEventListener('click', () => { Object.assign(state.viz, { fitY: false }, cfg); syncVizControls(); viz.update(); viz.redraw(); persist(); });
    presetHost.append(b);
  }

  const controls = document.getElementById('viz-controls');
  function field(id, text, node) {
    const f = el('div', 'field');
    const l = el('label', '', text);
    l.htmlFor = id;
    node.id = id;
    f.append(l, node);
    controls.append(f);
    return node;
  }
  function select(options) {
    const s = el('select');
    for (const [v, t] of options) { const o = el('option', '', t); o.value = v; s.append(o); }
    return s;
  }
  const DIM_KEYS = Object.keys(DIMS);
  const selX = field('viz-x', 'Group by', select(DIM_KEYS.map(k => [k, DIMS[k].label])));
  const selS = field('viz-s', 'Split by (colour)', select([['', 'None'], ...DIM_KEYS.filter(canSplit).map(k => [k, DIMS[k].label])]));
  const selM = field('viz-m', 'Measure', select(Object.keys(METRICS).map(k => [k, METRICS[k].label])));
  const chartWrap = el('div', 'field');
  chartWrap.append(el('span', 'ctl-label', 'Chart'));
  const chartSeg = segmented([['bars', 'Bars'], ['lines', 'Lines'], ['heatmap', 'Heatmap'], ['stacked', 'Stacked 100%']], state.viz.chart, v => { state.viz.chart = v; viz.update(); viz.redraw(); persist(); });
  chartWrap.append(chartSeg);
  controls.append(chartWrap);
  const fitLabel = el('label', 'check');
  const fitBox = el('input');
  fitBox.type = 'checkbox';
  fitBox.id = 'viz-fit';
  fitLabel.append(fitBox, document.createTextNode('Fit y-axis to the data (lines)'));
  controls.append(fitLabel);
  const swapBtn = el('button', 'ghost-btn', 'Swap group and split');
  swapBtn.type = 'button';
  controls.append(swapBtn, el('p', 'viz-hint', 'Only fields with 8 or fewer values can be a split, so each colour stays easy to tell apart.'));

  selX.addEventListener('change', () => { state.viz.x = selX.value; if (state.viz.s === state.viz.x) state.viz.s = ''; syncVizControls(); viz.update(); viz.redraw(); persist(); });
  selS.addEventListener('change', () => { state.viz.s = selS.value; syncVizControls(); viz.update(); viz.redraw(); persist(); });
  selM.addEventListener('change', () => { state.viz.metric = selM.value; viz.update(); viz.redraw(); persist(); });
  fitBox.addEventListener('change', () => { state.viz.fitY = fitBox.checked; viz.update(); viz.redraw(); persist(); });
  swapBtn.addEventListener('click', () => {
    const { x, s } = state.viz;
    if (!s || !canSplit(x)) return;
    state.viz.x = s; state.viz.s = x;
    syncVizControls(); viz.update(); viz.redraw(); persist();
  });

  function chartValidity(v) {
    const X = DIMS[v.x], S = v.s ? DIMS[v.s] : null;
    const marks = X.values.length * (S ? S.values.length : 1);
    return { bars: marks <= 96, lines: !!X.ordered, heatmap: !!S, stacked: !!S };
  }
  function syncVizControls() {
    const v = state.viz;
    selX.value = v.x;
    [...selS.options].forEach(o => { o.disabled = o.value === v.x; });
    selS.value = v.s;
    selM.value = v.metric;
    fitBox.checked = v.fitY;
    const ok = chartValidity(v);
    chartSeg.querySelectorAll('button').forEach(b => {
      b.disabled = !ok[b.dataset.value];
      b.setAttribute('aria-checked', String(b.dataset.value === v.chart));
    });
    swapBtn.disabled = !v.s || !canSplit(v.x);
  }

  const vizMain = document.getElementById('viz-main');
  const viz = makeCard(vizMain, { title: '', titleTag: 'h2', titleClass: 'viz-title', panel: 'visualizer', noTableToggle: true });
  const vizTableCard = el('article', 'card');
  const tTools = el('div', 'table-tools');
  const tTitle = el('h3', '', 'Data behind the chart');
  const copyBtn = el('button', 'ghost-btn', 'Copy table');
  copyBtn.type = 'button';
  tTools.append(tTitle, copyBtn);
  const vizTable = el('div');
  vizTableCard.append(tTools, vizTable);
  vizMain.append(vizTableCard);
  let vizTSV = '';
  copyBtn.addEventListener('click', () => {
    const done = ok => { copyBtn.textContent = ok ? 'Copied' : 'Select the table to copy'; setTimeout(() => { copyBtn.textContent = 'Copy table'; }, 1600); };
    try {
      navigator.clipboard.writeText(vizTSV).then(() => done(true), () => { selectTable(); done(false); });
    } catch (e) { selectTable(); done(false); }
  });
  function selectTable() {
    const t = vizTable.querySelector('table');
    if (!t) return;
    const range = document.createRange();
    range.selectNodeContents(t);
    const sel = getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  viz.update = () => {
    const v = state.viz, X = DIMS[v.x], S = v.s ? DIMS[v.s] : null, M = METRICS[v.metric];
    const ok = chartValidity(v);
    let chart = v.chart, switched = '';
    if (!ok[chart]) {
      chart = ['bars', 'lines', 'heatmap'].find(k => ok[k]);
      switched = chart === 'lines' ? 'Too many bars for this combination, so it is shown as lines.' : chart === 'heatmap' ? 'Too many bars for this combination, so it is shown as a heatmap.' : '';
      if (v.chart === 'lines' && !X.ordered) switched = 'Lines need an ordered field such as month or age group, so this is shown as bars.';
      if ((v.chart === 'heatmap' || v.chart === 'stacked') && !S) switched = 'Pick a split to use this chart type. Showing bars.';
      if (!chart) chart = 'heatmap';
    }
    const mk = chart === 'stacked' ? 'share' : v.metric;
    const Mx = METRICS[mk];
    const c = cube(ROWS, v.x, v.s);
    const { v: vals, n } = matrix(c, mk);
    const xn = c.xs.map(x => X.values[x]);
    const series = c.ss.map(s => ({ label: S ? S.values[s] : Mx.label, slot: S ? s : 0 }));
    const title = chart === 'stacked' ? `Mix of ${S.label.toLowerCase()} within each ${X.label.toLowerCase()}` : `${Mx.label} by ${X.label.toLowerCase()}${S ? `, split by ${S.label.toLowerCase()}` : ''}`;
    viz.titleEl.textContent = title;
    viz.question.hidden = !switched && !(mk === 'share' && S);
    viz.question.textContent = switched || (mk === 'share' && S ? `Shares add to 100% within each ${X.label.toLowerCase()}.` : '');
    // Reading
    if (!ROWS.length) setReading(viz, ['No admissions match the current filter.']);
    else {
      const names = [], cells = [];
      vals.forEach((r, i) => r.forEach((val, j) => { names.push(S ? `${xn[i]} · ${series[j].label}` : xn[i]); cells.push(val); }));
      setReading(viz, cells.filter(x => x != null).length < 2 ? ONE_GROUP : extremes(names, cells, Mx.fmt));
    }
    // Test
    viz.chips.replaceChildren();
    if (S && (mk === 'count' || mk === 'share') && c.xs.length > 1) setTest(viz, Stats.chiSquare(n), 'chi');
    else if (!S && M.stat === 'mean' && c.xs.length > 1) setTest(viz, Stats.anova(groupValues(c, M.kind)), 'anova');
    // Legend
    if (chart === 'heatmap') viz.legend.replaceChildren();
    else setLegend(viz, S ? series : [], chart === 'lines' ? 'line' : 'rect');
    const tip = ci => ({ title: xn[ci], rows: series.map((s, j) => ({ slot: S ? s.slot : 0, value: vals[ci][j] == null ? '–' : Mx.fmt(vals[ci][j]), label: `${S ? s.label + ' ' : ''}(n=${fmtInt(n[ci][j])})` })) });
    let order = xn.map((_, i) => i);
    if (chart === 'bars' && !X.ordered && !S) order.sort((a, b) => (vals[b][0] ?? -Infinity) - (vals[a][0] ?? -Infinity));
    viz.draw = () => {
      if (!xn.length) { viz.chart.replaceChildren(el('p', 'note', 'No admissions match the current filter.')); return; }
      if (chart === 'bars') {
        const sp = { aria: title, cats: order.map(i => xn[i]), series, values: order.map(i => vals[i]), fmt: Mx.fmt, axis: Mx.axis, tip: ci => tip(order[ci]), tick: X.tick ? ci => X.tick(c.xs[order[ci]]) : null, endLabels: true, height: 300 };
        (X.ordered ? drawVBar : drawHBar)(viz.chart, sp);
      } else if (chart === 'lines') {
        drawLine(viz.chart, {
          aria: title, cats: xn, fmt: Mx.fmt, axis: Mx.axis, fitY: v.fitY, height: 320, valueLabel: Mx.label.toLowerCase(),
          series: series.map((s, j) => ({ label: s.label, slot: s.slot, values: vals.map(r => r[j]) })),
          tick: X.tick ? i => X.tick(c.xs[i]) : null, tickLabel: X.key === 'month' ? i => (monthIsJan[c.xs[i]] ? xn[i].slice(4) : xn[i]) : null,
          extraTip: S ? null : i => [{ value: fmtInt(n[i][0]), label: 'admissions' }],
        });
      } else if (chart === 'heatmap') {
        const flat = vals.flat().filter(x => x != null);
        const lo = Math.min(...flat), hi = Math.max(...flat);
        const color = sequential(lo, hi);
        drawHeat(viz.chart, {
          aria: title, rows: xn, cols: series.map(s => s.label), values: vals, fmt: Mx.fmt, color,
          tip: (ri, ci) => ({ title: `${xn[ri]} · ${series[ci].label}`, rows: [{ value: vals[ri][ci] == null ? '–' : Mx.fmt(vals[ri][ci]), label: Mx.label.toLowerCase() }, { value: fmtInt(n[ri][ci]), label: 'admissions' }] }),
          scale: { lo, hi, color, loLabel: Mx.fmt(lo), hiLabel: Mx.fmt(hi) },
        });
      } else {
        drawStack(viz.chart, { aria: title, cats: xn, series, values: vals, tip });
      }
    };
    // Table (long format)
    const cols = [{ label: X.label }];
    if (S) cols.push({ label: S.label });
    cols.push({ label: 'Admissions', num: true }, { label: Mx.label, num: true });
    const rows = [];
    order.forEach(i => series.forEach((s, j) => {
      const r = [xn[i]];
      if (S) r.push(s.label);
      r.push(fmtInt(n[i][j]), vals[i][j] == null ? '–' : Mx.fmt(vals[i][j]));
      rows.push(r);
    }));
    renderTable(vizTable, cols, rows);
    vizTSV = [cols.map(c => c.label), ...rows].map(r => r.join('\t')).join('\n');
  };

  // ---------------------------------------------------------------- data model
  function renderModel() {
    const tables = Object.fromEntries(RAW.meta.tables.map(t => [t.name, t]));
    const fks = RAW.meta.foreignKeys;
    const host = document.getElementById('model-diagram');
    const W = 1000, H = 600;
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Snowflake schema: fact_admission in the centre, linked to eleven dimension tables, two of which link to a further level.' }, host);
    const gLinks = svg('g', {}, root), gBoxes = svg('g', {}, root);
    const boxW = 190, boxH = 44;
    const pos = {};
    const fact = { x: 430, y: 40, w: 220 };
    const factCols = tables.fact_admission.columns;
    const rowH = 25;
    fact.h = 46 + factCols.length * rowH;
    const left2 = [['dim_gender', 70], ['dim_blood_type', 150], ['dim_month', 430]];
    const left1 = [['dim_patient', 110], ['dim_date', 430]];
    const rightDims = ['dim_doctor', 'dim_hospital', 'dim_insurance_provider', 'dim_medical_condition', 'dim_medication', 'dim_admission_type', 'dim_test_result', 'dim_age_group'];
    left2.forEach(([n, y]) => { pos[n] = { x: 10, y, w: 160, h: boxH, lvl2: true }; });
    left1.forEach(([n, y]) => { pos[n] = { x: 200, y, w: 170, h: boxH }; });
    rightDims.forEach((n, i) => { pos[n] = { x: W - boxW - 10, y: 46 + i * 66, w: boxW, h: boxH }; });
    function box(name, p) {
      const g = svg('g', {}, gBoxes);
      svg('rect', { x: p.x, y: p.y, width: p.w, height: p.h, rx: 8, class: 'tbox' + (p.lvl2 ? ' lvl2' : '') }, g);
      label(g, p.x + 12, p.y + 19, name, 'tname');
      label(g, p.x + 12, p.y + 35, `${fmtInt(tables[name].rows)} rows${p.lvl2 ? ' · 2nd level' : ''}`, 'tmeta');
    }
    Object.entries(pos).forEach(([n, p]) => box(n, p));
    // fact box
    const gf = svg('g', {}, gBoxes);
    svg('rect', { x: fact.x, y: fact.y, width: fact.w, height: fact.h, rx: 8, class: 'tbox fact' }, gf);
    label(gf, fact.x + 12, fact.y + 20, 'fact_admission', 'tname');
    label(gf, fact.x + 12, fact.y + 36, `${fmtInt(tables.fact_admission.rows)} rows · one per admission`, 'tmeta');
    const fkCols = new Set(fks.filter(f => f[0] === 'fact_admission').map(f => f[1]));
    const colY = {};
    factCols.forEach((c, i) => {
      const y = fact.y + 46 + i * rowH + 16;
      colY[c] = y - 4;
      label(gf, fact.x + 12, y, c, 'tcol' + (fkCols.has(c) || i === 0 ? ' key' : ''));
      if (i === 0) label(gf, fact.x + fact.w - 12, y, 'PK', 'tmeta', 'end');
      else if (fkCols.has(c)) label(gf, fact.x + fact.w - 12, y, 'FK', 'tmeta', 'end');
    });
    function link(x1, y1, x2, y2) {
      const mx = (x1 + x2) / 2;
      svg('path', { d: `M${x1},${y1}C${mx},${y1} ${mx},${y2} ${x2},${y2}`, class: 'link' }, gLinks);
    }
    for (const [child, col, parent] of fks) {
      if (child === 'fact_admission') {
        const p = pos[parent];
        if (!p) continue;
        const y = colY[col];
        if (p.x > fact.x) link(fact.x + fact.w, y, p.x, p.y + p.h / 2);
        else link(p.x + p.w, p.y + p.h / 2, fact.x, y);
      } else {
        const a = pos[child], b = pos[parent];
        if (a && b) link(b.x + b.w, b.y + b.h / 2, a.x, a.y + a.h / 2);
      }
    }
    // table list
    const list = document.getElementById('model-tables');
    for (const t of RAW.meta.tables) {
      const card = el('div', 'mt');
      card.append(el('h4', '', t.name), el('p', 'tmeta-h', `${fmtInt(t.rows)} rows`));
      const ul = el('ul');
      t.columns.forEach((c, i) => {
        const li = el('li', '', c);
        const fk = fks.find(f => f[0] === t.name && f[1] === c);
        if (i === 0) li.append(el('span', 'k', 'PK'));
        else if (fk) li.append(el('span', 'k', '→ ' + fk[2]));
        ul.append(li);
      });
      card.append(ul);
      list.append(card);
    }
  }

  // ---------------------------------------------------------------- filters + tabs
  const filterHost = document.getElementById('filters');
  const filterSelects = {};
  for (const [k, text] of FILTERS) {
    const d = DIMS[k];
    const opts = [[-1, k === 'year' ? 'All years' : 'All']];
    d.values.forEach((v, i) => {
      let t = v;
      if (k === 'year' && i === 0 && (sm !== 1 || sd !== 1)) t = `${v} (from ${MONTHS[sm - 1]})`;
      if (k === 'year' && i === d.values.length - 1 && lm !== 11) t = `${v} (to ${MONTHS[lm]})`;
      opts.push([i, t]);
    });
    const f = el('div', 'field');
    const l = el('label', '', text);
    const s = select(opts);
    s.id = 'f-' + k;
    l.htmlFor = s.id;
    s.value = String(state.f[k]);
    s.addEventListener('change', () => { state.f[k] = Number(s.value); refresh(); });
    f.append(l, s);
    filterHost.append(f);
    filterSelects[k] = s;
  }
  const adjLabel = el('label', 'check');
  const adjBox = el('input');
  adjBox.type = 'checkbox';
  adjBox.id = 'f-adj';
  adjBox.checked = !state.excludeAdj;
  adjLabel.append(adjBox, document.createTextNode('Include negative bills'));
  adjBox.addEventListener('change', () => { state.excludeAdj = !adjBox.checked; refresh(); });
  filterHost.append(adjLabel);
  const meta = el('div', 'filter-meta');
  const countEl = el('span');
  const resetBtn = el('button', 'ghost-btn', 'Clear filters');
  resetBtn.type = 'button';
  resetBtn.addEventListener('click', () => {
    for (const [k] of FILTERS) { state.f[k] = -1; filterSelects[k].value = '-1'; }
    refresh();
  });
  meta.append(countEl, resetBtn);
  filterHost.append(meta);

  const TABS = ['dashboard', 'visualizer', 'model'];
  function showTab(tab, focus) {
    state.tab = tab;
    for (const t of TABS) {
      const btn = document.getElementById('tab-' + t);
      btn.setAttribute('aria-selected', String(t === tab));
      btn.tabIndex = t === tab ? 0 : -1;
      document.getElementById('view-' + t).hidden = t !== tab;
      if (t === tab && focus) btn.focus();
    }
    filterHost.hidden = tab === 'model';
    try { history.replaceState(null, '', '#' + tab); } catch (e) { /* ignore */ }
    hideTip();
    cards.forEach(c => { if (c.panel === tab && c.dirty) c.redraw(); });
    persist();
  }
  TABS.forEach((t, i) => {
    const btn = document.getElementById('tab-' + t);
    btn.addEventListener('click', () => showTab(t));
    btn.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        showTab(TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length], true);
      }
    });
  });

  function refresh() {
    ROWS = filterRows();
    for (const [k] of FILTERS) filterSelects[k].classList.toggle('active', state.f[k] >= 0);
    countEl.textContent = ROWS.length === N ? `All ${fmtInt(N)} admissions` : `${fmtInt(ROWS.length)} of ${fmtInt(N)} admissions`;
    resetBtn.disabled = ROWS.length === N && FILTERS.every(([k]) => state.f[k] < 0);
    renderKpis(ROWS);
    for (const c of cards) { c.update(); c.dirty = true; c.redraw(); }
    persist();
  }

  function redrawAll() { for (const c of cards) { c.dirty = true; c.redraw(); } }
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redrawAll);
  new MutationObserver(redrawAll).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(redrawAll);

  document.getElementById('meta-line').textContent =
    `${fmtInt(N)} admissions · ${MONTHS[sm - 1]} ${sy} – ${MONTHS[lm]} ${ly} · ${RAW.meta.source}`;

  syncVizControls();
  renderModel();
  refresh();
  showTab(state.tab);
})();

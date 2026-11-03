// Statistical tests used by the dashboard: chi-square test of independence,
// one-way ANOVA, and Pearson correlation, each with a p-value.
// Numerical routines follow Numerical Recipes (gamma via Lanczos, incomplete
// gamma by series / continued fraction, incomplete beta by continued fraction).

(function (root) {
  'use strict';

  const LANCZOS = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ];

  function lnGamma(z) {
    if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - lnGamma(1 - z);
    z -= 1;
    let x = LANCZOS[0];
    for (let i = 1; i < 9; i++) x += LANCZOS[i] / (z + i);
    const t = z + 7.5;
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }

  const TINY = 1e-300;

  // Regularized upper incomplete gamma Q(a, x).
  function gammaQ(a, x) {
    if (x <= 0) return 1;
    const front = Math.exp(-x + a * Math.log(x) - lnGamma(a));
    if (x < a + 1) {
      let ap = a, sum = 1 / a, del = sum;
      for (let n = 0; n < 1000; n++) {
        ap += 1;
        del *= x / ap;
        sum += del;
        if (Math.abs(del) < Math.abs(sum) * 1e-15) break;
      }
      return 1 - sum * front;
    }
    let b = x + 1 - a, c = 1 / TINY, d = 1 / b, h = d;
    for (let i = 1; i < 1000; i++) {
      const an = -i * (i - a);
      b += 2;
      d = an * d + b; if (Math.abs(d) < TINY) d = TINY;
      c = b + an / c; if (Math.abs(c) < TINY) c = TINY;
      d = 1 / d;
      const del = d * c;
      h *= del;
      if (Math.abs(del - 1) < 1e-15) break;
    }
    return front * h;
  }

  function betaCF(a, b, x) {
    const qab = a + b, qap = a + 1, qam = a - 1;
    let c = 1, d = 1 - qab * x / qap;
    if (Math.abs(d) < TINY) d = TINY;
    d = 1 / d;
    let h = d;
    for (let m = 1; m <= 1000; m++) {
      const m2 = 2 * m;
      let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; if (Math.abs(d) < TINY) d = TINY;
      c = 1 + aa / c; if (Math.abs(c) < TINY) c = TINY;
      d = 1 / d;
      h *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; if (Math.abs(d) < TINY) d = TINY;
      c = 1 + aa / c; if (Math.abs(c) < TINY) c = TINY;
      d = 1 / d;
      const del = d * c;
      h *= del;
      if (Math.abs(del - 1) < 1e-15) break;
    }
    return h;
  }

  // Regularized incomplete beta I_x(a, b).
  function betaI(a, b, x) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    const bt = Math.exp(lnGamma(a + b) - lnGamma(a) - lnGamma(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betaCF(a, b, x) / a : 1 - bt * betaCF(b, a, 1 - x) / b;
  }

  // counts: rows x cols matrix of observed frequencies.
  function chiSquare(counts) {
    const rows = counts.filter(r => r.some(v => v > 0));
    const nc = rows.length ? rows[0].length : 0;
    const colTot = Array.from({ length: nc }, (_, j) => rows.reduce((s, r) => s + r[j], 0));
    const keep = colTot.map(t => t > 0);
    const rowTot = rows.map(r => r.reduce((s, v, j) => s + (keep[j] ? v : 0), 0));
    const total = rowTot.reduce((s, v) => s + v, 0);
    const r = rows.length, c = keep.filter(Boolean).length;
    if (r < 2 || c < 2 || total === 0) return null;
    let chi2 = 0;
    rows.forEach((row, i) => row.forEach((o, j) => {
      if (!keep[j]) return;
      const e = rowTot[i] * colTot[j] / total;
      chi2 += (o - e) * (o - e) / e;
    }));
    const df = (r - 1) * (c - 1);
    return { chi2, df, p: gammaQ(df / 2, chi2 / 2), cramersV: Math.sqrt(chi2 / (total * (Math.min(r, c) - 1))), n: total };
  }

  // groups: array of numeric arrays.
  function anova(groups) {
    const gs = groups.filter(g => g.length > 0);
    const n = gs.reduce((s, g) => s + g.length, 0);
    const k = gs.length;
    if (k < 2 || n <= k) return null;
    let grand = 0;
    for (const g of gs) for (const v of g) grand += v;
    grand /= n;
    let ssb = 0, ssw = 0;
    for (const g of gs) {
      let m = 0;
      for (const v of g) m += v;
      m /= g.length;
      ssb += g.length * (m - grand) * (m - grand);
      for (const v of g) ssw += (v - m) * (v - m);
    }
    const df1 = k - 1, df2 = n - k;
    const f = (ssb / df1) / (ssw / df2);
    return { f, df1, df2, p: betaI(df2 / 2, df1 / 2, df2 / (df2 + df1 * f)), eta2: ssb / (ssb + ssw), n };
  }

  function pearson(xs, ys) {
    const n = xs.length;
    if (n < 3) return null;
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { mx += xs[i]; my += ys[i]; }
    mx /= n; my /= n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) {
      const dx = xs[i] - mx, dy = ys[i] - my;
      sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
    }
    if (sxx === 0 || syy === 0) return null;
    const r = sxy / Math.sqrt(sxx * syy);
    const df = n - 2;
    const t2 = r * r * df / Math.max(1e-300, 1 - r * r);
    return { r, n, p: betaI(df / 2, 0.5, df / (df + t2)) };
  }

  const api = { chiSquare, anova, pearson, gammaQ, betaI };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HCStats = api;
})(this);

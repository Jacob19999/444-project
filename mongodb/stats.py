"""Significance tests that finish what the MongoDB pipelines start.

The pipelines do the heavy lifting (joins, grouping, counts, sums); these
helpers turn those small result tables into test statistics:

  chi-square   gender/age/blood type x condition counts  -> is the mix different?
  ANOVA        n, sum, sum of squares per group           -> do group averages differ?
  Pearson r    n, sums, sums of products                  -> do two numbers move together?
"""

import math

import pandas as pd
from scipy import stats as sp

ALPHA = 0.05
TESTS = []  # every test run in this session, saved to results/tests.csv


def chi_square(df, row, col, count):
    table = df.pivot_table(index=row, columns=col, values=count, aggfunc="sum", fill_value=0)
    chi2, p, dof, expected = sp.chi2_contingency(table.values)
    n = table.values.sum()
    cramers_v = math.sqrt(chi2 / (n * (min(table.shape) - 1)))
    residuals = (table - expected) / expected**0.5
    return {"chi2": chi2, "dof": dof, "p": p, "cramers_v": cramers_v, "table": table, "residuals": residuals}


def print_chi_square(title, df, row, col, count):
    r = chi_square(df, row, col, count)
    verdict = "significant" if r["p"] < ALPHA else "not significant"
    print(f"\n[test] {title}: chi2 = {r['chi2']:.2f}, dof = {r['dof']}, p = {r['p']:.4f}, "
          f"Cramer's V = {r['cramers_v']:.4f} -> {verdict} at alpha {ALPHA}")
    TESTS.append({"test": title, "method": "chi-square", "statistic": round(r["chi2"], 3),
                  "df": str(r["dof"]), "p": round(r["p"], 4), "effect": f"Cramer's V = {r['cramers_v']:.4f}",
                  "significant": r["p"] < ALPHA})
    return r


def anova(df, group_col):
    """One-way ANOVA from per-group n, sum_x, sum_x2 (as produced in MongoDB)."""
    n, s, s2 = df["n"].astype(float), df["sum_x"].astype(float), df["sum_x2"].astype(float)
    N, k = n.sum(), len(df)
    grand = s.sum() / N
    ss_between = ((s / n - grand) ** 2 * n).sum()
    ss_total = s2.sum() - s.sum() ** 2 / N
    ss_within = ss_total - ss_between
    f = (ss_between / (k - 1)) / (ss_within / (N - k))
    p = sp.f.sf(f, k - 1, N - k)
    return {"F": f, "df1": k - 1, "df2": int(N - k), "p": p, "eta_squared": ss_between / ss_total}


def print_anova(title, df, group_col):
    r = anova(df, group_col)
    verdict = "significant" if r["p"] < ALPHA else "not significant"
    print(f"\n[test] {title}: F({r['df1']}, {r['df2']}) = {r['F']:.3f}, p = {r['p']:.4f}, "
          f"eta^2 = {r['eta_squared']:.6f} -> {verdict} at alpha {ALPHA}")
    TESTS.append({"test": title, "method": "one-way ANOVA", "statistic": round(r["F"], 3),
                  "df": f"{r['df1']}, {r['df2']}", "p": round(r["p"], 4), "effect": f"eta^2 = {r['eta_squared']:.6f}",
                  "significant": r["p"] < ALPHA})
    return r


def pearson(s):
    """Pearson r from n, sum_x, sum_y, sum_xy, sum_x2, sum_y2."""
    n = s["n"]
    num = n * s["sum_xy"] - s["sum_x"] * s["sum_y"]
    den = math.sqrt((n * s["sum_x2"] - s["sum_x"] ** 2) * (n * s["sum_y2"] - s["sum_y"] ** 2))
    r = num / den
    t = r * math.sqrt((n - 2) / (1 - r**2))
    p = 2 * sp.t.sf(abs(t), n - 2)
    return {"n": n, "r": round(r, 4), "r_squared": round(r**2, 4), "p": round(p, 4),
            "significant": bool(p < ALPHA)}


def save_tests(path):
    """Merge this run's tests into results/tests.csv (one row per test name)."""
    new = pd.DataFrame(TESTS)
    if new.empty:
        return
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat([old[~old["test"].isin(new["test"])], new])
    new.sort_values("test", key=lambda t: t.str.extract(r"Q(\d+)")[0].astype(int), kind="stable").to_csv(path, index=False)

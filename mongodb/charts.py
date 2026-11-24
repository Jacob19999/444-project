"""Stage 5 (Visualization): build the report charts from mongodb/results/*.csv.

Run after query.py:  python3 mongodb/charts.py   -> mongodb/charts/*.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
OUT = HERE / "charts"
OUT.mkdir(exist_ok=True)

# Validated categorical order (blue, orange, aqua, yellow, magenta) + chart ink.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#ffffff"
GOOD, BAD = "#2a78d6", "#e34948"  # diverging poles (below / above reference)
DIVERGING = LinearSegmentedColormap.from_list("div", ["#184f95", "#6da7ec", "#f0efec", "#ec8a89", "#b52b2a"])
SEQUENTIAL = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#6da7ec", "#2a78d6", "#104281"])

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "axes.titlesize": 12.5,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.titlepad": 22,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.7,
    "axes.axisbelow": True,
    "legend.frameon": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.dpi": 200,
})


def r(name):
    return pd.read_csv(RES / f"{name}.csv")


TESTS = r("tests").set_index("test")


def test_note(name):
    t = TESTS.loc[name]
    verdict = "significant" if t["significant"] else "not significant"
    return f"{t['method']}: stat = {t['statistic']}, p = {t['p']:.3f} ({verdict}); {t['effect']}"


def finish(fig, ax, title, subtitle, name):
    ax.set_title(title)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=8.8, color=INK2, va="bottom")
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def bar_labels(ax, bars, fmt, horizontal=False, pad=3):
    for b in bars:
        v = b.get_width() if horizontal else b.get_height()
        if horizontal:
            ax.annotate(fmt(v), (v, b.get_y() + b.get_height() / 2), xytext=(pad, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=INK2)
        else:
            ax.annotate(fmt(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, pad),
                        textcoords="offset points", ha="center", fontsize=8.5, color=INK2)


def heatmap(df, rows, cols, value, center, fmt, title, subtitle, name, cbar_label, span, row_order=None, col_order=None):
    # span is fixed per measure (not the data range) so tiny differences stay pale
    t = df.pivot_table(index=rows, columns=cols, values=value)
    if row_order:
        t = t.loc[row_order]
    if col_order:
        t = t[col_order]
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(t) + 1.9))
    im = ax.imshow(t.values, cmap=DIVERGING, vmin=center - span, vmax=center + span, aspect="auto")
    ax.set_xticks(range(len(t.columns)), t.columns)
    ax.set_yticks(range(len(t.index)), t.index)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    for i in range(t.shape[0]):
        for j in range(t.shape[1]):
            v = t.values[i, j]
            strong = abs(v - center) > 0.6 * span
            ax.text(j, i, fmt(v), ha="center", va="center", fontsize=8.5, color="#ffffff" if strong else INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label(cbar_label, color=INK2, fontsize=8.5)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, colors=INK2)
    finish(fig, ax, title, subtitle, name)


CONDITIONS = ["Arthritis", "Asthma", "Cancer", "Diabetes", "Hypertension", "Obesity"]
AGE_GROUPS = ["13-17", "18-34", "35-49", "50-64", "65+"]

# ---------------------------------------------------------------- Q1
d = r("q1a_gender_condition").pivot(index="condition", columns="gender", values="share_pct").loc[CONDITIONS[::-1]]
fig, ax = plt.subplots(figsize=(8, 4.2))
y = np.arange(len(d))
for k, g in enumerate(["Female", "Male"]):
    bars = ax.barh(y + (0.2 if k == 0 else -0.2), d[g], height=0.38, color=SERIES[k], label=g)
    bar_labels(ax, bars, lambda v: f"{v:.2f}%", horizontal=True)
ax.axvline(100 / 6, color=INK2, lw=1, ls="--")
ax.text(100 / 6 - 0.15, len(d) - 0.45, "even split 16.67%", color=INK2, fontsize=8, ha="right")
ax.set_yticks(y, d.index)
ax.set_xlim(0, 20)
ax.set_xlabel("Share of that gender's admissions (%)")
ax.grid(axis="y", visible=False)
ax.legend(loc="lower right", ncols=2, bbox_to_anchor=(1, -0.28))
finish(fig, ax, "Q1. Condition mix is the same for female and male patients",
       test_note("Q1 gender x condition"), "c01_q1_gender_condition")

# ---------------------------------------------------------------- Q2
d = r("q2b_discount_adjusted").merge(r("q2a_discount_raw")[["insurer", "discount_pct"]], on="insurer")
d = d.sort_values("mean_discount_pct")
fig, ax = plt.subplots(figsize=(8, 3.8))
colors = [GOOD if v > 0 else BAD for v in d["mean_discount_pct"]]
bars = ax.barh(d["insurer"], d["mean_discount_pct"], color=colors, height=0.55)
for b, v in zip(bars, d["mean_discount_pct"]):
    ax.annotate(f"{v:+.2f}%", (v, b.get_y() + b.get_height() / 2), xytext=(4 if v > 0 else -4, 0),
                textcoords="offset points", ha="left" if v > 0 else "right", va="center", fontsize=8.5, color=INK2)
ax.axvline(0, color=INK2, lw=1)
ax.set_xlim(-0.75, 0.85)
ax.set_xlabel("Condition-adjusted discount vs market average bill (%)   premium <  |  > discount")
ax.grid(axis="y", visible=False)
finish(fig, ax, "Q2. Mean insurer discount is +0.004%: no insurer is more than 0.53% from the market",
       "Market average bill = $25,594.63. Bars = average of each insurer's discount across the six conditions.",
       "c02_q2_discount")

# ---------------------------------------------------------------- Q3
d = r("q3a_condition_los").sort_values("avg_los", ascending=False)
overall = d["sum_x"].sum() / d["n"].sum()
fig, ax = plt.subplots(figsize=(8, 4))
bars = ax.bar(d["condition"], d["avg_los"], color=SERIES[0], width=0.6)
bar_labels(ax, bars, lambda v: f"{v:.2f}")
ax.axhline(overall, color=INK2, lw=1, ls="--")
ax.set_ylim(0, 18)
ax.set_ylabel("Average length of stay (days)")
ax.grid(axis="x", visible=False)
finish(fig, ax, "Q3. Every condition averages about 15.5 days in hospital",
       test_note("Q3 length of stay ~ condition") + f"  |  dashed line = overall {overall:.2f} days", "c03_q3_condition_los")

d = r("q3b_condition_test_los").melt(id_vars="condition", value_vars=["abnormal_los", "inconclusive_los", "normal_los"],
                                     var_name="test", value_name="los")
d["test"] = d["test"].str.replace("_los", "").str.title()
heatmap(d, "condition", "test", "los", overall, lambda v: f"{v:.2f}",
        "Q3. Test result does not lengthen the stay within any condition",
        f"Average length of stay (days); colour = distance from the overall {overall:.2f}-day average",
        "c04_q3_condition_test_heatmap", "days", 1.0, row_order=CONDITIONS)

# ---------------------------------------------------------------- Q4
d = r("q4a_insurer_billing").sort_values("avg_bill")
fig, ax = plt.subplots(figsize=(8, 3.8))
bars = ax.barh(d["insurer"], d["avg_bill"], color=SERIES[0], height=0.55)
bar_labels(ax, bars, lambda v: f"${v:,.0f}", horizontal=True)
ax.set_xlim(0, 30000)
ax.xaxis.set_major_formatter(lambda v, _: f"${v/1000:.0f}K")
ax.set_xlabel("Average bill per admission (negative adjustments excluded)")
ax.grid(axis="y", visible=False)
finish(fig, ax, "Q4. Average bill differs by only $219 (0.9%) across insurers",
       test_note("Q4 billing amount ~ insurer"), "c05_q4_insurer_bill")

d = r("q4b_insurer_year")
fig, ax = plt.subplots(figsize=(8, 4.2))
for k, (ins, g) in enumerate(d.groupby("insurer")):
    ax.plot(g["year"], g["avg_bill"], color=SERIES[k], lw=2, marker="o", ms=5, label=ins)
ax.set_xticks([2020, 2021, 2022, 2023])
ax.set_ylim(24000, 27000)
ax.yaxis.set_major_formatter(lambda v, _: f"${v/1000:.1f}K")
ax.set_ylabel("Average bill (axis starts at $24K)")
ax.grid(axis="x", visible=False)
ax.legend(ncols=5, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8.5)
finish(fig, ax, "Q4. No insurer is cheapest every year: the ranking reshuffles",
       "Average bill by admission year, full years 2020-2023", "c06_q4_insurer_year")

# ---------------------------------------------------------------- Q5
d = r("q5b_los_band_rate")
fig, ax = plt.subplots(figsize=(8, 4))
bands = sorted(d["los_band"].unique())
x = np.arange(len(bands))
for k, g in enumerate(["Female", "Male"]):
    s = d[d.gender == g].set_index("los_band").loc[bands]
    bars = ax.bar(x + (k - 0.5) * 0.36, s["avg_daily_rate"], width=0.34, color=SERIES[k], label=g)
    bar_labels(ax, bars, lambda v: f"${v:,.0f}")
ax.set_xticks(x, [b.lstrip("0").replace("-0", "-") for b in bands])
ax.yaxis.set_major_formatter(lambda v, _: f"${v/1000:.0f}K")
ax.set_ylabel("Average billing per day")
ax.set_xlabel("Length of stay")
ax.grid(axis="x", visible=False)
ax.legend(ncols=2)
c = r("q5c_correlations").set_index("pair")
finish(fig, ax, "Q5. Daily billing rate falls ~9x from short to long stays, for both genders",
       f"Total bill does not grow with stay (r = {c.loc['length of stay vs billing amount','r']:.3f}), "
       f"so the daily rate drops (r = {c.loc['length of stay vs billing per day','r']:.2f})",
       "c07_q5_rate_by_los")

d = r("q5a_age_gender_rate")
fig, ax = plt.subplots(figsize=(8, 4))
x = np.arange(len(AGE_GROUPS))
for k, g in enumerate(["Female", "Male"]):
    s = d[d.gender == g].set_index("age_group").loc[AGE_GROUPS]
    bars = ax.bar(x + (k - 0.5) * 0.36, s["bill_per_patient_day"], width=0.34, color=SERIES[k], label=g)
    bar_labels(ax, bars, lambda v: f"${v:,.0f}")
ax.set_xticks(x, [f"{a}\n(n={int(d[d.age_group == a].admissions.sum()):,})" for a in AGE_GROUPS])
ax.set_ylim(0, 2200)
ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
ax.set_ylabel("Billing per patient-day")
ax.grid(axis="x", visible=False)
ax.legend(ncols=2, loc="upper right")
finish(fig, ax, "Q5. Billing rate is flat across adult age groups and genders",
       "Total billed ÷ total patient-days. The 13-17 group has only 116 admissions, so its bars are noisy.",
       "c08_q5_rate_age_gender")

# ---------------------------------------------------------------- Q6
d = r("q6a2_los_histogram")
mean_los = r("q6b_los_overall")["avg_los"].iloc[0]
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.bar(d["los_days"], d["admissions"], color=SERIES[0], width=0.8)
ax.axhline(d["admissions"].mean(), color=INK2, lw=1, ls="--")
ax.text(30.6, d["admissions"].mean() + 40, f"{d['admissions'].mean():,.0f}/day", color=INK2, fontsize=8, ha="right")
ax.set_xlabel("Length of stay (days)")
ax.set_ylabel("Admissions")
ax.set_xlim(0.3, 30.7)
ax.grid(axis="x", visible=False)
finish(fig, ax, f"Q6. Stays are spread evenly from 1 to 30 days (mean {mean_los:.1f} days)",
       "Every stay length occurs 1,737-1,943 times: a flat (uniform) distribution, no typical stay",
       "c09_q6_los_histogram")

d = r("q6d_condition_type_los")
heatmap(d, "condition", "admission_type", "avg_los", mean_los, lambda v: f"{v:.2f}",
        "Q6. Condition x admission type: all 18 cells within ±0.5 day of average",
        test_note("Q6 length of stay ~ admission type") + "  |  colour = distance from 15.50 days",
        "c10_q6_condition_type_heatmap", "average stay (days)", 1.0, row_order=CONDITIONS,
        col_order=["Elective", "Urgent", "Emergency"])

# ---------------------------------------------------------------- Q7
d = r("q7a_age_condition")
heatmap(d, "age_group", "condition", "share_pct", 100 / 6, lambda v: f"{v:.1f}%",
        "Q7. Each condition is ~1/6 of every adult age group",
        test_note("Q7 age group x condition") + "  |  colour = distance from 16.7%",
        "c11_q7_age_condition_heatmap", "share of age group (%)", 4.0, row_order=AGE_GROUPS, col_order=CONDITIONS)

# ---------------------------------------------------------------- Q8
d = r("q8b_age_los")
big = d[d.admissions >= 100]
small = d[d.admissions < 100]
grp = r("q8a_age_group_los")
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(big["age"], big["avg_los"], color=SERIES[0], lw=1.6, marker="o", ms=3.2, label="ages with 700+ admissions")
ax.scatter(small["age"], small["avg_los"], s=16, facecolor="none", edgecolor=MUTED, label="ages with < 100 admissions")
for _, g in grp.iterrows():
    hi = min(g["max_age"], 89)
    ax.hlines(g["avg_los"], g["min_age"], hi, color=SERIES[1], lw=2.4)
ax.plot([], [], color=SERIES[1], lw=2.4, label="age-group average")
ax.set_ylim(10, 20)
ax.set_xlabel("Age at admission")
ax.set_ylabel("Average length of stay (days)")
ax.legend(ncols=3, loc="upper center", fontsize=8.5)
cr = r("q8c_correlation").iloc[0]
finish(fig, ax, "Q8. Length of stay does not change with age",
       f"Pearson r = {cr['r']:.4f} (p = {cr['p']:.3f}); " + test_note("Q8 length of stay ~ age group").split(";")[0].replace("one-way ANOVA", "ANOVA by group"),
       "c12_q8_age_los")

# ---------------------------------------------------------------- Q9
d = r("q9a_blood_los").sort_values("avg_los", ascending=False)
fig, ax = plt.subplots(figsize=(8, 3.8))
bars = ax.bar(d["blood_type"], d["avg_los"], color=SERIES[0], width=0.6)
bar_labels(ax, bars, lambda v: f"{v:.2f}")
ax.axhline(mean_los, color=INK2, lw=1, ls="--")
ax.set_ylim(0, 18)
ax.set_ylabel("Average length of stay (days)")
ax.grid(axis="x", visible=False)
finish(fig, ax, "Q9. B+ stays longest and O+ shortest, but the gap is under half a day",
       test_note("Q9 length of stay ~ blood type") + f"  |  dashed line = overall {mean_los:.2f} days", "c13_q9_blood_los")

d = r("q9b_blood_condition")
heatmap(d, "blood_type", "condition", "rate_pct", 100 / 6, lambda v: f"{v:.1f}%",
        "Q9. No blood type has a meaningfully higher rate of any condition",
        test_note("Q9 blood type x condition") + "  |  colour = distance from 16.7%",
        "c14_q9_blood_condition_heatmap", "share of blood type (%)", 4.0,
        row_order=["A+", "A-", "AB+", "AB-", "B+", "B-", "O+", "O-"], col_order=CONDITIONS)

# ---------------------------------------------------------------- Q10
d = r("q10a_condition_admission_type").pivot(index="condition", columns="admission_type", values="share_pct").loc[CONDITIONS[::-1]]
fig, ax = plt.subplots(figsize=(8, 4))
left = np.zeros(len(d))
for k, t in enumerate(["Elective", "Urgent", "Emergency"]):
    bars = ax.barh(d.index, d[t], left=left, color=SERIES[k], height=0.6, label=t, edgecolor=SURFACE, linewidth=1.5)
    for b, v, l in zip(bars, d[t], left):
        ax.text(l + v / 2, b.get_y() + b.get_height() / 2, f"{v:.1f}%", ha="center", va="center", fontsize=8.5,
                color="#ffffff" if k < 2 else INK)
    left += d[t].values
ax.set_xlim(0, 100)
ax.set_xlabel("Share of the condition's admissions (%)")
ax.grid(False)
ax.legend(ncols=3, loc="upper center", bbox_to_anchor=(0.5, -0.14))
finish(fig, ax, "Q10. Admission type mix is close to one-third each for every condition",
       test_note("Q10 condition x admission type") + "; largest cell: Diabetes-Urgent (residual +2.04)",
       "c15_q10_condition_type_mix")

d = r("q10c2_bill_histogram")
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.bar(d["bucket_start"] + 1250, d["admissions"], width=2300, color=SERIES[0])
for fence, lbl in [(-2757.10, "mean - 2 SD"), (53946.37, "mean + 2 SD")]:
    ax.axvline(fence, color=BAD, lw=1.2, ls="--")
    ax.text(fence + (600 if fence < 0 else -600), 3150, lbl, color=INK2, fontsize=8, ha="left" if fence < 0 else "right")
ax.set_xlim(-5000, 57500)
ax.set_ylim(0, 3300)
ax.xaxis.set_major_formatter(lambda v, _: f"${v/1000:.0f}K")
ax.set_xlabel("Billing amount ($2,500 buckets; 106 negative adjustments not shown)")
ax.set_ylabel("Admissions")
ax.grid(axis="x", visible=False)
finish(fig, ax, r"Q10. Bills are spread evenly from \$0 to \$52K: no bill lies beyond 2 SD",
       "The only out-of-pattern records are the 106 negative bills (refunds/adjustments)",
       "c16_q10_bill_histogram")

"""Build the D3 analytical report (Word) from the MongoDB results, charts and
execution screenshots.

Run after mongodb/query.py, mongodb/charts.py and mongodb/screenshots.py:
    python3 report/build_report.py   -> report/D3_Analytical_Report.docx
"""

import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401  (kept for easy landscape tweaks)
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MDB = ROOT / "mongodb"
RES, CHARTS, SHOTS = MDB / "results", MDB / "charts", MDB / "screenshots"
HERE = Path(__file__).resolve().parent
OUT = HERE / "D3_Analytical_Report.docx"
QUERY_SRC = (MDB / "query.py").read_text()

ACCENT = RGBColor(0x1C, 0x5C, 0xAB)
INK2 = RGBColor(0x52, 0x51, 0x4E)


def r(name):
    return pd.read_csv(RES / f"{name}.csv")


TESTS = r("tests").set_index("test")

# ---------------------------------------------------------------------------
# Pipeline diagram
# ---------------------------------------------------------------------------


def pipeline_diagram(path):
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    steps = [
        ("Raw CSV", "Data/healthcare_dataset.csv\n55,500 rows x 15 columns", "Source"),
        ("Clean", "pipeline/clean.py\n534 duplicates removed,\nnames, hospitals, dates,\nLOS, billing per day", "Stage 2"),
        ("Model", "pipeline/build_schema.py\nsnowflake schema:\n1 fact + 13 dimensions", "Stage 2"),
        ("Load", "mongodb/import_data.py\nMongoDB database\nhealthcare_snowflake", "Stage 1"),
        ("Query", "mongodb/query.py\n$match $lookup $unwind\n$group $setWindowFields\n+ stats.py tests", "Stages 3-4"),
        ("Validate", "query.py CHECK\n19/19 match pandas\n+ sensitivity test", "Stage 4"),
        ("Visualize", "charts.py (16 charts)\nscreenshots.py\nthis report", "Stage 5"),
    ]
    fig, ax = plt.subplots(figsize=(13, 3.2))
    ax.set_xlim(0, len(steps) * 1.9)
    ax.set_ylim(0, 3.2)
    ax.axis("off")
    colors = {"Source": "#e1e0d9", "Stage 1": "#cde2fb", "Stage 2": "#b7d3f6", "Stages 3-4": "#86b6ef",
              "Stage 4": "#9ec5f4", "Stage 5": "#cde2fb"}
    for i, (title, body, stage) in enumerate(steps):
        x = i * 1.9 + 0.1
        ax.add_patch(FancyBboxPatch((x, 0.35), 1.6, 2.3, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=colors[stage], ec="#52514e", lw=0.8))
        ax.text(x + 0.8, 2.85, stage, ha="center", fontsize=9, color="#52514e")
        ax.text(x + 0.8, 2.3, title, ha="center", fontsize=12, weight="bold", color="#0b0b0b")
        ax.text(x + 0.8, 1.95, body, ha="center", va="top", fontsize=8.2, color="#0b0b0b", linespacing=1.35)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + 1.62, 1.5), (x + 1.98, 1.5), arrowstyle="-|>", mutation_scale=14,
                                         color="#52514e", lw=1.2))
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# docx helpers
# ---------------------------------------------------------------------------
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Inches(1))

st = doc.styles
st["Normal"].font.name = "Calibri"
st["Normal"].font.size = Pt(11)
st["Normal"].paragraph_format.space_after = Pt(6)
st["Normal"].paragraph_format.line_spacing = 1.1
for name, size, color in [("Title", 26, ACCENT), ("Heading 1", 17, ACCENT), ("Heading 2", 13.5, ACCENT),
                          ("Heading 3", 11.5, RGBColor(0x0B, 0x0B, 0x0B))]:
    s = st[name]
    s.font.name = "Calibri"
    s.font.size = Pt(size)
    s.font.bold = True
    s.font.color.rgb = color
    s.paragraph_format.keep_with_next = True
    s.paragraph_format.space_before = Pt({"Title": 0, "Heading 1": 18, "Heading 2": 14, "Heading 3": 10}[name])
    s.paragraph_format.space_after = Pt(6 if name != "Heading 3" else 3)
for name in ("Title", "Heading 1", "Heading 2", "Heading 3"):
    rpr = st[name].element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if fonts.get(qn(attr)) is not None:
            del fonts.attrib[qn(attr)]
    fonts.set(qn("w:ascii"), "Calibri")
    fonts.set(qn("w:hAnsi"), "Calibri")


def add_runs(p, text):
    """**bold** and `code` markup inside a paragraph."""
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            p.add_run(part[2:-2]).bold = True
        elif part.startswith("`"):
            run = p.add_run(part[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
        else:
            p.add_run(part)
    return p


def P(text, style=None, italic=False, size=None, color=None, align=None, after=None):
    p = doc.add_paragraph(style=style)
    add_runs(p, text)
    for run in p.runs:
        if italic:
            run.italic = True
        if size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = color
    if align:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def H(text, level):
    return doc.add_heading(text, level=level)


def bullets(items, style="List Bullet"):
    for it in items:
        p = doc.add_paragraph(style=style)
        add_runs(p, it)
        p.paragraph_format.space_after = Pt(3)


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(rows, header, widths=None, size=9):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(str(h))
        run.bold = True
        run.font.size = Pt(size)
        shade(c, "DCE8F7")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            add_runs(cells[i].paragraphs[0], str(v))
            for run in cells[i].paragraphs[0].runs:
                run.font.size = Pt(size)
    for row in t.rows:
        for c in row.cells:
            c.paragraphs[0].paragraph_format.space_after = Pt(1)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def df_table(df, cols=None, rename=None, fmt=None, widths=None, size=8.5):
    df = df[cols] if cols else df
    fmt = fmt or {}
    rows = [[fmt[c](v) if c in fmt else v for c, v in zip(df.columns, rec)] for rec in df.itertuples(index=False)]
    header = [rename.get(c, c) if rename else c for c in df.columns]
    return table(rows, header, widths, size)


def code(text, size=7.5):
    text = textwrap.dedent(text).strip("\n")
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F3F3F1")
    pPr.append(shd)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        run = p.add_run(line)
        run.font.name = "Consolas"
        run._element.rPr.rFonts.set(qn("w:hAnsi"), "Consolas")
        run.font.size = Pt(size)
        if i < len(lines) - 1:
            run.add_break()
    return p


fig_no = [0]


def image(path, caption, max_width=6.5, dpi=None):
    w_px, h_px = Image.open(path).size
    dpi = dpi or 200
    width = min(max_width, w_px / dpi)
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    fig_no[0] += 1
    P(f"Figure {fig_no[0]}. {caption}", italic=True, size=9, color=INK2, align=WD_ALIGN_PARAGRAPH.CENTER, after=10)


def shot(name, caption):
    image(SHOTS / f"{name}.png", "Execution screenshot - " + caption, max_width=6.5, dpi=150)


def chart(name, caption):
    image(CHARTS / f"{name}.png", caption, max_width=6.3, dpi=200)


def pipeline_src(label):
    """Pull the exact show(...) call for a labelled pipeline out of query.py."""
    lines = QUERY_SRC.split("\n")
    idx = next(i for i, l in enumerate(lines) if f'"{label} ' in l)
    start = next(i for i in range(idx, -1, -1) if "show(" in lines[i])
    depth, end = 0, start
    for end in range(start, len(lines)):
        depth += lines[end].count("(") - lines[end].count(")")
        if depth == 0:
            break
    return "\n".join(lines[start:end + 1])


def func_src(name):
    m = re.search(rf"^def {name}\(.*?(?=^\S)", QUERY_SRC, re.S | re.M)
    return m.group(0)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def test_text(name):
    t = TESTS.loc[name]
    stat = "chi-square" if t["method"] == "chi-square" else "F"
    return (f"{t['method']}: {stat} = {t['statistic']}, df = {t['df']}, p = {t['p']:.4f}, {t['effect']} "
            f"({'significant' if t['significant'] else 'not significant'} at α = 0.05)")


def section(letter, title):
    H(f"{letter}. {title}", 3)


# ===========================================================================
# Title page
# ===========================================================================
pipeline_diagram(HERE / "pipeline_diagram.png")

for _ in range(6):
    doc.add_paragraph()
P("CIS 444/544 · Deliverable 3", size=12, color=INK2)
doc.add_paragraph("Healthcare Admissions Analytical Pipeline", style="Title")
P("MongoDB analysis of the Kaggle Healthcare Dataset (55,500 hospital admissions, 2019-2024)", size=13, color=INK2, after=30)
P("**Team members**", after=2)
for m in ["Chloe Jensrud", "Elizabeth Johnson", "Caitlin Sheeran", "Zijian (Jacob) Tang", "Nofogon Grace Marienne Dosso"]:
    P(m, after=0)
doc.add_paragraph()
P("**Tools:** MongoDB 8.0 (PyMongo), Python 3.12 (pandas, SciPy, matplotlib)", after=2)
P("**Analytical work files:** `mongodb/` and `pipeline/` (see Appendix A)", after=2)
P("**Date:** November 2026")
page_break()

H("Contents", 1)
for line in [
    "1. Data Analytics Pipeline (Stages 1-5)",
    "2. Answering the Business Questions (Q1 - Q10)",
    "3. Final Analytical Summary",
    "Appendix A. File inventory and how to re-run    Appendix B. Statistical tests",
]:
    P(line, after=2)
P("")
P("Each question follows the D3 template (A question, B approach, C query, D results, E insights, F recommendations); "
  "cost figures exclude the 106 negative bills and tests use α = 0.05.", size=10)
page_break()

# ===========================================================================
# 1. Pipeline
# ===========================================================================
H("1. Data Analytics Pipeline", 1)
H("1.1 Pipeline overview", 2)
P("The raw CSV is cleaned, split into the D2 snowflake schema, loaded into MongoDB, and analysed with aggregation pipelines.")
image(HERE / "pipeline_diagram.png", "Data analytics pipeline from raw CSV to report.", max_width=6.5)
table([
    ["Raw CSV", "`Data/healthcare_dataset.csv`", "55,500 admissions, 15 attributes"],
    ["Stage 2 Clean", "`pipeline/clean.py`", "Removes duplicates, fixes text and dates, adds derived fields"],
    ["Stage 2 Model", "`pipeline/build_schema.py`", "Writes the 14 snowflake tables"],
    ["Stage 1 Load", "`mongodb/import_data.py`", "Loads the tables into MongoDB"],
    ["Stages 3-4 Query", "`mongodb/query.py`, `stats.py`", "40+ aggregation pipelines and significance tests"],
    ["Stage 4 Validate", "`query.py CHECK`", "Re-checks results with pandas"],
    ["Stage 5 Visualize", "`charts.py`, `screenshots.py`", "Charts and screenshots for this report"],
], ["Step", "Script", "What it does"], widths=[1.3, 2.2, 3.0])

# ---------------------------------------------------------------- Stage 1
H("1.2 Stage 1: Data extraction", 2)
P("`import_data.py` loads each snowflake CSV into its own MongoDB collection, the same way as the class labs.")
code((MDB / "import_data.py").read_text().split('"""', 2)[2].strip())
shot("s1_1", "the 14 collections and their document counts.")
P("Every question starts from `fact_admission` and joins only the dimensions it needs.")
table([
    ["fact_admission", "54,966", "all foreign keys, age_at_admission, length_of_stay_days, billing_amount, billing_per_day, is_billing_adjustment", "All"],
    ["dim_patient → dim_gender / dim_blood_type", "48,896 → 2 / 8", "gender, blood_type", "Q1, Q5, Q9"],
    ["dim_medical_condition", "6", "medical_condition", "Q1-Q3, Q6, Q7, Q9, Q10"],
    ["dim_insurance_provider", "5", "insurance_provider", "Q2, Q4"],
    ["dim_admission_type", "3", "admission_type", "Q6, Q10"],
    ["dim_test_result", "3", "test_result", "Q1, Q3"],
    ["dim_age_group", "5", "age_group, min_age, max_age", "Q5, Q7, Q8"],
    ["dim_medication", "5", "medication", "Q4"],
    ["dim_date → dim_month", "1,857 → 62", "year, year_month", "Q4, Q10"],
    ["dim_doctor, dim_hospital", "40,341 / 39,635", "not used (almost one value per admission)", "-"],
], ["Collection", "Docs", "Attributes used", "Questions"], widths=[1.6, 0.8, 3.3, 0.8], size=8)
P("Tables are combined with `$lookup` + `$unwind`, written once as shared stages and reused with `*LOOKUP_...`.")
code(re.search(r"LOOKUP_PATIENT = \[.*?\n\]\n\nLOOKUP_GENDER = \[.*?\n\]\n", QUERY_SRC, re.S).group(0) +
     "\n" + re.search(r"LOOKUP_ADMIT_MONTH = \[.*?\n\]\n", QUERY_SRC, re.S).group(0))
P("This pipeline joins one admission to all ten dimensions to show the combined record.")
code(pipeline_src("S1b"))
shot("s1_2", "admission 1 joined to every dimension.")

# ---------------------------------------------------------------- Stage 2
H("1.3 Stage 2: Data cleaning and preparation", 2)
P("`pipeline/clean.py` fixes the problems found in D2 before the data is modelled and loaded.")
table([
    ["Duplicate records", "Dropped 534 exact duplicates", "55,500 → 54,966 rows"],
    ["Mixed-case names (`LesLie TErRy`)", "Converted to title case", "49,992 → 40,235 names"],
    ["Hospital name fragments", "Removed stray 'and' and commas", "39,876 → 39,635 hospitals"],
    ["Dates stored as text", "Parsed to dates and YYYYMMDD keys", "2019-05-08 to 2024-06-06"],
    ["106 negative bills", "Kept and flagged, excluded from cost metrics", "`is_billing_adjustment`"],
    ["Missing values", "Checked every column", "0 missing"],
    ["No patient ID", "Patient = name + gender + blood type", "48,896 patients"],
    ["Derived fields", "Added stay length, billing per day, age group", "LOS 1-30 days"],
    ["Near-duplicates (found in Q10)", "Kept, and tests re-run without them", "4,966 rows, no verdict changes"],
], ["Issue", "Action", "Result"], widths=[2.0, 2.6, 1.9], size=8.5)
P("These checks confirm the loaded MongoDB data has no duplicates, missing values, impossible dates or orphan keys.")
code(pipeline_src("S2b"))
shot("s2_1", "no duplicated source rows.")
shot("s2_2", "data quality summary.")
shot("s2_4", "negative bills by insurer.")

# ---------------------------------------------------------------- Stage 3
H("1.4 Stage 3: Data transformation and aggregation", 2)
P("Every pipeline follows the class order of filter → join → group → calculate → sort → limit, using only cheat-sheet operators.")
table([
    ["Filter billing adjustments", "`$match` on `is_billing_adjustment`", "Keeps refunds out of cost averages"],
    ["Length-of-stay bands", "`$switch`", "Groups stays for Q5 and Q6"],
    ["Shares within a group", "`$setWindowFields` + `partitionBy`", "Compares groups of different sizes"],
    ["Conditional counts", "`$sum` of `$cond`", "Abnormal rate, long-stay %, refunds"],
    ["Insurer discount", "(market avg − insurer avg) ÷ market avg", "No paid amount exists (Q2)"],
    ["Ranking", "`$rank`", "Top and bottom performers"],
    ["Year-over-year change", "`$shift`", "Billing trend (Q4)"],
    ["Best in each group", "`$sort` + `$first` / `$last`", "Cheapest insurer per medication"],
    ["Test-ready sums", "n, Σx, Σx² in `$group`", "Lets Python finish ANOVA and Pearson r"],
    ["Buckets", "`$toInt` of bill ÷ 2,500", "Billing histogram (Q10)"],
], ["Transformation", "How (MongoDB)", "Why"], widths=[1.8, 2.5, 2.2], size=8.5)

# ---------------------------------------------------------------- Stage 4
H("1.5 Stage 4: Data analysis and validation", 2)
P("Python finishes three tests from the pipeline sums: chi-square for two categories, ANOVA for averages across groups, and Pearson r for two numbers.")
code(func_src("anova_sums") + "\n" + func_src("pearson_sums"))
P("All 19 spot-checked results match an independent pandas calculation, and no test changes verdict without the near-duplicates.")
shot("check_1", "MongoDB results match pandas (19 of 19).")
shot("check_2", "sensitivity check without the near-duplicates.")

H("1.6 Stage 5: Data visualization", 2)
P("Charts use sorted bars for comparisons, lines for trends, histograms for distributions, and heatmaps with a fixed colour range for two-way tables.")
page_break()

# ===========================================================================
# 2. Questions
# ===========================================================================
H("2. Answering the Business Questions", 1)
P("Section C shows the exact pipeline code from `mongodb/query.py` for each question.")

# ---------------------------------------------------------------- Q1
q1b, q1c = r("q1b_gender_gap"), r("q1c_gender_abnormal")
H("Q1. Gender and type of disease", 2)
section("A", "Business question")
P("Is there a correlation between gender and type of diseases?")
section("B", "Analytical approach")
P("We joined admissions to gender (through dim_patient) and condition, counted each combination, compared each condition's share by gender, and ran a chi-square test.")
section("C", "Query")
code(pipeline_src("Q1a"))
P("The window stage writes each gender's total onto every row so the count can become a share.")
code(pipeline_src("Q1b"))
shot("q1_1", "condition mix within each gender and chi-square test.")
shot("q1_2", "female vs male share of each condition.")
section("D", "Results")
df_table(q1b, ["condition", "female", "male", "female_pct", "male_pct", "gap_pts"],
         {"condition": "Condition", "female": "Female adm.", "male": "Male adm.", "female_pct": "% of female", "male_pct": "% of male", "gap_pts": "Gap (pts)"},
         {"female": "{:,}".format, "male": "{:,}".format, "female_pct": "{:.2f}%".format, "male_pct": "{:.2f}%".format, "gap_pts": "{:+.2f}".format})
chart("c01_q1_gender_condition", "Share of each condition within female and male admissions.")
P(f"**Test:** {test_text('Q1 gender x condition')}.")
section("E", "Interpretation and insights")
bullets([
    "Each condition is 16.4%-16.9% of both genders' admissions, so gender and disease type are not related (p = 0.96).",
    "This is unexpected, since some conditions differ by sex in real life, which suggests the data was generated randomly.",
    "Abnormal test rates are also about one-third for both genders in every condition.",
])
section("F", "Business recommendations")
bullets(["Plan condition services on total volume, not separate gender forecasts."])

# ---------------------------------------------------------------- Q2
q2a, q2b, q2c = r("q2a_discount_raw"), r("q2b_discount_adjusted"), r("q2c_discount_summary").iloc[0]
H("Q2. Mean insurance provider discount", 2)
section("A", "Business question")
P("What is the mean healthcare insurance provider discount?")
section("B", "Analytical approach")
P("Because there is no paid amount, we measured each insurer's discount as how far its average bill is below the market average, both overall and within each condition.")
section("C", "Query")
code(pipeline_src("Q2b"))
P("The window partitioned by condition gives each condition's market average, so each insurer is compared like-for-like.")
shot("q2_1", "raw discount vs the market average.")
shot("q2_2", "condition-adjusted discount per insurer.")
shot("q2_3", "the mean insurer discount.")
section("D", "Results")
m = q2a.merge(q2b, on="insurer")
df_table(m, ["discount_rank", "insurer", "admissions", "avg_bill", "discount_usd", "discount_pct", "mean_discount_pct", "best_condition", "worst_condition"],
         {"discount_rank": "Rank", "insurer": "Insurer", "admissions": "Admissions", "avg_bill": "Avg bill", "discount_usd": "Discount $",
          "discount_pct": "Raw disc. %", "mean_discount_pct": "Adjusted disc. %", "best_condition": "Best condition", "worst_condition": "Worst condition"},
         {"admissions": "{:,}".format, "avg_bill": "${:,.2f}".format, "discount_usd": "${:+,.2f}".format, "discount_pct": "{:+.3f}%".format,
          "mean_discount_pct": "{:+.3f}%".format}, size=8)
P(f"Mean discount **{q2c.mean_discount_pct:+.3f}%**, typical size **{q2c.mean_abs_discount_pct:.3f}%**, market average bill **${q2a.market_avg.iloc[0]:,.2f}**.")
chart("c02_q2_discount", "Condition-adjusted discount by insurer (blue = below market, red = above).")
section("E", "Interpretation and insights")
bullets([
    "The mean insurer discount is +0.004%, and the typical discount or premium is only 0.23% (about $59 per bill).",
    "UnitedHealthcare is the only insurer with a visible discount (+0.53%, $136 less per admission), while Medicare is billed 0.33% more.",
    "Raw and adjusted figures match, so the small differences are not caused by insurers covering different conditions.",
])
section("F", "Business recommendations")
bullets([
    "Collect paid/allowed amounts, because real discounts happen after billing and cannot be measured from this data.",
    "Negotiate contracts on payment speed and denials rather than billed price, which is already the same for all insurers.",
])

# ---------------------------------------------------------------- Q3
q3a, q3c = r("q3a_condition_los"), r("q3c_condition_cost")
H("Q3. Medical condition and treatment length", 2)
section("A", "Business question")
P("Is there a correlation between medical condition and treatment length?")
section("B", "Analytical approach")
P("We grouped length of stay by condition (and by condition × test result) and ran an ANOVA.")
section("C", "Query")
code(pipeline_src("Q3a"))
code(pipeline_src("Q3b"))
P("`$avg` ignores nulls, so `$cond` returning the stay for one test result gives that result's average in one pass.")
shot("q3_1", "length of stay by condition and ANOVA.")
shot("q3_2", "length of stay by condition × test result.")
section("D", "Results")
df_table(q3a.merge(q3c, on="condition"), ["condition", "n", "avg_los", "min_los", "max_los", "long_stay_pct", "avg_bill", "bill_per_patient_day"],
         {"condition": "Condition", "n": "Admissions", "avg_los": "Avg stay (days)", "min_los": "Min", "max_los": "Max", "long_stay_pct": "22+ day stays",
          "avg_bill": "Avg bill", "bill_per_patient_day": "Bill / patient-day"},
         {"n": "{:,}".format, "avg_los": "{:.2f}".format, "long_stay_pct": "{:.1f}%".format, "avg_bill": "${:,.0f}".format, "bill_per_patient_day": "${:,.0f}".format})
chart("c03_q3_condition_los", "Average length of stay by condition.")
chart("c04_q3_condition_test_heatmap", "Average stay by condition and test result.")
P(f"**Test:** {test_text('Q3 length of stay ~ condition')}.")
section("E", "Interpretation and insights")
bullets([
    "All conditions average 15.4-15.7 days, so condition does not affect treatment length (p = 0.39).",
    "Test results do not change stay length in any consistent direction either.",
    "Real hospitals show large differences between conditions, so this again points to synthetic data.",
])
section("F", "Business recommendations")
bullets(["Use one 15.5-day planning figure for beds, and review any stay that reaches day 21."])

# ---------------------------------------------------------------- Q4
q4a, q4c = r("q4a_insurer_billing"), r("q4c_insurer_medication")
H("Q4. Billing across insurance companies", 2)
section("A", "Business question")
P("How does the billing amount compare across insurance companies and does one provide better rates than the others?")
section("B", "Analytical approach")
P("We compared total, average and per-day billing by insurer, ranked them, tracked them by year, and found the cheapest insurer for each medication.")
section("C", "Query")
code(pipeline_src("Q4a"))
code(pipeline_src("Q4b"))
P("`$shift` with `partitionBy` pulls each insurer's previous year so the yearly change can be calculated.")
shot("q4_1", "billing by insurer, ranked, with ANOVA.")
shot("q4_2", "average bill by insurer and year.")
shot("q4_3", "cheapest and dearest insurer for each medication.")
section("D", "Results")
df_table(q4a, ["rate_rank", "insurer", "n", "total_billed", "share_of_billing_pct", "avg_bill", "bill_per_patient_day"],
         {"rate_rank": "Rank", "insurer": "Insurer", "n": "Admissions", "total_billed": "Total billed", "share_of_billing_pct": "Share",
          "avg_bill": "Avg bill", "bill_per_patient_day": "Bill / patient-day"},
         {"n": "{:,}".format, "total_billed": lambda v: f"${v/1e6:,.1f}M", "share_of_billing_pct": "{:.2f}%".format,
          "avg_bill": "${:,.2f}".format, "bill_per_patient_day": "${:,.2f}".format})
chart("c05_q4_insurer_bill", "Average bill per admission by insurer.")
chart("c06_q4_insurer_year", "Average bill by insurer and year (zoomed axis).")
df_table(q4c, rename={"medication": "Medication", "cheapest_insurer": "Cheapest", "cheapest_avg": "Avg", "dearest_insurer": "Dearest", "dearest_avg": "Avg",
                      "spread_pct": "Spread"},
         cols=["medication", "cheapest_insurer", "cheapest_avg", "dearest_insurer", "dearest_avg", "spread_pct"],
         fmt={"cheapest_avg": "${:,.0f}".format, "dearest_avg": "${:,.0f}".format, "spread_pct": "{:.2f}%".format})
P(f"**Test:** {test_text('Q4 billing amount ~ insurer')}.")
section("E", "Interpretation and insights")
bullets([
    "Average bills differ by only $219 (0.9%) between UnitedHealthcare and Medicare, which is not significant (p = 0.82).",
    "The cheapest insurer changes by year, by medication and by metric, so no insurer has consistently better rates.",
])
section("F", "Business recommendations")
bullets(["Treat the insurers as equal on billed rates and only act on gaps that last two or more years."])

# ---------------------------------------------------------------- Q5
q5c = r("q5c_correlations")
H("Q5. Billing rate by length of stay, age and gender", 2)
section("A", "Business question")
P("How does the billing rate, based on length of hospital stay, compare between age and gender?")
section("B", "Analytical approach")
P("We compared billing per day across stay-length bands, age groups and genders, and measured correlations from MongoDB sums.")
section("C", "Query")
code(pipeline_src("Q5b"))
code(re.search(r'    pairs = \[.*?save="q5c_correlations"\)', QUERY_SRC, re.S).group(0))
P("`$switch` turns each stay into a band before grouping, and `pearson_sums` returns the six sums each correlation needs.")
shot("q5_1", "billing rate by age group and gender.")
shot("q5_2", "billing rate by stay band and gender.")
shot("q5_3", "Pearson correlations.")
section("D", "Results")
chart("c07_q5_rate_by_los", "Average billing per day by stay length and gender.")
chart("c08_q5_rate_age_gender", "Billing per patient-day by age group and gender.")
df_table(q5c, ["pair", "n", "r", "r_squared", "p", "significant"],
         {"pair": "Pair", "n": "n", "r": "Pearson r", "r_squared": "r²", "p": "p-value", "significant": "Significant"},
         {"n": "{:,}".format, "p": "{:.4f}".format})
section("E", "Interpretation and insights")
bullets([
    "The bill is the same no matter how long the stay is, so the daily rate falls from about $9,400 (1-7 days) to $990 (22-30 days).",
    "Billing rate is the same for men and women and across adult age groups; the 13-17 group has only 116 admissions.",
    "Age vs daily rate is statistically significant only because the sample is huge (r = −0.01 has no practical meaning).",
])
section("F", "Business recommendations")
bullets(["Focus margin reviews on stays over 21 days, where each extra day adds cost but no revenue."])

# ---------------------------------------------------------------- Q6
q6a, q6b, q6c = r("q6a_los_distribution"), r("q6b_los_overall").iloc[0], r("q6c_admission_type_los")
H("Q6. How long patients stay, by condition and admission type", 2)
section("A", "Business question")
P("How long do patients stay, and does that vary by condition or admission type?")
section("B", "Analytical approach")
P("We summarized the stay distribution, compared stays by admission type (ANOVA), and ranked all condition × admission type combinations.")
section("C", "Query")
code(pipeline_src("Q6a"))
code(pipeline_src("Q6d"))
P("The `[\"unbounded\", \"current\"]` window gives a running total for the cumulative share.")
shot("q6_1", "stay distribution in bands.")
shot("q6_3", "overall stay summary.")
shot("q6_4", "stay by admission type and ANOVA.")
shot("q6_5", "condition × admission type ranked.")
section("D", "Results")
P(f"**{int(q6b.admissions):,} admissions, {int(q6b.patient_days):,} patient-days, average {q6b.avg_los:.2f} days, range {int(q6b.min_los)}-{int(q6b.max_los)} days.**")
df_table(q6a, ["los_band", "admissions", "avg_los", "share_pct", "cumulative_pct"],
         {"los_band": "Stay", "admissions": "Admissions", "avg_los": "Avg stay", "share_pct": "Share", "cumulative_pct": "Cumulative"},
         {"admissions": "{:,}".format, "share_pct": "{:.1f}%".format, "cumulative_pct": "{:.1f}%".format})
chart("c09_q6_los_histogram", "Admissions for each length of stay.")
df_table(q6c, ["admission_type", "n", "avg_los"], {"admission_type": "Admission type", "n": "Admissions", "avg_los": "Avg stay (days)"},
         {"n": "{:,}".format, "avg_los": "{:.2f}".format})
chart("c10_q6_condition_type_heatmap", "Average stay for each condition × admission type.")
P(f"**Test:** {test_text('Q6 length of stay ~ admission type')}.")
section("E", "Interpretation and insights")
bullets([
    "Patients stay 15.5 days on average, but every stay from 1 to 30 days is equally common.",
    "Stay length does not differ by admission type (p = 0.14) or condition, and every combination is within half a day of average.",
    "It is surprising that emergency patients do not stay longer than elective patients.",
])
section("F", "Business recommendations")
bullets(["Plan capacity on about 460 occupied beds per day overall instead of by condition or admission type."])

# ---------------------------------------------------------------- Q7
q7b = r("q7b_condition_age")
H("Q7. Age and type of disease", 2)
section("A", "Business question")
P("Is there a correlation between age and type of diseases?")
section("B", "Analytical approach")
P("We compared the condition mix within each age group (chi-square) and the average age for each condition (ANOVA).")
section("C", "Query")
code(pipeline_src("Q7a"))
code(pipeline_src("Q7b"))
shot("q7_1", "condition mix within each age group and chi-square test.")
shot("q7_2", "age profile of each condition and ANOVA.")
section("D", "Results")
chart("c11_q7_age_condition_heatmap", "Share of each condition within each age group.")
df_table(q7b, ["condition", "n", "avg_age", "min_age", "max_age", "seniors_pct", "under_35_pct"],
         {"condition": "Condition", "n": "Admissions", "avg_age": "Avg age", "min_age": "Min", "max_age": "Max", "seniors_pct": "65+", "under_35_pct": "Under 35"},
         {"n": "{:,}".format, "seniors_pct": "{:.1f}%".format, "under_35_pct": "{:.1f}%".format})
P(f"**Tests:** {test_text('Q7 age group x condition')}; {test_text('Q7 age ~ condition')}.")
section("E", "Interpretation and insights")
bullets([
    "Each condition is about one-sixth of every adult age group, so age and disease type are not related (p = 0.35).",
    "The 13-17 group looks different, but with only 116 admissions it is just noise.",
    "Real data would show conditions like hypertension rising with age, so this is strong evidence of synthetic data.",
])
section("F", "Business recommendations")
bullets(["Use population health data, not this dataset, to plan age-targeted programmes."])

# ---------------------------------------------------------------- Q8
q8a, q8c = r("q8a_age_group_los"), r("q8c_correlation").iloc[0]
H("Q8. Age group and duration of stay", 2)
section("A", "Business question")
P("Does the age group have an effect on the duration of the patient's stay?")
section("B", "Analytical approach")
P("We compared average stay by age group (ANOVA) and by single year of age, and measured the age-stay correlation.")
section("C", "Query")
code(pipeline_src("Q8a"))
shot("q8_1", "stay by age group and ANOVA.")
shot("q8_3", "Pearson correlation between age and stay.")
section("D", "Results")
df_table(q8a, ["age_group", "n", "avg_los", "short_stay_pct", "long_stay_pct"],
         {"age_group": "Age group", "n": "Admissions", "avg_los": "Avg stay (days)", "short_stay_pct": "≤ 7 days", "long_stay_pct": "≥ 22 days"},
         {"n": "{:,}".format, "avg_los": "{:.2f}".format, "short_stay_pct": "{:.1f}%".format, "long_stay_pct": "{:.1f}%".format})
chart("c12_q8_age_los", "Average stay by age (blue) and by age group (orange).")
P(f"**Tests:** {test_text('Q8 length of stay ~ age group')}; Pearson r = {q8c.r:.4f}, p = {q8c.p:.3f}.")
section("E", "Interpretation and insights")
bullets([
    "Average stay ranges only from 15.3 to 15.6 days across age groups, which is not significant (p = 0.29).",
    "Patients over 50 stay about 4 hours longer, but this is too small to matter.",
])
section("F", "Business recommendations")
bullets(["Use one length-of-stay target for all age groups."])

# ---------------------------------------------------------------- Q9
q9c = r("q9c_blood_top_condition")
H("Q9. Blood type, length of stay and condition rates", 2)
section("A", "Business question")
P("Does the blood type of the individual cause a longer stay or have a higher rate of a certain condition?")
section("B", "Analytical approach")
P("We joined blood type through dim_patient, compared average stay (ANOVA) and condition rates (chi-square), and found each blood type's most common condition.")
section("C", "Query")
code(pipeline_src("Q9a"))
code(pipeline_src("Q9c"))
P("Three window stages add the blood-type, condition and grand totals so each rate can be compared with the overall rate.")
shot("q9_1", "stay by blood type, ranked, with ANOVA.")
shot("q9_3", "most common condition per blood type.")
section("D", "Results")
chart("c13_q9_blood_los", "Average stay by blood type.")
chart("c14_q9_blood_condition_heatmap", "Rate of each condition within each blood type.")
df_table(q9c, ["blood_type", "top_condition", "rate_pct", "dataset_pct", "lift_pts"],
         {"blood_type": "Blood type", "top_condition": "Most common condition", "rate_pct": "Rate in blood type", "dataset_pct": "Rate overall", "lift_pts": "Lift (pts)"},
         {"rate_pct": "{:.2f}%".format, "dataset_pct": "{:.2f}%".format, "lift_pts": "{:+.2f}".format})
P(f"**Tests:** {test_text('Q9 length of stay ~ blood type')}; {test_text('Q9 blood type x condition')}.")
section("E", "Interpretation and insights")
bullets([
    "B+ patients stay longest and O+ shortest, but the gap is under half a day and not significant (p = 0.12).",
    "No blood type has a meaningfully higher rate of any condition (p = 0.48); the biggest lift is under 1 point.",
])
section("F", "Business recommendations")
bullets(["Leave blood type out of risk and bed-planning models."])

# ---------------------------------------------------------------- Q10
q10c, q10dd, q10e = r("q10c_outliers"), r("q10d2_near_duplicates"), r("q10e_month_outliers")
res = r("q10b_residuals")
H("Q10. Admission type, condition and outliers", 2)
section("A", "Business question")
P("Does the admission type correlate with the type of condition the patient has and are there any outliers from the data?")
section("B", "Analytical approach")
P("We tested the admission type × condition mix (chi-square) and searched for outliers in table cells, bills, records and months.")
section("C", "Query")
code(pipeline_src("Q10a"))
code(pipeline_src("Q10c"))
code(pipeline_src("Q10d2"))
P("Q10d2 groups on every field except age, so any group with more than one document is a repeated record.")
shot("q10_1", "admission-type mix and chi-square test.")
shot("q10_2", "largest residuals and the 2-SD billing fences.")
shot("q10_3", "billing outliers by admission type.")
shot("q10_5", "the ten highest daily billing rates.")
shot("q10_6", "near-duplicate admissions.")
shot("q10_7", "busiest and quietest months.")
section("D", "Results")
chart("c15_q10_condition_type_mix", "Admission-type mix within each condition.")
df_table(res, rename={"condition": "Condition", "admission_type": "Admission type", "std_residual": "Std. residual"})
chart("c16_q10_bill_histogram", "Distribution of billing amounts with the mean ± 2 SD fences.")
df_table(q10c, ["admission_type", "admissions", "negative_bills", "negative_per_1000", "below_2sd", "above_2sd", "one_day_stays", "max_bill_per_day"],
         {"admission_type": "Type", "admissions": "Admissions", "negative_bills": "Negative bills", "negative_per_1000": "per 1,000",
          "below_2sd": "< mean-2SD", "above_2sd": "> mean+2SD", "one_day_stays": "1-day stays", "max_bill_per_day": "Max $/day"},
         {"admissions": "{:,}".format, "max_bill_per_day": "${:,.0f}".format}, size=8)
df_table(q10dd, rename={"age_gap_years": "Age difference (years)", "record_groups": "Repeated records", "extra_copies": "Extra copies"})
df_table(q10e, ["rank", "year_month", "admissions", "vs_avg_pct", "emergency_share_pct"],
         {"rank": "Rank", "year_month": "Month", "admissions": "Admissions", "vs_avg_pct": "vs. average", "emergency_share_pct": "Emergency share"},
         {"vs_avg_pct": "{:+.1f}%".format, "emergency_share_pct": "{:.1f}%".format})
P(f"**Test:** {test_text('Q10 condition x admission type')}.")
section("E", "Interpretation and insights")
bullets([
    "Every condition is split about one-third each across admission types, so they are not meaningfully related (p = 0.057, and 0.16 without duplicates).",
    "No bill is beyond 2 standard deviations because bills are spread evenly from $0 to $52K.",
    "The real outliers are 106 negative bills, one-day stays billed up to $52,212, and 4,966 near-duplicate records (10% of the raw file).",
])
section("F", "Business recommendations")
bullets([
    "Add a unique admission ID and remove the 4,966 near-duplicates before using the data for financial reporting.",
    "Review negative bills and very high daily rates automatically before billing.",
])

page_break()
# ===========================================================================
# 3. Summary
# ===========================================================================
H("3. Final Analytical Summary", 1)
H("Most important findings", 2)
bullets([
    "No demographic or clinical field affects stay length or cost; all ten tests were non-significant.",
    "The only strong pattern is that bills do not grow with stay, so the daily rate falls as stays get longer (Q5).",
    "Insurers are billed almost the same, with a mean discount of +0.004% (Q2, Q4).",
    "The most actionable finding is data quality: 10% of raw rows are duplicates or near-duplicates (Q10).",
])
H("Significant patterns and relationships", 2)
P("Every field behaves independently of the others, which confirms the D2 observation that the dataset is synthetic.")
H("How the findings address the business objectives", 2)
table([
    ["Q1 Gender × disease", "No association (p = 0.96)", "Plan on total condition volume"],
    ["Q2 Mean insurer discount", "+0.004% (typical 0.23%)", "Collect paid amounts"],
    ["Q3 Condition × stay", "No association (p = 0.39)", "One 15.5-day planning figure"],
    ["Q4 Billing by insurer", "$219 (0.9%) spread", "Treat insurers as equal on rates"],
    ["Q5 Billing rate", "Falls 9× with stay; flat by age/gender", "Review stays over 21 days"],
    ["Q6 Stay by condition / type", "Uniform 1-30 days (p = 0.14)", "Plan ~460 beds/day overall"],
    ["Q7 Age × disease", "No association (p = 0.35)", "Use population data for age programmes"],
    ["Q8 Age group × stay", "No effect (p = 0.29)", "One stay target for all ages"],
    ["Q9 Blood type", "No effect", "Exclude from risk models"],
    ["Q10 Type × condition, outliers", "Not robust; 4,966 near-duplicates", "De-duplicate at source"],
], ["Question", "Answer", "Decision supported"], widths=[1.9, 2.3, 2.3], size=8.5)
H("Business decisions supported", 2)
bullets([
    "Fix data quality first with admission IDs and duplicate checks.",
    "Plan capacity on total volume rather than by condition or age.",
    "Use payment data, not billed amounts, in insurer negotiations.",
])
H("Limitations", 2)
bullets([
    "The data is synthetic, so results should not be used for clinical decisions.",
    "There is no paid amount, so the discount is a proxy.",
    "There is no patient ID, so patients are matched on name, gender and blood type.",
    "The 13-17 group has only 116 admissions, and 2019 and 2024 are partial years.",
])
H("Future analysis", 2)
bullets([
    "Run the same pipelines on real de-identified admissions data.",
    "Add payment and denial data to measure true insurer discounts.",
    "Model readmissions and multi-factor length of stay once a reliable patient ID exists.",
])

page_break()
# ===========================================================================
# Appendices
# ===========================================================================
H("Appendix A. File inventory and how to re-run", 1)
table([
    ["pipeline/clean.py", "Stage 2 cleaning"],
    ["pipeline/build_schema.py", "Stage 2 snowflake tables"],
    ["mongodb/import_data.py", "Stage 1 load into MongoDB"],
    ["mongodb/query.py", "All aggregation pipelines (S1, S2, Q1-Q10, CHECK)"],
    ["mongodb/stats.py", "Chi-square, ANOVA, Pearson"],
    ["mongodb/charts.py", "The 16 charts"],
    ["mongodb/screenshots.py", "Execution screenshots"],
    ["mongodb/results/", "Every result table as CSV"],
    ["report/build_report.py", "Builds this report"],
], ["File", "Purpose"], widths=[2.2, 4.3])
code("""
pip install -r requirements.txt
python3 pipeline/clean.py && python3 pipeline/build_schema.py
python3 mongodb/import_data.py          # needs MongoDB on mongodb://127.0.0.1:27017
python3 mongodb/query.py                # or one step: python3 mongodb/query.py Q3
python3 mongodb/charts.py && python3 mongodb/screenshots.py
python3 report/build_report.py
""", size=8.5)

H("Appendix B. Statistical tests", 1)
tt = TESTS.reset_index()
df_table(tt, ["test", "method", "statistic", "df", "p", "effect", "significant"],
         {"test": "Test", "method": "Method", "statistic": "Statistic", "df": "df", "p": "p-value", "effect": "Effect size", "significant": "Significant"},
         {"p": "{:.4f}".format}, size=8)
sens = r("check_sensitivity")
P("Sensitivity check without the 4,966 near-duplicate admissions:")
df_table(sens, rename={"test": "Test", "p_all_rows": "p (all rows)", "p_without_near_dups": "p (without near-duplicates)", "same_verdict": "Same verdict"}, size=8)

# footer page numbers
for s in doc.sections:
    p = s.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(9)

doc.save(OUT)
print("wrote", OUT, f"({fig_no[0]} figures)")

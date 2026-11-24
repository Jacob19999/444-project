"""Build the D3 class report from the saved MongoDB results.

Run from the project folder with python3 report/build_report.py.
"""

import re
from io import BytesIO

from PIL import Image
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
MONGO = ROOT / "mongodb"
OUT = ROOT / "report" / "D3_Analytical_Report.docx"


CONSOLE = (MONGO / "results" / "full_output.txt").read_text()


doc = Document()
section = doc.sections[0]
section.page_width, section.page_height = Inches(8.5), Inches(11)
section.left_margin = section.right_margin = Inches(1)
section.top_margin = section.bottom_margin = Inches(0.85)

for name, font, size in [
    ("Normal", "Calibri", 11.5), ("Title", "Calibri", 25),
    ("Heading 1", "Calibri", 17), ("Heading 2", "Calibri", 14),
]:
    style = doc.styles[name]
    style.font.name = font
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor.from_string("171717")
    fonts = style.element.get_or_add_rPr().rFonts
    for key in ("asciiTheme", "hAnsiTheme"):
        fonts.attrib.pop(qn("w:" + key), None)
    fmt = style.paragraph_format
    fmt.space_before = Pt(0 if name in ("Normal", "Title") else 10)
    fmt.space_after = Pt(5)
    fmt.line_spacing = 1.1
    if name == "Title":
        props = style.element.get_or_add_pPr()
        border = props.find(qn("w:pBdr"))
        if border is not None:
            props.remove(border)

code_style = doc.styles.add_style("Query example", WD_STYLE_TYPE.PARAGRAPH)
code_style.font.name = "Courier New"
code_style.font.size = Pt(10)
code_format = code_style.paragraph_format
code_format.left_indent = Inches(0.18)
code_format.space_before = Pt(2)
code_format.space_after = Pt(6)
code_format.line_spacing = 1.0
code_format.keep_together = True


def centered(text, style=None):
    p = doc.add_paragraph(text, style)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def example(text):
    doc.add_paragraph(text.strip(), "Query example")


def question(heading, answer, query):
    heading = doc.add_heading(heading, level=1)
    heading.paragraph_format.page_break_before = True
    doc.add_paragraph(answer)
    example(query)


def terminal(block, columns, limit=None):
    """Keep original console values and alignment for the columns shown."""
    match = re.search(rf"^--- {block} [^\n]* ---\n(.+?)(?=\n\s*\n|\Z)",
                      CONSOLE, re.MULTILINE | re.DOTALL)
    lines = match.group(1).splitlines()
    header, rows = lines[0], lines[1:]
    names = list(re.finditer(r"\S+", header))
    # pandas pads each printed column. Its separator is blank on every row,
    # including rows with multiword labels such as "Blue Cross".
    edges = [0]
    for left, right in zip(names, names[1:]):
        gap = next(i for i in range(left.end(), right.start())
                   if all(line[i:i+1] == " " for line in lines))
        edges.append(gap + 1)
    edges.append(max(map(len, lines)))
    spans = {name.group(): (a, b) for name, a, b in zip(names, edges, edges[1:])}
    visible = [header, *rows[:limit]]
    excerpts = [" ".join(line[slice(*spans[col])] for col in columns).rstrip()
                for line in visible]
    question_id = re.match(r"Q\d+", block).group()
    label = doc.add_paragraph()
    label.add_run(f"Terminal output from {block}").bold = True
    if limit and limit < len(rows):
        label.add_run(f" (first {limit} rows)")
    label.paragraph_format.keep_with_next = True
    prompt = f"$ python3 mongodb/query.py {question_id}"
    para = doc.add_paragraph("\n".join([prompt, *excerpts]), "Query example")
    fill = OxmlElement("w:shd")
    fill.set(qn("w:fill"), "EFF2F4")
    para._p.get_or_add_pPr().append(fill)


def chart(filename, title, trim_top=0):
    """Use the project figure with a short title in the report."""
    if title:
        caption = doc.add_paragraph()
        caption.add_run(title).bold = True
        caption.paragraph_format.keep_with_next = True
    with Image.open(MONGO / "charts" / filename) as source:
        # Some original headings include a line of statistical test results.
        # Keep the plot area, axes and legend below that heading.
        plot = source.crop((0, trim_top, source.width, source.height))
        buffer = BytesIO()
        plot.save(buffer, format="PNG")
        buffer.seek(0)
        doc.add_picture(buffer, width=Inches(6.1))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


centered("Healthcare Admissions and Billing", "Title")
centered("CIS 444/544  •  Deliverable 3  •  November 2026")
centered("Chloe Jensrud, Beth Johnson, Caitlin Sheeran, Jacob Tang\nand Nofogon Grace Marienne Dosso")

doc.add_heading("Project overview", 1)
doc.add_paragraph(
    "We used the Kaggle Healthcare Dataset to compare hospital stays and bills from May 2019 "
    "to May 2024. The records are synthetic. Across all six medical conditions, the average "
    "stay was about 15½ days. Short stays stood out because their total bills were close to "
    "those for longer stays, leaving a much higher bill per day."
)
doc.add_heading("How we prepared the data", 2)
for paragraph in [
    "We started with 55,500 rows. We removed 534 exact duplicates, cleaned up names and "
    "hospital names, and used admission and discharge dates to count the days in each stay.",
    "We loaded 54,966 admissions into MongoDB. One collection holds the admissions. "
    "Thirteen smaller collections hold details such as patient, condition and insurer. "
    "We joined them by ID when a question needed those details.",
    "We kept 106 negative bills for review and left them out of billing averages. That gave "
    "us 54,860 admissions for the billing questions. We used all 54,966 for counts and stay lengths.",
    "We grouped admissions, counted records and compared averages. We checked 19 results "
    "against the cleaned CSV using pandas. All 19 matched.",
]:
    doc.add_paragraph(paragraph)
doc.add_heading("How to read the queries", 2)
doc.add_paragraph(
    "Each question shows a short PyMongo example. The examples use the setup in mongodb/query.py. "
    "The LOOKUP steps bring in names for each group. VALID_BILLS leaves out the negative bills. "
    "The show function prints the results as a table. Below each example, we show selected "
    "columns from the full query’s saved terminal output."
)
example("""
# Run question 3 from the project folder
python3 mongodb/query.py Q3
""")
doc.add_paragraph("The full queries are in mongodb/query.py. The output tables, charts and query "
                  "screenshots are in the results, charts and screenshots folders under mongodb.")

question("1. Do men and women have different medical conditions?",
    "The six conditions appeared about equally often in both groups. Arthritis showed the "
    "largest gap. It accounted for 16.90% of admissions for women and 16.64% for men. "
    "We counted admissions, so a patient who came back could appear more than once.", """
# Q1. Count admissions for each gender and condition.
show("Q1", fact_admission.aggregate([
    *LOOKUP_PATIENT, *LOOKUP_GENDER, *LOOKUP_CONDITION,
    {"$group": {
        "_id": {"gender": "$gender.gender",
                "condition": "$condition.medical_condition"},
        "admissions": {"$sum": 1}
    }},
    {"$sort": {"_id": 1}}
]))
""")
terminal("Q1b", ['condition', 'female', 'male', 'female_pct', 'male_pct'])
chart("c01_q1_gender_condition.png", "Share of admissions for each condition by gender", 97)

question("2. How much of a discount did insurers receive?",
    "We only have the amounts billed. To estimate a discount, we would also need the amounts "
    "insurers agreed to pay. We could still compare each insurer’s average bill with the "
    "overall average of $25,594.63. UnitedHealthcare was $135.74 below that average. "
    "Medicare was $83.45 above it.", """
# Q2. Find the overall average bill for the comparison.
show("Q2", fact_admission.aggregate([
    VALID_BILLS,
    {"$group": {"_id": None,
                "average_bill": {"$avg": "$billing_amount"}}}
]))
""")
doc.add_paragraph("We also compared bills within each condition. Averaging those differences across "
                  "the five insurers gave a gap of just 0.004% below average. Small differences "
                  "in opposite directions largely canceled out.")



terminal("Q2a", ['insurer', 'avg_bill', 'market_avg', 'discount_usd'])
chart("c05_q4_insurer_bill.png", "Average amount billed per admission by insurer", 100)

question("3. Which medical conditions had the longest stays?",
    "Asthma had the longest average stay at 15.68 days. Diabetes had the shortest at "
    "15.43 days. That is a difference of about six hours. The other four conditions fell "
    "between them.", """
# Q3. Average the days in the hospital for each condition.
show("Q3", fact_admission.aggregate([
    *LOOKUP_CONDITION,
    {"$group": {"_id": "$condition.medical_condition",
                "average_days": {"$avg": "$length_of_stay_days"}}},
    {"$sort": {"average_days": -1}}
]))
""")
terminal("Q3a", ['condition', 'n', 'avg_los', 'min_los', 'max_los'])
chart("c03_q3_condition_los.png", "Average stay by condition in days (dashed line shows the overall average)", 94)

question("4. Which insurer had the lowest average bill?",
    "UnitedHealthcare had the lowest average bill. Medicare had the highest. The gap was "
    "about $219 per admission, less than 1%. When we grouped admissions by medication, "
    "the insurer with the lowest bill changed.", """
# Q4. List insurers from lowest to highest average bill.
show("Q4", fact_admission.aggregate([
    VALID_BILLS, *LOOKUP_INSURANCE,
    {"$group": {"_id": "$insurer.insurance_provider",
                "average_bill": {"$avg": "$billing_amount"}}},
    {"$sort": {"average_bill": 1}}
]))
""")

terminal("Q4a", ['insurer', 'n', 'avg_bill'])
chart("c06_q4_insurer_year.png", "", 0)

question("5. How did the daily bill change with stay length, age and gender?",
    "We divided each bill by the number of days in that stay, then averaged those daily "
    "amounts. For women and men, the daily bill was about $9,400 for stays of 1–7 days "
    "and about $990 for stays of 22–30 days. Total bills were similar across these groups, "
    "so spreading a bill over more days brought the daily amount down.", """
# Q5. Compare daily bills by stay length and gender.
show("Q5", fact_admission.aggregate([
    VALID_BILLS, *LOOKUP_PATIENT, *LOOKUP_GENDER,
    {"$group": {"_id": {"stay": LOS_BAND, "gender": "$gender.gender"},
                "daily_bill": {"$avg": "$billing_per_day"}}},
    {"$sort": {"_id": 1}}
]))
""")
doc.add_paragraph("Across adult age groups, averages for women and men ranged from about $3,260 "
                  "to $3,540 per day. Ages 13–17 had higher averages, but that group had only "
                  "116 admissions.")
terminal("Q5b", ['los_band', 'gender', 'avg_bill', 'avg_daily_rate'])
chart("c07_q5_rate_by_los.png", "Average daily bill by stay length and gender", 97)

question("6. How long did patients stay by admission type?",
    "Stays ranged from 1 to 30 days and averaged 15.5 days overall. Emergency admissions "
    "averaged 15.58 days, elective admissions 15.51 and urgent admissions 15.40. Even "
    "when we split each admission type by condition, averages ranged only from 15.10 days "
    "for urgent diabetes admissions to 16.01 for emergency cancer admissions.", """
# Q6. Compare emergency, elective and urgent stays.
show("Q6", fact_admission.aggregate([
    *LOOKUP_ADMISSION_TYPE,
    {"$group": {"_id": "$adm_type.admission_type",
                "average_days": {"$avg": "$length_of_stay_days"}}},
    {"$sort": {"average_days": -1}}
]))
""")


terminal("Q6c", ['admission_type', 'n', 'avg_los'])
chart("c09_q6_los_histogram.png", "", 0)

question("7. Were some conditions more common at certain ages?",
    "Among adults, each of the six conditions accounted for about one in six admissions "
    "in every age group. The youngest group looked different. For example, 27 of the "
    "116 admissions for ages 13–17 were for obesity, compared with 11 for hypertension. "
    "With so few admissions, a handful of cases can change the percentages.", """
# Q7. Count each condition within each age group.
show("Q7", fact_admission.aggregate([
    *LOOKUP_AGE_GROUP, *LOOKUP_CONDITION,
    {"$group": {
        "_id": {"age_group": "$age_group.age_group",
                "condition": "$condition.medical_condition"},
        "admissions": {"$sum": 1}
    }},
    {"$sort": {"_id": 1}}
]))
""")
terminal("Q7a", ['age_group', 'condition', 'admissions', 'group_total', 'share_pct'], limit=6)
chart("c11_q7_age_condition_heatmap.png", "Share of admissions for each condition within each age group", 96)

question("8. Did older patients stay longer?",
    "Only slightly. Patients ages 65 and older averaged 15.58 days in the hospital. "
    "Those ages 18–34 averaged 15.41 days, about four hours less. Age alone tells us "
    "little about how long an individual admission lasted in these records.", """
# Q8. Count admissions and average days for each age group.
show("Q8", fact_admission.aggregate([
    *LOOKUP_AGE_GROUP,
    {"$group": {"_id": "$age_group.age_group", "admissions": {"$sum": 1},
                "average_days": {"$avg": "$length_of_stay_days"}}},
    {"$sort": {"_id": 1}}
]))
""")

terminal("Q8a", ['age_group', 'n', 'avg_los'])
chart("c12_q8_age_los.png", "Average stay by age at admission", 94)

question("9. Did blood type go with longer stays or certain conditions?",
    "B+ had the longest average stay at 15.69 days. O+ had the shortest at 15.25 days. "
    "The mix of conditions was also similar. For example, hypertension was the most common "
    "condition for AB+ admissions, at 17.49% compared with 16.65% across all admissions.", """
# Q9. Average the stay for each blood type.
show("Q9", fact_admission.aggregate([
    *LOOKUP_PATIENT, *LOOKUP_BLOOD_TYPE,
    {"$group": {"_id": "$blood.blood_type",
                "average_days": {"$avg": "$length_of_stay_days"}}},
    {"$sort": {"average_days": -1}}
]))
""")
terminal("Q9a", ['blood_type', 'n', 'avg_los'])
chart("c13_q9_blood_los.png", "Average stay by blood type in days (dashed line shows the overall average)", 95)

question("10. Did admission type vary by condition? What stood out?",
    "For every condition, about one-third of admissions were elective, one-third were "
    "emergencies and one-third were urgent. The unusual cases showed up in the billing "
    "and duplicate checks. We found 106 negative bills and a one-day stay billed at "
    "$52,211.85.", """
# Q10. Count the three admission types for each condition.
show("Q10", fact_admission.aggregate([
    *LOOKUP_CONDITION, *LOOKUP_ADMISSION_TYPE,
    {"$group": {
        "_id": {"condition": "$condition.medical_condition",
                "type": "$adm_type.admission_type"},
        "admissions": {"$sum": 1}
    }},
    {"$sort": {"_id": 1}}
]))
""")
doc.add_paragraph("After removing the exact duplicates, we found 4,966 more rows that matched "
                  "another admission in every original field except age. The ages differed by "
                  "one to five years. We kept these rows in the reported totals.")
terminal("Q10d2", ['age_gap_years', 'record_groups', 'extra_copies'])
chart("c15_q10_condition_type_mix.png", "Elective, urgent and emergency admissions for each condition", 100)

doc.add_heading("What we would check next", 2)
doc.add_paragraph("We would ask for a unique admission ID to check the repeated rows and payment "
                  "records to measure insurer discounts. The synthetic records work for practicing "
                  "these queries. Real hospital records would be needed for staffing or pricing decisions.")

doc.core_properties.title = "Healthcare Admissions and Billing"
doc.core_properties.author = "Chloe Jensrud, Beth Johnson, Caitlin Sheeran, Jacob Tang and Nofogon Grace Marienne Dosso"
doc.save(OUT)

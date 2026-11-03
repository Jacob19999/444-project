# 444-project: Healthcare Admissions and Billing Analysis

## Team Members

| Name | Email |
|---|---|
| Chloe Jensrud | chloe.jensrud@mnsu.edu |
| Elizabeth Johnson | elizabeth.johnson.4@mnsu.edu |
| Caitlin Sheeran | caitlin.sheeran@mnsu.edu |
| Zijian (Jacob) Tang | tang.zijian@mnsu.edu |
| Nofogon Grace Marienne Dosso | nofogongracemarienne.dosso@mnsu.edu |

## Project Introduction

This project looks at hospital admission records to find out what drives healthcare costs and how patients use hospital services. We will look at how billing amounts, length of stay, and admission types differ by patient demographics, medical condition, insurance provider, and time period.

From a data analytics point of view, this topic matters because healthcare spending is high and keeps rising. Hospitals, insurers, and policymakers depend on data to plan resources, set prices, staff departments, and spot unusual costs. The dataset has a mix of numerical, categorical, and date fields, so it supports many kinds of analysis: descriptive statistics, comparisons between groups, trends over time, and simple predictive modeling.

## Dataset Description

| Item | Details |
|---|---|
| **Name** | Healthcare Dataset |
| **Source** | Kaggle, published by Prasad Patil (synthetic data made to look like real hospital records) |
| **Link** | https://www.kaggle.com/datasets/prasad22/healthcare-dataset |
| **Size** | 55,500 rows (records) × 15 columns (attributes) |
| **Format** | CSV (`Data/healthcare_dataset.csv`, about 8.4 MB) |
| **Time span** | Admission dates from May 2019 to May 2024 |

Each row is one hospital admission for one patient.

## Important Attributes

| Attribute | Description | Type |
|---|---|---|
| Name | Patient name | Text (identifier, not used in analysis) |
| Age | Patient's age at admission (13–89) | Numerical (integer) |
| Gender | Patient gender (Male, Female) | Categorical |
| Blood Type | Patient blood type (A+, A-, B+, B-, AB+, AB-, O+, O-) | Categorical |
| Medical Condition | Primary diagnosis (Arthritis, Asthma, Cancer, Diabetes, Hypertension, Obesity) | Categorical |
| Date of Admission | Date the patient was admitted | Date/time |
| Doctor | Doctor responsible for the patient | Categorical (high cardinality) |
| Hospital | Hospital where the patient was admitted | Categorical (high cardinality) |
| Insurance Provider | Patient's insurer (Aetna, Blue Cross, Cigna, Medicare, UnitedHealthcare) | Categorical |
| Billing Amount | Total amount billed for the stay (USD) | Numerical (continuous) |
| Room Number | Room the patient stayed in (101–500) | Numerical (used as an identifier) |
| Admission Type | Emergency, Urgent, or Elective | Categorical |
| Discharge Date | Date the patient was discharged | Date/time |
| Medication | Medication given (Aspirin, Ibuprofen, Lipitor, Paracetamol, Penicillin) | Categorical |
| Test Results | Result of medical tests (Normal, Abnormal, Inconclusive) | Categorical |

**Derived attribute:** *Length of Stay* = Discharge Date − Date of Admission, in days (numerical, 1–30 days).

## Analytical Questions

1. **Cost drivers:** How do average billing amounts differ by medical condition, admission type, and insurance provider, and which mix of these factors goes with the highest and lowest costs?
2. **Length of stay:** How does length of stay change with age group, medical condition, and admission type, and how strong is the relationship between length of stay and billing amount?
3. **Demographic patterns:** How are medical conditions spread across age groups and genders, and are some conditions more common in certain groups?
4. **Trends over time:** How have admission volume, average billing amount, and the mix of admission types changed by month and year from 2019 to 2024? Are there seasonal patterns?
5. **Insurance comparison:** Do insurance providers differ in the patients they cover (age, condition, admission type) and in the average amounts billed to them?
6. **Treatment and outcomes:** How do test results and medications vary across medical conditions, and are abnormal test results linked to longer stays or higher bills?

## Data Quality and Preparation

The first profiling of the dataset found these issues:

- **Duplicate records:** 534 rows are exact duplicates and should be removed.
- **Inconsistent capitalization:** Patient names have random upper/lower case (e.g., `Bobby JacksOn`, `DaNnY sMitH`). They should be converted to a standard case, or dropped, since names are not used in the analysis.
- **Messy hospital names:** About 4,800 hospital names end with a stray comma, and about 5,700 start with "and " (e.g., `"Hernandez Rogers and Vang,"`). These need to be cleaned before grouping by hospital.
- **Invalid values / outliers:** 108 records have a negative billing amount (minimum about −$2,008). We will look into these and either remove them or mark them as refunds/adjustments.
- **Incorrect data types:** `Date of Admission` and `Discharge Date` are loaded as text and must be converted to dates. `Room Number` is numeric but should be treated as an identifier.
- **High-cardinality fields:** `Doctor` (~40,000 unique) and `Hospital` (~40,000 unique) have too many values to compare directly. They will be left out of most group comparisons or grouped together.
- **Missing values:** None found, but we will check again after cleaning.
- **Synthetic data:** The dataset is synthetic, and many distributions are close to uniform (for example, average billing is almost the same, about $25K, for every condition). Findings will describe patterns in this dataset and should not be read as real-world clinical conclusions.

**Planned preprocessing steps:**

1. Remove exact duplicate rows.
2. Standardize text fields (names, hospital names).
3. Convert date columns to dates, and add `Length of Stay`, admission year, and admission month.
4. Handle negative billing amounts.
5. Make age groups (e.g., 13–17, 18–34, 35–49, 50–64, 65+) for segmentation.

## Expected Analysis and Project Direction

We expect to learn how cost and length of stay relate to patient characteristics and the type of care given, and whether there are clear patterns over time or differences between insurance providers. Because the data is synthetic, we also expect some relationships to be weak or missing. Reporting that honestly is part of the analysis.

Planned types of analysis:

- **Descriptive statistics** for all key attributes, before and after cleaning
- **Comparisons** of billing and length of stay across conditions, admission types, insurers, and demographic groups (group-by summaries, with ANOVA or chi-square tests where they fit)
- **Trend analysis** of monthly and yearly admissions and billing
- **Correlation analysis** between age, length of stay, and billing amount
- **Segmentation** of patients by age group, condition, and admission type
- **Visualizations and a dashboard** (bar charts, box plots, heatmaps, time-series line charts) to share the findings
- **Predictive analysis (optional):** a simple regression or classification model (e.g., predicting billing amount or test result) to see whether the available attributes can predict outcomes

## Data Pipeline: CSV to Snowflake Schema

The raw CSV is cleaned and split into a **snowflake schema**: one fact table with one row per admission, plus dimension tables. Two of the dimensions are normalized one level further. The tables are written as CSVs and loaded into a Snowflake database with the scripts in `sql/`.

```
 dim_gender ─────┐
                 ├─ dim_patient ─┐
 dim_blood_type ─┘               │
                  dim_doctor ────┤
                dim_hospital ────┤
      dim_insurance_provider ────┤
       dim_medical_condition ────┼── fact_admission
              dim_medication ────┤
          dim_admission_type ────┤
             dim_test_result ────┤
               dim_age_group ────┤
 dim_month ── dim_date ──────────┘  (admission + discharge date)
```

| Table | Rows | Contents |
|---|---|---|
| `fact_admission` | 54,966 | Foreign keys to every dimension, plus age at admission, room number, length of stay, billing amount, billing per day, and an `is_billing_adjustment` flag |
| `dim_patient` | 48,896 | Cleaned patient name, linked to gender and blood type |
| `dim_doctor` / `dim_hospital` | 40,341 / 39,635 | Doctor names; cleaned hospital names |
| `dim_date` → `dim_month` | 1,857 → 62 | Calendar from 2019-05-08 to 2024-06-06; the month table holds year, quarter, and month |
| Small lookups | 2–8 each | Gender, blood type, insurer, condition, medication, admission type, test result, age group |

**Cleaning decisions:**
- 534 exact duplicate rows are removed.
- Names are converted to title case, with suffixes such as DDS and PhD kept in capitals.
- Leading "and " and trailing commas or " and" are stripped from hospital names.
- 106 negative billing amounts are **kept and flagged**, not deleted. The analysis queries filter them out.
- The source has no patient ID, so a patient is identified by name + gender + blood type. Age is stored per admission on the fact table.

### Running it

```bash
pip install -r requirements.txt
python3 pipeline/clean.py          # -> output/cleaned_healthcare.csv
python3 pipeline/build_schema.py   # -> output/tables/*.csv (14 tables)
python3 pipeline/verify_local.py   # checks keys + runs every analysis query in SQLite
```

Then, in Snowflake:

1. `sql/01_create_tables.sql` creates the `HEALTHCARE_DB.ANALYTICS` database, schema, and tables.
2. `sql/02_load_data.sql` creates a stage, uploads the CSVs, and runs `COPY INTO` for each table. The upload step uses SnowSQL / `snow sql`; you can also upload the files through Snowsight.
3. `sql/03_analysis_queries.sql` has one query for each analytical question (Q1–Q6), plus correlation, monthly trend, and data-quality queries.

The dataset has no discount or paid-amount column, so Q2 (insurer discount) compares each insurer's average bill with the overall average. It is a proxy, not a true discount.

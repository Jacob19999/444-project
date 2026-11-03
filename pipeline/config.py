"""Shared paths and settings for the pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA = ROOT / "Data" / "healthcare_dataset.csv"
OUTPUT_DIR = ROOT / "output"
TABLES_DIR = OUTPUT_DIR / "tables"
CLEANED_DATA = OUTPUT_DIR / "cleaned_healthcare.csv"
DASHBOARD_JSON = OUTPUT_DIR / "dashboard_data.json"
FINDINGS_MD = OUTPUT_DIR / "findings.md"

# Age groups used for segmentation (right-inclusive upper bounds).
AGE_BINS = [12, 17, 34, 49, 64, 120]
AGE_LABELS = ["13-17", "18-34", "35-49", "50-64", "65+"]

# Years with a complete Jan-Dec record; 2019 and 2024 are partial.
FULL_YEARS = [2020, 2021, 2022, 2023]

ALPHA = 0.05

# Snowflake SQL scripts and the local SQLite copy used to test them.
SQL_DIR = ROOT / "sql"
ANALYSIS_SQL = SQL_DIR / "03_analysis_queries.sql"
LOCAL_DB = OUTPUT_DIR / "healthcare_snowflake.db"

# Load order for the snowflake schema: parent tables before the tables
# that reference them.
SCHEMA_TABLES = [
    "dim_gender",
    "dim_blood_type",
    "dim_patient",
    "dim_doctor",
    "dim_hospital",
    "dim_insurance_provider",
    "dim_medical_condition",
    "dim_medication",
    "dim_admission_type",
    "dim_test_result",
    "dim_age_group",
    "dim_month",
    "dim_date",
    "fact_admission",
]

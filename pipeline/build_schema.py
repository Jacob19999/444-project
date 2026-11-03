"""Split the cleaned data into snowflake-schema tables (output/tables/*.csv).

Model (one fact table, normalized dimensions):

    dim_gender ─┐
                ├─ dim_patient ─┐
 dim_blood_type ┘               │
                 dim_doctor ────┤
               dim_hospital ────┤
     dim_insurance_provider ────┤
      dim_medical_condition ────┼── fact_admission
             dim_medication ────┤
         dim_admission_type ────┤
            dim_test_result ────┤
              dim_age_group ────┤
     dim_month ── dim_date ─────┘  (admission and discharge date)

Each CSV matches a table in sql/01_create_tables.sql, column for column.

Run: python3 pipeline/build_schema.py   (after pipeline/clean.py)
"""

import pandas as pd

from config import AGE_BINS, AGE_LABELS, CLEANED_DATA, SCHEMA_TABLES, TABLES_DIR


def lookup(values: pd.Series, id_col: str, name_col: str) -> pd.DataFrame:
    """Small dimension: one row per distinct value, ids in alphabetical order."""
    names = sorted(values.unique())
    return pd.DataFrame({id_col: range(1, len(names) + 1), name_col: names})


def key_map(dim: pd.DataFrame, id_col: str, name_col: str) -> dict:
    return dict(zip(dim[name_col], dim[id_col]))


def build_age_group() -> pd.DataFrame:
    return pd.DataFrame({
        "age_group_id": range(1, len(AGE_LABELS) + 1),
        "age_group": AGE_LABELS,
        "min_age": [lo + 1 for lo in AGE_BINS[:-1]],
        "max_age": AGE_BINS[1:],
    })


def build_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Contiguous calendar from first admission to last discharge."""
    days = pd.date_range(df["Date of Admission"].min(), df["Discharge Date"].max(), freq="D")

    dim_date = pd.DataFrame({
        "date_id": days.strftime("%Y%m%d").astype(int),
        "full_date": days.strftime("%Y-%m-%d"),
        "month_id": days.strftime("%Y%m").astype(int),
        "day_of_month": days.day,
        "day_of_week": days.dayofweek + 1,  # 1 = Monday
        "day_name": days.day_name(),
        "is_weekend": days.dayofweek >= 5,
    })

    months = days.to_period("M").unique()
    dim_month = pd.DataFrame({
        "month_id": months.strftime("%Y%m").astype(int),
        "year": months.year,
        "quarter": months.quarter,
        "month_number": months.month,
        "month_name": months.strftime("%B"),
        "year_month": months.strftime("%Y-%m"),
    })
    return dim_month, dim_date


def build_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    t = {}

    t["dim_gender"] = lookup(df["Gender"], "gender_id", "gender")
    t["dim_blood_type"] = lookup(df["Blood Type"], "blood_type_id", "blood_type")
    t["dim_doctor"] = lookup(df["Doctor"], "doctor_id", "doctor_name")
    t["dim_hospital"] = lookup(df["Hospital"], "hospital_id", "hospital_name")
    t["dim_insurance_provider"] = lookup(df["Insurance Provider"], "insurance_provider_id", "insurance_provider")
    t["dim_medical_condition"] = lookup(df["Medical Condition"], "medical_condition_id", "medical_condition")
    t["dim_medication"] = lookup(df["Medication"], "medication_id", "medication")
    t["dim_admission_type"] = lookup(df["Admission Type"], "admission_type_id", "admission_type")
    t["dim_test_result"] = lookup(df["Test Results"], "test_result_id", "test_result")
    t["dim_age_group"] = build_age_group()
    t["dim_month"], t["dim_date"] = build_dates(df)

    # The source has no patient ID. A patient is identified by cleaned name +
    # gender + blood type; age is per admission, so it lives on the fact table.
    gender_ids = key_map(t["dim_gender"], "gender_id", "gender")
    blood_ids = key_map(t["dim_blood_type"], "blood_type_id", "blood_type")
    patient_cols = ["Name", "Gender", "Blood Type"]
    patients = df[patient_cols].drop_duplicates().sort_values(patient_cols).reset_index(drop=True)
    patients["patient_id"] = patients.index + 1
    t["dim_patient"] = pd.DataFrame({
        "patient_id": patients["patient_id"],
        "patient_name": patients["Name"],
        "gender_id": patients["Gender"].map(gender_ids),
        "blood_type_id": patients["Blood Type"].map(blood_ids),
    })

    fact = df.merge(patients, on=patient_cols, how="left")
    age_ids = key_map(t["dim_age_group"], "age_group_id", "age_group")

    def ids(dim, col, id_col, name_col):
        return fact[col].map(key_map(t[dim], id_col, name_col))

    t["fact_admission"] = pd.DataFrame({
        "admission_id": range(1, len(fact) + 1),
        "source_row": fact["Source Row"],
        "patient_id": fact["patient_id"],
        "doctor_id": ids("dim_doctor", "Doctor", "doctor_id", "doctor_name"),
        "hospital_id": ids("dim_hospital", "Hospital", "hospital_id", "hospital_name"),
        "insurance_provider_id": ids("dim_insurance_provider", "Insurance Provider", "insurance_provider_id", "insurance_provider"),
        "medical_condition_id": ids("dim_medical_condition", "Medical Condition", "medical_condition_id", "medical_condition"),
        "medication_id": ids("dim_medication", "Medication", "medication_id", "medication"),
        "admission_type_id": ids("dim_admission_type", "Admission Type", "admission_type_id", "admission_type"),
        "test_result_id": ids("dim_test_result", "Test Results", "test_result_id", "test_result"),
        "age_group_id": fact["Age Group"].map(age_ids),
        "admission_date_id": fact["Date of Admission"].dt.strftime("%Y%m%d").astype(int),
        "discharge_date_id": fact["Discharge Date"].dt.strftime("%Y%m%d").astype(int),
        "age_at_admission": fact["Age"],
        "room_number": fact["Room Number"],
        "length_of_stay_days": fact["Length of Stay"],
        "billing_amount": fact["Billing Amount"],
        "billing_per_day": fact["Billing Per Day"],
        "is_billing_adjustment": fact["Is Billing Adjustment"],
    })

    assert len(t["fact_admission"]) == len(df), "patient join changed the row count"
    assert t["fact_admission"].notna().all().all(), "fact row with an unmatched dimension key"
    return t


def main() -> None:
    df = pd.read_csv(CLEANED_DATA, parse_dates=["Date of Admission", "Discharge Date"])
    tables = build_tables(df)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name in SCHEMA_TABLES:
        table = tables[name]
        # Booleans as TRUE/FALSE so Snowflake's COPY INTO parses them directly.
        for col in table.select_dtypes(bool):
            table[col] = table[col].map({True: "TRUE", False: "FALSE"})
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False)
        print(f"{name:<24} {len(table):>7,} rows")
    print(f"wrote {len(SCHEMA_TABLES)} tables to {TABLES_DIR}")


if __name__ == "__main__":
    main()

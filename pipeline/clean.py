"""Clean the raw Kaggle CSV and write output/cleaned_healthcare.csv.

Steps (see README, "Data Quality and Preparation"):
  1. Drop the 534 exact duplicate rows.
  2. Standardize capitalization of patient names.
  3. Strip stray "and" / comma fragments from hospital names.
  4. Parse both date columns and derive length of stay.
  5. Flag (not drop) negative billing amounts as billing adjustments.
  6. Add age group for segmentation.

Run: python3 pipeline/clean.py
"""

import re

import pandas as pd

from config import AGE_BINS, AGE_LABELS, CLEANED_DATA, OUTPUT_DIR, RAW_DATA

# Name tokens that title case gets wrong ("Dds" -> "DDS", "Phd" -> "PhD").
NAME_FIXES = {
    "Dds": "DDS",
    "Dvm": "DVM",
    "Md": "MD",
    "Phd": "PhD",
    "Ii": "II",
    "Iii": "III",
    "Iv": "IV",
}


def clean_name(name: str) -> str:
    words = name.strip().title().split()
    return " ".join(NAME_FIXES.get(w, w) for w in words)


def clean_hospital(name: str) -> str:
    # Values look like "and Garcia Morris Cunningham," or "Sons Rich and":
    # fragments of a generated company name. Trim only the leading and
    # trailing fragments; internal commas ("Powers Miller, and Flores") stay.
    name = name.strip()
    name = re.sub(r"^and\s+", "", name)
    name = name.rstrip(", ").strip()
    name = re.sub(r",?\s+and$", "", name)
    return name.rstrip(", ").strip()


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_DATA)
    # Keep the original CSV line number (header is line 1) for traceability.
    df.insert(0, "Source Row", df.index + 2)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    data_cols = [c for c in df.columns if c != "Source Row"]
    df = df.drop_duplicates(subset=data_cols, keep="first").copy()

    df["Name"] = df["Name"].map(clean_name)
    df["Doctor"] = df["Doctor"].str.strip()
    df["Hospital"] = df["Hospital"].map(clean_hospital)

    df["Date of Admission"] = pd.to_datetime(df["Date of Admission"], format="%Y-%m-%d")
    df["Discharge Date"] = pd.to_datetime(df["Discharge Date"], format="%Y-%m-%d")
    df["Length of Stay"] = (df["Discharge Date"] - df["Date of Admission"]).dt.days

    df["Billing Amount"] = df["Billing Amount"].round(2)
    df["Is Billing Adjustment"] = df["Billing Amount"] < 0
    df["Billing Per Day"] = (df["Billing Amount"] / df["Length of Stay"]).round(2)

    df["Age Group"] = pd.cut(df["Age"], bins=AGE_BINS, labels=AGE_LABELS).astype(str)

    assert df.notna().all().all(), "cleaning introduced missing values"
    assert (df["Length of Stay"] >= 1).all(), "discharge before admission"
    return df.reset_index(drop=True)


def main() -> None:
    raw = load_raw()
    df = clean(raw)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEANED_DATA, index=False, date_format="%Y-%m-%d")

    print(f"raw rows:            {len(raw):,}")
    print(f"duplicates removed:  {len(raw) - len(df):,}")
    print(f"clean rows:          {len(df):,}")
    print(f"billing adjustments: {df['Is Billing Adjustment'].sum():,} (negative amounts, flagged)")
    print(f"distinct hospitals:  {raw['Hospital'].nunique():,} -> {df['Hospital'].nunique():,}")
    print(f"wrote {CLEANED_DATA}")


if __name__ == "__main__":
    main()

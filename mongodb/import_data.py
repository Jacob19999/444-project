"""Stage 1 (Extraction): load the 14 snowflake-schema CSVs into MongoDB.

Database: healthcare_snowflake (one collection per table)
Source:   output/tables/*.csv, written by pipeline/clean.py + pipeline/build_schema.py

Run: python3 mongodb/import_data.py
"""

from pathlib import Path

import pandas as pd
from pymongo import MongoClient

DATA_DIR = Path(__file__).resolve().parent.parent / "output" / "tables"
DB_NAME = "healthcare_snowflake"

client = MongoClient("mongodb://127.0.0.1:27017/")
db = client[DB_NAME]

for csv_path in sorted(DATA_DIR.glob("*.csv")):
    name = csv_path.stem  # e.g. fact_admission, dim_patient
    # pandas infers int/float so keys stay numbers and $lookup matches.
    # TRUE/FALSE columns (is_weekend, is_billing_adjustment) become booleans.
    df = pd.read_csv(csv_path)
    df = df.astype(object).where(df.notna(), None)

    db[name].drop()  # makes the script safe to re-run
    db[name].insert_many(df.to_dict("records"))
    print(f"{name:<24} {db[name].count_documents({}):>7,} docs")

# Indexes on the keys that $lookup searches (foreignField), so joins from the
# 54,966 fact documents stay fast.
db["dim_patient"].create_index("patient_id")
db["dim_gender"].create_index("gender_id")
db["dim_blood_type"].create_index("blood_type_id")
db["dim_date"].create_index("date_id")
db["dim_month"].create_index("month_id")

print("\ncollections:", sorted(db.list_collection_names()))
client.close()

"""Check the snowflake-schema tables and test the Snowflake SQL locally.

  1. Every CSV header matches its CREATE TABLE in sql/01_create_tables.sql
     (COPY INTO loads by column position, so order matters).
  2. Primary keys are unique and every foreign key resolves, which Snowflake
     itself does not enforce.
  3. The fact table rebuilds the cleaned dataset with no lost rows.
  4. Every query in sql/03_analysis_queries.sql runs, against a SQLite copy
     (output/healthcare_snowflake.db) with Snowflake's MEDIAN, STDDEV, and
     CORR added as custom aggregates.

Run: python3 pipeline/verify_local.py   (after pipeline/build_schema.py)
"""

import math
import re
import sqlite3
import statistics

import pandas as pd

from config import ANALYSIS_SQL, CLEANED_DATA, LOCAL_DB, SCHEMA_TABLES, SQL_DIR, TABLES_DIR


class Median:
    def __init__(self):
        self.values = []

    def step(self, value):
        if value is not None:
            self.values.append(value)

    def finalize(self):
        return statistics.median(self.values) if self.values else None


class Stddev(Median):
    def finalize(self):  # sample standard deviation, as in Snowflake
        return statistics.stdev(self.values) if len(self.values) > 1 else None


class Corr:
    def __init__(self):
        self.pairs = []

    def step(self, y, x):
        if x is not None and y is not None:
            self.pairs.append((x, y))

    def finalize(self):
        if len(self.pairs) < 2:
            return None
        xs, ys = zip(*self.pairs)
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        sxy = sum((x - mx) * (y - my) for x, y in self.pairs)
        sxx = sum((x - mx) ** 2 for x in xs)
        syy = sum((y - my) ** 2 for y in ys)
        return sxy / math.sqrt(sxx * syy)


def ddl_columns() -> dict[str, list[str]]:
    sql = (SQL_DIR / "01_create_tables.sql").read_text()
    tables = {}
    for name, body in re.findall(r"CREATE OR REPLACE TABLE (\w+) \((.*?)\n\);", sql, re.S):
        lines = [ln.split("--")[0].strip() for ln in body.strip().splitlines()]
        tables[name] = [ln.split()[0] for ln in lines if ln]
    return tables


def foreign_keys() -> list[tuple[str, str, str, str]]:
    """(child table, child column, parent table, parent column) from the DDL."""
    sql = (SQL_DIR / "01_create_tables.sql").read_text()
    fks = []
    for name, body in re.findall(r"CREATE OR REPLACE TABLE (\w+) \((.*?)\n\);", sql, re.S):
        for col, parent, pcol in re.findall(r"(\w+)\s+INTEGER.*?REFERENCES (\w+) \((\w+)\)", body):
            fks.append((name, col, parent, pcol))
    return fks


def load_tables() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in SCHEMA_TABLES:
        df = pd.read_csv(TABLES_DIR / f"{name}.csv", keep_default_na=False)
        for col in df.columns:
            if set(df[col].unique()) <= {"TRUE", "FALSE"}:
                df[col] = (df[col] == "TRUE").astype(int)
        tables[name] = df
    return tables


def check_schema(tables: dict[str, pd.DataFrame]) -> None:
    ddl = ddl_columns()
    assert set(ddl) == set(SCHEMA_TABLES), f"DDL tables differ: {set(ddl) ^ set(SCHEMA_TABLES)}"
    for name, df in tables.items():
        assert list(df.columns) == ddl[name], f"{name}: CSV columns {list(df.columns)} != DDL {ddl[name]}"
        pk = df.columns[0]
        assert df[pk].is_unique, f"{name}.{pk} has duplicate keys"
    print(f"ok  {len(tables)} CSV headers match the DDL; primary keys unique")

    fks = foreign_keys()
    for child, col, parent, pcol in fks:
        missing = ~tables[child][col].isin(tables[parent][pcol])
        assert not missing.any(), f"{child}.{col}: {missing.sum()} rows not in {parent}.{pcol}"
    print(f"ok  {len(fks)} foreign keys all resolve")


def check_round_trip(tables: dict[str, pd.DataFrame]) -> None:
    clean = pd.read_csv(CLEANED_DATA)
    fact = tables["fact_admission"]
    assert len(fact) == len(clean), "fact row count differs from cleaned data"
    joined = (
        fact.merge(tables["dim_patient"], on="patient_id")
        .merge(tables["dim_gender"], on="gender_id")
        .merge(tables["dim_medical_condition"], on="medical_condition_id")
        .merge(tables["dim_hospital"], on="hospital_id")
        .sort_values("source_row")
        .reset_index(drop=True)
    )
    clean = clean.sort_values("Source Row").reset_index(drop=True)
    assert (joined["patient_name"] == clean["Name"]).all()
    assert (joined["gender"] == clean["Gender"]).all()
    assert (joined["medical_condition"] == clean["Medical Condition"]).all()
    assert (joined["hospital_name"] == clean["Hospital"]).all()
    assert (joined["billing_amount"] == clean["Billing Amount"]).all()
    print(f"ok  fact table joins back to all {len(clean):,} cleaned rows")


def run_queries(tables: dict[str, pd.DataFrame]) -> None:
    LOCAL_DB.unlink(missing_ok=True)
    con = sqlite3.connect(LOCAL_DB)
    con.create_aggregate("MEDIAN", 1, Median)
    con.create_aggregate("STDDEV", 1, Stddev)
    con.create_aggregate("CORR", 2, Corr)
    for name, df in tables.items():
        df.to_sql(name, con, index=False)

    statements = [s.strip() for s in ANALYSIS_SQL.read_text().split(";") if s.strip()]
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    for stmt in statements:
        lines = stmt.splitlines()
        title = next((ln[3:] for ln in lines if re.match(r"-- Q\d", ln)), None)
        if title is None:  # USE SCHEMA and other Snowflake-only setup
            continue
        result = pd.read_sql_query(stmt, con)
        print(f"\n=== {title}  ({len(result)} rows)")
        print(result.head(12).to_string(index=False))
    con.close()
    print(f"\nok  all analysis queries ran; local database at {LOCAL_DB}")


def main() -> None:
    tables = load_tables()
    check_schema(tables)
    check_round_trip(tables)
    run_queries(tables)


if __name__ == "__main__":
    main()

-- Snowflake schema for the healthcare admissions dataset.
-- Run first, in a Snowflake worksheet or with SnowSQL.
--
-- One fact table (fact_admission, one row per admission) surrounded by
-- dimension tables. Two dimensions are normalized one level further
-- (that is what makes it a snowflake schema rather than a star):
--   dim_patient -> dim_gender, dim_blood_type
--   dim_date    -> dim_month
--
-- Column order must match the CSV files in output/tables/, which COPY INTO
-- loads by position. Snowflake records PRIMARY KEY / FOREIGN KEY constraints
-- but does not enforce them; pipeline/verify_local.py checks them instead.

CREATE DATABASE IF NOT EXISTS HEALTHCARE_DB;
CREATE SCHEMA IF NOT EXISTS HEALTHCARE_DB.ANALYTICS;
USE SCHEMA HEALTHCARE_DB.ANALYTICS;

-- Second-level (snowflaked) dimensions -------------------------------------

CREATE OR REPLACE TABLE dim_gender (
    gender_id               INTEGER       NOT NULL PRIMARY KEY,
    gender                  VARCHAR(10)   NOT NULL
);

CREATE OR REPLACE TABLE dim_blood_type (
    blood_type_id           INTEGER       NOT NULL PRIMARY KEY,
    blood_type              VARCHAR(3)    NOT NULL
);

CREATE OR REPLACE TABLE dim_month (
    month_id                INTEGER       NOT NULL PRIMARY KEY,  -- YYYYMM
    year                    INTEGER       NOT NULL,
    quarter                 INTEGER       NOT NULL,
    month_number            INTEGER       NOT NULL,
    month_name              VARCHAR(10)   NOT NULL,
    year_month              VARCHAR(7)    NOT NULL               -- 'YYYY-MM'
);

-- First-level dimensions ---------------------------------------------------

-- The source has no patient ID; a patient is cleaned name + gender + blood type.
CREATE OR REPLACE TABLE dim_patient (
    patient_id              INTEGER       NOT NULL PRIMARY KEY,
    patient_name            VARCHAR(100)  NOT NULL,
    gender_id               INTEGER       NOT NULL REFERENCES dim_gender (gender_id),
    blood_type_id           INTEGER       NOT NULL REFERENCES dim_blood_type (blood_type_id)
);

CREATE OR REPLACE TABLE dim_doctor (
    doctor_id               INTEGER       NOT NULL PRIMARY KEY,
    doctor_name             VARCHAR(100)  NOT NULL
);

CREATE OR REPLACE TABLE dim_hospital (
    hospital_id             INTEGER       NOT NULL PRIMARY KEY,
    hospital_name           VARCHAR(100)  NOT NULL
);

CREATE OR REPLACE TABLE dim_insurance_provider (
    insurance_provider_id   INTEGER       NOT NULL PRIMARY KEY,
    insurance_provider      VARCHAR(50)   NOT NULL
);

CREATE OR REPLACE TABLE dim_medical_condition (
    medical_condition_id    INTEGER       NOT NULL PRIMARY KEY,
    medical_condition       VARCHAR(50)   NOT NULL
);

CREATE OR REPLACE TABLE dim_medication (
    medication_id           INTEGER       NOT NULL PRIMARY KEY,
    medication              VARCHAR(50)   NOT NULL
);

CREATE OR REPLACE TABLE dim_admission_type (
    admission_type_id       INTEGER       NOT NULL PRIMARY KEY,
    admission_type          VARCHAR(20)   NOT NULL
);

CREATE OR REPLACE TABLE dim_test_result (
    test_result_id          INTEGER       NOT NULL PRIMARY KEY,
    test_result             VARCHAR(20)   NOT NULL
);

CREATE OR REPLACE TABLE dim_age_group (
    age_group_id            INTEGER       NOT NULL PRIMARY KEY,
    age_group               VARCHAR(10)   NOT NULL,
    min_age                 INTEGER       NOT NULL,
    max_age                 INTEGER       NOT NULL
);

CREATE OR REPLACE TABLE dim_date (
    date_id                 INTEGER       NOT NULL PRIMARY KEY,  -- YYYYMMDD
    full_date               DATE          NOT NULL,
    month_id                INTEGER       NOT NULL REFERENCES dim_month (month_id),
    day_of_month            INTEGER       NOT NULL,
    day_of_week             INTEGER       NOT NULL,              -- 1 = Monday
    day_name                VARCHAR(10)   NOT NULL,
    is_weekend              BOOLEAN       NOT NULL
);

-- Fact table ---------------------------------------------------------------

CREATE OR REPLACE TABLE fact_admission (
    admission_id            INTEGER       NOT NULL PRIMARY KEY,
    source_row              INTEGER       NOT NULL,              -- line in the raw CSV
    patient_id              INTEGER       NOT NULL REFERENCES dim_patient (patient_id),
    doctor_id               INTEGER       NOT NULL REFERENCES dim_doctor (doctor_id),
    hospital_id             INTEGER       NOT NULL REFERENCES dim_hospital (hospital_id),
    insurance_provider_id   INTEGER       NOT NULL REFERENCES dim_insurance_provider (insurance_provider_id),
    medical_condition_id    INTEGER       NOT NULL REFERENCES dim_medical_condition (medical_condition_id),
    medication_id           INTEGER       NOT NULL REFERENCES dim_medication (medication_id),
    admission_type_id       INTEGER       NOT NULL REFERENCES dim_admission_type (admission_type_id),
    test_result_id          INTEGER       NOT NULL REFERENCES dim_test_result (test_result_id),
    age_group_id            INTEGER       NOT NULL REFERENCES dim_age_group (age_group_id),
    admission_date_id       INTEGER       NOT NULL REFERENCES dim_date (date_id),
    discharge_date_id       INTEGER       NOT NULL REFERENCES dim_date (date_id),
    age_at_admission        INTEGER       NOT NULL,
    room_number             INTEGER       NOT NULL,
    length_of_stay_days     INTEGER       NOT NULL,              -- discharge - admission
    billing_amount          NUMBER(12, 2) NOT NULL,
    billing_per_day         NUMBER(12, 2) NOT NULL,              -- billing_amount / length_of_stay_days
    is_billing_adjustment   BOOLEAN       NOT NULL               -- TRUE when billing_amount < 0
);

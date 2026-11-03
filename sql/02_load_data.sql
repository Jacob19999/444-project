-- Load output/tables/*.csv into the tables from 01_create_tables.sql.
--
-- Step 1 needs SnowSQL or the Snowflake CLI (`snow sql -f ...`), run from
-- the repo root so the relative path resolves. In the Snowsight web UI, skip
-- step 1 and instead upload the 14 CSVs to HEALTHCARE_STAGE through
-- Data > Databases > HEALTHCARE_DB > ANALYTICS > Stages > + Files.
-- Steps 2-3 work either way: the patterns accept .csv and .csv.gz.

USE SCHEMA HEALTHCARE_DB.ANALYTICS;

CREATE OR REPLACE FILE FORMAT healthcare_csv
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"';  -- hospital names contain commas

CREATE OR REPLACE STAGE healthcare_stage
    FILE_FORMAT = healthcare_csv;

-- 1. Upload ---------------------------------------------------------------

PUT file://output/tables/*.csv @healthcare_stage AUTO_COMPRESS = TRUE OVERWRITE = TRUE;

-- 2. Copy, parents before children ----------------------------------------

COPY INTO dim_gender             FROM @healthcare_stage PATTERN = '.*dim_gender[.]csv([.]gz)?';
COPY INTO dim_blood_type         FROM @healthcare_stage PATTERN = '.*dim_blood_type[.]csv([.]gz)?';
COPY INTO dim_patient            FROM @healthcare_stage PATTERN = '.*dim_patient[.]csv([.]gz)?';
COPY INTO dim_doctor             FROM @healthcare_stage PATTERN = '.*dim_doctor[.]csv([.]gz)?';
COPY INTO dim_hospital           FROM @healthcare_stage PATTERN = '.*dim_hospital[.]csv([.]gz)?';
COPY INTO dim_insurance_provider FROM @healthcare_stage PATTERN = '.*dim_insurance_provider[.]csv([.]gz)?';
COPY INTO dim_medical_condition  FROM @healthcare_stage PATTERN = '.*dim_medical_condition[.]csv([.]gz)?';
COPY INTO dim_medication         FROM @healthcare_stage PATTERN = '.*dim_medication[.]csv([.]gz)?';
COPY INTO dim_admission_type     FROM @healthcare_stage PATTERN = '.*dim_admission_type[.]csv([.]gz)?';
COPY INTO dim_test_result        FROM @healthcare_stage PATTERN = '.*dim_test_result[.]csv([.]gz)?';
COPY INTO dim_age_group          FROM @healthcare_stage PATTERN = '.*dim_age_group[.]csv([.]gz)?';
COPY INTO dim_month              FROM @healthcare_stage PATTERN = '.*dim_month[.]csv([.]gz)?';
COPY INTO dim_date               FROM @healthcare_stage PATTERN = '.*dim_date[.]csv([.]gz)?';
COPY INTO fact_admission         FROM @healthcare_stage PATTERN = '.*fact_admission[.]csv([.]gz)?';

-- 3. Check row counts -----------------------------------------------------
-- Expected: fact_admission 54,966 | dim_patient 48,896 | dim_doctor 40,341
--           dim_hospital 39,635 | dim_date 1,857 | dim_month 62
--           and the small lookups 2 / 8 / 5 / 6 / 5 / 3 / 3 / 5.

SELECT 'fact_admission' AS table_name, COUNT(*) AS row_count FROM fact_admission
UNION ALL SELECT 'dim_patient',            COUNT(*) FROM dim_patient
UNION ALL SELECT 'dim_doctor',             COUNT(*) FROM dim_doctor
UNION ALL SELECT 'dim_hospital',           COUNT(*) FROM dim_hospital
UNION ALL SELECT 'dim_date',               COUNT(*) FROM dim_date
UNION ALL SELECT 'dim_month',              COUNT(*) FROM dim_month
UNION ALL SELECT 'dim_gender',             COUNT(*) FROM dim_gender
UNION ALL SELECT 'dim_blood_type',         COUNT(*) FROM dim_blood_type
UNION ALL SELECT 'dim_insurance_provider', COUNT(*) FROM dim_insurance_provider
UNION ALL SELECT 'dim_medical_condition',  COUNT(*) FROM dim_medical_condition
UNION ALL SELECT 'dim_medication',         COUNT(*) FROM dim_medication
UNION ALL SELECT 'dim_admission_type',     COUNT(*) FROM dim_admission_type
UNION ALL SELECT 'dim_test_result',        COUNT(*) FROM dim_test_result
UNION ALL SELECT 'dim_age_group',          COUNT(*) FROM dim_age_group;

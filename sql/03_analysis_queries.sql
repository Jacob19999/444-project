-- Analytical queries for the team's questions, written for Snowflake.
-- Run after 02_load_data.sql. pipeline/verify_local.py runs this same file
-- against a local SQLite copy, so each statement ends with ';' and starts
-- with a '-- Qn' comment line that names it.
--
-- Unless noted, queries exclude the 106 billing adjustments (negative
-- billing amounts) so refunds don't pull cost averages down.

USE SCHEMA HEALTHCARE_DB.ANALYTICS;

-- Q1a Is there a correlation between gender and type of disease?
-- Share of each gender's admissions that fall under each condition. If the
-- two are unrelated, every condition sits near 1/6 (16.7%) for both genders.
SELECT
    g.gender,
    mc.medical_condition,
    COUNT(*) AS admissions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY g.gender), 2) AS pct_of_gender
FROM fact_admission f
JOIN dim_patient p            ON p.patient_id = f.patient_id
JOIN dim_gender g             ON g.gender_id = p.gender_id
JOIN dim_medical_condition mc ON mc.medical_condition_id = f.medical_condition_id
GROUP BY g.gender, mc.medical_condition
ORDER BY g.gender, mc.medical_condition;

-- Q1b Is there a correlation between age and type of disease?
-- Condition mix within each age group, plus the average age per group.
SELECT
    ag.age_group,
    mc.medical_condition,
    COUNT(*) AS admissions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY ag.age_group), 2) AS pct_of_age_group,
    ROUND(AVG(f.age_at_admission), 1) AS avg_age
FROM fact_admission f
JOIN dim_age_group ag         ON ag.age_group_id = f.age_group_id
JOIN dim_medical_condition mc ON mc.medical_condition_id = f.medical_condition_id
GROUP BY ag.age_group_id, ag.age_group, mc.medical_condition
ORDER BY ag.age_group_id, mc.medical_condition;

-- Q2 What is the mean healthcare insurance provider discount?
-- The dataset has no discount, allowed-amount, or paid-amount column, so a
-- true discount cannot be computed. As a proxy, this compares each insurer's
-- mean bill with the mean across all insurers: a negative pct_vs_overall
-- means that insurer is billed less than average (an implied discount).
WITH clean AS (
    SELECT * FROM fact_admission WHERE NOT is_billing_adjustment
),
overall AS (
    SELECT AVG(billing_amount) AS overall_avg FROM clean
)
SELECT
    ip.insurance_provider,
    ROUND(AVG(c.billing_amount), 2) AS avg_billing,
    ROUND(o.overall_avg, 2) AS overall_avg_billing,
    ROUND(AVG(c.billing_amount) - o.overall_avg, 2) AS diff_vs_overall,
    ROUND(100.0 * (AVG(c.billing_amount) - o.overall_avg) / o.overall_avg, 2) AS pct_vs_overall
FROM clean c
JOIN dim_insurance_provider ip ON ip.insurance_provider_id = c.insurance_provider_id
CROSS JOIN overall o
GROUP BY ip.insurance_provider, o.overall_avg
ORDER BY pct_vs_overall;

-- Q3 Is there a correlation between medical condition and treatment length?
SELECT
    mc.medical_condition,
    COUNT(*) AS admissions,
    ROUND(AVG(f.length_of_stay_days), 2) AS avg_los_days,
    MEDIAN(f.length_of_stay_days) AS median_los_days,
    ROUND(STDDEV(f.length_of_stay_days), 2) AS stddev_los_days,
    MIN(f.length_of_stay_days) AS min_los_days,
    MAX(f.length_of_stay_days) AS max_los_days
FROM fact_admission f
JOIN dim_medical_condition mc ON mc.medical_condition_id = f.medical_condition_id
GROUP BY mc.medical_condition
ORDER BY avg_los_days DESC;

-- Q4 How does the billing amount compare across insurance companies?
SELECT
    ip.insurance_provider,
    COUNT(*) AS admissions,
    ROUND(SUM(f.billing_amount), 2) AS total_billing,
    ROUND(AVG(f.billing_amount), 2) AS avg_billing,
    ROUND(MEDIAN(f.billing_amount), 2) AS median_billing,
    ROUND(MIN(f.billing_amount), 2) AS min_billing,
    ROUND(MAX(f.billing_amount), 2) AS max_billing
FROM fact_admission f
JOIN dim_insurance_provider ip ON ip.insurance_provider_id = f.insurance_provider_id
WHERE NOT f.is_billing_adjustment
GROUP BY ip.insurance_provider
ORDER BY avg_billing DESC;

-- Q5 How does the billing rate (billing per day of stay) compare between
-- age and gender? Median is shown because 1-day stays make the mean jumpy.
SELECT
    ag.age_group,
    g.gender,
    COUNT(*) AS admissions,
    ROUND(AVG(f.billing_per_day), 2) AS avg_billing_per_day,
    ROUND(MEDIAN(f.billing_per_day), 2) AS median_billing_per_day,
    ROUND(AVG(f.length_of_stay_days), 2) AS avg_los_days
FROM fact_admission f
JOIN dim_age_group ag ON ag.age_group_id = f.age_group_id
JOIN dim_patient p    ON p.patient_id = f.patient_id
JOIN dim_gender g     ON g.gender_id = p.gender_id
WHERE NOT f.is_billing_adjustment
GROUP BY ag.age_group_id, ag.age_group, g.gender
ORDER BY ag.age_group_id, g.gender;

-- Q6 How long do patients stay, and does it vary by condition, age group,
-- or admission type? One row per group, stacked so the three breakdowns
-- can be compared side by side.
SELECT 'All patients' AS breakdown, 'All' AS grp, COUNT(*) AS admissions,
       ROUND(AVG(length_of_stay_days), 2) AS avg_los_days,
       MEDIAN(length_of_stay_days) AS median_los_days
FROM fact_admission
UNION ALL
SELECT 'Medical condition', mc.medical_condition, COUNT(*),
       ROUND(AVG(f.length_of_stay_days), 2), MEDIAN(f.length_of_stay_days)
FROM fact_admission f
JOIN dim_medical_condition mc ON mc.medical_condition_id = f.medical_condition_id
GROUP BY mc.medical_condition
UNION ALL
SELECT 'Age group', ag.age_group, COUNT(*),
       ROUND(AVG(f.length_of_stay_days), 2), MEDIAN(f.length_of_stay_days)
FROM fact_admission f
JOIN dim_age_group ag ON ag.age_group_id = f.age_group_id
GROUP BY ag.age_group
UNION ALL
SELECT 'Admission type', adt.admission_type, COUNT(*),
       ROUND(AVG(f.length_of_stay_days), 2), MEDIAN(f.length_of_stay_days)
FROM fact_admission f
JOIN dim_admission_type adt ON adt.admission_type_id = f.admission_type_id
GROUP BY adt.admission_type
ORDER BY breakdown, grp;

-- Q7 (extra) Is billing correlated with length of stay or age?
-- Pearson correlation: values near 0 mean no linear relationship.
SELECT
    ROUND(CORR(billing_amount, length_of_stay_days), 4) AS corr_billing_vs_los,
    ROUND(CORR(billing_amount, age_at_admission), 4) AS corr_billing_vs_age,
    ROUND(CORR(length_of_stay_days, age_at_admission), 4) AS corr_los_vs_age
FROM fact_admission
WHERE NOT is_billing_adjustment;

-- Q8 (extra) Monthly trend, walking the snowflake chain fact -> date -> month.
SELECT
    m.year_month,
    COUNT(*) AS admissions,
    ROUND(AVG(f.billing_amount), 2) AS avg_billing,
    ROUND(AVG(f.length_of_stay_days), 2) AS avg_los_days
FROM fact_admission f
JOIN dim_date d  ON d.date_id = f.admission_date_id
JOIN dim_month m ON m.month_id = d.month_id
WHERE NOT f.is_billing_adjustment
GROUP BY m.year_month
ORDER BY m.year_month;

-- Q9 (data quality) The flagged billing adjustments, by insurer and admission type.
SELECT
    ip.insurance_provider,
    adt.admission_type,
    COUNT(*) AS adjustments,
    ROUND(SUM(f.billing_amount), 2) AS total_adjustment,
    ROUND(MIN(f.billing_amount), 2) AS largest_adjustment
FROM fact_admission f
JOIN dim_insurance_provider ip ON ip.insurance_provider_id = f.insurance_provider_id
JOIN dim_admission_type adt     ON adt.admission_type_id = f.admission_type_id
WHERE f.is_billing_adjustment
GROUP BY ip.insurance_provider, adt.admission_type
ORDER BY adjustments DESC;

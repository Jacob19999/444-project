from pathlib import Path
import sys

from pymongo import MongoClient
import pandas as pd

import stats


client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["healthcare_snowflake"]

fact_admission = db["fact_admission"]

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
pd.set_option("display.width", 200)


def show(title, cursor, save=None):
    print(f"\n--- {title} ---")
    df = pd.DataFrame(list(cursor))
    if len(df) == 1 and len(df.columns) > 8:
        print(df.T.rename(columns={0: "value"}).rename_axis("field").to_string())
    else:
        print(df.to_string(index=False) if not df.empty else "(no results)")
    if save:
        df.to_csv(RESULTS_DIR / f"{save}.csv", index=False)
    return df


# Star schema lookups: spread into a pipeline with *LOOKUP_CONDITION.
# fact_admission -> dim_patient -> dim_gender
# fact_admission -> dim_patient -> dim_blood_type
# fact_admission -> dim_medical_condition / dim_insurance_provider /
#                   dim_admission_type / dim_test_result / dim_age_group /
#                   dim_medication
# fact_admission -> dim_date (admission_date_id) -> dim_month
LOOKUP_PATIENT = [
    {
        "$lookup": {
            "from": "dim_patient",
            "localField": "patient_id",
            "foreignField": "patient_id",
            "as": "patient",
        }
    },
    {"$unwind": "$patient"},
]

LOOKUP_GENDER = [
    {
        "$lookup": {
            "from": "dim_gender",
            "localField": "patient.gender_id",
            "foreignField": "gender_id",
            "as": "gender",
        }
    },
    {"$unwind": "$gender"},
]

LOOKUP_BLOOD_TYPE = [
    {
        "$lookup": {
            "from": "dim_blood_type",
            "localField": "patient.blood_type_id",
            "foreignField": "blood_type_id",
            "as": "blood",
        }
    },
    {"$unwind": "$blood"},
]

LOOKUP_CONDITION = [
    {
        "$lookup": {
            "from": "dim_medical_condition",
            "localField": "medical_condition_id",
            "foreignField": "medical_condition_id",
            "as": "condition",
        }
    },
    {"$unwind": "$condition"},
]

LOOKUP_INSURANCE = [
    {
        "$lookup": {
            "from": "dim_insurance_provider",
            "localField": "insurance_provider_id",
            "foreignField": "insurance_provider_id",
            "as": "insurer",
        }
    },
    {"$unwind": "$insurer"},
]

LOOKUP_ADMISSION_TYPE = [
    {
        "$lookup": {
            "from": "dim_admission_type",
            "localField": "admission_type_id",
            "foreignField": "admission_type_id",
            "as": "adm_type",
        }
    },
    {"$unwind": "$adm_type"},
]

LOOKUP_TEST_RESULT = [
    {
        "$lookup": {
            "from": "dim_test_result",
            "localField": "test_result_id",
            "foreignField": "test_result_id",
            "as": "test",
        }
    },
    {"$unwind": "$test"},
]

LOOKUP_AGE_GROUP = [
    {
        "$lookup": {
            "from": "dim_age_group",
            "localField": "age_group_id",
            "foreignField": "age_group_id",
            "as": "age_group",
        }
    },
    {"$unwind": "$age_group"},
]

LOOKUP_MEDICATION = [
    {
        "$lookup": {
            "from": "dim_medication",
            "localField": "medication_id",
            "foreignField": "medication_id",
            "as": "medication",
        }
    },
    {"$unwind": "$medication"},
]

LOOKUP_ADMIT_MONTH = [
    {
        "$lookup": {
            "from": "dim_date",
            "localField": "admission_date_id",
            "foreignField": "date_id",
            "as": "admit_date",
        }
    },
    {"$unwind": "$admit_date"},
    {
        "$lookup": {
            "from": "dim_month",
            "localField": "admit_date.month_id",
            "foreignField": "month_id",
            "as": "admit_month",
        }
    },
    {"$unwind": "$admit_month"},
]

VALID_BILLS = {"$match": {"is_billing_adjustment": False}}

LOS_BAND = {
    "$switch": {
        "branches": [
            {"case": {"$lte": ["$length_of_stay_days", 7]}, "then": "01-07 days"},
            {"case": {"$lte": ["$length_of_stay_days", 14]}, "then": "08-14 days"},
            {"case": {"$lte": ["$length_of_stay_days", 21]}, "then": "15-21 days"},
        ],
        "default": "22-30 days",
    }
}

def anova_sums(field):
    return {
        "n": {"$sum": 1},
        "sum_x": {"$sum": field},
        "sum_x2": {"$sum": {"$multiply": [field, field]}},
    }


def pearson_sums(x, y):
    return {
        "$group": {
            "_id": None,
            "n": {"$sum": 1},
            "sum_x": {"$sum": x},
            "sum_y": {"$sum": y},
            "sum_xy": {"$sum": {"$multiply": [x, y]}},
            "sum_x2": {"$sum": {"$multiply": [x, x]}},
            "sum_y2": {"$sum": {"$multiply": [y, y]}},
        }
    }


def stage1():
    show(
        "S1a collections and document counts",
        [
            {"collection": name, "documents": db[name].count_documents({})}
            for name in sorted(db.list_collection_names())
        ],
        save="s1a_collections",
    )

    show(
        "S1b one admission joined to all dimensions",
        fact_admission.aggregate(
            [
                {"$match": {"admission_id": 1}},
                *LOOKUP_PATIENT,
                *LOOKUP_GENDER,
                *LOOKUP_BLOOD_TYPE,
                *LOOKUP_CONDITION,
                *LOOKUP_INSURANCE,
                *LOOKUP_ADMISSION_TYPE,
                *LOOKUP_TEST_RESULT,
                *LOOKUP_AGE_GROUP,
                *LOOKUP_MEDICATION,
                *LOOKUP_ADMIT_MONTH,
                {
                    "$project": {
                        "_id": 0,
                        "admission_id": "$admission_id",
                        "patient": "$patient.patient_name",
                        "gender": "$gender.gender",
                        "blood_type": "$blood.blood_type",
                        "age": "$age_at_admission",
                        "age_group": "$age_group.age_group",
                        "condition": "$condition.medical_condition",
                        "admission_type": "$adm_type.admission_type",
                        "insurer": "$insurer.insurance_provider",
                        "medication": "$medication.medication",
                        "test_result": "$test.test_result",
                        "admitted": "$admit_date.full_date",
                        "year_month": "$admit_month.year_month",
                        "los_days": "$length_of_stay_days",
                        "billing_amount": "$billing_amount",
                        "billing_per_day": "$billing_per_day",
                    }
                },
            ]
        ),
        save="s1b_joined_admission",
    )


def stage2():
    show(
        "S2a duplicate source rows (expect 0)",
        list(
            fact_admission.aggregate(
                [
                    {"$group": {"_id": "$source_row", "copies": {"$sum": 1}}},
                    {"$match": {"copies": {"$gt": 1}}},
                    {"$count": "duplicate_rows"},
                ]
            )
        )
        or [{"duplicate_rows": 0}],
    )

    show(
        "S2b data quality summary",
        fact_admission.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "admissions": {"$sum": 1},
                        "missing_patient": {
                            "$sum": {"$cond": [{"$eq": [{"$ifNull": ["$patient_id", None]}, None]}, 1, 0]}
                        },
                        "missing_bill": {
                            "$sum": {"$cond": [{"$eq": [{"$ifNull": ["$billing_amount", None]}, None]}, 1, 0]}
                        },
                        "negative_bills": {"$sum": {"$cond": ["$is_billing_adjustment", 1, 0]}},
                        "discharge_before_admit": {
                            "$sum": {"$cond": [{"$lt": ["$discharge_date_id", "$admission_date_id"]}, 1, 0]}
                        },
                        "min_los": {"$min": "$length_of_stay_days"},
                        "max_los": {"$max": "$length_of_stay_days"},
                        "min_age": {"$min": "$age_at_admission"},
                        "max_age": {"$max": "$age_at_admission"},
                        "min_bill": {"$min": "$billing_amount"},
                        "max_bill": {"$max": "$billing_amount"},
                    }
                },
                {"$project": {"_id": 0}},
            ]
        ),
        save="s2b_quality",
    )

    show(
        "S2c fact rows with no matching patient (expect 0)",
        list(
            fact_admission.aggregate(
                [
                    {
                        "$lookup": {
                            "from": "dim_patient",
                            "localField": "patient_id",
                            "foreignField": "patient_id",
                            "as": "patient",
                        }
                    },
                    {"$match": {"patient": {"$size": 0}}},
                    {"$count": "orphans"},
                ]
            )
        )
        or [{"orphans": 0}],
    )

    show(
        "S2d billing adjustments (negative bills) by insurer",
        fact_admission.aggregate(
            [
                {"$match": {"is_billing_adjustment": True}},
                *LOOKUP_INSURANCE,
                {
                    "$group": {
                        "_id": "$insurer.insurance_provider",
                        "adjustments": {"$sum": 1},
                        "total_adjusted": {"$sum": "$billing_amount"},
                        "largest": {"$min": "$billing_amount"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "insurer": "$_id",
                        "adjustments": "$adjustments",
                        "total_adjusted": {"$round": ["$total_adjusted", 2]},
                        "largest": "$largest",
                    }
                },
                {"$sort": {"adjustments": -1}},
            ]
        ),
        save="s2d_adjustments",
    )


# Q1. Is there a correlation between gender and type of diseases?
def q1():
    q1a = show(
        "Q1a condition mix within each gender",
        fact_admission.aggregate(
            [
                *LOOKUP_PATIENT,
                *LOOKUP_GENDER,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": {"gender": "$gender.gender", "condition": "$condition.medical_condition"},
                        "admissions": {"$sum": 1},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "gender": "$_id.gender",
                        "condition": "$_id.condition",
                        "admissions": "$admissions",
                    }
                },
                {
                    "$setWindowFields": {
                        "partitionBy": "$gender",
                        "sortBy": {"admissions": -1},
                        "output": {
                            "gender_total": {
                                "$sum": "$admissions",
                                "window": {"documents": ["unbounded", "unbounded"]},
                            },
                            "rank_in_gender": {"$rank": {}},
                        },
                    }
                },
                {
                    "$set": {
                        "share_pct": {
                            "$round": [{"$multiply": [{"$divide": ["$admissions", "$gender_total"]}, 100]}, 2]
                        }
                    }
                },
                {"$sort": {"gender": 1, "rank_in_gender": 1}},
            ]
        ),
        save="q1a_gender_condition",
    )
    stats.print_chi_square("Q1 gender x condition", q1a, "gender", "condition", "admissions")

    show(
        "Q1b female vs male share of each condition (gap in percentage points)",
        fact_admission.aggregate(
            [
                *LOOKUP_PATIENT,
                *LOOKUP_GENDER,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": "$condition.medical_condition",
                        "female": {"$sum": {"$cond": [{"$eq": ["$gender.gender", "Female"]}, 1, 0]}},
                        "male": {"$sum": {"$cond": [{"$eq": ["$gender.gender", "Male"]}, 1, 0]}},
                    }
                },
                {
                    "$setWindowFields": {
                        "sortBy": {"_id": 1},
                        "output": {
                            "all_female": {"$sum": "$female", "window": {"documents": ["unbounded", "unbounded"]}},
                            "all_male": {"$sum": "$male", "window": {"documents": ["unbounded", "unbounded"]}},
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "condition": "$_id",
                        "female": "$female",
                        "male": "$male",
                        "female_pct": {"$round": [{"$multiply": [{"$divide": ["$female", "$all_female"]}, 100]}, 2]},
                        "male_pct": {"$round": [{"$multiply": [{"$divide": ["$male", "$all_male"]}, 100]}, 2]},
                    }
                },
                {"$set": {"gap_pts": {"$round": [{"$subtract": ["$female_pct", "$male_pct"]}, 2]}}},
                {"$sort": {"gap_pts": -1}},
            ]
        ),
        save="q1b_gender_gap",
    )

    show(
        "Q1c abnormal test rate by gender x condition",
        fact_admission.aggregate(
            [
                *LOOKUP_PATIENT,
                *LOOKUP_GENDER,
                *LOOKUP_CONDITION,
                *LOOKUP_TEST_RESULT,
                {
                    "$group": {
                        "_id": {"condition": "$condition.medical_condition", "gender": "$gender.gender"},
                        "admissions": {"$sum": 1},
                        "abnormal": {"$sum": {"$cond": [{"$eq": ["$test.test_result", "Abnormal"]}, 1, 0]}},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "condition": "$_id.condition",
                        "gender": "$_id.gender",
                        "admissions": "$admissions",
                        "abnormal_rate_pct": {
                            "$round": [{"$multiply": [{"$divide": ["$abnormal", "$admissions"]}, 100]}, 2]
                        },
                    }
                },
                {"$sort": {"condition": 1, "gender": 1}},
            ]
        ),
        save="q1c_gender_abnormal",
    )


# Q2. What is the mean healthcare insurance provider discount?
def q2():
    show(
        "Q2a insurer discount vs market average bill",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_INSURANCE,
                {
                    "$group": {
                        "_id": "$insurer.insurance_provider",
                        "admissions": {"$sum": 1},
                        "total_billed": {"$sum": "$billing_amount"},
                        "avg_bill_per_day": {"$avg": "$billing_per_day"},
                    }
                },
                {"$set": {"avg_bill": {"$divide": ["$total_billed", "$admissions"]}}},
                {
                    "$setWindowFields": {
                        "sortBy": {"avg_bill": 1},
                        "output": {
                            "market_billed": {"$sum": "$total_billed", "window": {"documents": ["unbounded", "unbounded"]}},
                            "market_admissions": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}},
                            "discount_rank": {"$rank": {}},
                        },
                    }
                },
                {"$set": {"market_avg": {"$divide": ["$market_billed", "$market_admissions"]}}},
                {
                    "$project": {
                        "_id": 0,
                        "discount_rank": "$discount_rank",
                        "insurer": "$_id",
                        "admissions": "$admissions",
                        "avg_bill": {"$round": ["$avg_bill", 2]},
                        "market_avg": {"$round": ["$market_avg", 2]},
                        "discount_usd": {"$round": [{"$subtract": ["$market_avg", "$avg_bill"]}, 2]},
                        "discount_pct": {
                            "$round": [
                                {"$multiply": [{"$divide": [{"$subtract": ["$market_avg", "$avg_bill"]}, "$market_avg"]}, 100]},
                                3,
                            ]
                        },
                        "avg_bill_per_day": {"$round": ["$avg_bill_per_day", 2]},
                    }
                },
                {"$sort": {"discount_rank": 1}},
            ]
        ),
        save="q2a_discount_raw",
    )

    q2b = show(
        "Q2b condition-adjusted discount per insurer",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_INSURANCE,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": {"insurer": "$insurer.insurance_provider", "condition": "$condition.medical_condition"},
                        "admissions": {"$sum": 1},
                        "total_billed": {"$sum": "$billing_amount"},
                    }
                },
                {
                    "$setWindowFields": {
                        "partitionBy": "$_id.condition",
                        "sortBy": {"total_billed": 1},
                        "output": {
                            "cond_billed": {"$sum": "$total_billed", "window": {"documents": ["unbounded", "unbounded"]}},
                            "cond_admissions": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}},
                        },
                    }
                },
                {
                    "$set": {
                        "avg_bill": {"$divide": ["$total_billed", "$admissions"]},
                        "cond_avg": {"$divide": ["$cond_billed", "$cond_admissions"]},
                    }
                },
                {
                    "$set": {
                        "discount_pct": {
                            "$multiply": [{"$divide": [{"$subtract": ["$cond_avg", "$avg_bill"]}, "$cond_avg"]}, 100]
                        }
                    }
                },
                {"$sort": {"discount_pct": -1}},
                {
                    "$group": {
                        "_id": "$_id.insurer",
                        "mean_discount_pct": {"$avg": "$discount_pct"},
                        "best_condition": {"$first": "$_id.condition"},
                        "best_discount_pct": {"$first": "$discount_pct"},
                        "worst_condition": {"$last": "$_id.condition"},
                        "worst_discount_pct": {"$last": "$discount_pct"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "insurer": "$_id",
                        "mean_discount_pct": {"$round": ["$mean_discount_pct", 3]},
                        "best_condition": "$best_condition",
                        "best_discount_pct": {"$round": ["$best_discount_pct", 2]},
                        "worst_condition": "$worst_condition",
                        "worst_discount_pct": {"$round": ["$worst_discount_pct", 2]},
                    }
                },
                {"$sort": {"mean_discount_pct": -1}},
            ]
        ),
        save="q2b_discount_adjusted",
    )

    show(
        "Q2c mean insurer discount (summary of Q2b)",
        [
            {
                "insurers": len(q2b),
                "mean_discount_pct": round(q2b["mean_discount_pct"].mean(), 3),
                "mean_abs_discount_pct": round(q2b["mean_discount_pct"].abs().mean(), 3),
                "best_vs_worst_spread_pts": round(q2b["mean_discount_pct"].max() - q2b["mean_discount_pct"].min(), 3),
            }
        ],
        save="q2c_discount_summary",
    )


# Q3. Is there a correlation between medical condition and treatment length?
def q3():
    q3a = show(
        "Q3a length of stay by condition",
        fact_admission.aggregate(
            [
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": "$condition.medical_condition",
                        **anova_sums("$length_of_stay_days"),
                        "min_los": {"$min": "$length_of_stay_days"},
                        "max_los": {"$max": "$length_of_stay_days"},
                        "long_stays": {"$sum": {"$cond": [{"$gte": ["$length_of_stay_days", 22]}, 1, 0]}},
                    }
                },
                {
                    "$project": {
                        "condition": "$_id",
                        "_id": 0,
                        "n": "$n",
                        "sum_x": "$sum_x",
                        "sum_x2": "$sum_x2",
                        "avg_los": {"$round": [{"$divide": ["$sum_x", "$n"]}, 3]},
                        "min_los": "$min_los",
                        "max_los": "$max_los",
                        "long_stay_pct": {"$round": [{"$multiply": [{"$divide": ["$long_stays", "$n"]}, 100]}, 2]},
                    }
                },
                {"$sort": {"avg_los": -1}},
            ]
        ),
        save="q3a_condition_los",
    )
    stats.print_anova("Q3 length of stay ~ condition", q3a, "condition")

    show(
        "Q3b avg length of stay by condition x test result",
        fact_admission.aggregate(
            [
                *LOOKUP_CONDITION,
                *LOOKUP_TEST_RESULT,
                {
                    "$group": {
                        "_id": "$condition.medical_condition",
                        "abnormal_los": {"$avg": {"$cond": [{"$eq": ["$test.test_result", "Abnormal"]}, "$length_of_stay_days", None]}},
                        "inconclusive_los": {"$avg": {"$cond": [{"$eq": ["$test.test_result", "Inconclusive"]}, "$length_of_stay_days", None]}},
                        "normal_los": {"$avg": {"$cond": [{"$eq": ["$test.test_result", "Normal"]}, "$length_of_stay_days", None]}},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "condition": "$_id",
                        "abnormal_los": {"$round": ["$abnormal_los", 2]},
                        "inconclusive_los": {"$round": ["$inconclusive_los", 2]},
                        "normal_los": {"$round": ["$normal_los", 2]},
                        "abnormal_minus_normal": {"$round": [{"$subtract": ["$abnormal_los", "$normal_los"]}, 2]},
                    }
                },
                {"$sort": {"abnormal_minus_normal": -1}},
            ]
        ),
        save="q3b_condition_test_los",
    )

    show(
        "Q3c bill per patient-day and avg bill by condition",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": "$condition.medical_condition",
                        "admissions": {"$sum": 1},
                        "total_billed": {"$sum": "$billing_amount"},
                        "patient_days": {"$sum": "$length_of_stay_days"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "condition": "$_id",
                        "admissions": "$admissions",
                        "avg_bill": {"$round": [{"$divide": ["$total_billed", "$admissions"]}, 2]},
                        "bill_per_patient_day": {"$round": [{"$divide": ["$total_billed", "$patient_days"]}, 2]},
                    }
                },
                {"$sort": {"avg_bill": -1}},
            ]
        ),
        save="q3c_condition_cost",
    )


# Q4. How does the billing amount compare across insurance companies and does one provide better rates than the others?
def q4():
    q4a = show(
        "Q4a billing by insurer (ranked cheapest average bill first)",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_INSURANCE,
                {
                    "$group": {
                        "_id": "$insurer.insurance_provider",
                        **anova_sums("$billing_amount"),
                        "patient_days": {"$sum": "$length_of_stay_days"},
                        "min_bill": {"$min": "$billing_amount"},
                        "max_bill": {"$max": "$billing_amount"},
                    }
                },
                {
                    "$setWindowFields": {
                        "sortBy": {"sum_x": -1},
                        "output": {
                            "all_billed": {"$sum": "$sum_x", "window": {"documents": ["unbounded", "unbounded"]}},
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "insurer": "$_id",
                        "n": "$n",
                        "sum_x": "$sum_x",
                        "sum_x2": "$sum_x2",
                        "total_billed": {"$round": ["$sum_x", 0]},
                        "share_of_billing_pct": {"$round": [{"$multiply": [{"$divide": ["$sum_x", "$all_billed"]}, 100]}, 2]},
                        "avg_bill": {"$round": [{"$divide": ["$sum_x", "$n"]}, 2]},
                        "bill_per_patient_day": {"$round": [{"$divide": ["$sum_x", "$patient_days"]}, 2]},
                        "min_bill": "$min_bill",
                        "max_bill": "$max_bill",
                    }
                },
                {"$setWindowFields": {"sortBy": {"avg_bill": 1}, "output": {"rate_rank": {"$rank": {}}}}},
                {"$sort": {"rate_rank": 1}},
            ]
        ),
        save="q4a_insurer_billing",
    )
    stats.print_anova("Q4 billing amount ~ insurer", q4a, "insurer")

    show(
        "Q4b average bill by insurer and year",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_INSURANCE,
                *LOOKUP_ADMIT_MONTH,
                {"$match": {"admit_month.year": {"$gte": 2020, "$lte": 2023}}},
                {
                    "$group": {
                        "_id": {"insurer": "$insurer.insurance_provider", "year": "$admit_month.year"},
                        "admissions": {"$sum": 1},
                        "avg_bill": {"$avg": "$billing_amount"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "insurer": "$_id.insurer",
                        "year": "$_id.year",
                        "admissions": "$admissions",
                        "avg_bill": {"$round": ["$avg_bill", 2]},
                    }
                },
                {
                    "$setWindowFields": {
                        "partitionBy": "$insurer",
                        "sortBy": {"year": 1},
                        "output": {"prev_avg": {"$shift": {"output": "$avg_bill", "by": -1}}},
                    }
                },
                {
                    "$set": {
                        "yoy_change_pct": {
                            "$cond": [
                                {"$eq": ["$prev_avg", None]},
                                None,
                                {"$round": [{"$multiply": [{"$divide": [{"$subtract": ["$avg_bill", "$prev_avg"]}, "$prev_avg"]}, 100]}, 2]},
                            ]
                        }
                    }
                },
                {"$project": {"prev_avg": 0}},
                {"$sort": {"insurer": 1, "year": 1}},
            ]
        ),
        save="q4b_insurer_year",
    )

    show(
        "Q4c cheapest and dearest insurer for each medication",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_INSURANCE,
                *LOOKUP_MEDICATION,
                {
                    "$group": {
                        "_id": {"medication": "$medication.medication", "insurer": "$insurer.insurance_provider"},
                        "avg_bill": {"$avg": "$billing_amount"},
                    }
                },
                {"$sort": {"_id.medication": 1, "avg_bill": 1}},
                {
                    "$group": {
                        "_id": "$_id.medication",
                        "cheapest_insurer": {"$first": "$_id.insurer"},
                        "cheapest_avg": {"$first": "$avg_bill"},
                        "dearest_insurer": {"$last": "$_id.insurer"},
                        "dearest_avg": {"$last": "$avg_bill"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "medication": "$_id",
                        "cheapest_insurer": "$cheapest_insurer",
                        "cheapest_avg": {"$round": ["$cheapest_avg", 2]},
                        "dearest_insurer": "$dearest_insurer",
                        "dearest_avg": {"$round": ["$dearest_avg", 2]},
                        "spread_pct": {
                            "$round": [
                                {"$multiply": [{"$divide": [{"$subtract": ["$dearest_avg", "$cheapest_avg"]}, "$cheapest_avg"]}, 100]},
                                2,
                            ]
                        },
                    }
                },
                {"$sort": {"spread_pct": -1}},
            ]
        ),
        save="q4c_insurer_medication",
    )


# Q5. How does the billing rate, based on length of hospital stay, compare between age and gender?
def q5():
    show(
        "Q5a billing rate by age group x gender",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_AGE_GROUP,
                *LOOKUP_PATIENT,
                *LOOKUP_GENDER,
                {
                    "$group": {
                        "_id": {"age_group": "$age_group.age_group", "gender": "$gender.gender"},
                        "admissions": {"$sum": 1},
                        "total_billed": {"$sum": "$billing_amount"},
                        "patient_days": {"$sum": "$length_of_stay_days"},
                        "avg_daily_rate": {"$avg": "$billing_per_day"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "age_group": "$_id.age_group",
                        "gender": "$_id.gender",
                        "admissions": "$admissions",
                        "avg_bill": {"$round": [{"$divide": ["$total_billed", "$admissions"]}, 2]},
                        "avg_los": {"$round": [{"$divide": ["$patient_days", "$admissions"]}, 2]},
                        "bill_per_patient_day": {"$round": [{"$divide": ["$total_billed", "$patient_days"]}, 2]},
                        "avg_daily_rate": {"$round": ["$avg_daily_rate", 2]},
                    }
                },
                {"$sort": {"age_group": 1, "gender": 1}},
            ]
        ),
        save="q5a_age_gender_rate",
    )

    show(
        "Q5b billing rate by length-of-stay band x gender",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                *LOOKUP_PATIENT,
                *LOOKUP_GENDER,
                {"$set": {"los_band": LOS_BAND}},
                {
                    "$group": {
                        "_id": {"los_band": "$los_band", "gender": "$gender.gender"},
                        "admissions": {"$sum": 1},
                        "avg_bill": {"$avg": "$billing_amount"},
                        "avg_daily_rate": {"$avg": "$billing_per_day"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "los_band": "$_id.los_band",
                        "gender": "$_id.gender",
                        "admissions": "$admissions",
                        "avg_bill": {"$round": ["$avg_bill", 2]},
                        "avg_daily_rate": {"$round": ["$avg_daily_rate", 2]},
                    }
                },
                {"$sort": {"los_band": 1, "gender": 1}},
            ]
        ),
        save="q5b_los_band_rate",
    )

    pairs = [
        ("length of stay vs billing amount", "$length_of_stay_days", "$billing_amount"),
        ("length of stay vs billing per day", "$length_of_stay_days", "$billing_per_day"),
        ("age vs billing per day", "$age_at_admission", "$billing_per_day"),
        ("age vs billing amount", "$age_at_admission", "$billing_amount"),
    ]
    rows = []
    for label, x, y in pairs:
        sums = list(fact_admission.aggregate([VALID_BILLS, pearson_sums(x, y)]))[0]
        rows.append({"pair": label, **stats.pearson(sums)})
    show("Q5c Pearson correlations", rows, save="q5c_correlations")


# Q6. How long do patients stay, and does that vary by condition or admission type?
def q6():
    show(
        "Q6a length-of-stay distribution",
        fact_admission.aggregate(
            [
                {"$set": {"los_band": LOS_BAND}},
                {
                    "$group": {
                        "_id": "$los_band",
                        "admissions": {"$sum": 1},
                        "avg_los": {"$avg": "$length_of_stay_days"},
                    }
                },
                {
                    "$setWindowFields": {
                        "sortBy": {"_id": 1},
                        "output": {
                            "all": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}},
                            "running": {"$sum": "$admissions", "window": {"documents": ["unbounded", "current"]}},
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "los_band": "$_id",
                        "admissions": "$admissions",
                        "avg_los": {"$round": ["$avg_los", 2]},
                        "share_pct": {"$round": [{"$multiply": [{"$divide": ["$admissions", "$all"]}, 100]}, 2]},
                        "cumulative_pct": {"$round": [{"$multiply": [{"$divide": ["$running", "$all"]}, 100]}, 2]},
                    }
                },
            ]
        ),
        save="q6a_los_distribution",
    )

    show(
        "Q6a2 admissions for each length of stay (1-30 days)",
        fact_admission.aggregate(
            [
                {"$group": {"_id": "$length_of_stay_days", "admissions": {"$sum": 1}}},
                {"$project": {"_id": 0, "los_days": "$_id", "admissions": "$admissions"}},
                {"$sort": {"los_days": 1}},
            ]
        ),
        save="q6a2_los_histogram",
    )

    show(
        "Q6b overall length of stay",
        fact_admission.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "admissions": {"$sum": 1},
                        "avg_los": {"$avg": "$length_of_stay_days"},
                        "min_los": {"$min": "$length_of_stay_days"},
                        "max_los": {"$max": "$length_of_stay_days"},
                        "patient_days": {"$sum": "$length_of_stay_days"},
                    }
                },
                {"$project": {"_id": 0, "admissions": "$admissions", "avg_los": {"$round": ["$avg_los", 3]}, "min_los": "$min_los", "max_los": "$max_los", "patient_days": "$patient_days"}},
            ]
        ),
        save="q6b_los_overall",
    )

    q6c = show(
        "Q6c length of stay by admission type",
        fact_admission.aggregate(
            [
                *LOOKUP_ADMISSION_TYPE,
                {"$group": {"_id": "$adm_type.admission_type", **anova_sums("$length_of_stay_days")}},
                {
                    "$project": {
                        "_id": 0,
                        "admission_type": "$_id",
                        "n": "$n",
                        "sum_x": "$sum_x",
                        "sum_x2": "$sum_x2",
                        "avg_los": {"$round": [{"$divide": ["$sum_x", "$n"]}, 3]},
                    }
                },
                {"$sort": {"avg_los": -1}},
            ]
        ),
        save="q6c_admission_type_los",
    )
    stats.print_anova("Q6 length of stay ~ admission type", q6c, "admission_type")

    show(
        "Q6d length of stay by condition x admission type (ranked)",
        fact_admission.aggregate(
            [
                *LOOKUP_CONDITION,
                *LOOKUP_ADMISSION_TYPE,
                {
                    "$group": {
                        "_id": {"condition": "$condition.medical_condition", "admission_type": "$adm_type.admission_type"},
                        "admissions": {"$sum": 1},
                        "patient_days": {"$sum": "$length_of_stay_days"},
                    }
                },
                {"$set": {"avg_los": {"$divide": ["$patient_days", "$admissions"]}}},
                {
                    "$setWindowFields": {
                        "sortBy": {"avg_los": -1},
                        "output": {
                            "all_days": {"$sum": "$patient_days", "window": {"documents": ["unbounded", "unbounded"]}},
                            "all_adm": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}},
                            "rank": {"$rank": {}},
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "rank": "$rank",
                        "condition": "$_id.condition",
                        "admission_type": "$_id.admission_type",
                        "admissions": "$admissions",
                        "avg_los": {"$round": ["$avg_los", 2]},
                        "vs_overall_days": {"$round": [{"$subtract": ["$avg_los", {"$divide": ["$all_days", "$all_adm"]}]}, 2]},
                    }
                },
                {"$sort": {"rank": 1}},
            ]
        ),
        save="q6d_condition_type_los",
    )


# Q7. Is there a correlation between age and type of diseases?
def q7():
    q7a = show(
        "Q7a condition mix within each age group",
        fact_admission.aggregate(
            [
                *LOOKUP_AGE_GROUP,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": {"age_group": "$age_group.age_group", "condition": "$condition.medical_condition"},
                        "admissions": {"$sum": 1},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "age_group": "$_id.age_group",
                        "condition": "$_id.condition",
                        "admissions": "$admissions",
                    }
                },
                {
                    "$setWindowFields": {
                        "partitionBy": "$age_group",
                        "sortBy": {"admissions": -1},
                        "output": {
                            "group_total": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}},
                            "rank_in_group": {"$rank": {}},
                        },
                    }
                },
                {"$set": {"share_pct": {"$round": [{"$multiply": [{"$divide": ["$admissions", "$group_total"]}, 100]}, 2]}}},
                {"$sort": {"age_group": 1, "rank_in_group": 1}},
            ]
        ),
        save="q7a_age_condition",
    )
    stats.print_chi_square("Q7 age group x condition", q7a, "age_group", "condition", "admissions")

    q7b = show(
        "Q7b age profile of each condition",
        fact_admission.aggregate(
            [
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": "$condition.medical_condition",
                        **anova_sums("$age_at_admission"),
                        "min_age": {"$min": "$age_at_admission"},
                        "max_age": {"$max": "$age_at_admission"},
                        "seniors": {"$sum": {"$cond": [{"$gte": ["$age_at_admission", 65]}, 1, 0]}},
                        "under_35": {"$sum": {"$cond": [{"$lt": ["$age_at_admission", 35]}, 1, 0]}},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "condition": "$_id",
                        "n": "$n",
                        "sum_x": "$sum_x",
                        "sum_x2": "$sum_x2",
                        "avg_age": {"$round": [{"$divide": ["$sum_x", "$n"]}, 2]},
                        "min_age": "$min_age",
                        "max_age": "$max_age",
                        "seniors_pct": {"$round": [{"$multiply": [{"$divide": ["$seniors", "$n"]}, 100]}, 2]},
                        "under_35_pct": {"$round": [{"$multiply": [{"$divide": ["$under_35", "$n"]}, 100]}, 2]},
                    }
                },
                {"$sort": {"avg_age": -1}},
            ]
        ),
        save="q7b_condition_age",
    )
    stats.print_anova("Q7 age ~ condition", q7b, "condition")


# Q8. Does the age group have an effect on the duration of the patient's stay?
def q8():
    q8a = show(
        "Q8a length of stay by age group",
        fact_admission.aggregate(
            [
                *LOOKUP_AGE_GROUP,
                {
                    "$group": {
                        "_id": {"age_group": "$age_group.age_group", "min_age": "$age_group.min_age", "max_age": "$age_group.max_age"},
                        **anova_sums("$length_of_stay_days"),
                        "long_stays": {"$sum": {"$cond": [{"$gte": ["$length_of_stay_days", 22]}, 1, 0]}},
                        "short_stays": {"$sum": {"$cond": [{"$lte": ["$length_of_stay_days", 7]}, 1, 0]}},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "age_group": "$_id.age_group",
                        "min_age": "$_id.min_age",
                        "max_age": "$_id.max_age",
                        "n": "$n",
                        "sum_x": "$sum_x",
                        "sum_x2": "$sum_x2",
                        "avg_los": {"$round": [{"$divide": ["$sum_x", "$n"]}, 3]},
                        "short_stay_pct": {"$round": [{"$multiply": [{"$divide": ["$short_stays", "$n"]}, 100]}, 2]},
                        "long_stay_pct": {"$round": [{"$multiply": [{"$divide": ["$long_stays", "$n"]}, 100]}, 2]},
                    }
                },
                {"$sort": {"min_age": 1}},
            ]
        ),
        save="q8a_age_group_los",
    )
    stats.print_anova("Q8 length of stay ~ age group", q8a, "age_group")

    show(
        "Q8b average length of stay by single year of age",
        fact_admission.aggregate(
            [
                {
                    "$group": {
                        "_id": "$age_at_admission",
                        "admissions": {"$sum": 1},
                        "avg_los": {"$avg": "$length_of_stay_days"},
                    }
                },
                {"$project": {"_id": 0, "age": "$_id", "admissions": "$admissions", "avg_los": {"$round": ["$avg_los", 3]}}},
                {"$sort": {"age": 1}},
            ]
        ),
        save="q8b_age_los",
    )

    sums = list(fact_admission.aggregate([pearson_sums("$age_at_admission", "$length_of_stay_days")]))[0]
    show("Q8c Pearson correlation age vs length of stay", [{"pair": "age vs length of stay", **stats.pearson(sums)}], save="q8c_correlation")


# Q9. Does the blood type of the individual cause a longer stay or have a higher rate of a certain condition?
def q9():
    q9a = show(
        "Q9a length of stay by blood type (ranked)",
        fact_admission.aggregate(
            [
                *LOOKUP_PATIENT,
                *LOOKUP_BLOOD_TYPE,
                {"$group": {"_id": "$blood.blood_type", **anova_sums("$length_of_stay_days")}},
                {"$set": {"avg_los": {"$divide": ["$sum_x", "$n"]}}},
                {"$setWindowFields": {"sortBy": {"avg_los": -1}, "output": {"rank": {"$rank": {}}}}},
                {
                    "$project": {
                        "_id": 0,
                        "rank": "$rank",
                        "blood_type": "$_id",
                        "n": "$n",
                        "sum_x": "$sum_x",
                        "sum_x2": "$sum_x2",
                        "avg_los": {"$round": ["$avg_los", 3]},
                    }
                },
            ]
        ),
        save="q9a_blood_los",
    )
    stats.print_anova("Q9 length of stay ~ blood type", q9a, "blood_type")

    q9b = show(
        "Q9b condition rate within each blood type",
        fact_admission.aggregate(
            [
                *LOOKUP_PATIENT,
                *LOOKUP_BLOOD_TYPE,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": {"blood_type": "$blood.blood_type", "condition": "$condition.medical_condition"},
                        "admissions": {"$sum": 1},
                    }
                },
                {"$project": {"_id": 0, "blood_type": "$_id.blood_type", "condition": "$_id.condition", "admissions": "$admissions"}},
                {
                    "$setWindowFields": {
                        "partitionBy": "$blood_type",
                        "sortBy": {"admissions": -1},
                        "output": {"blood_total": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}}},
                    }
                },
                {"$set": {"rate_pct": {"$round": [{"$multiply": [{"$divide": ["$admissions", "$blood_total"]}, 100]}, 2]}}},
                {"$sort": {"blood_type": 1, "condition": 1}},
            ]
        ),
        save="q9b_blood_condition",
    )
    stats.print_chi_square("Q9 blood type x condition", q9b, "blood_type", "condition", "admissions")

    show(
        "Q9c most common condition per blood type vs dataset rate",
        fact_admission.aggregate(
            [
                *LOOKUP_PATIENT,
                *LOOKUP_BLOOD_TYPE,
                *LOOKUP_CONDITION,
                {
                    "$group": {
                        "_id": {"blood_type": "$blood.blood_type", "condition": "$condition.medical_condition"},
                        "admissions": {"$sum": 1},
                    }
                },
                {
                    "$setWindowFields": {
                        "partitionBy": "$_id.blood_type",
                        "sortBy": {"admissions": -1},
                        "output": {"blood_total": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}}},
                    }
                },
                {
                    "$setWindowFields": {
                        "partitionBy": "$_id.condition",
                        "sortBy": {"admissions": -1},
                        "output": {"cond_total": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}}},
                    }
                },
                {
                    "$setWindowFields": {
                        "sortBy": {"admissions": -1},
                        "output": {"grand_total": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}}},
                    }
                },
                {
                    "$set": {
                        "rate_pct": {"$multiply": [{"$divide": ["$admissions", "$blood_total"]}, 100]},
                        "dataset_pct": {"$multiply": [{"$divide": ["$cond_total", "$grand_total"]}, 100]},
                    }
                },
                {"$sort": {"_id.blood_type": 1, "rate_pct": -1}},
                {
                    "$group": {
                        "_id": "$_id.blood_type",
                        "top_condition": {"$first": "$_id.condition"},
                        "rate_pct": {"$first": "$rate_pct"},
                        "dataset_pct": {"$first": "$dataset_pct"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "blood_type": "$_id",
                        "top_condition": "$top_condition",
                        "rate_pct": {"$round": ["$rate_pct", 2]},
                        "dataset_pct": {"$round": ["$dataset_pct", 2]},
                        "lift_pts": {"$round": [{"$subtract": ["$rate_pct", "$dataset_pct"]}, 2]},
                    }
                },
                {"$sort": {"lift_pts": -1}},
            ]
        ),
        save="q9c_blood_top_condition",
    )


# Q10. Does the admission type correlate with the type of condition the patient has, and are there any outliers in the data?
def q10():
    q10a = show(
        "Q10a admission type mix within each condition",
        fact_admission.aggregate(
            [
                *LOOKUP_CONDITION,
                *LOOKUP_ADMISSION_TYPE,
                {
                    "$group": {
                        "_id": {"condition": "$condition.medical_condition", "admission_type": "$adm_type.admission_type"},
                        "admissions": {"$sum": 1},
                    }
                },
                {"$project": {"_id": 0, "condition": "$_id.condition", "admission_type": "$_id.admission_type", "admissions": "$admissions"}},
                {
                    "$setWindowFields": {
                        "partitionBy": "$condition",
                        "sortBy": {"admissions": -1},
                        "output": {"cond_total": {"$sum": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}}},
                    }
                },
                {"$set": {"share_pct": {"$round": [{"$multiply": [{"$divide": ["$admissions", "$cond_total"]}, 100]}, 2]}}},
                {"$sort": {"condition": 1, "admission_type": 1}},
            ]
        ),
        save="q10a_condition_admission_type",
    )
    result = stats.print_chi_square("Q10 condition x admission type", q10a, "condition", "admission_type", "admissions")
    residuals = result["residuals"].stack().rename("std_residual").reset_index()
    residuals["std_residual"] = residuals["std_residual"].round(2)
    residuals["abs"] = residuals["std_residual"].abs()
    show(
        "Q10b largest standardized residuals (|r| > 2 would be a notable cell)",
        residuals.sort_values("abs", ascending=False).drop(columns="abs").head(6).to_dict("records"),
        save="q10b_residuals",
    )

    s = list(fact_admission.aggregate([VALID_BILLS, {"$group": {"_id": None, **anova_sums("$billing_amount")}}]))[0]
    mean = s["sum_x"] / s["n"]
    sd = ((s["sum_x2"] - s["n"] * mean**2) / (s["n"] - 1)) ** 0.5
    low_fence, high_fence = mean - 2 * sd, mean + 2 * sd
    print(f"\nbilling mean = {mean:,.2f}, sd = {sd:,.2f}, 2-sd fences = [{low_fence:,.2f}, {high_fence:,.2f}]")

    show(
        "Q10c billing outliers by admission type",
        fact_admission.aggregate(
            [
                *LOOKUP_ADMISSION_TYPE,
                {
                    "$group": {
                        "_id": "$adm_type.admission_type",
                        "admissions": {"$sum": 1},
                        "negative_bills": {"$sum": {"$cond": ["$is_billing_adjustment", 1, 0]}},
                        "below_2sd": {"$sum": {"$cond": [{"$lt": ["$billing_amount", low_fence]}, 1, 0]}},
                        "above_2sd": {"$sum": {"$cond": [{"$gt": ["$billing_amount", high_fence]}, 1, 0]}},
                        "one_day_stays": {"$sum": {"$cond": [{"$eq": ["$length_of_stay_days", 1]}, 1, 0]}},
                        "max_bill_per_day": {"$max": "$billing_per_day"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "admission_type": "$_id",
                        "admissions": "$admissions",
                        "negative_bills": "$negative_bills",
                        "below_2sd": "$below_2sd",
                        "above_2sd": "$above_2sd",
                        "negative_per_1000": {"$round": [{"$multiply": [{"$divide": ["$negative_bills", "$admissions"]}, 1000]}, 2]},
                        "one_day_stays": "$one_day_stays",
                        "max_bill_per_day": "$max_bill_per_day",
                    }
                },
                {"$sort": {"admission_type": 1}},
            ]
        ),
        save="q10c_outliers",
    )

    show(
        "Q10c2 billing amount distribution ($2,500 buckets)",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                {"$set": {"bucket": {"$multiply": [{"$toInt": {"$divide": ["$billing_amount", 2500]}}, 2500]}}},
                {"$group": {"_id": "$bucket", "admissions": {"$sum": 1}}},
                {"$project": {"_id": 0, "bucket_start": "$_id", "admissions": "$admissions"}},
                {"$sort": {"bucket_start": 1}},
            ]
        ),
        save="q10c2_bill_histogram",
    )

    show(
        "Q10d top 10 admissions by billing per day",
        fact_admission.aggregate(
            [
                VALID_BILLS,
                {"$sort": {"billing_per_day": -1}},
                {"$limit": 10},
                *LOOKUP_CONDITION,
                *LOOKUP_ADMISSION_TYPE,
                *LOOKUP_INSURANCE,
                {
                    "$project": {
                        "_id": 0,
                        "admission_id": "$admission_id",
                        "condition": "$condition.medical_condition",
                        "admission_type": "$adm_type.admission_type",
                        "insurer": "$insurer.insurance_provider",
                        "los_days": "$length_of_stay_days",
                        "billing_amount": "$billing_amount",
                        "billing_per_day": "$billing_per_day",
                    }
                },
            ]
        ),
        save="q10d_top_daily_rate",
    )

    near_dups = show(
        "Q10d2 near-duplicate admissions (identical except age)",
        fact_admission.aggregate(
            [
                {
                    "$group": {
                        "_id": {
                            "patient": "$patient_id",
                            "doctor": "$doctor_id",
                            "hospital": "$hospital_id",
                            "insurer": "$insurance_provider_id",
                            "condition": "$medical_condition_id",
                            "medication": "$medication_id",
                            "type": "$admission_type_id",
                            "test": "$test_result_id",
                            "admitted": "$admission_date_id",
                            "discharged": "$discharge_date_id",
                            "room": "$room_number",
                            "bill": "$billing_amount",
                        },
                        "copies": {"$sum": 1},
                        "min_age": {"$min": "$age_at_admission"},
                        "max_age": {"$max": "$age_at_admission"},
                    }
                },
                {"$match": {"copies": {"$gt": 1}}},
                {"$set": {"age_gap": {"$subtract": ["$max_age", "$min_age"]}}},
                {
                    "$group": {
                        "_id": "$age_gap",
                        "record_groups": {"$sum": 1},
                        "extra_copies": {"$sum": {"$subtract": ["$copies", 1]}},
                    }
                },
                {"$project": {"_id": 0, "age_gap_years": "$_id", "record_groups": "$record_groups", "extra_copies": "$extra_copies"}},
                {"$sort": {"age_gap_years": 1}},
            ]
        ),
        save="q10d2_near_duplicates",
    )
    print(f"\ntotal extra copies: {near_dups['extra_copies'].sum():,} of {fact_admission.count_documents({}):,} admissions")

    show(
        "Q10e monthly admissions by type: busiest and quietest months",
        fact_admission.aggregate(
            [
                *LOOKUP_ADMISSION_TYPE,
                *LOOKUP_ADMIT_MONTH,
                {"$match": {"admit_month.year": {"$gte": 2020, "$lte": 2023}}},
                {
                    "$group": {
                        "_id": "$admit_month.year_month",
                        "admissions": {"$sum": 1},
                        "emergency": {"$sum": {"$cond": [{"$eq": ["$adm_type.admission_type", "Emergency"]}, 1, 0]}},
                    }
                },
                {
                    "$setWindowFields": {
                        "sortBy": {"admissions": -1},
                        "output": {
                            "avg_month": {"$avg": "$admissions", "window": {"documents": ["unbounded", "unbounded"]}},
                            "rank": {"$rank": {}},
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "rank": "$rank",
                        "year_month": "$_id",
                        "admissions": "$admissions",
                        "vs_avg_pct": {"$round": [{"$multiply": [{"$divide": [{"$subtract": ["$admissions", "$avg_month"]}, "$avg_month"]}, 100]}, 2]},
                        "emergency_share_pct": {"$round": [{"$multiply": [{"$divide": ["$emergency", "$admissions"]}, 100]}, 2]},
                    }
                },
                {"$match": {"$or": [{"rank": {"$lte": 3}}, {"rank": {"$gte": 46}}]}},
                {"$sort": {"rank": 1}},
            ]
        ),
        save="q10e_month_outliers",
    )

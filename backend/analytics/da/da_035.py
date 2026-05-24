"""
DA-035: SICR Threshold Sensitivity Test
Compute ECL impact of moving SICR threshold from 30 DPD to 25 DPD.
LMS Risk Theme: 3
CAP Seq: R.35
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-035",
    "name": "SICR Threshold Sensitivity Test",
    "description": "ECL impact of SICR at 25 vs 30 DPD; identify cusp accounts DPD 25-30",
    "cap_seq": "R.35",
    "risk_theme": 3,
    "required_inputs": ["loan_tape"],
    "optional_inputs": [],
}

STAGE1_ECL_RATE = 0.005
STAGE2_ECL_RATE = 0.030


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    SICR Threshold Sensitivity:
    1. Identify 'cusp accounts': DPD 25-30 currently Stage 1.
    2. Compute additional ECL if these were Stage 2.
    3. Show full ECL sensitivity: current SICR (30) vs tighter SICR (25).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. Identify cusp accounts: DPD 25-30, Stage 1 ─────────────────────
    cusp_accounts = con.execute(f"""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
            TOTAL_ECL_PROVISION,
            (OUTSTANDING_PRINCIPAL * {STAGE2_ECL_RATE}) AS ecl_at_stage2,
            (OUTSTANDING_PRINCIPAL * {STAGE1_ECL_RATE}) AS ecl_at_stage1,
            (OUTSTANDING_PRINCIPAL * ({STAGE2_ECL_RATE} - {STAGE1_ECL_RATE})) AS additional_ecl_if_stage2,
            'SICR_CUSP_25_30' AS exception_type
        FROM loan_tape
        WHERE DPD BETWEEN 25 AND 30
          AND IND_AS_STAGE = 1
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
          AND OUTSTANDING_PRINCIPAL > 0
        ORDER BY DPD DESC, OUTSTANDING_PRINCIPAL DESC
    """ if "TOTAL_ECL_PROVISION" in df.columns else f"""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
            NULL AS TOTAL_ECL_PROVISION,
            (OUTSTANDING_PRINCIPAL * {STAGE2_ECL_RATE}) AS ecl_at_stage2,
            (OUTSTANDING_PRINCIPAL * {STAGE1_ECL_RATE}) AS ecl_at_stage1,
            (OUTSTANDING_PRINCIPAL * ({STAGE2_ECL_RATE} - {STAGE1_ECL_RATE})) AS additional_ecl_if_stage2,
            'SICR_CUSP_25_30' AS exception_type
        FROM loan_tape
        WHERE DPD BETWEEN 25 AND 30
          AND IND_AS_STAGE = 1
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
          AND OUTSTANDING_PRINCIPAL > 0
        ORDER BY DPD DESC, OUTSTANDING_PRINCIPAL DESC
    """).pl()

    total_additional_ecl = float(cusp_accounts["additional_ecl_if_stage2"].sum() or 0) if len(cusp_accounts) > 0 else 0

    if len(cusp_accounts) > 0:
        anomaly_flags.append({
            "field": "DPD",
            "value": len(cusp_accounts),
            "threshold": "SICR threshold sensitivity at 25 DPD",
            "message": f"{len(cusp_accounts)} accounts in DPD 25-30 (Stage 1); additional ECL ₹{total_additional_ecl:,.0f} if SICR threshold moved to 25"
        })

    # ── 2. Full SICR sensitivity: DPD buckets ─────────────────────────────
    sensitivity_analysis = con.execute(f"""
        WITH dpd_buckets AS (
            SELECT
                CASE
                    WHEN DPD BETWEEN 25 AND 27 THEN '25-27 DPD'
                    WHEN DPD BETWEEN 28 AND 30 THEN '28-30 DPD'
                    WHEN DPD BETWEEN 31 AND 35 THEN '31-35 DPD'
                    ELSE 'OTHER'
                END AS dpd_band,
                IND_AS_STAGE,
                OUTSTANDING_PRINCIPAL,
                TOTAL_ECL_PROVISION
            FROM loan_tape
            WHERE DPD BETWEEN 25 AND 35
              AND IND_AS_STAGE IS NOT NULL
              AND OUTSTANDING_PRINCIPAL IS NOT NULL
        )
        SELECT
            dpd_band,
            IND_AS_STAGE,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(COALESCE(TOTAL_ECL_PROVISION, OUTSTANDING_PRINCIPAL * 0.005)) AS current_ecl,
            SUM(OUTSTANDING_PRINCIPAL * {STAGE2_ECL_RATE}) AS ecl_at_stage2,
            SUM(OUTSTANDING_PRINCIPAL * {STAGE2_ECL_RATE})
                - SUM(COALESCE(TOTAL_ECL_PROVISION, OUTSTANDING_PRINCIPAL * 0.005)) AS additional_ecl_needed
        FROM dpd_buckets
        GROUP BY dpd_band, IND_AS_STAGE
        ORDER BY dpd_band, IND_AS_STAGE
    """ if "TOTAL_ECL_PROVISION" in df.columns else f"""
        WITH dpd_buckets AS (
            SELECT
                CASE
                    WHEN DPD BETWEEN 25 AND 27 THEN '25-27 DPD'
                    WHEN DPD BETWEEN 28 AND 30 THEN '28-30 DPD'
                    WHEN DPD BETWEEN 31 AND 35 THEN '31-35 DPD'
                    ELSE 'OTHER'
                END AS dpd_band,
                IND_AS_STAGE,
                OUTSTANDING_PRINCIPAL
            FROM loan_tape
            WHERE DPD BETWEEN 25 AND 35
              AND IND_AS_STAGE IS NOT NULL
              AND OUTSTANDING_PRINCIPAL IS NOT NULL
        )
        SELECT
            dpd_band,
            IND_AS_STAGE,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(OUTSTANDING_PRINCIPAL * {STAGE1_ECL_RATE}) AS current_ecl,
            SUM(OUTSTANDING_PRINCIPAL * {STAGE2_ECL_RATE}) AS ecl_at_stage2,
            SUM(OUTSTANDING_PRINCIPAL * ({STAGE2_ECL_RATE} - {STAGE1_ECL_RATE})) AS additional_ecl_needed
        FROM dpd_buckets
        GROUP BY dpd_band, IND_AS_STAGE
        ORDER BY dpd_band, IND_AS_STAGE
    """).pl()

    return {
        "da_ref": "DA-035",
        "total_records": len(df),
        "exceptions_count": len(cusp_accounts),
        "exceptions_df": cusp_accounts,
        "sensitivity_analysis": sensitivity_analysis,
        "summary": {
            "cusp_accounts": len(cusp_accounts),
            "cusp_outstanding": round(float(cusp_accounts["OUTSTANDING_PRINCIPAL"].sum() or 0), 2) if len(cusp_accounts) > 0 else 0,
            "additional_ecl_at_25dpd_threshold": round(total_additional_ecl, 2),
            "current_sicr_threshold": 30,
            "sensitivity_threshold": 25,
        },
        "anomaly_flags": anomaly_flags,
    }

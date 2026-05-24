"""
DA-014: SICR Backstop Validation
Flag DPD >= 30 accounts still in Stage 1; compute ECL impact of required reclassification.
LMS Risk Theme: 4
CAP Seq: R.14
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-014",
    "name": "SICR Backstop Validation",
    "description": "DPD >= 30 must be Stage 2; flag Stage 1 accounts in SICR zone and compute ECL impact",
    "cap_seq": "R.14",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": [],
}

# Approximation rates for ECL impact
STAGE1_ECL_RATE = 0.005   # 0.5% of outstanding
STAGE2_ECL_RATE = 0.030   # 3.0% of outstanding


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    SICR Backstop Validation:
    1. Flag all DPD >= 30 AND IND_AS_STAGE = 1 (SICR backstop failure).
    2. Flag DPD 28-35 day zone accounts (SICR cusp).
    3. Compute ECL impact of Stage 1 -> Stage 2 migration.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. SICR backstop failures: DPD >= 30 AND Stage 1 ─────────────────
    sicr_failures = con.execute("""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
            TOTAL_ECL_PROVISION,
            STAGE_1_ECL,
            (OUTSTANDING_PRINCIPAL * 0.030) AS ecl_at_stage2,
            (OUTSTANDING_PRINCIPAL * 0.005) AS ecl_at_stage1,
            ((OUTSTANDING_PRINCIPAL * 0.030) - (OUTSTANDING_PRINCIPAL * 0.005)) AS additional_ecl_needed,
            'SICR_BACKSTOP_FAILURE' AS exception_type
        FROM loan_tape
        WHERE DPD >= 30
          AND IND_AS_STAGE = 1
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
          AND OUTSTANDING_PRINCIPAL > 0
        ORDER BY DPD DESC, OUTSTANDING_PRINCIPAL DESC
    """ if "TOTAL_ECL_PROVISION" in df.columns else """
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
            NULL AS TOTAL_ECL_PROVISION,
            NULL AS STAGE_1_ECL,
            (OUTSTANDING_PRINCIPAL * 0.030) AS ecl_at_stage2,
            (OUTSTANDING_PRINCIPAL * 0.005) AS ecl_at_stage1,
            ((OUTSTANDING_PRINCIPAL * 0.030) - (OUTSTANDING_PRINCIPAL * 0.005)) AS additional_ecl_needed,
            'SICR_BACKSTOP_FAILURE' AS exception_type
        FROM loan_tape
        WHERE DPD >= 30
          AND IND_AS_STAGE = 1
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
          AND OUTSTANDING_PRINCIPAL > 0
        ORDER BY DPD DESC, OUTSTANDING_PRINCIPAL DESC
    """).pl()

    if len(sicr_failures) > 0:
        total_additional_ecl = float(sicr_failures["additional_ecl_needed"].sum() or 0)
        anomaly_flags.append({
            "field": "IND_AS_STAGE",
            "value": len(sicr_failures),
            "threshold": "DPD >= 30 => Stage >= 2 (SICR backstop)",
            "message": f"{len(sicr_failures)} accounts with DPD >= 30 still in Stage 1; additional ECL needed: ₹{total_additional_ecl:,.0f}"
        })

    # ── 2. SICR cusp zone: DPD 28-35 days ────────────────────────────────
    sicr_cusp = con.execute("""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
            (OUTSTANDING_PRINCIPAL * 0.030) AS ecl_if_stage2,
            (OUTSTANDING_PRINCIPAL * 0.005) AS current_ecl_rate,
            'SICR_CUSP_ZONE' AS exception_type
        FROM loan_tape
        WHERE DPD BETWEEN 28 AND 35
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
        ORDER BY DPD DESC
    """).pl()

    if len(sicr_cusp) > 0:
        cusp_amount = float(sicr_cusp["OUTSTANDING_PRINCIPAL"].sum() or 0)
        anomaly_flags.append({
            "field": "DPD",
            "value": len(sicr_cusp),
            "threshold": "DPD 28-35 = SICR assessment zone",
            "message": f"{len(sicr_cusp)} accounts in DPD 28-35 (SICR cusp); ₹{cusp_amount:,.0f} outstanding requires SICR assessment"
        })

    # ── 3. ECL impact by product ───────────────────────────────────────────
    ecl_impact_by_product = pl.DataFrame()
    if len(sicr_failures) > 0:
        con.register("sicr_failures", sicr_failures.to_arrow())
        ecl_impact_by_product = con.execute("""
            SELECT
                PRODUCT_CODE,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                SUM(additional_ecl_needed) AS total_additional_ecl,
                AVG(DPD) AS avg_dpd,
                MAX(DPD) AS max_dpd
            FROM sicr_failures
            GROUP BY PRODUCT_CODE
            ORDER BY total_additional_ecl DESC
        """).pl()

    # ── 4. DPD distribution in Stage 1 ────────────────────────────────────
    dpd_dist_stage1 = con.execute("""
        SELECT
            CASE
                WHEN DPD = 0 THEN '0 (Current)'
                WHEN DPD BETWEEN 1 AND 14 THEN '1-14 DPD'
                WHEN DPD BETWEEN 15 AND 29 THEN '15-29 DPD'
                WHEN DPD BETWEEN 30 AND 59 THEN '30-59 DPD (SICR)'
                ELSE '60+ DPD'
            END AS dpd_bucket,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding
        FROM loan_tape
        WHERE IND_AS_STAGE = 1
          AND DPD IS NOT NULL
        GROUP BY 1
        ORDER BY MIN(DPD)
    """).pl()

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [sicr_failures, sicr_cusp] if len(f) > 0]
    if exc_frames:
        all_cols = set()
        for f in exc_frames:
            all_cols.update(f.columns)
        normalized = []
        for f in exc_frames:
            for col in sorted(all_cols):
                if col not in f.columns:
                    f = f.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))
            normalized.append(f.select(sorted(all_cols)))
        exceptions_df = pl.concat(normalized)
    else:
        exceptions_df = pl.DataFrame()

    total_additional_ecl = float(sicr_failures["additional_ecl_needed"].sum() or 0) if len(sicr_failures) > 0 else 0

    return {
        "da_ref": "DA-014",
        "total_records": len(df),
        "exceptions_count": len(sicr_failures),
        "exceptions_df": exceptions_df,
        "sicr_backstop_failures": sicr_failures,
        "sicr_cusp_zone": sicr_cusp,
        "ecl_impact_by_product": ecl_impact_by_product,
        "dpd_distribution_stage1": dpd_dist_stage1,
        "summary": {
            "total_loans": len(df),
            "sicr_backstop_failures": len(sicr_failures),
            "sicr_cusp_zone_count": len(sicr_cusp),
            "total_additional_ecl_needed": round(total_additional_ecl, 2),
            "stage1_ecl_rate_used": STAGE1_ECL_RATE,
            "stage2_ecl_rate_used": STAGE2_ECL_RATE,
        },
        "anomaly_flags": anomaly_flags,
    }

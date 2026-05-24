"""
DA-009: NPA Stage Transition Analysis
Compute stage migration matrix; flag backward migrations and quick NPA recurrence.
LMS Risk Theme: 4
CAP Seq: R.09
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-009",
    "name": "NPA Stage Transition Analysis",
    "description": "Stage migration matrix; flag backward migrations without genuine repayment",
    "cap_seq": "R.09",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["prior_loan_tape"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    NPA Stage Transition Analysis:
    1. Build transition matrix: Stage X -> Stage Y counts and amounts from prior to current.
    2. Flag backward migrations (3→2, 2→1) without genuine repayment.
    3. Flag 'cured' accounts that returned to NPA within 90 days.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("current_tape", df.to_arrow())

    anomaly_flags = []
    transition_matrix = pl.DataFrame()
    backward_migrations = pl.DataFrame()
    quick_redefault = pl.DataFrame()

    prior_tape = kwargs.get("prior_loan_tape")

    if prior_tape is not None:
        prior_df = prior_tape.collect() if isinstance(prior_tape, pl.LazyFrame) else prior_tape
        con.register("prior_tape", prior_df.to_arrow())

        # ── 1. Stage transition matrix ────────────────────────────────────
        transition_matrix = con.execute("""
            WITH transitions AS (
                SELECT
                    p.LOAN_ACCOUNT_NO,
                    p.IND_AS_STAGE AS prior_stage,
                    c.IND_AS_STAGE AS current_stage,
                    c.OUTSTANDING_PRINCIPAL AS current_outstanding,
                    p.OUTSTANDING_PRINCIPAL AS prior_outstanding,
                    c.LAST_PAYMENT_DATE,
                    c.LAST_PAYMENT_AMOUNT,
                    c.DPD AS current_dpd,
                    p.DPD AS prior_dpd
                FROM prior_tape p
                JOIN current_tape c ON p.LOAN_ACCOUNT_NO = c.LOAN_ACCOUNT_NO
                WHERE p.IND_AS_STAGE IS NOT NULL
                  AND c.IND_AS_STAGE IS NOT NULL
            )
            SELECT
                prior_stage,
                current_stage,
                COUNT(*) AS account_count,
                SUM(current_outstanding) AS total_outstanding,
                SUM(CASE WHEN current_stage < prior_stage THEN 1 ELSE 0 END) AS backward_count
            FROM transitions
            GROUP BY prior_stage, current_stage
            ORDER BY prior_stage, current_stage
        """).pl()

        # ── 2. Backward migrations without genuine repayment ─────────────
        backward_migrations = con.execute("""
            WITH transitions AS (
                SELECT
                    p.LOAN_ACCOUNT_NO,
                    p.IND_AS_STAGE AS prior_stage,
                    c.IND_AS_STAGE AS current_stage,
                    c.OUTSTANDING_PRINCIPAL,
                    c.BRANCH_CODE,
                    c.PRODUCT_CODE,
                    c.PAN_NUMBER,
                    c.DPD AS current_dpd,
                    c.LAST_PAYMENT_AMOUNT,
                    c.LAST_PAYMENT_DATE,
                    c.EMI_AMOUNT
                FROM prior_tape p
                JOIN current_tape c ON p.LOAN_ACCOUNT_NO = c.LOAN_ACCOUNT_NO
                WHERE p.IND_AS_STAGE IS NOT NULL
                  AND c.IND_AS_STAGE IS NOT NULL
                  AND c.IND_AS_STAGE < p.IND_AS_STAGE
            )
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                prior_stage, current_stage,
                current_dpd, LAST_PAYMENT_AMOUNT, EMI_AMOUNT,
                OUTSTANDING_PRINCIPAL,
                CASE
                    WHEN LAST_PAYMENT_AMOUNT IS NULL OR LAST_PAYMENT_AMOUNT = 0
                    THEN 'BACKWARD_MIGRATION_NO_PAYMENT'
                    WHEN LAST_PAYMENT_AMOUNT < EMI_AMOUNT * 0.5
                    THEN 'BACKWARD_MIGRATION_PARTIAL_PAYMENT'
                    ELSE 'BACKWARD_MIGRATION_WITH_PAYMENT'
                END AS exception_type
            FROM transitions
            WHERE current_dpd > 0
               OR LAST_PAYMENT_AMOUNT IS NULL
               OR LAST_PAYMENT_AMOUNT = 0
            ORDER BY OUTSTANDING_PRINCIPAL DESC
        """).pl()

        if len(backward_migrations) > 0:
            anomaly_flags.append({
                "field": "IND_AS_STAGE",
                "value": len(backward_migrations),
                "threshold": "Backward stage migration requires genuine repayment",
                "message": f"{len(backward_migrations)} backward stage migrations without sufficient repayment"
            })

        # ── 3. Quick NPA recurrence (cured accounts back in NPA < 90 days)
        # Using last payment date as proxy for cure date
        quick_redefault = con.execute(f"""
            WITH cured_accounts AS (
                SELECT
                    p.LOAN_ACCOUNT_NO,
                    p.IND_AS_STAGE AS prior_stage,
                    c.IND_AS_STAGE AS current_stage,
                    c.OUTSTANDING_PRINCIPAL,
                    c.BRANCH_CODE,
                    c.PRODUCT_CODE,
                    c.PAN_NUMBER,
                    c.DPD AS current_dpd,
                    c.LAST_PAYMENT_DATE,
                    c.RESTRUCTURE_DATE
                FROM prior_tape p
                JOIN current_tape c ON p.LOAN_ACCOUNT_NO = c.LOAN_ACCOUNT_NO
                WHERE p.IND_AS_STAGE = 3
                  AND c.IND_AS_STAGE IN (1, 2)
            )
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                prior_stage, current_stage, current_dpd,
                LAST_PAYMENT_DATE,
                DATE_DIFF('day', CAST(LAST_PAYMENT_DATE AS DATE), CAST('{reporting_date}' AS DATE)) AS days_since_cure,
                'QUICK_REDEFAULT_RISK' AS exception_type
            FROM cured_accounts
            WHERE current_dpd > 0
        """).pl()

        if len(quick_redefault) > 0:
            anomaly_flags.append({
                "field": "IND_AS_STAGE",
                "value": len(quick_redefault),
                "threshold": "90 days clean period after NPA cure",
                "message": f"{len(quick_redefault)} recently cured NPA accounts already showing DPD > 0"
            })

    else:
        # Without prior tape, compute cross-sectional analysis
        transition_matrix = con.execute("""
            SELECT
                IND_AS_STAGE AS current_stage,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                AVG(DPD) AS avg_dpd,
                MAX(DPD) AS max_dpd
            FROM current_tape
            WHERE IND_AS_STAGE IS NOT NULL
            GROUP BY IND_AS_STAGE
            ORDER BY IND_AS_STAGE
        """).pl()

        anomaly_flags.append({
            "field": "prior_loan_tape",
            "value": None,
            "threshold": "Required for transition analysis",
            "message": "Prior period loan tape not provided; full transition analysis skipped"
        })

    exceptions_df = backward_migrations if len(backward_migrations) > 0 else quick_redefault

    return {
        "da_ref": "DA-009",
        "total_records": len(df),
        "exceptions_count": len(backward_migrations) + len(quick_redefault),
        "exceptions_df": exceptions_df,
        "transition_matrix": transition_matrix,
        "backward_migrations": backward_migrations,
        "quick_redefault": quick_redefault,
        "summary": {
            "total_records": len(df),
            "backward_migrations": len(backward_migrations),
            "quick_redefault_risk": len(quick_redefault),
            "prior_tape_provided": prior_tape is not None,
        },
        "anomaly_flags": anomaly_flags,
    }

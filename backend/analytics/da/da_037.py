"""
DA-037: Loan Stage Migration Matrix
Build period-over-period stage migration matrix; flag high backward migration rates.
LMS Risk Theme: 4
CAP Seq: R.37
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-037",
    "name": "Loan Stage Migration Matrix",
    "description": "Stage migration matrix; flag Stage 3->2 backward migrations without receipts",
    "cap_seq": "R.37",
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
    Loan Migration Matrix:
    1. Build stage migration matrix from prior to current period.
    2. Flag high backward migration rates (Stage 3->2).
    3. Identify accounts moving backward without genuine cash receipts.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("current_tape", df.to_arrow())

    anomaly_flags = []
    prior_tape = kwargs.get("prior_loan_tape")

    if prior_tape is None:
        return {
            "da_ref": "DA-037",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "prior_loan_tape not provided"},
            "anomaly_flags": [{"field": "prior_loan_tape", "value": None,
                                "threshold": "Required", "message": "Prior period data not provided"}],
        }

    prior_df = prior_tape.collect() if isinstance(prior_tape, pl.LazyFrame) else prior_tape
    con.register("prior_tape", prior_df.to_arrow())

    # ── 1. Build migration matrix ─────────────────────────────────────────
    migration_matrix = con.execute("""
        SELECT
            p.IND_AS_STAGE AS from_stage,
            c.IND_AS_STAGE AS to_stage,
            COUNT(*) AS account_count,
            SUM(c.OUTSTANDING_PRINCIPAL) AS current_outstanding,
            SUM(p.OUTSTANDING_PRINCIPAL) AS prior_outstanding,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY p.IND_AS_STAGE), 2) AS migration_pct
        FROM prior_tape p
        JOIN current_tape c ON p.LOAN_ACCOUNT_NO = c.LOAN_ACCOUNT_NO
        WHERE p.IND_AS_STAGE IS NOT NULL AND c.IND_AS_STAGE IS NOT NULL
        GROUP BY p.IND_AS_STAGE, c.IND_AS_STAGE
        ORDER BY p.IND_AS_STAGE, c.IND_AS_STAGE
    """).pl()

    # ── 2. Backward migrations without genuine receipts ────────────────────
    backward_no_receipt = con.execute("""
        WITH backward_migrations AS (
            SELECT
                p.LOAN_ACCOUNT_NO,
                p.PAN_NUMBER,
                p.PRODUCT_CODE,
                p.BRANCH_CODE,
                p.IND_AS_STAGE AS from_stage,
                c.IND_AS_STAGE AS to_stage,
                c.OUTSTANDING_PRINCIPAL AS current_outstanding,
                c.DPD AS current_dpd,
                c.LAST_PAYMENT_AMOUNT,
                c.LAST_PAYMENT_DATE,
                p.OUTSTANDING_PRINCIPAL AS prior_outstanding
            FROM prior_tape p
            JOIN current_tape c ON p.LOAN_ACCOUNT_NO = c.LOAN_ACCOUNT_NO
            WHERE p.IND_AS_STAGE = 3 AND c.IND_AS_STAGE < 3
        )
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            from_stage, to_stage, current_outstanding, current_dpd,
            LAST_PAYMENT_AMOUNT, LAST_PAYMENT_DATE,
            prior_outstanding,
            CASE
                WHEN current_dpd > 0 THEN 'BACKWARD_MIGRATION_STILL_DPD'
                WHEN COALESCE(LAST_PAYMENT_AMOUNT, 0) = 0 THEN 'BACKWARD_MIGRATION_NO_PAYMENT'
                WHEN LAST_PAYMENT_AMOUNT < prior_outstanding * 0.25 THEN 'BACKWARD_MIGRATION_INSUFFICIENT_PAYMENT'
                ELSE 'BACKWARD_MIGRATION_PARTIAL'
            END AS exception_type
        FROM backward_migrations
        WHERE current_dpd > 0
           OR COALESCE(LAST_PAYMENT_AMOUNT, 0) = 0
           OR LAST_PAYMENT_AMOUNT < prior_outstanding * 0.25
        ORDER BY current_outstanding DESC
    """).pl()

    if len(backward_no_receipt) > 0:
        amount = float(backward_no_receipt["current_outstanding"].sum() or 0)
        anomaly_flags.append({
            "field": "IND_AS_STAGE",
            "value": len(backward_no_receipt),
            "threshold": "Stage 3->2 requires DPD=0 and full overdue cleared",
            "message": f"{len(backward_no_receipt)} backward migrations (Stage 3->2) without genuine receipts; ₹{amount:,.0f}"
        })

    # ── Backward migration rate ────────────────────────────────────────────
    if len(migration_matrix) > 0:
        backward = migration_matrix.filter(pl.col("to_stage") < pl.col("from_stage"))
        total_movements = int(migration_matrix["account_count"].sum() or 0)
        backward_count = int(backward["account_count"].sum() or 0)
        backward_rate = backward_count / total_movements * 100 if total_movements > 0 else 0

        if backward_rate > 5:
            anomaly_flags.append({
                "field": "MIGRATION_MATRIX",
                "value": round(backward_rate, 2),
                "threshold": "< 5% backward migration rate",
                "message": f"Overall backward migration rate {backward_rate:.2f}% (> 5% concern)"
            })

    return {
        "da_ref": "DA-037",
        "total_records": len(df),
        "exceptions_count": len(backward_no_receipt),
        "exceptions_df": backward_no_receipt,
        "migration_matrix": migration_matrix,
        "summary": {
            "total_records": len(df),
            "prior_records": len(prior_df),
            "backward_migrations_no_receipt": len(backward_no_receipt),
        },
        "anomaly_flags": anomaly_flags,
    }

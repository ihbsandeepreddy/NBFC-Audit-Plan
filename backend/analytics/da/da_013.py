"""
DA-013: DPD Independent Recomputation
Recompute DPD from repayment history and compare to stored DPD; flag suppression.
LMS Risk Theme: 4
CAP Seq: R.13
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-013",
    "name": "DPD Independent Recomputation",
    "description": "Recompute DPD from payment history; flag where computed DPD > stored DPD",
    "cap_seq": "R.13",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["repayment_history"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    DPD Independent Recomputation:
    1. For accounts with DPD > 0, recompute DPD from repayment_history.
    2. DPD = Reporting Date - Date of FIRST missed payment.
    3. Partial payment does NOT reset DPD unless overdue fully cleared.
    4. Compare computed DPD to stored DPD; flag where computed > stored (suppression).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    dpd_suppression_df = pl.DataFrame()
    recomputed_df = pl.DataFrame()

    if repayment_history is None:
        # Without repayment history, use loan tape fields to infer
        # Flag accounts where DPD suggests stage mismatch
        if "DPD" in df.columns and "IND_AS_STAGE" in df.columns:
            stage_dpd_mismatch = con.execute("""
                SELECT
                    LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                    DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
                    CASE
                        WHEN DPD >= 30 AND IND_AS_STAGE = 1 THEN 'SICR_BREACH_DPD_STAGE'
                        WHEN DPD >= 90 AND IND_AS_STAGE < 3 THEN 'NPA_NOT_CLASSIFIED'
                        ELSE 'DPD_STAGE_MISMATCH'
                    END AS exception_type
                FROM loan_tape
                WHERE (DPD >= 30 AND IND_AS_STAGE = 1)
                   OR (DPD >= 90 AND IND_AS_STAGE < 3)
                ORDER BY DPD DESC
            """).pl()

            if len(stage_dpd_mismatch) > 0:
                anomaly_flags.append({
                    "field": "DPD/IND_AS_STAGE",
                    "value": len(stage_dpd_mismatch),
                    "threshold": "DPD >= 30 => Stage >= 2; DPD >= 90 => Stage 3",
                    "message": f"{len(stage_dpd_mismatch)} DPD-Stage mismatches (no repayment history available for full recomputation)"
                })

            return {
                "da_ref": "DA-013",
                "total_records": len(df),
                "exceptions_count": len(stage_dpd_mismatch),
                "exceptions_df": stage_dpd_mismatch,
                "summary": {"note": "Repayment history not provided; DPD-stage cross-check performed"},
                "anomaly_flags": anomaly_flags,
            }

    # ── Full DPD recomputation from repayment history ─────────────────────
    rh_df = repayment_history.collect() if isinstance(repayment_history, pl.LazyFrame) else repayment_history
    con.register("repayment_hist", rh_df.to_arrow())

    payment_date_col = "PAYMENT_DATE" if "PAYMENT_DATE" in rh_df.columns else "TXN_DATE"
    payment_amount_col = "PAYMENT_AMOUNT" if "PAYMENT_AMOUNT" in rh_df.columns else "AMOUNT"
    due_date_col = "DUE_DATE" if "DUE_DATE" in rh_df.columns else None
    due_amount_col = "DUE_AMOUNT" if "DUE_AMOUNT" in rh_df.columns else "EMI_AMOUNT"

    # Only recompute for accounts where DPD > 0 in stored tape
    if due_date_col and payment_date_col in rh_df.columns:
        recomputed_df = con.execute(f"""
            WITH schedule AS (
                SELECT
                    r.LOAN_ACCOUNT_NO,
                    r."{due_date_col}" AS due_date,
                    COALESCE(r."{due_amount_col}", l.EMI_AMOUNT, 0) AS due_amount,
                    r."{payment_date_col}" AS payment_date,
                    COALESCE(r."{payment_amount_col}", 0) AS payment_amount
                FROM repayment_hist r
                JOIN loan_tape l ON r.LOAN_ACCOUNT_NO = l.LOAN_ACCOUNT_NO
                WHERE l.DPD > 0
            ),
            -- For each due date, sum all payments received on or before reporting date
            payments_by_due AS (
                SELECT
                    s1.LOAN_ACCOUNT_NO,
                    s1.due_date,
                    s1.due_amount,
                    SUM(s2.payment_amount) AS total_paid_by_due_date
                FROM schedule s1
                JOIN schedule s2 ON s1.LOAN_ACCOUNT_NO = s2.LOAN_ACCOUNT_NO
                    AND s2.payment_date <= '{reporting_date}'
                    AND s2.payment_date <= s1.due_date + INTERVAL 30 DAY
                GROUP BY s1.LOAN_ACCOUNT_NO, s1.due_date, s1.due_amount
            ),
            -- Find first missed payment (not fully covered)
            first_miss AS (
                SELECT
                    LOAN_ACCOUNT_NO,
                    MIN(CASE
                        WHEN total_paid_by_due_date < due_amount * 0.99
                             AND due_date <= '{reporting_date}'
                        THEN due_date
                    END) AS first_missed_due_date
                FROM payments_by_due
                GROUP BY LOAN_ACCOUNT_NO
            ),
            computed_dpd AS (
                SELECT
                    fm.LOAN_ACCOUNT_NO,
                    fm.first_missed_due_date,
                    DATE_DIFF('day', CAST(fm.first_missed_due_date AS DATE), CAST('{reporting_date}' AS DATE)) AS computed_dpd
                FROM first_miss fm
                WHERE fm.first_missed_due_date IS NOT NULL
            )
            SELECT
                l.LOAN_ACCOUNT_NO,
                l.PAN_NUMBER,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.DPD AS stored_dpd,
                cd.computed_dpd,
                (cd.computed_dpd - l.DPD) AS dpd_gap,
                cd.first_missed_due_date,
                l.OUTSTANDING_PRINCIPAL,
                l.IND_AS_STAGE,
                CASE
                    WHEN cd.computed_dpd > l.DPD + 5 THEN 'DPD_SUPPRESSION'
                    WHEN cd.computed_dpd < l.DPD - 5 THEN 'DPD_OVERSTATED'
                    ELSE 'MATCH'
                END AS exception_type
            FROM loan_tape l
            JOIN computed_dpd cd ON l.LOAN_ACCOUNT_NO = cd.LOAN_ACCOUNT_NO
            WHERE cd.computed_dpd != l.DPD
            ORDER BY dpd_gap DESC
        """).pl()
    else:
        # Simpler computation: flag where payment_date > last due_date implies missed payment
        recomputed_df = con.execute(f"""
            WITH latest_payment AS (
                SELECT
                    LOAN_ACCOUNT_NO,
                    MAX("{payment_date_col}") AS last_payment_date,
                    SUM("{payment_amount_col}") AS total_paid_in_period
                FROM repayment_hist
                WHERE "{payment_date_col}" <= '{reporting_date}'
                GROUP BY LOAN_ACCOUNT_NO
            ),
            inferred_dpd AS (
                SELECT
                    l.LOAN_ACCOUNT_NO,
                    l.PAN_NUMBER,
                    l.PRODUCT_CODE,
                    l.BRANCH_CODE,
                    l.DPD AS stored_dpd,
                    DATE_DIFF('day', CAST(lp.last_payment_date AS DATE), CAST('{reporting_date}' AS DATE)) AS days_since_last_payment,
                    l.OUTSTANDING_PRINCIPAL,
                    l.IND_AS_STAGE,
                    lp.last_payment_date
                FROM loan_tape l
                LEFT JOIN latest_payment lp ON l.LOAN_ACCOUNT_NO = lp.LOAN_ACCOUNT_NO
                WHERE l.DPD > 0
            )
            SELECT *,
                CASE
                    WHEN days_since_last_payment > stored_dpd + 5 THEN 'DPD_SUPPRESSION'
                    ELSE 'MATCH'
                END AS exception_type
            FROM inferred_dpd
            WHERE days_since_last_payment > stored_dpd + 5
            ORDER BY (days_since_last_payment - stored_dpd) DESC
        """).pl()

    dpd_suppression_df = recomputed_df.filter(
        pl.col("exception_type") == "DPD_SUPPRESSION"
    ) if len(recomputed_df) > 0 and "exception_type" in recomputed_df.columns else pl.DataFrame()

    if len(dpd_suppression_df) > 0:
        dpd_gap_col = "dpd_gap" if "dpd_gap" in dpd_suppression_df.columns else None
        max_gap = float(dpd_suppression_df[dpd_gap_col].max() or 0) if dpd_gap_col else 0
        anomaly_flags.append({
            "field": "DPD",
            "value": len(dpd_suppression_df),
            "threshold": "Computed DPD == Stored DPD (±5 days)",
            "message": f"{len(dpd_suppression_df)} accounts where computed DPD > stored DPD (max gap: {max_gap:.0f} days) - DPD suppression risk"
        })

    # ── Stage impact analysis ──────────────────────────────────────────────
    stage_impact = pl.DataFrame()
    if len(dpd_suppression_df) > 0 and "computed_dpd" in dpd_suppression_df.columns:
        con.register("dpd_suppression", dpd_suppression_df.to_arrow())
        stage_impact = con.execute("""
            SELECT
                IND_AS_STAGE AS stored_stage,
                CASE
                    WHEN computed_dpd >= 90 THEN 3
                    WHEN computed_dpd >= 30 THEN 2
                    ELSE 1
                END AS computed_stage,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS outstanding
            FROM dpd_suppression
            GROUP BY IND_AS_STAGE,
                CASE
                    WHEN computed_dpd >= 90 THEN 3
                    WHEN computed_dpd >= 30 THEN 2
                    ELSE 1
                END
            ORDER BY 1, 2
        """).pl()

    return {
        "da_ref": "DA-013",
        "total_records": len(df),
        "exceptions_count": len(dpd_suppression_df),
        "exceptions_df": dpd_suppression_df,
        "full_recomputed_df": recomputed_df,
        "stage_impact_analysis": stage_impact,
        "summary": {
            "total_loans": len(df),
            "dpd_gt_zero": df.filter(pl.col("DPD") > 0).height if "DPD" in df.columns else 0,
            "dpd_suppression_cases": len(dpd_suppression_df),
            "repayment_history_provided": repayment_history is not None,
        },
        "anomaly_flags": anomaly_flags,
    }

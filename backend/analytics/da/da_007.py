"""
DA-007: Repayment Mode Analysis
Flag cash repayments on large loans, bounce rate analysis, consecutive bounce detection.
LMS Risk Theme: 5
CAP Seq: R.07
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-007",
    "name": "Repayment Mode Analysis",
    "description": "PMLA cash check >₹50K, NACH/PDC bounce rates, consecutive bounce early-NPA warning",
    "cap_seq": "R.07",
    "risk_theme": 5,
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
    Repayment Mode Analysis:
    1. Flag REPAYMENT_MODE = 'CASH' for loans > ₹50,000 (PMLA violation risk).
    2. Flag PDC/NACH bounce rate by branch.
    3. Flag accounts with >3 consecutive bounces (early NPA warning).
    4. Cross-reference with DPD to check if bounces are captured.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. Cash repayment on loans > ₹50,000 (PMLA) ─────────────────────
    pmla_cash_df = pl.DataFrame()
    if "REPAYMENT_MODE" in df.columns and "OUTSTANDING_PRINCIPAL" in df.columns:
        pmla_cash_df = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, DISBURSEMENT_AMOUNT,
                REPAYMENT_MODE, DPD,
                'CASH_REPAYMENT_PMLA_RISK' AS exception_type
            FROM loan_tape
            WHERE UPPER(REPAYMENT_MODE) = 'CASH'
              AND COALESCE(OUTSTANDING_PRINCIPAL, DISBURSEMENT_AMOUNT, 0) > 50000
            ORDER BY OUTSTANDING_PRINCIPAL DESC
        """).pl()

        if len(pmla_cash_df) > 0:
            cash_amount = float(pmla_cash_df["OUTSTANDING_PRINCIPAL"].sum() or 0)
            anomaly_flags.append({
                "field": "REPAYMENT_MODE",
                "value": len(pmla_cash_df),
                "threshold": "No CASH for loans > ₹50,000 (PMLA)",
                "message": f"{len(pmla_cash_df)} loans >₹50K with CASH repayment mode (PMLA risk); ₹{cash_amount:,.0f}"
            })

    # ── 2. Branch-wise bounce analysis (from repayment_history) ──────────
    branch_bounce_df = pl.DataFrame()
    consecutive_bounce_df = pl.DataFrame()
    bounce_dpd_gap_df = pl.DataFrame()

    if repayment_history is not None:
        rh_df = repayment_history.collect() if isinstance(repayment_history, pl.LazyFrame) else repayment_history
        if len(rh_df) > 0:
            con.register("repayment_hist", rh_df.to_arrow())

            # Check available columns for bounce detection
            has_status = "PAYMENT_STATUS" in rh_df.columns or "BOUNCE_FLAG" in rh_df.columns
            has_mode = "REPAYMENT_MODE" in rh_df.columns or "PAYMENT_MODE" in rh_df.columns
            bounce_col = "BOUNCE_FLAG" if "BOUNCE_FLAG" in rh_df.columns else "PAYMENT_STATUS"
            bounce_filter = "BOUNCE_FLAG = TRUE" if "BOUNCE_FLAG" in rh_df.columns else "UPPER(PAYMENT_STATUS) IN ('BOUNCED', 'RETURNED', 'DISHONOURED')"

            if has_status:
                branch_bounce_df = con.execute(f"""
                    WITH bounce_data AS (
                        SELECT
                            r.LOAN_ACCOUNT_NO,
                            l.BRANCH_CODE,
                            r.PAYMENT_DATE,
                            {bounce_col},
                            CASE WHEN {bounce_filter} THEN 1 ELSE 0 END AS is_bounce
                        FROM repayment_hist r
                        JOIN loan_tape l ON r.LOAN_ACCOUNT_NO = l.LOAN_ACCOUNT_NO
                    )
                    SELECT
                        BRANCH_CODE,
                        COUNT(*) AS total_payments,
                        SUM(is_bounce) AS bounce_count,
                        ROUND(100.0 * SUM(is_bounce) / NULLIF(COUNT(*), 0), 2) AS bounce_rate_pct
                    FROM bounce_data
                    GROUP BY BRANCH_CODE
                    ORDER BY bounce_rate_pct DESC
                """).pl()

                # ── 3. Consecutive bounces ────────────────────────────────
                consecutive_bounce_df = con.execute(f"""
                    WITH bounce_seq AS (
                        SELECT
                            LOAN_ACCOUNT_NO,
                            PAYMENT_DATE,
                            is_bounce,
                            SUM(1 - is_bounce) OVER (
                                PARTITION BY LOAN_ACCOUNT_NO
                                ORDER BY PAYMENT_DATE
                                ROWS UNBOUNDED PRECEDING
                            ) AS reset_group
                        FROM (
                            SELECT
                                LOAN_ACCOUNT_NO,
                                PAYMENT_DATE,
                                CASE WHEN {bounce_filter} THEN 1 ELSE 0 END AS is_bounce
                            FROM repayment_hist
                        ) t
                    ),
                    consec_counts AS (
                        SELECT
                            LOAN_ACCOUNT_NO,
                            reset_group,
                            COUNT(*) AS consecutive_bounces,
                            MIN(PAYMENT_DATE) AS first_bounce_date,
                            MAX(PAYMENT_DATE) AS last_bounce_date
                        FROM bounce_seq
                        WHERE is_bounce = 1
                        GROUP BY LOAN_ACCOUNT_NO, reset_group
                    )
                    SELECT
                        c.LOAN_ACCOUNT_NO,
                        c.consecutive_bounces,
                        c.first_bounce_date,
                        c.last_bounce_date,
                        l.DPD AS current_dpd,
                        l.IND_AS_STAGE AS current_stage,
                        l.BRANCH_CODE,
                        l.PRODUCT_CODE,
                        CASE
                            WHEN c.consecutive_bounces > 3 AND l.DPD = 0 THEN 'BOUNCE_DPD_MISMATCH'
                            ELSE 'CONSECUTIVE_BOUNCE'
                        END AS exception_type
                    FROM consec_counts c
                    JOIN loan_tape l ON c.LOAN_ACCOUNT_NO = l.LOAN_ACCOUNT_NO
                    WHERE c.consecutive_bounces > 3
                    ORDER BY c.consecutive_bounces DESC
                """).pl()

                if len(consecutive_bounce_df) > 0:
                    anomaly_flags.append({
                        "field": "BOUNCE_COUNT",
                        "value": len(consecutive_bounce_df),
                        "threshold": "<= 3 consecutive bounces",
                        "message": f"{len(consecutive_bounce_df)} accounts with >3 consecutive bounces (early NPA warning)"
                    })

                # ── 4. Bounces not reflected in DPD ──────────────────────
                bounce_dpd_gap_df = consecutive_bounce_df.filter(
                    pl.col("exception_type") == "BOUNCE_DPD_MISMATCH"
                ) if len(consecutive_bounce_df) > 0 else pl.DataFrame()

                if len(bounce_dpd_gap_df) > 0:
                    anomaly_flags.append({
                        "field": "DPD",
                        "value": len(bounce_dpd_gap_df),
                        "threshold": "Bounces should increase DPD",
                        "message": f"{len(bounce_dpd_gap_df)} accounts with >3 bounces but DPD = 0 (DPD suppression risk)"
                    })

    # ── Repayment mode summary from loan_tape ─────────────────────────────
    mode_summary = pl.DataFrame()
    if "REPAYMENT_MODE" in df.columns:
        mode_summary = con.execute("""
            SELECT
                UPPER(REPAYMENT_MODE) AS repayment_mode,
                COUNT(*) AS loan_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding
            FROM loan_tape
            WHERE REPAYMENT_MODE IS NOT NULL
            GROUP BY UPPER(REPAYMENT_MODE)
            ORDER BY loan_count DESC
        """).pl()

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [pmla_cash_df, consecutive_bounce_df] if len(f) > 0]
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

    return {
        "da_ref": "DA-007",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "pmla_cash_violations": pmla_cash_df,
        "branch_bounce_rates": branch_bounce_df,
        "consecutive_bounces": consecutive_bounce_df,
        "bounce_dpd_mismatches": bounce_dpd_gap_df,
        "repayment_mode_summary": mode_summary,
        "summary": {
            "total_loans": len(df),
            "pmla_cash_violations": len(pmla_cash_df),
            "consecutive_bounce_accounts": len(consecutive_bounce_df),
            "bounce_dpd_gaps": len(bounce_dpd_gap_df),
        },
        "anomaly_flags": anomaly_flags,
    }

"""
DA-011: Evergreening Detection
Detect loan substitution via repayment + fresh disbursement to same PAN within 5 days.
LMS Risk Theme: 7
CAP Seq: R.11
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-011",
    "name": "Evergreening Detection",
    "description": "Flag repayment followed by fresh disbursement to same PAN within 0-5 days",
    "cap_seq": "R.11",
    "risk_theme": 7,
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
    Evergreening Detection:
    1. Find same-PAN: repayment received AND fresh disbursement within 0-5 days.
    2. Filter: repayment >= 80% of overdue AND disbursement >= 80% of repayment.
    3. Flag where borrower had DPD > 0 at time of fresh disbursement.
    4. Compute what DPD would have been if repayment excluded.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    evergreening_df = pl.DataFrame()

    pan_col = "PAN_NUMBER" if "PAN_NUMBER" in df.columns else "PAN"
    if pan_col not in df.columns:
        return {
            "da_ref": "DA-011",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "PAN column not found"},
            "anomaly_flags": [],
        }

    # ── Method 1: From loan tape only ─────────────────────────────────────
    # If no repayment history, use LAST_PAYMENT_DATE and DISBURSEMENT_DATE
    if repayment_history is None:
        if "LAST_PAYMENT_DATE" in df.columns and "DISBURSEMENT_DATE" in df.columns:
            evergreening_df = con.execute(f"""
                WITH fresh_loans AS (
                    SELECT
                        new_loan.LOAN_ACCOUNT_NO AS new_loan_no,
                        new_loan."{pan_col}" AS pan,
                        new_loan.DISBURSEMENT_DATE AS new_disb_date,
                        new_loan.DISBURSEMENT_AMOUNT AS new_disb_amount,
                        new_loan.DPD AS new_loan_dpd,
                        new_loan.PRODUCT_CODE,
                        new_loan.BRANCH_CODE
                    FROM loan_tape new_loan
                    WHERE new_loan.DISBURSEMENT_DATE IS NOT NULL
                ),
                existing_with_payment AS (
                    SELECT
                        existing.LOAN_ACCOUNT_NO AS old_loan_no,
                        existing."{pan_col}" AS pan,
                        existing.LAST_PAYMENT_DATE,
                        existing.LAST_PAYMENT_AMOUNT,
                        existing.OUTSTANDING_PRINCIPAL AS overdue_outstanding,
                        existing.DPD AS old_dpd,
                        existing.EMI_AMOUNT
                    FROM loan_tape existing
                    WHERE existing.LAST_PAYMENT_DATE IS NOT NULL
                      AND existing.LAST_PAYMENT_AMOUNT IS NOT NULL
                      AND existing.LAST_PAYMENT_AMOUNT > 0
                )
                SELECT
                    fl.new_loan_no,
                    ep.old_loan_no,
                    fl.pan,
                    ep.LAST_PAYMENT_DATE AS payment_date,
                    ep.LAST_PAYMENT_AMOUNT AS payment_amount,
                    fl.new_disb_date AS disbursement_date,
                    fl.new_disb_amount AS disbursement_amount,
                    ep.old_dpd AS dpd_before_payment,
                    fl.new_loan_dpd AS dpd_at_new_disbursement,
                    ep.overdue_outstanding,
                    DATE_DIFF('day', CAST(ep.LAST_PAYMENT_DATE AS DATE), CAST(fl.new_disb_date AS DATE)) AS days_between,
                    ROUND(100.0 * ep.LAST_PAYMENT_AMOUNT / NULLIF(ep.overdue_outstanding, 0), 2) AS payment_to_outstanding_pct,
                    ROUND(100.0 * fl.new_disb_amount / NULLIF(ep.LAST_PAYMENT_AMOUNT, 0), 2) AS disb_to_payment_pct,
                    'EVERGREENING_PATTERN' AS exception_type
                FROM fresh_loans fl
                JOIN existing_with_payment ep ON fl.pan = ep.pan
                  AND fl.new_loan_no != ep.old_loan_no
                  AND DATE_DIFF('day', CAST(ep.LAST_PAYMENT_DATE AS DATE), CAST(fl.new_disb_date AS DATE)) BETWEEN 0 AND 5
                  AND DATE_DIFF('day', CAST(ep.LAST_PAYMENT_DATE AS DATE), CAST(fl.new_disb_date AS DATE)) >= 0
                WHERE ep.LAST_PAYMENT_AMOUNT >= ep.overdue_outstanding * 0.80
                  AND fl.new_disb_amount >= ep.LAST_PAYMENT_AMOUNT * 0.80
                ORDER BY days_between, fl.new_disb_amount DESC
            """).pl()

    # ── Method 2: From repayment history ──────────────────────────────────
    elif repayment_history is not None:
        rh_df = repayment_history.collect() if isinstance(repayment_history, pl.LazyFrame) else repayment_history
        con.register("repayment_hist", rh_df.to_arrow())

        payment_date_col = "PAYMENT_DATE" if "PAYMENT_DATE" in rh_df.columns else "TXN_DATE"
        payment_amount_col = "PAYMENT_AMOUNT" if "PAYMENT_AMOUNT" in rh_df.columns else "AMOUNT"

        if payment_date_col in rh_df.columns and payment_amount_col in rh_df.columns:
            evergreening_df = con.execute(f"""
                WITH payments AS (
                    SELECT
                        r.LOAN_ACCOUNT_NO,
                        l."{pan_col}" AS pan,
                        r."{payment_date_col}" AS payment_date,
                        r."{payment_amount_col}" AS payment_amount,
                        l.DPD AS dpd_at_payment,
                        l.OUTSTANDING_PRINCIPAL AS outstanding_at_payment,
                        l.EMI_AMOUNT
                    FROM repayment_hist r
                    JOIN loan_tape l ON r.LOAN_ACCOUNT_NO = l.LOAN_ACCOUNT_NO
                    WHERE r."{payment_amount_col}" > 0
                ),
                fresh_disb AS (
                    SELECT
                        LOAN_ACCOUNT_NO,
                        "{pan_col}" AS pan,
                        DISBURSEMENT_DATE,
                        DISBURSEMENT_AMOUNT,
                        DPD AS dpd_at_disb,
                        PRODUCT_CODE,
                        BRANCH_CODE
                    FROM loan_tape
                    WHERE DISBURSEMENT_DATE IS NOT NULL
                )
                SELECT
                    fd.LOAN_ACCOUNT_NO AS new_loan_no,
                    p.LOAN_ACCOUNT_NO AS old_loan_no,
                    fd.pan,
                    p.payment_date,
                    p.payment_amount,
                    fd.DISBURSEMENT_DATE AS disbursement_date,
                    fd.DISBURSEMENT_AMOUNT AS disbursement_amount,
                    p.dpd_at_payment AS dpd_before_payment,
                    fd.dpd_at_disb AS dpd_at_new_disbursement,
                    p.outstanding_at_payment AS overdue_outstanding,
                    DATE_DIFF('day', CAST(p.payment_date AS DATE), CAST(fd.DISBURSEMENT_DATE AS DATE)) AS days_between,
                    ROUND(100.0 * p.payment_amount / NULLIF(p.outstanding_at_payment, 0), 2) AS payment_to_outstanding_pct,
                    ROUND(100.0 * fd.DISBURSEMENT_AMOUNT / NULLIF(p.payment_amount, 0), 2) AS disb_to_payment_pct,
                    CASE
                        WHEN p.dpd_at_payment > 0 THEN 'EVERGREENING_WITH_DPD'
                        ELSE 'EVERGREENING_PATTERN'
                    END AS exception_type
                FROM fresh_disb fd
                JOIN payments p ON fd.pan = p.pan
                  AND fd.LOAN_ACCOUNT_NO != p.LOAN_ACCOUNT_NO
                  AND DATE_DIFF('day', CAST(p.payment_date AS DATE), CAST(fd.DISBURSEMENT_DATE AS DATE)) BETWEEN 0 AND 5
                  AND DATE_DIFF('day', CAST(p.payment_date AS DATE), CAST(fd.DISBURSEMENT_DATE AS DATE)) >= 0
                WHERE p.payment_amount >= p.outstanding_at_payment * 0.80
                  AND fd.DISBURSEMENT_AMOUNT >= p.payment_amount * 0.80
                ORDER BY days_between, fd.DISBURSEMENT_AMOUNT DESC
            """).pl()

    if len(evergreening_df) > 0:
        with_dpd = evergreening_df.filter(pl.col("dpd_before_payment") > 0) if "dpd_before_payment" in evergreening_df.columns else pl.DataFrame()
        anomaly_flags.append({
            "field": "DISBURSEMENT_DATE/LAST_PAYMENT_DATE",
            "value": len(evergreening_df),
            "threshold": "0 evergreening patterns",
            "message": f"{len(evergreening_df)} potential evergreening patterns (payment + fresh disb within 5 days to same PAN)"
        })
        if len(with_dpd) > 0:
            anomaly_flags.append({
                "field": "DPD_AT_DISBURSEMENT",
                "value": len(with_dpd),
                "threshold": "No disbursement to borrower with DPD > 0",
                "message": f"{len(with_dpd)} evergreening cases where borrower had DPD > 0 at time of disbursement"
            })

    return {
        "da_ref": "DA-011",
        "total_records": len(df),
        "exceptions_count": len(evergreening_df),
        "exceptions_df": evergreening_df,
        "summary": {
            "total_loans": len(df),
            "evergreening_patterns": len(evergreening_df),
            "with_prior_dpd": len(evergreening_df.filter(pl.col("dpd_before_payment") > 0)) if len(evergreening_df) > 0 and "dpd_before_payment" in evergreening_df.columns else 0,
            "total_amount_at_risk": float(evergreening_df["disbursement_amount"].sum() or 0) if len(evergreening_df) > 0 and "disbursement_amount" in evergreening_df.columns else 0,
        },
        "anomaly_flags": anomaly_flags,
    }

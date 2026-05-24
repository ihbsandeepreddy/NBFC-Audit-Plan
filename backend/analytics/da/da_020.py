"""
DA-020: Interest Income Cut-off Test
Flag next-period interest entries that belong to the audit period; compute cut-off adjustment.
LMS Risk Theme: 8
CAP Seq: R.20
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-020",
    "name": "Interest Income Cut-off Test",
    "description": "Flag next-period GL interest entries belonging to audit period; compute adjustment",
    "cap_seq": "R.20",
    "risk_theme": 8,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["next_period_gl"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Interest Income Cut-off:
    1. Flag interest entries in next_period_gl that relate to the audit period.
    2. Compute cut-off adjustment: interest accrued up to reporting_date but booked after.
    3. Flag interest booked in audit period but relating to future periods (overstatement).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    next_period_gl = kwargs.get("next_period_gl")

    # ── Compute accrued interest on loan tape (audit period) ───────────────
    days_in_period = kwargs.get("days_in_period", 90)

    accrual_by_loan = con.execute(f"""
        SELECT
            LOAN_ACCOUNT_NO, PRODUCT_CODE, BRANCH_CODE,
            OUTSTANDING_PRINCIPAL, INTEREST_RATE, IND_AS_STAGE,
            ROUND(OUTSTANDING_PRINCIPAL * (INTEREST_RATE / 100.0 / 365.0) * {days_in_period}, 2) AS computed_accrual,
            COALESCE(ACCRUED_INTEREST, 0) AS lms_accrued
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL > 0 AND INTEREST_RATE > 0
    """ if "ACCRUED_INTEREST" in df.columns else f"""
        SELECT
            LOAN_ACCOUNT_NO, PRODUCT_CODE, BRANCH_CODE,
            OUTSTANDING_PRINCIPAL, INTEREST_RATE, IND_AS_STAGE,
            ROUND(OUTSTANDING_PRINCIPAL * (INTEREST_RATE / 100.0 / 365.0) * {days_in_period}, 2) AS computed_accrual,
            NULL AS lms_accrued
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL > 0 AND INTEREST_RATE > 0
    """).pl()

    cutoff_exceptions = pl.DataFrame()
    cutoff_overstatement = 0.0
    cutoff_understatement = 0.0

    if next_period_gl is not None:
        if isinstance(next_period_gl, pl.DataFrame):
            ngl_df = next_period_gl
        elif isinstance(next_period_gl, pl.LazyFrame):
            ngl_df = next_period_gl.collect()
        else:
            ngl_df = pl.DataFrame(next_period_gl)

        con.register("next_gl", ngl_df.to_arrow())

        # Detect columns
        gl_date_col = "GL_DATE" if "GL_DATE" in ngl_df.columns else "ENTRY_DATE"
        gl_amount_col = "AMOUNT" if "AMOUNT" in ngl_df.columns else "INTEREST_AMOUNT"
        gl_period_col = "PERIOD" if "PERIOD" in ngl_df.columns else None
        gl_lan_col = "LOAN_ACCOUNT_NO" if "LOAN_ACCOUNT_NO" in ngl_df.columns else None

        if gl_date_col in ngl_df.columns and gl_amount_col in ngl_df.columns:
            # Find next-period entries with interest accrual date <= reporting_date
            accrual_date_col = "ACCRUAL_DATE" if "ACCRUAL_DATE" in ngl_df.columns else gl_date_col
            cutoff_exceptions = con.execute(f"""
                SELECT
                    n."{gl_date_col}" AS gl_booking_date,
                    n."{gl_amount_col}" AS interest_amount,
                    n."{accrual_date_col}" AS accrual_date,
                    CASE
                        WHEN CAST(n."{accrual_date_col}" AS DATE) <= CAST('{reporting_date}' AS DATE)
                             AND CAST(n."{gl_date_col}" AS DATE) > CAST('{reporting_date}' AS DATE)
                        THEN 'UNDERSTATEMENT_CUTOFF'
                        WHEN CAST(n."{accrual_date_col}" AS DATE) > CAST('{reporting_date}' AS DATE)
                             AND CAST(n."{gl_date_col}" AS DATE) <= CAST('{reporting_date}' AS DATE)
                        THEN 'OVERSTATEMENT_CUTOFF'
                        ELSE 'OK'
                    END AS exception_type
                FROM next_gl n
                WHERE
                    (CAST(n."{accrual_date_col}" AS DATE) <= CAST('{reporting_date}' AS DATE)
                     AND CAST(n."{gl_date_col}" AS DATE) > CAST('{reporting_date}' AS DATE))
                    OR
                    (CAST(n."{accrual_date_col}" AS DATE) > CAST('{reporting_date}' AS DATE)
                     AND CAST(n."{gl_date_col}" AS DATE) <= CAST('{reporting_date}' AS DATE))
                ORDER BY interest_amount DESC
            """).pl()

            if len(cutoff_exceptions) > 0:
                over = cutoff_exceptions.filter(pl.col("exception_type") == "OVERSTATEMENT_CUTOFF")
                under = cutoff_exceptions.filter(pl.col("exception_type") == "UNDERSTATEMENT_CUTOFF")
                cutoff_overstatement = float(over["interest_amount"].sum() or 0) if len(over) > 0 else 0
                cutoff_understatement = float(under["interest_amount"].sum() or 0) if len(under) > 0 else 0

                if abs(cutoff_overstatement) > 100000 or abs(cutoff_understatement) > 100000:
                    anomaly_flags.append({
                        "field": "GL_ENTRY_DATE",
                        "value": len(cutoff_exceptions),
                        "threshold": "Material cut-off difference <= ₹1,00,000",
                        "message": f"Interest cut-off exceptions: overstatement ₹{cutoff_overstatement:,.0f}, understatement ₹{cutoff_understatement:,.0f}"
                    })
    else:
        anomaly_flags.append({
            "field": "next_period_gl",
            "value": None,
            "threshold": "Required",
            "message": "Next period GL data not provided; cut-off test based on loan tape accruals only"
        })

    # ── Portfolio accrual summary ──────────────────────────────────────────
    accrual_summary = {
        "performing": round(float(
            accrual_by_loan.filter(pl.col("IND_AS_STAGE") != 3)["computed_accrual"].sum() or 0), 2),
        "npa": round(float(
            accrual_by_loan.filter(pl.col("IND_AS_STAGE") == 3)["computed_accrual"].sum() or 0), 2),
        "total": round(float(accrual_by_loan["computed_accrual"].sum() or 0), 2),
    }

    return {
        "da_ref": "DA-020",
        "total_records": len(df),
        "exceptions_count": len(cutoff_exceptions),
        "exceptions_df": cutoff_exceptions,
        "accrual_by_loan": accrual_by_loan,
        "summary": {
            "total_loans": len(df),
            "computed_interest_accrual": accrual_summary,
            "cutoff_exceptions": len(cutoff_exceptions),
            "overstatement_amount": round(cutoff_overstatement, 2),
            "understatement_amount": round(cutoff_understatement, 2),
            "net_adjustment_needed": round(cutoff_understatement - cutoff_overstatement, 2),
        },
        "anomaly_flags": anomaly_flags,
    }

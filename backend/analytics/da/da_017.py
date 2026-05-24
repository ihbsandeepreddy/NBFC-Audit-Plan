"""
DA-017: Interest Income Reconciliation
Compare expected interest income (computed) vs GL; flag NPA interest in P&L.
LMS Risk Theme: 8
CAP Seq: R.17
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-017",
    "name": "Interest Income Reconciliation",
    "description": "Expected vs GL interest income; flag NPA interest going to P&L instead of suspense",
    "cap_seq": "R.17",
    "risk_theme": 8,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["gl_interest"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Interest Income Reconciliation:
    1. Expected interest = OUTSTANDING_PRINCIPAL × INTEREST_RATE/365 × days_in_period.
    2. Compare to GL interest income.
    3. Separate performing vs NPA interest; NPA must go to suspense NOT P&L.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    days_in_period = kwargs.get("days_in_period", 90)  # Default to quarter

    # ── 1. Compute expected interest income from loan tape ─────────────────
    interest_computation = con.execute(f"""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            OUTSTANDING_PRINCIPAL,
            INTEREST_RATE,
            DPD,
            IND_AS_STAGE,
            ACCRUED_INTEREST,
            INTEREST_SUSPENSE,
            -- Daily accrual × days
            ROUND(OUTSTANDING_PRINCIPAL * (INTEREST_RATE / 100.0 / 365.0) * {days_in_period}, 2) AS expected_interest,
            CASE WHEN IND_AS_STAGE = 3 THEN 'NPA' ELSE 'PERFORMING' END AS loan_status
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL
          AND INTEREST_RATE IS NOT NULL
          AND OUTSTANDING_PRINCIPAL > 0
    """).pl()

    con.register("int_comp", interest_computation.to_arrow())

    # ── Portfolio-level interest summary ──────────────────────────────────
    portfolio_interest = con.execute("""
        SELECT
            loan_status,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(expected_interest) AS expected_interest_income,
            SUM(COALESCE(ACCRUED_INTEREST, 0)) AS lms_accrued_interest,
            SUM(COALESCE(INTEREST_SUSPENSE, 0)) AS interest_in_suspense
        FROM int_comp
        GROUP BY loan_status
    """).pl()

    total_expected = float(interest_computation["expected_interest"].sum() or 0)
    performing_expected = float(
        interest_computation.filter(pl.col("loan_status") == "PERFORMING")["expected_interest"].sum() or 0
    )
    npa_expected = float(
        interest_computation.filter(pl.col("loan_status") == "NPA")["expected_interest"].sum() or 0
    )

    # ── 2. Compare to GL ───────────────────────────────────────────────────
    gl_interest = kwargs.get("gl_interest")
    gl_comparison = {}
    gl_diff_df = pl.DataFrame()

    if gl_interest is not None:
        if isinstance(gl_interest, (int, float)):
            gl_total = float(gl_interest)
            difference = performing_expected - gl_total
            gl_comparison = {
                "expected_performing_interest": round(performing_expected, 2),
                "gl_interest_income": round(gl_total, 2),
                "difference": round(difference, 2),
                "pct_diff": round(abs(difference) / max(gl_total, 1) * 100, 2),
            }
            if abs(difference) > 100000:  # > ₹1L
                anomaly_flags.append({
                    "field": "INTEREST_INCOME",
                    "value": round(difference, 2),
                    "threshold": "Difference <= ₹1,00,000",
                    "message": f"LMS expected interest ₹{performing_expected:,.0f} vs GL ₹{gl_total:,.0f} (diff: ₹{difference:,.0f})"
                })
        elif isinstance(gl_interest, dict):
            # Product-wise GL interest
            gl_df = pl.DataFrame({
                "PRODUCT_CODE": list(gl_interest.keys()),
                "gl_interest": [float(v) for v in gl_interest.values()]
            })
            con.register("gl_int", gl_df.to_arrow())
            gl_diff_df = con.execute("""
                WITH lms_int AS (
                    SELECT PRODUCT_CODE,
                           SUM(expected_interest) AS lms_interest,
                           SUM(OUTSTANDING_PRINCIPAL) AS outstanding
                    FROM int_comp
                    WHERE loan_status = 'PERFORMING'
                    GROUP BY PRODUCT_CODE
                )
                SELECT
                    l.PRODUCT_CODE,
                    l.lms_interest,
                    g.gl_interest,
                    (l.lms_interest - g.gl_interest) AS difference,
                    ROUND(ABS(l.lms_interest - g.gl_interest) / NULLIF(g.gl_interest, 0) * 100, 2) AS pct_diff,
                    CASE WHEN ABS(l.lms_interest - g.gl_interest) > 100000 THEN 'MATERIAL_DIFF' ELSE 'OK' END AS flag
                FROM lms_int l
                LEFT JOIN gl_int g ON l.PRODUCT_CODE = g.PRODUCT_CODE
            """).pl()

            material_diffs = gl_diff_df.filter(pl.col("flag") == "MATERIAL_DIFF") if len(gl_diff_df) > 0 else pl.DataFrame()
            if len(material_diffs) > 0:
                anomaly_flags.append({
                    "field": "INTEREST_INCOME_BY_PRODUCT",
                    "value": len(material_diffs),
                    "threshold": "Difference <= ₹1,00,000 per product",
                    "message": f"{len(material_diffs)} products with material LMS vs GL interest income difference"
                })

    # ── 3. NPA interest in P&L (not suspense) ─────────────────────────────
    npa_pl_leakage = pl.DataFrame()
    if "ACCRUED_INTEREST" in df.columns and "INTEREST_SUSPENSE" in df.columns:
        npa_pl_leakage = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, INTEREST_RATE, DPD, IND_AS_STAGE,
                ACCRUED_INTEREST,
                INTEREST_SUSPENSE,
                (ACCRUED_INTEREST - COALESCE(INTEREST_SUSPENSE, 0)) AS pl_leakage,
                'NPA_INTEREST_IN_PL' AS exception_type
            FROM loan_tape
            WHERE IND_AS_STAGE = 3
              AND ACCRUED_INTEREST > COALESCE(INTEREST_SUSPENSE, 0)
              AND ACCRUED_INTEREST > 0
            ORDER BY pl_leakage DESC
        """).pl()

        if len(npa_pl_leakage) > 0:
            total_leakage = float(npa_pl_leakage["pl_leakage"].sum() or 0)
            anomaly_flags.append({
                "field": "ACCRUED_INTEREST/INTEREST_SUSPENSE",
                "value": len(npa_pl_leakage),
                "threshold": "NPA interest must be in suspense",
                "message": f"{len(npa_pl_leakage)} NPA accounts with interest accrued to P&L instead of suspense; ₹{total_leakage:,.0f} overstatement"
            })

    return {
        "da_ref": "DA-017",
        "total_records": len(df),
        "exceptions_count": len(npa_pl_leakage),
        "exceptions_df": npa_pl_leakage,
        "interest_computation": interest_computation,
        "portfolio_interest": portfolio_interest,
        "gl_comparison": gl_comparison,
        "gl_diff_by_product": gl_diff_df,
        "summary": {
            "total_loans": len(df),
            "total_expected_interest": round(total_expected, 2),
            "performing_expected": round(performing_expected, 2),
            "npa_expected": round(npa_expected, 2),
            "days_in_period": days_in_period,
            "npa_pl_leakage_count": len(npa_pl_leakage),
            "npa_pl_leakage_amount": round(float(npa_pl_leakage["pl_leakage"].sum() or 0), 2) if len(npa_pl_leakage) > 0 else 0,
        },
        "anomaly_flags": anomaly_flags,
    }

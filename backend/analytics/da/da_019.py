"""
DA-019: NPA Interest Accrual Test
Flag Stage 3 accounts where accrued interest exceeds suspense (NPA interest in P&L).
LMS Risk Theme: 8
CAP Seq: R.19
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-019",
    "name": "NPA Interest Accrual Test",
    "description": "Flag Stage 3 loans where ACCRUED_INTEREST > INTEREST_SUSPENSE (P&L contamination)",
    "cap_seq": "R.19",
    "risk_theme": 8,
    "required_inputs": ["loan_tape"],
    "optional_inputs": [],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    NPA Interest Accrual Test:
    1. Flag Stage 3 (NPA) accounts where ACCRUED_INTEREST > INTEREST_SUSPENSE.
    2. This means NPA interest going to P&L instead of interest suspense account.
    3. Compute total overstatement amount by product and branch.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # Check required columns
    has_accrued = "ACCRUED_INTEREST" in df.columns
    has_suspense = "INTEREST_SUSPENSE" in df.columns
    has_stage = "IND_AS_STAGE" in df.columns

    if not has_stage:
        return {
            "da_ref": "DA-019",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "IND_AS_STAGE column not found"},
            "anomaly_flags": [],
        }

    if not has_accrued and not has_suspense:
        # Use DPD >= 90 as NPA proxy and interest rate computation
        npa_interest_df = con.execute(f"""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, INTEREST_RATE, DPD, IND_AS_STAGE,
                ROUND(OUTSTANDING_PRINCIPAL * (INTEREST_RATE / 100.0 / 365.0) * 90, 2) AS estimated_accrued_interest,
                0 AS INTEREST_SUSPENSE,
                ROUND(OUTSTANDING_PRINCIPAL * (INTEREST_RATE / 100.0 / 365.0) * 90, 2) AS overstatement,
                'NPA_INTEREST_ESTIMATED_NO_SUSPENSE' AS exception_type
            FROM loan_tape
            WHERE IND_AS_STAGE = 3
              AND OUTSTANDING_PRINCIPAL > 0
              AND INTEREST_RATE > 0
            ORDER BY overstatement DESC
        """).pl()

        if len(npa_interest_df) > 0:
            overstatement = float(npa_interest_df["overstatement"].sum() or 0)
            anomaly_flags.append({
                "field": "ACCRUED_INTEREST",
                "value": len(npa_interest_df),
                "threshold": "NPA interest must be in suspense",
                "message": f"{len(npa_interest_df)} NPA accounts with estimated accrued interest; ACCRUED_INTEREST and INTEREST_SUSPENSE columns not available for precise test"
            })

        return {
            "da_ref": "DA-019",
            "total_records": len(df),
            "exceptions_count": len(npa_interest_df),
            "exceptions_df": npa_interest_df,
            "summary": {"note": "Estimated; ACCRUED_INTEREST and INTEREST_SUSPENSE not in dataset"},
            "anomaly_flags": anomaly_flags,
        }

    # ── Full test with both columns ────────────────────────────────────────
    accrued_col = "ACCRUED_INTEREST" if has_accrued else "0"
    suspense_col = "INTEREST_SUSPENSE" if has_suspense else "0"

    npa_pl_leakage = con.execute(f"""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            OUTSTANDING_PRINCIPAL, INTEREST_RATE, DPD, IND_AS_STAGE,
            {accrued_col} AS ACCRUED_INTEREST,
            {suspense_col} AS INTEREST_SUSPENSE,
            ({accrued_col} - COALESCE({suspense_col}, 0)) AS pl_overstatement,
            CASE
                WHEN {accrued_col} > 0 AND (COALESCE({suspense_col}, 0) = 0) THEN 'NPA_INTEREST_NO_SUSPENSE'
                WHEN {accrued_col} > COALESCE({suspense_col}, 0) THEN 'NPA_INTEREST_PARTIAL_SUSPENSE'
                ELSE 'OK'
            END AS exception_type
        FROM loan_tape
        WHERE IND_AS_STAGE = 3
          AND {accrued_col} > COALESCE({suspense_col}, 0)
          AND OUTSTANDING_PRINCIPAL > 0
        ORDER BY pl_overstatement DESC
    """).pl()

    if len(npa_pl_leakage) > 0:
        total_overstatement = float(npa_pl_leakage["pl_overstatement"].sum() or 0)
        no_suspense = npa_pl_leakage.filter(pl.col("exception_type") == "NPA_INTEREST_NO_SUSPENSE").height if has_suspense else len(npa_pl_leakage)
        anomaly_flags.append({
            "field": "ACCRUED_INTEREST/INTEREST_SUSPENSE",
            "value": len(npa_pl_leakage),
            "threshold": "Accrued <= Suspense for Stage 3",
            "message": f"{len(npa_pl_leakage)} NPA accounts with P&L overstatement of ₹{total_overstatement:,.0f} (interest not fully in suspense)"
        })

    # ── By product and branch ──────────────────────────────────────────────
    by_product = pl.DataFrame()
    if len(npa_pl_leakage) > 0:
        con.register("npa_leakage", npa_pl_leakage.to_arrow())
        by_product = con.execute("""
            SELECT
                PRODUCT_CODE,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS npa_outstanding,
                SUM(pl_overstatement) AS total_overstatement
            FROM npa_leakage
            GROUP BY PRODUCT_CODE
            ORDER BY total_overstatement DESC
        """).pl()

    # ── NPA interest summary ───────────────────────────────────────────────
    npa_summary = con.execute(f"""
        SELECT
            COUNT(*) AS npa_account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS npa_outstanding,
            SUM({accrued_col}) AS total_accrued,
            SUM({suspense_col}) AS total_suspense,
            SUM({accrued_col} - COALESCE({suspense_col}, 0)) AS total_pl_overstatement
        FROM loan_tape
        WHERE IND_AS_STAGE = 3
          AND OUTSTANDING_PRINCIPAL > 0
    """).pl().to_dicts()[0] if len(df) > 0 else {}

    return {
        "da_ref": "DA-019",
        "total_records": len(df),
        "exceptions_count": len(npa_pl_leakage),
        "exceptions_df": npa_pl_leakage,
        "overstatement_by_product": by_product,
        "summary": {
            "total_loans": len(df),
            "npa_accounts": int(npa_summary.get("npa_account_count") or 0),
            "total_npa_outstanding": round(float(npa_summary.get("npa_outstanding") or 0), 2),
            "total_accrued_interest": round(float(npa_summary.get("total_accrued") or 0), 2),
            "total_in_suspense": round(float(npa_summary.get("total_suspense") or 0), 2),
            "total_pl_overstatement": round(float(npa_summary.get("total_pl_overstatement") or 0), 2),
            "leakage_accounts": len(npa_pl_leakage),
        },
        "anomaly_flags": anomaly_flags,
    }

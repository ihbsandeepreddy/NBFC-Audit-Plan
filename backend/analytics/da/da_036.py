"""
DA-036: ECL Model Completeness
Verify all active accounts are in ECL computation; cross-check totals.
LMS Risk Theme: 3
CAP Seq: R.36
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-036",
    "name": "ECL Model Completeness",
    "description": "All active accounts have ECL; loan tape total = Stage 1+2+3 sum; no missing segments",
    "cap_seq": "R.36",
    "risk_theme": 3,
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
    ECL Model Completeness:
    1. Verify all active accounts are in ECL computation (no missing segments).
    2. Cross-check: loan_tape total outstanding = Stage 1 + Stage 2 + Stage 3 totals.
    3. Flag accounts with IND_AS_STAGE but no TOTAL_ECL_PROVISION (null/0).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    ecl_col = "TOTAL_ECL_PROVISION" if "TOTAL_ECL_PROVISION" in df.columns else None

    # ── 1. Accounts with stage but no ECL provision ───────────────────────
    no_ecl_df = pl.DataFrame()
    if ecl_col:
        no_ecl_df = con.execute(f"""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                IND_AS_STAGE, DPD, OUTSTANDING_PRINCIPAL,
                "{ecl_col}" AS ecl_provision,
                'STAGED_NO_ECL_PROVISION' AS exception_type
            FROM loan_tape
            WHERE IND_AS_STAGE IS NOT NULL
              AND IND_AS_STAGE > 0
              AND OUTSTANDING_PRINCIPAL > 0
              AND ("{ecl_col}" IS NULL OR "{ecl_col}" = 0)
            ORDER BY OUTSTANDING_PRINCIPAL DESC
        """).pl()

        if len(no_ecl_df) > 0:
            amount = float(no_ecl_df["OUTSTANDING_PRINCIPAL"].sum() or 0)
            anomaly_flags.append({
                "field": "TOTAL_ECL_PROVISION",
                "value": len(no_ecl_df),
                "threshold": "All staged accounts must have ECL",
                "message": f"{len(no_ecl_df)} accounts with stage classification but zero/null ECL; ₹{amount:,.0f} outstanding"
            })

    # ── 2. Stage completeness check ───────────────────────────────────────
    # Cross-check: sum of staged = total outstanding
    stage_totals = con.execute("""
        SELECT
            IND_AS_STAGE,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS outstanding,
            SUM(COALESCE(TOTAL_ECL_PROVISION, 0)) AS ecl_provision
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL
        GROUP BY IND_AS_STAGE
    """ if ecl_col else """
        SELECT
            IND_AS_STAGE,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS outstanding,
            NULL AS ecl_provision
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL
        GROUP BY IND_AS_STAGE
    """).pl()

    total_os = float(df["OUTSTANDING_PRINCIPAL"].sum() or 0) if "OUTSTANDING_PRINCIPAL" in df.columns else 0
    staged_os = float(stage_totals["outstanding"].sum() or 0)
    unstaged_os = total_os - staged_os

    if abs(unstaged_os) > 1:  # Material difference
        anomaly_flags.append({
            "field": "IND_AS_STAGE",
            "value": abs(unstaged_os),
            "threshold": "Staged total == portfolio total",
            "message": f"Stage totals {staged_os:,.0f} != portfolio total {total_os:,.0f} (gap: {unstaged_os:,.0f}) — accounts may be missing from ECL model"
        })

    # ── 3. Missing stage accounts ─────────────────────────────────────────
    null_stage_df = con.execute("""
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
            DPD, OUTSTANDING_PRINCIPAL,
            NULL AS IND_AS_STAGE,
            'NULL_IND_AS_STAGE' AS exception_type
        FROM loan_tape
        WHERE IND_AS_STAGE IS NULL
          AND OUTSTANDING_PRINCIPAL > 0
        ORDER BY OUTSTANDING_PRINCIPAL DESC
    """).pl()

    if len(null_stage_df) > 0:
        null_amount = float(null_stage_df["OUTSTANDING_PRINCIPAL"].sum() or 0)
        anomaly_flags.append({
            "field": "IND_AS_STAGE",
            "value": len(null_stage_df),
            "threshold": "All active accounts must have IND_AS_STAGE",
            "message": f"{len(null_stage_df)} accounts with null IND_AS_STAGE; ₹{null_amount:,.0f} outside ECL model"
        })

    # ── 4. Product/branch ECL completeness ────────────────────────────────
    segment_completeness = pl.DataFrame()
    if ecl_col and "PRODUCT_CODE" in df.columns:
        segment_completeness = con.execute(f"""
            SELECT
                PRODUCT_CODE,
                COUNT(*) AS total_accounts,
                SUM(CASE WHEN "{ecl_col}" IS NULL OR "{ecl_col}" = 0 THEN 1 ELSE 0 END) AS missing_ecl,
                ROUND(100.0 * SUM(CASE WHEN "{ecl_col}" IS NULL OR "{ecl_col}" = 0 THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2) AS missing_ecl_pct,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                SUM("{ecl_col}") AS total_ecl
            FROM loan_tape
            WHERE OUTSTANDING_PRINCIPAL > 0 AND IND_AS_STAGE IS NOT NULL
            GROUP BY PRODUCT_CODE
            ORDER BY missing_ecl_pct DESC
        """).pl()

    exc_frames = [f for f in [no_ecl_df, null_stage_df] if len(f) > 0]
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
        "da_ref": "DA-036",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "stage_totals": stage_totals,
        "segment_completeness": segment_completeness,
        "summary": {
            "total_records": len(df),
            "total_outstanding": round(total_os, 2),
            "staged_outstanding": round(staged_os, 2),
            "unstaged_outstanding": round(unstaged_os, 2),
            "null_stage_accounts": len(null_stage_df),
            "no_ecl_accounts": len(no_ecl_df),
        },
        "anomaly_flags": anomaly_flags,
    }

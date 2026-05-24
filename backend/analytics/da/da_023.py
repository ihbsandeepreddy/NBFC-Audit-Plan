"""
DA-023: Restructured Accounts Observation Period
Flag restructured accounts upgraded before 12 months observation period; compute ECL impact.
LMS Risk Theme: 4
CAP Seq: R.23
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-023",
    "name": "Restructured Accounts Observation Period",
    "description": "Flag restructured accounts upgraded Stage 2->1 before 12-month observation period",
    "cap_seq": "R.23",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": [],
}

STAGE2_ECL_RATE = 0.030
STAGE1_ECL_RATE = 0.005


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Restructured Accounts Observation Period:
    1. Flag IS_RESTRUCTURED=True accounts upgraded Stage 2->1 before 12 months from RESTRUCTURE_DATE.
    2. Compute ECL impact of premature upgrade.
    3. Flag accounts where restructure date is null but IS_RESTRUCTURED = True.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    has_restructured = "IS_RESTRUCTURED" in df.columns
    has_restructure_date = "RESTRUCTURE_DATE" in df.columns

    if not has_restructured:
        return {
            "da_ref": "DA-023",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "IS_RESTRUCTURED column not found"},
            "anomaly_flags": [],
        }

    # ── 1. Restructured accounts in Stage 1 (potentially premature upgrade)
    if has_restructure_date:
        premature_upgrade = con.execute(f"""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, DPD, IND_AS_STAGE,
                IS_RESTRUCTURED, RESTRUCTURE_DATE,
                DATE_DIFF('month', CAST(RESTRUCTURE_DATE AS DATE), CAST('{reporting_date}' AS DATE)) AS months_since_restructure,
                -- ECL impact: should be Stage 2 rate instead of Stage 1
                ROUND(OUTSTANDING_PRINCIPAL * ({STAGE2_ECL_RATE} - {STAGE1_ECL_RATE}), 2) AS additional_ecl_needed,
                'PREMATURE_UPGRADE_RESTRUCTURED' AS exception_type
            FROM loan_tape
            WHERE IS_RESTRUCTURED = TRUE
              AND IND_AS_STAGE = 1
              AND RESTRUCTURE_DATE IS NOT NULL
              AND DATE_DIFF('month', CAST(RESTRUCTURE_DATE AS DATE), CAST('{reporting_date}' AS DATE)) < 12
              AND OUTSTANDING_PRINCIPAL > 0
            ORDER BY additional_ecl_needed DESC
        """).pl()
    else:
        # If no restructure_date, flag all restructured Stage 1 accounts
        premature_upgrade = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, DPD, IND_AS_STAGE,
                IS_RESTRUCTURED,
                NULL AS RESTRUCTURE_DATE,
                NULL AS months_since_restructure,
                ROUND(OUTSTANDING_PRINCIPAL * 0.025, 2) AS additional_ecl_needed,
                'RESTRUCTURED_IN_STAGE1_NO_DATE' AS exception_type
            FROM loan_tape
            WHERE IS_RESTRUCTURED = TRUE
              AND IND_AS_STAGE = 1
              AND OUTSTANDING_PRINCIPAL > 0
            ORDER BY additional_ecl_needed DESC
        """).pl()

    if len(premature_upgrade) > 0:
        total_ecl_impact = float(premature_upgrade["additional_ecl_needed"].sum() or 0)
        anomaly_flags.append({
            "field": "IS_RESTRUCTURED/IND_AS_STAGE",
            "value": len(premature_upgrade),
            "threshold": "12 months observation in Stage 2 before upgrade",
            "message": f"{len(premature_upgrade)} restructured accounts potentially upgraded prematurely; ECL impact ₹{total_ecl_impact:,.0f}"
        })

    # ── 2. Restructured accounts with null RESTRUCTURE_DATE ───────────────
    null_date_restructured = pl.DataFrame()
    if has_restructure_date:
        null_date_restructured = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, DPD, IND_AS_STAGE,
                'RESTRUCTURED_NULL_DATE' AS exception_type
            FROM loan_tape
            WHERE IS_RESTRUCTURED = TRUE
              AND RESTRUCTURE_DATE IS NULL
        """).pl()

        if len(null_date_restructured) > 0:
            anomaly_flags.append({
                "field": "RESTRUCTURE_DATE",
                "value": len(null_date_restructured),
                "threshold": "Restructure date required when IS_RESTRUCTURED=True",
                "message": f"{len(null_date_restructured)} restructured accounts without RESTRUCTURE_DATE"
            })

    # ── 3. Restructured accounts summary ──────────────────────────────────
    restructured_summary = con.execute(f"""
        SELECT
            IND_AS_STAGE,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            {f"AVG(DATE_DIFF('month', CAST(RESTRUCTURE_DATE AS DATE), CAST('{reporting_date}' AS DATE))) AS avg_months_since_restructure" if has_restructure_date else "NULL AS avg_months_since_restructure"}
        FROM loan_tape
        WHERE IS_RESTRUCTURED = TRUE
        GROUP BY IND_AS_STAGE
        ORDER BY IND_AS_STAGE
    """).pl()

    exc_frames = [f for f in [premature_upgrade, null_date_restructured] if len(f) > 0]
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
        "da_ref": "DA-023",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "premature_upgrades": premature_upgrade,
        "null_date_restructured": null_date_restructured,
        "restructured_summary": restructured_summary,
        "summary": {
            "total_loans": len(df),
            "total_restructured": df.filter(pl.col("IS_RESTRUCTURED") == True).height if "IS_RESTRUCTURED" in df.columns else 0,
            "premature_upgrades": len(premature_upgrade),
            "ecl_impact": round(float(premature_upgrade["additional_ecl_needed"].sum() or 0), 2) if len(premature_upgrade) > 0 else 0,
        },
        "anomaly_flags": anomaly_flags,
    }

"""
DA-004: Rate Override Detection
Compare LMS interest rates to sanctioned rates and credit policy floor.
LMS Risk Theme: 3
CAP Seq: R.04
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-004",
    "name": "Rate Override Detection",
    "description": "Compare LMS interest rate to sanctioned rate; flag overrides and below-floor rates",
    "cap_seq": "R.04",
    "risk_theme": 3,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["sanction_data", "credit_policy"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Rate Override Detection:
    1. Compare INTEREST_RATE in loan_tape vs sanctioned rate (kwargs['sanction_data']).
    2. Flag where LMS rate ≠ sanctioned rate (allowing ±0.01% rounding tolerance).
    3. Group by branch, product, time period.
    4. Flag rates below RATE_FLOOR in credit policy.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    rate_overrides = pl.DataFrame()
    below_floor = pl.DataFrame()

    # ── 1. Compare LMS rate vs sanction rate ─────────────────────────────
    sanction_data = kwargs.get("sanction_data")
    if sanction_data is not None:
        if isinstance(sanction_data, pl.DataFrame):
            sanc_df = sanction_data
        elif isinstance(sanction_data, pl.LazyFrame):
            sanc_df = sanction_data.collect()
        else:
            sanc_df = pl.DataFrame(sanction_data)

        con.register("sanctions", sanc_df.to_arrow())

        # Determine the sanctioned rate column name
        sanc_rate_col = "SANCTIONED_RATE"
        if "SANCTIONED_RATE" not in sanc_df.columns:
            for candidate in ["sanction_rate", "sanctioned_roi", "approved_rate", "INTEREST_RATE"]:
                if candidate in sanc_df.columns:
                    sanc_rate_col = candidate
                    break

        rate_overrides = con.execute(f"""
            SELECT
                l.LOAN_ACCOUNT_NO,
                l.PAN_NUMBER,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.DISBURSEMENT_DATE,
                l.INTEREST_RATE AS lms_rate,
                s."{sanc_rate_col}" AS sanctioned_rate,
                (l.INTEREST_RATE - s."{sanc_rate_col}") AS rate_difference,
                'RATE_OVERRIDE' AS exception_type
            FROM loan_tape l
            JOIN sanctions s ON l.LOAN_ACCOUNT_NO = s.LOAN_ACCOUNT_NO
            WHERE ABS(l.INTEREST_RATE - s."{sanc_rate_col}") > 0.01
            ORDER BY ABS(l.INTEREST_RATE - s."{sanc_rate_col}") DESC
        """).pl()

        if len(rate_overrides) > 0:
            anomaly_flags.append({
                "field": "INTEREST_RATE",
                "value": len(rate_overrides),
                "threshold": "LMS rate == Sanctioned rate (±0.01%)",
                "message": f"{len(rate_overrides)} accounts where LMS rate ≠ sanctioned rate"
            })

    # ── 2. Group rate overrides by branch, product, period ────────────────
    branch_product_summary = pl.DataFrame()
    if len(rate_overrides) > 0 and "BRANCH_CODE" in rate_overrides.columns:
        con.register("rate_overrides", rate_overrides.to_arrow())
        branch_product_summary = con.execute("""
            SELECT
                BRANCH_CODE,
                PRODUCT_CODE,
                COUNT(*) AS override_count,
                AVG(rate_difference) AS avg_rate_diff,
                MIN(rate_difference) AS min_rate_diff,
                MAX(rate_difference) AS max_rate_diff,
                SUM(CASE WHEN rate_difference < 0 THEN 1 ELSE 0 END) AS below_sanction_count
            FROM rate_overrides
            GROUP BY BRANCH_CODE, PRODUCT_CODE
            ORDER BY override_count DESC
        """).pl()

    # ── 3. Flag rates below RATE_FLOOR in credit policy ───────────────────
    if credit_policy is not None and "INTEREST_RATE" in df.columns and "PRODUCT_CODE" in df.columns:
        # Build policy floors table
        policy_rows = []
        if isinstance(credit_policy, list):
            for p in credit_policy:
                if "product_code" in p and "rate_floor" in p:
                    policy_rows.append({"product_code": p["product_code"], "rate_floor": float(p["rate_floor"])})
        elif isinstance(credit_policy, dict):
            for prod, params in credit_policy.items():
                if isinstance(params, dict) and "rate_floor" in params:
                    policy_rows.append({"product_code": prod, "rate_floor": float(params["rate_floor"])})

        if policy_rows:
            policy_df = pl.DataFrame(policy_rows)
            con.register("policy_floors", policy_df.to_arrow())
            below_floor = con.execute("""
                SELECT
                    l.LOAN_ACCOUNT_NO,
                    l.PAN_NUMBER,
                    l.PRODUCT_CODE,
                    l.BRANCH_CODE,
                    l.INTEREST_RATE,
                    p.rate_floor,
                    (p.rate_floor - l.INTEREST_RATE) AS shortfall,
                    'RATE_BELOW_POLICY_FLOOR' AS exception_type
                FROM loan_tape l
                JOIN policy_floors p ON l.PRODUCT_CODE = p.product_code
                WHERE l.INTEREST_RATE < p.rate_floor
                ORDER BY shortfall DESC
            """).pl()

            if len(below_floor) > 0:
                anomaly_flags.append({
                    "field": "INTEREST_RATE",
                    "value": len(below_floor),
                    "threshold": "rate >= rate_floor per credit policy",
                    "message": f"{len(below_floor)} accounts with rate below credit policy floor"
                })
    elif "INTEREST_RATE" in df.columns:
        # Generic floor check: flag rates < 6% as suspiciously low for NBFC
        below_floor = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                INTEREST_RATE,
                6.0 AS rate_floor,
                (6.0 - INTEREST_RATE) AS shortfall,
                'RATE_BELOW_GENERIC_FLOOR' AS exception_type
            FROM loan_tape
            WHERE INTEREST_RATE < 6.0
        """).pl()

        if len(below_floor) > 0:
            anomaly_flags.append({
                "field": "INTEREST_RATE",
                "value": len(below_floor),
                "threshold": "6% generic floor",
                "message": f"{len(below_floor)} accounts with rate below 6% (NBFC generic floor)"
            })

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [rate_overrides, below_floor] if len(f) > 0]
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

    # Product-level rate distribution
    rate_dist = pl.DataFrame()
    if "INTEREST_RATE" in df.columns and "PRODUCT_CODE" in df.columns:
        rate_dist = con.execute("""
            SELECT
                PRODUCT_CODE,
                COUNT(*) AS loan_count,
                MIN(INTEREST_RATE) AS min_rate,
                MAX(INTEREST_RATE) AS max_rate,
                AVG(INTEREST_RATE) AS avg_rate,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY INTEREST_RATE) AS p25_rate,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY INTEREST_RATE) AS p75_rate
            FROM loan_tape
            WHERE INTEREST_RATE IS NOT NULL
            GROUP BY PRODUCT_CODE
            ORDER BY PRODUCT_CODE
        """).pl()

    return {
        "da_ref": "DA-004",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "rate_overrides": rate_overrides,
        "below_floor": below_floor,
        "branch_product_summary": branch_product_summary,
        "rate_distribution": rate_dist,
        "summary": {
            "total_loans": len(df),
            "rate_overrides_count": len(rate_overrides),
            "below_floor_count": len(below_floor),
            "sanction_data_provided": sanction_data is not None,
        },
        "anomaly_flags": anomaly_flags,
    }

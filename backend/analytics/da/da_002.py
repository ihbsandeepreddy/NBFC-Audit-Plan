"""
DA-002: LOS-LMS Reconciliation
Reconcile LOS sanctions to LMS disbursements; detect ghost loans and stale sanctions.
LMS Risk Theme: 13
CAP Seq: S.01
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-002",
    "name": "LOS-LMS Reconciliation",
    "description": "Reconcile LOS sanctions against LMS disbursements; flag ghost loans and stale sanctions",
    "cap_seq": "S.01",
    "risk_theme": 13,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["los_sanctions"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    LOS-LMS Reconciliation:
    1. Find LMS disbursements without a matching LOS sanction (ghost loans).
    2. Find LOS sanctions aged >90 days without disbursement.
    3. Flag branches with conversion rate (sanctions->disbursements) outside ±2 SD of mean.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("lms", df.to_arrow())

    anomaly_flags = []
    los_sanctions = kwargs.get("los_sanctions")

    # ── If no LOS data provided, run basic LMS checks ─────────────────────
    if los_sanctions is None:
        # Flag disbursements missing sanction reference columns
        missing_sanction_ref = con.execute("""
            SELECT LOAN_ACCOUNT_NO, PRODUCT_CODE, BRANCH_CODE,
                   DISBURSEMENT_DATE, DISBURSEMENT_AMOUNT,
                   'MISSING_LOS_DATA' AS exception_type
            FROM lms
            WHERE SANCTION_DATE IS NULL OR SANCTION_AMOUNT IS NULL
        """ if "SANCTION_DATE" in df.columns else """
            SELECT LOAN_ACCOUNT_NO, PRODUCT_CODE, BRANCH_CODE,
                   DISBURSEMENT_DATE, DISBURSEMENT_AMOUNT,
                   'NO_LOS_PROVIDED' AS exception_type
            FROM lms
            LIMIT 0
        """).pl()

        return {
            "da_ref": "DA-002",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {
                "note": "LOS sanctions data not provided; basic LMS checks run",
                "lms_records": len(df),
            },
            "anomaly_flags": [{"field": "los_sanctions", "value": None, "threshold": "Required", "message": "LOS sanctions data not provided; full reconciliation skipped"}],
        }

    # ── Register LOS sanctions ─────────────────────────────────────────────
    if isinstance(los_sanctions, pl.DataFrame):
        los_df = los_sanctions
    elif isinstance(los_sanctions, pl.LazyFrame):
        los_df = los_sanctions.collect()
    else:
        los_df = pl.DataFrame(los_sanctions)

    con.register("los", los_df.to_arrow())

    # ── 1. Ghost loans: LMS disbursements without matching LOS sanction ────
    # Match on LOAN_ACCOUNT_NO (or closest available key)
    ghost_loans = con.execute("""
        SELECT
            l.LOAN_ACCOUNT_NO,
            l.PAN_NUMBER,
            l.PRODUCT_CODE,
            l.BRANCH_CODE,
            l.DISBURSEMENT_DATE,
            l.DISBURSEMENT_AMOUNT,
            'GHOST_LOAN_NO_LOS_SANCTION' AS exception_type
        FROM lms l
        LEFT JOIN los s ON l.LOAN_ACCOUNT_NO = s.LOAN_ACCOUNT_NO
        WHERE s.LOAN_ACCOUNT_NO IS NULL
        ORDER BY l.DISBURSEMENT_AMOUNT DESC NULLS LAST
    """).pl()

    if len(ghost_loans) > 0:
        ghost_amount = float(ghost_loans["DISBURSEMENT_AMOUNT"].sum() or 0)
        anomaly_flags.append({
            "field": "LOAN_ACCOUNT_NO",
            "value": len(ghost_loans),
            "threshold": 0,
            "message": f"{len(ghost_loans)} LMS disbursements with no matching LOS sanction (ghost loans); ₹{ghost_amount:,.0f} at risk"
        })

    # ── 2. Stale LOS sanctions: aged >90 days without disbursement ─────────
    # Need sanction_date and reporting_date
    stale_sanctions = pl.DataFrame()
    if "SANCTION_DATE" in los_df.columns:
        stale_sanctions = con.execute(f"""
            SELECT
                s.LOAN_ACCOUNT_NO,
                s.SANCTION_DATE,
                s.SANCTION_AMOUNT,
                DATE_DIFF('day', CAST(s.SANCTION_DATE AS DATE), CAST('{reporting_date}' AS DATE)) AS days_since_sanction,
                'STALE_SANCTION_NO_DISBURSEMENT' AS exception_type
            FROM los s
            LEFT JOIN lms l ON s.LOAN_ACCOUNT_NO = l.LOAN_ACCOUNT_NO
            WHERE l.LOAN_ACCOUNT_NO IS NULL
              AND DATE_DIFF('day', CAST(s.SANCTION_DATE AS DATE), CAST('{reporting_date}' AS DATE)) > 90
            ORDER BY days_since_sanction DESC
        """).pl()

        if len(stale_sanctions) > 0:
            stale_amount = float(stale_sanctions["SANCTION_AMOUNT"].sum() or 0) if "SANCTION_AMOUNT" in stale_sanctions.columns else 0
            anomaly_flags.append({
                "field": "SANCTION_DATE",
                "value": len(stale_sanctions),
                "threshold": "90 days",
                "message": f"{len(stale_sanctions)} LOS sanctions aged >90 days without disbursement; ₹{stale_amount:,.0f} sanctioned amount"
            })

    # ── 3. Branch conversion rate analysis ────────────────────────────────
    branch_analysis = pl.DataFrame()
    if "BRANCH_CODE" in df.columns and "BRANCH_CODE" in los_df.columns:
        branch_analysis = con.execute("""
            WITH lms_branch AS (
                SELECT BRANCH_CODE, COUNT(*) AS disbursements
                FROM lms
                GROUP BY BRANCH_CODE
            ),
            los_branch AS (
                SELECT BRANCH_CODE, COUNT(*) AS sanctions
                FROM los
                GROUP BY BRANCH_CODE
            ),
            branch_conv AS (
                SELECT
                    COALESCE(l.BRANCH_CODE, s.BRANCH_CODE) AS BRANCH_CODE,
                    COALESCE(l.disbursements, 0) AS disbursements,
                    COALESCE(s.sanctions, 0) AS sanctions,
                    CASE WHEN COALESCE(s.sanctions, 0) > 0
                         THEN CAST(COALESCE(l.disbursements, 0) AS DOUBLE) / s.sanctions
                         ELSE NULL
                    END AS conversion_rate
                FROM lms_branch l
                FULL OUTER JOIN los_branch s ON l.BRANCH_CODE = s.BRANCH_CODE
            ),
            stats AS (
                SELECT
                    AVG(conversion_rate) AS mean_rate,
                    STDDEV(conversion_rate) AS std_rate
                FROM branch_conv
                WHERE conversion_rate IS NOT NULL
            )
            SELECT
                bc.BRANCH_CODE,
                bc.disbursements,
                bc.sanctions,
                bc.conversion_rate,
                s.mean_rate,
                s.std_rate,
                CASE
                    WHEN bc.conversion_rate IS NULL THEN 'NO_DATA'
                    WHEN ABS(bc.conversion_rate - s.mean_rate) > 2 * s.std_rate THEN 'OUTLIER_CONVERSION'
                    ELSE 'OK'
                END AS conversion_flag
            FROM branch_conv bc, stats s
            ORDER BY bc.BRANCH_CODE
        """).pl()

        outlier_branches = branch_analysis.filter(pl.col("conversion_flag") == "OUTLIER_CONVERSION")
        if len(outlier_branches) > 0:
            anomaly_flags.append({
                "field": "BRANCH_CONVERSION_RATE",
                "value": len(outlier_branches),
                "threshold": "±2 SD from mean",
                "message": f"{len(outlier_branches)} branches with conversion rate outside ±2 SD of mean"
            })

    # ── Compile combined exceptions ────────────────────────────────────────
    exceptions_frames = [f for f in [ghost_loans, stale_sanctions] if len(f) > 0]
    if exceptions_frames:
        # Normalize columns before concat
        all_exc_cols = set()
        for f in exceptions_frames:
            all_exc_cols.update(f.columns)
        normalized = []
        for f in exceptions_frames:
            for col in all_exc_cols:
                if col not in f.columns:
                    f = f.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))
            normalized.append(f.select(sorted(all_exc_cols)))
        exceptions_df = pl.concat(normalized)
    else:
        exceptions_df = pl.DataFrame()

    total_exc = len(ghost_loans) + len(stale_sanctions)

    return {
        "da_ref": "DA-002",
        "total_records": len(df),
        "exceptions_count": total_exc,
        "exceptions_df": exceptions_df,
        "ghost_loans": ghost_loans,
        "stale_sanctions": stale_sanctions,
        "branch_analysis": branch_analysis,
        "summary": {
            "lms_disbursement_count": len(df),
            "los_sanction_count": len(los_df),
            "ghost_loans_count": len(ghost_loans),
            "ghost_loans_amount": float(ghost_loans["DISBURSEMENT_AMOUNT"].sum() or 0) if len(ghost_loans) > 0 else 0,
            "stale_sanctions_count": len(stale_sanctions),
            "outlier_branches": len(branch_analysis.filter(pl.col("conversion_flag") == "OUTLIER_CONVERSION")) if len(branch_analysis) > 0 else 0,
        },
        "anomaly_flags": anomaly_flags,
    }

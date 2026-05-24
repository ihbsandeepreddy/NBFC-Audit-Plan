"""
DA-027: Bureau Score Anomaly
Flag below-policy bureau scores, stale reports, and score vs delinquency mismatch.
LMS Risk Theme: 6
CAP Seq: R.27
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-027",
    "name": "Bureau Score Anomaly",
    "description": "Flag below-policy CIBIL, stale bureau reports, and high-score delinquency mismatch",
    "cap_seq": "R.27",
    "risk_theme": 6,
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
    Bureau Score Anomaly:
    1. Flag BUREAU_SCORE below credit policy minimum.
    2. Flag loans disbursed > 90 days after BUREAU_INQUIRY_DATE (stale report).
    3. Flag high score (>750) accounts with DPD > 30 (score vs delinquency mismatch).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # Get product-wise min bureau score from credit policy
    min_bureau_by_product = {}
    if credit_policy:
        if isinstance(credit_policy, list):
            for p in credit_policy:
                if "product_code" in p and "min_bureau_score" in p:
                    min_bureau_by_product[p["product_code"]] = int(p["min_bureau_score"])
        elif isinstance(credit_policy, dict):
            for prod, params in credit_policy.items():
                if isinstance(params, dict) and "min_bureau_score" in params:
                    min_bureau_by_product[prod] = int(params["min_bureau_score"])

    default_min_score = 600  # Generic NBFC floor

    # ── 1. Below-policy bureau score ──────────────────────────────────────
    below_min_score = pl.DataFrame()
    if "BUREAU_SCORE" in df.columns:
        if min_bureau_by_product:
            policy_df = pl.DataFrame({
                "product_code": list(min_bureau_by_product.keys()),
                "min_score": list(min_bureau_by_product.values())
            })
            con.register("bureau_policy", policy_df.to_arrow())
            below_min_score = con.execute(f"""
                SELECT
                    l.LOAN_ACCOUNT_NO, l.PAN_NUMBER, l.PRODUCT_CODE, l.BRANCH_CODE,
                    l.BUREAU_SCORE, l.DISBURSEMENT_AMOUNT, l.DPD, l.IND_AS_STAGE,
                    COALESCE(p.min_score, {default_min_score}) AS min_required_score,
                    'BUREAU_BELOW_POLICY_MIN' AS exception_type
                FROM loan_tape l
                LEFT JOIN bureau_policy p ON l.PRODUCT_CODE = p.product_code
                WHERE l.BUREAU_SCORE < COALESCE(p.min_score, {default_min_score})
                  AND l.BUREAU_SCORE IS NOT NULL
                ORDER BY l.BUREAU_SCORE ASC
            """).pl()
        else:
            below_min_score = con.execute(f"""
                SELECT
                    LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                    BUREAU_SCORE, DISBURSEMENT_AMOUNT, DPD, IND_AS_STAGE,
                    {default_min_score} AS min_required_score,
                    'BUREAU_BELOW_GENERIC_MIN' AS exception_type
                FROM loan_tape
                WHERE BUREAU_SCORE < {default_min_score}
                  AND BUREAU_SCORE IS NOT NULL
                ORDER BY BUREAU_SCORE ASC
            """).pl()

        if len(below_min_score) > 0:
            anomaly_flags.append({
                "field": "BUREAU_SCORE",
                "value": len(below_min_score),
                "threshold": f"BUREAU_SCORE >= {default_min_score} (policy min)",
                "message": f"{len(below_min_score)} loans with bureau score below policy minimum"
            })

    # ── 2. Stale bureau report: BUREAU_INQUIRY_DATE > 90 days before disb ─
    stale_bureau_df = pl.DataFrame()
    if "BUREAU_INQUIRY_DATE" in df.columns and "DISBURSEMENT_DATE" in df.columns:
        stale_bureau_df = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                BUREAU_SCORE, BUREAU_INQUIRY_DATE, DISBURSEMENT_DATE,
                DATE_DIFF('day', CAST(BUREAU_INQUIRY_DATE AS DATE), CAST(DISBURSEMENT_DATE AS DATE)) AS days_between,
                'STALE_BUREAU_REPORT' AS exception_type
            FROM loan_tape
            WHERE BUREAU_INQUIRY_DATE IS NOT NULL
              AND DISBURSEMENT_DATE IS NOT NULL
              AND DATE_DIFF('day', CAST(BUREAU_INQUIRY_DATE AS DATE), CAST(DISBURSEMENT_DATE AS DATE)) > 90
            ORDER BY days_between DESC
        """).pl()

        if len(stale_bureau_df) > 0:
            anomaly_flags.append({
                "field": "BUREAU_INQUIRY_DATE",
                "value": len(stale_bureau_df),
                "threshold": "Bureau report <= 90 days before disbursement",
                "message": f"{len(stale_bureau_df)} disbursements with bureau report > 90 days old at time of disbursement"
            })

    # ── 3. High score but delinquent ───────────────────────────────────────
    high_score_delinquent = pl.DataFrame()
    if "BUREAU_SCORE" in df.columns and "DPD" in df.columns:
        high_score_delinquent = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                BUREAU_SCORE, DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
                DISBURSEMENT_DATE, BUREAU_INQUIRY_DATE,
                'HIGH_SCORE_DELINQUENT' AS exception_type
            FROM loan_tape
            WHERE BUREAU_SCORE > 750
              AND DPD > 30
              AND BUREAU_SCORE IS NOT NULL
              AND DPD IS NOT NULL
            ORDER BY DPD DESC, BUREAU_SCORE DESC
        """).pl()

        if len(high_score_delinquent) > 0:
            anomaly_flags.append({
                "field": "BUREAU_SCORE",
                "value": len(high_score_delinquent),
                "threshold": "High bureau score (>750) should not have DPD > 30",
                "message": f"{len(high_score_delinquent)} accounts with bureau score >750 but DPD > 30 (score model concerns)"
            })

    # ── Bureau score distribution ─────────────────────────────────────────
    score_dist = pl.DataFrame()
    if "BUREAU_SCORE" in df.columns:
        score_dist = con.execute("""
            SELECT
                CASE
                    WHEN BUREAU_SCORE < 600 THEN '<600'
                    WHEN BUREAU_SCORE BETWEEN 600 AND 699 THEN '600-699'
                    WHEN BUREAU_SCORE BETWEEN 700 AND 749 THEN '700-749'
                    WHEN BUREAU_SCORE BETWEEN 750 AND 799 THEN '750-799'
                    WHEN BUREAU_SCORE >= 800 THEN '800+'
                    ELSE 'NULL'
                END AS score_band,
                COUNT(*) AS loan_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                    / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS par_pct
            FROM loan_tape
            GROUP BY 1
            ORDER BY MIN(BUREAU_SCORE) NULLS LAST
        """).pl()

    exc_frames = [f for f in [below_min_score, stale_bureau_df, high_score_delinquent] if len(f) > 0]
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
        "da_ref": "DA-027",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "below_min_score": below_min_score,
        "stale_bureau": stale_bureau_df,
        "high_score_delinquent": high_score_delinquent,
        "score_distribution": score_dist,
        "summary": {
            "total_loans": len(df),
            "below_policy_score": len(below_min_score),
            "stale_bureau_reports": len(stale_bureau_df),
            "high_score_delinquent": len(high_score_delinquent),
        },
        "anomaly_flags": anomaly_flags,
    }

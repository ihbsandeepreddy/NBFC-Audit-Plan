"""
DA-016: CRILC Reconciliation
Compare SMA/NPA classification in LMS vs CRILC submission; flag late submissions.
LMS Risk Theme: 4
CAP Seq: R.16
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-016",
    "name": "CRILC Reconciliation",
    "description": "LMS vs CRILC classification mismatch; flag late submission and product-wise rates",
    "cap_seq": "R.16",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["crilc_data"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    CRILC Reconciliation:
    1. Compare SMA/NPA classification in loan_tape vs crilc_data.
    2. Flag where LMS stage ≠ CRILC classification.
    3. Flag CRILC submissions > 7 days after quarter end.
    4. Compute mismatch rate by product.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    crilc_data = kwargs.get("crilc_data")

    if crilc_data is None:
        return {
            "da_ref": "DA-016",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "CRILC data not provided"},
            "anomaly_flags": [{"field": "crilc_data", "value": None,
                                "threshold": "Required", "message": "CRILC data not provided"}],
        }

    if isinstance(crilc_data, pl.DataFrame):
        crilc_df = crilc_data
    elif isinstance(crilc_data, pl.LazyFrame):
        crilc_df = crilc_data.collect()
    else:
        crilc_df = pl.DataFrame(crilc_data)

    con.register("crilc", crilc_df.to_arrow())

    # Determine CRILC column names
    crilc_lan_col = "LOAN_ACCOUNT_NO" if "LOAN_ACCOUNT_NO" in crilc_df.columns else "LAN"
    crilc_class_col = "CRILC_CLASSIFICATION" if "CRILC_CLASSIFICATION" in crilc_df.columns else (
        "SMA_STATUS" if "SMA_STATUS" in crilc_df.columns else "CLASSIFICATION"
    )
    crilc_sub_date = "SUBMISSION_DATE" if "SUBMISSION_DATE" in crilc_df.columns else "REPORT_DATE"
    crilc_stage_col = "IND_AS_STAGE" if "IND_AS_STAGE" in crilc_df.columns else None

    # ── 1. LMS vs CRILC classification mismatch ───────────────────────────
    # Map DPD to SMA category
    classification_mismatch = con.execute(f"""
        WITH lms_classified AS (
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                DPD, IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
                CASE
                    WHEN DPD >= 90 THEN 'NPA'
                    WHEN DPD >= 60 THEN 'SMA-2'
                    WHEN DPD >= 30 THEN 'SMA-1'
                    WHEN DPD >= 1 THEN 'SMA-0'
                    ELSE 'STANDARD'
                END AS lms_classification
            FROM loan_tape
        )
        SELECT
            l.LOAN_ACCOUNT_NO,
            l.PAN_NUMBER,
            l.PRODUCT_CODE,
            l.BRANCH_CODE,
            l.DPD,
            l.IND_AS_STAGE AS lms_stage,
            l.OUTSTANDING_PRINCIPAL,
            l.lms_classification,
            c."{crilc_class_col}" AS crilc_classification,
            CASE
                WHEN l.lms_classification != c."{crilc_class_col}" THEN 'CLASSIFICATION_MISMATCH'
                ELSE 'MATCH'
            END AS recon_status
        FROM lms_classified l
        JOIN crilc c ON l.LOAN_ACCOUNT_NO = c."{crilc_lan_col}"
        WHERE l.lms_classification != c."{crilc_class_col}"
        ORDER BY l.OUTSTANDING_PRINCIPAL DESC
    """).pl()

    if len(classification_mismatch) > 0:
        anomaly_flags.append({
            "field": "IND_AS_STAGE",
            "value": len(classification_mismatch),
            "threshold": "LMS classification == CRILC classification",
            "message": f"{len(classification_mismatch)} accounts with LMS vs CRILC classification mismatch"
        })

    # ── 2. Late CRILC submission (> 7 days after quarter end) ─────────────
    late_submissions = pl.DataFrame()
    if crilc_sub_date in crilc_df.columns:
        late_submissions = con.execute(f"""
            SELECT
                c."{crilc_lan_col}" AS LOAN_ACCOUNT_NO,
                c."{crilc_sub_date}" AS submission_date,
                CAST('{reporting_date}' AS DATE) AS quarter_end_date,
                DATE_DIFF('day', CAST('{reporting_date}' AS DATE), CAST(c."{crilc_sub_date}" AS DATE)) AS days_after_quarter_end,
                'LATE_CRILC_SUBMISSION' AS exception_type
            FROM crilc c
            WHERE DATE_DIFF('day', CAST('{reporting_date}' AS DATE), CAST(c."{crilc_sub_date}" AS DATE)) > 7
        """).pl()

        if len(late_submissions) > 0:
            anomaly_flags.append({
                "field": "SUBMISSION_DATE",
                "value": len(late_submissions),
                "threshold": "Submission <= 7 days after quarter end",
                "message": f"{len(late_submissions)} CRILC submissions > 7 days after quarter end"
            })

    # ── 3. Mismatch rate by product ────────────────────────────────────────
    mismatch_by_product = pl.DataFrame()
    if len(classification_mismatch) > 0 and "PRODUCT_CODE" in classification_mismatch.columns:
        con.register("mismatches", classification_mismatch.to_arrow())
        mismatch_by_product = con.execute("""
            WITH total_by_prod AS (
                SELECT PRODUCT_CODE, COUNT(*) AS total FROM loan_tape GROUP BY PRODUCT_CODE
            ),
            mismatch_by_prod AS (
                SELECT PRODUCT_CODE, COUNT(*) AS mismatch_count FROM mismatches GROUP BY PRODUCT_CODE
            )
            SELECT
                t.PRODUCT_CODE,
                t.total AS total_in_crilc,
                COALESCE(m.mismatch_count, 0) AS mismatch_count,
                ROUND(100.0 * COALESCE(m.mismatch_count, 0) / t.total, 2) AS mismatch_rate_pct
            FROM total_by_prod t
            LEFT JOIN mismatch_by_prod m ON t.PRODUCT_CODE = m.PRODUCT_CODE
            ORDER BY mismatch_rate_pct DESC
        """).pl()

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [classification_mismatch, late_submissions] if len(f) > 0]
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
        "da_ref": "DA-016",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "classification_mismatches": classification_mismatch,
        "late_submissions": late_submissions,
        "mismatch_by_product": mismatch_by_product,
        "summary": {
            "crilc_records": len(crilc_df),
            "lms_records": len(df),
            "classification_mismatches": len(classification_mismatch),
            "late_submissions": len(late_submissions),
        },
        "anomaly_flags": anomaly_flags,
    }

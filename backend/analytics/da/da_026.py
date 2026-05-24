"""
DA-026: KYC Validation
PAN format check, PAN/mobile/bank deduplication, VKYC post-disbursement detection.
LMS Risk Theme: 13
CAP Seq: S.03
"""

import polars as pl
import duckdb
import re
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-026",
    "name": "KYC Validation",
    "description": "PAN format/duplication, mobile/bank sharing, VKYC after disbursement",
    "cap_seq": "S.03",
    "risk_theme": 13,
    "required_inputs": ["loan_tape"],
    "optional_inputs": [],
}

PAN_PATTERN = r'^[A-Z]{5}[0-9]{4}[A-Z]$'


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    KYC Validation:
    1. PAN format: must match [A-Z]{5}[0-9]{4}[A-Z] exactly.
    2. PAN duplication: same PAN on 3+ active accounts of same product.
    3. Mobile sharing: same mobile on 10+ accounts.
    4. Bank account sharing: same bank account on 3+ different borrowers.
    5. VKYC post-disbursement: VKYC_DATE > DISBURSEMENT_DATE.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    pan_col = "PAN_NUMBER" if "PAN_NUMBER" in df.columns else ("PAN" if "PAN" in df.columns else None)

    # ── 1. PAN format validation ───────────────────────────────────────────
    invalid_pan_df = pl.DataFrame()
    if pan_col:
        # Use Polars regex for PAN validation
        invalid_pan_df = df.filter(
            pl.col(pan_col).is_not_null() &
            ~pl.col(pan_col).str.contains(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
        ).select([
            pl.col("LOAN_ACCOUNT_NO"),
            pl.col(pan_col).alias("PAN_NUMBER"),
            pl.lit("INVALID_PAN_FORMAT").alias("exception_type"),
        ] + (["PRODUCT_CODE"] if "PRODUCT_CODE" in df.columns else [])
          + (["BRANCH_CODE"] if "BRANCH_CODE" in df.columns else []))

        if len(invalid_pan_df) > 0:
            anomaly_flags.append({
                "field": "PAN_NUMBER",
                "value": len(invalid_pan_df),
                "threshold": "PAN = [A-Z]{5}[0-9]{4}[A-Z]",
                "message": f"{len(invalid_pan_df)} loans with invalid PAN format"
            })

    # ── 2. PAN duplication: 3+ active accounts same product ───────────────
    pan_dup_df = pl.DataFrame()
    if pan_col and "PRODUCT_CODE" in df.columns:
        stage_filter = "AND (IND_AS_STAGE IN (1,2) OR IND_AS_STAGE IS NULL)" if "IND_AS_STAGE" in df.columns else ""
        pan_dup_df = con.execute(f"""
            SELECT
                "{pan_col}" AS PAN_NUMBER,
                PRODUCT_CODE,
                COUNT(*) AS active_loan_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_exposure,
                'PAN_DUPLICATE_SAME_PRODUCT' AS exception_type
            FROM loan_tape
            WHERE "{pan_col}" IS NOT NULL
              {stage_filter}
            GROUP BY "{pan_col}", PRODUCT_CODE
            HAVING COUNT(*) >= 3
            ORDER BY active_loan_count DESC
        """).pl()

        if len(pan_dup_df) > 0:
            anomaly_flags.append({
                "field": "PAN_NUMBER",
                "value": len(pan_dup_df),
                "threshold": "< 3 active loans per PAN per product",
                "message": f"{len(pan_dup_df)} PAN+Product combos with 3+ active loans"
            })

    # ── 3. Mobile sharing: 10+ accounts ───────────────────────────────────
    mobile_share_df = pl.DataFrame()
    if "MOBILE_NUMBER" in df.columns:
        mobile_share_df = con.execute("""
            SELECT
                MOBILE_NUMBER,
                COUNT(*) AS account_count,
                COUNT(DISTINCT PAN_NUMBER) AS distinct_pans,
                SUM(OUTSTANDING_PRINCIPAL) AS total_exposure,
                'MOBILE_SHARED_10PLUS' AS exception_type
            FROM loan_tape
            WHERE MOBILE_NUMBER IS NOT NULL
            GROUP BY MOBILE_NUMBER
            HAVING COUNT(*) >= 10
            ORDER BY account_count DESC
        """).pl()

        if len(mobile_share_df) > 0:
            anomaly_flags.append({
                "field": "MOBILE_NUMBER",
                "value": len(mobile_share_df),
                "threshold": "< 10 accounts per mobile",
                "message": f"{len(mobile_share_df)} mobiles shared across 10+ accounts"
            })

    # ── 4. Bank account sharing: 3+ different borrowers ───────────────────
    bank_share_df = pl.DataFrame()
    if "BANK_ACCOUNT_NO" in df.columns and pan_col:
        bank_share_df = con.execute(f"""
            SELECT
                BANK_ACCOUNT_NO,
                COUNT(DISTINCT "{pan_col}") AS distinct_borrowers,
                COUNT(*) AS total_loans,
                SUM(OUTSTANDING_PRINCIPAL) AS total_exposure,
                'BANK_ACCOUNT_SHARED_3PLUS' AS exception_type
            FROM loan_tape
            WHERE BANK_ACCOUNT_NO IS NOT NULL
              AND "{pan_col}" IS NOT NULL
            GROUP BY BANK_ACCOUNT_NO
            HAVING COUNT(DISTINCT "{pan_col}") >= 3
            ORDER BY distinct_borrowers DESC
        """).pl()

        if len(bank_share_df) > 0:
            anomaly_flags.append({
                "field": "BANK_ACCOUNT_NO",
                "value": len(bank_share_df),
                "threshold": "< 3 borrowers per bank account",
                "message": f"{len(bank_share_df)} bank accounts shared across 3+ different borrowers"
            })

    # ── 5. VKYC post-disbursement ──────────────────────────────────────────
    vkyc_late_df = pl.DataFrame()
    if "VKYC_DATE" in df.columns and "DISBURSEMENT_DATE" in df.columns:
        vkyc_late_df = con.execute("""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                DISBURSEMENT_DATE, VKYC_DATE,
                DATE_DIFF('day', CAST(DISBURSEMENT_DATE AS DATE), CAST(VKYC_DATE AS DATE)) AS vkyc_delay_days,
                'VKYC_POST_DISBURSEMENT' AS exception_type
            FROM loan_tape
            WHERE VKYC_DATE > DISBURSEMENT_DATE
              AND VKYC_DATE IS NOT NULL
              AND DISBURSEMENT_DATE IS NOT NULL
            ORDER BY vkyc_delay_days DESC
        """).pl()

        if len(vkyc_late_df) > 0:
            anomaly_flags.append({
                "field": "VKYC_DATE",
                "value": len(vkyc_late_df),
                "threshold": "VKYC must be before disbursement",
                "message": f"{len(vkyc_late_df)} loans where VKYC was done AFTER disbursement"
            })

    # ── Compile all exceptions ─────────────────────────────────────────────
    exc_frames = [f for f in [invalid_pan_df, pan_dup_df, mobile_share_df, bank_share_df, vkyc_late_df] if len(f) > 0]
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
        "da_ref": "DA-026",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "invalid_pan": invalid_pan_df,
        "pan_duplicates": pan_dup_df,
        "mobile_sharing": mobile_share_df,
        "bank_account_sharing": bank_share_df,
        "vkyc_post_disbursement": vkyc_late_df,
        "summary": {
            "total_loans": len(df),
            "invalid_pan_count": len(invalid_pan_df),
            "pan_dup_combos": len(pan_dup_df),
            "mobile_shared_10plus": len(mobile_share_df),
            "bank_shared_3plus": len(bank_share_df),
            "vkyc_post_disb": len(vkyc_late_df),
        },
        "anomaly_flags": anomaly_flags,
    }

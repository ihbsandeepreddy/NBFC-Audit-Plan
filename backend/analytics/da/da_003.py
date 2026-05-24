"""
DA-003: Duplicate Loans Detection
Identify PAN-level, mobile, and bank-account duplicate patterns indicating ghost borrowers.
LMS Risk Theme: 13
CAP Seq: S.02
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-003",
    "name": "Duplicate Loans Detection",
    "description": "Flag same-PAN multi-loan, mobile/bank-account sharing patterns indicative of ghost borrowers",
    "cap_seq": "S.02",
    "risk_theme": 13,
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
    Duplicate Loan Detection:
    1. Same PAN with 3+ active loans of same product.
    2. Same MOBILE_NUMBER on 10+ accounts (ghost borrower network).
    3. Same BANK_ACCOUNT_NO on 3+ different borrowers.
    4. Compute branch-wise and DSA-wise duplicate rates.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. PAN-product duplicates: same PAN + product, 3+ active loans ────
    pan_prod_col = "PAN_NUMBER" if "PAN_NUMBER" in df.columns else ("PAN" if "PAN" in df.columns else None)
    pan_dup_df = pl.DataFrame()
    if pan_prod_col and "PRODUCT_CODE" in df.columns:
        stage_filter = "AND (IND_AS_STAGE IN (1,2) OR IND_AS_STAGE IS NULL)" if "IND_AS_STAGE" in df.columns else ""
        pan_dup_df = con.execute(f"""
            SELECT
                "{pan_prod_col}" AS PAN_NUMBER,
                PRODUCT_CODE,
                COUNT(*) AS loan_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                MAX(DPD) AS max_dpd,
                'PAN_PRODUCT_MULTIPLE_ACTIVE' AS exception_type
            FROM loan_tape
            WHERE "{pan_prod_col}" IS NOT NULL
              AND PRODUCT_CODE IS NOT NULL
              {stage_filter}
            GROUP BY "{pan_prod_col}", PRODUCT_CODE
            HAVING COUNT(*) >= 3
            ORDER BY loan_count DESC
        """).pl()

        if len(pan_dup_df) > 0:
            anomaly_flags.append({
                "field": "PAN_NUMBER",
                "value": len(pan_dup_df),
                "threshold": "< 3 active loans per PAN per product",
                "message": f"{len(pan_dup_df)} PAN+Product combinations with 3+ active loans"
            })

    # ── 2. Mobile number sharing: 10+ accounts ────────────────────────────
    mobile_dup_df = pl.DataFrame()
    if "MOBILE_NUMBER" in df.columns:
        mobile_dup_df = con.execute("""
            SELECT
                MOBILE_NUMBER,
                COUNT(*) AS account_count,
                COUNT(DISTINCT PAN_NUMBER) AS distinct_pans,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                'MOBILE_GHOST_BORROWER' AS exception_type
            FROM loan_tape
            WHERE MOBILE_NUMBER IS NOT NULL
            GROUP BY MOBILE_NUMBER
            HAVING COUNT(*) >= 10
            ORDER BY account_count DESC
        """).pl()

        if len(mobile_dup_df) > 0:
            anomaly_flags.append({
                "field": "MOBILE_NUMBER",
                "value": len(mobile_dup_df),
                "threshold": "< 10 accounts per mobile",
                "message": f"{len(mobile_dup_df)} mobile numbers shared across 10+ accounts (ghost borrower risk)"
            })

    # ── 3. Bank account sharing: same bank account on 3+ different borrowers
    bank_dup_df = pl.DataFrame()
    if "BANK_ACCOUNT_NO" in df.columns and pan_prod_col:
        bank_dup_df = con.execute(f"""
            SELECT
                BANK_ACCOUNT_NO,
                COUNT(DISTINCT "{pan_prod_col}") AS distinct_borrowers,
                COUNT(*) AS loan_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                'BANK_ACCOUNT_SHARED' AS exception_type
            FROM loan_tape
            WHERE BANK_ACCOUNT_NO IS NOT NULL
              AND "{pan_prod_col}" IS NOT NULL
            GROUP BY BANK_ACCOUNT_NO
            HAVING COUNT(DISTINCT "{pan_prod_col}") >= 3
            ORDER BY distinct_borrowers DESC
        """).pl()

        if len(bank_dup_df) > 0:
            anomaly_flags.append({
                "field": "BANK_ACCOUNT_NO",
                "value": len(bank_dup_df),
                "threshold": "< 3 distinct borrowers per bank account",
                "message": f"{len(bank_dup_df)} bank accounts shared across 3+ different borrowers"
            })

    # ── 4. Branch-wise duplicate rates ────────────────────────────────────
    branch_dup_rate = pl.DataFrame()
    if "BRANCH_CODE" in df.columns and pan_prod_col and "PRODUCT_CODE" in df.columns:
        branch_dup_rate = con.execute(f"""
            WITH dup_lans AS (
                SELECT LOAN_ACCOUNT_NO
                FROM (
                    SELECT LOAN_ACCOUNT_NO, "{pan_prod_col}", PRODUCT_CODE, BRANCH_CODE,
                           COUNT(*) OVER (PARTITION BY "{pan_prod_col}", PRODUCT_CODE) AS cnt
                    FROM loan_tape
                    WHERE "{pan_prod_col}" IS NOT NULL
                ) t
                WHERE cnt >= 3
            )
            SELECT
                l.BRANCH_CODE,
                COUNT(*) AS total_loans,
                COUNT(d.LOAN_ACCOUNT_NO) AS dup_loans,
                ROUND(100.0 * COUNT(d.LOAN_ACCOUNT_NO) / NULLIF(COUNT(*), 0), 2) AS dup_rate_pct
            FROM loan_tape l
            LEFT JOIN dup_lans d ON l.LOAN_ACCOUNT_NO = d.LOAN_ACCOUNT_NO
            GROUP BY l.BRANCH_CODE
            ORDER BY dup_rate_pct DESC NULLS LAST
        """).pl()

    # ── 5. DSA-wise duplicate rates ───────────────────────────────────────
    dsa_dup_rate = pl.DataFrame()
    if "DSA_CODE" in df.columns and pan_prod_col and "PRODUCT_CODE" in df.columns:
        dsa_dup_rate = con.execute(f"""
            WITH dup_lans AS (
                SELECT LOAN_ACCOUNT_NO
                FROM (
                    SELECT LOAN_ACCOUNT_NO, "{pan_prod_col}", PRODUCT_CODE,
                           COUNT(*) OVER (PARTITION BY "{pan_prod_col}", PRODUCT_CODE) AS cnt
                    FROM loan_tape
                    WHERE "{pan_prod_col}" IS NOT NULL
                ) t
                WHERE cnt >= 3
            )
            SELECT
                l.DSA_CODE,
                COUNT(*) AS total_loans,
                COUNT(d.LOAN_ACCOUNT_NO) AS dup_loans,
                ROUND(100.0 * COUNT(d.LOAN_ACCOUNT_NO) / NULLIF(COUNT(*), 0), 2) AS dup_rate_pct
            FROM loan_tape l
            LEFT JOIN dup_lans d ON l.LOAN_ACCOUNT_NO = d.LOAN_ACCOUNT_NO
            WHERE l.DSA_CODE IS NOT NULL
            GROUP BY l.DSA_CODE
            ORDER BY dup_rate_pct DESC NULLS LAST
        """).pl()

    # ── Compile exception records ──────────────────────────────────────────
    exc_frames = []
    for frm, exc_type in [(pan_dup_df, "PAN_PRODUCT_MULTIPLE_ACTIVE"),
                           (mobile_dup_df, "MOBILE_GHOST_BORROWER"),
                           (bank_dup_df, "BANK_ACCOUNT_SHARED")]:
        if len(frm) > 0:
            exc_frames.append(frm)

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

    total_exc = len(pan_dup_df) + len(mobile_dup_df) + len(bank_dup_df)

    return {
        "da_ref": "DA-003",
        "total_records": len(df),
        "exceptions_count": total_exc,
        "exceptions_df": exceptions_df,
        "pan_product_duplicates": pan_dup_df,
        "mobile_duplicates": mobile_dup_df,
        "bank_account_duplicates": bank_dup_df,
        "branch_dup_rates": branch_dup_rate,
        "dsa_dup_rates": dsa_dup_rate,
        "summary": {
            "pan_product_dup_combos": len(pan_dup_df),
            "mobile_ghost_networks": len(mobile_dup_df),
            "bank_account_shared": len(bank_dup_df),
        },
        "anomaly_flags": anomaly_flags,
    }

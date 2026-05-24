"""
DA-030: PAR Bucket Analysis
Compute PAR by DPD bucket; analyze by product, branch, DSA; compute flow rates.
LMS Risk Theme: 2
CAP Seq: R.30
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-030",
    "name": "PAR Bucket Analysis",
    "description": "PAR by bucket (Current/1-30/31-60/61-90/90+) with flow rates by product/branch/DSA",
    "cap_seq": "R.30",
    "risk_theme": 2,
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
    PAR Bucket Analysis:
    1. Compute PAR by bucket: Current, 1-30 DPD, 31-60, 61-90, 90+ DPD.
    2. By product, branch, DSA.
    3. QoQ movement between buckets.
    4. Flow rates (% of 1-30 that moved to 31-60, etc.) using prior period data.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. Portfolio-level PAR buckets ────────────────────────────────────
    portfolio_par = con.execute("""
        SELECT
            CASE
                WHEN DPD = 0 THEN 'CURRENT'
                WHEN DPD BETWEEN 1 AND 30 THEN '1-30 DPD'
                WHEN DPD BETWEEN 31 AND 60 THEN '31-60 DPD'
                WHEN DPD BETWEEN 61 AND 90 THEN '61-90 DPD'
                WHEN DPD > 90 THEN '90+ DPD (NPA)'
                ELSE 'UNKNOWN'
            END AS dpd_bucket,
            CASE
                WHEN DPD = 0 THEN 0
                WHEN DPD BETWEEN 1 AND 30 THEN 1
                WHEN DPD BETWEEN 31 AND 60 THEN 2
                WHEN DPD BETWEEN 61 AND 90 THEN 3
                WHEN DPD > 90 THEN 4
                ELSE 5
            END AS bucket_order,
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS outstanding,
            ROUND(100.0 * SUM(OUTSTANDING_PRINCIPAL)
                / NULLIF(SUM(SUM(OUTSTANDING_PRINCIPAL)) OVER (), 0), 2) AS portfolio_share_pct
        FROM loan_tape
        WHERE DPD IS NOT NULL AND OUTSTANDING_PRINCIPAL IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 2
    """).pl()

    # ── 2. By product ──────────────────────────────────────────────────────
    par_by_product = con.execute("""
        SELECT
            PRODUCT_CODE,
            SUM(CASE WHEN DPD = 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS current_os,
            SUM(CASE WHEN DPD BETWEEN 1 AND 30 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_1_30,
            SUM(CASE WHEN DPD BETWEEN 31 AND 60 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_31_60,
            SUM(CASE WHEN DPD BETWEEN 61 AND 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_61_90,
            SUM(CASE WHEN DPD > 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_90_plus,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS total_par_pct
        FROM loan_tape
        WHERE DPD IS NOT NULL AND OUTSTANDING_PRINCIPAL IS NOT NULL
          AND PRODUCT_CODE IS NOT NULL
        GROUP BY PRODUCT_CODE
        ORDER BY total_par_pct DESC
    """).pl()

    # ── 3. By branch ──────────────────────────────────────────────────────
    par_by_branch = pl.DataFrame()
    if "BRANCH_CODE" in df.columns:
        par_by_branch = con.execute("""
            SELECT
                BRANCH_CODE,
                SUM(CASE WHEN DPD = 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS current_os,
                SUM(CASE WHEN DPD BETWEEN 1 AND 30 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_1_30,
                SUM(CASE WHEN DPD BETWEEN 31 AND 60 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_31_60,
                SUM(CASE WHEN DPD BETWEEN 61 AND 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_61_90,
                SUM(CASE WHEN DPD > 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_90_plus,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                    / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS total_par_pct
            FROM loan_tape
            WHERE DPD IS NOT NULL AND OUTSTANDING_PRINCIPAL IS NOT NULL
              AND BRANCH_CODE IS NOT NULL
            GROUP BY BRANCH_CODE
            ORDER BY total_par_pct DESC
        """).pl()

    # ── 4. By DSA ─────────────────────────────────────────────────────────
    par_by_dsa = pl.DataFrame()
    if "DSA_CODE" in df.columns:
        par_by_dsa = con.execute("""
            SELECT
                DSA_CODE,
                SUM(CASE WHEN DPD = 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS current_os,
                SUM(CASE WHEN DPD > 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_amount,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                    / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS total_par_pct
            FROM loan_tape
            WHERE DSA_CODE IS NOT NULL AND OUTSTANDING_PRINCIPAL IS NOT NULL
            GROUP BY DSA_CODE
            ORDER BY total_par_pct DESC
        """).pl()

    # ── 5. QoQ flow rates if prior period available ────────────────────────
    flow_rates = pl.DataFrame()
    prior_tape = kwargs.get("prior_loan_tape")

    if prior_tape is not None:
        prior_df = prior_tape.collect() if isinstance(prior_tape, pl.LazyFrame) else prior_tape
        con.register("prior_tape", prior_df.to_arrow())

        flow_rates = con.execute(f"""
            WITH prior_buckets AS (
                SELECT LOAN_ACCOUNT_NO,
                    CASE
                        WHEN DPD = 0 THEN 'CURRENT'
                        WHEN DPD BETWEEN 1 AND 30 THEN '1-30'
                        WHEN DPD BETWEEN 31 AND 60 THEN '31-60'
                        WHEN DPD BETWEEN 61 AND 90 THEN '61-90'
                        ELSE 'NPA'
                    END AS prior_bucket,
                    OUTSTANDING_PRINCIPAL AS prior_os
                FROM prior_tape
                WHERE DPD IS NOT NULL
            ),
            current_buckets AS (
                SELECT LOAN_ACCOUNT_NO,
                    CASE
                        WHEN DPD = 0 THEN 'CURRENT'
                        WHEN DPD BETWEEN 1 AND 30 THEN '1-30'
                        WHEN DPD BETWEEN 31 AND 60 THEN '31-60'
                        WHEN DPD BETWEEN 61 AND 90 THEN '61-90'
                        ELSE 'NPA'
                    END AS current_bucket,
                    OUTSTANDING_PRINCIPAL AS current_os
                FROM loan_tape
                WHERE DPD IS NOT NULL
            )
            SELECT
                p.prior_bucket,
                c.current_bucket,
                COUNT(*) AS account_count,
                SUM(c.current_os) AS outstanding,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY p.prior_bucket), 2) AS flow_rate_pct
            FROM prior_buckets p
            JOIN current_buckets c ON p.LOAN_ACCOUNT_NO = c.LOAN_ACCOUNT_NO
            GROUP BY p.prior_bucket, c.current_bucket
            ORDER BY p.prior_bucket, c.current_bucket
        """).pl()

    # ── Flags ──────────────────────────────────────────────────────────────
    # Flag if NPA bucket > 10% of portfolio
    if len(portfolio_par) > 0:
        npa_share = portfolio_par.filter(pl.col("dpd_bucket") == "90+ DPD (NPA)")
        if len(npa_share) > 0:
            npa_pct = float(npa_share["portfolio_share_pct"].sum() or 0)
            if npa_pct > 10:
                anomaly_flags.append({
                    "field": "DPD_BUCKET",
                    "value": npa_pct,
                    "threshold": "NPA < 10% of portfolio",
                    "message": f"NPA bucket = {npa_pct:.2f}% of portfolio (> 10% high concern)"
                })

    return {
        "da_ref": "DA-030",
        "total_records": len(df),
        "exceptions_count": 0,
        "exceptions_df": pl.DataFrame(),
        "portfolio_par_buckets": portfolio_par,
        "par_by_product": par_by_product,
        "par_by_branch": par_by_branch,
        "par_by_dsa": par_by_dsa,
        "flow_rates": flow_rates,
        "summary": {
            "total_loans": len(df),
            "total_outstanding": round(float(df["OUTSTANDING_PRINCIPAL"].sum() or 0), 2) if "OUTSTANDING_PRINCIPAL" in df.columns else 0,
        },
        "anomaly_flags": anomaly_flags,
    }

"""
DA-029: Vintage Analysis
Bucket loans by disbursement quarter; compute vintage-wise NPA, early delinquency.
LMS Risk Theme: 2
CAP Seq: R.29
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-029",
    "name": "Vintage Analysis",
    "description": "Disbursement-quarter bucketing; NPA rate per vintage; 90-day early delinquency",
    "cap_seq": "R.29",
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
    Vintage Analysis:
    1. Bucket loans by disbursement quarter (Q1 FY24, Q2 FY24, ...).
    2. Compute current DPD distribution, NPA rate, ECL rate per vintage.
    3. Flag vintages with NPA rate > 2x portfolio average.
    4. 90-day early delinquency rate (DPD 30+ within 90 days of disbursement).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    if "DISBURSEMENT_DATE" not in df.columns:
        return {
            "da_ref": "DA-029",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "DISBURSEMENT_DATE not found"},
            "anomaly_flags": [],
        }

    # ── 1. Vintage bucketing by disbursement quarter ───────────────────────
    vintage_df = con.execute(f"""
        WITH vintaged AS (
            SELECT *,
                -- Indian FY: Apr-Jun = Q1, Jul-Sep = Q2, Oct-Dec = Q3, Jan-Mar = Q4
                CASE
                    WHEN EXTRACT(MONTH FROM CAST(DISBURSEMENT_DATE AS DATE)) BETWEEN 4 AND 6 THEN
                        'Q1 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 1999 AS VARCHAR)
                    WHEN EXTRACT(MONTH FROM CAST(DISBURSEMENT_DATE AS DATE)) BETWEEN 7 AND 9 THEN
                        'Q2 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 1999 AS VARCHAR)
                    WHEN EXTRACT(MONTH FROM CAST(DISBURSEMENT_DATE AS DATE)) BETWEEN 10 AND 12 THEN
                        'Q3 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 1999 AS VARCHAR)
                    ELSE
                        'Q4 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 2000 AS VARCHAR)
                END AS vintage_label,
                DATE_DIFF('day', CAST(DISBURSEMENT_DATE AS DATE), CAST('{reporting_date}' AS DATE)) AS loan_age_days
            FROM loan_tape
            WHERE DISBURSEMENT_DATE IS NOT NULL
        )
        SELECT
            vintage_label,
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(DISBURSEMENT_AMOUNT) AS total_disbursed,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_amount,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS npa_rate_pct,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS par_rate_pct,
            SUM(CASE WHEN TOTAL_ECL_PROVISION IS NOT NULL THEN TOTAL_ECL_PROVISION ELSE 0 END) AS total_ecl,
            ROUND(100.0 * SUM(CASE WHEN TOTAL_ECL_PROVISION IS NOT NULL THEN TOTAL_ECL_PROVISION ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS ecl_rate_pct,
            AVG(loan_age_days) AS avg_loan_age_days,
            -- Early delinquency: DPD 30+ within 90 days of disbursement
            SUM(CASE WHEN DPD >= 30 AND loan_age_days <= 90 THEN 1 ELSE 0 END) AS early_delinquent_count,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 30 AND loan_age_days <= 90 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 2) AS early_delinquency_rate_pct
        FROM vintaged
        GROUP BY vintage_label
        ORDER BY MIN(DISBURSEMENT_DATE)
    """ if "TOTAL_ECL_PROVISION" in df.columns else f"""
        WITH vintaged AS (
            SELECT *,
                CASE
                    WHEN EXTRACT(MONTH FROM CAST(DISBURSEMENT_DATE AS DATE)) BETWEEN 4 AND 6 THEN
                        'Q1 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 1999 AS VARCHAR)
                    WHEN EXTRACT(MONTH FROM CAST(DISBURSEMENT_DATE AS DATE)) BETWEEN 7 AND 9 THEN
                        'Q2 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 1999 AS VARCHAR)
                    WHEN EXTRACT(MONTH FROM CAST(DISBURSEMENT_DATE AS DATE)) BETWEEN 10 AND 12 THEN
                        'Q3 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 1999 AS VARCHAR)
                    ELSE
                        'Q4 FY' || CAST(EXTRACT(YEAR FROM CAST(DISBURSEMENT_DATE AS DATE)) - 2000 AS VARCHAR)
                END AS vintage_label,
                DATE_DIFF('day', CAST(DISBURSEMENT_DATE AS DATE), CAST('{reporting_date}' AS DATE)) AS loan_age_days
            FROM loan_tape
            WHERE DISBURSEMENT_DATE IS NOT NULL
        )
        SELECT
            vintage_label,
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(DISBURSEMENT_AMOUNT) AS total_disbursed,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_amount,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS npa_rate_pct,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS par_rate_pct,
            NULL AS total_ecl,
            NULL AS ecl_rate_pct,
            AVG(loan_age_days) AS avg_loan_age_days,
            SUM(CASE WHEN DPD >= 30 AND loan_age_days <= 90 THEN 1 ELSE 0 END) AS early_delinquent_count,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 30 AND loan_age_days <= 90 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 2) AS early_delinquency_rate_pct
        FROM vintaged
        GROUP BY vintage_label
        ORDER BY MIN(DISBURSEMENT_DATE)
    """).pl()

    # ── 2. Flag vintages with NPA rate > 2x portfolio average ─────────────
    portfolio_npa_avg = float(vintage_df["npa_rate_pct"].mean() or 0)
    bad_vintages = vintage_df.filter(
        (pl.col("npa_rate_pct") > portfolio_npa_avg * 2) &
        (pl.col("npa_rate_pct") > 0)
    )

    if len(bad_vintages) > 0:
        anomaly_flags.append({
            "field": "VINTAGE_NPA_RATE",
            "value": len(bad_vintages),
            "threshold": f"< {portfolio_npa_avg * 2:.2f}% (2x portfolio average)",
            "message": f"{len(bad_vintages)} vintages with NPA rate > 2x portfolio average ({portfolio_npa_avg:.2f}%)"
        })

    # ── 3. Early delinquency flag ─────────────────────────────────────────
    high_early_delinq = vintage_df.filter(pl.col("early_delinquency_rate_pct") > 10)
    if len(high_early_delinq) > 0:
        anomaly_flags.append({
            "field": "EARLY_DELINQUENCY",
            "value": len(high_early_delinq),
            "threshold": "< 10% early delinquency rate",
            "message": f"{len(high_early_delinq)} vintages with > 10% early delinquency rate (DPD30+ within 90 days)"
        })

    exceptions_df = bad_vintages

    return {
        "da_ref": "DA-029",
        "total_records": len(df),
        "exceptions_count": len(bad_vintages),
        "exceptions_df": exceptions_df,
        "vintage_analysis": vintage_df,
        "bad_vintages": bad_vintages,
        "summary": {
            "total_loans": len(df),
            "vintage_count": len(vintage_df),
            "portfolio_avg_npa_pct": round(portfolio_npa_avg, 2),
            "vintages_above_2x_avg": len(bad_vintages),
            "high_early_delinquency_vintages": len(high_early_delinq),
        },
        "anomaly_flags": anomaly_flags,
    }

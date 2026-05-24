"""
DA-032: PD Backtesting
Compare model PD to actual default rate over 3 years; flag material understatement.
LMS Risk Theme: 3
CAP Seq: R.32
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-032",
    "name": "PD Backtesting",
    "description": "Actual default rate vs model PD over 3 years; flag > 20% understatement",
    "cap_seq": "R.32",
    "risk_theme": 3,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["historical_loan_data"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    PD Backtesting:
    1. For each quarter: identify Stage 1/2 accounts, check default in next 12 months.
    2. Compute actual default rate vs management model PD.
    3. Flag if actual > model by > 20%.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("current_tape", df.to_arrow())

    anomaly_flags = []
    historical_data = kwargs.get("historical_loan_data")
    model_pd = kwargs.get("model_pd", {})  # {product_code: pd_rate}

    if historical_data is None:
        # Use current tape to estimate: accounts that were Stage 1/2 and are now NPA
        if "IND_AS_STAGE" in df.columns and "DPD" in df.columns:
            stage12_npa = con.execute("""
                SELECT
                    PRODUCT_CODE,
                    COUNT(*) AS total_stage12_plus_npa,
                    SUM(CASE WHEN IND_AS_STAGE = 3 THEN 1 ELSE 0 END) AS current_npa_count,
                    ROUND(100.0 * SUM(CASE WHEN IND_AS_STAGE = 3 THEN 1 ELSE 0 END)
                        / NULLIF(COUNT(*), 0), 4) AS observed_default_rate_pct
                FROM current_tape
                WHERE PRODUCT_CODE IS NOT NULL
                GROUP BY PRODUCT_CODE
                ORDER BY observed_default_rate_pct DESC
            """).pl()

            return {
                "da_ref": "DA-032",
                "total_records": len(df),
                "exceptions_count": 0,
                "exceptions_df": pl.DataFrame(),
                "observed_rates": stage12_npa,
                "summary": {"note": "Historical data not provided; current period cross-section used"},
                "anomaly_flags": [{"field": "historical_loan_data", "value": None,
                                    "threshold": "3 years required", "message": "Historical data not provided for full backtesting"}],
            }

    if isinstance(historical_data, pl.DataFrame):
        hist_df = historical_data
    elif isinstance(historical_data, pl.LazyFrame):
        hist_df = historical_data.collect()
    else:
        hist_df = pl.DataFrame(historical_data)

    con.register("historical", hist_df.to_arrow())

    # Requires columns: LOAN_ACCOUNT_NO, PRODUCT_CODE, IND_AS_STAGE, PERIOD (YYYY-QQ), DPD
    period_col = "PERIOD" if "PERIOD" in hist_df.columns else (
        "QUARTER" if "QUARTER" in hist_df.columns else "REPORTING_DATE"
    )

    backtest_results = con.execute(f"""
        WITH observation_periods AS (
            SELECT DISTINCT "{period_col}" AS period_label
            FROM historical
            ORDER BY "{period_col}"
        ),
        stage12_at_period AS (
            SELECT
                h.LOAN_ACCOUNT_NO,
                h.PRODUCT_CODE,
                h."{period_col}" AS observation_period,
                h.IND_AS_STAGE AS start_stage
            FROM historical h
            WHERE h.IND_AS_STAGE IN (1, 2)
        ),
        default_in_forward AS (
            SELECT
                s.LOAN_ACCOUNT_NO,
                s.PRODUCT_CODE,
                s.observation_period,
                s.start_stage,
                MAX(CASE WHEN f.IND_AS_STAGE = 3 THEN 1 ELSE 0 END) AS defaulted_12m
            FROM stage12_at_period s
            JOIN historical f ON s.LOAN_ACCOUNT_NO = f.LOAN_ACCOUNT_NO
               AND f."{period_col}" > s.observation_period
            GROUP BY s.LOAN_ACCOUNT_NO, s.PRODUCT_CODE, s.observation_period, s.start_stage
        )
        SELECT
            PRODUCT_CODE,
            observation_period,
            start_stage,
            COUNT(*) AS observation_count,
            SUM(defaulted_12m) AS default_count,
            ROUND(100.0 * SUM(defaulted_12m) / NULLIF(COUNT(*), 0), 4) AS actual_pd_pct
        FROM default_in_forward
        GROUP BY PRODUCT_CODE, observation_period, start_stage
        ORDER BY PRODUCT_CODE, observation_period
    """).pl()

    # ── Compare to model PD ────────────────────────────────────────────────
    pd_exceptions = []
    if model_pd and len(backtest_results) > 0:
        for row in backtest_results.to_dicts():
            product = row.get("PRODUCT_CODE")
            actual_pd = float(row.get("actual_pd_pct") or 0)
            m_pd = model_pd.get(product, model_pd.get("DEFAULT", 0))
            if m_pd and actual_pd > float(m_pd) * 1.20:  # actual > model by > 20%
                gap = actual_pd - float(m_pd)
                pd_exceptions.append({
                    **row,
                    "model_pd_pct": float(m_pd),
                    "gap_pct": round(gap, 4),
                    "exception_type": "PD_UNDERSTATED",
                })
                anomaly_flags.append({
                    "field": "MODEL_PD",
                    "value": round(actual_pd, 2),
                    "threshold": f"Within 20% of model PD ({float(m_pd):.2f}%)",
                    "message": f"Product {product}: Actual PD {actual_pd:.2f}% vs model {float(m_pd):.2f}% (understatement by {gap:.2f}%)"
                })

    exceptions_df = pl.DataFrame(pd_exceptions) if pd_exceptions else pl.DataFrame()

    return {
        "da_ref": "DA-032",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "backtest_results": backtest_results,
        "summary": {
            "historical_records": len(hist_df),
            "observation_periods": backtest_results["observation_period"].n_unique() if len(backtest_results) > 0 and "observation_period" in backtest_results.columns else 0,
            "pd_understatement_cases": len(exceptions_df),
        },
        "anomaly_flags": anomaly_flags,
    }

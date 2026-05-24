"""
DA-005: Segment Variance Analysis
PAR% and risk metrics by segment; flag outliers using statistical thresholds.
LMS Risk Theme: 2
CAP Seq: R.05
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-005",
    "name": "Segment Variance Analysis",
    "description": "PAR%, DPD, EMI, ticket stats by segment; flag segments > 2 SD above mean PAR",
    "cap_seq": "R.05",
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
    Segment Variance Analysis:
    1. Compute PAR% (Principal at Risk where DPD > 0) by BRANCH_CODE, PRODUCT_CODE.
    2. Compute min/avg/max DPD, EMI, tenure, ticket size, FOIR by segment.
    3. Flag segments where PAR% > 2 standard deviations from mean.
    4. QoQ PAR shift if prior period data available via kwargs['prior_loan_tape'].

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. Segment-level PAR and risk metrics ─────────────────────────────
    segment_cols = []
    for c in ["BRANCH_CODE", "PRODUCT_CODE"]:
        if c in df.columns:
            segment_cols.append(c)

    group_by_clause = ", ".join(segment_cols) if segment_cols else "PRODUCT_CODE"
    select_segment = ", ".join([f'"{c}"' for c in segment_cols]) if segment_cols else "'ALL' AS PRODUCT_CODE"

    foir_col = "FOIR" if "FOIR" in df.columns else "NULL"
    emi_col = "EMI_AMOUNT" if "EMI_AMOUNT" in df.columns else "NULL"
    tenure_col = "TENURE_MONTHS" if "TENURE_MONTHS" in df.columns else "NULL"

    segment_metrics = con.execute(f"""
        SELECT
            {select_segment},
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_amount,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS par_pct,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_amount,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS npa_pct,
            MIN(DPD) AS min_dpd,
            AVG(DPD) AS avg_dpd,
            MAX(DPD) AS max_dpd,
            MIN({emi_col}) AS min_emi,
            AVG({emi_col}) AS avg_emi,
            MAX({emi_col}) AS max_emi,
            MIN({tenure_col}) AS min_tenure,
            AVG({tenure_col}) AS avg_tenure,
            MAX({tenure_col}) AS max_tenure,
            MIN(DISBURSEMENT_AMOUNT) AS min_ticket,
            AVG(DISBURSEMENT_AMOUNT) AS avg_ticket,
            MAX(DISBURSEMENT_AMOUNT) AS max_ticket,
            AVG({foir_col}) AS avg_foir
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL
          AND DPD IS NOT NULL
        GROUP BY {group_by_clause}
        ORDER BY par_pct DESC NULLS LAST
    """).pl()

    # ── 2. Flag segments > 2 SD from mean PAR% ────────────────────────────
    par_outliers = pl.DataFrame()
    if len(segment_metrics) > 1 and "par_pct" in segment_metrics.columns:
        con.register("seg_metrics", segment_metrics.to_arrow())
        par_outliers = con.execute("""
            WITH stats AS (
                SELECT AVG(par_pct) AS mean_par, STDDEV(par_pct) AS std_par
                FROM seg_metrics
                WHERE par_pct IS NOT NULL
            )
            SELECT
                s.*,
                st.mean_par,
                st.std_par,
                (s.par_pct - st.mean_par) / NULLIF(st.std_par, 0) AS z_score,
                'SEGMENT_PAR_OUTLIER' AS exception_type
            FROM seg_metrics s, stats st
            WHERE s.par_pct > st.mean_par + 2 * st.std_par
            ORDER BY s.par_pct DESC
        """).pl()

        if len(par_outliers) > 0:
            anomaly_flags.append({
                "field": "PAR_PCT",
                "value": len(par_outliers),
                "threshold": "mean + 2 SD",
                "message": f"{len(par_outliers)} segments with PAR% > 2 SD above mean"
            })

    # ── 3. Portfolio-level PAR summary ────────────────────────────────────
    portfolio_par = con.execute("""
        SELECT
            COUNT(*) AS total_loans,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(CASE WHEN DPD BETWEEN 1  AND 30  THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_1_30,
            SUM(CASE WHEN DPD BETWEEN 31 AND 60  THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_31_60,
            SUM(CASE WHEN DPD BETWEEN 61 AND 90  THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_61_90,
            SUM(CASE WHEN DPD >  90            THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_90_plus,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS portfolio_par_pct
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL AND DPD IS NOT NULL
    """).pl().to_dicts()[0] if len(df) > 0 else {}

    # ── 4. QoQ PAR shift if prior period available ────────────────────────
    qoq_shift = pl.DataFrame()
    prior_tape = kwargs.get("prior_loan_tape")
    if prior_tape is not None:
        prior_df = prior_tape.collect() if isinstance(prior_tape, pl.LazyFrame) else prior_tape
        con.register("prior_tape", prior_df.to_arrow())
        qoq_shift = con.execute(f"""
            WITH current_par AS (
                SELECT {select_segment},
                    ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                        / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS current_par_pct
                FROM loan_tape
                WHERE OUTSTANDING_PRINCIPAL IS NOT NULL AND DPD IS NOT NULL
                GROUP BY {group_by_clause}
            ),
            prior_par AS (
                SELECT {select_segment},
                    ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                        / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS prior_par_pct
                FROM prior_tape
                WHERE OUTSTANDING_PRINCIPAL IS NOT NULL AND DPD IS NOT NULL
                GROUP BY {group_by_clause}
            )
            SELECT
                c.*,
                p.prior_par_pct,
                (c.current_par_pct - p.prior_par_pct) AS par_shift,
                CASE
                    WHEN (c.current_par_pct - p.prior_par_pct) > 5 THEN 'MATERIAL_DETERIORATION'
                    WHEN (c.current_par_pct - p.prior_par_pct) < -5 THEN 'MATERIAL_IMPROVEMENT'
                    ELSE 'STABLE'
                END AS qoq_flag
            FROM current_par c
            LEFT JOIN prior_par p USING ({group_by_clause})
            ORDER BY par_shift DESC NULLS LAST
        """).pl()

    exceptions_df = par_outliers

    return {
        "da_ref": "DA-005",
        "total_records": len(df),
        "exceptions_count": len(par_outliers),
        "exceptions_df": exceptions_df,
        "segment_metrics": segment_metrics,
        "par_outliers": par_outliers,
        "qoq_shift": qoq_shift,
        "summary": {
            "total_records": len(df),
            "portfolio_par": portfolio_par,
            "segment_count": len(segment_metrics),
            "outlier_segments": len(par_outliers),
        },
        "anomaly_flags": anomaly_flags,
    }

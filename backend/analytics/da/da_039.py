"""
DA-039: PD Actual vs Model by Segment
Segment-level PD comparison: actual default rate vs management model PD.
LMS Risk Theme: 3
CAP Seq: R.39
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-039",
    "name": "PD Actual vs Model by Segment",
    "description": "Segment-level actual PD vs model PD; flag over/under-statement by segment",
    "cap_seq": "R.39",
    "risk_theme": 3,
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
    PD Actual vs Model by Segment:
    1. Segment-level: compute actual default rate over last 4 quarters.
    2. Compare to management model PD per segment.
    3. Output: segment, model_pd, actual_pd, gap_pct, direction.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    model_pd_data = kwargs.get("model_pd", {})  # {product_code: pd_rate}

    # ── Compute actual PD proxy from current tape ─────────────────────────
    # Actual PD proxy: accounts with IND_AS_STAGE = 3 / total active accounts
    actual_pd_by_segment = con.execute("""
        SELECT
            PRODUCT_CODE,
            COUNT(*) AS total_accounts,
            SUM(CASE WHEN IND_AS_STAGE = 3 THEN 1 ELSE 0 END) AS default_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            ROUND(100.0 * SUM(CASE WHEN IND_AS_STAGE = 3 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 4) AS actual_pd_pct,
            AVG(DPD) AS avg_dpd,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 30 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 4) AS sicr_rate_pct
        FROM loan_tape
        WHERE PRODUCT_CODE IS NOT NULL
          AND IND_AS_STAGE IS NOT NULL
        GROUP BY PRODUCT_CODE
        ORDER BY actual_pd_pct DESC
    """).pl()

    # ── Compare to model PD ────────────────────────────────────────────────
    pd_comparison = []
    if model_pd_data and len(actual_pd_by_segment) > 0:
        for row in actual_pd_by_segment.to_dicts():
            product = row.get("PRODUCT_CODE")
            actual_pd = float(row.get("actual_pd_pct") or 0)
            model_pd = float(model_pd_data.get(product, model_pd_data.get("DEFAULT", 0)))
            if model_pd > 0:
                gap_pct = round(actual_pd - model_pd, 4)
                gap_pct_rel = round((actual_pd - model_pd) / model_pd * 100, 2) if model_pd != 0 else None
                pd_comparison.append({
                    "PRODUCT_CODE": product,
                    "total_accounts": row.get("total_accounts"),
                    "default_count": row.get("default_count"),
                    "actual_pd_pct": actual_pd,
                    "model_pd_pct": model_pd,
                    "gap_abs": gap_pct,
                    "gap_rel_pct": gap_pct_rel,
                    "direction": "UNDERSTATED" if actual_pd > model_pd else "OVERSTATED",
                    "material": abs(gap_pct_rel or 0) > 20,
                })

                if abs(gap_pct_rel or 0) > 20:
                    anomaly_flags.append({
                        "field": "MODEL_PD",
                        "value": round(actual_pd, 2),
                        "threshold": f"Within 20% of model PD ({model_pd:.2f}%)",
                        "message": f"Segment {product}: Actual PD {actual_pd:.2f}% vs model {model_pd:.2f}% ({gap_pct_rel:.1f}% {'understatement' if actual_pd > model_pd else 'overstatement'})"
                    })

    exceptions_df = pl.DataFrame(pd_comparison).filter(pl.col("material") == True) if pd_comparison else pl.DataFrame()

    # ── DPD-based PD segmentation ─────────────────────────────────────────
    dpd_based_pd = con.execute("""
        SELECT
            PRODUCT_CODE,
            CASE
                WHEN DPD = 0 THEN 'CURRENT'
                WHEN DPD BETWEEN 1 AND 30 THEN 'SMA_0'
                WHEN DPD BETWEEN 31 AND 60 THEN 'SMA_1'
                WHEN DPD BETWEEN 61 AND 89 THEN 'SMA_2'
                ELSE 'NPA'
            END AS delinquency_band,
            COUNT(*) AS account_count,
            SUM(OUTSTANDING_PRINCIPAL) AS outstanding
        FROM loan_tape
        WHERE PRODUCT_CODE IS NOT NULL
        GROUP BY PRODUCT_CODE, 2
        ORDER BY PRODUCT_CODE, MIN(DPD)
    """).pl()

    return {
        "da_ref": "DA-039",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "actual_pd_by_segment": actual_pd_by_segment,
        "pd_comparison": pl.DataFrame(pd_comparison) if pd_comparison else pl.DataFrame(),
        "dpd_segmentation": dpd_based_pd,
        "summary": {
            "total_loans": len(df),
            "segments_analyzed": len(actual_pd_by_segment),
            "material_pd_mismatches": len(exceptions_df),
            "model_pd_provided": len(model_pd_data) > 0,
        },
        "anomaly_flags": anomaly_flags,
    }

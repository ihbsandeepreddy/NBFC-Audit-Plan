"""
DA-033: LGD Backtesting
Compute actual LGD from resolved NPAs; compare to management assumption.
LMS Risk Theme: 3
CAP Seq: R.33
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-033",
    "name": "LGD Backtesting",
    "description": "Actual LGD from resolved NPAs vs management assumption; flag > 15% understatement",
    "cap_seq": "R.33",
    "risk_theme": 3,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["resolved_npa_data"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    LGD Backtesting:
    1. From resolved NPAs: compute recovery_rate = amount_recovered / outstanding_at_default.
    2. LGD = 1 - recovery_rate.
    3. Compare to management LGD assumption.
    4. Flag if management LGD < actual LGD by > 15%.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    resolved_npa = kwargs.get("resolved_npa_data")
    management_lgd = kwargs.get("management_lgd", {})  # {product_code: lgd_rate}

    if resolved_npa is None:
        return {
            "da_ref": "DA-033",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "resolved_npa_data not provided"},
            "anomaly_flags": [{"field": "resolved_npa_data", "value": None,
                                "threshold": "Required", "message": "Resolved NPA data not provided"}],
        }

    if isinstance(resolved_npa, pl.DataFrame):
        res_df = resolved_npa
    elif isinstance(resolved_npa, pl.LazyFrame):
        res_df = resolved_npa.collect()
    else:
        res_df = pl.DataFrame(resolved_npa)

    con.register("resolved", res_df.to_arrow())

    # Detect columns
    recovery_col = "AMOUNT_RECOVERED" if "AMOUNT_RECOVERED" in res_df.columns else (
        "RECOVERY_AMOUNT" if "RECOVERY_AMOUNT" in res_df.columns else "SETTLED_AMOUNT"
    )
    npa_os_col = "OUTSTANDING_AT_DEFAULT" if "OUTSTANDING_AT_DEFAULT" in res_df.columns else (
        "NPA_OUTSTANDING" if "NPA_OUTSTANDING" in res_df.columns else "OUTSTANDING_PRINCIPAL"
    )
    product_col = "PRODUCT_CODE" if "PRODUCT_CODE" in res_df.columns else "PRODUCT"

    # ── Compute actual LGD ────────────────────────────────────────────────
    lgd_by_product = con.execute(f"""
        SELECT
            "{product_col}" AS PRODUCT_CODE,
            COUNT(*) AS resolved_npa_count,
            SUM("{npa_os_col}") AS total_npa_outstanding,
            SUM("{recovery_col}") AS total_recovered,
            ROUND(SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS recovery_rate,
            ROUND(1 - SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS actual_lgd
        FROM resolved
        WHERE "{npa_os_col}" > 0
        GROUP BY "{product_col}"
        ORDER BY actual_lgd DESC
    """).pl()

    # ── Compare to management LGD ──────────────────────────────────────────
    lgd_exceptions = []
    if management_lgd and len(lgd_by_product) > 0:
        for row in lgd_by_product.to_dicts():
            product = row.get("PRODUCT_CODE")
            actual_lgd = float(row.get("actual_lgd") or 0)
            mgmt_lgd = float(management_lgd.get(product, management_lgd.get("DEFAULT", 0.5)))
            if mgmt_lgd < actual_lgd - 0.15:  # management < actual by > 15%
                lgd_exceptions.append({
                    **row,
                    "management_lgd": mgmt_lgd,
                    "lgd_gap": round(actual_lgd - mgmt_lgd, 4),
                    "exception_type": "LGD_UNDERSTATED",
                })
                anomaly_flags.append({
                    "field": "MANAGEMENT_LGD",
                    "value": round(actual_lgd * 100, 2),
                    "threshold": f"Within 15% of actual LGD ({actual_lgd * 100:.2f}%)",
                    "message": f"Product {product}: Management LGD {mgmt_lgd * 100:.2f}% vs actual {actual_lgd * 100:.2f}% (understated by {(actual_lgd - mgmt_lgd) * 100:.2f}%)"
                })

    exceptions_df = pl.DataFrame(lgd_exceptions) if lgd_exceptions else pl.DataFrame()

    # ── Recovery analysis by resolution type ─────────────────────────────
    resolution_summary = pl.DataFrame()
    resolution_type_col = "RESOLUTION_TYPE" if "RESOLUTION_TYPE" in res_df.columns else None
    if resolution_type_col:
        resolution_summary = con.execute(f"""
            SELECT
                "{resolution_type_col}" AS resolution_type,
                COUNT(*) AS count,
                SUM("{npa_os_col}") AS total_outstanding,
                SUM("{recovery_col}") AS total_recovered,
                ROUND(SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS recovery_rate,
                ROUND(1 - SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS lgd
            FROM resolved
            WHERE "{npa_os_col}" > 0
            GROUP BY "{resolution_type_col}"
            ORDER BY count DESC
        """).pl()

    # Overall LGD
    overall = con.execute(f"""
        SELECT
            COUNT(*) AS total_resolved,
            SUM("{npa_os_col}") AS total_outstanding,
            SUM("{recovery_col}") AS total_recovered,
            ROUND(SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS overall_recovery_rate,
            ROUND(1 - SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS overall_lgd
        FROM resolved WHERE "{npa_os_col}" > 0
    """).pl().to_dicts()[0]

    return {
        "da_ref": "DA-033",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "lgd_by_product": lgd_by_product,
        "resolution_summary": resolution_summary,
        "summary": {
            "resolved_npa_count": int(overall.get("total_resolved") or 0),
            "total_npa_outstanding": round(float(overall.get("total_outstanding") or 0), 2),
            "total_recovered": round(float(overall.get("total_recovered") or 0), 2),
            "overall_recovery_rate": round(float(overall.get("overall_recovery_rate") or 0), 4),
            "overall_lgd": round(float(overall.get("overall_lgd") or 0), 4),
            "lgd_understatement_cases": len(exceptions_df),
        },
        "anomaly_flags": anomaly_flags,
    }

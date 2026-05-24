"""
DA-040: LGD Actual vs Model by Product
Product-level LGD backtesting using resolved NPAs.
LMS Risk Theme: 3
CAP Seq: R.40
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-040",
    "name": "LGD Actual vs Model by Product",
    "description": "Product-level LGD backtesting; actual recovery vs management assumption",
    "cap_seq": "R.40",
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
    LGD Actual vs Model by Product:
    1. Use resolved NPAs: recovery_amount / outstanding_at_npa_classification.
    2. Compare to management assumption per product.
    3. Flag products with material understatement.

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
            "da_ref": "DA-040",
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
    collateral_col = "COLLATERAL_REALIZED" if "COLLATERAL_REALIZED" in res_df.columns else None

    # ── Compute LGD by product ────────────────────────────────────────────
    if collateral_col and collateral_col in res_df.columns:
        lgd_sql = f"""
            SELECT
                "{product_col}" AS PRODUCT_CODE,
                COUNT(*) AS resolved_count,
                SUM("{npa_os_col}") AS total_npa_outstanding,
                SUM("{recovery_col}") AS total_cash_recovered,
                SUM("{collateral_col}") AS total_collateral_realized,
                SUM("{recovery_col}" + COALESCE("{collateral_col}", 0)) AS total_recovered,
                ROUND(SUM("{recovery_col}" + COALESCE("{collateral_col}", 0)) / NULLIF(SUM("{npa_os_col}"), 0), 4) AS recovery_rate,
                ROUND(1 - SUM("{recovery_col}" + COALESCE("{collateral_col}", 0)) / NULLIF(SUM("{npa_os_col}"), 0), 4) AS actual_lgd
            FROM resolved
            WHERE "{npa_os_col}" > 0
            GROUP BY "{product_col}"
            ORDER BY actual_lgd DESC
        """
    else:
        lgd_sql = f"""
            SELECT
                "{product_col}" AS PRODUCT_CODE,
                COUNT(*) AS resolved_count,
                SUM("{npa_os_col}") AS total_npa_outstanding,
                SUM("{recovery_col}") AS total_recovered,
                ROUND(SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS recovery_rate,
                ROUND(1 - SUM("{recovery_col}") / NULLIF(SUM("{npa_os_col}"), 0), 4) AS actual_lgd
            FROM resolved
            WHERE "{npa_os_col}" > 0
            GROUP BY "{product_col}"
            ORDER BY actual_lgd DESC
        """

    lgd_by_product = con.execute(lgd_sql).pl()

    # ── Compare to management LGD ──────────────────────────────────────────
    lgd_comparison = []
    if management_lgd and len(lgd_by_product) > 0:
        for row in lgd_by_product.to_dicts():
            product = row.get("PRODUCT_CODE")
            actual_lgd = float(row.get("actual_lgd") or 0)
            mgmt_lgd = float(management_lgd.get(product, management_lgd.get("DEFAULT", 0.5)))
            gap = actual_lgd - mgmt_lgd
            lgd_comparison.append({
                **row,
                "management_lgd": mgmt_lgd,
                "lgd_gap_abs": round(gap, 4),
                "lgd_gap_rel_pct": round(gap / mgmt_lgd * 100, 2) if mgmt_lgd != 0 else None,
                "direction": "UNDERSTATED" if gap > 0 else "OVERSTATED",
                "material": abs(gap) > 0.15,
            })
            if abs(gap) > 0.15:
                anomaly_flags.append({
                    "field": "MANAGEMENT_LGD",
                    "value": round(actual_lgd * 100, 2),
                    "threshold": f"Within 15% of actual LGD ({actual_lgd * 100:.2f}%)",
                    "message": f"Product {product}: Management LGD {mgmt_lgd * 100:.2f}% vs actual {actual_lgd * 100:.2f}% (gap: {gap * 100:.2f}%)"
                })

    exceptions_df = pl.DataFrame([r for r in lgd_comparison if r.get("material")]) if lgd_comparison else pl.DataFrame()

    return {
        "da_ref": "DA-040",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "lgd_by_product": lgd_by_product,
        "lgd_comparison": pl.DataFrame(lgd_comparison) if lgd_comparison else pl.DataFrame(),
        "summary": {
            "resolved_npa_records": len(res_df),
            "products_analyzed": len(lgd_by_product),
            "material_lgd_mismatches": len(exceptions_df),
        },
        "anomaly_flags": anomaly_flags,
    }

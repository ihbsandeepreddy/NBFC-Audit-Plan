"""
DA-041: CRAR RWA Validation
Compute auditor RWA vs management RWA; flag unincluded off-balance-sheet items.
LMS Risk Theme: 12
CAP Seq: R.41
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-041",
    "name": "CRAR RWA Validation",
    "description": "Compute auditor RWA on-BS; compare to management; flag off-BS items",
    "cap_seq": "R.41",
    "risk_theme": 12,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["rwa_weights"],
}

# Default RBI risk weights
DEFAULT_RWA_WEIGHTS = {
    "HOME_LOAN": 35,       # Housing loans <= 75L
    "HOUSING": 35,
    "PERSONAL": 100,
    "CONSUMER": 100,
    "VEHICLE": 100,
    "GOLD": 100,
    "BUSINESS": 100,
    "MSME": 100,
    "NPA": 150,
    "DEFAULT": 100,
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    CRAR RWA Validation:
    1. Apply product-wise RBI risk weights to outstanding principal.
    2. NPA accounts: 150% risk weight.
    3. Compare auditor RWA vs management RWA (if provided).
    4. Flag unincluded off-balance-sheet items.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    rwa_weights = kwargs.get("rwa_weights", DEFAULT_RWA_WEIGHTS)
    management_rwa = kwargs.get("management_rwa")  # Single number or dict

    # Build risk weight table
    weight_rows = []
    for product, weight in rwa_weights.items():
        weight_rows.append({"product_code": product, "risk_weight_pct": float(weight)})

    if not weight_rows:
        weight_rows = [{"product_code": p, "risk_weight_pct": 100.0}
                       for p in DEFAULT_RWA_WEIGHTS.items()]

    rw_df = pl.DataFrame(weight_rows)
    con.register("risk_weights", rw_df.to_arrow())

    # ── Compute auditor RWA ────────────────────────────────────────────────
    rwa_by_product = con.execute("""
        WITH loan_rw AS (
            SELECT
                l.LOAN_ACCOUNT_NO,
                l.PRODUCT_CODE,
                l.OUTSTANDING_PRINCIPAL,
                l.IND_AS_STAGE,
                l.DPD,
                -- NPA gets 150%, others per product
                CASE
                    WHEN l.IND_AS_STAGE = 3 OR l.DPD >= 90 THEN 150.0
                    ELSE COALESCE(rw.risk_weight_pct, 100.0)
                END AS risk_weight_pct
            FROM loan_tape l
            LEFT JOIN risk_weights rw ON UPPER(l.PRODUCT_CODE) = UPPER(rw.product_code)
            WHERE l.OUTSTANDING_PRINCIPAL IS NOT NULL AND l.OUTSTANDING_PRINCIPAL > 0
        )
        SELECT
            PRODUCT_CODE,
            CASE WHEN IND_AS_STAGE = 3 OR DPD >= 90 THEN 'NPA' ELSE 'STANDARD' END AS asset_status,
            risk_weight_pct,
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(OUTSTANDING_PRINCIPAL * risk_weight_pct / 100.0) AS rwa_amount
        FROM loan_rw
        GROUP BY PRODUCT_CODE, asset_status, risk_weight_pct
        ORDER BY rwa_amount DESC
    """).pl()

    auditor_rwa = float(rwa_by_product["rwa_amount"].sum() or 0)

    # ── Off-balance-sheet items ─────────────────────────────────────────────
    off_bs_rwa = 0.0
    off_bs_items = kwargs.get("off_bs_items")
    if off_bs_items is not None:
        if isinstance(off_bs_items, (int, float)):
            off_bs_rwa = float(off_bs_items)
        elif isinstance(off_bs_items, list):
            for item in off_bs_items:
                if isinstance(item, dict):
                    amount = float(item.get("amount", 0) or 0)
                    ccf = float(item.get("credit_conversion_factor", 1.0))  # Default 100% CCF
                    rw = float(item.get("risk_weight", 100)) / 100.0
                    off_bs_rwa += amount * ccf * rw

    total_auditor_rwa = auditor_rwa + off_bs_rwa

    # ── Compare to management ─────────────────────────────────────────────
    rwa_diff = 0.0
    rwa_diff_pct = 0.0
    if management_rwa:
        mgmt_rwa_total = float(management_rwa) if isinstance(management_rwa, (int, float)) else 0
        rwa_diff = total_auditor_rwa - mgmt_rwa_total
        rwa_diff_pct = rwa_diff / mgmt_rwa_total * 100 if mgmt_rwa_total != 0 else 0

        if abs(rwa_diff_pct) > 5:  # > 5% material difference
            anomaly_flags.append({
                "field": "RWA",
                "value": round(rwa_diff, 2),
                "threshold": "Auditor RWA within 5% of management RWA",
                "message": f"Auditor RWA ₹{total_auditor_rwa:,.0f} vs Management ₹{mgmt_rwa_total:,.0f} (diff: {rwa_diff_pct:.2f}%)"
            })

    if off_bs_rwa > 0 and not off_bs_items:
        anomaly_flags.append({
            "field": "OFF_BALANCE_SHEET",
            "value": off_bs_rwa,
            "threshold": "All off-BS items should be included in RWA",
            "message": f"Off-balance-sheet items with RWA ₹{off_bs_rwa:,.0f} need verification"
        })

    return {
        "da_ref": "DA-041",
        "total_records": len(df),
        "exceptions_count": 1 if rwa_diff_pct > 5 else 0,
        "exceptions_df": pl.DataFrame(),
        "rwa_by_product": rwa_by_product,
        "summary": {
            "auditor_rwa_on_bs": round(auditor_rwa, 2),
            "auditor_rwa_off_bs": round(off_bs_rwa, 2),
            "total_auditor_rwa": round(total_auditor_rwa, 2),
            "management_rwa": round(float(management_rwa or 0), 2),
            "rwa_difference": round(rwa_diff, 2),
            "rwa_diff_pct": round(rwa_diff_pct, 2),
        },
        "anomaly_flags": anomaly_flags,
    }

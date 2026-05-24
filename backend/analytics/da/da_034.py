"""
DA-034: Macro Overlay Test
Validate directional consistency of management macro overlay on ECL.
LMS Risk Theme: 3
CAP Seq: R.34
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-034",
    "name": "Macro Overlay Test",
    "description": "Validate ECL macro overlay direction vs macro events; flag net-positive overlays",
    "cap_seq": "R.34",
    "risk_theme": 3,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["macro_events"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Macro Overlay Test:
    1. Validate directional consistency: adverse macro event → increase ECL.
    2. Check if overlay is directionally appropriate.
    3. Flag if overlay is net positive (reducing ECL) without documented justification.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    macro_events = kwargs.get("macro_events", [])
    management_overlays = kwargs.get("management_overlays", [])  # [{period, product, overlay_amount, direction}]

    if not macro_events and not management_overlays:
        return {
            "da_ref": "DA-034",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "macro_events and management_overlays not provided"},
            "anomaly_flags": [{"field": "macro_events", "value": None,
                                "threshold": "Required", "message": "Macro events not provided"}],
        }

    # ── Analyze overlay data ───────────────────────────────────────────────
    overlay_exceptions = []

    if isinstance(management_overlays, list) and management_overlays:
        overlay_df = pl.DataFrame(management_overlays)
        con.register("overlays", overlay_df.to_arrow())

        overlay_amount_col = "overlay_amount" if "overlay_amount" in overlay_df.columns else "OVERLAY_AMOUNT"
        direction_col = "direction" if "direction" in overlay_df.columns else "DIRECTION"
        period_col = "period" if "period" in overlay_df.columns else "PERIOD"
        justification_col = "justification" if "justification" in overlay_df.columns else None

        # Flag net-positive overlays (reducing ECL) without justification
        if overlay_amount_col in overlay_df.columns:
            net_positive_q = f"""
                SELECT *,
                    CASE
                        WHEN {overlay_amount_col} < 0 THEN 'ECL_REDUCING_OVERLAY'
                        ELSE 'ECL_INCREASING_OVERLAY'
                    END AS overlay_direction
                FROM overlays
                WHERE {overlay_amount_col} < 0
            """
            if justification_col:
                net_positive_q = f"""
                    SELECT *,
                        CASE
                            WHEN {overlay_amount_col} < 0 THEN 'ECL_REDUCING_OVERLAY'
                            ELSE 'ECL_INCREASING_OVERLAY'
                        END AS overlay_direction
                    FROM overlays
                    WHERE {overlay_amount_col} < 0
                      AND ({justification_col} IS NULL OR TRIM({justification_col}) = '')
                """

            net_positive_df = con.execute(net_positive_q).pl()

            if len(net_positive_df) > 0:
                total_reduction = float(net_positive_df[overlay_amount_col].sum() or 0)
                anomaly_flags.append({
                    "field": "OVERLAY_AMOUNT",
                    "value": len(net_positive_df),
                    "threshold": "ECL-reducing overlays require documented justification",
                    "message": f"{len(net_positive_df)} ECL-reducing overlays without justification; total reduction ₹{abs(total_reduction):,.0f}"
                })
                overlay_exceptions = net_positive_df.to_dicts()

    # ── Directional consistency check ─────────────────────────────────────
    if macro_events and management_overlays:
        # Check if adverse events have positive overlay
        adverse_events = [e for e in macro_events if e.get("severity", "NEUTRAL").upper() in ("ADVERSE", "HIGH", "SEVERE")]
        positive_overlays = [o for o in management_overlays if float(o.get("overlay_amount", 0)) > 0]

        if adverse_events and not positive_overlays:
            anomaly_flags.append({
                "field": "MACRO_OVERLAY",
                "value": len(adverse_events),
                "threshold": "Adverse macro events should result in positive ECL overlay",
                "message": f"{len(adverse_events)} adverse macro events with no corresponding positive ECL overlay"
            })

        favorable_events = [e for e in macro_events if e.get("severity", "NEUTRAL").upper() in ("FAVORABLE", "LOW", "POSITIVE")]
        reducing_overlays = [o for o in management_overlays if float(o.get("overlay_amount", 0)) < 0]

        if reducing_overlays and not favorable_events:
            total_reduction = sum(float(o.get("overlay_amount", 0)) for o in reducing_overlays)
            anomaly_flags.append({
                "field": "MACRO_OVERLAY",
                "value": len(reducing_overlays),
                "threshold": "ECL-reducing overlays require favorable macro events",
                "message": f"{len(reducing_overlays)} ECL-reducing overlays (₹{abs(total_reduction):,.0f}) without favorable macro event justification"
            })

    exceptions_df = pl.DataFrame(overlay_exceptions) if overlay_exceptions else pl.DataFrame()

    # Macro events summary
    macro_summary = {
        "total_macro_events": len(macro_events) if isinstance(macro_events, list) else 0,
        "adverse_events": len([e for e in macro_events if e.get("severity", "").upper() in ("ADVERSE", "HIGH")] if isinstance(macro_events, list) else []),
        "total_overlays": len(management_overlays) if isinstance(management_overlays, list) else 0,
        "ecl_reducing_overlays": len([o for o in management_overlays if float(o.get("overlay_amount", 0)) < 0] if isinstance(management_overlays, list) else []),
    }

    return {
        "da_ref": "DA-034",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "summary": macro_summary,
        "anomaly_flags": anomaly_flags,
    }

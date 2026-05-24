"""
DA-028: Geographic Concentration
Flag state/district concentration; compute HHI and NPA comparison by geography.
LMS Risk Theme: 2
CAP Seq: R.28
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-028",
    "name": "Geographic Concentration",
    "description": "State/district portfolio concentration > 30%; NPA comparison; HHI index",
    "cap_seq": "R.28",
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
    Geographic Concentration:
    1. Compute outstanding by state derived from BRANCH_CODE prefix (or STATE column).
    2. Flag state > 30% of total portfolio.
    3. Flag state where NPA% > 2x national average.
    4. HHI computation by state.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # Determine geography column
    geo_col = None
    for candidate in ["STATE", "STATE_CODE", "GEOGRAPHY", "REGION"]:
        if candidate in df.columns:
            geo_col = candidate
            break

    if geo_col is None and "BRANCH_CODE" in df.columns:
        # Derive state from first 2 chars of branch code
        df = df.with_columns(
            pl.col("BRANCH_CODE").str.slice(0, 2).alias("STATE_DERIVED")
        )
        geo_col = "STATE_DERIVED"
        con.register("loan_tape", df.to_arrow())

    if geo_col is None:
        return {
            "da_ref": "DA-028",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "No geography column found (STATE, BRANCH_CODE, etc.)"},
            "anomaly_flags": [],
        }

    # ── Portfolio totals ───────────────────────────────────────────────────
    totals = con.execute("""
        SELECT
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS total_npa,
            COUNT(*) AS total_loans
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL
    """).pl().to_dicts()[0]

    total_os = float(totals.get("total_outstanding") or 1)
    national_npa_pct = float(totals.get("total_npa") or 0) / total_os * 100

    # ── State-level analysis ───────────────────────────────────────────────
    state_analysis = con.execute(f"""
        SELECT
            "{geo_col}" AS state,
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_amount,
            ROUND(100.0 * SUM(OUTSTANDING_PRINCIPAL) / {total_os}, 2) AS portfolio_share_pct,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS state_npa_pct,
            SUM(DISBURSEMENT_AMOUNT) AS total_disbursed
        FROM loan_tape
        WHERE "{geo_col}" IS NOT NULL
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
        GROUP BY "{geo_col}"
        ORDER BY total_outstanding DESC
    """).pl()

    # ── Flag state > 30% portfolio ─────────────────────────────────────────
    high_concentration = state_analysis.filter(pl.col("portfolio_share_pct") > 30)
    if len(high_concentration) > 0:
        for row in high_concentration.to_dicts():
            anomaly_flags.append({
                "field": "STATE",
                "value": row["portfolio_share_pct"],
                "threshold": "30% max per state",
                "message": f"State '{row['state']}' has {row['portfolio_share_pct']:.1f}% of portfolio (> 30% limit)"
            })

    # ── Flag state NPA% > 2x national average ─────────────────────────────
    high_npa_states = state_analysis.filter(
        (pl.col("state_npa_pct") > national_npa_pct * 2) &
        (pl.col("state_npa_pct") > 0)
    )
    if len(high_npa_states) > 0:
        anomaly_flags.append({
            "field": "STATE_NPA_PCT",
            "value": len(high_npa_states),
            "threshold": f"< {national_npa_pct * 2:.2f}% (2x national average)",
            "message": f"{len(high_npa_states)} states with NPA% > 2x national average ({national_npa_pct:.2f}%)"
        })

    # ── HHI computation by state ───────────────────────────────────────────
    if len(state_analysis) > 0:
        shares = (state_analysis["total_outstanding"] / total_os * 100).to_list()
        hhi = round(sum(s ** 2 for s in shares if s is not None), 2)
    else:
        hhi = 0.0

    if hhi > 2500:
        anomaly_flags.append({
            "field": "HHI_GEOGRAPHIC",
            "value": hhi,
            "threshold": "< 2500 (moderate concentration)",
            "message": f"Geographic HHI = {hhi:.0f} (highly concentrated portfolio)"
        })

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [high_concentration, high_npa_states] if len(f) > 0]
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

    return {
        "da_ref": "DA-028",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "state_analysis": state_analysis,
        "high_concentration_states": high_concentration,
        "high_npa_states": high_npa_states,
        "hhi_geographic": hhi,
        "summary": {
            "total_loans": len(df),
            "total_outstanding": round(total_os, 2),
            "national_npa_pct": round(national_npa_pct, 2),
            "states_above_30pct": len(high_concentration),
            "states_above_2x_npa": len(high_npa_states),
            "hhi": hhi,
            "hhi_level": "HIGH" if hhi > 2500 else ("MODERATE" if hhi > 1500 else "LOW"),
        },
        "anomaly_flags": anomaly_flags,
    }

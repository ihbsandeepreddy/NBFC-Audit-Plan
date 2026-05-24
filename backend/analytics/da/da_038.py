"""
DA-038: NPA Resolution Analysis
Compute NPA resolution rates; flag premature upgrades not meeting RBI cure criteria.
LMS Risk Theme: 4
CAP Seq: R.38
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-038",
    "name": "NPA Resolution Analysis",
    "description": "NPA resolution rates; flag upgrades without 12-month clean DPD (RBI cure criteria)",
    "cap_seq": "R.38",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["npa_register"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    NPA Resolution Analysis:
    1. From npa_register, compute resolution rates by product/branch.
    2. Recovery rates: upgrade vs write-off vs settlement.
    3. Flag accounts upgraded from NPA without meeting RBI cure criteria (DPD=0 for 12 months).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    npa_register = kwargs.get("npa_register")

    if npa_register is None:
        return {
            "da_ref": "DA-038",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "npa_register not provided"},
            "anomaly_flags": [{"field": "npa_register", "value": None,
                                "threshold": "Required", "message": "NPA register not provided"}],
        }

    if isinstance(npa_register, pl.DataFrame):
        npa_df = npa_register
    elif isinstance(npa_register, pl.LazyFrame):
        npa_df = npa_register.collect()
    else:
        npa_df = pl.DataFrame(npa_register)

    con.register("npa_reg", npa_df.to_arrow())

    # Detect columns
    npa_date_col = "NPA_DATE" if "NPA_DATE" in npa_df.columns else "CLASSIFICATION_DATE"
    upgrade_date_col = "UPGRADE_DATE" if "UPGRADE_DATE" in npa_df.columns else "RESOLUTION_DATE"
    resolution_col = "RESOLUTION_TYPE" if "RESOLUTION_TYPE" in npa_df.columns else "STATUS"
    lan_col = "LOAN_ACCOUNT_NO" if "LOAN_ACCOUNT_NO" in npa_df.columns else "LAN"
    product_col = "PRODUCT_CODE" if "PRODUCT_CODE" in npa_df.columns else "PRODUCT"

    # ── 1. Resolution rate summary ────────────────────────────────────────
    resolution_summary = con.execute(f"""
        SELECT
            "{product_col}" AS PRODUCT_CODE,
            COUNT(*) AS total_npa_accounts,
            SUM(CASE WHEN "{resolution_col}" IN ('UPGRADED', 'REGULARIZED', 'CURED') THEN 1 ELSE 0 END) AS upgraded_count,
            SUM(CASE WHEN "{resolution_col}" IN ('WRITTEN_OFF', 'WRITEOFF', 'TECHNICALLY_WRITTEN_OFF') THEN 1 ELSE 0 END) AS writeoff_count,
            SUM(CASE WHEN "{resolution_col}" IN ('SETTLED', 'OTS', 'ONE_TIME_SETTLEMENT') THEN 1 ELSE 0 END) AS settled_count,
            ROUND(100.0 * SUM(CASE WHEN "{resolution_col}" IN ('UPGRADED', 'REGULARIZED', 'CURED') THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 2) AS upgrade_rate_pct
        FROM npa_reg
        GROUP BY "{product_col}"
        ORDER BY total_npa_accounts DESC
    """).pl()

    # ── 2. Premature upgrades: upgraded < 12 months after NPA date ────────
    premature_upgrades = pl.DataFrame()
    if npa_date_col in npa_df.columns and upgrade_date_col in npa_df.columns:
        premature_upgrades = con.execute(f"""
            SELECT
                n."{lan_col}" AS LOAN_ACCOUNT_NO,
                n."{product_col}" AS PRODUCT_CODE,
                n."{npa_date_col}" AS npa_date,
                n."{upgrade_date_col}" AS upgrade_date,
                DATE_DIFF('month', CAST(n."{npa_date_col}" AS DATE),
                    CAST(n."{upgrade_date_col}" AS DATE)) AS months_as_npa,
                l.DPD AS current_dpd,
                l.IND_AS_STAGE AS current_stage,
                l.OUTSTANDING_PRINCIPAL,
                'PREMATURE_NPA_UPGRADE' AS exception_type
            FROM npa_reg n
            LEFT JOIN loan_tape l ON n."{lan_col}" = l.LOAN_ACCOUNT_NO
            WHERE UPPER(n."{resolution_col}") IN ('UPGRADED', 'REGULARIZED', 'CURED')
              AND n."{upgrade_date_col}" IS NOT NULL
              AND n."{npa_date_col}" IS NOT NULL
              AND DATE_DIFF('month', CAST(n."{npa_date_col}" AS DATE),
                  CAST(n."{upgrade_date_col}" AS DATE)) < 12
            ORDER BY months_as_npa ASC
        """).pl()

        if len(premature_upgrades) > 0:
            anomaly_flags.append({
                "field": "UPGRADE_DATE",
                "value": len(premature_upgrades),
                "threshold": "12 months DPD=0 before upgrade (RBI criteria)",
                "message": f"{len(premature_upgrades)} NPA accounts upgraded before completing 12-month cure period"
            })

    # ── 3. Re-NPA analysis: recently upgraded accounts back in NPA ────────
    renpa_df = pl.DataFrame()
    if upgrade_date_col in npa_df.columns:
        renpa_df = con.execute(f"""
            SELECT
                n."{lan_col}" AS LOAN_ACCOUNT_NO,
                n."{product_col}" AS PRODUCT_CODE,
                n."{upgrade_date_col}" AS upgrade_date,
                l.DPD AS current_dpd,
                l.IND_AS_STAGE AS current_stage,
                l.OUTSTANDING_PRINCIPAL,
                DATE_DIFF('day', CAST(n."{upgrade_date_col}" AS DATE), CAST('{reporting_date}' AS DATE)) AS days_since_upgrade,
                'RE_NPA_WITHIN_90_DAYS' AS exception_type
            FROM npa_reg n
            JOIN loan_tape l ON n."{lan_col}" = l.LOAN_ACCOUNT_NO
            WHERE UPPER(n."{resolution_col}") IN ('UPGRADED', 'REGULARIZED', 'CURED')
              AND l.DPD >= 90
              AND DATE_DIFF('day', CAST(n."{upgrade_date_col}" AS DATE), CAST('{reporting_date}' AS DATE)) <= 90
        """).pl()

        if len(renpa_df) > 0:
            anomaly_flags.append({
                "field": "DPD",
                "value": len(renpa_df),
                "threshold": "< 90 DPD within 90 days of upgrade",
                "message": f"{len(renpa_df)} accounts upgraded from NPA now back at DPD >= 90 within 90 days"
            })

    exc_frames = [f for f in [premature_upgrades, renpa_df] if len(f) > 0]
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
        "da_ref": "DA-038",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "resolution_summary": resolution_summary,
        "premature_upgrades": premature_upgrades,
        "renpa_accounts": renpa_df,
        "summary": {
            "total_npa_register": len(npa_df),
            "premature_upgrades": len(premature_upgrades),
            "renpa_within_90d": len(renpa_df),
        },
        "anomaly_flags": anomaly_flags,
    }

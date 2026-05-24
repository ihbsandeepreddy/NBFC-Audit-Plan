"""
DA-008: Branch/DSA Concentration Analysis
Flag high branch/DSA concentration in PAR and disbursements; compute HHI.
LMS Risk Theme: 2
CAP Seq: R.08
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-008",
    "name": "Branch/DSA Concentration Analysis",
    "description": "Flag branch > 20% PAR, DSA > 15% disbursements, HHI computation",
    "cap_seq": "R.08",
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
    Branch/DSA Concentration Analysis:
    1. Flag any branch with > 20% of total PAR.
    2. Flag any DSA with > 15% of total disbursements.
    3. Flag branches with NPA% > 2x portfolio average.
    4. Geographic HHI computation.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── Portfolio totals ───────────────────────────────────────────────────
    portfolio_totals = con.execute("""
        SELECT
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS total_par,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS total_npa,
            SUM(DISBURSEMENT_AMOUNT) AS total_disbursements,
            COUNT(*) AS total_loans,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS portfolio_npa_pct
        FROM loan_tape
        WHERE OUTSTANDING_PRINCIPAL IS NOT NULL
    """).pl().to_dicts()[0]

    total_par = portfolio_totals.get("total_par") or 0
    total_disb = portfolio_totals.get("total_disbursements") or 0
    portfolio_npa_pct = portfolio_totals.get("portfolio_npa_pct") or 0

    # ── 1. Branch PAR concentration ───────────────────────────────────────
    branch_par_df = con.execute(f"""
        SELECT
            BRANCH_CODE,
            COUNT(*) AS loan_count,
            SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
            SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_amount,
            SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_amount,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS branch_par_pct,
            ROUND(100.0 * SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS branch_npa_pct,
            ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                / NULLIF({total_par}, 0), 2) AS par_share_pct
        FROM loan_tape
        WHERE BRANCH_CODE IS NOT NULL
          AND OUTSTANDING_PRINCIPAL IS NOT NULL
        GROUP BY BRANCH_CODE
        ORDER BY par_amount DESC
    """).pl()

    branch_par_exceptions = branch_par_df.filter(pl.col("par_share_pct") > 20)
    if len(branch_par_exceptions) > 0:
        anomaly_flags.append({
            "field": "BRANCH_CODE",
            "value": len(branch_par_exceptions),
            "threshold": "< 20% of total PAR per branch",
            "message": f"{len(branch_par_exceptions)} branches with > 20% of total portfolio PAR"
        })

    # ── 2. Branch NPA% > 2x portfolio average ─────────────────────────────
    high_npa_branches = branch_par_df.filter(
        (pl.col("branch_npa_pct") > portfolio_npa_pct * 2) & (pl.col("branch_npa_pct") > 0)
    )
    if len(high_npa_branches) > 0:
        anomaly_flags.append({
            "field": "BRANCH_NPA_PCT",
            "value": len(high_npa_branches),
            "threshold": f"< {portfolio_npa_pct * 2:.2f}% (2x portfolio average)",
            "message": f"{len(high_npa_branches)} branches with NPA% > 2x portfolio average ({portfolio_npa_pct:.2f}%)"
        })

    # ── 3. DSA disbursement concentration ─────────────────────────────────
    dsa_disb_df = pl.DataFrame()
    dsa_exceptions = pl.DataFrame()
    if "DSA_CODE" in df.columns:
        dsa_disb_df = con.execute(f"""
            SELECT
                DSA_CODE,
                COUNT(*) AS loan_count,
                SUM(DISBURSEMENT_AMOUNT) AS total_disbursed,
                ROUND(100.0 * SUM(DISBURSEMENT_AMOUNT) / NULLIF({total_disb}, 0), 2) AS disb_share_pct,
                SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS par_amount,
                ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                    / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS dsa_par_pct
            FROM loan_tape
            WHERE DSA_CODE IS NOT NULL
              AND DISBURSEMENT_AMOUNT IS NOT NULL
            GROUP BY DSA_CODE
            ORDER BY total_disbursed DESC
        """).pl()

        dsa_exceptions = dsa_disb_df.filter(pl.col("disb_share_pct") > 15)
        if len(dsa_exceptions) > 0:
            anomaly_flags.append({
                "field": "DSA_CODE",
                "value": len(dsa_exceptions),
                "threshold": "< 15% of disbursements per DSA",
                "message": f"{len(dsa_exceptions)} DSAs with > 15% of total disbursements"
            })

    # ── 4. HHI computation ────────────────────────────────────────────────
    # HHI = sum of (market_share_pct)^2 — range 0 to 10000
    # > 2500 = highly concentrated, 1500-2500 = moderate
    hhi_branch = 0.0
    hhi_dsa = 0.0
    if len(branch_par_df) > 0 and "total_outstanding" in branch_par_df.columns:
        total_os = float(branch_par_df["total_outstanding"].sum() or 1)
        branch_shares = (branch_par_df["total_outstanding"] / total_os * 100).to_list()
        hhi_branch = round(sum(s ** 2 for s in branch_shares if s), 2)

    if len(dsa_disb_df) > 0 and "total_disbursed" in dsa_disb_df.columns:
        total_d = float(dsa_disb_df["total_disbursed"].sum() or 1)
        dsa_shares = (dsa_disb_df["total_disbursed"] / total_d * 100).to_list()
        hhi_dsa = round(sum(s ** 2 for s in dsa_shares if s), 2)

    if hhi_branch > 2500:
        anomaly_flags.append({
            "field": "HHI_BRANCH",
            "value": hhi_branch,
            "threshold": "< 2500 (moderate concentration)",
            "message": f"Branch concentration HHI = {hhi_branch:.0f} (> 2500: highly concentrated)"
        })

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [branch_par_exceptions, high_npa_branches, dsa_exceptions] if len(f) > 0]
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
        "da_ref": "DA-008",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "branch_par_analysis": branch_par_df,
        "dsa_disb_analysis": dsa_disb_df,
        "hhi_branch": hhi_branch,
        "hhi_dsa": hhi_dsa,
        "summary": {
            "total_loans": len(df),
            "portfolio_npa_pct": portfolio_npa_pct,
            "branches_above_20pct_par": len(branch_par_exceptions),
            "branches_above_2x_avg_npa": len(high_npa_branches),
            "dsas_above_15pct_disb": len(dsa_exceptions),
            "hhi_branch": hhi_branch,
            "hhi_dsa": hhi_dsa,
            "hhi_branch_level": "HIGH" if hhi_branch > 2500 else ("MODERATE" if hhi_branch > 1500 else "LOW"),
        },
        "anomaly_flags": anomaly_flags,
    }

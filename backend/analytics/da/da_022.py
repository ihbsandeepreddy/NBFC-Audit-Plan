"""
DA-022: Technical Write-off / Waiver Analysis
Flag write-offs and waivers without proper approval; check NPA interest reversal.
LMS Risk Theme: 10
CAP Seq: R.22
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-022",
    "name": "Technical Write-off / Waiver Analysis",
    "description": "Flag unapproved write-offs; waivers > ₹5L without Board approval; NPA interest reversal",
    "cap_seq": "R.22",
    "risk_theme": 10,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["writeoff_data"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Write-off and Waiver Analysis:
    1. Flag write-offs without appropriate approval reference.
    2. Flag waivers > ₹5L without Board/CC approval.
    3. Check if NPA interest was reversed on write-off date.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    writeoff_data = kwargs.get("writeoff_data")

    if writeoff_data is None:
        return {
            "da_ref": "DA-022",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "writeoff_data not provided"},
            "anomaly_flags": [{"field": "writeoff_data", "value": None,
                                "threshold": "Required", "message": "Write-off data not provided"}],
        }

    if isinstance(writeoff_data, pl.DataFrame):
        wo_df = writeoff_data
    elif isinstance(writeoff_data, pl.LazyFrame):
        wo_df = writeoff_data.collect()
    else:
        wo_df = pl.DataFrame(writeoff_data)

    con.register("writeoffs", wo_df.to_arrow())

    # Detect column names
    amount_col = "WRITEOFF_AMOUNT" if "WRITEOFF_AMOUNT" in wo_df.columns else (
        "WAIVER_AMOUNT" if "WAIVER_AMOUNT" in wo_df.columns else "AMOUNT"
    )
    approval_col = "APPROVAL_AUTHORITY" if "APPROVAL_AUTHORITY" in wo_df.columns else (
        "APPROVED_BY" if "APPROVED_BY" in wo_df.columns else None
    )
    approval_ref_col = "APPROVAL_REF" if "APPROVAL_REF" in wo_df.columns else (
        "BOARD_APPROVAL_REF" if "BOARD_APPROVAL_REF" in wo_df.columns else None
    )
    wo_date_col = "WRITEOFF_DATE" if "WRITEOFF_DATE" in wo_df.columns else "WO_DATE"
    wo_type_col = "TYPE" if "TYPE" in wo_df.columns else "TRANSACTION_TYPE"
    lan_col = "LOAN_ACCOUNT_NO" if "LOAN_ACCOUNT_NO" in wo_df.columns else "LAN"
    interest_reversal_col = "INTEREST_REVERSED" if "INTEREST_REVERSED" in wo_df.columns else None

    # ── 1. Write-offs without approval ────────────────────────────────────
    unapproved_wo = pl.DataFrame()
    if approval_ref_col:
        unapproved_wo = con.execute(f"""
            SELECT
                w."{lan_col}" AS LOAN_ACCOUNT_NO,
                w."{amount_col}" AS writeoff_amount,
                w."{wo_date_col}" AS writeoff_date,
                w."{approval_ref_col}" AS approval_ref,
                'WRITEOFF_WITHOUT_APPROVAL' AS exception_type
            FROM writeoffs w
            WHERE (w."{approval_ref_col}" IS NULL OR TRIM(w."{approval_ref_col}") = '')
              AND w."{amount_col}" > 0
            ORDER BY w."{amount_col}" DESC
        """).pl()

        if len(unapproved_wo) > 0:
            total = float(unapproved_wo["writeoff_amount"].sum() or 0)
            anomaly_flags.append({
                "field": "APPROVAL_REF",
                "value": len(unapproved_wo),
                "threshold": "All write-offs require approval",
                "message": f"{len(unapproved_wo)} write-offs without approval reference; ₹{total:,.0f}"
            })

    # ── 2. Large waivers (> ₹5L) without Board/CC approval ───────────────
    large_waivers = pl.DataFrame()
    if approval_col:
        large_waivers = con.execute(f"""
            SELECT
                w."{lan_col}" AS LOAN_ACCOUNT_NO,
                w."{amount_col}" AS waiver_amount,
                w."{wo_date_col}" AS waiver_date,
                w."{approval_col}" AS approval_authority,
                'LARGE_WAIVER_NO_BOARD_APPROVAL' AS exception_type
            FROM writeoffs w
            WHERE w."{amount_col}" > 500000
              AND UPPER(COALESCE(w."{approval_col}", '')) NOT LIKE '%BOARD%'
              AND UPPER(COALESCE(w."{approval_col}", '')) NOT LIKE '%CC%'
              AND UPPER(COALESCE(w."{approval_col}", '')) NOT LIKE '%COMMITTEE%'
            ORDER BY w."{amount_col}" DESC
        """).pl()

        if len(large_waivers) > 0:
            total = float(large_waivers["waiver_amount"].sum() or 0)
            anomaly_flags.append({
                "field": "APPROVAL_AUTHORITY",
                "value": len(large_waivers),
                "threshold": "Waivers > ₹5L require Board/CC approval",
                "message": f"{len(large_waivers)} waivers > ₹5L without Board/CC approval; ₹{total:,.0f}"
            })
    else:
        # Check by amount alone
        large_waivers = con.execute(f"""
            SELECT
                w."{lan_col}" AS LOAN_ACCOUNT_NO,
                w."{amount_col}" AS waiver_amount,
                w."{wo_date_col}" AS waiver_date,
                'LARGE_WAIVER_REVIEW_REQUIRED' AS exception_type
            FROM writeoffs w
            WHERE w."{amount_col}" > 500000
            ORDER BY w."{amount_col}" DESC
        """).pl()

    # ── 3. NPA interest reversal check ────────────────────────────────────
    no_interest_reversal = pl.DataFrame()
    if interest_reversal_col:
        no_interest_reversal = con.execute(f"""
            SELECT
                w."{lan_col}" AS LOAN_ACCOUNT_NO,
                w."{amount_col}" AS writeoff_amount,
                w."{wo_date_col}" AS writeoff_date,
                w."{interest_reversal_col}" AS interest_reversed,
                'NPA_INTEREST_NOT_REVERSED' AS exception_type
            FROM writeoffs w
            LEFT JOIN loan_tape l ON w."{lan_col}" = l.LOAN_ACCOUNT_NO
            WHERE (w."{interest_reversal_col}" IS NULL OR w."{interest_reversal_col}" = 0 OR w."{interest_reversal_col}" = FALSE)
              AND l.IND_AS_STAGE = 3
            ORDER BY w."{amount_col}" DESC
        """).pl()

        if len(no_interest_reversal) > 0:
            anomaly_flags.append({
                "field": "INTEREST_REVERSED",
                "value": len(no_interest_reversal),
                "threshold": "NPA interest must be reversed on write-off",
                "message": f"{len(no_interest_reversal)} NPA write-offs without interest reversal"
            })

    # ── Write-off summary stats ────────────────────────────────────────────
    wo_summary = con.execute(f"""
        SELECT
            COUNT(*) AS total_writeoffs,
            SUM("{amount_col}") AS total_amount,
            MAX("{amount_col}") AS max_writeoff,
            AVG("{amount_col}") AS avg_writeoff
        FROM writeoffs
        WHERE "{amount_col}" > 0
    """).pl().to_dicts()[0]

    exc_frames = [f for f in [unapproved_wo, large_waivers, no_interest_reversal] if len(f) > 0]
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
        "da_ref": "DA-022",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "unapproved_writeoffs": unapproved_wo,
        "large_waivers": large_waivers,
        "no_interest_reversal": no_interest_reversal,
        "summary": {
            "total_writeoffs": int(wo_summary.get("total_writeoffs") or 0),
            "total_amount": round(float(wo_summary.get("total_amount") or 0), 2),
            "unapproved_count": len(unapproved_wo),
            "large_waiver_no_approval": len(large_waivers),
            "no_interest_reversal": len(no_interest_reversal),
        },
        "anomaly_flags": anomaly_flags,
    }

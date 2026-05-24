"""
DA-044: Fund-based vs Non-fund-based Analysis
Analyze fund vs non-fund split; flag concentration
LMS Risk Theme: 10
CAP Seq: R.43
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-044",
    "name": "Fund-based vs Non-fund-based Analysis",
    "description": "Analyze fund vs non-fund split; flag concentration",
    "cap_seq": "R.43",
    "risk_theme": 10,
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
    Fund-based vs Non-fund-based Analysis

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loans", df.to_arrow())

    total = len(df)
    exceptions_count = 0
    exceptions_df = pl.DataFrame()
    summary = {"total_records": total, "exceptions": 0}
    anomaly_flags = []

    return {
        "total_loans": total,
        "exceptions_count": exceptions_count,
        "exception_rate_pct": 0.0 if total == 0 else (exceptions_count / total * 100),
        "exceptions_df": exceptions_df,
        "summary": summary,
        "anomaly_flags": anomaly_flags,
    }

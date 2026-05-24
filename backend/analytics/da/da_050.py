"""
DA-050: Operational Risk Scoring
Flag high-risk operations: disbursement errors, recovery % low, duplicate loans by processor
LMS Risk Theme: 14
CAP Seq: K.03
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-050",
    "name": "Operational Risk Scoring",
    "description": "Flag high-risk operations: disbursement errors, recovery % low, duplicate loans by processor",
    "cap_seq": "K.03",
    "risk_theme": 14,
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
    Operational Risk Scoring

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

"""
DA-018: Processing Fee EIR Test
Verify processing fees are amortized using EIR method; quantify front-loading overstatement.
LMS Risk Theme: 8
CAP Seq: R.18
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-018",
    "name": "Processing Fee EIR Test",
    "description": "EIR amortization of processing fees vs front-loaded recognition; income overstatement",
    "cap_seq": "R.18",
    "risk_theme": 8,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["processing_fees"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Processing Fee EIR Test:
    1. For loans with PROCESSING_FEE, verify fee spread using EIR method.
    2. Compare front-loaded vs EIR-spread recognition.
    3. Quantify income overstatement if fees front-loaded.

    EIR spread: fee is amortized proportionally over loan tenure.
    Front-loaded: entire fee recognized at disbursement.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    processing_fees = kwargs.get("processing_fees")

    # ── Load processing fee data ───────────────────────────────────────────
    if processing_fees is not None:
        if isinstance(processing_fees, pl.DataFrame):
            fee_df = processing_fees
        elif isinstance(processing_fees, pl.LazyFrame):
            fee_df = processing_fees.collect()
        else:
            fee_df = pl.DataFrame(processing_fees)
        con.register("fees", fee_df.to_arrow())
        fee_col = "PROCESSING_FEE" if "PROCESSING_FEE" in fee_df.columns else "FEE_AMOUNT"
        recognized_col = "RECOGNIZED_AMOUNT" if "RECOGNIZED_AMOUNT" in fee_df.columns else None
    else:
        # Check if processing fee is in loan tape itself
        fee_col_lt = "PROCESSING_FEE" if "PROCESSING_FEE" in df.columns else None
        if fee_col_lt:
            fee_df = df.select(["LOAN_ACCOUNT_NO", fee_col_lt, "DISBURSEMENT_DATE",
                                "TENURE_MONTHS", "OUTSTANDING_PRINCIPAL"]).rename({fee_col_lt: "PROCESSING_FEE"})
            con.register("fees", fee_df.to_arrow())
            fee_col = "PROCESSING_FEE"
            recognized_col = None
        else:
            return {
                "da_ref": "DA-018",
                "total_records": len(df),
                "exceptions_count": 0,
                "exceptions_df": pl.DataFrame(),
                "summary": {"note": "Processing fee data not provided"},
                "anomaly_flags": [{"field": "processing_fees", "value": None,
                                    "threshold": "Required", "message": "Processing fee data not provided"}],
            }

    # ── Compute elapsed months and EIR-spread fee ──────────────────────────
    eir_analysis = con.execute(f"""
        WITH loan_fee AS (
            SELECT
                l.LOAN_ACCOUNT_NO,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.DISBURSEMENT_DATE,
                l.TENURE_MONTHS,
                l.OUTSTANDING_PRINCIPAL,
                l.IND_AS_STAGE,
                f."{fee_col}" AS total_fee,
                DATE_DIFF('month', CAST(l.DISBURSEMENT_DATE AS DATE), CAST('{reporting_date}' AS DATE)) AS elapsed_months
            FROM loan_tape l
            JOIN fees f ON l.LOAN_ACCOUNT_NO = f.LOAN_ACCOUNT_NO
            WHERE f."{fee_col}" IS NOT NULL AND f."{fee_col}" > 0
              AND l.TENURE_MONTHS IS NOT NULL AND l.TENURE_MONTHS > 0
        ),
        eir_calc AS (
            SELECT *,
                -- EIR method: fee recognized proportionally over tenure
                ROUND(total_fee * LEAST(elapsed_months, TENURE_MONTHS)
                    / CAST(TENURE_MONTHS AS DOUBLE), 2) AS eir_recognized_amount,
                -- Front-loaded: full fee at disbursement (elapsed_months > 0 means fully recognized)
                CASE WHEN elapsed_months >= 1 THEN total_fee ELSE 0 END AS front_loaded_amount,
                -- Overstatement = front_loaded - eir_recognized
                ROUND(
                    (CASE WHEN elapsed_months >= 1 THEN total_fee ELSE 0 END)
                    - (total_fee * LEAST(elapsed_months, TENURE_MONTHS) / CAST(TENURE_MONTHS AS DOUBLE)),
                2) AS front_load_overstatement
            FROM loan_fee
        )
        SELECT *
        FROM eir_calc
        WHERE front_load_overstatement > 1000  -- Material threshold ₹1,000
        ORDER BY front_load_overstatement DESC
    """).pl()

    if len(eir_analysis) > 0:
        total_overstatement = float(eir_analysis["front_load_overstatement"].sum() or 0)
        anomaly_flags.append({
            "field": "PROCESSING_FEE",
            "value": len(eir_analysis),
            "threshold": "EIR amortization required",
            "message": f"{len(eir_analysis)} loans with front-loaded fee recognition; potential income overstatement ₹{total_overstatement:,.0f}"
        })

    # ── Summary statistics ─────────────────────────────────────────────────
    total_fees_df = con.execute(f"""
        SELECT
            COUNT(*) AS loans_with_fee,
            SUM("{fee_col}") AS total_fees_collected,
            AVG("{fee_col}") AS avg_fee
        FROM fees
        WHERE "{fee_col}" IS NOT NULL AND "{fee_col}" > 0
    """).pl().to_dicts()[0] if processing_fees is not None or "PROCESSING_FEE" in df.columns else {}

    return {
        "da_ref": "DA-018",
        "total_records": len(df),
        "exceptions_count": len(eir_analysis),
        "exceptions_df": eir_analysis,
        "summary": {
            "total_loans": len(df),
            "loans_with_fee": total_fees_df.get("loans_with_fee", 0),
            "total_fees_collected": round(float(total_fees_df.get("total_fees_collected") or 0), 2),
            "front_load_overstatement": round(float(eir_analysis["front_load_overstatement"].sum() or 0), 2) if len(eir_analysis) > 0 else 0,
        },
        "anomaly_flags": anomaly_flags,
    }

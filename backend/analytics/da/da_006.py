"""
DA-006: EMI Anomaly Detection
Flag zero EMIs, EMI inconsistencies vs computed value, and unexplained EMI changes.
LMS Risk Theme: 3
CAP Seq: R.06
"""

import polars as pl
import duckdb
import math
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-006",
    "name": "EMI Anomaly Detection",
    "description": "Flag zero EMIs, EMI vs computed formula mismatch, unexplained changes",
    "cap_seq": "R.06",
    "risk_theme": 3,
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
    EMI Anomaly Detection:
    1. Flag EMI_AMOUNT = 0 for active performing loans (DPD = 0, IND_AS_STAGE = 1).
    2. Flag EMI inconsistency: computed EMI vs stored EMI using standard formula.
       EMI = P * r * (1+r)^n / ((1+r)^n - 1), where r = monthly rate, n = remaining tenure.
    3. Flag accounts where EMI changed without tenure/rate change (via repayment history).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    # ── 1. EMI = 0 for active performing loans ────────────────────────────
    zero_emi_df = pl.DataFrame()
    if "EMI_AMOUNT" in df.columns and "DPD" in df.columns:
        stage_filter = "AND IND_AS_STAGE = 1" if "IND_AS_STAGE" in df.columns else ""
        zero_emi_df = con.execute(f"""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, INTEREST_RATE, TENURE_MONTHS, EMI_AMOUNT, DPD,
                'ZERO_EMI_PERFORMING_LOAN' AS exception_type
            FROM loan_tape
            WHERE (EMI_AMOUNT = 0 OR EMI_AMOUNT IS NULL)
              AND DPD = 0
              {stage_filter}
              AND OUTSTANDING_PRINCIPAL > 0
        """).pl()

        if len(zero_emi_df) > 0:
            anomaly_flags.append({
                "field": "EMI_AMOUNT",
                "value": len(zero_emi_df),
                "threshold": "EMI > 0 for performing loans",
                "message": f"{len(zero_emi_df)} performing loans with zero/null EMI"
            })

    # ── 2. Computed EMI vs stored EMI ─────────────────────────────────────
    emi_mismatch_df = pl.DataFrame()
    required_cols = {"EMI_AMOUNT", "OUTSTANDING_PRINCIPAL", "INTEREST_RATE", "TENURE_MONTHS"}
    if required_cols.issubset(set(df.columns)):
        # Compute EMI using DuckDB: EMI = P * r * (1+r)^n / ((1+r)^n - 1)
        # r = monthly rate = annual_rate / 1200
        # n = remaining tenure months
        emi_mismatch_df = con.execute("""
            WITH emi_calc AS (
                SELECT
                    LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                    OUTSTANDING_PRINCIPAL, INTEREST_RATE, TENURE_MONTHS, EMI_AMOUNT,
                    -- Monthly rate
                    (INTEREST_RATE / 100.0 / 12.0) AS r,
                    TENURE_MONTHS AS n
            FROM loan_tape
            WHERE OUTSTANDING_PRINCIPAL > 0
              AND INTEREST_RATE > 0
              AND TENURE_MONTHS > 0
              AND EMI_AMOUNT > 0
            ),
            with_computed AS (
                SELECT *,
                    CASE
                        WHEN r = 0 THEN OUTSTANDING_PRINCIPAL / n
                        ELSE OUTSTANDING_PRINCIPAL * r * POWER(1 + r, n)
                             / (POWER(1 + r, n) - 1)
                    END AS computed_emi
                FROM emi_calc
            )
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                OUTSTANDING_PRINCIPAL, INTEREST_RATE, TENURE_MONTHS,
                EMI_AMOUNT AS stored_emi,
                ROUND(computed_emi, 2) AS computed_emi,
                ROUND(ABS(EMI_AMOUNT - computed_emi) / NULLIF(computed_emi, 0) * 100, 2) AS pct_deviation,
                'EMI_FORMULA_MISMATCH' AS exception_type
            FROM with_computed
            WHERE ABS(EMI_AMOUNT - computed_emi) / NULLIF(computed_emi, 0) > 0.05
              AND ABS(EMI_AMOUNT - computed_emi) > 100
            ORDER BY pct_deviation DESC
        """).pl()

        if len(emi_mismatch_df) > 0:
            anomaly_flags.append({
                "field": "EMI_AMOUNT",
                "value": len(emi_mismatch_df),
                "threshold": "Computed EMI ±5%",
                "message": f"{len(emi_mismatch_df)} accounts where stored EMI deviates >5% from formula"
            })

    # ── 3. EMI change detection from repayment history ────────────────────
    emi_change_df = pl.DataFrame()
    if repayment_history is not None:
        rh_df = repayment_history.collect() if isinstance(repayment_history, pl.LazyFrame) else repayment_history
        if "EMI_AMOUNT" in rh_df.columns and "LOAN_ACCOUNT_NO" in rh_df.columns:
            con.register("repayment_hist", rh_df.to_arrow())
            emi_change_df = con.execute("""
                WITH emi_changes AS (
                    SELECT
                        LOAN_ACCOUNT_NO,
                        EMI_AMOUNT,
                        LAG(EMI_AMOUNT) OVER (PARTITION BY LOAN_ACCOUNT_NO ORDER BY PAYMENT_DATE) AS prev_emi,
                        INTEREST_RATE,
                        LAG(INTEREST_RATE) OVER (PARTITION BY LOAN_ACCOUNT_NO ORDER BY PAYMENT_DATE) AS prev_rate,
                        TENURE_MONTHS,
                        LAG(TENURE_MONTHS) OVER (PARTITION BY LOAN_ACCOUNT_NO ORDER BY PAYMENT_DATE) AS prev_tenure
                    FROM repayment_hist
                )
                SELECT
                    LOAN_ACCOUNT_NO,
                    EMI_AMOUNT AS new_emi,
                    prev_emi AS old_emi,
                    (EMI_AMOUNT - prev_emi) AS emi_change,
                    INTEREST_RATE AS new_rate,
                    prev_rate AS old_rate,
                    TENURE_MONTHS AS new_tenure,
                    prev_tenure AS old_tenure,
                    'UNEXPLAINED_EMI_CHANGE' AS exception_type
                FROM emi_changes
                WHERE prev_emi IS NOT NULL
                  AND ABS(EMI_AMOUNT - prev_emi) > 100
                  AND INTEREST_RATE = prev_rate
                  AND TENURE_MONTHS = prev_tenure
            """).pl()

            if len(emi_change_df) > 0:
                anomaly_flags.append({
                    "field": "EMI_AMOUNT",
                    "value": len(emi_change_df),
                    "threshold": "No change without rate/tenure change",
                    "message": f"{len(emi_change_df)} EMI changes without corresponding rate/tenure change"
                })

    # ── Compile all exceptions ─────────────────────────────────────────────
    exc_frames = [f for f in [zero_emi_df, emi_mismatch_df, emi_change_df] if len(f) > 0]
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

    # Product-level EMI stats
    emi_stats = pl.DataFrame()
    if "EMI_AMOUNT" in df.columns and "PRODUCT_CODE" in df.columns:
        emi_stats = con.execute("""
            SELECT
                PRODUCT_CODE,
                COUNT(*) AS loan_count,
                SUM(CASE WHEN EMI_AMOUNT = 0 OR EMI_AMOUNT IS NULL THEN 1 ELSE 0 END) AS zero_emi_count,
                MIN(EMI_AMOUNT) AS min_emi,
                AVG(EMI_AMOUNT) AS avg_emi,
                MAX(EMI_AMOUNT) AS max_emi
            FROM loan_tape
            GROUP BY PRODUCT_CODE
            ORDER BY zero_emi_count DESC
        """).pl()

    return {
        "da_ref": "DA-006",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "zero_emi_loans": zero_emi_df,
        "emi_formula_mismatch": emi_mismatch_df,
        "unexplained_emi_changes": emi_change_df,
        "emi_stats_by_product": emi_stats,
        "summary": {
            "total_loans": len(df),
            "zero_emi_count": len(zero_emi_df),
            "formula_mismatch_count": len(emi_mismatch_df),
            "unexplained_change_count": len(emi_change_df),
        },
        "anomaly_flags": anomaly_flags,
    }

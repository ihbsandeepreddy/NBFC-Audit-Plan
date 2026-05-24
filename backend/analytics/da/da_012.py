"""
DA-012: Disbursement to Active NPA
Detect fresh disbursements to borrowers who already had DPD > 0 at disbursement date.
LMS Risk Theme: 7
CAP Seq: R.12
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-012",
    "name": "Disbursement to Active NPA",
    "description": "Flag disbursements to borrowers with existing DPD > 0; same-day disburse-close patterns",
    "cap_seq": "R.12",
    "risk_theme": 7,
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
    Disbursement to Active NPA:
    1. Find disbursements to borrowers who ALREADY had DPD > 0 at disbursement date.
    2. Cross-reference with existing loans: same PAN, check DPD on all existing loans.
    3. Flag same-day disbursement and closure patterns (loan substitution).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    pan_col = "PAN_NUMBER" if "PAN_NUMBER" in df.columns else "PAN"
    if pan_col not in df.columns:
        return {
            "da_ref": "DA-012",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "PAN column not found"},
            "anomaly_flags": [],
        }

    # ── 1. Disbursements to borrowers with DPD > 0 on existing loans ──────
    # Detect: new loan (newer DISBURSEMENT_DATE) to PAN that already has an
    # existing loan with DPD > 0 (tracked at reporting date)
    disb_to_npa = con.execute(f"""
        WITH existing_dpd AS (
            SELECT
                "{pan_col}" AS pan,
                MAX(DPD) AS max_existing_dpd,
                SUM(CASE WHEN DPD >= 90 THEN OUTSTANDING_PRINCIPAL ELSE 0 END) AS npa_outstanding,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                MAX(IND_AS_STAGE) AS max_stage
            FROM loan_tape
            WHERE DPD IS NOT NULL
            GROUP BY "{pan_col}"
        ),
        new_disbursements AS (
            SELECT
                l.LOAN_ACCOUNT_NO,
                l."{pan_col}" AS pan,
                l.DISBURSEMENT_DATE,
                l.DISBURSEMENT_AMOUNT,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.DSA_CODE,
                l.DPD AS new_loan_dpd
            FROM loan_tape l
            WHERE l.DISBURSEMENT_DATE IS NOT NULL
        )
        SELECT
            nd.LOAN_ACCOUNT_NO,
            nd.pan,
            nd.DISBURSEMENT_DATE,
            nd.DISBURSEMENT_AMOUNT,
            nd.PRODUCT_CODE,
            nd.BRANCH_CODE,
            nd.DSA_CODE,
            nd.new_loan_dpd,
            ed.max_existing_dpd AS dpd_on_existing_loans,
            ed.npa_outstanding AS existing_npa_outstanding,
            ed.max_stage AS existing_max_stage,
            CASE
                WHEN ed.max_existing_dpd >= 90 THEN 'DISB_TO_NPA_BORROWER'
                WHEN ed.max_existing_dpd >= 30 THEN 'DISB_TO_SMA2_BORROWER'
                WHEN ed.max_existing_dpd > 0 THEN 'DISB_TO_SMA_BORROWER'
                ELSE 'CLEAN'
            END AS exception_type
        FROM new_disbursements nd
        JOIN existing_dpd ed ON nd.pan = ed.pan
        WHERE ed.max_existing_dpd > 0
        ORDER BY ed.max_existing_dpd DESC, nd.DISBURSEMENT_AMOUNT DESC
    """).pl()

    if len(disb_to_npa) > 0:
        npa_count = disb_to_npa.filter(pl.col("exception_type") == "DISB_TO_NPA_BORROWER").height
        sma_count = disb_to_npa.filter(pl.col("exception_type") != "DISB_TO_NPA_BORROWER").height
        if npa_count > 0:
            anomaly_flags.append({
                "field": "DISBURSEMENT_DATE",
                "value": npa_count,
                "threshold": "No disbursement to NPA borrower",
                "message": f"{npa_count} fresh disbursements to borrowers already classified as NPA"
            })
        if sma_count > 0:
            anomaly_flags.append({
                "field": "DISBURSEMENT_DATE",
                "value": sma_count,
                "threshold": "No disbursement to SMA borrower",
                "message": f"{sma_count} disbursements to borrowers with SMA classification (DPD 1-89)"
            })

    # ── 2. Same-day disbursement and closure (loan substitution) ──────────
    same_day_subst = con.execute(f"""
        WITH closures AS (
            SELECT
                "{pan_col}" AS pan,
                LOAN_ACCOUNT_NO AS closed_loan_no,
                MATURITY_DATE AS close_date,
                OUTSTANDING_PRINCIPAL AS closed_amount
            FROM loan_tape
            WHERE DPD = 0
              AND OUTSTANDING_PRINCIPAL = 0
              AND MATURITY_DATE IS NOT NULL
        ),
        new_disb AS (
            SELECT
                "{pan_col}" AS pan,
                LOAN_ACCOUNT_NO AS new_loan_no,
                DISBURSEMENT_DATE,
                DISBURSEMENT_AMOUNT
            FROM loan_tape
            WHERE DISBURSEMENT_DATE IS NOT NULL
              AND DISBURSEMENT_AMOUNT > 0
        )
        SELECT
            nd.new_loan_no,
            cl.closed_loan_no,
            nd.pan,
            nd.DISBURSEMENT_DATE,
            nd.DISBURSEMENT_AMOUNT,
            cl.close_date AS closure_date,
            cl.closed_amount,
            'SAME_DAY_DISB_CLOSURE' AS exception_type
        FROM new_disb nd
        JOIN closures cl ON nd.pan = cl.pan
          AND nd.new_loan_no != cl.closed_loan_no
          AND nd.DISBURSEMENT_DATE = cl.close_date
        ORDER BY nd.DISBURSEMENT_AMOUNT DESC
    """).pl()

    if len(same_day_subst) > 0:
        anomaly_flags.append({
            "field": "DISBURSEMENT_DATE",
            "value": len(same_day_subst),
            "threshold": "0 same-day disbursement-closure patterns",
            "message": f"{len(same_day_subst)} same-day disbursement and closure patterns (loan substitution risk)"
        })

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [disb_to_npa, same_day_subst] if len(f) > 0]
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
        "da_ref": "DA-012",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "disb_to_npa_borrowers": disb_to_npa,
        "same_day_substitutions": same_day_subst,
        "summary": {
            "total_loans": len(df),
            "disb_to_npa_count": len(disb_to_npa.filter(pl.col("exception_type") == "DISB_TO_NPA_BORROWER")) if len(disb_to_npa) > 0 else 0,
            "disb_to_sma_count": len(disb_to_npa.filter(pl.col("exception_type") != "DISB_TO_NPA_BORROWER")) if len(disb_to_npa) > 0 else 0,
            "same_day_substitutions": len(same_day_subst),
        },
        "anomaly_flags": anomaly_flags,
    }

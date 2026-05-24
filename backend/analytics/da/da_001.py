"""
DA-001: LMS-GL Reconciliation
Reconcile LMS outstanding principal by product to General Ledger balances.
LMS Risk Theme: 1
CAP Seq: R.01
"""

import polars as pl
import duckdb
import re
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-001",
    "name": "LMS-GL Reconciliation",
    "description": "Reconcile LMS outstanding principal by product to GL; flag data quality issues",
    "cap_seq": "R.01",
    "risk_theme": 1,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["gl_data"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    LMS-GL Reconciliation performs:
    1. Sum OUTSTANDING_PRINCIPAL by PRODUCT_CODE from LMS and compare to GL amounts.
    2. Flag differences > ₹1 lakh (100,000) per product.
    3. Flag duplicate LOAN_ACCOUNT_NO.
    4. Flag null mandatory fields.
    5. Flag INTEREST_RATE outside 0-60%.
    6. Flag DISBURSEMENT_DATE > MATURITY_DATE.
    7. Flag OUTSTANDING_PRINCIPAL < 0 and DPD < 0.
    8. Flag IND_AS_STAGE not in {1,2,3}.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    all_exceptions = []

    # ── 1. Duplicate LOAN_ACCOUNT_NO ──────────────────────────────────────
    dup_query = """
        SELECT
            LOAN_ACCOUNT_NO,
            COUNT(*) AS occurrence_count,
            'DUPLICATE_LAN' AS exception_type
        FROM loan_tape
        WHERE LOAN_ACCOUNT_NO IS NOT NULL
        GROUP BY LOAN_ACCOUNT_NO
        HAVING COUNT(*) > 1
    """
    dup_df = con.execute(dup_query).pl()
    if len(dup_df) > 0:
        anomaly_flags.append({
            "field": "LOAN_ACCOUNT_NO",
            "value": len(dup_df),
            "threshold": 0,
            "message": f"{len(dup_df)} duplicate LOAN_ACCOUNT_NO values found"
        })
    all_exceptions.append(dup_df.select(["LOAN_ACCOUNT_NO", "exception_type"]) if len(dup_df) > 0 else pl.DataFrame({"LOAN_ACCOUNT_NO": [], "exception_type": []}))

    # ── 2. Null mandatory fields ───────────────────────────────────────────
    mandatory_cols = [
        "LOAN_ACCOUNT_NO", "PAN_NUMBER", "DISBURSEMENT_DATE",
        "OUTSTANDING_PRINCIPAL", "INTEREST_RATE", "DPD", "IND_AS_STAGE"
    ]
    existing_mandatory = [c for c in mandatory_cols if c in df.columns]
    null_records_list = []
    for col in existing_mandatory:
        null_rows = con.execute(f"""
            SELECT LOAN_ACCOUNT_NO,
                   '{col}' AS null_field,
                   'NULL_MANDATORY_FIELD' AS exception_type
            FROM loan_tape
            WHERE "{col}" IS NULL
        """).pl()
        if len(null_rows) > 0:
            anomaly_flags.append({
                "field": col,
                "value": len(null_rows),
                "threshold": 0,
                "message": f"{len(null_rows)} records with null {col}"
            })
            null_records_list.append(null_rows)

    # ── 3. Interest rate outside 0-60% ────────────────────────────────────
    if "INTEREST_RATE" in df.columns:
        rate_exc = con.execute("""
            SELECT LOAN_ACCOUNT_NO, INTEREST_RATE,
                   'RATE_OUT_OF_RANGE' AS exception_type
            FROM loan_tape
            WHERE INTEREST_RATE < 0 OR INTEREST_RATE > 60
        """).pl()
        if len(rate_exc) > 0:
            anomaly_flags.append({
                "field": "INTEREST_RATE",
                "value": len(rate_exc),
                "threshold": "0-60",
                "message": f"{len(rate_exc)} records with INTEREST_RATE outside 0-60%"
            })

    # ── 4. DISBURSEMENT_DATE > MATURITY_DATE ──────────────────────────────
    date_exc = pl.DataFrame()
    if "DISBURSEMENT_DATE" in df.columns and "MATURITY_DATE" in df.columns:
        date_exc = con.execute("""
            SELECT LOAN_ACCOUNT_NO, DISBURSEMENT_DATE, MATURITY_DATE,
                   'DISB_AFTER_MATURITY' AS exception_type
            FROM loan_tape
            WHERE DISBURSEMENT_DATE > MATURITY_DATE
        """).pl()
        if len(date_exc) > 0:
            anomaly_flags.append({
                "field": "DISBURSEMENT_DATE/MATURITY_DATE",
                "value": len(date_exc),
                "threshold": "DISB <= MATURITY",
                "message": f"{len(date_exc)} records where DISBURSEMENT_DATE > MATURITY_DATE"
            })

    # ── 5. Negative OUTSTANDING_PRINCIPAL or DPD ──────────────────────────
    neg_exc = pl.DataFrame()
    if "OUTSTANDING_PRINCIPAL" in df.columns and "DPD" in df.columns:
        neg_exc = con.execute("""
            SELECT LOAN_ACCOUNT_NO, OUTSTANDING_PRINCIPAL, DPD,
                   CASE
                       WHEN OUTSTANDING_PRINCIPAL < 0 AND DPD < 0 THEN 'NEG_PRINCIPAL_AND_DPD'
                       WHEN OUTSTANDING_PRINCIPAL < 0 THEN 'NEGATIVE_PRINCIPAL'
                       ELSE 'NEGATIVE_DPD'
                   END AS exception_type
            FROM loan_tape
            WHERE OUTSTANDING_PRINCIPAL < 0 OR DPD < 0
        """).pl()
        if len(neg_exc) > 0:
            anomaly_flags.append({
                "field": "OUTSTANDING_PRINCIPAL/DPD",
                "value": len(neg_exc),
                "threshold": ">= 0",
                "message": f"{len(neg_exc)} records with negative OUTSTANDING_PRINCIPAL or DPD"
            })

    # ── 6. IND_AS_STAGE not in {1, 2, 3} ─────────────────────────────────
    stage_exc = pl.DataFrame()
    if "IND_AS_STAGE" in df.columns:
        stage_exc = con.execute("""
            SELECT LOAN_ACCOUNT_NO, IND_AS_STAGE,
                   'INVALID_IND_AS_STAGE' AS exception_type
            FROM loan_tape
            WHERE IND_AS_STAGE NOT IN (1, 2, 3)
        """).pl()
        if len(stage_exc) > 0:
            anomaly_flags.append({
                "field": "IND_AS_STAGE",
                "value": len(stage_exc),
                "threshold": "{1,2,3}",
                "message": f"{len(stage_exc)} records with IND_AS_STAGE not in (1,2,3)"
            })

    # ── 7. LMS vs GL reconciliation (by PRODUCT_CODE) ─────────────────────
    gl_recon_df = pl.DataFrame()
    gl_exceptions = pl.DataFrame()
    if "OUTSTANDING_PRINCIPAL" in df.columns and "PRODUCT_CODE" in df.columns:
        lms_by_product = con.execute("""
            SELECT
                PRODUCT_CODE,
                SUM(OUTSTANDING_PRINCIPAL) AS lms_outstanding,
                COUNT(*) AS loan_count
            FROM loan_tape
            GROUP BY PRODUCT_CODE
        """).pl()

        gl_data = kwargs.get("gl_data")
        if gl_data is not None:
            if isinstance(gl_data, dict):
                gl_df = pl.DataFrame({
                    "PRODUCT_CODE": list(gl_data.keys()),
                    "gl_outstanding": [float(v) for v in gl_data.values()]
                })
            elif isinstance(gl_data, pl.DataFrame):
                gl_df = gl_data
            else:
                gl_df = pl.from_pandas(gl_data) if hasattr(gl_data, 'to_dict') else pl.DataFrame()

            if len(gl_df) > 0:
                con.register("gl_table", gl_df.to_arrow())
                gl_recon_df = con.execute("""
                    SELECT
                        l.PRODUCT_CODE,
                        l.lms_outstanding,
                        l.loan_count,
                        g.gl_outstanding,
                        (l.lms_outstanding - g.gl_outstanding) AS difference,
                        ABS(l.lms_outstanding - g.gl_outstanding) AS abs_difference,
                        CASE
                            WHEN ABS(l.lms_outstanding - g.gl_outstanding) > 100000
                            THEN 'RECON_DIFFERENCE_GT_1L'
                            ELSE 'OK'
                        END AS recon_status
                    FROM lms_by_product l
                    LEFT JOIN gl_table g ON l.PRODUCT_CODE = g.PRODUCT_CODE
                """).pl()

                gl_exceptions = gl_recon_df.filter(pl.col("recon_status") == "RECON_DIFFERENCE_GT_1L")
                if len(gl_exceptions) > 0:
                    anomaly_flags.append({
                        "field": "LMS_GL_RECON",
                        "value": len(gl_exceptions),
                        "threshold": "Difference <= ₹1,00,000",
                        "message": f"{len(gl_exceptions)} products with LMS-GL difference > ₹1L"
                    })
        else:
            gl_recon_df = lms_by_product

    # ── 8. Compile all data-quality exceptions ────────────────────────────
    dq_exceptions = con.execute("""
        SELECT
            LOAN_ACCOUNT_NO,
            COALESCE(PRODUCT_CODE, 'UNKNOWN') AS PRODUCT_CODE,
            COALESCE(BRANCH_CODE, 'UNKNOWN') AS BRANCH_CODE,
            OUTSTANDING_PRINCIPAL,
            INTEREST_RATE,
            DPD,
            IND_AS_STAGE,
            CASE
                WHEN LOAN_ACCOUNT_NO IS NULL THEN 'NULL_LAN'
                WHEN PAN_NUMBER IS NULL THEN 'NULL_PAN'
                WHEN OUTSTANDING_PRINCIPAL < 0 THEN 'NEG_PRINCIPAL'
                WHEN DPD < 0 THEN 'NEG_DPD'
                WHEN INTEREST_RATE < 0 OR INTEREST_RATE > 60 THEN 'RATE_RANGE'
                WHEN IND_AS_STAGE NOT IN (1,2,3) THEN 'INVALID_STAGE'
                ELSE 'OTHER'
            END AS exception_type
        FROM loan_tape
        WHERE
            LOAN_ACCOUNT_NO IS NULL
            OR PAN_NUMBER IS NULL
            OR OUTSTANDING_PRINCIPAL < 0
            OR DPD < 0
            OR INTEREST_RATE < 0
            OR INTEREST_RATE > 60
            OR IND_AS_STAGE NOT IN (1, 2, 3)
    """ + ("OR DISBURSEMENT_DATE > MATURITY_DATE" if "DISBURSEMENT_DATE" in df.columns and "MATURITY_DATE" in df.columns else "")
    ).pl()

    # Stage summary
    stage_summary = {}
    if "IND_AS_STAGE" in df.columns and "OUTSTANDING_PRINCIPAL" in df.columns:
        stage_agg = con.execute("""
            SELECT IND_AS_STAGE,
                   COUNT(*) AS count,
                   SUM(OUTSTANDING_PRINCIPAL) AS outstanding
            FROM loan_tape
            GROUP BY IND_AS_STAGE
            ORDER BY IND_AS_STAGE
        """).pl()
        stage_summary = {
            str(row["IND_AS_STAGE"]): {
                "count": row["count"],
                "outstanding": round(float(row["outstanding"] or 0), 2)
            }
            for row in stage_agg.to_dicts()
        }

    total_outstanding = float(df["OUTSTANDING_PRINCIPAL"].sum() or 0) if "OUTSTANDING_PRINCIPAL" in df.columns else 0.0

    return {
        "da_ref": "DA-001",
        "total_records": len(df),
        "exceptions_count": len(dq_exceptions),
        "exceptions_df": dq_exceptions,
        "gl_recon_df": gl_recon_df,
        "gl_exceptions_count": len(gl_exceptions),
        "summary": {
            "total_records": len(df),
            "total_outstanding_principal": round(total_outstanding, 2),
            "duplicate_lans": len(dup_df),
            "null_mandatory_field_records": sum(len(n) for n in null_records_list),
            "invalid_stage_records": len(stage_exc),
            "negative_value_records": len(neg_exc),
            "rate_out_of_range": len(con.execute("SELECT COUNT(*) AS c FROM loan_tape WHERE INTEREST_RATE < 0 OR INTEREST_RATE > 60").pl()) if "INTEREST_RATE" in df.columns else 0,
            "stage_distribution": stage_summary,
        },
        "anomaly_flags": anomaly_flags,
    }

"""
DA-021: RPT Loans Testing
Cross-match loans against related party register; compare RPT vs non-RPT loan terms.
LMS Risk Theme: 9
CAP Seq: R.21
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-021",
    "name": "RPT Loans Testing",
    "description": "Cross-match loan book vs RPT register; flag undisclosed RPT and favourable terms",
    "cap_seq": "R.21",
    "risk_theme": 9,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["rpt_register"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    RPT Loans Testing:
    1. Cross-match LOAN_ACCOUNT_NO against rpt_register (list of related party PANs).
    2. Flag loans to related parties not in declared RPT register.
    3. Compare ROI of RPT loans vs similar non-RPT borrowers.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    rpt_register = kwargs.get("rpt_register")

    # ── Mark declared RPT loans ────────────────────────────────────────────
    declared_rpt = con.execute("""
        SELECT LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
               OUTSTANDING_PRINCIPAL, INTEREST_RATE, DPD, IND_AS_STAGE,
               IS_RELATED_PARTY, RELATED_PARTY_TYPE,
               'DECLARED_RPT' AS rpt_status
        FROM loan_tape
        WHERE IS_RELATED_PARTY = TRUE
    """ if "IS_RELATED_PARTY" in df.columns else """
        SELECT LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
               OUTSTANDING_PRINCIPAL, INTEREST_RATE, DPD, IND_AS_STAGE,
               NULL AS IS_RELATED_PARTY, NULL AS RELATED_PARTY_TYPE,
               'DECLARED_RPT' AS rpt_status
        FROM loan_tape
        WHERE 1=0
    """).pl()

    # ── Cross-match with RPT register ─────────────────────────────────────
    undisclosed_rpt = pl.DataFrame()
    if rpt_register is not None:
        if isinstance(rpt_register, list):
            # List of PANs
            rpt_pans = [p for p in rpt_register if isinstance(p, str)]
            rpt_df = pl.DataFrame({"rpt_pan": rpt_pans})
        elif isinstance(rpt_register, pl.DataFrame):
            rpt_df = rpt_register
            pan_col_rpt = "PAN" if "PAN" in rpt_df.columns else ("rpt_pan" if "rpt_pan" in rpt_df.columns else rpt_df.columns[0])
            rpt_df = rpt_df.rename({pan_col_rpt: "rpt_pan"}) if pan_col_rpt != "rpt_pan" else rpt_df
        else:
            rpt_df = pl.DataFrame({"rpt_pan": [str(p) for p in rpt_register]})

        con.register("rpt_reg", rpt_df.to_arrow())
        pan_col = "PAN_NUMBER" if "PAN_NUMBER" in df.columns else "PAN"

        undisclosed_rpt = con.execute(f"""
            SELECT
                l.LOAN_ACCOUNT_NO,
                l."{pan_col}" AS PAN_NUMBER,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.OUTSTANDING_PRINCIPAL,
                l.INTEREST_RATE,
                l.DPD,
                l.IND_AS_STAGE,
                'UNDISCLOSED_RPT_LOAN' AS exception_type
            FROM loan_tape l
            JOIN rpt_reg r ON l."{pan_col}" = r.rpt_pan
            WHERE (l.IS_RELATED_PARTY IS NULL OR l.IS_RELATED_PARTY = FALSE)
        """ if "IS_RELATED_PARTY" in df.columns else f"""
            SELECT
                l.LOAN_ACCOUNT_NO,
                l."{pan_col}" AS PAN_NUMBER,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.OUTSTANDING_PRINCIPAL,
                l.INTEREST_RATE,
                l.DPD,
                l.IND_AS_STAGE,
                'RPT_IDENTIFIED_VIA_PAN_MATCH' AS exception_type
            FROM loan_tape l
            JOIN rpt_reg r ON l."{pan_col}" = r.rpt_pan
        """).pl()

        if len(undisclosed_rpt) > 0:
            anomaly_flags.append({
                "field": "IS_RELATED_PARTY",
                "value": len(undisclosed_rpt),
                "threshold": "All RPT loans must be disclosed",
                "message": f"{len(undisclosed_rpt)} loans matched to RPT register but not flagged as related party in LMS"
            })

    # ── Compare RPT vs non-RPT terms ──────────────────────────────────────
    rpt_terms_comparison = pl.DataFrame()
    pan_col = "PAN_NUMBER" if "PAN_NUMBER" in df.columns else "PAN"

    all_rpt_pans_query = ""
    if rpt_register is not None:
        all_rpt_pans_query = f"WHERE l.\"{pan_col}\" IN (SELECT rpt_pan FROM rpt_reg)"
    elif "IS_RELATED_PARTY" in df.columns:
        all_rpt_pans_query = "WHERE l.IS_RELATED_PARTY = TRUE"

    if all_rpt_pans_query:
        rpt_terms_comparison = con.execute(f"""
            WITH rpt_loans AS (
                SELECT l.*, 'RPT' AS borrower_type
                FROM loan_tape l
                {all_rpt_pans_query}
            ),
            non_rpt AS (
                SELECT l.*, 'NON_RPT' AS borrower_type
                FROM loan_tape l
                WHERE l.LOAN_ACCOUNT_NO NOT IN (SELECT LOAN_ACCOUNT_NO FROM rpt_loans)
            ),
            combined AS (
                SELECT * FROM rpt_loans
                UNION ALL
                SELECT * FROM non_rpt
            )
            SELECT
                borrower_type,
                PRODUCT_CODE,
                COUNT(*) AS loan_count,
                AVG(INTEREST_RATE) AS avg_roi,
                AVG(OUTSTANDING_PRINCIPAL) AS avg_ticket,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                ROUND(100.0 * SUM(CASE WHEN DPD > 0 THEN OUTSTANDING_PRINCIPAL ELSE 0 END)
                    / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 2) AS par_pct
            FROM combined
            GROUP BY borrower_type, PRODUCT_CODE
            ORDER BY borrower_type, PRODUCT_CODE
        """).pl()

        # Flag if RPT average ROI < non-RPT by > 2%
        if len(rpt_terms_comparison) > 0:
            rpt_avg = rpt_terms_comparison.filter(pl.col("borrower_type") == "RPT")
            non_rpt_avg = rpt_terms_comparison.filter(pl.col("borrower_type") == "NON_RPT")
            if len(rpt_avg) > 0 and len(non_rpt_avg) > 0:
                rpt_roi = float(rpt_avg["avg_roi"].mean() or 0)
                non_rpt_roi = float(non_rpt_avg["avg_roi"].mean() or 0)
                if non_rpt_roi - rpt_roi > 2:
                    anomaly_flags.append({
                        "field": "INTEREST_RATE",
                        "value": round(non_rpt_roi - rpt_roi, 2),
                        "threshold": "RPT ROI should not be > 2% below non-RPT",
                        "message": f"RPT average ROI {rpt_roi:.2f}% vs non-RPT {non_rpt_roi:.2f}% (gap: {non_rpt_roi - rpt_roi:.2f}%) — potential favourable terms"
                    })

    exceptions_df = undisclosed_rpt

    return {
        "da_ref": "DA-021",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "declared_rpt_loans": declared_rpt,
        "undisclosed_rpt": undisclosed_rpt,
        "rpt_terms_comparison": rpt_terms_comparison,
        "summary": {
            "total_loans": len(df),
            "declared_rpt_loans": len(declared_rpt),
            "undisclosed_rpt_matches": len(undisclosed_rpt),
            "rpt_register_provided": rpt_register is not None,
        },
        "anomaly_flags": anomaly_flags,
    }

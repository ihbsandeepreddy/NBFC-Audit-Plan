"""
DA-024: Field Change Log Analysis
Identify high-risk field changes near quarter-end and repeated modifications.
LMS Risk Theme: 11
CAP Seq: R.24
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-024",
    "name": "Field Change Log Analysis",
    "description": "Flag high-risk field changes near quarter-end; repeated modifications by same user",
    "cap_seq": "R.24",
    "risk_theme": 11,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["field_change_log"],
}

HIGH_RISK_FIELDS = ["ROI", "INTEREST_RATE", "EMI_AMOUNT", "ASSET_CLASSIFICATION", "DPD",
                    "IND_AS_STAGE", "OUTSTANDING_PRINCIPAL", "STAGE"]


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Field Change Log Analysis:
    1. Flag high-risk field changes in last 5 days of quarter.
    2. Flag repeated modifications by same user/branch (>3 changes on same field).
    3. Flag classification changes without cash receipts.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    field_change_log = kwargs.get("field_change_log")

    if field_change_log is None:
        return {
            "da_ref": "DA-024",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "field_change_log not provided"},
            "anomaly_flags": [{"field": "field_change_log", "value": None,
                                "threshold": "Required", "message": "Field change log not provided"}],
        }

    if isinstance(field_change_log, pl.DataFrame):
        log_df = field_change_log
    elif isinstance(field_change_log, pl.LazyFrame):
        log_df = field_change_log.collect()
    else:
        log_df = pl.DataFrame(field_change_log)

    con.register("change_log", log_df.to_arrow())

    # Detect column names
    change_date_col = "CHANGE_DATE" if "CHANGE_DATE" in log_df.columns else "MODIFIED_DATE"
    field_name_col = "FIELD_NAME" if "FIELD_NAME" in log_df.columns else "COLUMN_CHANGED"
    user_col = "USER_ID" if "USER_ID" in log_df.columns else "MODIFIED_BY"
    lan_col = "LOAN_ACCOUNT_NO" if "LOAN_ACCOUNT_NO" in log_df.columns else "LAN"
    old_val_col = "OLD_VALUE" if "OLD_VALUE" in log_df.columns else "PREVIOUS_VALUE"
    new_val_col = "NEW_VALUE" if "NEW_VALUE" in log_df.columns else "UPDATED_VALUE"

    high_risk_list = "', '".join(HIGH_RISK_FIELDS)

    # ── 1. High-risk fields changed in last 5 days of quarter ─────────────
    period_end_changes = con.execute(f"""
        SELECT
            cl."{lan_col}" AS LOAN_ACCOUNT_NO,
            cl."{change_date_col}" AS change_date,
            cl."{field_name_col}" AS field_name,
            cl."{user_col}" AS user_id,
            cl."{old_val_col}" AS old_value,
            cl."{new_val_col}" AS new_value,
            'PERIOD_END_HIGH_RISK_CHANGE' AS exception_type
        FROM change_log cl
        WHERE UPPER(cl."{field_name_col}") IN ('{high_risk_list}')
          AND EXTRACT(MONTH FROM CAST(cl."{change_date_col}" AS DATE)) IN (3, 6, 9, 12)
          AND (DAY(LAST_DAY(CAST(cl."{change_date_col}" AS DATE))) -
               EXTRACT(DAY FROM CAST(cl."{change_date_col}" AS DATE))) < 5
        ORDER BY cl."{change_date_col}" DESC
    """).pl()

    if len(period_end_changes) > 0:
        anomaly_flags.append({
            "field": "CHANGE_DATE",
            "value": len(period_end_changes),
            "threshold": "0 high-risk changes in last 5 days of quarter",
            "message": f"{len(period_end_changes)} high-risk field changes in last 5 days of quarter-end"
        })

    # ── 2. Repeated modifications: >3 changes on same field by same user ──
    repeated_mods = con.execute(f"""
        SELECT
            cl."{user_col}" AS user_id,
            cl."{lan_col}" AS LOAN_ACCOUNT_NO,
            cl."{field_name_col}" AS field_name,
            COUNT(*) AS change_count,
            MIN(cl."{change_date_col}") AS first_change,
            MAX(cl."{change_date_col}") AS last_change,
            'REPEATED_FIELD_MODIFICATION' AS exception_type
        FROM change_log cl
        WHERE UPPER(cl."{field_name_col}") IN ('{high_risk_list}')
        GROUP BY cl."{user_col}", cl."{lan_col}", cl."{field_name_col}"
        HAVING COUNT(*) > 3
        ORDER BY change_count DESC
    """).pl()

    if len(repeated_mods) > 0:
        anomaly_flags.append({
            "field": "USER_ID",
            "value": len(repeated_mods),
            "threshold": "<= 3 changes per field per account",
            "message": f"{len(repeated_mods)} user-field-account combinations with >3 changes"
        })

    # ── 3. Classification changes without cash receipts ────────────────────
    classif_no_payment = pl.DataFrame()
    if repayment_history is not None:
        rh_df = repayment_history.collect() if isinstance(repayment_history, pl.LazyFrame) else repayment_history
        con.register("repayment_hist", rh_df.to_arrow())
        payment_date_col = "PAYMENT_DATE" if "PAYMENT_DATE" in rh_df.columns else "TXN_DATE"

        classif_no_payment = con.execute(f"""
            WITH classif_changes AS (
                SELECT
                    cl."{lan_col}" AS LOAN_ACCOUNT_NO,
                    cl."{change_date_col}" AS change_date,
                    cl."{old_val_col}" AS old_classification,
                    cl."{new_val_col}" AS new_classification,
                    cl."{user_col}" AS user_id
                FROM change_log cl
                WHERE UPPER(cl."{field_name_col}") IN ('IND_AS_STAGE', 'ASSET_CLASSIFICATION', 'DPD')
                  AND cl."{new_val_col}" < cl."{old_val_col}"  -- backward classification
            ),
            payments_near_change AS (
                SELECT
                    cc.LOAN_ACCOUNT_NO,
                    cc.change_date,
                    cc.old_classification,
                    cc.new_classification,
                    cc.user_id,
                    SUM(rh.PAYMENT_AMOUNT) AS payment_received
                FROM classif_changes cc
                LEFT JOIN repayment_hist rh ON cc.LOAN_ACCOUNT_NO = rh.LOAN_ACCOUNT_NO
                  AND ABS(DATE_DIFF('day', CAST(rh."{payment_date_col}" AS DATE),
                      CAST(cc.change_date AS DATE))) <= 5
                GROUP BY cc.LOAN_ACCOUNT_NO, cc.change_date, cc.old_classification,
                         cc.new_classification, cc.user_id
            )
            SELECT *,
                'BACKWARD_CLASSIFICATION_NO_PAYMENT' AS exception_type
            FROM payments_near_change
            WHERE COALESCE(payment_received, 0) < 1000
            ORDER BY change_date DESC
        """).pl() if payment_date_col in rh_df.columns else pl.DataFrame()

        if len(classif_no_payment) > 0:
            anomaly_flags.append({
                "field": "IND_AS_STAGE",
                "value": len(classif_no_payment),
                "threshold": "Stage improvements require cash receipts",
                "message": f"{len(classif_no_payment)} backward classifications without corresponding cash receipts"
            })

    exc_frames = [f for f in [period_end_changes, repeated_mods, classif_no_payment] if len(f) > 0]
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
        "da_ref": "DA-024",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "period_end_changes": period_end_changes,
        "repeated_modifications": repeated_mods,
        "classification_no_payment": classif_no_payment,
        "summary": {
            "total_change_log_entries": len(log_df),
            "period_end_high_risk_changes": len(period_end_changes),
            "repeated_modifications": len(repeated_mods),
            "backward_classif_no_payment": len(classif_no_payment),
        },
        "anomaly_flags": anomaly_flags,
    }

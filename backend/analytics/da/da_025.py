"""
DA-025: Audit Trail Gap Analysis
Detect gaps in audit log, privileged user activity, and modifications without trail.
LMS Risk Theme: 11
CAP Seq: R.25
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-025",
    "name": "Audit Trail Gap Analysis",
    "description": "Find audit log gaps > 1hr during business hours; flag DBA/SYSTEM users",
    "cap_seq": "R.25",
    "risk_theme": 11,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["audit_log"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Audit Trail Gap Analysis:
    1. Find gaps > 1 hour during business hours (9 AM - 6 PM).
    2. Flag entries with SYSTEM or DBA as user_id.
    3. Flag modifications in loan_tape without corresponding audit trail entry.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    audit_log = kwargs.get("audit_log")

    if audit_log is None:
        return {
            "da_ref": "DA-025",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "audit_log not provided"},
            "anomaly_flags": [{"field": "audit_log", "value": None,
                                "threshold": "Required", "message": "Audit log not provided"}],
        }

    if isinstance(audit_log, pl.DataFrame):
        log_df = audit_log
    elif isinstance(audit_log, pl.LazyFrame):
        log_df = audit_log.collect()
    else:
        log_df = pl.DataFrame(audit_log)

    con.register("audit_log", log_df.to_arrow())

    # Detect column names
    ts_col = "TIMESTAMP" if "TIMESTAMP" in log_df.columns else (
        "LOG_TIMESTAMP" if "LOG_TIMESTAMP" in log_df.columns else "EVENT_TIME"
    )
    user_col = "USER_ID" if "USER_ID" in log_df.columns else "USERNAME"
    action_col = "ACTION" if "ACTION" in log_df.columns else "OPERATION"
    entity_col = "ENTITY_ID" if "ENTITY_ID" in log_df.columns else "LOAN_ACCOUNT_NO"
    table_col = "TABLE_NAME" if "TABLE_NAME" in log_df.columns else None

    # ── 1. Business-hours gaps > 1 hour ───────────────────────────────────
    business_hour_gaps = con.execute(f"""
        WITH ordered_events AS (
            SELECT
                "{ts_col}" AS event_ts,
                CAST("{ts_col}" AS TIMESTAMP) AS event_time,
                "{user_col}" AS user_id,
                LEAD(CAST("{ts_col}" AS TIMESTAMP)) OVER (ORDER BY "{ts_col}") AS next_event_time
            FROM audit_log
            WHERE EXTRACT(HOUR FROM CAST("{ts_col}" AS TIMESTAMP)) BETWEEN 9 AND 18
        )
        SELECT
            event_ts AS gap_start,
            next_event_time AS gap_end,
            DATE_DIFF('minute', event_time, next_event_time) AS gap_minutes,
            user_id,
            'AUDIT_GAP_GT_1HOUR' AS exception_type
        FROM ordered_events
        WHERE DATE_DIFF('minute', event_time, next_event_time) > 60
          AND next_event_time IS NOT NULL
        ORDER BY gap_minutes DESC
    """).pl()

    if len(business_hour_gaps) > 0:
        max_gap = float(business_hour_gaps["gap_minutes"].max() or 0)
        anomaly_flags.append({
            "field": "TIMESTAMP",
            "value": len(business_hour_gaps),
            "threshold": "No gaps > 60 minutes during business hours",
            "message": f"{len(business_hour_gaps)} audit log gaps > 1 hour during business hours (max: {max_gap:.0f} min)"
        })

    # ── 2. DBA/SYSTEM user activity ────────────────────────────────────────
    privileged_activity = con.execute(f"""
        SELECT
            "{user_col}" AS user_id,
            "{action_col}" AS action,
            "{ts_col}" AS event_time,
            "{entity_col}" AS entity_id,
            COUNT(*) AS event_count,
            'PRIVILEGED_USER_ACTIVITY' AS exception_type
        FROM audit_log
        WHERE UPPER("{user_col}") IN ('SYSTEM', 'DBA', 'ADMIN', 'ROOT', 'SA', 'SYSADMIN')
        GROUP BY "{user_col}", "{action_col}", "{ts_col}", "{entity_col}"
        ORDER BY "{ts_col}" DESC
    """).pl()

    if len(privileged_activity) > 0:
        anomaly_flags.append({
            "field": "USER_ID",
            "value": len(privileged_activity),
            "threshold": "No SYSTEM/DBA direct modifications",
            "message": f"{len(privileged_activity)} actions by privileged/system users (bypassed application controls risk)"
        })

    # ── 3. High-frequency user actions (possible mass modification) ────────
    user_action_freq = con.execute(f"""
        SELECT
            "{user_col}" AS user_id,
            CAST("{ts_col}" AS DATE) AS action_date,
            COUNT(*) AS action_count,
            COUNT(DISTINCT "{entity_col}") AS distinct_entities,
            'HIGH_FREQUENCY_USER_ACTION' AS exception_type
        FROM audit_log
        GROUP BY "{user_col}", CAST("{ts_col}" AS DATE)
        HAVING COUNT(*) > 500
        ORDER BY action_count DESC
    """).pl()

    if len(user_action_freq) > 0:
        anomaly_flags.append({
            "field": "USER_ACTIVITY",
            "value": len(user_action_freq),
            "threshold": "< 500 actions per user per day",
            "message": f"{len(user_action_freq)} user-day combinations with > 500 actions (mass modification risk)"
        })

    # ── 4. Modifications without audit trail ─────────────────────────────
    # Check if loan_tape has accounts with no audit trail entry
    no_trail = pl.DataFrame()
    if entity_col in log_df.columns:
        no_trail = con.execute(f"""
            SELECT
                l.LOAN_ACCOUNT_NO,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.DPD,
                l.IND_AS_STAGE,
                'NO_AUDIT_TRAIL' AS exception_type
            FROM loan_tape l
            LEFT JOIN audit_log a ON l.LOAN_ACCOUNT_NO = a."{entity_col}"
            WHERE a."{entity_col}" IS NULL
              AND l.OUTSTANDING_PRINCIPAL > 0
            LIMIT 100
        """).pl()

        if len(no_trail) > 0:
            anomaly_flags.append({
                "field": "AUDIT_TRAIL",
                "value": len(no_trail),
                "threshold": "All loan records should have audit trail",
                "message": f"{len(no_trail)} active loan accounts with no audit trail entries (sample)"
            })

    exc_frames = [f for f in [business_hour_gaps, privileged_activity, user_action_freq] if len(f) > 0]
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
        "da_ref": "DA-025",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "business_hour_gaps": business_hour_gaps,
        "privileged_activity": privileged_activity,
        "high_frequency_actions": user_action_freq,
        "no_audit_trail": no_trail,
        "summary": {
            "total_audit_entries": len(log_df),
            "business_hour_gaps": len(business_hour_gaps),
            "privileged_user_actions": len(privileged_activity),
            "high_frequency_days": len(user_action_freq),
        },
        "anomaly_flags": anomaly_flags,
    }

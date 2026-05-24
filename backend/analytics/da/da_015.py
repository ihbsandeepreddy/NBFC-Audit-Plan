"""
DA-015: Stage Override Pattern Analysis
Analyze manual stage override logs for unapproved, blanket, and period-end patterns.
LMS Risk Theme: 4
CAP Seq: R.15
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-015",
    "name": "Stage Override Pattern Analysis",
    "description": "Flag unapproved overrides, blanket same-day moves, period-end patterns",
    "cap_seq": "R.15",
    "risk_theme": 4,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["stage_override_log"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Stage Override Pattern Analysis:
    1. Count overrides by direction (1->2, 2->1, 2->3, 3->2) by month.
    2. Flag overrides without CC approval reference.
    3. Flag blanket overrides: all accounts in a product/branch moved same day.
    4. Flag override patterns correlated with period-end dates (last 5 days of quarter).

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []
    override_log = kwargs.get("stage_override_log")

    if override_log is None:
        return {
            "da_ref": "DA-015",
            "total_records": len(df),
            "exceptions_count": 0,
            "exceptions_df": pl.DataFrame(),
            "summary": {"note": "stage_override_log not provided"},
            "anomaly_flags": [{"field": "stage_override_log", "value": None,
                                "threshold": "Required", "message": "Stage override log not provided"}],
        }

    if isinstance(override_log, pl.DataFrame):
        log_df = override_log
    elif isinstance(override_log, pl.LazyFrame):
        log_df = override_log.collect()
    else:
        log_df = pl.DataFrame(override_log)

    con.register("override_log", log_df.to_arrow())

    # Determine column names
    override_date_col = "OVERRIDE_DATE" if "OVERRIDE_DATE" in log_df.columns else "CHANGE_DATE"
    from_stage_col = "FROM_STAGE" if "FROM_STAGE" in log_df.columns else "OLD_STAGE"
    to_stage_col = "TO_STAGE" if "TO_STAGE" in log_df.columns else "NEW_STAGE"
    approval_col = "APPROVAL_REF" if "APPROVAL_REF" in log_df.columns else ("CC_APPROVAL" if "CC_APPROVAL" in log_df.columns else None)
    user_col = "USER_ID" if "USER_ID" in log_df.columns else "CHANGED_BY"
    lan_col = "LOAN_ACCOUNT_NO" if "LOAN_ACCOUNT_NO" in log_df.columns else "LAN"

    # ── 1. Override counts by direction and month ─────────────────────────
    direction_monthly = con.execute(f"""
        SELECT
            STRFTIME(CAST("{override_date_col}" AS DATE), '%Y-%m') AS month,
            CONCAT(CAST("{from_stage_col}" AS VARCHAR), '->', CAST("{to_stage_col}" AS VARCHAR)) AS direction,
            COUNT(*) AS override_count,
            CASE
                WHEN "{to_stage_col}" < "{from_stage_col}" THEN 'BACKWARD'
                WHEN "{to_stage_col}" > "{from_stage_col}" THEN 'FORWARD'
                ELSE 'NO_CHANGE'
            END AS migration_type
        FROM override_log
        WHERE "{from_stage_col}" IS NOT NULL AND "{to_stage_col}" IS NOT NULL
        GROUP BY 1, 2, 4
        ORDER BY 1, 2
    """).pl()

    # ── 2. Overrides without approval reference ────────────────────────────
    unapproved_overrides = pl.DataFrame()
    if approval_col:
        unapproved_overrides = con.execute(f"""
            SELECT
                o."{lan_col}" AS LOAN_ACCOUNT_NO,
                o."{override_date_col}" AS override_date,
                o."{from_stage_col}" AS from_stage,
                o."{to_stage_col}" AS to_stage,
                o."{approval_col}" AS approval_ref,
                o."{user_col}" AS user_id,
                'OVERRIDE_WITHOUT_APPROVAL' AS exception_type
            FROM override_log o
            WHERE (o."{approval_col}" IS NULL OR TRIM(o."{approval_col}") = '')
              AND "{to_stage_col}" < "{from_stage_col}"
            ORDER BY o."{override_date_col}" DESC
        """).pl()

        if len(unapproved_overrides) > 0:
            anomaly_flags.append({
                "field": "APPROVAL_REF",
                "value": len(unapproved_overrides),
                "threshold": "All backward overrides require CC approval",
                "message": f"{len(unapproved_overrides)} backward stage overrides without CC approval reference"
            })

    # ── 3. Blanket overrides: product/branch moved same day ───────────────
    blanket_overrides = con.execute(f"""
        WITH daily_overrides AS (
            SELECT
                CAST("{override_date_col}" AS DATE) AS override_date,
                "{from_stage_col}" AS from_stage,
                "{to_stage_col}" AS to_stage,
                COUNT(*) AS override_count
            FROM override_log
            WHERE "{from_stage_col}" IS NOT NULL AND "{to_stage_col}" IS NOT NULL
            GROUP BY 1, 2, 3
        )
        SELECT
            override_date,
            from_stage,
            to_stage,
            override_count,
            CASE
                WHEN override_count >= 10 AND to_stage < from_stage THEN 'BLANKET_BACKWARD_OVERRIDE'
                WHEN override_count >= 20 THEN 'BLANKET_FORWARD_OVERRIDE'
                ELSE 'HIGH_VOLUME_OVERRIDE'
            END AS exception_type
        FROM daily_overrides
        WHERE override_count >= 10
        ORDER BY override_count DESC
    """).pl()

    if len(blanket_overrides) > 0:
        blanket_back = blanket_overrides.filter(pl.col("exception_type") == "BLANKET_BACKWARD_OVERRIDE")
        if len(blanket_back) > 0:
            anomaly_flags.append({
                "field": "OVERRIDE_DATE",
                "value": len(blanket_back),
                "threshold": "< 10 same-direction overrides on same day",
                "message": f"{len(blanket_back)} days with 10+ backward stage overrides (blanket classification manipulation)"
            })

    # ── 4. Period-end override patterns (last 5 days of quarter) ──────────
    period_end_overrides = con.execute(f"""
        WITH override_dates AS (
            SELECT *,
                CAST("{override_date_col}" AS DATE) AS ovrd_date,
                EXTRACT(MONTH FROM CAST("{override_date_col}" AS DATE)) AS ovrd_month,
                EXTRACT(DAY FROM CAST("{override_date_col}" AS DATE)) AS ovrd_day,
                DAY(LAST_DAY(CAST("{override_date_col}" AS DATE))) AS days_in_month
            FROM override_log
            WHERE "{from_stage_col}" IS NOT NULL AND "{to_stage_col}" IS NOT NULL
        )
        SELECT
            ovrd_date AS override_date,
            "{from_stage_col}" AS from_stage,
            "{to_stage_col}" AS to_stage,
            COUNT(*) AS override_count,
            'PERIOD_END_OVERRIDE' AS exception_type
        FROM override_dates
        WHERE
            -- Quarter end months: March, June, September, December
            ovrd_month IN (3, 6, 9, 12)
            AND (days_in_month - ovrd_day) < 5
            AND "{to_stage_col}" < "{from_stage_col}"
        GROUP BY ovrd_date, "{from_stage_col}", "{to_stage_col}"
        ORDER BY override_count DESC
    """).pl()

    if len(period_end_overrides) > 0:
        anomaly_flags.append({
            "field": "OVERRIDE_DATE",
            "value": len(period_end_overrides),
            "threshold": "0 period-end backward overrides",
            "message": f"{len(period_end_overrides)} backward override events in last 5 days of quarter-end month"
        })

    # ── Compile exceptions ─────────────────────────────────────────────────
    exc_frames = [f for f in [unapproved_overrides, blanket_overrides, period_end_overrides] if len(f) > 0]
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

    total_backward = len(log_df.filter(pl.col(to_stage_col) < pl.col(from_stage_col))) if (to_stage_col in log_df.columns and from_stage_col in log_df.columns) else 0

    return {
        "da_ref": "DA-015",
        "total_records": len(df),
        "exceptions_count": len(exceptions_df),
        "exceptions_df": exceptions_df,
        "direction_monthly": direction_monthly,
        "unapproved_overrides": unapproved_overrides,
        "blanket_overrides": blanket_overrides,
        "period_end_overrides": period_end_overrides,
        "summary": {
            "total_override_events": len(log_df),
            "total_backward_overrides": total_backward,
            "unapproved_backward": len(unapproved_overrides),
            "blanket_events": len(blanket_overrides),
            "period_end_events": len(period_end_overrides),
        },
        "anomaly_flags": anomaly_flags,
    }

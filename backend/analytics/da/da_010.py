"""
DA-010: Credit Policy Compliance Validation
Validate every loan against product-wise credit policy parameters.
LMS Risk Theme: 6
CAP Seq: R.10
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-010",
    "name": "Credit Policy Compliance Validation",
    "description": "Row-level credit policy checks: age, ticket, ROI, bureau, FOIR, LTV, tenure",
    "cap_seq": "R.10",
    "risk_theme": 6,
    "required_inputs": ["loan_tape"],
    "optional_inputs": ["credit_policy"],
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    Credit Policy Compliance Validation:
    - Check AGE bounds, ticket size ceiling/floor, ROI band, bureau score min,
      FOIR max, LTV max, tenure max per product policy.
    - Group violations by type, branch, product.
    - Compute exception rate per product.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loans", df.to_arrow())

    anomaly_flags = []

    # Build policy DataFrame
    policy_list = []
    raw_policy = credit_policy or kwargs.get("policy_data") or []

    if isinstance(raw_policy, list):
        policy_list = raw_policy
    elif isinstance(raw_policy, dict):
        # {product_code: {param: value}} format
        for prod, params in raw_policy.items():
            if isinstance(params, dict):
                row = {"product_code": prod}
                row.update(params)
                policy_list.append(row)

    if not policy_list:
        # Use default NBFC-generic policy
        products = df["PRODUCT_CODE"].unique().to_list() if "PRODUCT_CODE" in df.columns else ["DEFAULT"]
        for p in products:
            policy_list.append({
                "product_code": p,
                "min_age": 21, "max_age": 65,
                "min_ticket_size": 5000, "max_ticket_size": 5000000,
                "rate_floor": 10.0, "rate_ceiling": 48.0,
                "min_bureau_score": 600,
                "max_foir": 0.65, "max_ltv": 0.90,
                "min_tenure_months": 3, "max_tenure_months": 84,
                "collateral_required": False
            })

    policy_df = pl.DataFrame(policy_list)
    # Ensure all required columns exist
    policy_cols = ["product_code", "min_age", "max_age", "max_ticket_size", "min_ticket_size",
                   "rate_floor", "rate_ceiling", "min_bureau_score", "max_foir", "max_ltv",
                   "max_tenure_months", "min_tenure_months"]
    for col in policy_cols:
        if col not in policy_df.columns:
            policy_df = policy_df.with_columns(pl.lit(None).alias(col))

    con.register("policy", policy_df.to_arrow())

    # Check which optional columns exist in loan tape
    borrower_age_col = "BORROWER_AGE" if "BORROWER_AGE" in df.columns else "NULL AS BORROWER_AGE"
    bureau_col = "BUREAU_SCORE" if "BUREAU_SCORE" in df.columns else "NULL AS BUREAU_SCORE"
    foir_col = "FOIR" if "FOIR" in df.columns else "NULL AS FOIR"
    ltv_col = "LTV_RATIO" if "LTV_RATIO" in df.columns else "NULL AS LTV_RATIO"
    tenure_col = "TENURE_MONTHS" if "TENURE_MONTHS" in df.columns else "NULL AS TENURE_MONTHS"

    violations = con.execute(f"""
        WITH loan_policy AS (
            SELECT
                l.LOAN_ACCOUNT_NO,
                l.PAN_NUMBER,
                l.PRODUCT_CODE,
                l.BRANCH_CODE,
                l.DISBURSEMENT_DATE,
                l.OUTSTANDING_PRINCIPAL,
                l.DISBURSEMENT_AMOUNT,
                l.INTEREST_RATE,
                l.DPD,
                l.IND_AS_STAGE,
                l.{borrower_age_col.split(' AS ')[0] if ' AS ' in borrower_age_col else borrower_age_col} AS BORROWER_AGE,
                l.{bureau_col.split(' AS ')[0] if ' AS ' in bureau_col else bureau_col} AS BUREAU_SCORE,
                l.{foir_col.split(' AS ')[0] if ' AS ' in foir_col else foir_col} AS FOIR,
                l.{ltv_col.split(' AS ')[0] if ' AS ' in ltv_col else ltv_col} AS LTV_RATIO,
                l.{tenure_col.split(' AS ')[0] if ' AS ' in tenure_col else tenure_col} AS TENURE_MONTHS,
                p.min_age, p.max_age,
                p.max_ticket_size, p.min_ticket_size,
                p.rate_floor, p.rate_ceiling,
                p.min_bureau_score,
                p.max_foir, p.max_ltv,
                p.max_tenure_months, p.min_tenure_months
            FROM loans l
            LEFT JOIN policy p ON l.PRODUCT_CODE = p.product_code
        ),
        violation_flags AS (
            SELECT *,
                CASE WHEN min_age IS NOT NULL AND BORROWER_AGE IS NOT NULL AND BORROWER_AGE < min_age THEN 'AGE_BELOW_MIN' END AS age_min_flag,
                CASE WHEN max_age IS NOT NULL AND BORROWER_AGE IS NOT NULL AND BORROWER_AGE > max_age THEN 'AGE_ABOVE_MAX' END AS age_max_flag,
                CASE WHEN max_ticket_size IS NOT NULL AND DISBURSEMENT_AMOUNT IS NOT NULL AND DISBURSEMENT_AMOUNT > max_ticket_size THEN 'TICKET_ABOVE_CEILING' END AS ticket_max_flag,
                CASE WHEN min_ticket_size IS NOT NULL AND DISBURSEMENT_AMOUNT IS NOT NULL AND DISBURSEMENT_AMOUNT < min_ticket_size THEN 'TICKET_BELOW_FLOOR' END AS ticket_min_flag,
                CASE WHEN rate_floor IS NOT NULL AND INTEREST_RATE IS NOT NULL AND INTEREST_RATE < rate_floor THEN 'RATE_BELOW_FLOOR' END AS rate_min_flag,
                CASE WHEN rate_ceiling IS NOT NULL AND INTEREST_RATE IS NOT NULL AND INTEREST_RATE > rate_ceiling THEN 'RATE_ABOVE_CEILING' END AS rate_max_flag,
                CASE WHEN min_bureau_score IS NOT NULL AND BUREAU_SCORE IS NOT NULL AND BUREAU_SCORE < min_bureau_score THEN 'BUREAU_BELOW_MIN' END AS bureau_flag,
                CASE WHEN max_foir IS NOT NULL AND FOIR IS NOT NULL AND FOIR > max_foir THEN 'FOIR_BREACH' END AS foir_flag,
                CASE WHEN max_ltv IS NOT NULL AND LTV_RATIO IS NOT NULL AND LTV_RATIO > max_ltv THEN 'LTV_BREACH' END AS ltv_flag,
                CASE WHEN max_tenure_months IS NOT NULL AND TENURE_MONTHS IS NOT NULL AND TENURE_MONTHS > max_tenure_months THEN 'TENURE_ABOVE_MAX' END AS tenure_flag
            FROM loan_policy
        )
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE, DISBURSEMENT_DATE,
            OUTSTANDING_PRINCIPAL, DISBURSEMENT_AMOUNT, INTEREST_RATE,
            BORROWER_AGE, BUREAU_SCORE, FOIR, LTV_RATIO, TENURE_MONTHS, DPD, IND_AS_STAGE,
            age_min_flag, age_max_flag, ticket_max_flag, ticket_min_flag,
            rate_min_flag, rate_max_flag, bureau_flag, foir_flag, ltv_flag, tenure_flag,
            TRIM(
                COALESCE(age_min_flag || ' ', '') ||
                COALESCE(age_max_flag || ' ', '') ||
                COALESCE(ticket_max_flag || ' ', '') ||
                COALESCE(ticket_min_flag || ' ', '') ||
                COALESCE(rate_min_flag || ' ', '') ||
                COALESCE(rate_max_flag || ' ', '') ||
                COALESCE(bureau_flag || ' ', '') ||
                COALESCE(foir_flag || ' ', '') ||
                COALESCE(ltv_flag || ' ', '') ||
                COALESCE(tenure_flag, '')
            ) AS all_violations
        FROM violation_flags
        WHERE age_min_flag IS NOT NULL OR age_max_flag IS NOT NULL
           OR ticket_max_flag IS NOT NULL OR ticket_min_flag IS NOT NULL
           OR rate_min_flag IS NOT NULL OR rate_max_flag IS NOT NULL
           OR bureau_flag IS NOT NULL OR foir_flag IS NOT NULL
           OR ltv_flag IS NOT NULL OR tenure_flag IS NOT NULL
        ORDER BY OUTSTANDING_PRINCIPAL DESC NULLS LAST
    """).pl()

    # Summary by violation type
    violation_flag_cols = ["age_min_flag", "age_max_flag", "ticket_max_flag", "ticket_min_flag",
                           "rate_min_flag", "rate_max_flag", "bureau_flag", "foir_flag", "ltv_flag", "tenure_flag"]
    summary_by_type = {}
    for vtype in violation_flag_cols:
        if vtype in violations.columns:
            count = violations.filter(pl.col(vtype).is_not_null()).height
            if count > 0:
                amount = float(violations.filter(pl.col(vtype).is_not_null())["OUTSTANDING_PRINCIPAL"].sum() or 0)
                summary_by_type[vtype] = {"count": count, "amount": round(amount, 2)}
                anomaly_flags.append({
                    "field": vtype,
                    "value": count,
                    "threshold": "0 violations",
                    "message": f"{count} credit policy violations of type {vtype}"
                })

    # Exception rate by product
    product_exc_rate = pl.DataFrame()
    if "PRODUCT_CODE" in df.columns and len(violations) > 0:
        con.register("violations", violations.to_arrow())
        product_exc_rate = con.execute("""
            WITH total_by_prod AS (
                SELECT PRODUCT_CODE, COUNT(*) AS total FROM loans GROUP BY PRODUCT_CODE
            ),
            exc_by_prod AS (
                SELECT PRODUCT_CODE, COUNT(*) AS exc_count FROM violations GROUP BY PRODUCT_CODE
            )
            SELECT
                t.PRODUCT_CODE,
                t.total AS total_loans,
                COALESCE(e.exc_count, 0) AS violations_count,
                ROUND(100.0 * COALESCE(e.exc_count, 0) / t.total, 2) AS exception_rate_pct
            FROM total_by_prod t
            LEFT JOIN exc_by_prod e ON t.PRODUCT_CODE = e.PRODUCT_CODE
            ORDER BY exception_rate_pct DESC
        """).pl()

    return {
        "da_ref": "DA-010",
        "total_records": len(df),
        "exceptions_count": len(violations),
        "exceptions_df": violations,
        "product_exception_rates": product_exc_rate,
        "summary": {
            "total_loans": len(df),
            "violations_count": len(violations),
            "violation_rate_pct": round(len(violations) / len(df) * 100, 2) if len(df) > 0 else 0,
            "by_type": summary_by_type,
        },
        "anomaly_flags": anomaly_flags,
    }

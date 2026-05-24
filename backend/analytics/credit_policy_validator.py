"""
Credit Policy Validator
Validates every loan against stored product-wise credit policy parameters
Uses DuckDB for 10M+ row processing
"""

import logging
import polars as pl
import duckdb
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def validate_portfolio(
    loan_tape: pl.LazyFrame,
    policies: List[Dict[str, Any]],
    reporting_date: str = "2025-09-30",
) -> Dict[str, Any]:
    """
    Validate every loan in the portfolio against credit policy.

    Args:
        loan_tape: Normalized loan tape (Polars LazyFrame, 48-field schema)
        policies: List of credit policy dicts (product-wise from DB)
        reporting_date: Audit period end date (YYYY-MM-DD)

    Returns:
        Dict with: violations_df, total_loans, violations_count, rate, summary_by_type,
                   summary_by_product, summary_by_branch
    """
    if not policies:
        df = loan_tape.collect()
        return {"total_loans": len(df), "violations_count": 0, "violation_rate_pct": 0,
                "violations_df": pl.DataFrame(), "summary_by_type": {}, "summary_by_product": [], "summary_by_branch": []}

    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loans", df.to_arrow())

    # Build policy table from list of dicts
    policy_df = pl.DataFrame(policies)
    con.register("policy", policy_df.to_arrow())

    violations = con.execute("""
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
                CAST(l.BORROWER_AGE AS INTEGER) AS BORROWER_AGE,
                CAST(l.BUREAU_SCORE AS INTEGER) AS BUREAU_SCORE,
                CAST(l.FOIR AS DOUBLE) AS FOIR,
                CAST(l.LTV_RATIO AS DOUBLE) AS LTV_RATIO,
                CAST(l.TENURE_MONTHS AS INTEGER) AS TENURE_MONTHS,
                l.DPD,
                l.IND_AS_STAGE,
                CAST(p.min_age AS INTEGER) AS p_min_age,
                CAST(p.max_age AS INTEGER) AS p_max_age,
                CAST(p.max_ticket_size AS DOUBLE) AS p_max_ticket_size,
                CAST(p.min_ticket_size AS DOUBLE) AS p_min_ticket_size,
                CAST(p.rate_floor AS DOUBLE) AS p_rate_floor,
                CAST(p.rate_ceiling AS DOUBLE) AS p_rate_ceiling,
                CAST(p.min_bureau_score AS INTEGER) AS p_min_bureau_score,
                CAST(p.max_foir AS DOUBLE) AS p_max_foir,
                CAST(p.max_ltv AS DOUBLE) AS p_max_ltv,
                CAST(p.max_tenure_months AS INTEGER) AS p_max_tenure_months,
                CAST(p.min_tenure_months AS INTEGER) AS p_min_tenure_months
            FROM loans l
            LEFT JOIN policy p ON l.PRODUCT_CODE = p.product_code
        ),
        violation_flags AS (
            SELECT *,
                CASE WHEN p_min_age IS NOT NULL AND BORROWER_AGE IS NOT NULL
                          AND BORROWER_AGE < p_min_age THEN 'AGE_BELOW_MIN' END AS age_min_flag,
                CASE WHEN p_max_age IS NOT NULL AND BORROWER_AGE IS NOT NULL
                          AND BORROWER_AGE > p_max_age THEN 'AGE_ABOVE_MAX' END AS age_max_flag,
                CASE WHEN p_max_ticket_size IS NOT NULL AND DISBURSEMENT_AMOUNT IS NOT NULL
                          AND DISBURSEMENT_AMOUNT > p_max_ticket_size THEN 'TICKET_ABOVE_CEILING' END AS ticket_max_flag,
                CASE WHEN p_min_ticket_size IS NOT NULL AND DISBURSEMENT_AMOUNT IS NOT NULL
                          AND DISBURSEMENT_AMOUNT < p_min_ticket_size THEN 'TICKET_BELOW_FLOOR' END AS ticket_min_flag,
                CASE WHEN p_rate_floor IS NOT NULL AND INTEREST_RATE IS NOT NULL
                          AND INTEREST_RATE < p_rate_floor THEN 'RATE_BELOW_FLOOR' END AS rate_min_flag,
                CASE WHEN p_rate_ceiling IS NOT NULL AND INTEREST_RATE IS NOT NULL
                          AND INTEREST_RATE > p_rate_ceiling THEN 'RATE_ABOVE_CEILING' END AS rate_max_flag,
                CASE WHEN p_min_bureau_score IS NOT NULL AND BUREAU_SCORE IS NOT NULL
                          AND BUREAU_SCORE < p_min_bureau_score THEN 'BUREAU_BELOW_MIN' END AS bureau_flag,
                CASE WHEN p_max_foir IS NOT NULL AND FOIR IS NOT NULL
                          AND FOIR > p_max_foir THEN 'FOIR_BREACH' END AS foir_flag,
                CASE WHEN p_max_ltv IS NOT NULL AND LTV_RATIO IS NOT NULL
                          AND LTV_RATIO > p_max_ltv THEN 'LTV_BREACH' END AS ltv_flag,
                CASE WHEN p_max_tenure_months IS NOT NULL AND TENURE_MONTHS IS NOT NULL
                          AND TENURE_MONTHS > p_max_tenure_months THEN 'TENURE_ABOVE_MAX' END AS tenure_flag
            FROM loan_policy
        )
        SELECT
            LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE, DISBURSEMENT_DATE,
            OUTSTANDING_PRINCIPAL, DISBURSEMENT_AMOUNT, INTEREST_RATE,
            BORROWER_AGE, BUREAU_SCORE, FOIR, LTV_RATIO, TENURE_MONTHS, DPD, IND_AS_STAGE,
            age_min_flag, age_max_flag, ticket_max_flag, ticket_min_flag,
            rate_min_flag, rate_max_flag, bureau_flag, foir_flag, ltv_flag, tenure_flag,
            TRIM(COALESCE(age_min_flag || ' | ', '') ||
                 COALESCE(age_max_flag || ' | ', '') ||
                 COALESCE(ticket_max_flag || ' | ', '') ||
                 COALESCE(ticket_min_flag || ' | ', '') ||
                 COALESCE(rate_min_flag || ' | ', '') ||
                 COALESCE(rate_max_flag || ' | ', '') ||
                 COALESCE(bureau_flag || ' | ', '') ||
                 COALESCE(foir_flag || ' | ', '') ||
                 COALESCE(ltv_flag || ' | ', '') ||
                 COALESCE(tenure_flag, '')) AS all_violations
        FROM violation_flags
        WHERE age_min_flag IS NOT NULL OR age_max_flag IS NOT NULL
           OR ticket_max_flag IS NOT NULL OR ticket_min_flag IS NOT NULL
           OR rate_min_flag IS NOT NULL OR rate_max_flag IS NOT NULL
           OR bureau_flag IS NOT NULL OR foir_flag IS NOT NULL
           OR ltv_flag IS NOT NULL OR tenure_flag IS NOT NULL
        ORDER BY OUTSTANDING_PRINCIPAL DESC
    """).pl()

    total = len(df)
    violations_count = len(violations)

    # Summary by violation type
    violation_type_cols = [
        "age_min_flag", "age_max_flag", "ticket_max_flag", "ticket_min_flag",
        "rate_min_flag", "rate_max_flag", "bureau_flag", "foir_flag", "ltv_flag", "tenure_flag"
    ]
    summary_by_type = {}
    for vtype in violation_type_cols:
        if vtype in violations.columns:
            flagged = violations.filter(pl.col(vtype).is_not_null())
            if len(flagged) > 0:
                amount = flagged["OUTSTANDING_PRINCIPAL"].sum()
                summary_by_type[vtype] = {
                    "count": len(flagged),
                    "amount_crore": round(float(amount or 0), 2)
                }

    # Summary by product
    summary_by_product = []
    if "PRODUCT_CODE" in violations.columns:
        prod_summary = violations.group_by("PRODUCT_CODE").agg([
            pl.count().alias("count"),
            pl.sum("OUTSTANDING_PRINCIPAL").alias("amount")
        ]).sort("count", descending=True)
        summary_by_product = prod_summary.to_dicts()

    # Summary by branch (top 20)
    summary_by_branch = []
    if "BRANCH_CODE" in violations.columns:
        branch_summary = violations.group_by("BRANCH_CODE").agg([
            pl.count().alias("count"),
            pl.sum("OUTSTANDING_PRINCIPAL").alias("amount")
        ]).sort("count", descending=True).head(20)
        summary_by_branch = branch_summary.to_dicts()

    return {
        "total_loans": total,
        "violations_count": violations_count,
        "violation_rate_pct": round(violations_count / total * 100, 2) if total > 0 else 0,
        "violations_amount_crore": round(float(violations["OUTSTANDING_PRINCIPAL"].sum() or 0), 2),
        "violations_df": violations,
        "summary_by_type": summary_by_type,
        "summary_by_product": summary_by_product,
        "summary_by_branch": summary_by_branch,
    }

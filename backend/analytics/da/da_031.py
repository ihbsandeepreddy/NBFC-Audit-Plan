"""
DA-031: ECL Coverage Ratio Analysis
Compute ECL coverage by stage; compare to benchmarks; flag under-provisioned segments.
LMS Risk Theme: 3
CAP Seq: R.31
"""

import polars as pl
import duckdb
from typing import Optional, Dict, Any

METADATA = {
    "da_ref": "DA-031",
    "name": "ECL Coverage Ratio Analysis",
    "description": "ECL coverage by stage vs benchmarks; flag segments with < benchmark - 20%",
    "cap_seq": "R.31",
    "risk_theme": 3,
    "required_inputs": ["loan_tape"],
    "optional_inputs": [],
}

ECL_BENCHMARKS = {
    1: 0.005,   # Stage 1: ~0.5%
    2: 0.030,   # Stage 2: ~3%
    3: 0.500,   # Stage 3: ~50%+
}


def run(
    loan_tape: pl.LazyFrame,
    repayment_history: Optional[pl.LazyFrame] = None,
    credit_policy: Optional[dict] = None,
    reporting_date: str = "2025-09-30",
    **kwargs
) -> Dict[str, Any]:
    """
    ECL Coverage Ratio Analysis:
    1. Compute TOTAL_ECL_PROVISION / OUTSTANDING_PRINCIPAL by IND_AS_STAGE.
    2. Compare against benchmarks (Stage 1: 0.5%, Stage 2: 3%, Stage 3: 50%+).
    3. Flag segments where coverage < benchmark by > 20%.

    Returns dict with: total_records, exceptions_count, exceptions_df, summary, anomaly_flags
    """
    con = duckdb.connect()

    df = loan_tape.collect()
    con.register("loan_tape", df.to_arrow())

    anomaly_flags = []

    ecl_col = "TOTAL_ECL_PROVISION" if "TOTAL_ECL_PROVISION" in df.columns else None

    if ecl_col is None:
        # Try to build ECL from stage-wise columns
        if "STAGE_1_ECL" in df.columns and "STAGE_2_ECL" in df.columns and "STAGE_3_ECL" in df.columns:
            df = df.with_columns(
                (pl.col("STAGE_1_ECL").fill_null(0) +
                 pl.col("STAGE_2_ECL").fill_null(0) +
                 pl.col("STAGE_3_ECL").fill_null(0)).alias("TOTAL_ECL_PROVISION")
            )
            con.register("loan_tape", df.to_arrow())
            ecl_col = "TOTAL_ECL_PROVISION"

    # ── 1. Stage-level ECL coverage ───────────────────────────────────────
    stage_coverage = pl.DataFrame()
    if ecl_col:
        stage_coverage = con.execute(f"""
            SELECT
                IND_AS_STAGE,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                SUM("{ecl_col}") AS total_ecl,
                ROUND(100.0 * SUM("{ecl_col}") / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 4) AS coverage_pct
            FROM loan_tape
            WHERE IND_AS_STAGE IS NOT NULL
              AND OUTSTANDING_PRINCIPAL IS NOT NULL
            GROUP BY IND_AS_STAGE
            ORDER BY IND_AS_STAGE
        """).pl()
    else:
        stage_coverage = con.execute("""
            SELECT
                IND_AS_STAGE,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                NULL AS total_ecl,
                NULL AS coverage_pct
            FROM loan_tape
            WHERE IND_AS_STAGE IS NOT NULL
              AND OUTSTANDING_PRINCIPAL IS NOT NULL
            GROUP BY IND_AS_STAGE
            ORDER BY IND_AS_STAGE
        """).pl()

    # ── 2. Compare to benchmarks ───────────────────────────────────────────
    coverage_exceptions = []
    if ecl_col and len(stage_coverage) > 0:
        for row in stage_coverage.to_dicts():
            stage = int(row.get("IND_AS_STAGE") or 0)
            coverage = float(row.get("coverage_pct") or 0) / 100.0
            benchmark = ECL_BENCHMARKS.get(stage)
            if benchmark and coverage < benchmark * 0.80:  # < 80% of benchmark
                coverage_exceptions.append({
                    "stage": stage,
                    "coverage_pct": round(coverage * 100, 4),
                    "benchmark_pct": round(benchmark * 100, 2),
                    "gap_pct": round((benchmark - coverage) * 100, 4),
                    "total_outstanding": row.get("total_outstanding"),
                    "total_ecl": row.get("total_ecl"),
                    "exception_type": "COVERAGE_BELOW_BENCHMARK",
                })
                anomaly_flags.append({
                    "field": "ECL_COVERAGE",
                    "value": round(coverage * 100, 2),
                    "threshold": f"{benchmark * 100:.1f}% (benchmark for Stage {stage})",
                    "message": f"Stage {stage} ECL coverage {coverage * 100:.2f}% vs benchmark {benchmark * 100:.1f}% (gap > 20%)"
                })

    coverage_exc_df = pl.DataFrame(coverage_exceptions) if coverage_exceptions else pl.DataFrame()

    # ── 3. Accounts with stage but no ECL provision ───────────────────────
    no_provision_df = pl.DataFrame()
    if ecl_col:
        no_provision_df = con.execute(f"""
            SELECT
                LOAN_ACCOUNT_NO, PAN_NUMBER, PRODUCT_CODE, BRANCH_CODE,
                IND_AS_STAGE, OUTSTANDING_PRINCIPAL,
                "{ecl_col}" AS ecl_provision,
                'STAGE_BUT_NO_ECL' AS exception_type
            FROM loan_tape
            WHERE IND_AS_STAGE IS NOT NULL
              AND IND_AS_STAGE > 0
              AND OUTSTANDING_PRINCIPAL > 0
              AND ("{ecl_col}" IS NULL OR "{ecl_col}" = 0)
            ORDER BY OUTSTANDING_PRINCIPAL DESC
        """).pl()

        if len(no_provision_df) > 0:
            no_prov_amount = float(no_provision_df["OUTSTANDING_PRINCIPAL"].sum() or 0)
            anomaly_flags.append({
                "field": "TOTAL_ECL_PROVISION",
                "value": len(no_provision_df),
                "threshold": "All staged accounts must have ECL provision",
                "message": f"{len(no_provision_df)} accounts with stage classification but zero/null ECL provision; ₹{no_prov_amount:,.0f} outstanding"
            })

    # ── Product-level coverage ─────────────────────────────────────────────
    product_coverage = pl.DataFrame()
    if ecl_col and "PRODUCT_CODE" in df.columns:
        product_coverage = con.execute(f"""
            SELECT
                PRODUCT_CODE,
                IND_AS_STAGE,
                COUNT(*) AS account_count,
                SUM(OUTSTANDING_PRINCIPAL) AS total_outstanding,
                SUM("{ecl_col}") AS total_ecl,
                ROUND(100.0 * SUM("{ecl_col}") / NULLIF(SUM(OUTSTANDING_PRINCIPAL), 0), 4) AS coverage_pct
            FROM loan_tape
            WHERE IND_AS_STAGE IS NOT NULL AND PRODUCT_CODE IS NOT NULL
            GROUP BY PRODUCT_CODE, IND_AS_STAGE
            ORDER BY PRODUCT_CODE, IND_AS_STAGE
        """).pl()

    total_ecl = float(df[ecl_col].sum() or 0) if ecl_col and ecl_col in df.columns else 0
    total_outstanding = float(df["OUTSTANDING_PRINCIPAL"].sum() or 0) if "OUTSTANDING_PRINCIPAL" in df.columns else 0

    return {
        "da_ref": "DA-031",
        "total_records": len(df),
        "exceptions_count": len(coverage_exc_df) + len(no_provision_df),
        "exceptions_df": coverage_exc_df,
        "stage_coverage": stage_coverage,
        "no_provision_accounts": no_provision_df,
        "product_coverage": product_coverage,
        "benchmarks": ECL_BENCHMARKS,
        "summary": {
            "total_loans": len(df),
            "total_outstanding": round(total_outstanding, 2),
            "total_ecl": round(total_ecl, 2),
            "overall_coverage_pct": round(total_ecl / total_outstanding * 100, 4) if total_outstanding > 0 else 0,
            "stages_below_benchmark": len(coverage_exc_df),
            "no_provision_accounts": len(no_provision_df),
        },
        "anomaly_flags": anomaly_flags,
    }

"""
Financial Ratio Computation Engine
Accepts normalized financial data and computes 35+ NBFC ratios
"""

from typing import Dict, Any, Optional


FINANCIAL_ATTRIBUTES = {
    "total_assets": "Total Assets (₹ Cr)",
    "gross_loans": "Gross Loan Portfolio / AUM (₹ Cr)",
    "net_loans": "Net Loans after ECL (₹ Cr)",
    "cash_and_equivalents": "Cash and Cash Equivalents (₹ Cr)",
    "investments": "Investments (₹ Cr)",
    "borrowings_total": "Total Borrowings (₹ Cr)",
    "net_worth": "Net Worth / Equity (₹ Cr)",
    "tier1_capital": "Tier I Capital (₹ Cr)",
    "tier2_capital": "Tier II Capital (₹ Cr)",
    "rwa_on_bs": "Risk Weighted Assets — On Balance Sheet (₹ Cr)",
    "rwa_off_bs": "Risk Weighted Assets — Off Balance Sheet (₹ Cr)",
    "gross_npa": "Gross NPA (₹ Cr)",
    "net_npa": "Net NPA (₹ Cr)",
    "ecl_stage1": "ECL Provision Stage 1 (₹ Cr)",
    "ecl_stage2": "ECL Provision Stage 2 (₹ Cr)",
    "ecl_stage3": "ECL Provision Stage 3 (₹ Cr)",
    "ecl_total": "Total ECL Provision (₹ Cr)",
    "stage1_outstanding": "Stage 1 Outstanding (₹ Cr)",
    "stage2_outstanding": "Stage 2 Outstanding (₹ Cr)",
    "stage3_outstanding": "Stage 3 Outstanding (₹ Cr)",
    "interest_income": "Interest Income (₹ Cr)",
    "interest_expense": "Interest / Finance Costs (₹ Cr)",
    "nii": "Net Interest Income / NII (₹ Cr)",
    "operating_expense": "Operating Expenses / Opex (₹ Cr)",
    "credit_cost": "Credit Cost / Provision Charge (₹ Cr)",
    "pat": "Profit After Tax (₹ Cr)",
    "pbt": "Profit Before Tax (₹ Cr)",
    "avg_assets": "Average Total Assets (₹ Cr)",
    "avg_equity": "Average Net Worth (₹ Cr)",
    "avg_earning_assets": "Average Earning Assets (₹ Cr)",
    "avg_borrowings": "Average Borrowings (₹ Cr)",
    "num_borrowers": "Number of Active Borrowers",
    "num_branches": "Number of Branches",
    "num_employees": "Number of Employees",
    "disbursements_period": "Disbursements in Period (₹ Cr)",
    "hqla": "High Quality Liquid Assets (₹ Cr)",
    "net_cash_outflows_30d": "Net Cash Outflows — 30 days (₹ Cr)",
    "off_bs_commitments": "Off-Balance Sheet Commitments (₹ Cr)",
    "period_label": "Period Label (e.g. Q2 FY2526)",
    "days_in_period": "Number of Days in Reporting Period",
}


def generate_excel_template() -> bytes:
    """Generate downloadable XLSX template with all financial attributes"""
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financial Data Input"

    # Styling
    yellow = PatternFill("solid", fgColor="FFFF00")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )

    # Header row
    headers = ["Attribute Code", "Description", "Period 1 (Current)", "Period 2 (Prior)", "Notes"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin

    ws.row_dimensions[1].height = 30

    # Instructions row
    ws.cell(row=2, column=1, value="INSTRUCTIONS:")
    ws.cell(row=2, column=2, value="Enter values in ₹ Crore. Yellow cells are editable. All amounts in ₹ Crore unless stated. Use negative values for losses.")
    ws.cell(row=2, column=1).font = Font(bold=True)

    # Data rows
    for i, (code, description) in enumerate(FINANCIAL_ATTRIBUTES.items(), start=3):
        ws.cell(row=i, column=1, value=code)
        ws.cell(row=i, column=2, value=description)
        c1 = ws.cell(row=i, column=3)
        c2 = ws.cell(row=i, column=4)
        c1.fill = yellow
        c2.fill = yellow
        c1.border = thin
        c2.border = thin

        # Notes for specific fields
        notes = {
            "avg_assets": "= (Opening + Closing Total Assets) / 2",
            "avg_earning_assets": "= Average of Gross Loans + Investments",
            "avg_borrowings": "= (Opening + Closing Total Borrowings) / 2",
            "avg_equity": "= (Opening + Closing Net Worth) / 2",
            "nii": "= Interest Income - Interest Expense",
            "rwa_on_bs": "Standard: 100%, NPA: 150%, Govt Securities: 0%, HL≤75L: 35%",
            "ecl_total": "= Stage1 ECL + Stage2 ECL + Stage3 ECL",
            "days_in_period": "92 for Q2, 91 for Q1/Q3, 90 for Q4 (non-leap year)",
        }
        if code in notes:
            ws.cell(row=i, column=5, value=notes[code])

    # Column widths
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 50

    # Add Ratios preview sheet
    ws2 = wb.create_sheet("Ratios Reference")
    ws2.cell(1, 1, "Ratio").font = Font(bold=True)
    ws2.cell(1, 2, "Formula").font = Font(bold=True)
    ws2.cell(1, 3, "Benchmark").font = Font(bold=True)

    ratios_ref = [
        ("CRAR", "(Tier I + Tier II) / Total RWA × 100", "Min 15%"),
        ("Tier I Ratio", "Tier I Capital / Total RWA × 100", "Min 10%"),
        ("GNPA %", "Gross NPA / Gross Loans × 100", "< 5% good"),
        ("NNPA %", "Net NPA / (Gross Loans - ECL) × 100", "< 2% preferred"),
        ("PCR", "Total ECL / Gross NPA × 100", "> 70%"),
        ("NIM", "NII / Avg Earning Assets × 100", "> 5% typical"),
        ("ROA", "PAT / Avg Total Assets × 100", "> 2% preferred"),
        ("ROE", "PAT / Avg Net Worth × 100", "> 12% preferred"),
        ("Cost of Funds", "Interest Expense / Avg Borrowings × 100", "7-10% typical"),
        ("LCR", "HQLA / Net Cash Outflows 30d × 100", "Min 100% for NBFC-UL"),
        ("Leverage", "Total Borrowings / Tier I Capital", "Max 6x for NBFC-UL"),
        ("Credit Cost", "Credit Cost / Avg Earning Assets × 100", "< 3% preferred"),
        ("Cost-to-Income", "Operating Expense / NII × 100", "< 50% preferred"),
    ]
    for i, (ratio, formula, benchmark) in enumerate(ratios_ref, 2):
        ws2.cell(i, 1, ratio)
        ws2.cell(i, 2, formula)
        ws2.cell(i, 3, benchmark)
    ws2.column_dimensions["A"].width = 20
    ws2.column_dimensions["B"].width = 45
    ws2.column_dimensions["C"].width = 25

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _safe_div(num: float, denom: float, default: Optional[float] = None) -> Optional[float]:
    if denom and denom != 0:
        return num / denom
    return default


def _pct(val: Optional[float], decimals: int = 2) -> Optional[float]:
    if val is None:
        return None
    return round(val * 100, decimals)


def _flag(value: float, op: str, threshold: float) -> str:
    ops = {">": value > threshold, "<": value < threshold, ">=": value >= threshold, "<=": value <= threshold}
    return "BREACH" if ops.get(op, False) else "OK"


def compute_ratios(data: Dict[str, Any], period_label: str = "Current") -> Dict[str, Any]:
    """Compute all NBFC financial ratios from input data dictionary"""

    def g(key: str, default: float = 0.0) -> float:
        v = data.get(key)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    rwa_total = g("rwa_on_bs") + g("rwa_off_bs")
    gross_loans = g("gross_loans") or 1
    tier1 = g("tier1_capital")
    tier2 = g("tier2_capital")
    total_capital = tier1 + tier2
    ecl_total = g("ecl_total") or (g("ecl_stage1") + g("ecl_stage2") + g("ecl_stage3"))
    avg_assets = g("avg_assets") or g("total_assets") or 1
    avg_equity = g("avg_equity") or g("net_worth") or 1
    avg_earning_assets = g("avg_earning_assets") or gross_loans
    avg_borrowings = g("avg_borrowings") or g("borrowings_total") or 1
    nii = g("nii") or (g("interest_income") - g("interest_expense"))

    ratios: Dict[str, Any] = {}

    # ── Capital Adequacy ──────────────────────────────────────────────────────
    crar_val = _pct(_safe_div(total_capital, rwa_total)) if rwa_total > 0 else None
    ratios["CRAR"] = {"value": crar_val, "description": "Capital to Risk-Weighted Assets Ratio",
                      "benchmark": "Min 15%", "flag": _flag(crar_val or 100, "<", 15)}

    tier1_val = _pct(_safe_div(tier1, rwa_total)) if rwa_total > 0 else None
    ratios["TIER1_RATIO"] = {"value": tier1_val, "description": "Tier I Capital Ratio",
                              "benchmark": "Min 10%", "flag": _flag(tier1_val or 100, "<", 10)}

    lev = _safe_div(g("borrowings_total"), tier1)
    ratios["LEVERAGE"] = {"value": round(lev, 2) if lev is not None else None,
                          "description": "Leverage Ratio (Total Borrowings / Tier I)",
                          "benchmark": "Max 6x for NBFC-UL", "flag": _flag(lev or 0, ">", 6)}

    # ── Asset Quality ─────────────────────────────────────────────────────────
    gnpa_pct = _pct(_safe_div(g("gross_npa"), gross_loans))
    ratios["GNPA_PCT"] = {"value": gnpa_pct, "description": "Gross NPA Ratio",
                          "benchmark": "< 5% good, > 10% concern",
                          "flag": "HIGH" if (gnpa_pct or 0) > 10 else "OK"}

    net_loan_base = gross_loans - ecl_total
    nnpa_pct = _pct(_safe_div(g("net_npa"), net_loan_base if net_loan_base > 0 else gross_loans))
    ratios["NNPA_PCT"] = {"value": nnpa_pct, "description": "Net NPA Ratio",
                          "benchmark": "< 2% preferred", "flag": "HIGH" if (nnpa_pct or 0) > 5 else "OK"}

    pcr = _pct(_safe_div(ecl_total, g("gross_npa") or 1))
    ratios["PCR"] = {"value": pcr, "description": "Provision Coverage Ratio",
                     "benchmark": "> 70% preferred", "flag": "LOW" if (pcr or 100) < 70 else "OK"}

    ecl_cov = _pct(_safe_div(ecl_total, gross_loans))
    ratios["ECL_COVERAGE"] = {"value": ecl_cov, "description": "Total ECL / Gross Loans",
                               "benchmark": "Varies by product mix", "flag": "OK"}

    stage2_pct = _pct(_safe_div(g("stage2_outstanding"), gross_loans))
    ratios["STAGE2_PCT"] = {"value": stage2_pct, "description": "Stage 2 Assets as % of Gross Loans",
                             "benchmark": "< 8%", "flag": "HIGH" if (stage2_pct or 0) > 8 else "OK"}

    stage3_pct = _pct(_safe_div(g("stage3_outstanding"), gross_loans))
    ratios["STAGE3_PCT"] = {"value": stage3_pct, "description": "Stage 3 (NPA) % of Gross Loans",
                             "benchmark": "= GNPA%", "flag": "OK"}

    stage1_ecl_cov = _pct(_safe_div(g("ecl_stage1"), g("stage1_outstanding") or 1))
    ratios["STAGE1_ECL_COVERAGE"] = {"value": stage1_ecl_cov, "description": "ECL Coverage Stage 1",
                                      "benchmark": "~0.5%", "flag": "OK"}

    stage2_ecl_cov = _pct(_safe_div(g("ecl_stage2"), g("stage2_outstanding") or 1))
    ratios["STAGE2_ECL_COVERAGE"] = {"value": stage2_ecl_cov, "description": "ECL Coverage Stage 2",
                                      "benchmark": "~3-5%", "flag": "LOW" if (stage2_ecl_cov or 100) < 2 else "OK"}

    stage3_ecl_cov = _pct(_safe_div(g("ecl_stage3"), g("stage3_outstanding") or 1))
    ratios["STAGE3_ECL_COVERAGE"] = {"value": stage3_ecl_cov, "description": "ECL Coverage Stage 3 (NPA)",
                                      "benchmark": "> 50% for NBFC", "flag": "LOW" if (stage3_ecl_cov or 100) < 50 else "OK"}

    # ── Profitability ─────────────────────────────────────────────────────────
    roa = _pct(_safe_div(g("pat"), avg_assets), 2)
    ratios["ROA"] = {"value": roa, "description": "Return on Assets",
                     "benchmark": "> 2% preferred", "flag": "LOW" if (roa or 0) < 1 else "OK"}

    roe = _pct(_safe_div(g("pat"), avg_equity), 2)
    ratios["ROE"] = {"value": roe, "description": "Return on Equity",
                     "benchmark": "> 12% preferred", "flag": "LOW" if (roe or 0) < 8 else "OK"}

    nim = _pct(_safe_div(nii, avg_earning_assets), 2)
    ratios["NIM"] = {"value": nim, "description": "Net Interest Margin",
                     "benchmark": "> 5% typical for NBFC", "flag": "LOW" if (nim or 100) < 3 else "OK"}

    yield_val = _pct(_safe_div(g("interest_income"), avg_earning_assets), 2)
    ratios["YIELD_ON_ASSETS"] = {"value": yield_val, "description": "Yield on Earning Assets",
                                  "benchmark": "8-18% typical", "flag": "OK"}

    cof = _pct(_safe_div(g("interest_expense"), avg_borrowings), 2)
    ratios["COST_OF_FUNDS"] = {"value": cof, "description": "Cost of Funds",
                                "benchmark": "7-10% typical", "flag": "OK"}

    spread = round(((yield_val or 0) - (cof or 0)), 2)
    ratios["SPREAD"] = {"value": spread, "description": "Interest Rate Spread (Yield - CoF)",
                        "benchmark": "> 3% preferred", "flag": "LOW" if spread < 2 else "OK"}

    credit_cost = _pct(_safe_div(g("credit_cost"), avg_earning_assets), 2)
    ratios["CREDIT_COST"] = {"value": credit_cost, "description": "Credit Cost / Avg Earning Assets",
                              "benchmark": "< 3% preferred", "flag": "HIGH" if (credit_cost or 0) > 3 else "OK"}

    cti = _pct(_safe_div(g("operating_expense"), nii if nii and nii > 0 else 1))
    ratios["COST_TO_INCOME"] = {"value": cti, "description": "Cost to Income Ratio",
                                 "benchmark": "< 50% preferred", "flag": "HIGH" if (cti or 0) > 50 else "OK"}

    pat_margin = _pct(_safe_div(g("pat"), g("interest_income") or 1))
    ratios["PAT_MARGIN"] = {"value": pat_margin, "description": "PAT / Interest Income",
                             "benchmark": "> 15% preferred", "flag": "OK"}

    # ── Liquidity ─────────────────────────────────────────────────────────────
    lcr_val = _pct(_safe_div(g("hqla"), g("net_cash_outflows_30d") or 1))
    ratios["LCR"] = {"value": lcr_val, "description": "Liquidity Coverage Ratio",
                     "benchmark": "Min 100% for NBFC-UL",
                     "flag": "BREACH" if (lcr_val or 100) < 100 else "OK"}

    # ── Efficiency ────────────────────────────────────────────────────────────
    borrowers = g("num_borrowers") or 1
    opex_per_borrower = round(_safe_div(g("operating_expense") * 10_000_000, borrowers) or 0)
    ratios["OPEX_PER_BORROWER"] = {"value": opex_per_borrower, "description": "Operating Cost per Borrower (₹)",
                                    "benchmark": "Varies by segment", "flag": "OK"}

    branches = g("num_branches") or 1
    aum_per_branch = round(_safe_div(g("gross_loans"), branches) or 0, 2)
    ratios["AUM_PER_BRANCH"] = {"value": aum_per_branch, "description": "AUM per Branch (₹ Cr)",
                                 "benchmark": "Varies by business model", "flag": "OK"}

    employees = g("num_employees") or 1
    aum_per_emp = round(_safe_div(g("gross_loans"), employees) or 0, 4)
    ratios["AUM_PER_EMPLOYEE"] = {"value": aum_per_emp, "description": "AUM per Employee (₹ Cr)",
                                   "benchmark": "Varies by product mix", "flag": "OK"}

    # ── Portfolio Mix ─────────────────────────────────────────────────────────
    loans_to_assets = _pct(_safe_div(gross_loans, g("total_assets") or 1))
    ratios["LOANS_TO_ASSETS"] = {"value": loans_to_assets, "description": "Loans as % of Total Assets",
                                  "benchmark": "> 70% for focused NBFC", "flag": "OK"}

    debt_to_equity = round(_safe_div(g("borrowings_total"), g("net_worth") or 1) or 0, 2)
    ratios["DEBT_TO_EQUITY"] = {"value": debt_to_equity, "description": "Debt to Equity Ratio",
                                 "benchmark": "Max 6x for NBFC", "flag": _flag(debt_to_equity, ">", 6)}

    # Summary
    breach_count = sum(1 for r in ratios.values() if r.get("flag") == "BREACH")
    warning_count = sum(1 for r in ratios.values() if r.get("flag") in ["HIGH", "LOW"])

    return {
        "period": period_label,
        "ratios": ratios,
        "input_data": {k: g(k) for k in FINANCIAL_ATTRIBUTES if k not in ["period_label", "days_in_period"]},
        "summary": {
            "total_ratios": len(ratios),
            "breaches": breach_count,
            "warnings": warning_count,
            "healthy": len(ratios) - breach_count - warning_count,
        }
    }


def compute_variance(current: Dict[str, Any], prior: Dict[str, Any]) -> Dict[str, Any]:
    """Compute period-over-period variance for all ratios"""
    variance = {}

    for ratio_code, curr_info in current.get("ratios", {}).items():
        curr_val = curr_info.get("value")
        prior_info = prior.get("ratios", {}).get(ratio_code, {})
        prior_val = prior_info.get("value")

        if curr_val is not None and prior_val is not None:
            try:
                abs_change = round(float(curr_val) - float(prior_val), 2)
                pct_change = round(abs_change / abs(float(prior_val)) * 100, 1) if float(prior_val) != 0 else None
                variance[ratio_code] = {
                    "current": curr_val, "prior": prior_val,
                    "absolute_change": abs_change, "pct_change": pct_change,
                    "direction": "UP" if abs_change > 0 else ("DOWN" if abs_change < 0 else "FLAT"),
                    "flag": "MATERIAL" if pct_change is not None and abs(pct_change) > 15 else "OK",
                }
            except (TypeError, ValueError):
                pass

    return variance

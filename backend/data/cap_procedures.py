"""
Complete CAP Procedures static data — all 19 procedures from the Excel
Seeded into every new engagement on creation
"""

CAP_PROCEDURES = [
    # ── PLANNING ─────────────────────────────────────────────────────────────
    {
        "seq_number": "P.01", "phase": "planning", "section": "Materiality",
        "procedure_name": "Compute Overall Materiality, Performance Materiality, Clearly Trivial threshold",
        "procedure_description": (
            "Step 1: Open Materiality sheet. Enter Total Assets, Gross Loan Portfolio, NII, Net Worth.\n"
            "Step 2: Select Gross Loan Portfolio (0.75%) as primary benchmark — regulators focus on AUM quality.\n"
            "Step 3: Record OM, PM (65% of OM), Trivial (5% of OM) in WP-MAT-01.\n"
            "Step 4: Review all 10 Qualitative Flags — CRAR breach, fraud, RBI penalty, RPT non-arm's-length, going concern — all material regardless of amount.\n"
            "Step 5: Obtain Manager sign-off on WP-MAT-01 before any fieldwork begins."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "All",
        "regulatory_reference": "SA 320 para 9-11",
        "expected_control": "Manager reviews and approves materiality before fieldwork. Qualitative flags considered at engagement acceptance.",
        "data_analytics_step": "DA-049: Compute 4 benchmark materialities. Flag if selected materiality differs from prior year by >15%.",
        "documents_to_obtain": "Latest Balance Sheet; NII schedule; AUM by product; Prior year file",
        "wp_reference": "WP-MAT-01", "budget_hours": 4,
        "template_team_response": "AUM as at [DATE] = ₹[X] Cr. OM = ₹[Y] Cr (0.75% of AUM). PM = ₹[Z] Cr (65% of OM). Trivial = ₹[A] Cr. Qualitative flags reviewed — [none identified / flags: describe]. WP-MAT-01 signed by Manager on [date].",
    },
    {
        "seq_number": "P.02", "phase": "planning", "section": "Fraud Risk Assessment",
        "procedure_name": "Conduct SA 240 fraud brainstorming — 25 NBFC fraud schemes, client-specific risks",
        "procedure_description": (
            "Step 1: Convene formal brainstorming with entire team. Record attendees, date, duration in WP-FRD-01.\n"
            "Step 2: Review all 25 NBFC fraud schemes in Fraud Risk Matrix sheet. For each High-risk scheme, cross-reference the CAP Seq No. addressing it.\n"
            "Step 3: Assess management override risk: period-end JEs, ECL overlay directional bias, NPA date override frequency.\n"
            "Step 4: Add client-specific risks from: prior year, RBI IRR, internal audit, industry events.\n"
            "Step 5: All team members sign attendance in WP-FRD-01."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "E/O,C",
        "regulatory_reference": "SA 240 para 15-17",
        "expected_control": "Management conducts fraud risk assessment. Board receives periodic fraud reports. Whistle-blower mechanism available.",
        "data_analytics_step": "DA-050: Composite red flag scoring — run all 13 LMS analytics simultaneously.",
        "documents_to_obtain": "Fraud Risk Matrix sheet; Prior year file; RBI IRR; Internal Audit Report; Board minutes",
        "wp_reference": "WP-FRD-01", "budget_hours": 3,
        "template_team_response": "Brainstorming [date] — attendees: [list]. 25 schemes reviewed. High-risk identified: (1) [scheme], (2) [scheme]. WP-FRD-01 signed by all team.",
    },
    {
        "seq_number": "P.03", "phase": "planning", "section": "Engagement Planning",
        "procedure_name": "Review RBI Inspection Report — document audit implications in Key Info Review",
        "procedure_description": (
            "Step 1: Obtain latest RBI IRR. Read in full. For each observation, complete one row in Key Info Review.\n"
            "Step 2: For each finding, complete Impact Decision: which CAP procedures need enhancement?\n"
            "Step 3: NPA/IRAC observations → enhance S.03; ECL concerns → S.05; RPT → S.07; IT/audit trail → C.01; capital adequacy → S.09.\n"
            "Step 4: Document all decisions with Manager sign-off in Key Info Review sheet."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "All",
        "regulatory_reference": "SA 315 para 11",
        "expected_control": "Management maintains IRR Action Tracker reviewed by Audit Committee quarterly.",
        "data_analytics_step": "Cross-reference IRR findings with LMS analytics — if IRR noted NPA misclassification, run DA-013 with enhanced parameters.",
        "documents_to_obtain": "RBI IRR (latest); Management IRR response; IRR Action Tracker; Board/AC minutes on IRR",
        "wp_reference": "WP-RCM-01", "budget_hours": 3,
        "template_team_response": "RBI IRR dated [date]. [X] observations. Key: (1) [observation] → enhanced [CAP seq]; (2) [observation] → [action]. All documented in Key Info Review. Manager sign-off [date].",
    },

    # ── RISK ASSESSMENT ───────────────────────────────────────────────────────
    {
        "seq_number": "R.01", "phase": "risk_assessment", "section": "LMS Data Integrity",
        "procedure_name": "Extract LMS loan tape — data integrity and sanity checks (LMS Risk Theme 1)",
        "procedure_description": (
            "Step 1: Request LMS loan tape as at period end (48 fields per Data Schema sheet). Covers ALL accounts.\n"
            "Step 2: Complete Data Completeness Check: record count vs LMS portal; outstanding vs GL; all 48 fields populated.\n"
            "Step 3: Data integrity checks:\n"
            "  (a) Duplicate LOAN_ACCOUNT_NO\n"
            "  (b) Null/blank: LAN, PAN, DISBURSEMENT_DATE, OUTSTANDING_PRINCIPAL, INTEREST_RATE, DPD, IND_AS_STAGE\n"
            "  (c) INTEREST_RATE outside 0-60%\n"
            "  (d) DISBURSEMENT_DATE > MATURITY_DATE\n"
            "  (e) OUTSTANDING_PRINCIPAL < 0\n"
            "  (f) DPD < 0\n"
            "  (g) IND_AS_STAGE not in {1,2,3}\n"
            "Step 4: Exception rate > 2% → escalate to Manager before relying on LMS.\n"
            "Step 5: Document in WP-LG-01. Data quality conclusion required before any other LMS-dependent procedure."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "C,A/V",
        "regulatory_reference": "SA 500 para 6; RBI IT Framework 2017 para 4.3",
        "expected_control": "LMS has field-level validation preventing null entries. System generates daily data quality report reviewed by IT/Operations.",
        "data_analytics_step": "DA-001: Sum OUTSTANDING_PRINCIPAL by product vs GL. Flag differences >₹1L. Flag: duplicate LANs, null mandatory fields, invalid stage codes, impossible date sequences. LMS Risk Theme 1.",
        "documents_to_obtain": "LMS loan tape (48 fields per Data Schema); GL trial balance; LMS portal record count screenshot",
        "wp_reference": "WP-LG-01", "budget_hours": 8,
        "template_team_response": "LMS tape received [date] — [X] records, ₹[Y] Cr. GL reconciliation: difference ₹[A] Cr — items: [describe]. Integrity: [B] dup LANs, [C] null mandatory fields, [D] rate outliers, [E] invalid stage codes. Exception rate: [F]%. Data [acceptable/not acceptable] for reliance. Refer WP-LG-01.",
    },
    {
        "seq_number": "R.02", "phase": "risk_assessment", "section": "LMS Data Integrity",
        "procedure_name": "KYC validation — PAN/mobile/bank duplication, KYC post-disbursement (LMS Risk Theme 2)",
        "procedure_description": (
            "Step 1: Extract KYC fields: PAN_NUMBER, AADHAAR_LAST4, MOBILE_NUMBER, BANK_ACCOUNT_NO, IFSC_CODE.\n"
            "Step 2: Run:\n"
            "  (a) PAN format: AAAAA0000A (10 chars) — flag non-conforming\n"
            "  (b) PAN duplication: same PAN on 3+ active accounts of same product\n"
            "  (c) Mobile sharing: same mobile on 10+ borrower accounts\n"
            "  (d) Bank account sharing: same account on 3+ different borrowers\n"
            "  (e) KYC post-disbursement: VKYC_DATE > DISBURSEMENT_DATE\n"
            "Step 3: Quantify exceptions by branch and DSA. Concentration in one branch = systemic failure.\n"
            "Step 4: Cross-reference flagged accounts with SMA/NPA data."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "R&O,CL",
        "regulatory_reference": "PMLA 2002 s.12; RBI KYC MD para 38",
        "expected_control": "CKYC verification mandatory. LOS prevents disbursement if CKYC not cleared.",
        "data_analytics_step": "DA-026: Flag invalid PAN format, PAN/mobile/bank duplication, VKYC post-disbursement. Branch-wise exception count. LMS Risk Theme 2.",
        "documents_to_obtain": "LMS KYC fields; LOS VKYC logs; CKYC confirmations (sample); Bureau consent log",
        "wp_reference": "WP-ITGC-01", "budget_hours": 6,
        "template_team_response": "KYC on [X] records. PAN format: [A] exceptions. PAN dup: [B] PANs on 3+ accounts. Mobile sharing: [C] on 10+ accounts. KYC post-disbursal: [D] accounts — concentrated in [Branch/DSA]. SMA/NPA: [E]% of KYC exceptions are delinquent. Refer WP-ITGC-01.",
    },
    {
        "seq_number": "R.03", "phase": "risk_assessment", "section": "Portfolio Analytics",
        "procedure_name": "Period-to-period change monitoring and variance analytics (LMS Risk Themes 4, 5, 6)",
        "procedure_description": (
            "Step 1: Extract period-to-period changes in key fields: ROI, EMI amount, EMI dates, tenure, moratorium, asset classification, security value, repayment mode.\n"
            "Step 2: Flag high-risk changes: near period-end (last 5 days of quarter), repeated modifications by same user/branch, classification changes without cash receipts.\n"
            "Step 3: Variance analytics by segment — min/avg/max for: ROI, EMI, tenure, ticket size, LTV/FOIR, DPD, waivers. Flag outliers >2 standard deviations from mean.\n"
            "Step 4: Stress clusters: geographic NPA concentration, single branch >20% of PAR, QoQ PAR shift >5%.\n"
            "Step 5: Escalate systematic patterns as potential systemic control failure or fraud."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "A/V,C",
        "regulatory_reference": "SA 520 para 5; SA 240 para 32",
        "expected_control": "Change management controls prevent unauthorised field modifications. All changes require maker-checker and are logged.",
        "data_analytics_step": "DA-004 (rate override): flag LMS rate ≠ sanctioned rate. DA-005 (segment variance): compute PAR% by branch/state/product, flag outliers >2SD.",
        "documents_to_obtain": "LMS field change log; LMS DPD/PAR report by branch/state/product; Branch/DSA performance MIS",
        "wp_reference": "WP-RCM-01", "budget_hours": 6,
        "template_team_response": "Period changes extracted: [X] field changes across [Y] accounts. High-risk: [Z] near period-end, [A] repeated by same user. Variance: ROI outliers [B] accounts, DPD outliers [C] accounts. Stress clusters: Branch [X] has [Y]% of total PAR. Escalated for targeted substantive testing.",
    },

    # ── CONTROLS ──────────────────────────────────────────────────────────────
    {
        "seq_number": "C.01", "phase": "controls", "section": "IT General Controls",
        "procedure_name": "Test LMS audit trail — application and database level (MCA April 2023)",
        "procedure_description": (
            "Step 1: Obtain IT confirmation audit trail is active at both application and database levels. Obtain activation certificate or system config screenshot.\n"
            "Step 2: Test application-level: make a test change in LMS test account. Navigate to audit log — verify old value, new value, user ID, timestamp captured, log cannot be edited.\n"
            "Step 3: Test database-level: request DBA to demonstrate direct database query is also captured. If DBA cannot demonstrate → CARO 2020 Clause 3(xviii) reportable matter.\n"
            "Step 4: Check inactivity: was audit trail switched off at any point in the audit period? Obtain continuous activation confirmation.\n"
            "Step 5: Document in WP-AT-01. Database-level failure = observation."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "C,E/O",
        "regulatory_reference": "MCA Notification April 1, 2023; Companies Act 2013 s.128",
        "expected_control": "Audit trail permanently enabled — cannot be disabled by any user including administrators. Logs archived to separate read-only repository daily.",
        "data_analytics_step": "DA-025: Extract audit log. Identify gaps >1 hour during business hours. Flag entries with SYSTEM or DBA as user ID. LMS Risk Theme 4.",
        "documents_to_obtain": "Audit trail activation certificate; DBA confirmation DB-level logging; Audit trail log extract (sample); Test evidence of change capture",
        "wp_reference": "WP-AT-01", "budget_hours": 6,
        "template_team_response": "Application-level: test change on [date] — captured with user ID [X], timestamp [Y], old/new values ✓. Database-level: DBA [demonstrated ✓ / COULD NOT demonstrate — escalated]. Inactivity: [no gaps / gaps on dates X,Y]. CARO 3(xviii): [compliant / non-compliant — OBS-XXX raised]. Refer WP-AT-01.",
    },
    {
        "seq_number": "C.02", "phase": "controls", "section": "IT General Controls",
        "procedure_name": "Test user access management — terminated employees, privileged access, maker-checker",
        "procedure_description": (
            "Step 1: Obtain LMS user access report — all user IDs, roles, last login. Obtain HR list of separations in audit period.\n"
            "Step 2: Cross-reference: any separated employee with active LMS access post-separation = control failure.\n"
            "Step 3: Privileged access: for each admin/DBA user, verify written approval from IT Manager and CISO, and quarterly access review.\n"
            "Step 4: Maker-checker: test 20 disbursements — maker ID ≠ checker ID, both active employees, checker has sufficient authority.\n"
            "Step 5: Dormant accounts: user IDs with no login in 90+ days should be disabled."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "C,E/O",
        "regulatory_reference": "SA 315 para 21; RBI IT Framework 2017 para 4.4",
        "expected_control": "HR integrated with LMS — separation triggers automatic access revocation within 2 hours. Maker-checker system-enforced.",
        "data_analytics_step": "DA-025: Cross-match terminated employees with LMS user report. Compute gap between separation and LMS revocation. Flag gaps >24 hours.",
        "documents_to_obtain": "LMS user access report; HR separations in audit period; Access provisioning log; Maker-checker report for 20 disbursements",
        "wp_reference": "WP-ITGC-01", "budget_hours": 8,
        "template_team_response": "LMS users: [X] total, [Y] active. HR separations: [Z]. Cross-ref: [A] separated employees with LMS access post-separation — worst gap [B] days. Privileged: [C] admin users — [D] had written approval. Maker-checker: 20 tested — [E] instances maker=checker (failure). Dormant: [F] accounts no login 90+ days. Observations: [refer OBS]. Refer WP-ITGC-01.",
    },

    # ── SUBSTANTIVE ───────────────────────────────────────────────────────────
    {
        "seq_number": "S.01", "phase": "substantive", "section": "Loan Origination",
        "procedure_name": "Sanction-to-disbursement reconciliation — verify all disbursements have valid LOS sanctions",
        "procedure_description": (
            "Step 1: Extract all Q2 FY26 disbursements from LMS: LAN, sanction date, amount, disbursement date, amount, product, branch. Extract all LOS sanctioned cases for same period.\n"
            "Step 2: Reconcile:\n"
            "  (a) LOS sanctions not in LMS — confirmed lapsed/cancelled?\n"
            "  (b) LMS disbursements not in LOS — CRITICAL: each case is a potential ghost disbursement, investigate immediately.\n"
            "Step 3: Compute sanction-to-disbursement conversion rate by product and branch.\n"
            "Step 4: Reconcile total LMS disbursements to GL disbursement account.\n"
            "Step 5: Select sample: all disbursements >₹1 Cr (100%), ₹10L-₹1 Cr (30 accounts), <₹10L (50 accounts)."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "E/O,C",
        "regulatory_reference": "SA 500 para 6; RBI/DNBS/2023/001 para 8.2",
        "expected_control": "LOS and LMS integrated via API. Every LOS sanction auto-creates pending disbursement in LMS. Manual disbursements not possible.",
        "data_analytics_step": "DA-002: JOIN LOS sanction to LMS disbursement on SANCTION_ID. Flag LMS disbursements without LOS record. Flag LOS sanctions aged >90 days without disbursement. LMS Risk Theme 13.",
        "documents_to_obtain": "LMS disbursement extract; LOS sanction register; GL disbursement account ledger; Sample sanction letters",
        "wp_reference": "WP-MAT-01", "budget_hours": 8,
        "template_team_response": "LMS disbursements: [X] accounts, ₹[Y] Cr. LOS sanctions: [A] accounts, ₹[B] Cr. Reconciliation: [C] LMS without LOS — investigated: [describe]. [D] LOS without LMS — confirmed lapsed. LMS to GL: difference [nil/₹X Cr — timing]. Sample: [X] large (100%), [Y] medium (30), [Z] small (50). Refer WP-MAT-01 and Sampling Log.",
    },
    {
        "seq_number": "S.02", "phase": "substantive", "section": "Loan Origination",
        "procedure_name": "Credit appraisal review — policy compliance for sample (age, rate, bureau, FOIR, authority)",
        "procedure_description": (
            "Step 1: For sample from S.01, obtain complete credit file: application, credit memo, bureau report, income documents, bank statements, sanction letter.\n"
            "Step 2: Verify against Credit Policy Summary:\n"
            "  (a) Borrower age — within policy min/max\n"
            "  (b) Loan amount — within product ticket size ceiling\n"
            "  (c) Interest rate — within approved rate grid\n"
            "  (d) Bureau score — above policy minimum\n"
            "  (e) FOIR/LTV — within policy limit\n"
            "  (f) Sanction authority — appropriate delegation level for ticket size\n"
            "  (g) Mandatory documents — all items present\n"
            "Step 3: For each exception, check formally approved deviation with specific risk justification.\n"
            "Step 4: Compute exception rate. Compare to prior year."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "E/O,A/V",
        "regulatory_reference": "RBI FPC para 4; SA 500 para 6",
        "expected_control": "LOS has built-in credit policy validation — rejects applications outside bands. Deviation approvals workflow-based in LOS.",
        "data_analytics_step": "DA-010: Policy compliance — from LOS, flag: ROI < floor, ticket size > ceiling, bureau score < minimum, age outside band. LMS Risk Theme 10.",
        "documents_to_obtain": "Credit files for sample; Credit Policy Summary sheet; Delegation authority matrix; Deviation register",
        "wp_reference": "WP-RCM-01", "budget_hours": 12,
        "template_team_response": "Tested [X] accounts. Exceptions: (a) Age [B], (b) Ticket [C], (c) Rate [D] below grid, (d) Bureau [E] below min, (e) FOIR/LTV [F] breaches, (f) Authority [G] above limit, (g) Docs [H] missing. Deviation approval absent: [I]. Exception rate: [J]% vs prior year [K]%. Observations: [refer OBS].",
    },
    {
        "seq_number": "S.03", "phase": "substantive", "section": "NPA Classification",
        "procedure_name": "Independent DPD recomputation — verify NPA date uses first default date (not latest bounce)",
        "procedure_description": (
            "Step 1: Extract all accounts with DPD > 0 as at period end.\n"
            "Step 2: For sample (all accounts DPD 60-120 + 30 random from DPD 1-59), obtain full repayment history.\n"
            "Step 3: Independently compute DPD:\n"
            "  RULES:\n"
            "  - First missed = EARLIEST date any scheduled payment was due and not fully received\n"
            "  - Do NOT use latest missed payment date\n"
            "  - Partial payment does NOT reset DPD unless overdue amount fully cleared\n"
            "Step 4: Compare computed DPD to LMS DPD. Flag where LMS DPD < computed DPD — NPA date suppression.\n"
            "Step 5: For suppressed accounts: was DPD-resetting repayment funded by same-day fresh disbursement?\n"
            "Step 6: Extrapolate to full population. Quantify NPA understatement."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "A/V,CL",
        "regulatory_reference": "RBI/2021-22/112 DOR.STR.REC.68 para 4",
        "expected_control": "LMS automatically computes DPD from first default date. No manual override of DPD is possible without CC approval.",
        "data_analytics_step": "DA-013: DPD Aging Bridge — recompute DPD from repayment history. Compare to LMS DPD. Flag computed DPD > LMS DPD. LMS Risk Theme 3.",
        "documents_to_obtain": "LMS loan tape (DPD field); LMS repayment history for sample (every transaction); Repayment audit trail",
        "wp_reference": "WP-NPA-01", "budget_hours": 10,
        "template_team_response": "Population: [X] accounts with DPD > 0. Sample: [Y] DPD 60-120 + 30 random = [Z] total. Recomputation complete. Exceptions: [A] accounts where LMS DPD < computed DPD — gap [B]–[C] days. Most common cause: [describe]. Evergreening cross-check: [D] had fresh disbursement within 5 days. Projected NPA understatement: ₹[X] Cr. OBS-XXX raised. Refer WP-NPA-01.",
    },
    {
        "seq_number": "S.04", "phase": "substantive", "section": "NPA Classification",
        "procedure_name": "Stage migration — SICR 30-DPD backstop, overrides with CC approval, restructured account observation period",
        "procedure_description": (
            "Step 1: Extract all accounts with DPD 28-35 days. Per Ind AS 109 para 5.5.11, DPD ≥ 30 = REBUTTABLE PRESUMPTION of SICR → should be Stage 2.\n"
            "Step 2: For each account with DPD ≥ 30 at Stage 1, check override log: is there a PER-ACCOUNT SICR rebuttal?\n"
            "  VALID REBUTTAL: account-specific (NOT blanket), documented evidence credit risk has NOT increased, approved by Credit Committee.\n"
            "Step 3: Accounts with DPD ≥ 30 at Stage 1 without valid per-account rebuttal = MISCLASSIFIED.\n"
            "Step 4: Review all Stage 2→1 and 3→2 overrides. CC approval? Rationale account-specific? Genuine repayments?\n"
            "Step 5: Restructured accounts: all restructured in last 12 months must remain Stage 2 for full 12-month observation period."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "A/V,CL",
        "regulatory_reference": "Ind AS 109 para 5.5.11; SA 540 para 8",
        "expected_control": "LMS SICR engine auto-moves accounts to Stage 2 at DPD=30. Override requires CC approval workflow.",
        "data_analytics_step": "DA-014: Query: DPD>=30 AND STAGE=1 — list should be empty or fully rebutted. DA-015: Stage override pattern — plot by month, direction, segment.",
        "documents_to_obtain": "LMS extract: DPD 28-35 accounts (Stage 1 and 2); LMS stage override log; Restructured accounts register; CC minutes for stage changes",
        "wp_reference": "WP-STG-01", "budget_hours": 8,
        "template_team_response": "DPD 28-35: [X] accounts at Stage 1 = ₹[Y] Cr. SICR rebuttal: [A] valid account-specific, [B] blanket policy-level (invalid), [C] no override. Misclassified: [B+C] accounts, ₹[D] Cr. ECL impact: additional ₹[E] Cr. Overrides: [F] total — [G] CC approval, [H] without approval. Restructured: [I] upgraded before 12-month period — OBS raised.",
    },
    {
        "seq_number": "S.05", "phase": "substantive", "section": "ECL Provisioning",
        "procedure_name": "ECL independent recomputation — auditor's own PD/LGD estimate for 2 material segments",
        "procedure_description": (
            "Step 1: Identify 2 most material ECL segments by outstanding balance.\n"
            "Step 2: For each segment: loan tape, 3-year historical repayment data, management's ECL inputs (PD, LGD, EAD, SICR threshold, macro adjustment, overlay).\n"
            "Step 3: Develop auditor's PD: extract 3-year actual default data from LMS. Compute actual default rate by quarter. If auditor PD > management PD by >20% → management's PD likely understated.\n"
            "Step 4: Develop auditor's LGD: from resolved NPA pool (last 2 years), compute actual recovery / outstanding at default.\n"
            "Step 5: Apply auditor's PD × LGD × EAD to compute auditor ECL. Compare to management ECL.\n"
            "Step 6: Gap > 10% of PM → document in SUAM as potential misstatement."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "A/V",
        "regulatory_reference": "SA 540 para 15; Ind AS 109",
        "expected_control": "Credit Risk team runs ECL model. Output reviewed by CFO and CRO. Board Risk Committee approves final ECL provision quarterly.",
        "data_analytics_step": "DA-039: PD backtesting — compare predicted PD to actual default rates by segment for last 4 quarters. DA-040: LGD backtesting.",
        "documents_to_obtain": "LMS 3-year historical repayment data; Resolved NPA register (last 2 years); Management's ECL model workings; PD, LGD, EAD inputs",
        "wp_reference": "WP-ECL-12", "budget_hours": 10,
        "template_team_response": "Segments: (1) [Product A] ₹[X] Cr [Y]% AUM; (2) [Product B] ₹[A] Cr [B]% AUM. Seg 1: Auditor PD [X]% vs Mgmt [Y]% — gap [Z]%. Auditor LGD [A]% vs Mgmt [B]%. Auditor ECL ₹[C] Cr vs Mgmt ₹[D] Cr — diff ₹[E] Cr. Total gap: ₹[G] Cr vs PM ₹[H] Cr — [below/above PM]. Refer WP-ECL-12.",
    },
    {
        "seq_number": "S.06", "phase": "substantive", "section": "Income Recognition",
        "procedure_name": "Interest income reconciliation — NPA cash basis only, EIR compliance, cut-off test",
        "procedure_description": (
            "Step 1: Reconcile GL interest income to LMS interest schedule by product. Difference >₹10L must be explained.\n"
            "Step 2: NPA interest test: extract all Stage 3/NPA accounts. Check if interest accrued in P&L — it should NOT be.\n"
            "Step 3: Verify NPA interest suspense account: all NPA interest credited here (not P&L). Only cash receipt moves interest from suspense to P&L.\n"
            "Step 4: EIR: select 10 accounts with processing fees. Verify fee is spread over tenure using EIR method — not recognised upfront.\n"
            "Step 5: Cut-off: extract next period interest entries relating to the audit period. Quantify accrual missing."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "C,A/V",
        "regulatory_reference": "RBI IRAC Norms para 6; Ind AS 109 para 5.4.1",
        "expected_control": "LMS automatically debits interest suspense for all NPA accounts. EIR amortization runs automatically on disbursement date.",
        "data_analytics_step": "DA-019: Compute expected interest (outstanding × ROI/365 × days). Compare to LMS accrued. Flag NPA accounts with interest in P&L.",
        "documents_to_obtain": "GL interest income ledger; LMS interest schedule; Interest suspense account; EIR model (sample); Next period interest postings",
        "wp_reference": "WP-INT-01", "budget_hours": 8,
        "template_team_response": "LMS interest: ₹[X] Cr. GL: ₹[Y] Cr. Reconciling items: [describe]. NPA interest in P&L: [Z] accounts — ₹[A] Cr — misstatement in SUAM. Suspense: balance ₹[B] Cr vs expected ₹[C] Cr. EIR: [E] of 10 correctly spread, [F] front-loaded — ₹[G] Cr misstatement. Cut-off: ₹[H] Cr accrual missing.",
    },
    {
        "seq_number": "S.07", "phase": "substantive", "section": "Related Party Transactions",
        "procedure_name": "Build three-layer RPT universe — Companies Act, Ind AS 24, RBI Connected Lending",
        "procedure_description": (
            "Step 1 — Layer 1 (Companies Act s.2(76)): Obtain Board-approved RPT register. Verify includes directors, director relatives, KMP, KMP relatives, holding/subsidiary/associate companies.\n"
            "Step 2 — Layer 2 (Ind AS 24 para 9): Additional parties: entities under common control of KMP, post-employment benefit plans, entities where NBFC has >20% voting rights.\n"
            "Step 3 — Layer 3 (RBI Connected Lending para 7): Entities where director/shareholder >10% holds >25% interest; cross-shareholding with promoter group; fintech/LSP partners with promoter relationship.\n"
            "Step 4: MCA search — for each director and promoter, search all companies where they are director. Cross-reference with borrower master.\n"
            "Step 5: Extract all RPT transactions from LMS. Test arm's length: compare rate, collateral, tenure to similar unrelated borrowers.\n"
            "Step 6: Compare three-layer universe to Ind AS 24 disclosure. Undisclosed RPT = observation."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "P&D,CL",
        "regulatory_reference": "SA 550 para 11; Ind AS 24 para 9, 18-23",
        "expected_control": "Company Secretary maintains three-layer RPT register reviewed by Audit Committee annually. Directors file annual interest disclosures.",
        "data_analytics_step": "DA-043: Cross-match borrower PAN with director/promoter PAN from MCA. Flag common directors, addresses, authorised signatories. DA-044: Fund flow tracing.",
        "documents_to_obtain": "Board-approved RPT register; MCA search output for all directors/promoters; LMS RPT transaction extract; Ind AS 24 disclosure draft; Shareholder register",
        "wp_reference": "WP-RPT-01", "budget_hours": 8,
        "template_team_response": "Layer 1: Board register [X] entities. Layer 2: [Z] additional (PF trust, associate). Layer 3: MCA search [A] directors — [B] matches in borrower master — [C] not in declared register. Universe: [total] entities. RPT loans: ₹[X] Cr. Arm's length: [D] RPT loans at below-market rate. Disclosure: [E] entities not in Ind AS 24 note — OBS raised.",
    },
    {
        "seq_number": "S.08", "phase": "substantive", "section": "Evergreening Detection",
        "procedure_name": "Evergreening — same-day repayment-disbursement chains, closure+new loan patterns",
        "procedure_description": (
            "Step 1: From LMS, identify all borrower PANs where a repayment was received AND fresh disbursement made within 0–5 days in the audit period.\n"
            "Step 2: Filter high-confidence: repayment ≥ 80% of overdue amount AND fresh disbursement ≥ 80% of repayment amount.\n"
            "Step 3: For each case: (a) trace repayment source (b) was borrower in DPD > 0 at fresh disbursement date?\n"
            "Step 4: Confirmed evergreening: compute what DPD/stage would be if repayment excluded. Quantify provision impact.\n"
            "Step 5: Closure + new loan: flag same borrower where old loan closed and new loan opened within 30 days.\n"
            "Step 6: Investigate top 10 cases — trace funds end-to-end using bank statements."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "E/O,C",
        "regulatory_reference": "SA 240 para 32; RBI/2021-22/112 para 4",
        "expected_control": "NBFC policy prohibits disbursement to borrower with DPD > 0. LOS checks DPD of all existing loans before processing new application.",
        "data_analytics_step": "DA-011: Same-PAN repayment on T + disbursement on T to T+5. Filter: repayment ≥80% overdue, disbursement ≥80% repayment. DA-012: Disbursements where existing loan DPD > 0.",
        "documents_to_obtain": "LMS repayment history by PAN; LMS disbursement history by PAN; Repayment source bank statements; Sanction approvals for flagged disbursements",
        "wp_reference": "WP-FRD-01", "budget_hours": 8,
        "template_team_response": "Full period analysis. Potential evergreening: [Z] borrower-PAN chains. High-confidence: [A] cases, ₹[B] Cr. Top 10 deep-dive: [describe key findings]. NPA impact if repayments excluded: [C] accounts → NPA, provision impact ₹[D] Cr. Closure + new loan: [E] cases in 30 days — [F] had DPD at closure. OBS-XXX raised.",
    },
    {
        "seq_number": "S.09", "phase": "substantive", "section": "Regulatory Compliance",
        "procedure_name": "CRAR independent recomputation — Tier I, Tier II, RWA on-BS and off-BS, CRAR ≥ 15%",
        "procedure_description": (
            "Step 1: Obtain NBFC's CRAR computation workbook.\n"
            "Step 2: Independently verify Tier I capital: paid-up equity (vs share register), free reserves (vs Balance Sheet), less deductions.\n"
            "Step 3: Independently verify RWA on-BS: from validated LMS tape, apply RBI risk weights — standard assets 100%, NPA 150%, Govt securities 0%, HL ≤₹75L at 35%.\n"
            "Step 4: Verify RWA off-BS: obtain undrawn commitments, guarantees, co-lending FLDG, LC/BG. Apply CCF.\n"
            "Step 5: Compute auditor CRAR = (Tier I + Tier II) / (RWA on-BS + off-BS). If auditor CRAR < 15% while management CRAR ≥ 15% → IMMEDIATE escalation."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "CL,A/V",
        "regulatory_reference": "RBI/DNBS/2023/001 para 5",
        "expected_control": "CRAR computed by Finance team, reviewed by CFO, approved by Risk Committee.",
        "data_analytics_step": "DA-048: From validated LMS tape, apply RBI risk weights by product. Compare to management RWA. Include off-BS items.",
        "documents_to_obtain": "NBFC CRAR computation workbook; Balance Sheet; Tier I computation; Tier II instruments list; LMS product-wise outstanding (validated); Off-BS commitments schedule",
        "wp_reference": "WP-CRAR-01", "budget_hours": 8,
        "template_team_response": "Tier I: Equity ₹[X] + Reserves ₹[Y] − Deductions ₹[Z] = ₹[A] Cr. Mgmt Tier I: ₹[B] Cr — diff ₹[C] Cr. RWA on-BS: Auditor ₹[D] Cr vs Mgmt ₹[E] Cr — gap ₹[F] Cr. Off-BS: NBFC excluded [items] — adjusted RWA +₹[G] Cr. Auditor CRAR: [X]% vs Mgmt: [Y]%. [Compliant / Below 15% — immediately escalated].",
    },

    # ── COMPLETION ────────────────────────────────────────────────────────────
    {
        "seq_number": "K.01", "phase": "completion", "section": "Completion & Reporting",
        "procedure_name": "Prepare SUAM — accumulate uncorrected misstatements and evaluate vs materiality",
        "procedure_description": (
            "Step 1: Open SUAM sheet. For each misstatement in Exception Register, add one row: description, FS area, overstatement/understatement, amount, corrected/uncorrected.\n"
            "Step 2: Obtain written management explanation (waiver letter) for all uncorrected items.\n"
            "Step 3: Assess: individual uncorrected > PM → material. Aggregate uncorrected > PM → material in aggregate.\n"
            "Step 4: Qualitative materiality: below PM in amount may still be material by nature — fraud, regulatory breach, RPT, going concern.\n"
            "Step 5: Opinion impact: corrected/below PM → unmodified may be appropriate. Any uncorrected > PM → modified per SA 705.\n"
            "Step 6: EQCR review of SUAM before report sign-off."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "All",
        "regulatory_reference": "SA 450 para 5-12; SA 705",
        "expected_control": "Management corrects all identified errors before sign-off. MRL confirms no known misstatements have been omitted.",
        "data_analytics_step": "Cross-reference all CAP rows with Exceptions Found=Yes — ensure every exception is reflected in SUAM.",
        "documents_to_obtain": "Exception Register; SUAM sheet; Management waiver letters; Prior period SUAM",
        "wp_reference": "WP-MAT-01", "budget_hours": 4,
        "template_team_response": "SUAM prepared: [X] misstatements. Corrected: [Y] items, ₹[A] Cr. Uncorrected: [Z] items, ₹[B] Cr. Individual: [C] items above PM — discussed with EQCR. Aggregate: ₹[B] Cr vs PM ₹[D] Cr — [below/above PM]. Qualitative: [E] items material by nature. Opinion: [Unmodified/Modified]. EQCR review [date].",
    },
    {
        "seq_number": "K.02", "phase": "completion", "section": "Completion & Reporting",
        "procedure_name": "Obtain Management Representation Letter with all NBFC-specific confirmations",
        "procedure_description": (
            "Step 1: Prepare MRL draft per WP-MRL-01. Must be signed by CEO and CFO only.\n"
            "Step 2: Verify MRL includes ALL NBFC-specific confirmations:\n"
            "  (a) ECL model accuracy and key assumptions are reasonable and internally consistent\n"
            "  (b) RPT completeness — all three layers disclosed\n"
            "  (c) All RBI circulars complied with — no regulatory orders concealed\n"
            "  (d) Audit trail active at application AND database levels throughout audit period\n"
            "  (e) CRILC submissions accurate and complete\n"
            "  (f) All frauds reported to RBI within prescribed timelines\n"
            "  (g) No material post-period events not disclosed\n"
            "  (h) Adequate resources to continue operations for 12 months\n"
            "Step 3: MRL date = audit report date.\n"
            "Step 4: File signed MRL in WP-MRL-01."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "All",
        "regulatory_reference": "SA 580 para 9-14",
        "expected_control": "Management has standard MRL template reviewed by legal counsel annually. Signed by CEO and CFO on audit report date.",
        "data_analytics_step": "Cross-reference MRL representations against audit findings — any contradiction must be investigated before accepting.",
        "documents_to_obtain": "Signed MRL (CEO + CFO); Prior year MRL; Draft MRL in WP-MRL-01",
        "wp_reference": "WP-MRL-01", "budget_hours": 3,
        "template_team_response": "MRL draft — all 8 NBFC-specific confirmations included. Sent to CEO and CFO on [date]. Signed MRL received on [date]. MRL date matches audit report date. RPT representation confirmed three-layer scope.",
    },
    {
        "seq_number": "K.03", "phase": "completion", "section": "Completion & Reporting",
        "procedure_name": "Draft Key Audit Matters — ECL estimation and Related Party Transactions",
        "procedure_description": (
            "Step 1: Identify KAM candidates per SA 701 para 9:\n"
            "  (a) ECL estimation — large, uncertain, forward-looking, highly sensitive to assumptions\n"
            "  (b) NPA classification — RBI IRAC compliance, judgment on first default date\n"
            "  (c) RPT — three-layer complexity, connected lending near regulatory limit\n"
            "Step 2: Draft each KAM in SA 701 format:\n"
            "  Section 1 — Why it was a KAM: size, complexity, judgment, regulatory sensitivity\n"
            "  Section 2 — How addressed in audit: specific CAP procedures\n"
            "Step 3: Language must be entity-specific — NOT copied from prior year.\n"
            "Step 4: EQCR review all KAM drafts before finalisation."
        ),
        "applicable_to": "ALL", "risk_rating": "high", "assertion": "P&D,All",
        "regulatory_reference": "SA 701 para 9-12; NFRA Thematic 2024",
        "expected_control": "Management does not prepare or influence KAM language. EQCR reviews all KAMs independently before report issuance.",
        "data_analytics_step": "No specific analytics. Ensure KAM procedures reference specific CAP Seq No.",
        "documents_to_obtain": "EQCR review; Prior year KAM (reference only); Ind AS 107 ECL disclosure draft",
        "wp_reference": "WP-OPN-01", "budget_hours": 5,
        "template_team_response": "KAM 1 — ECL Estimation: Provision ₹[X] Cr on AUM ₹[Y] Cr. Significant judgment on SICR thresholds, PD/LGD, macro overlays. Addressed via CAP S.04, S.05, WP-ECL-12. KAM 2 — RPT: Three-layer universe — MCA search identified [Z] additional parties. Addressed via CAP S.07, WP-RPT-01. EQCR reviewed [date].",
    },
]

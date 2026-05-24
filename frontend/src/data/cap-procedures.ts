import type { Phase, RiskRating } from '@/types'

export interface StaticCAPProcedure {
  seq_number: string
  phase: Phase
  section: string
  procedure_name: string
  procedure_description: string
  applicable_to: string
  risk_rating: RiskRating
  assertion: string
  regulatory_reference: string
  expected_control: string
  data_analytics_step: string
  documents_to_obtain: string
  wp_reference: string
  template_team_response: string
}

export const CAP_PROCEDURES: StaticCAPProcedure[] = [
  // ─── PLANNING ────────────────────────────────────────────────────────────────
  {
    seq_number: 'P.01',
    phase: 'planning',
    section: 'Materiality',
    procedure_name: 'Determine Overall and Performance Materiality',
    procedure_description:
      'Determine overall materiality (OM), performance materiality (PM) and trivial threshold based on financial benchmarks (Gross Loans, Total Assets, NII, Net Worth). Document rationale for benchmark selection per SA 320.',
    applicable_to: 'All NBFC engagements',
    risk_rating: 'high',
    assertion: 'N/A',
    regulatory_reference: 'SA 320 — Materiality in Planning and Performing an Audit',
    expected_control: 'Partner-approved materiality memo prior to fieldwork commencement',
    data_analytics_step: 'N/A',
    documents_to_obtain: 'Latest audited financial statements, management accounts, AUM schedule',
    wp_reference: 'WP-P.01',
    template_team_response:
      'We determined materiality as follows:\n• Benchmark selected: Gross Loans ([X]% of gross loan book of ₹[Y] Cr)\n• Overall Materiality (OM): ₹[Z] Cr\n• Performance Materiality (PM): ₹[A] Cr (65% of OM)\n• Trivial Threshold: ₹[B] Cr (5% of OM)\nRationale: [Explain why Gross Loans was selected as primary benchmark — e.g., NBFC\'s primary risk exposure is credit risk embedded in the loan book, users focus on loan quality]\nQualitative factors considered: [List any qualitative flags such as CRAR proximity to minimum, regulatory actions, fraud risk]\nApproved by: [Partner name] on [Date]',
  },
  {
    seq_number: 'P.02',
    phase: 'planning',
    section: 'Fraud Risk',
    procedure_name: 'Fraud Risk Brainstorming and Assessment',
    procedure_description:
      'Conduct engagement team brainstorming session per SA 240. Identify NBFC-specific fraud risks including loan evergreening, inflated collateral, round-tripping, KYC falsification, and management override of controls. Document presumed risks and planned responses.',
    applicable_to: 'All NBFC engagements',
    risk_rating: 'high',
    assertion: 'Occurrence, Completeness',
    regulatory_reference: 'SA 240 — The Auditor\'s Responsibilities Relating to Fraud in an Audit of Financial Statements',
    expected_control: 'Management anti-fraud policy; Whistleblower mechanism; Internal audit coverage of fraud-prone areas',
    data_analytics_step: 'DA-001 (Duplicate LAN detection); DA-002 (Round-trip loan detection); DA-015 (Evergreening flags)',
    documents_to_obtain: 'Previous year audit file, fraud risk matrix, IA reports, RBI inspection findings',
    wp_reference: 'WP-P.02',
    template_team_response:
      'Brainstorming session conducted on [Date] with team members: [Names and roles]\n\nFraud risks identified:\n1. Revenue recognition fraud (interest income manipulation): [High/Medium/Low] risk — [Rationale]\n2. Loan evergreening to avoid NPA classification: [High] risk — [Rationale]\n3. Collateral overvaluation for secured lending: [Medium] risk\n4. KYC falsification and ghost borrowers: [High] risk\n5. Management override of ECL provisioning models: [High] risk\n6. Round-tripping through related parties: [Medium] risk\n\nAudit responses planned:\n• Unpredictable procedures: [Describe]\n• Extended substantive testing on areas identified: [List areas]\n• Management override procedures: Journal entry testing per SA 240 para 32\n\nConclusion: Fraud risk has been [adequately/insufficiently] addressed by management controls. Additional procedures planned: [DA-001, DA-002, S.08]',
  },
  {
    seq_number: 'P.03',
    phase: 'planning',
    section: 'Regulatory Compliance',
    procedure_name: 'RBI Internal Rate of Return and Compliance Review',
    procedure_description:
      'Review RBI IRR guidelines applicable to NBFC category (Base Layer/Middle Layer/Upper Layer). Assess compliance with Master Direction on NBFC — Scale Based Regulation, IRACP norms, and other circulars issued during the audit period. Identify any new circulars that may impact the audit.',
    applicable_to: 'All RBI-regulated NBFCs',
    risk_rating: 'high',
    assertion: 'Completeness, Rights and Obligations',
    regulatory_reference: 'RBI Master Direction — NBFC Scale Based Regulation 2023; RBI Circular on IRACP Norms',
    expected_control: 'Compliance function tracking regulatory changes; Board-level compliance committee',
    data_analytics_step: 'N/A',
    documents_to_obtain: 'RBI registration certificate, compliance tracker, board minutes, CRAR computation, NBS returns',
    wp_reference: 'WP-P.03',
    template_team_response:
      'RBI regulatory review conducted for period [Period]:\n\nLayer classification: [Base/Middle/Upper/Top] Layer NBFC\nDeposit category: [Non-deposit/Deposit-taking/CIC]\n\nKey regulatory requirements applicable:\n1. IRACP norms — NPA classification: [90 DPD/Special Mention Account criteria reviewed]\n2. Scale-based regulation requirements: [List applicable requirements]\n3. New circulars during audit period: [List RBI circulars with effective dates]\n4. CRAR requirement: [Tier I + Tier II requirement per category]\n\nCompliance gaps identified: [None/List gaps]\nImpact on audit approach: [Describe adjustments to audit plan based on regulatory review]\nLinked CAP procedures: P.03 informs S.03, S.04, S.09',
  },
  // ─── RISK ASSESSMENT ─────────────────────────────────────────────────────────
  {
    seq_number: 'R.01',
    phase: 'risk_assessment',
    section: 'Data Integrity',
    procedure_name: 'LMS Data Integrity and Completeness Validation',
    procedure_description:
      'Obtain loan tape (LMS extract) as at reporting date. Validate completeness of loan portfolio data against trial balance NPA schedule and AUM schedule. Check for duplicate LANs, missing mandatory fields (bureau score, DPD, EMI), and orphan records. Perform record-count reconciliation.',
    applicable_to: 'All NBFCs with LMS',
    risk_rating: 'high',
    assertion: 'Completeness, Existence',
    regulatory_reference: 'SA 315 (Revised) — Identifying and Assessing the Risks of Material Misstatement; RBI Circular on Data Quality',
    expected_control: 'Automated LMS controls for data validation; Monthly LMS-GL reconciliation by finance team',
    data_analytics_step: 'DA-001 (Duplicate LAN detection); DA-002 (Mandatory field completeness); DA-003 (LMS-GL reconciliation)',
    documents_to_obtain: 'LMS loan tape extract (all active loans as at period end), Trial balance, AUM schedule, NPA schedule',
    wp_reference: 'WP-R.01',
    template_team_response:
      'LMS data integrity procedures performed on [Date]:\n\nData obtained: LMS extract dated [Date] — [N] records, [₹X Cr] total outstanding\n\nDA-001 Duplicate LAN test:\n• Total records reviewed: [N]\n• Duplicate LANs found: [N] — [Description of duplicates]\n• Resolution: [Confirmed duplicates/Data entry errors/System artifacts]\n\nDA-002 Mandatory field completeness:\n• Fields tested: LAN, Customer ID, DPD, Bureau Score, EMI, Disbursement Date, Product Code\n• Missing field rate: [X%] — [Below/Above] acceptable threshold of 1%\n• High-risk gaps: [List fields with >1% missing]\n\nDA-003 LMS-GL reconciliation:\n• LMS total outstanding: ₹[X] Cr\n• GL loan book balance: ₹[Y] Cr\n• Difference: ₹[Z] Cr ([%]) — [Reconciling items explained]\n\nConclusion: Data quality is [acceptable/requires management action]. [N] exceptions raised in Exception Register (Ref: EX-[seq])',
  },
  {
    seq_number: 'R.02',
    phase: 'risk_assessment',
    section: 'KYC Compliance',
    procedure_name: 'KYC and AML Compliance Validation',
    procedure_description:
      'Test a sample of loan files for KYC completeness per RBI KYC Master Direction and PMLA requirements. Check for: photo ID, address proof, PAN/Aadhaar linking, periodic KYC update for existing customers, CDD for high-risk customers, and FATF beneficial ownership for corporates.',
    applicable_to: 'All NBFCs — deposit taking and non-deposit',
    risk_rating: 'medium',
    assertion: 'Completeness, Rights and Obligations',
    regulatory_reference: 'RBI KYC Master Direction 2016 (as amended); PMLA 2002; FATF Recommendations',
    expected_control: 'Centralised KYC database; Automated KYC expiry alerts; Onboarding checklist with mandatory fields',
    data_analytics_step: 'DA-004 (KYC expiry check); DA-005 (PAN deduplication)',
    documents_to_obtain: 'KYC policy, sample loan files (40 files for KYC test), CKYC records, AML STR register',
    wp_reference: 'WP-R.02',
    template_team_response:
      'KYC compliance test performed [Date]:\n\nSample size: [N] loans selected using [random/risk-based] sampling\nSampling criteria: [Describe — e.g., 20 high-value, 20 random]\n\nKYC deficiencies noted:\n1. Missing current address proof: [N] files ([X%])\n2. PAN not linked: [N] files\n3. Periodic KYC not updated (>2 years): [N] files\n4. High-risk customers without enhanced CDD: [N] files\n5. FATF beneficial ownership gaps (corporate loans): [N] files\n\nDA-004 KYC expiry analysis:\n• Total active loans: [N]\n• KYC expired (>2 years): [N] ([X%])\n• KYC critical gap (>5 years): [N] ([X%])\n\nAML observations: [Describe STR coverage, suspicious transaction review]\n\nConclusion: [Compliant/Deficiencies noted]. Exceptions raised: [EX-XX]',
  },
  {
    seq_number: 'R.03',
    phase: 'risk_assessment',
    section: 'Portfolio Analytics',
    procedure_name: 'Portfolio Risk Segmentation and Concentration Analysis',
    procedure_description:
      'Perform portfolio analytics on loan tape: product-wise breakdown, geographic concentration, vintage analysis (disbursements by quarter vs current DPD), top-borrower concentration, sector concentration. Compare current period vs prior period for deterioration trends.',
    applicable_to: 'All NBFCs',
    risk_rating: 'high',
    assertion: 'Presentation and Disclosure',
    regulatory_reference: 'SA 315 (Revised); RBI Circular on Large Exposure Framework; Ind AS 107 — Financial Instruments: Disclosures',
    expected_control: 'Portfolio MIS reviewed by Risk Committee monthly; Board-level portfolio review quarterly',
    data_analytics_step: 'DA-006 (Product concentration); DA-007 (Geographic heatmap); DA-008 (Vintage cohort analysis)',
    documents_to_obtain: 'LMS tape, Board MIS pack, Portfolio risk report, Prior period comparative',
    wp_reference: 'WP-R.03',
    template_team_response:
      'Portfolio risk segmentation performed [Date]:\n\nProduct-wise breakdown:\n• [Product A]: ₹[X] Cr ([%] of book)\n• [Product B]: ₹[Y] Cr ([%] of book)\n• [Other]: ₹[Z] Cr ([%] of book)\n\nTop-10 borrower concentration: ₹[X] Cr ([%] of total book)\nLarge exposure limit compliance: [Compliant/Breached — details]\n\nGeographic concentration (top 3 states):\n• [State 1]: [%]\n• [State 2]: [%]\n• [State 3]: [%]\n\nVintage analysis key findings:\n• Cohorts disbursed in [period] showing [X%] NPA rate — [above/below] book average\n• High-stress cohorts identified: [Describe]\n\nConclusion: Portfolio concentration risk is [low/medium/high]. Key risks: [List]. Informs ECL and NPA procedures (S.03, S.04, S.05)',
  },
  // ─── CONTROLS ────────────────────────────────────────────────────────────────
  {
    seq_number: 'C.01',
    phase: 'controls',
    section: 'IT Controls',
    procedure_name: 'Audit Trail and System Log Review',
    procedure_description:
      'Test design and operating effectiveness of IT audit trail controls per Companies Act 2013 Section 143(3)(j) and MCA notification on audit trail. Verify: audit trail enabled in accounting software (tally/SAP/custom), logs cannot be tampered, deletion logs captured, backdated entries flagged.',
    applicable_to: 'All companies — mandatory per MCA 2022 notification',
    risk_rating: 'high',
    assertion: 'Accuracy, Completeness',
    regulatory_reference: 'Companies Act 2013 — Section 143(3)(j); MCA Notification on Audit Trail (April 2022); CARO 2020 Clause 3(vi)',
    expected_control: 'Immutable audit log; Role-based access with log capture; System-generated timestamps; Log backup and retention',
    data_analytics_step: 'DA-009 (Journal entry review — backdated/after-hours); DA-010 (User access pattern analysis)',
    documents_to_obtain: 'IT policy, access log extracts, audit trail configuration screenshots, VAPT report',
    wp_reference: 'WP-C.01',
    template_team_response:
      'Audit trail controls assessment [Date]:\n\nSystem in scope: [ERP/Accounting software name and version]\nAudit trail status: [Enabled/Disabled]\n\nDesign effectiveness:\n• Audit trail enabled: [Yes/No]\n• Covers all transactions: [Yes/Partial — specify gaps]\n• Deletion events captured: [Yes/No]\n• Backdated entry alerting: [Yes/No]\n• Log tampering protection: [Yes/No]\n\nOperating effectiveness (sample testing):\n• Sample of [N] journal entries traced to audit trail\n• Backdated entries found: [N] — [Description]\n• After-hours entries without approval: [N]\n• Override of system controls: [N instances]\n\nDA-009 results: [N] suspicious journal entries flagged (backdated >30 days, after-hours without approval, round-number amounts)\n\nCARO 2020 Clause 3(vi) assessment: [Compliant/Adverse finding — details]\n\nConclusion: Audit trail control is [effective/ineffective]. CARO reporting: [Yes/No adverse comment]',
  },
  {
    seq_number: 'C.02',
    phase: 'controls',
    section: 'IT Controls',
    procedure_name: 'User Access Management and Segregation of Duties',
    procedure_description:
      'Review user access controls in LMS, core banking/NBFC system, and accounting ERP. Check: segregation of duties (disbursement vs NPA classification vs accounting), dormant user accounts, super-user/admin access, shared credentials, and privileged access monitoring. Compare user list against HR active employee list.',
    applicable_to: 'All NBFCs with IT systems',
    risk_rating: 'high',
    assertion: 'Completeness, Accuracy',
    regulatory_reference: 'SA 315 (Revised) — IT General Controls; RBI Circular on Cyber Security Framework for NBFCs; CARO 2020',
    expected_control: 'Quarterly user access review; Automated offboarding workflow; Role-based access control (RBAC); Privileged access management (PAM)',
    data_analytics_step: 'DA-010 (User access analysis — dormant accounts, SoD conflicts)',
    documents_to_obtain: 'Active user list from IT, HR payroll list, Access rights matrix, Last login report',
    wp_reference: 'WP-C.02',
    template_team_response:
      'User access management assessment [Date]:\n\nSystems reviewed: [LMS system name, ERP name]\nTotal users: [N] (LMS), [N] (ERP)\n\nDA-010 access analysis results:\n• Total users reviewed: [N]\n• Dormant users (no login >90 days): [N] — [List if significant]\n• Terminated employees with active access: [N] — HIGH RISK\n• SoD conflicts (disbursement + NPA classification same user): [N]\n• Super-user/admin accounts: [N] — [Justified/Unjustified]\n• Shared credentials: [N instances]\n\nHR reconciliation:\n• Active employees per HR: [N]\n• Active system users: [N]\n• Unmatched users (ex-employees with access): [N]\n\nConclusion: User access controls are [effective/deficient]. [N] critical exceptions raised. Impacts on audit: [Increased substantive testing in area X]',
  },
  // ─── SUBSTANTIVE ─────────────────────────────────────────────────────────────
  {
    seq_number: 'S.01',
    phase: 'substantive',
    section: 'Loan Portfolio',
    procedure_name: 'Sanction-to-Disbursement Process Review',
    procedure_description:
      'Test sample of disbursements during audit period: verify credit approval per credit policy, sanction authority compliance (Sanction Authority Matrix), KYC and credit score at sanction, EMI/NMI calculation, disbursement to correct beneficiary account, and post-disbursement monitoring trigger setup.',
    applicable_to: 'All NBFCs',
    risk_rating: 'high',
    assertion: 'Occurrence, Rights and Obligations, Accuracy',
    regulatory_reference: 'SA 250; RBI Master Direction — Fair Practices Code; Credit Policy of entity',
    expected_control: 'Automated credit scoring; Sanction authority matrix enforced in LMS; Disbursement to bank-verified account only',
    data_analytics_step: 'DA-011 (Policy exception detection); DA-012 (Disbursement beneficiary validation)',
    documents_to_obtain: 'Loan files for sample (sanction letter, KYC, credit appraisal, disbursement instruction, bank statement)',
    wp_reference: 'WP-S.01',
    template_team_response:
      'Sanction-to-disbursement testing [Date]:\n\nSample: [N] loans selected (₹[X] Cr total) using [sampling method]\nSampling stratification: >[X] Cr: [N], [Y-X] Cr: [N], <[Y] Cr: [N]\n\nDA-011 Policy exception detection:\n• Loans exceeding FOIR limit ([X%]): [N] ([Amount])\n• Loans below minimum bureau score ([X]): [N] ([Amount])\n• Loans exceeding LTV limit ([X%]): [N] ([Amount])\n• Sanction authority override (higher amount than authority level): [N] cases\n\nFile testing results ([N] files tested):\n• Missing sanction letter: [N]\n• KYC not complete at sanction: [N]\n• Credit score below policy minimum: [N]\n• Disbursement to third-party account: [N] — [CRITICAL if found]\n• EMI calculation error >₹[threshold]: [N]\n\nConclusion: [N] exceptions noted. Impact on financial statements: ₹[X] Cr of loans disbursed without proper authority. Refer to Exception Register EX-[seq]',
  },
  {
    seq_number: 'S.02',
    phase: 'substantive',
    section: 'Credit Appraisal',
    procedure_name: 'Credit Appraisal Quality and Policy Compliance',
    procedure_description:
      'For selected sample, review quality of credit appraisal: income verification method, collateral valuation methodology, co-borrower/guarantor assessment, bureau score interpretation, stress-testing. Compare appraisal parameters against credit policy. Check for override approvals and document rationale.',
    applicable_to: 'All secured and high-value loan products',
    risk_rating: 'high',
    assertion: 'Occurrence, Valuation',
    regulatory_reference: 'RBI Master Direction on Fair Practices Code; SA 540 (ECL and estimates); Internal Credit Policy',
    expected_control: 'Automated credit scoring model; Field investigation reports; Valuation by approved valuers panel; Credit committee review for large tickets',
    data_analytics_step: 'DA-013 (Bureau score trend analysis); DA-014 (Collateral coverage ratio)',
    documents_to_obtain: 'Credit appraisal notes, Field investigation reports, Valuation reports, Bureau score print-outs, Override approval emails',
    wp_reference: 'WP-S.02',
    template_team_response:
      'Credit appraisal quality review [Date]:\n\nSample: [N] loan files tested\n\nIncome verification:\n• Bank statement analysis: [N]/[N] files — [Adequate/Gaps noted]\n• ITR vs actual income variance >20%: [N] files\n• Informal income acceptance without backup: [N] files\n\nCollateral (secured loans in sample: [N]):\n• Approved panel valuer used: [N]/[N]\n• Valuation date >6 months old at sanction: [N]\n• LTV exceeded post-valuation: [N]\n• Collateral not registered/perfected: [N]\n\nCredit score:\n• Bureau score below policy minimum: [N] (approved with override)\n• Override approved by appropriate authority: [N]/[N]\n• Override rationale documented: [N]/[N]\n\nConclusion: Credit appraisal quality is [acceptable/poor]. Key risk: [describe]. Exceptions: EX-[seq]',
  },
  {
    seq_number: 'S.03',
    phase: 'substantive',
    section: 'NPA Classification',
    procedure_name: 'DPD Recomputation and NPA Classification Accuracy',
    procedure_description:
      'Independently recompute DPD (Days Past Due) for a stratified sample of loans using transaction-level repayment data. Validate that NPA classification (SMA-0, SMA-1, SMA-2, Substandard, Doubtful, Loss) matches RBI IRACP norms. Check for classification errors, delayed NPA recognition (ever-greening flags).',
    applicable_to: 'All NBFCs',
    risk_rating: 'high',
    assertion: 'Valuation, Completeness',
    regulatory_reference: 'RBI Master Circular on IRACP Norms; Ind AS 109 — Financial Instruments (Stage classification)',
    expected_control: 'Automated DPD engine in LMS; Daily batch process for NPA flag update; Exception report for manual overrides',
    data_analytics_step: 'DA-016 (Independent DPD recomputation); DA-017 (NPA classification validation); DA-015 (Evergreening detection)',
    documents_to_obtain: 'Repayment history (transaction-level dump), LMS classification report, NPA schedule, Management\'s NPA computation',
    wp_reference: 'WP-S.03',
    template_team_response:
      'DPD recomputation and NPA validation [Date]:\n\nDA-016 Independent DPD Recomputation:\n• Total loans in sample: [N] (₹[X] Cr)\n• Recomputed DPD matches LMS DPD: [N] ([%])\n• DPD understated by LMS (possible evergreening): [N] loans (₹[Y] Cr)\n• DPD overstated by LMS: [N] loans\n\nDA-015 Evergreening detection:\n• Loans with top-up disbursement within 30 days of overdue: [N] (₹[X] Cr)\n• Loans restructured without downgrade: [N]\n• Circular payments pattern detected: [N] accounts\n\nNPA classification discrepancies:\n• Loans misclassified as Standard (should be NPA): [N] (₹[X] Cr)\n• Stage 1 loans that should be Stage 2: [N] (₹[X] Cr)\n\nImpact on provisioning:\n• Additional provision required: ₹[X] Cr\n• Impact on profit: ₹[X] Cr (pre-tax)\n• Exceeds PM (₹[PM] Cr): [Yes/No]\n\nConclusion: NPA classification requires [no adjustment/adjustment of ₹X Cr]. Raised in SUAM: [SUAM-XX]. Exception: EX-[seq]',
  },
  {
    seq_number: 'S.04',
    phase: 'substantive',
    section: 'ECL / Stage Migration',
    procedure_name: 'SICR Assessment and Stage Migration Testing',
    procedure_description:
      'Evaluate management\'s SICR (Significant Increase in Credit Risk) criteria per Ind AS 109. Test whether loans showing SICR triggers (backstop: 30 DPD, qualitative: payment stress, industry downturn, borrower-specific news) have been correctly migrated from Stage 1 to Stage 2. Check for front-loading bias.',
    applicable_to: 'NBFCs reporting under Ind AS 109',
    risk_rating: 'high',
    assertion: 'Valuation, Completeness',
    regulatory_reference: 'Ind AS 109 — Financial Instruments; SA 540 (Revised) — Auditing Accounting Estimates; RBI ECL Implementation Circular',
    expected_control: 'Automated SICR model with qualitative overlays; Stage migration report with exception flags; RCCM (Risk and Credit Committee) review of SICR policy annually',
    data_analytics_step: 'DA-018 (SICR trigger validation); DA-019 (Stage migration completeness)',
    documents_to_obtain: 'SICR policy document, Stage migration report, ECL model documentation, Back-testing results',
    wp_reference: 'WP-S.04',
    template_team_response:
      'SICR and Stage Migration assessment [Date]:\n\nSICR criteria review:\n• Backstop criterion (30 DPD): [Correctly implemented/Issues noted]\n• Qualitative criteria: [List criteria from policy — payment stress signals, watch list, etc.]\n• Forward-looking information incorporated: [Yes/No] — [Describe macroeconomic variables used]\n\nDA-018 SICR trigger validation:\n• Stage 1 loans with DPD 1-29 (SICR backstop met): [N] (₹[X] Cr) — should be Stage 2\n• Stage 1 loans on credit watch list: [N] (₹[X] Cr)\n• Discrepancy — loans remaining Stage 1 despite SICR: [N] (₹[X] Cr)\n\nDA-019 Stage migration completeness:\n• Loans upgraded Stage 2→1 without cure period: [N]\n• Cure period applied: [months] — [Compliant/Non-compliant with policy]\n\nECL impact of SICR correction:\n• Additional Stage 2 provision required: ₹[X] Cr\n• Net profit impact: ₹[X] Cr\n\nConclusion: SICR assessment [adequate/requires restatement]. SUAM: [SUAM-XX]',
  },
  {
    seq_number: 'S.05',
    phase: 'substantive',
    section: 'ECL',
    procedure_name: 'ECL Model Recomputation and Adequacy Assessment',
    procedure_description:
      'Independently recompute ECL for 2 material segments (by product/stage) using auditor\'s own PD/LGD/EAD estimates derived from historical data analysis. Compare with management\'s ECL. Test ECL model inputs: PD calibration (through-the-cycle vs point-in-time), LGD (collateral recovery rates, cure rates), EAD (drawdown assumptions), discount rate. Assess model governance.',
    applicable_to: 'NBFCs under Ind AS 109',
    risk_rating: 'high',
    assertion: 'Valuation',
    regulatory_reference: 'Ind AS 109 paras 5.5.1–5.5.20; SA 540 (Revised); RBI Circular on ECL for NBFCs',
    expected_control: 'Independent model validation by Risk/Actuarial function; Annual back-testing; ECL committee sign-off; Sensitivity analysis documentation',
    data_analytics_step: 'DA-020 (ECL recomputation — Segment A); DA-021 (ECL recomputation — Segment B); DA-022 (Macro overlay impact)',
    documents_to_obtain: 'ECL model documentation, PD/LGD/EAD parameter files, Back-testing report, Model validation report, Historical loss data, Recovery rate schedule',
    wp_reference: 'WP-S.05',
    template_team_response:
      'ECL recomputation and adequacy assessment [Date]:\n\nSegment A — [Product name, Stage X]:\n• Management ECL: ₹[X] Cr (coverage: [%])\n• Auditor recomputed ECL: ₹[Y] Cr (coverage: [%])\n• Difference: ₹[Z] Cr ([%] of management estimate)\n• Key driver of difference: [PD calibration/LGD assumption/Macro overlay]\n\nSegment B — [Product name, Stage X]:\n• Management ECL: ₹[X] Cr\n• Auditor ECL: ₹[Y] Cr\n• Difference: ₹[Z] Cr\n\nModel inputs assessment:\n• PD: [Through-the-cycle used — appropriate/inappropriate for IFRS 9 forward-looking requirement]\n• LGD: Recovery rate [%] — [Supported by historical data/Optimistic]\n• Macro overlays: [GDP, unemployment used — adequate/insufficient]\n• Model validation: [Performed/Not performed] by [function]\n\nTotal ECL adequacy:\n• Management total ECL: ₹[X] Cr\n• Auditor assessment: ₹[Y] Cr\n• Shortfall: ₹[Z] Cr — [Exceeds/Does not exceed] PM of ₹[PM] Cr\n\nConclusion: [ECL adequate/understated]. SUAM entry: [SUAM-XX]',
  },
  {
    seq_number: 'S.06',
    phase: 'substantive',
    section: 'Income Recognition',
    procedure_name: 'Interest Income Recognition and Accrual Testing',
    procedure_description:
      'Test interest income recognition: verify effective interest rate (EIR) method application per Ind AS 109, cutoff of interest income vs. accrual, interest on NPA accounts (should be recognized only on cash basis per RBI), processing fee amortization over loan tenure, and prepayment income recognition.',
    applicable_to: 'All NBFCs',
    risk_rating: 'high',
    assertion: 'Occurrence, Accuracy, Cutoff',
    regulatory_reference: 'Ind AS 109 para 5.4 — EIR Method; RBI IRACP Norms — Interest on NPA; Ind AS 18 (legacy); SA 240',
    expected_control: 'Automated EIR calculation in system; Separate NPA interest suspense account; Month-end accrual review by Finance',
    data_analytics_step: 'DA-023 (Interest income recomputation on sample); DA-024 (NPA interest in P&L detection)',
    documents_to_obtain: 'Interest income GL schedule, EIR calculation workings, NPA account list, Processing fee register',
    wp_reference: 'WP-S.06',
    template_team_response:
      'Interest income recognition testing [Date]:\n\nDA-023 Interest income recomputation:\n• Sample: [N] accounts (₹[X] Cr outstanding)\n• EIR method correctly applied: [N]/[N]\n• EIR method errors — impact: ₹[X] Cr\n\nNPA interest in P&L (DA-024):\n• Total NPA loans: ₹[X] Cr\n• Interest recognised on NPA loans: ₹[Y] Cr (should be nil per cash basis)\n• Overstatement of income: ₹[Y] Cr — [Exceeds/Below] PM\n\nCutoff testing:\n• Loans disbursed/repaid in last 5 days of period — [N] accounts reviewed\n• Cutoff errors (interest booked in wrong period): ₹[X] Cr\n\nProcessing fee amortisation:\n• Policy: amortised over [loan tenure/upfront] — [Compliant with EIR/Non-compliant]\n• Unamortised fees deferred correctly: [Yes/No] — Impact: ₹[X] Cr\n\nConclusion: Income [correctly recognised/overstated by ₹X Cr]. SUAM: [SUAM-XX]',
  },
  {
    seq_number: 'S.07',
    phase: 'substantive',
    section: 'Related Party Transactions',
    procedure_name: 'RPT Universe Identification and Disclosure Completeness',
    procedure_description:
      'Obtain complete RPT universe: identify all related parties per Ind AS 24 (promoters, directors, KMPs, subsidiaries, associates, entities with common control). Check: RPT disclosure completeness in notes, arm\'s-length pricing, board/shareholder approval where required, SEBI (for listed) RPT policy compliance, RBI large exposure compliance for group entities.',
    applicable_to: 'All NBFCs — especially listed entities',
    risk_rating: 'high',
    assertion: 'Completeness, Presentation and Disclosure',
    regulatory_reference: 'Ind AS 24 — Related Party Disclosures; SEBI LODR Regulation 23 (listed); Companies Act Section 188; SA 550 — Related Parties',
    expected_control: 'Board-approved RPT register; Annual declaration by directors/KMPs; Audit committee review of material RPTs; SEBI RPT policy for listed entities',
    data_analytics_step: 'DA-025 (RPT completeness — GL payee matching against related party list)',
    documents_to_obtain: 'Related party register, Director declarations, Board minutes (RPT approvals), Bank statements (payments to/from RPs), Loan book (loans to related parties)',
    wp_reference: 'WP-S.07',
    template_team_response:
      'RPT universe and disclosure testing [Date]:\n\nDA-025 RPT completeness scan:\n• Related party master list: [N] entities/individuals\n• GL payee matches: [N] potential RPTs detected via name matching\n• New RPTs identified (not in declared list): [N] — [Details]\n\nRPT sample testing ([N] transactions, ₹[X] Cr):\n• Arm\'s-length pricing — market rate evidence available: [N]/[N]\n• Board/Audit Committee approval obtained: [N]/[N]\n• Shareholder approval (Section 188 limits exceeded): [N] cases — [Approved/Not approved]\n• SEBI RPT policy followed (listed entity): [Compliant/Deficient]\n\nDisclosure completeness:\n• RPTs disclosed in notes: [N] transactions\n• Undisclosed RPTs identified: [N] — [Amount]\n• Format and classification correct (Ind AS 24): [Yes/Partially]\n\nConclusion: RPT disclosures [complete/incomplete]. Undisclosed RPTs: ₹[X] Cr. Refer EX-[seq], SUAM [SUAM-XX]',
  },
  {
    seq_number: 'S.08',
    phase: 'substantive',
    section: 'Evergreening',
    procedure_name: 'Loan Evergreening and Restructuring Detection',
    procedure_description:
      'Detect loan evergreening (extending credit to enable borrower to repay existing overdue) and irregular restructuring: scan for loans topped up within 30 days of overdue date, back-to-back disbursements across group entities, interest capitalisation without fresh credit assessment, and restructuring without RBI-compliant framework.',
    applicable_to: 'All NBFCs — critical for mid/upper layer',
    risk_rating: 'high',
    assertion: 'Occurrence, Valuation',
    regulatory_reference: 'SA 240 — Fraud; RBI Circular on Restructuring of Advances; RBI IRACP Norms — Asset Classification; Ind AS 109',
    expected_control: 'LMS rule engine blocking same-borrower top-up within 30 days of overdue; Restructuring committee with IA participation; CRILC reporting for >₹5 Cr accounts',
    data_analytics_step: 'DA-015 (Evergreening pattern detection); DA-026 (Restructuring completeness and compliance)',
    documents_to_obtain: 'Loan transaction history, Restructuring register, CRILC submissions, Same-customer disbursement report',
    wp_reference: 'WP-S.08',
    template_team_response:
      'Evergreening and restructuring detection [Date]:\n\nDA-015 Evergreening analysis:\n• Same-borrower top-up within 30 days of overdue: [N] accounts (₹[X] Cr)\n• Confirmed evergreening (reviewed files): [N] accounts (₹[Y] Cr)\n• Avoided NPA through top-up: [N] accounts — if classified NPA, additional provision: ₹[Z] Cr\n\nDA-026 Restructuring compliance:\n• Total restructured accounts: [N] (₹[X] Cr)\n• RBI-compliant restructuring (Resolution Framework): [N]\n• Restructured without downgrade: [N] — [Regulatory violation — details]\n• CRILC reported: [N]/[N accounts >₹5 Cr]\n\nCircular payment pattern:\n• Round-trip accounts identified: [N] accounts (₹[X] Cr)\n• Confirmed round-trip (follow-on investigation): [N]\n\nFraud indicator assessment:\n• Fraud risk elevated: [Yes/No] — [Rationale]\n• Referred to SA 240 fraud response: [Yes/No]\n\nConclusion: Evergreening risk is [low/medium/high]. Potential NPA understatement: ₹[X] Cr. SUAM: [SUAM-XX]. Fraud: [Suspected/Ruled out]',
  },
  {
    seq_number: 'S.09',
    phase: 'substantive',
    section: 'Capital Adequacy',
    procedure_name: 'CRAR and Tier I Capital Adequacy Verification',
    procedure_description:
      'Independently verify Capital to Risk-weighted Assets Ratio (CRAR) computation. Check: risk weight assignment per RBI guidelines, Tier I and Tier II capital components, deductions from regulatory capital (goodwill, DTA, investments), CRAR against regulatory minimum (10% Tier I, 15% overall for NBFC-ND-SI), and adequacy of capital planning.',
    applicable_to: 'NBFC-ND-SI and Deposit-taking NBFCs',
    risk_rating: 'high',
    assertion: 'Accuracy, Presentation and Disclosure',
    regulatory_reference: 'RBI Master Circular on Prudential Norms for NBFCs; RBI Scale Based Regulation — Capital Requirements; Ind AS 32 — Financial Instruments: Presentation',
    expected_control: 'Monthly CRAR computation reviewed by CFO; Board capital adequacy review; Stress-testing for CRAR sensitivity',
    data_analytics_step: 'DA-027 (CRAR recomputation — risk weight validation)',
    documents_to_obtain: 'CRAR computation workings, Risk-weighted assets schedule, Capital adequacy return (NBS-7), Instrument-wise capital classification, DTA computation',
    wp_reference: 'WP-S.09',
    template_team_response:
      'CRAR verification [Date]:\n\nManagement\'s CRAR: [X]% (Tier I: [Y]%, Tier II: [Z]%)\n\nDA-027 Risk weight validation:\n• Total RWA per management: ₹[X] Cr\n• Auditor recomputed RWA: ₹[Y] Cr\n• Difference: ₹[Z] Cr ([%]) — [Reasons for variance]\n\nCapital computation:\n• Tier I Capital: ₹[X] Cr\n  - Paid-up equity: ₹[A] Cr\n  - Retained earnings: ₹[B] Cr\n  - Deductions (intangibles, DTA): ₹[C] Cr\n• Tier II Capital: ₹[X] Cr\n  - Subordinated debt: ₹[A] Cr (limits applied)\n  - General provisions: ₹[B] Cr (max 1.25% of RWA)\n\nAuditor computed CRAR: [X]% (Tier I: [Y]%)\nRegulatory minimum: 15% overall, 10% Tier I\nHeadroom: [+X%/−X% BREACH]\n\nConclusion: CRAR is [compliant/in breach of] regulatory minimum. [If breach: qualitative flag raised, going concern assessment triggered]. CARO Clause 3(xv) assessment: [Compliant/Adverse]',
  },
  // ─── COMPLETION ──────────────────────────────────────────────────────────────
  {
    seq_number: 'K.01',
    phase: 'completion',
    section: 'SUAM',
    procedure_name: 'Schedule of Unadjusted Misstatements (SUAM) and Opinion Assessment',
    procedure_description:
      'Compile all identified misstatements in the SUAM. Evaluate individually and in aggregate: whether uncorrected misstatements exceed PM, assess qualitative factors even where quantitative thresholds not breached. Apply SA 450 evaluation framework. Obtain management representation on SUAM items. Determine audit opinion impact (unmodified/modified).',
    applicable_to: 'All engagements',
    risk_rating: 'high',
    assertion: 'N/A — Opinion procedure',
    regulatory_reference: 'SA 450 — Evaluation of Misstatements Identified During the Audit; SA 705 — Modifications to the Opinion in the Independent Auditor\'s Report; SA 706',
    expected_control: 'N/A',
    data_analytics_step: 'N/A',
    documents_to_obtain: 'All SUAM entries, Management response to SUAM, Representation letter',
    wp_reference: 'WP-K.01',
    template_team_response:
      'SUAM evaluation [Date]:\n\nSUAM Summary:\n• Corrected misstatements: ₹[X] Cr ([N] items)\n• Uncorrected misstatements: ₹[Y] Cr ([N] items)\n  - Overstatements: ₹[A] Cr\n  - Understatements: ₹[B] Cr\n• Qualitative items (material by nature): [N] items\n\nIndividual assessment:\n• Items exceeding PM individually: [N] items — [List]\n• Items waived by management with rationale: [N]\n\nAggregate assessment:\n• Total uncorrected vs PM (₹[PM] Cr): [₹Y Cr — [X%] of PM]\n• Aggregation analysis: [Directional consistency — overstatements aggregate to X Cr]\n• Aggregate exceeds PM: [Yes/No]\n\nOpinion assessment per SA 705:\n• Uncorrected aggregate: [Does not exceed/Exceeds] PM\n• Qualitative flags: [List]\n• Recommended opinion: [Unmodified / Qualified (except for) / Adverse]\n• SA 705 paragraph reference: [Para X]\n\nManagement response to SUAM: Received on [Date]. Management has [corrected/waived/disputed] the following items: [List]',
  },
  {
    seq_number: 'K.02',
    phase: 'completion',
    section: 'Management Representations',
    procedure_name: 'Management Representation Letter Review',
    procedure_description:
      'Obtain and review management representation letter (MRL) covering all required representations per SA 580: going concern, fraud, completeness of related parties, subsequent events, compliance with laws, completeness of accounting records, SUAM acknowledgment. Ensure signed by CEO and CFO on letterhead, dated same as audit report.',
    applicable_to: 'All engagements',
    risk_rating: 'medium',
    assertion: 'N/A',
    regulatory_reference: 'SA 580 — Written Representations; SA 560 — Subsequent Events; SA 265',
    expected_control: 'N/A',
    data_analytics_step: 'N/A',
    documents_to_obtain: 'Signed MRL on company letterhead (CEO + CFO sign-off)',
    wp_reference: 'WP-K.02',
    template_team_response:
      'MRL review [Date]:\n\nMRL received: [Yes/No] — Dated: [Date] (should match report date: [Date])\nSigned by: [CEO name] and [CFO name]\n\nMRL checklist:\n□ Going concern statement: [Included/Missing]\n□ Fraud confirmation (no known fraud): [Included/Missing]\n□ All related parties identified: [Included/Missing]\n□ Subsequent events: [Included/Missing — period: report date to MRL date]\n□ Compliance with laws and regulations: [Included/Missing]\n□ Completeness of accounting records: [Included/Missing]\n□ SUAM acknowledgment: [Included/Missing]\n□ Litigation and contingent liabilities disclosed: [Included/Missing]\n□ Capital adequacy representation: [Included/Missing]\n\nGaps: [List any missing representations and follow-up action]\n\nConclusion: MRL is [complete/incomplete — action required before issuing report]',
  },
  {
    seq_number: 'K.03',
    phase: 'completion',
    section: 'Key Audit Matters',
    procedure_name: 'Key Audit Matters Identification and Drafting',
    procedure_description:
      'Determine KAMs per SA 701: matters that required significant auditor attention (complex estimates, significant risk, judgment). For NBFC: ECL provisioning, NPA classification, and RPT disclosures are typically KAMs. Draft KAM communication with: description of matter, why it was a KAM, how it was addressed in the audit. Obtain EQCR review.',
    applicable_to: 'Listed entities and large NBFCs',
    risk_rating: 'medium',
    assertion: 'N/A — Communication procedure',
    regulatory_reference: 'SA 701 — Communicating Key Audit Matters in the Independent Auditor\'s Report; SA 260; SA 265',
    expected_control: 'N/A',
    data_analytics_step: 'N/A',
    documents_to_obtain: 'Prior year KAMs, Audit committee discussion notes, EQCR review comments',
    wp_reference: 'WP-K.03',
    template_team_response:
      'KAM determination and drafting [Date]:\n\nKAMs identified for current year:\n\nKAM 1: Expected Credit Loss (ECL) Provisioning\n• Why a KAM: ECL involves significant management judgment in PD/LGD estimation, forward-looking macro overlays, and SICR assessment. Total ECL of ₹[X] Cr is material.\n• How addressed: [Summarize procedures S.04, S.05 — ECL model testing, independent recomputation, sensitivity analysis]\n• Conclusion: ECL is [adequately/inadequately] provisioned.\n\nKAM 2: NPA Classification and Asset Quality\n• Why a KAM: NPA classification involves complex DPD computation, evergreening risk, and large judgment-based staging. NPA book of ₹[X] Cr.\n• How addressed: [Summarize S.03, S.08 — DPD recomputation, evergreening detection, sample testing]\n\nKAM 3: Related Party Transactions\n• Why a KAM: [If applicable — RPT complexity, undisclosed RPTs risk, arm\'s-length pricing judgment]\n• How addressed: [Summarize S.07]\n\nEQCR review: [Completed by [Name] on [Date] / Pending]\n\nFinal KAM text: [Attach drafted KAM paragraphs for report]',
  },
]

export function getProcedureBySeq(seq: string): StaticCAPProcedure | undefined {
  return CAP_PROCEDURES.find(p => p.seq_number === seq)
}

export function getProceduresByPhase(phase: Phase): StaticCAPProcedure[] {
  return CAP_PROCEDURES.filter(p => p.phase === phase)
}

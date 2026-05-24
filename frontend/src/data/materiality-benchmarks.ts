export interface MaterialityBenchmark {
  id: string
  label: string
  description: string
  percentage: number
  recommended_for: string
  basis: string
}

export const MATERIALITY_BENCHMARKS: MaterialityBenchmark[] = [
  {
    id: 'gross_loans',
    label: 'Gross Loan Portfolio',
    description:
      'Most relevant benchmark for NBFCs as the primary economic activity is lending. Users of NBFC financial statements focus on loan book quality, NPA ratios, and credit risk. Recommended by most NBFC engagement partners.',
    percentage: 0.75,
    recommended_for: 'Lending-focused NBFCs, MFIs, HFCs, vehicle finance companies',
    basis: 'SA 320 para A6 — for financial institutions, benchmarks related to loans may be most relevant to users',
  },
  {
    id: 'total_assets',
    label: 'Total Assets',
    description:
      'Used when NBFC has significant non-lending activities (investments, treasury, fee income). Covers all balance sheet items comprehensively. Standard fallback for diversified NBFCs.',
    percentage: 0.5,
    recommended_for: 'Diversified NBFCs with significant non-lending activities, investment companies, CICs',
    basis: 'ICAI guidance — 0.5% to 1% of total assets for financial sector entities',
  },
  {
    id: 'nii',
    label: 'Net Interest Income (NII)',
    description:
      'Appropriate for P&L focused engagements where primary concern is income statement accuracy. Used when NII is the primary driver of stakeholder decisions (e.g., for profitability-focused assessments).',
    percentage: 5.0,
    recommended_for: 'Engagements where profitability and interest spread analysis is primary focus',
    basis: 'SA 320 para A3 — profit before tax or revenue may be appropriate where performance is measured primarily through income',
  },
  {
    id: 'net_worth',
    label: 'Net Worth / Total Equity',
    description:
      'Recommended when NBFC is close to CRAR minimum or capital adequacy is a primary concern. Ensures misstatements that affect capital computation are captured. Key for RBI-focused compliance audits.',
    percentage: 1.0,
    recommended_for: 'NBFCs near CRAR minimum, entities with going concern concerns, high-leverage NBFCs',
    basis: 'SA 320 — net assets (equity) may be appropriate when users focus on capital adequacy; CRAR sensitivity',
  },
]

export interface MaterialityComputation {
  benchmark_id: string
  benchmark_value: number
  om_percentage: number
  overall_materiality: number
  performance_materiality: number  // 65% of OM
  trivial_threshold: number        // 5% of OM
}

export function computeMateriality(
  benchmarkId: string,
  benchmarkValue: number,
  customPercentage?: number
): MaterialityComputation {
  const benchmark = MATERIALITY_BENCHMARKS.find(b => b.id === benchmarkId)
  const pct = customPercentage ?? benchmark?.percentage ?? 0.75
  const om = (benchmarkValue * pct) / 100
  return {
    benchmark_id: benchmarkId,
    benchmark_value: benchmarkValue,
    om_percentage: pct,
    overall_materiality: om,
    performance_materiality: om * 0.65,
    trivial_threshold: om * 0.05,
  }
}

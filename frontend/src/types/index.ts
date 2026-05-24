export type UserRole = 'partner' | 'eqcr' | 'manager' | 'senior_auditor' | 'it_auditor' | 'articled_assistant' | 'specialist'
export type ProcedureStatus = 'pending' | 'in_progress' | 'completed'
export type ReviewStatus = 'not_reviewed' | 'in_review' | 'approved'
export type RiskRating = 'high' | 'medium' | 'low'
export type Phase = 'planning' | 'risk_assessment' | 'controls' | 'substantive' | 'completion'
export type ExceptionStatus = 'open' | 'partially_open' | 'resolved' | 'caro_adverse'
export type JobStatus = 'uploaded' | 'normalizing' | 'running' | 'completed' | 'failed'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
}

export interface Engagement {
  id: string
  client_name: string
  audit_firm_name: string
  engagement_partner_name: string
  eqcr_partner_name: string
  file_reference: string
  period_from: string
  period_to: string
  target_report_date: string
  nbfc_layer: string
  deposit_category: string
  engagement_type: string
  sebi_status: string
  risk_level: string
  overall_materiality: number | null
  performance_materiality: number | null
  trivial_threshold: number | null
  gross_loan_portfolio: number | null
  tier_i_capital: number | null
  team_roster: TeamMember[]
  qualitative_flags: QualitativeFlag[]
}

export interface TeamMember {
  staff_code: string
  name: string
  role: string
  max_hours: number
  rate_per_hour: number
  sections_assigned: string
  notes?: string
}

export interface QualitativeFlag {
  flag_name: string
  flagged: boolean
  notes?: string
}

export interface CAPProcedure {
  id: string
  engagement_id: string
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
  template_team_response?: string
  // Dynamic fields
  status: ProcedureStatus
  assigned_to: string | null
  budget_hours: number | null
  actual_hours: number | null
  start_date: string | null
  completion_date: string | null
  team_response: string
  exceptions_found: boolean
  observation: string
  reviewer_comments: string
  review_status: ReviewStatus
  reviewed_by: string | null
  reviewed_at: string | null
  updated_at: string
}

export interface AuditException {
  id: string
  engagement_id: string
  exception_ref: string
  cap_seq: string
  nature: string
  description: string
  account_or_lan?: string
  amount_crore?: number
  risk_rating: RiskRating
  suam_ref?: string
  wp_reference: string
  management_response?: string
  status: ExceptionStatus
  created_at: string
}

export interface SUAMEntry {
  id: string
  engagement_id: string
  suam_ref: string
  fs_area: string
  direction: 'overstatement' | 'understatement'
  amount_crore: number
  is_corrected: boolean
  is_qualitative: boolean
  has_waiver: boolean
  exceeds_pm: boolean
  exceeds_om: boolean
}

export interface CreditPolicy {
  id: string
  product_code: string
  product_name: string
  min_age: number
  max_age: number
  max_ticket_size: number
  min_ticket_size?: number
  rate_floor: number
  rate_ceiling: number
  min_bureau_score: number
  max_foir: number
  max_ltv: number
  max_tenure_months: number
  sanction_authority_levels: Record<string, string>
}

export interface AnalyticsJob {
  id: string
  engagement_id: string
  job_type: string
  da_ref: string
  status: JobStatus
  original_filename: string
  file_size_bytes: number
  total_records?: number
  records_processed?: number
  exceptions_found: number
  progress_percent: number
  results_summary?: Record<string, unknown>
  output_file_path?: string
  error_message?: string
  created_at: string
  completed_at?: string
}

export interface FinancialRatio {
  name: string
  category: string
  current: number | null
  prior: number | null
  change: number | null
  benchmark: number | null
  unit: string
  breach: boolean
}

export interface DRQItem {
  id: string
  category: string
  description: string
  format: string
  period: string
  responsible: string
  status: 'pending' | 'requested' | 'received'
  date_requested?: string
  date_received?: string
  notes?: string
}

export interface WorkingPaper {
  wp_ref: string
  description: string
  cap_seq: string
  assigned_to: string
  status: 'draft' | 'final' | 'reviewed'
  date: string
}

// WebSocket event types
export type WSEventType =
  | 'CAP_STATUS_UPDATED'
  | 'EXCEPTION_ADDED'
  | 'SUAM_RECALCULATED'
  | 'ANALYTICS_JOB_COMPLETE'
  | 'USER_JOINED'
  | 'USER_LEFT'

export interface WSEvent {
  type: WSEventType
  payload: Record<string, unknown>
  user_name?: string
  timestamp: string
}

export interface ActivityFeedItem {
  id: string
  type: WSEventType
  message: string
  user_name?: string
  timestamp: string
}

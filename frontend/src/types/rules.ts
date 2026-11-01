export type RuleSeverity = 'CRITICAL' | 'MAJOR' | 'MINOR'
export type RuleStatus = 'PASS' | 'FAIL' | 'REVIEW' | 'NOT_EVALUATED' | 'WAIVED'
export type HarnessVerdictType = 'ACCEPT' | 'REJECT' | 'HOLD'
export type CheckSheetItemState = 'OK' | 'NG' | 'CORRECTED'
export type BranchType = 'W' | 'X' | 'T' | 'Y' | 'V'

export interface EvidenceRef {
  name: string
  value: unknown
  source: string
  timestamp?: string
  confidence?: number
  bounding_box?: [number, number, number, number]
  metadata?: Record<string, unknown>
}

export interface RuleResult {
  rule_id: string
  family: string
  name: string
  source_doc: string
  severity: RuleSeverity
  status: RuleStatus
  mandatory: boolean
  expected?: unknown
  actual?: unknown
  tolerance?: unknown
  deviation?: unknown
  evidence_refs: EvidenceRef[]
  reason: string
  reaction_plan?: string
}

export interface CheckSheetEntry {
  first_piece: CheckSheetItemState
  last_piece: CheckSheetItemState
  notes?: string
}

export interface FinalAssemblyCheckSheetInput {
  shift: string
  date: string
  part_no: string
  associate_name: string
  e_code: string
  total_production_qty: number
  label_serial_from: number
  label_serial_to: number
  label_serial_scrapped: number
  checks: Record<string, CheckSheetEntry>
}

export interface BranchTapingInput {
  branch_id: string
  branch_type: BranchType
  laps?: number
  cycle_time_seconds?: number
  cross_taping_present: boolean
  excess_taping: boolean
  loose_taping: boolean
  step_laps?: number
  completion_laps?: number
  extension_mm?: number
}

export interface OperatorAttestation {
  user_id: string
  user_name: string
  timestamp: string
  attested: boolean
  notes: string
}

export interface OperatorInput {
  check_sheet?: FinalAssemblyCheckSheetInput
  branch_taping?: BranchTapingInput[]
  master_sample_status?: 'OK' | 'NG' | 'EXPIRED'
  attestations?: Record<string, OperatorAttestation>
  dsi_test_result?: Record<string, unknown>
}

export interface HarnessVerdict {
  verdict_id: string
  timestamp: string
  verdict: HarnessVerdictType
  variant: string
  part_no: string
  rule_pack_version: string
  calibration_provenance: string
  image_hash: string
  rule_results: RuleResult[]
  summary: {
    PASS: number
    FAIL: number
    REVIEW: number
    NOT_EVALUATED: number
    WAIVED: number
    TOTAL: number
    CRITICAL_FAIL?: number
    MAJOR_FAIL?: number
    MINOR_FAIL?: number
  }
  reaction_plan: string
  reasons: string[]
}

export interface RuleEvaluationRequest {
  variant: string
  part_no: string
  use_active_image: boolean
  image_base64?: string
  operator_input?: OperatorInput
}

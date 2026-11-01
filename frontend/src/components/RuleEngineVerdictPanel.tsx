import {
  CheckCircle2,
  CircleX,
  ClipboardCheck,
  Clock3,
  Download,
  FileChartColumn,
  Play,
  Search,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from 'lucide-react'
import { useState } from 'react'
import type {
  BranchTapingInput,
  CheckSheetEntry,
  CheckSheetItemState,
  FinalAssemblyCheckSheetInput,
  HarnessVerdict,
  OperatorInput,
  RuleResult,
} from '../types/rules'
import { downloadVerdictCsv, downloadVerdictPdf, evaluateRules } from '../services/api'

interface RuleEngineVerdictPanelProps {
  verdict: HarnessVerdict | null
  onVerdictChange: (verdict: HarnessVerdict) => void
  onSelectRule?: (rule: RuleResult | null) => void
  selectedRuleId?: string | null
  className?: string
}

const DEFAULT_CHECK_ITEMS = [
  { id: 'FRM19-01-LENGTH', name: 'Length as per drawing', severity: 'CRITICAL' },
  { id: 'FRM19-02-PART-ATTACH', name: 'Correct part attachment', severity: 'CRITICAL' },
  { id: 'FRM19-03-NO-CKT-WRONG', name: 'No circuit wrong', severity: 'CRITICAL' },
  { id: 'FRM19-04-COLOUR-VTB', name: 'Correct colour VTB', severity: 'MAJOR' },
  { id: 'FRM19-05-VTB-PUNCHING', name: 'VTB punching as per drawing', severity: 'MAJOR' },
  { id: 'FRM19-06-NO-EXCESS-TAPE', name: 'No excess taping', severity: 'MAJOR' },
  { id: 'FRM19-07-LABEL-ATTACH', name: 'Correct label attachment', severity: 'MAJOR' },
  { id: 'FRM19-08-NO-LOOSE-TAPE', name: 'No loose taping', severity: 'MAJOR' },
  { id: 'FRM19-09-NO-WRONG-TERM', name: 'No wrong terminal', severity: 'CRITICAL' },
]

export function RuleEngineVerdictPanel({
  verdict,
  onVerdictChange,
  onSelectRule,
  selectedRuleId,
  className = '',
}: RuleEngineVerdictPanelProps) {
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)
  const [showOperatorForm, setShowOperatorForm] = useState(false)
  const [localSelectedRule, setLocalSelectedRule] = useState<RuleResult | null>(null)

  // Filtering states
  const [familyFilter, setFamilyFilter] = useState<string>('all')
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Operator Inputs State
  const [shift, setShift] = useState('A')
  const [associateName, setAssociateName] = useState('Line Associate 01')
  const [eCode, setECode] = useState('EMP-7801')
  const [partNo, setPartNo] = useState('YH200502')
  const [variant, setVariant] = useState('YH200502')
  const [totalQty, setTotalQty] = useState(1)
  const [serialFrom, setSerialFrom] = useState(100001)
  const [serialTo, setSerialTo] = useState(100001)
  const [serialScrapped, setSerialScrapped] = useState(0)
  const [masterSampleStatus, setMasterSampleStatus] = useState<'OK' | 'NG' | 'EXPIRED'>('OK')

  // Check Sheet Items Map
  const [checks, setChecks] = useState<Record<string, CheckSheetEntry>>(() => {
    const init: Record<string, CheckSheetEntry> = {}
    for (const item of DEFAULT_CHECK_ITEMS) {
      init[item.id] = { first_piece: 'OK', last_piece: 'OK', notes: '' }
    }
    return init
  })

  // Branch Taping Inputs
  const [tapingList] = useState<BranchTapingInput[]>([
    {
      branch_id: 'BR-01',
      branch_type: 'W',
      laps: 28,
      cycle_time_seconds: 22.0,
      cross_taping_present: false,
      excess_taping: false,
      loose_taping: false,
      extension_mm: 30.0,
    },
  ])

  const handleRunEvaluation = async () => {
    setEvaluating(true)
    setEvalError(null)

    const checkSheetInput: FinalAssemblyCheckSheetInput = {
      shift,
      date: new Date().toISOString().split('T')[0],
      part_no: partNo,
      associate_name: associateName,
      e_code: eCode,
      total_production_qty: totalQty,
      label_serial_from: serialFrom,
      label_serial_to: serialTo,
      label_serial_scrapped: serialScrapped,
      checks,
    }

    const operatorInput: OperatorInput = {
      check_sheet: checkSheetInput,
      branch_taping: tapingList,
      master_sample_status: masterSampleStatus,
      attestations: {
        'WI79-DUMMY-SEALS': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Dummy seals verified in all unpopulated cavities',
        },
        'WI79-TBO-CHECK': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Secondary locks engaged, zero push-back',
        },
        'WI79-HOUSING-TERMINAL': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Housing intact, terminal lance clean',
        },
        'WI79-CLAMP-STAMP': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Clamp stamp applied at inspection checkpoints',
        },
        'WI79-CIRCUIT-STAMP': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Circuit electrical continuity stamp verified',
        },
        'PTDB-19': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Crimping tight, no PVC highlight',
        },
        'PTDB-20': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Conductor flush inside terminal crimp',
        },
        'PTDB-21': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'White wire secondary lock confirmed at CNG coupler',
        },
        'PTDB-22': {
          user_id: eCode,
          user_name: associateName,
          timestamp: new Date().toISOString(),
          attested: true,
          notes: 'Relay box terminal seating locked',
        },
      },
    }

    try {
      const res = await evaluateRules({
        variant,
        part_no: partNo,
        use_active_image: true,
        operator_input: operatorInput,
      })
      onVerdictChange(res)
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : 'Evaluation error')
    } finally {
      setEvaluating(false)
    }
  }

  // Filtered Rules
  const filteredRules = (verdict?.rule_results || []).filter((r) => {
    if (familyFilter !== 'all' && r.family !== familyFilter) return false
    if (severityFilter !== 'all' && r.severity !== severityFilter) return false
    if (statusFilter !== 'all' && r.status !== statusFilter) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const match =
        r.rule_id.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.reason.toLowerCase().includes(q)
      if (!match) return false
    }
    return true
  })

  const verdictType = verdict?.verdict || 'HOLD'
  const isAccept = verdictType === 'ACCEPT'
  const isReject = verdictType === 'REJECT'
  const isHold = verdictType === 'HOLD'

  const activeSelectedRule =
    verdict?.rule_results.find((r) => r.rule_id === selectedRuleId) || localSelectedRule

  const handleRowClick = (rule: RuleResult) => {
    setLocalSelectedRule(rule)
    onSelectRule?.(rule)
  }

  return (
    <div className={`rule-engine-container ${className}`}>
      {/* 1. Large Verdict Banner */}
      <div
        className={`rule-verdict-banner ${
          isAccept
            ? 'rule-verdict-banner--accept'
            : isReject
            ? 'rule-verdict-banner--reject'
            : 'rule-verdict-banner--hold'
        }`}
      >
        <div className="rule-verdict-banner-inner">
          <div className="rule-verdict-main">
            <div className="rule-verdict-icon-box">
              {isAccept && <CheckCircle2 size={32} color="#ffffff" />}
              {isReject && <CircleX size={32} color="#ffffff" />}
              {isHold && <Clock3 size={32} color="#ffffff" />}
            </div>
            <div>
              <div className="rule-verdict-tag-row">
                <span className="rule-verdict-eyebrow">
                  Final Quality Verdict · {verdict?.variant || variant}
                </span>
                <span className="rule-verdict-pack-tag">
                  Pack v{verdict?.rule_pack_version || '1.0.0'}
                </span>
              </div>
              <h2 className="rule-verdict-title">
                {isAccept && 'ACCEPT — CONFORMING HARNESS'}
                {isReject && 'REJECT — NON-CONFORMANCE DETECTED'}
                {isHold && 'HOLD — PENDING QUALITY INSPECTION / ATTESTATION'}
              </h2>
              <div className="rule-verdict-provenance">
                <span>Provenance: <strong>{verdict?.calibration_provenance || 'uncalibrated'}</strong></span>
                {verdict && (
                  <span className="rule-verdict-stats-badge">
                    {verdict.summary.PASS} PASS / {verdict.summary.FAIL} FAIL / {verdict.summary.REVIEW} REVIEW / {verdict.summary.NOT_EVALUATED} HELD
                  </span>
                )}
                {!verdict && <span>· No evaluation executed yet</span>}
              </div>
            </div>
          </div>

          <div className="rule-verdict-actions">
            <button
              type="button"
              onClick={handleRunEvaluation}
              disabled={evaluating}
              className="rule-btn-evaluate"
            >
              <Play size={16} />
              {evaluating ? 'Evaluating...' : 'Evaluate Rules'}
            </button>

            {verdict && (
              <>
                <button
                  type="button"
                  onClick={() => downloadVerdictPdf(verdict.verdict_id)}
                  className="rule-btn-glass"
                >
                  <Download size={15} />
                  PDF Cert
                </button>
                <button
                  type="button"
                  onClick={() => downloadVerdictCsv(verdict.verdict_id)}
                  className="rule-btn-glass"
                >
                  <FileChartColumn size={15} />
                  CSV
                </button>
              </>
            )}

            <button
              type="button"
              onClick={() => setShowOperatorForm(!showOperatorForm)}
              className="rule-btn-glass"
            >
              <SlidersHorizontal size={15} />
              {showOperatorForm ? 'Hide Operator Inputs' : 'Operator Inputs'}
            </button>
          </div>
        </div>

        {/* Reaction Plan Alert on REJECT or HOLD */}
        {(isReject || isHold) && verdict?.reaction_plan && (
          <div className="rule-reaction-plan-box">
            <TriangleAlert size={19} color="#ffffff" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div className="rule-reaction-plan-content">
              <strong>Factory Reaction Plan:</strong>
              <p>{verdict.reaction_plan}</p>
            </div>
          </div>
        )}
      </div>

      {evalError && (
        <div className="alert-banner" role="alert">
          <TriangleAlert size={20} />
          <div>
            <strong>Evaluation Error</strong>
            <span>{evalError}</span>
          </div>
        </div>
      )}

      {/* 2. Operator Inputs Drawer / Form */}
      {showOperatorForm && (
        <div className="panel rule-operator-panel">
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ClipboardCheck size={20} color="var(--blue-600)" />
              <div>
                <p className="eyebrow">QUALITY ATTESTATION & CHECK SHEET</p>
                <h2 style={{ fontSize: '18px', margin: 0 }}>
                  Operator Inspection Inputs (FRM/PR/19 rev 10 & BT45-02)
                </h2>
              </div>
            </div>
            <button
              type="button"
              className="button button--ghost"
              style={{ minHeight: '30px', padding: '0 10px', fontSize: '10px' }}
              onClick={() => setShowOperatorForm(false)}
            >
              <X size={14} /> Close
            </button>
          </div>

          <div className="rule-operator-grid">
            <div className="rule-form-group">
              <label className="rule-form-label">Shift</label>
              <select
                value={shift}
                onChange={(e) => setShift(e.target.value)}
                className="rule-form-select"
              >
                <option value="A">Shift A (Morning)</option>
                <option value="B">Shift B (Evening)</option>
                <option value="C">Shift C (Night)</option>
              </select>
            </div>
            <div className="rule-form-group">
              <label className="rule-form-label">Associate Name</label>
              <input
                type="text"
                value={associateName}
                onChange={(e) => setAssociateName(e.target.value)}
                className="rule-form-input"
              />
            </div>
            <div className="rule-form-group">
              <label className="rule-form-label">Employee E-Code</label>
              <input
                type="text"
                value={eCode}
                onChange={(e) => setECode(e.target.value)}
                className="rule-form-input"
              />
            </div>
            <div className="rule-form-group">
              <label className="rule-form-label">Master Sample Status</label>
              <select
                value={masterSampleStatus}
                onChange={(e) => setMasterSampleStatus(e.target.value as 'OK' | 'NG' | 'EXPIRED')}
                className="rule-form-select"
              >
                <option value="OK">OK (Validated Active)</option>
                <option value="NG">NG (Non-conforming)</option>
                <option value="EXPIRED">EXPIRED (Shift Expired)</option>
              </select>
            </div>

            <div className="rule-form-group">
              <label className="rule-form-label">Total Production Qty</label>
              <input
                type="number"
                value={totalQty}
                onChange={(e) => setTotalQty(Number(e.target.value))}
                className="rule-form-input"
              />
            </div>
            <div className="rule-form-group">
              <label className="rule-form-label">Label Serial From</label>
              <input
                type="number"
                value={serialFrom}
                onChange={(e) => setSerialFrom(Number(e.target.value))}
                className="rule-form-input"
              />
            </div>
            <div className="rule-form-group">
              <label className="rule-form-label">Label Serial To</label>
              <input
                type="number"
                value={serialTo}
                onChange={(e) => setSerialTo(Number(e.target.value))}
                className="rule-form-input"
              />
            </div>
            <div className="rule-form-group">
              <label className="rule-form-label">Labels Scrapped</label>
              <input
                type="number"
                value={serialScrapped}
                onChange={(e) => setSerialScrapped(Number(e.target.value))}
                className="rule-form-input"
              />
            </div>
          </div>

          {/* 9 Check Sheet Items */}
          <div className="rule-checksheet-section">
            <div className="rule-checksheet-header">
              <span>FRM/PR/19 Check Items (9 Checks × 2 Pieces)</span>
              <small style={{ color: 'var(--slate-500)', fontSize: '11px', fontWeight: 600 }}>
                Shift First & Last Piece Inspection Log
              </small>
            </div>
            <div className="table-wrap" style={{ background: '#ffffff', borderRadius: '4px', border: '1px solid var(--slate-200)' }}>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '28%' }}>Check Item</th>
                    <th style={{ width: '12%' }}>Severity</th>
                    <th style={{ width: '15%' }}>First Piece</th>
                    <th style={{ width: '15%' }}>Last Piece</th>
                    <th>Operator Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {DEFAULT_CHECK_ITEMS.map((item) => {
                    const entry = checks[item.id] || { first_piece: 'OK', last_piece: 'OK', notes: '' }
                    return (
                      <tr key={item.id}>
                        <td><strong>{item.name}</strong></td>
                        <td>
                          <span
                            className={`rule-severity-tag rule-severity-tag--${item.severity.toLowerCase()}`}
                          >
                            {item.severity}
                          </span>
                        </td>
                        <td>
                          <select
                            value={entry.first_piece}
                            onChange={(e) =>
                              setChecks((prev) => ({
                                ...prev,
                                [item.id]: { ...entry, first_piece: e.target.value as CheckSheetItemState },
                              }))
                            }
                            className="rule-form-select"
                            style={{ height: '30px', fontSize: '10px' }}
                          >
                            <option value="OK">OK</option>
                            <option value="NG">NG</option>
                            <option value="CORRECTED">CORRECTED</option>
                          </select>
                        </td>
                        <td>
                          <select
                            value={entry.last_piece}
                            onChange={(e) =>
                              setChecks((prev) => ({
                                ...prev,
                                [item.id]: { ...entry, last_piece: e.target.value as CheckSheetItemState },
                              }))
                            }
                            className="rule-form-select"
                            style={{ height: '30px', fontSize: '10px' }}
                          >
                            <option value="OK">OK</option>
                            <option value="NG">NG</option>
                            <option value="CORRECTED">CORRECTED</option>
                          </select>
                        </td>
                        <td>
                          <input
                            type="text"
                            placeholder="Optional notes"
                            value={entry.notes || ''}
                            onChange={(e) =>
                              setChecks((prev) => ({
                                ...prev,
                                [item.id]: { ...entry, notes: e.target.value },
                              }))
                            }
                            className="rule-form-input"
                            style={{ height: '30px', fontSize: '11px' }}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 3. Filterable Rule Results Table */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">DETERMINISTIC QA VERIFICATION</p>
            <h2 style={{ fontSize: '18px', margin: 0 }}>
              Deterministic Rule Results ({filteredRules.length} of {verdict?.rule_results.length || 0})
            </h2>
          </div>

          {/* Filters Bar */}
          <div className="rule-filter-bar">
            <div className="rule-search-box">
              <Search size={14} color="var(--slate-500)" />
              <input
                type="text"
                placeholder="Search rule..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <select
              value={familyFilter}
              onChange={(e) => setFamilyFilter(e.target.value)}
              className="rule-filter-select"
            >
              <option value="all">All Families</option>
              <option value="msil_tolerances">MSIL Tolerances</option>
              <option value="taping_standard">BT45-02 Taping</option>
              <option value="visual_inspection_wi79">WI/PR/79 Visual</option>
              <option value="final_assembly_frm19">FRM/PR/19 Check Sheet</option>
              <option value="ptdb_yh200502">PTDB YH200502</option>
              <option value="pre_gates">Pre-Gates</option>
            </select>

            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="rule-filter-select"
            >
              <option value="all">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="MAJOR">MAJOR</option>
              <option value="MINOR">MINOR</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rule-filter-select"
            >
              <option value="all">All Statuses</option>
              <option value="PASS">PASS</option>
              <option value="FAIL">FAIL</option>
              <option value="REVIEW">REVIEW</option>
              <option value="NOT_EVALUATED">NOT_EVALUATED</option>
            </select>
          </div>
        </div>

        {/* Selected Rule Detail Card (Expanded view on selection) */}
        {activeSelectedRule && (
          <div className="rule-detail-card">
            <header>
              <div>
                <span className="eyebrow" style={{ color: 'var(--blue-600)' }}>SELECTED RULE SPECIFICATION</span>
                <h4>
                  {activeSelectedRule.rule_id} — {activeSelectedRule.name}
                </h4>
              </div>
              <button
                type="button"
                className="button button--ghost"
                style={{ minHeight: '26px', padding: '0 8px', fontSize: '10px' }}
                onClick={() => {
                  setLocalSelectedRule(null)
                  onSelectRule?.(null)
                }}
              >
                <X size={13} /> Close
              </button>
            </header>

            <div className="rule-detail-grid">
              <div className="rule-detail-stat">
                <span>Rule Family</span>
                <strong>{activeSelectedRule.family}</strong>
              </div>
              <div className="rule-detail-stat">
                <span>Status</span>
                <strong
                  className={`rule-status-badge rule-status-badge--${activeSelectedRule.status.toLowerCase().replace('_', '-')}`}
                >
                  {activeSelectedRule.status}
                </strong>
              </div>
              <div className="rule-detail-stat">
                <span>Severity</span>
                <strong
                  className={`rule-severity-tag rule-severity-tag--${activeSelectedRule.severity.toLowerCase()}`}
                >
                  {activeSelectedRule.severity}
                </strong>
              </div>
              <div className="rule-detail-stat">
                <span>Nominal Tolerance</span>
                <strong>{activeSelectedRule.tolerance !== null && activeSelectedRule.tolerance !== undefined ? String(activeSelectedRule.tolerance) : '—'}</strong>
              </div>
              <div className="rule-detail-stat">
                <span>Expected Value</span>
                <strong>{activeSelectedRule.expected !== null && activeSelectedRule.expected !== undefined ? `${activeSelectedRule.expected} mm` : '—'}</strong>
              </div>
              <div className="rule-detail-stat">
                <span>Actual Measured</span>
                <strong>{activeSelectedRule.actual !== null && activeSelectedRule.actual !== undefined ? `${activeSelectedRule.actual} mm` : '—'}</strong>
              </div>
              <div className="rule-detail-stat">
                <span>Deviation</span>
                <strong>{activeSelectedRule.deviation !== null && activeSelectedRule.deviation !== undefined ? `${typeof activeSelectedRule.deviation === 'number' && activeSelectedRule.deviation > 0 ? '+' : ''}${activeSelectedRule.deviation} mm` : '—'}</strong>
              </div>
              <div className="rule-detail-stat">
                <span>Source Standard</span>
                <strong>{activeSelectedRule.source_doc}</strong>
              </div>
            </div>

            <div className="rule-detail-reason">
              <strong>Evaluation Result: </strong>{activeSelectedRule.reason}
              {activeSelectedRule.reaction_plan && (
                <div style={{ marginTop: '6px', color: 'var(--red-600)', fontWeight: 600 }}>
                  Reaction Plan: {activeSelectedRule.reaction_plan}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Table */}
        <div className="rule-table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: '110px' }}>Status</th>
                <th style={{ width: '140px' }}>Rule ID</th>
                <th style={{ width: '140px' }}>Family</th>
                <th style={{ width: '90px' }}>Severity</th>
                <th style={{ width: '100px' }}>Expected</th>
                <th style={{ width: '110px' }}>Actual / Dev</th>
                <th>Reason / Standard Compliance</th>
              </tr>
            </thead>
            <tbody>
              {filteredRules.map((rule) => {
                const isSelected = activeSelectedRule?.rule_id === rule.rule_id
                const isFail = rule.status === 'FAIL'
                const isReview = rule.status === 'REVIEW'

                return (
                  <tr
                    key={rule.rule_id}
                    onClick={() => handleRowClick(rule)}
                    className={`rule-table-row ${
                      isSelected
                        ? 'rule-table-row--selected'
                        : isFail
                        ? 'rule-table-row--fail'
                        : isReview
                        ? 'rule-table-row--review'
                        : ''
                    }`}
                  >
                    <td>
                      <span
                        className={`rule-status-badge rule-status-badge--${rule.status.toLowerCase().replace('_', '-')}`}
                      >
                        {rule.status}
                      </span>
                    </td>
                    <td>
                      <strong style={{ fontFamily: 'Consolas, monospace', fontSize: '11px', color: 'var(--navy-900)' }}>
                        {rule.rule_id}
                      </strong>
                    </td>
                    <td>
                      <span style={{ color: 'var(--slate-500)', fontSize: '11px' }}>
                        {rule.family}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`rule-severity-tag rule-severity-tag--${rule.severity.toLowerCase()}`}
                      >
                        {rule.severity}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontFamily: 'Consolas, monospace', fontSize: '11px', color: 'var(--slate-700)' }}>
                        {rule.expected !== null && rule.expected !== undefined ? String(rule.expected) : '—'}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontFamily: 'Consolas, monospace', fontSize: '11px', fontWeight: 600, color: 'var(--navy-900)' }}>
                        {rule.actual !== null && rule.actual !== undefined ? String(rule.actual) : '—'}
                      </span>
                      {rule.deviation !== null && rule.deviation !== undefined && (
                        <span style={{ marginLeft: '4px', color: 'var(--slate-500)', fontSize: '10px' }}>
                          ({typeof rule.deviation === 'number' && rule.deviation > 0 ? '+' : ''}{String(rule.deviation)})
                        </span>
                      )}
                    </td>
                    <td>
                      <span style={{ color: 'var(--slate-700)', fontSize: '11px', lineHeight: 1.4 }}>
                        {rule.reason}
                      </span>
                    </td>
                  </tr>
                )
              })}
              {filteredRules.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: '36px', textAlign: 'center', color: 'var(--slate-500)' }}>
                    No rules match the current filters. Click "Evaluate Rules" above to generate a deterministic evaluation.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

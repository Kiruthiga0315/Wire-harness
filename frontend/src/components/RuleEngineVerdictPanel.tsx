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
} from 'lucide-react'
import { useState } from 'react'
import type {
  BranchTapingInput,
  BranchType,
  CheckSheetEntry,
  CheckSheetItemState,
  FinalAssemblyCheckSheetInput,
  HarnessVerdict,
  OperatorInput,
  RuleResult,
  RuleSeverity,
  RuleStatus,
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
  const [tapingList, setTapingList] = useState<BranchTapingInput[]>([
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

  return (
    <div className={`space-y-4 ${className}`}>
      {/* 1. Large Verdict Banner */}
      <div
        className={`rounded-xl border p-5 shadow-sm transition-all ${
          isAccept
            ? 'border-emerald-600 bg-emerald-600 text-white'
            : isReject
            ? 'border-rose-600 bg-rose-600 text-white'
            : 'border-amber-500 bg-amber-500 text-slate-950'
        }`}
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-black/15 p-3">
              {isAccept && <CheckCircle2 className="h-9 w-9 text-white" />}
              {isReject && <CircleX className="h-9 w-9 text-white" />}
              {isHold && <Clock3 className="h-9 w-9 text-slate-950" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider opacity-85">
                  Final Quality Verdict · {verdict?.variant || variant}
                </span>
                <span className="rounded bg-black/20 px-2 py-0.5 text-[11px] font-mono font-medium">
                  Pack v{verdict?.rule_pack_version || '1.0.0'}
                </span>
              </div>
              <h2 className="text-2xl font-black tracking-tight">
                {isAccept && 'ACCEPT — CONFORMING HARNESS'}
                {isReject && 'REJECT — NON-CONFORMANCE DETECTED'}
                {isHold && 'HOLD — PENDING QUALITY INSPECTION / ATTESTATION'}
              </h2>
              <p className="mt-0.5 text-xs font-medium opacity-90">
                Provenance: {verdict?.calibration_provenance || 'uncalibrated'} ·{' '}
                {verdict ? `${verdict.summary.PASS} PASS / ${verdict.summary.FAIL} FAIL / ${verdict.summary.REVIEW} REVIEW / ${verdict.summary.NOT_EVALUATED} HELD` : 'No evaluation executed yet'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleRunEvaluation}
              disabled={evaluating}
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold shadow-sm transition ${
                isAccept || isReject
                  ? 'bg-white text-slate-900 hover:bg-slate-100'
                  : 'bg-slate-900 text-white hover:bg-slate-800'
              } disabled:opacity-50`}
            >
              <Play className="h-4 w-4" />
              {evaluating ? 'Evaluating...' : 'Evaluate Rules'}
            </button>

            {verdict && (
              <>
                <button
                  type="button"
                  onClick={() => downloadVerdictPdf(verdict.verdict_id)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/30 bg-black/10 px-3 py-2 text-xs font-semibold backdrop-blur hover:bg-black/20"
                >
                  <Download className="h-3.5 w-3.5" />
                  PDF Cert
                </button>
                <button
                  type="button"
                  onClick={() => downloadVerdictCsv(verdict.verdict_id)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/30 bg-black/10 px-3 py-2 text-xs font-semibold backdrop-blur hover:bg-black/20"
                >
                  <FileChartColumn className="h-3.5 w-3.5" />
                  CSV
                </button>
              </>
            )}

            <button
              type="button"
              onClick={() => setShowOperatorForm(!showOperatorForm)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/30 bg-black/10 px-3 py-2 text-xs font-semibold hover:bg-black/20"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {showOperatorForm ? 'Hide Operator Inputs' : 'Operator Inputs'}
            </button>
          </div>
        </div>

        {/* Reaction Plan Alert on REJECT or HOLD */}
        {(isReject || isHold) && verdict?.reaction_plan && (
          <div className="mt-4 rounded-lg bg-black/20 p-3 text-xs font-medium">
            <div className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-white" />
              <div>
                <span className="font-bold uppercase tracking-wider text-white">Factory Reaction Plan:</span>
                <p className="mt-0.5 text-white/95">{verdict.reaction_plan}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {evalError && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
          <b>Evaluation Error:</b> {evalError}
        </div>
      )}

      {/* 2. Operator Inputs Drawer / Form */}
      {showOperatorForm && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5 text-sky-600" />
              <h3 className="font-bold text-slate-900 dark:text-slate-100">
                Operator Inspection Inputs (FRM/PR/19 rev 10 & BT45-02)
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setShowOperatorForm(false)}
              className="text-xs font-medium text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
              Close
            </button>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Shift</label>
              <select
                value={shift}
                onChange={(e) => setShift(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              >
                <option value="A">Shift A (Morning)</option>
                <option value="B">Shift B (Evening)</option>
                <option value="C">Shift C (Night)</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Associate Name</label>
              <input
                type="text"
                value={associateName}
                onChange={(e) => setAssociateName(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Employee E-Code</label>
              <input
                type="text"
                value={eCode}
                onChange={(e) => setECode(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Master Sample Status</label>
              <select
                value={masterSampleStatus}
                onChange={(e) => setMasterSampleStatus(e.target.value as 'OK' | 'NG' | 'EXPIRED')}
                className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              >
                <option value="OK">OK (Validated Active)</option>
                <option value="NG">NG (Non-conforming)</option>
                <option value="EXPIRED">EXPIRED (Shift Expired)</option>
              </select>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Total Production Qty</label>
              <input
                type="number"
                value={totalQty}
                onChange={(e) => setTotalQty(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Label Serial From</label>
              <input
                type="number"
                value={serialFrom}
                onChange={(e) => setSerialFrom(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Label Serial To</label>
              <input
                type="number"
                value={serialTo}
                onChange={(e) => setSerialTo(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold uppercase text-slate-500">Labels Scrapped</label>
              <input
                type="number"
                value={serialScrapped}
                onChange={(e) => setSerialScrapped(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>
          </div>

          {/* 9 Check Sheet Items */}
          <div className="mt-5">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              FRM/PR/19 Check Items (9 Checks x 2 Pieces)
            </h4>
            <div className="mt-2 divide-y divide-slate-100 overflow-x-auto rounded border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
                  <tr>
                    <th className="p-2.5">Check Item</th>
                    <th className="p-2.5">Severity</th>
                    <th className="p-2.5">First Piece</th>
                    <th className="p-2.5">Last Piece</th>
                    <th className="p-2.5">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {DEFAULT_CHECK_ITEMS.map((item) => {
                    const entry = checks[item.id] || { first_piece: 'OK', last_piece: 'OK', notes: '' }
                    return (
                      <tr key={item.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                        <td className="p-2.5 font-medium text-slate-900 dark:text-slate-100">{item.name}</td>
                        <td className="p-2.5">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                              item.severity === 'CRITICAL'
                                ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                            }`}
                          >
                            {item.severity}
                          </span>
                        </td>
                        <td className="p-2.5">
                          <select
                            value={entry.first_piece}
                            onChange={(e) =>
                              setChecks((prev) => ({
                                ...prev,
                                [item.id]: { ...entry, first_piece: e.target.value as CheckSheetItemState },
                              }))
                            }
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-800"
                          >
                            <option value="OK">OK</option>
                            <option value="NG">NG</option>
                            <option value="CORRECTED">CORRECTED</option>
                          </select>
                        </td>
                        <td className="p-2.5">
                          <select
                            value={entry.last_piece}
                            onChange={(e) =>
                              setChecks((prev) => ({
                                ...prev,
                                [item.id]: { ...entry, last_piece: e.target.value as CheckSheetItemState },
                              }))
                            }
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-800"
                          >
                            <option value="OK">OK</option>
                            <option value="NG">NG</option>
                            <option value="CORRECTED">CORRECTED</option>
                          </select>
                        </td>
                        <td className="p-2.5">
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
                            className="w-full rounded border border-slate-300 px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-800"
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
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-slate-500" />
            <h3 className="font-bold text-slate-900 dark:text-slate-100">
              Deterministic Rule Results ({filteredRules.length} of {verdict?.rule_results.length || 0})
            </h3>
          </div>

          {/* Filters Bar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search rule..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-3 text-xs dark:border-slate-700 dark:bg-slate-800"
              />
            </div>

            <select
              value={familyFilter}
              onChange={(e) => setFamilyFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
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
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
            >
              <option value="all">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="MAJOR">MAJOR</option>
              <option value="MINOR">MINOR</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-800"
            >
              <option value="all">All Statuses</option>
              <option value="PASS">PASS</option>
              <option value="FAIL">FAIL</option>
              <option value="REVIEW">REVIEW</option>
              <option value="NOT_EVALUATED">NOT_EVALUATED</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
              <tr>
                <th className="p-3">Status</th>
                <th className="p-3">Rule ID</th>
                <th className="p-3">Family</th>
                <th className="p-3">Severity</th>
                <th className="p-3">Expected</th>
                <th className="p-3">Actual / Dev</th>
                <th className="p-3">Reason / Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filteredRules.map((rule) => {
                const isSelected = selectedRuleId === rule.rule_id
                const isFail = rule.status === 'FAIL'
                const isReview = rule.status === 'REVIEW'
                const isPass = rule.status === 'PASS'

                return (
                  <tr
                    key={rule.rule_id}
                    onClick={() => onSelectRule?.(rule)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-sky-50 dark:bg-sky-950/40'
                        : isFail
                        ? 'bg-rose-50/40 hover:bg-rose-50/70 dark:bg-rose-950/20'
                        : isReview
                        ? 'bg-amber-50/40 hover:bg-amber-50/70 dark:bg-amber-950/20'
                        : 'hover:bg-slate-50/80 dark:hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="p-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold ${
                          isPass
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : isFail
                            ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                            : isReview
                            ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {rule.status}
                      </span>
                    </td>
                    <td className="p-3 font-mono font-bold text-slate-900 dark:text-slate-100">
                      {rule.rule_id}
                    </td>
                    <td className="p-3 text-slate-600 dark:text-slate-300">{rule.family}</td>
                    <td className="p-3">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          rule.severity === 'CRITICAL'
                            ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                            : rule.severity === 'MAJOR'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                        }`}
                      >
                        {rule.severity}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                      {rule.expected !== null && rule.expected !== undefined ? String(rule.expected) : '—'}
                    </td>
                    <td className="p-3 font-mono text-[11px]">
                      {rule.actual !== null && rule.actual !== undefined ? String(rule.actual) : '—'}
                      {rule.deviation !== null && rule.deviation !== undefined && (
                        <span className="ml-1 text-slate-400">({String(rule.deviation)})</span>
                      )}
                    </td>
                    <td className="p-3 text-slate-700 dark:text-slate-300">
                      <p className="line-clamp-2">{rule.reason}</p>
                    </td>
                  </tr>
                )
              })}
              {filteredRules.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-400">
                    No rules match current filters.
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

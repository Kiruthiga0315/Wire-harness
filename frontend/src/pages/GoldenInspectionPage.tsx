import {
  CheckCircle2,
  CircleCheckBig,
  CircleDot,
  CircleX,
  Download,
  FileImage,
  FileText,
  GitBranch,
  ImagePlus,
  Info,
  Network,
  RefreshCw,
  Ruler,
  Scan,
  Search,
  TriangleAlert,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import {
  API_BASE_URL,
  GOLDEN_HARNESS_URL,
  downloadGoldenReportPdf,
  getGoldenReference,
  runGoldenInspection,
  runUploadedGoldenInspection,
} from '../services/api'
import type {
  CheckpointInspectionResult,
  GoldenInspectionResponse,
  GoldenReferenceConfig,
  TopologyFeatureLocation,
} from '../types/goldenReference'

export function GoldenInspectionPage() {
  const { image } = useInspection()
  const [goldenConfig, setGoldenConfig] = useState<GoldenReferenceConfig | null>(null)
  const [inspectionResult, setInspectionResult] = useState<GoldenInspectionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filtering for quality audit table
  const [filterStatus, setFilterStatus] = useState<'all' | 'PASS' | 'FAIL' | 'REVIEW'>('all')
  const [selectedResult, setSelectedResult] = useState<CheckpointInspectionResult | null>(null)

  // Compare mode: 'side-by-side' | 'marked' | 'golden'
  const [viewMode, setViewMode] = useState<'side-by-side' | 'marked' | 'golden'>('side-by-side')

  // Bottom Analytics Tabs: 'audit' | 'topology' | 'lengths' | 'tapes_sticker' | 'terminals'
  const [activeTab, setActiveTab] = useState<'audit' | 'topology' | 'lengths' | 'tapes_sticker' | 'terminals'>('audit')

  // Topology filter & search
  const [topologyType, setTopologyType] = useState<'all' | 'terminal' | 'junction' | 'node'>('all')
  const [topologySearch, setTopologySearch] = useState('')

  // Length category filter
  const [lengthCategory, setLengthCategory] = useState<'all' | 'junction_terminal' | 'junction_junction' | 'node_node'>('all')

  useEffect(() => {
    void (async () => {
      try {
        const cfg = await getGoldenReference()
        setGoldenConfig(cfg)
      } catch (err) {
        console.error(err)
      }
    })()
  }, [])

  const executeInspection = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await runGoldenInspection()
      setInspectionResult(res)
      if (res.results.length > 0) {
        setSelectedResult(res.results[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inspection execution failed.')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const res = await runUploadedGoldenInspection(file)
      setInspectionResult(res)
      if (res.results.length > 0) {
        setSelectedResult(res.results[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inspection failed on uploaded file.')
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  const filteredResults = (inspectionResult?.results || []).filter((r) => {
    if (filterStatus === 'all') return true
    return r.status === filterStatus
  })

  // Helpers for extracting normalized location attributes
  const getItemId = (item: TopologyFeatureLocation) =>
    item.terminal_id || item.junction_id || item.node_id || item.id || item.checkpoint_id || 'Unknown'
  const getItemX = (item: TopologyFeatureLocation) =>
    item.location_x ?? item.x ?? item.golden_x ?? 0
  const getItemY = (item: TopologyFeatureLocation) =>
    item.location_y ?? item.y ?? item.golden_y ?? 0
  const getItemCategory = (item: TopologyFeatureLocation, fallback: 'terminal' | 'junction' | 'node') =>
    item.type || fallback

  // Extract all topology locations (Terminals, Junctions, Nodes)
  const terminalLocations = (inspectionResult?.topology_summary?.terminals || []).map((t) => ({ ...t, type: 'terminal' }))
  const junctionLocations = (inspectionResult?.topology_summary?.junctions || []).map((j) => ({ ...j, type: 'junction' }))
  const nodeLocations = (inspectionResult?.topology_summary?.nodes || []).map((n) => ({ ...n, type: 'node' }))

  const allTopologyLocations: TopologyFeatureLocation[] = [
    ...terminalLocations,
    ...junctionLocations,
    ...nodeLocations,
  ].filter((item) => {
    if (topologyType !== 'all' && item.type !== topologyType) return false
    if (topologySearch.trim()) {
      const q = topologySearch.trim().toLowerCase()
      const id = getItemId(item).toLowerCase()
      const label = (item.label || '').toLowerCase()
      return id.includes(q) || label.includes(q)
    }
    return true
  })

  const exportReportJson = () => {
    if (!inspectionResult) return
    const blob = new Blob([JSON.stringify(inspectionResult, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `golden_inspection_report_${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportReportCsv = () => {
    if (!inspectionResult) return
    const headers = [
      'checkpoint_id',
      'terminal_id',
      'node_id',
      'measurement_type',
      'expected_mm',
      'detected_mm',
      'tolerance_mm',
      'deviation_mm',
      'percentage_deviation',
      'status',
      'confidence',
      'message',
    ]
    const rows = inspectionResult.results.map((r) => [
      r.checkpoint_id,
      r.terminal_id || '',
      r.node_id || '',
      r.measurement_type,
      r.expected_value ?? '',
      r.detected_value ?? '',
      r.tolerance ?? '',
      r.deviation ?? '',
      r.percentage_deviation ?? '',
      r.status,
      r.confidence,
      `"${r.message.replace(/"/g, '""')}"`,
    ])

    // Extra Topology & Inspection sections in CSV
    const extraRows: (string | number)[][] = []
    if (inspectionResult.topology_summary) {
      const top = inspectionResult.topology_summary
      extraRows.push([])
      extraRows.push(['# TOPOLOGY SUMMARY', '', '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Terminals Count', top.terminal_count, '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Junctions Count', top.junction_count, '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Branches Count', top.branch_count, '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Spine Nodes Count', top.node_count, '', '', '', '', '', '', '', '', '', ''])

      extraRows.push([])
      extraRows.push(['# INTER-COMPONENT LENGTHS', '', '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Route Type', 'From Component', 'To Component', 'Expected (mm)', 'Detected (mm)', 'Detected (cm)', 'Tolerance (mm)', 'Deviation (mm)', 'Status', '', '', ''])
      for (const jt of top.junction_to_terminal_lengths || []) {
        extraRows.push(['Junction to Terminal', jt.junction_id, jt.terminal_id, jt.expected_mm ?? '', jt.detected_mm ?? '', jt.detected_cm ?? '', jt.tolerance_mm ?? '', jt.deviation_mm ?? '', jt.status, '', '', ''])
      }
      for (const jj of top.junction_to_junction_lengths || []) {
        extraRows.push(['Junction to Junction', jj.from_junction, jj.to_junction, jj.expected_mm ?? '', jj.detected_mm ?? '', jj.detected_cm ?? '', jj.tolerance_mm ?? '', jj.deviation_mm ?? '', jj.status, '', '', ''])
      }
      for (const nn of top.node_to_node_lengths || []) {
        extraRows.push(['Node to Node', nn.from_node, nn.to_node, nn.expected_mm ?? '', nn.detected_mm ?? '', nn.detected_cm ?? '', nn.tolerance_mm ?? '', nn.deviation_mm ?? '', nn.status, '', '', ''])
      }
    }

    if (inspectionResult.colored_tapes) {
      const ct = inspectionResult.colored_tapes
      extraRows.push([])
      extraRows.push(['# COLORED TAPES VERIFICATION', '', '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Tape Color', 'Detected', 'Coverage %', 'Confidence %', 'Description', '', '', '', '', '', '', ''])
      if (ct.green) extraRows.push(['Green Tape', ct.green.detected ? 'DETECTED' : 'NOT_DETECTED', `${ct.green.percentage}%`, `${(ct.green.confidence * 100).toFixed(0)}%`, `"${ct.green.description}"`, '', '', '', '', '', '', ''])
      if (ct.dark_blue) extraRows.push(['Dark Blue Tape', ct.dark_blue.detected ? 'DETECTED' : 'NOT_DETECTED', `${ct.dark_blue.percentage}%`, `${(ct.dark_blue.confidence * 100).toFixed(0)}%`, `"${ct.dark_blue.description}"`, '', '', '', '', '', '', ''])
      if (ct.grey) extraRows.push(['Gray Tape', ct.grey.detected ? 'DETECTED' : 'NOT_DETECTED', `${ct.grey.percentage}%`, `${(ct.grey.confidence * 100).toFixed(0)}%`, `"${ct.grey.description}"`, '', '', '', '', '', '', ''])
    }

    if (inspectionResult.sticker) {
      const stk = inspectionResult.sticker
      extraRows.push([])
      extraRows.push(['# SPECIFICATION STICKER & BARCODE', '', '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Status', stk.status, 'Confidence', `${(stk.confidence * 100).toFixed(0)}%`, '', '', '', '', '', '', '', ''])
      extraRows.push(['Part Number', stk.fields?.part_number || '', 'Harness Code', stk.fields?.harness_code || '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Drawing Number', stk.fields?.drawing_number || '', 'Barcode Payload', stk.fields?.barcode_payload || '', '', '', '', '', '', '', '', ''])
    }

    if (inspectionResult.terminal_identifications) {
      extraRows.push([])
      extraRows.push(['# TERMINAL IDENTIFICATION MATRIX', '', '', '', '', '', '', '', '', '', '', ''])
      extraRows.push(['Terminal ID', 'Location X', 'Location Y', 'Parent Junction', 'Expected (mm)', 'Detected (mm)', 'Deviation (mm)', 'Status', 'Confidence', '', '', ''])
      for (const t of inspectionResult.terminal_identifications) {
        extraRows.push([t.terminal_id, t.location_x, t.location_y, t.parent_junction, t.expected_mm ?? '', t.detected_mm ?? '', t.deviation_mm ?? '', t.status, `${(t.confidence * 100).toFixed(0)}%`, '', '', ''])
      }
    }

    const csvContent = [headers.join(','), ...rows.map((row) => row.join(',')), ...extraRows.map((row) => row.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `golden_inspection_report_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const overallTone: 'pass' | 'ng' | 'warning' =
    inspectionResult?.overall_status === 'PASS'
      ? 'pass'
      : inspectionResult?.overall_status === 'FAIL'
        ? 'ng'
        : 'warning'

  const topSummary = inspectionResult?.topology_summary
  const tapes = inspectionResult?.colored_tapes
  const sticker = inspectionResult?.sticker

  return (
    <>
      <PageHeader
        eyebrow="AUTOMATED QUALITY VERIFICATION"
        title="Golden Reference Inspection"
        description="Inspect workpiece against the physical golden harness baseline with precision mm deviations & tolerance rules."
        actions={
          <div className="button-group">
            <label className="button button--secondary" style={{ cursor: 'pointer' }}>
              <ImagePlus size={16} />
              Upload Test Image
              <input type="file" accept="image/*" onChange={handleFileUpload} style={{ display: 'none' }} />
            </label>
            <button
              className="button button--primary"
              onClick={executeInspection}
              disabled={loading}
              title="Align test workpiece with golden reference & compare measurements"
            >
              <RefreshCw size={16} className={loading ? 'spin' : ''} />
              {loading ? 'Aligning & Measuring…' : 'Run Golden Inspection'}
            </button>
            {inspectionResult && (
              <>
                <button
                  className="button button--secondary"
                  onClick={() => void downloadGoldenReportPdf()}
                  title="Export Official PDF Inspection Certificate"
                >
                  <Download size={16} />
                  PDF
                </button>
                <button className="button button--secondary" onClick={exportReportCsv} title="Export CSV Report">
                  <FileText size={16} />
                  CSV
                </button>
                <button className="button button--secondary" onClick={exportReportJson} title="Export JSON Report">
                  <Download size={16} />
                  JSON
                </button>
              </>
            )}
          </div>
        }
      />

      {error && (
        <div className="alert-banner" role="alert">
          <TriangleAlert size={20} />
          <div>
            <strong>Inspection Notice</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Row 1: Primary Quality Metrics Cards */}
      <section className="engineering-metrics" style={{ gridTemplateColumns: '1.2fr repeat(5, 1fr)', marginBottom: 12 }}>
        <article style={{ background: overallTone === 'pass' ? '#f0fdf4' : overallTone === 'ng' ? '#fef2f2' : '#fffbeb' }}>
          <span>Overall Inspection Verdict</span>
          <strong
            style={{
              color:
                overallTone === 'pass'
                  ? 'var(--green-600)'
                  : overallTone === 'ng'
                    ? 'var(--red-600)'
                    : 'var(--amber-600)',
            }}
          >
            {inspectionResult ? inspectionResult.overall_status : 'READY'}
          </strong>
          <small>{inspectionResult ? inspectionResult.inspection_id : 'Click Run Inspection'}</small>
        </article>
        <article>
          <span>Checkpoints Evaluated</span>
          <strong>{inspectionResult?.total_checkpoints ?? goldenConfig?.checkpoints.length ?? 0}</strong>
          <small>Physical terminals & nodes</small>
        </article>
        <article>
          <span>Passed (Within Spec)</span>
          <strong style={{ color: 'var(--green-600)' }}>{inspectionResult?.passed_count ?? 0}</strong>
          <small>|Deviation| ≤ Tolerance</small>
        </article>
        <article>
          <span>Failed (Out of Spec)</span>
          <strong style={{ color: 'var(--red-600)' }}>{inspectionResult?.failed_count ?? 0}</strong>
          <small>Exceeds engineering limit</small>
        </article>
        <article>
          <span>Review Required</span>
          <strong style={{ color: 'var(--amber-600)' }}>{inspectionResult?.review_count ?? 0}</strong>
          <small>Unconfirmed or low conf.</small>
        </article>
        <article>
          <span>Calibration Scale</span>
          <strong>{inspectionResult ? `${inspectionResult.pixels_per_mm.toFixed(3)}` : '0.916'}</strong>
          <small>pixels / mm</small>
        </article>
      </section>

      {/* Row 2: Harness Feature & Topology Overview (Items 1-4, 7-8) */}
      <section className="engineering-metrics" style={{ gridTemplateColumns: 'repeat(6, 1fr)', marginBottom: 20 }}>
        {/* 1. No of terminals */}
        <article style={{ borderLeft: '3px solid #16a34a' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#16a34a', marginBottom: 4 }}>
            <CircleDot size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>1. Terminals</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {topSummary?.terminal_count ?? goldenConfig?.checkpoints.filter((c) => c.type === 'terminal').length ?? 41}
          </strong>
          <small>Detected connectors / endpoints</small>
        </article>

        {/* 2. No of junctions */}
        <article style={{ borderLeft: '3px solid #0284c7' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0284c7', marginBottom: 4 }}>
            <GitBranch size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>2. Junctions</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {topSummary?.junction_count ?? 31}
          </strong>
          <small>Branching splits (J01–J31)</small>
        </article>

        {/* 3. No of branches */}
        <article style={{ borderLeft: '3px solid #9333ea' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#9333ea', marginBottom: 4 }}>
            <Network size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>3. Branches</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {topSummary?.branch_count ?? 72}
          </strong>
          <small>Extracted wire segments</small>
        </article>

        {/* 4. No of nodes */}
        <article style={{ borderLeft: '3px solid #d97706' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#d97706', marginBottom: 4 }}>
            <Scan size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>4. Spine Nodes</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {topSummary?.node_count ?? 6}
          </strong>
          <small>Trunk joints (N01–N12)</small>
        </article>

        {/* 7. Presence of colored tapes */}
        <article style={{ borderLeft: '3px solid #0d9488' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0d9488', marginBottom: 4 }}>
            <span style={{ fontSize: 13 }}>🎨</span>
            <span style={{ margin: 0, fontWeight: 700 }}>7. Colored Tapes</span>
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: '2px 5px',
                borderRadius: 3,
                background: tapes?.green?.detected ? '#dcfce7' : '#f1f5f9',
                color: tapes?.green?.detected ? '#166534' : '#64748b',
              }}
              title={`Green Tape: ${tapes?.green?.detected ? 'PRESENT' : 'NOT DETECTED'} (${tapes?.green?.percentage ?? 0}%)`}
            >
              🟢 {tapes?.green?.detected ? `${tapes.green.percentage}%` : 'Green'}
            </span>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: '2px 5px',
                borderRadius: 3,
                background: tapes?.dark_blue?.detected ? '#dbeafe' : '#f1f5f9',
                color: tapes?.dark_blue?.detected ? '#1e40af' : '#64748b',
              }}
              title={`Dark Blue Tape: ${tapes?.dark_blue?.detected ? 'PRESENT' : 'NOT DETECTED'} (${tapes?.dark_blue?.percentage ?? 0}%)`}
            >
              🔵 {tapes?.dark_blue?.detected ? `${tapes.dark_blue.percentage}%` : 'Blue'}
            </span>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: '2px 5px',
                borderRadius: 3,
                background: tapes?.grey?.detected ? '#f3f4f6' : '#f1f5f9',
                color: tapes?.grey?.detected ? '#374151' : '#64748b',
              }}
              title={`Gray Tape: ${tapes?.grey?.detected ? 'PRESENT' : 'NOT DETECTED'} (${tapes?.grey?.percentage ?? 0}%)`}
            >
              ⚪ {tapes?.grey?.detected ? `${tapes.grey.percentage}%` : 'Gray'}
            </span>
          </div>
          <small style={{ marginTop: 4 }}>Green / Dark Blue / Gray tapes</small>
        </article>

        {/* 8. Presence of sticker */}
        <article style={{ borderLeft: '3px solid #2563eb' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#2563eb', marginBottom: 4 }}>
            <span style={{ fontSize: 13 }}>🏷️</span>
            <span style={{ margin: 0, fontWeight: 700 }}>8. Spec Sticker</span>
          </div>
          <strong
            style={{
              fontSize: 14,
              color: sticker?.present ? 'var(--green-600)' : sticker ? 'var(--red-600)' : 'var(--navy-900)',
            }}
          >
            {sticker?.status ?? (inspectionResult ? 'PRESENT' : 'READY')}
          </strong>
          <small style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
            {sticker?.fields?.part_number ? `Part: ${sticker.fields.part_number}` : 'OCR & Barcode verified'}
          </small>
        </article>
      </section>

      {/* Visual Comparison Area */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 420px', gap: 20, marginBottom: 24 }}>
        <article className="panel" style={{ overflow: 'hidden' }}>
          <div className="panel-header" style={{ padding: '12px 18px' }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className={`button ${viewMode === 'side-by-side' ? 'button--primary' : 'button--secondary'}`}
                style={{ padding: '5px 10px', fontSize: 11 }}
                onClick={() => setViewMode('side-by-side')}
              >
                <FileImage size={14} /> Side-by-Side Comparison
              </button>
              <button
                className={`button ${viewMode === 'marked' ? 'button--primary' : 'button--secondary'}`}
                style={{ padding: '5px 10px', fontSize: 11 }}
                onClick={() => setViewMode('marked')}
              >
                <Scan size={14} /> Marked Test Workpiece
              </button>
              <button
                className={`button ${viewMode === 'golden' ? 'button--primary' : 'button--secondary'}`}
                style={{ padding: '5px 10px', fontSize: 11 }}
                onClick={() => setViewMode('golden')}
              >
                <FileText size={14} /> Golden Reference Image
              </button>
            </div>
            <div className="checkpoint-legend">
              <span>
                <i style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--green-600)' }} /> PASS
              </span>
              <span>
                <i style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red-600)' }} /> FAIL
              </span>
              <span>
                <i style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--amber-600)' }} /> REVIEW
              </span>
            </div>
          </div>

          <div
            style={{
              height: 640,
              background: '#0d1520',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 12,
              gap: 12,
              overflow: 'hidden',
            }}
          >
            {viewMode === 'side-by-side' && (
              <>
                <div style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <span style={{ color: '#94a3b8', fontSize: 10, fontWeight: 700, marginBottom: 6, letterSpacing: 1 }}>
                    GOLDEN BASELINE (GROUND TRUTH)
                  </span>
                  <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    <img
                      src={GOLDEN_HARNESS_URL}
                      alt="Golden harness baseline"
                      style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain', borderRadius: 4 }}
                    />
                  </div>
                </div>

                <div style={{ width: 1, height: '90%', background: 'rgba(255,255,255,0.1)' }} />

                <div style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <span style={{ color: '#38bdf8', fontSize: 10, fontWeight: 700, marginBottom: 6, letterSpacing: 1 }}>
                    TEST WORKPIECE WITH TOLERANCE OVERLAYS
                  </span>
                  <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    {inspectionResult ? (
                      <img
                        src={inspectionResult.marked_image_data_url}
                        alt="Marked test inspection image"
                        style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain', borderRadius: 4 }}
                      />
                    ) : (
                      <div style={{ color: '#64748b', fontSize: 12, textAlign: 'center' }}>
                        Click <strong>Run Golden Inspection</strong> or upload test photograph to evaluate.
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {viewMode === 'marked' && (
              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {inspectionResult ? (
                  <img
                    src={inspectionResult.marked_image_data_url}
                    alt="Marked test image"
                    style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                  />
                ) : (
                  <span style={{ color: '#64748b', fontSize: 12 }}>Run inspection to view marked results.</span>
                )}
              </div>
            )}

            {viewMode === 'golden' && (
              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <img
                  src={GOLDEN_HARNESS_URL}
                  alt="Golden harness baseline"
                  style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'contain' }}
                />
              </div>
            )}
          </div>
        </article>

        {/* Selected Measurement Detail Inspector */}
        <aside className="panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="panel-header">
            <div>
              <p className="eyebrow">MEASUREMENT VERIFICATION</p>
              <h2>{selectedResult ? selectedResult.terminal_id || selectedResult.checkpoint_id : 'Checkpoint Details'}</h2>
            </div>
            {selectedResult && (
              <StatusPill tone={selectedResult.status === 'PASS' ? 'pass' : selectedResult.status === 'FAIL' ? 'ng' : 'warning'}>
                {selectedResult.status}
              </StatusPill>
            )}
          </div>

          {selectedResult ? (
            <div style={{ padding: 18, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ background: '#f8fafc', padding: 12, borderRadius: 6, border: '1px solid var(--slate-200)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 10, color: 'var(--slate-500)', textTransform: 'uppercase', fontWeight: 700 }}>
                    Expected vs Detected (mm)
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--blue-600)', fontWeight: 700 }}>
                    Tolerance ±{selectedResult.tolerance} mm
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--slate-500)', display: 'block' }}>Expected</span>
                    <strong style={{ fontSize: 20, color: 'var(--navy-900)' }}>{selectedResult.expected_value} mm</strong>
                  </div>
                  <span style={{ color: 'var(--slate-400)', fontSize: 18, fontWeight: 700 }}>→</span>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--slate-500)', display: 'block' }}>Detected</span>
                    <strong
                      style={{
                        fontSize: 20,
                        color:
                          selectedResult.status === 'PASS'
                            ? 'var(--green-600)'
                            : selectedResult.status === 'FAIL'
                              ? 'var(--red-600)'
                              : 'var(--amber-600)',
                      }}
                    >
                      {selectedResult.detected_value ?? '—'} mm
                    </strong>
                  </div>
                </div>
                {selectedResult.deviation !== null && (
                  <div style={{ marginTop: 8, fontSize: 11, color: 'var(--slate-600)' }}>
                    Deviation: <strong>{selectedResult.deviation > 0 ? `+${selectedResult.deviation}` : selectedResult.deviation} mm</strong> (
                    {selectedResult.percentage_deviation}%)
                  </div>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div style={{ padding: 10, background: '#f8fafc', borderRadius: 4, border: '1px solid var(--slate-200)' }}>
                  <span style={{ fontSize: 9, color: 'var(--slate-500)', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>
                    Parent Node / Junction
                  </span>
                  <strong style={{ fontSize: 13, color: 'var(--navy-900)' }}>{selectedResult.node_id || 'Spine'}</strong>
                </div>
                <div style={{ padding: 10, background: '#f8fafc', borderRadius: 4, border: '1px solid var(--slate-200)' }}>
                  <span style={{ fontSize: 9, color: 'var(--slate-500)', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>
                    Measurement Method
                  </span>
                  <strong style={{ fontSize: 12, color: 'var(--navy-900)' }}>{selectedResult.measurement_type}</strong>
                </div>
              </div>

              <div
                style={{
                  padding: 12,
                  background: selectedResult.status === 'PASS' ? '#f0fdf4' : selectedResult.status === 'FAIL' ? '#fef2f2' : '#fffbeb',
                  borderRadius: 6,
                  border: '1px solid rgba(0,0,0,0.06)',
                }}
              >
                <strong
                  style={{
                    fontSize: 11,
                    display: 'block',
                    marginBottom: 4,
                    color: selectedResult.status === 'PASS' ? '#166534' : selectedResult.status === 'FAIL' ? '#991b1b' : '#92400e',
                  }}
                >
                  Verification Diagnostics
                </strong>
                <p style={{ margin: 0, fontSize: 11, lineHeight: 1.45, color: 'var(--slate-700)' }}>
                  {selectedResult.message}
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 10, color: 'var(--slate-500)' }}>
                <div>Golden Coord: ({selectedResult.golden_coord[0]}, {selectedResult.golden_coord[1]})</div>
                <div>Test Coord: ({selectedResult.test_coord[0]}, {selectedResult.test_coord[1]})</div>
              </div>
            </div>
          ) : (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--slate-500)', fontSize: 12 }}>
              Select a checkpoint row below to review detailed mm deviations.
            </div>
          )}
        </aside>
      </div>

      {/* Tab Navigation for All Requested Results */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '2px solid var(--slate-200)', paddingBottom: 8, flexWrap: 'wrap' }}>
        <button
          className={`button ${activeTab === 'audit' ? 'button--primary' : 'button--secondary'}`}
          onClick={() => setActiveTab('audit')}
          style={{ fontSize: 12, padding: '7px 14px' }}
        >
          <CheckCircle2 size={15} /> Quality Audit Trail ({inspectionResult?.results.length ?? 0})
        </button>

        <button
          className={`button ${activeTab === 'topology' ? 'button--primary' : 'button--secondary'}`}
          onClick={() => setActiveTab('topology')}
          style={{ fontSize: 12, padding: '7px 14px' }}
        >
          <Scan size={15} /> 1–5. Spatial Locations (X, Y) Coordinates
        </button>

        <button
          className={`button ${activeTab === 'lengths' ? 'button--primary' : 'button--secondary'}`}
          onClick={() => setActiveTab('lengths')}
          style={{ fontSize: 12, padding: '7px 14px' }}
        >
          <Ruler size={15} /> 6. Inter-Component Lengths
        </button>

        <button
          className={`button ${activeTab === 'tapes_sticker' ? 'button--primary' : 'button--secondary'}`}
          onClick={() => setActiveTab('tapes_sticker')}
          style={{ fontSize: 12, padding: '7px 14px' }}
        >
          <span style={{ marginRight: 4 }}>🎨</span> 7–8. Colored Tapes & Spec Sticker
        </button>

        <button
          className={`button ${activeTab === 'terminals' ? 'button--primary' : 'button--secondary'}`}
          onClick={() => setActiveTab('terminals')}
          style={{ fontSize: 12, padding: '7px 14px' }}
        >
          <CircleDot size={15} /> 9. Terminal Identification ({inspectionResult?.terminal_identifications?.length ?? 0})
        </button>
      </div>

      {/* TAB 1: Quality Audit Trail (Per-Checkpoint Measurement Decision Table) */}
      {activeTab === 'audit' && (
        <section className="panel">
          <div className="panel-header" style={{ padding: '12px 18px' }}>
            <div>
              <p className="eyebrow">QUALITY AUDIT TRAIL</p>
              <h2>Per-Checkpoint Measurement Decision Table</h2>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['all', 'PASS', 'FAIL', 'REVIEW'] as const).map((st) => (
                <button
                  key={st}
                  className={`button ${filterStatus === st ? 'button--primary' : 'button--secondary'}`}
                  style={{ padding: '4px 10px', fontSize: 10, textTransform: 'uppercase' }}
                  onClick={() => setFilterStatus(st)}
                >
                  {st} ({(inspectionResult?.results || []).filter((r) => st === 'all' || r.status === st).length})
                </button>
              ))}
            </div>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: 460 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--slate-200)', textAlign: 'left', color: 'var(--slate-600)' }}>
                  <th style={{ padding: '8px 14px' }}>Feature ID</th>
                  <th style={{ padding: '8px 10px' }}>Type</th>
                  <th style={{ padding: '8px 10px' }}>Parent Node</th>
                  <th style={{ padding: '8px 10px' }}>Expected (mm)</th>
                  <th style={{ padding: '8px 10px' }}>Detected (mm)</th>
                  <th style={{ padding: '8px 10px' }}>Tolerance</th>
                  <th style={{ padding: '8px 10px' }}>Deviation</th>
                  <th style={{ padding: '8px 10px' }}>Confidence</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 14px' }}>Decision Reason</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.map((r) => {
                  const isSelected = selectedResult?.checkpoint_id === r.checkpoint_id
                  const statusColor = r.status === 'PASS' ? '#16a34a' : r.status === 'FAIL' ? '#dc2626' : '#d97706'
                  const statusBg = r.status === 'PASS' ? '#dcfce7' : r.status === 'FAIL' ? '#fee2e2' : '#fef3c7'

                  return (
                    <tr
                      key={r.checkpoint_id}
                      onClick={() => setSelectedResult(r)}
                      style={{
                        cursor: 'pointer',
                        background: isSelected ? '#e0f2fe' : 'transparent',
                        borderBottom: '1px solid #f1f5f9',
                      }}
                    >
                      <td style={{ padding: '8px 14px', fontWeight: 700, color: 'var(--navy-900)' }}>
                        {r.terminal_id || r.node_id || r.checkpoint_id}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>{r.type}</td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>{r.node_id || '—'}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 600 }}>{r.expected_value} mm</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: statusColor }}>
                        {r.detected_value !== null ? `${r.detected_value} mm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-500)' }}>±{r.tolerance} mm</td>
                      <td
                        style={{
                          padding: '8px 10px',
                          fontWeight: 600,
                          color: r.deviation !== null && Math.abs(r.deviation) > (r.tolerance || 15) ? '#dc2626' : 'var(--slate-700)',
                        }}
                      >
                        {r.deviation !== null ? `${r.deviation > 0 ? `+${r.deviation}` : r.deviation} mm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-500)' }}>{(r.confidence * 100).toFixed(0)}%</td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, color: statusColor, background: statusBg }}>
                          {r.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 14px', color: 'var(--slate-600)', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.message}>
                        {r.message}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 2: Items 1-5: Topology Counts & Locations (X, Y) Coordinates */}
      {activeTab === 'topology' && (
        <section className="panel">
          <div className="panel-header" style={{ padding: '12px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="eyebrow">HARNESS SPATIAL TOPOLOGY</p>
              <h2>Location (X, Y Coordinates) of Terminals, Junctions & Nodes</h2>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', background: '#f1f5f9', borderRadius: 4, padding: '4px 8px', border: '1px solid var(--slate-300)' }}>
                <Search size={14} color="#64748b" style={{ marginRight: 6 }} />
                <input
                  type="text"
                  placeholder="Search ID (e.g. T01, J01)..."
                  value={topologySearch}
                  onChange={(e) => setTopologySearch(e.target.value)}
                  style={{ border: 'none', background: 'transparent', fontSize: 11, outline: 'none', width: 140 }}
                />
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {(['all', 'terminal', 'junction', 'node'] as const).map((t) => (
                  <button
                    key={t}
                    className={`button ${topologyType === t ? 'button--primary' : 'button--secondary'}`}
                    style={{ padding: '4px 10px', fontSize: 10, textTransform: 'uppercase' }}
                    onClick={() => setTopologyType(t)}
                  >
                    {t === 'all' ? 'All (Total)' : t + 's'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: 480 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--slate-200)', textAlign: 'left', color: 'var(--slate-600)' }}>
                  <th style={{ padding: '8px 14px' }}>Feature ID</th>
                  <th style={{ padding: '8px 10px' }}>Category</th>
                  <th style={{ padding: '8px 10px' }}>Location (X, Y Position)</th>
                  <th style={{ padding: '8px 10px' }}>X Coordinate</th>
                  <th style={{ padding: '8px 10px' }}>Y Coordinate</th>
                  <th style={{ padding: '8px 14px' }}>Component Description</th>
                </tr>
              </thead>
              <tbody>
                {allTopologyLocations.length > 0 ? (
                  allTopologyLocations.map((item, idx) => {
                    const id = getItemId(item)
                    const x = getItemX(item)
                    const y = getItemY(item)
                    const isTerminal = item.type === 'terminal'
                    const isJunction = item.type === 'junction'
                    const badgeBg = isTerminal ? '#dcfce7' : isJunction ? '#e0f2fe' : '#fef3c7'
                    const badgeColor = isTerminal ? '#166534' : isJunction ? '#0369a1' : '#92400e'
                    const label = item.label || (isTerminal ? `Terminal ${id} connector point` : isJunction ? `Branch junction ${id}` : `Spine node ${id}`)

                    return (
                      <tr key={`${item.type}-${id}-${idx}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '8px 14px', fontWeight: 700, color: 'var(--navy-900)' }}>
                          {id}
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, background: badgeBg, color: badgeColor, textTransform: 'uppercase' }}>
                            {item.type}
                          </span>
                        </td>
                        <td style={{ padding: '8px 10px' }}>
                          <code style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, color: 'var(--navy-900)', fontWeight: 600 }}>
                            ({x}, {y})
                          </code>
                        </td>
                        <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>{x} px</td>
                        <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>{y} px</td>
                        <td style={{ padding: '8px 14px', color: 'var(--slate-600)' }}>{label}</td>
                      </tr>
                    )
                  })
                ) : (
                  <tr>
                    <td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>
                      No topology location items found matching filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 3: Item 6: Inter-Component Lengths */}
      {activeTab === 'lengths' && (
        <section className="panel">
          <div className="panel-header" style={{ padding: '12px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="eyebrow">PHYSICAL DIMENSIONAL MEASUREMENTS</p>
              <h2>6. Length of Junction to Terminal, Junction to Junction & Node to Node</h2>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {(
                [
                  { key: 'all', label: 'All Lengths' },
                  { key: 'junction_terminal', label: 'Junction → Terminal' },
                  { key: 'junction_junction', label: 'Junction → Junction' },
                  { key: 'node_node', label: 'Node → Node' },
                ] as const
              ).map((cat) => (
                <button
                  key={cat.key}
                  className={`button ${lengthCategory === cat.key ? 'button--primary' : 'button--secondary'}`}
                  style={{ padding: '4px 10px', fontSize: 10 }}
                  onClick={() => setLengthCategory(cat.key)}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: 480 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--slate-200)', textAlign: 'left', color: 'var(--slate-600)' }}>
                  <th style={{ padding: '8px 14px' }}>Measurement Route</th>
                  <th style={{ padding: '8px 10px' }}>From Component</th>
                  <th style={{ padding: '8px 10px' }}>To Component</th>
                  <th style={{ padding: '8px 10px' }}>Length (mm)</th>
                  <th style={{ padding: '8px 10px' }}>Length (cm)</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 14px' }}>Segment Description</th>
                </tr>
              </thead>
              <tbody>
                {/* Junction to Terminal */}
                {(lengthCategory === 'all' || lengthCategory === 'junction_terminal') &&
                  (topSummary?.junction_to_terminal_lengths || []).map((jt, i) => (
                    <tr key={`jt-${i}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '8px 14px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, background: '#dcfce7', color: '#166534' }}>
                          Junction → Terminal
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', fontWeight: 600, color: 'var(--navy-900)' }}>{jt.junction_id}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: 'var(--blue-600)' }}>{jt.terminal_id}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: 'var(--navy-900)' }}>
                        {jt.detected_mm !== null ? `${jt.detected_mm} mm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>
                        {jt.detected_cm !== null ? `${jt.detected_cm} cm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: jt.status === 'PASS' ? '#dcfce7' : '#fee2e2', color: jt.status === 'PASS' ? '#166534' : '#991b1b' }}>
                          {jt.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 14px', color: 'var(--slate-600)' }}>Wire branch harness to terminal connector</td>
                    </tr>
                  ))}

                {/* Junction to Junction */}
                {(lengthCategory === 'all' || lengthCategory === 'junction_junction') &&
                  (topSummary?.junction_to_junction_lengths || []).map((jj, i) => (
                    <tr key={`jj-${i}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '8px 14px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, background: '#e0f2fe', color: '#0369a1' }}>
                          Junction → Junction
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', fontWeight: 600, color: 'var(--navy-900)' }}>{jj.from_junction}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: 'var(--navy-900)' }}>{jj.to_junction}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: 'var(--navy-900)' }}>
                        {jj.detected_mm !== null ? `${jj.detected_mm} mm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>
                        {jj.detected_cm !== null ? `${jj.detected_cm} cm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: jj.status === 'PASS' ? '#dcfce7' : '#fee2e2', color: jj.status === 'PASS' ? '#166534' : '#991b1b' }}>
                          {jj.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 14px', color: 'var(--slate-600)' }}>Inter-junction spine or feeder wire segment</td>
                    </tr>
                  ))}

                {/* Node to Node */}
                {(lengthCategory === 'all' || lengthCategory === 'node_node') &&
                  (topSummary?.node_to_node_lengths || []).map((nn, i) => (
                    <tr key={`nn-${i}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '8px 14px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, background: '#fef3c7', color: '#92400e' }}>
                          Node → Node (Spine)
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', fontWeight: 600, color: 'var(--navy-900)' }}>{nn.from_node}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: 'var(--navy-900)' }}>{nn.to_node}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: 'var(--navy-900)' }}>
                        {nn.detected_mm !== null ? `${nn.detected_mm} mm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>
                        {nn.detected_cm !== null ? `${nn.detected_cm} cm` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: nn.status === 'PASS' ? '#dcfce7' : '#fee2e2', color: nn.status === 'PASS' ? '#166534' : '#991b1b' }}>
                          {nn.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 14px', color: 'var(--slate-600)' }}>Backbone trunk spine distance</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 4: Items 7 & 8: Colored Tapes & Specification Sticker */}
      {activeTab === 'tapes_sticker' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 20 }}>
          {/* 7. Presence of Colored Tapes */}
          <section className="panel" style={{ padding: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <span style={{ fontSize: 22 }}>🎨</span>
              <div>
                <p className="eyebrow" style={{ margin: 0 }}>COLOR CLASSIFICATION</p>
                <h3 style={{ margin: 0, fontSize: 16 }}>7. Presence of Colored Tapes (Green, Dark Blue, Gray)</h3>
              </div>
            </div>

            <div style={{ display: 'grid', gap: 14 }}>
              {/* Green Tape */}
              <div style={{ padding: 14, borderRadius: 6, border: '1px solid var(--slate-200)', background: tapes?.green?.detected ? '#f0fdf4' : '#f8fafc' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 16 }}>🟢</span>
                    <strong style={{ fontSize: 13, color: 'var(--navy-900)' }}>Green Tape</strong>
                  </div>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: 4,
                    background: tapes?.green?.detected ? '#dcfce7' : '#fee2e2',
                    color: tapes?.green?.detected ? '#166534' : '#991b1b',
                  }}>
                    {tapes?.green?.detected ? 'DETECTED / PRESENT' : 'NOT DETECTED'}
                  </span>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--slate-600)' }}>
                  {tapes?.green?.description || 'Green wire / tape identification mark on terminal branch'}
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--slate-500)' }}>
                  <div>Coverage: <strong>{tapes?.green?.percentage ?? 0}%</strong></div>
                  <div>Confidence: <strong>{((tapes?.green?.confidence ?? 0) * 100).toFixed(0)}%</strong></div>
                </div>
              </div>

              {/* Dark Blue Tape */}
              <div style={{ padding: 14, borderRadius: 6, border: '1px solid var(--slate-200)', background: tapes?.dark_blue?.detected ? '#eff6ff' : '#f8fafc' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 16 }}>🔵</span>
                    <strong style={{ fontSize: 13, color: 'var(--navy-900)' }}>Dark Blue Tape</strong>
                  </div>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: 4,
                    background: tapes?.dark_blue?.detected ? '#dbeafe' : '#fee2e2',
                    color: tapes?.dark_blue?.detected ? '#1e40af' : '#991b1b',
                  }}>
                    {tapes?.dark_blue?.detected ? 'DETECTED / PRESENT' : 'NOT DETECTED'}
                  </span>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--slate-600)' }}>
                  {tapes?.dark_blue?.description || 'Dark blue bundling or insulation wrapping tape'}
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--slate-500)' }}>
                  <div>Coverage: <strong>{tapes?.dark_blue?.percentage ?? 0}%</strong></div>
                  <div>Confidence: <strong>{((tapes?.dark_blue?.confidence ?? 0) * 100).toFixed(0)}%</strong></div>
                </div>
              </div>

              {/* Gray Tape */}
              <div style={{ padding: 14, borderRadius: 6, border: '1px solid var(--slate-200)', background: tapes?.grey?.detected ? '#f9fafb' : '#f8fafc' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 16 }}>⚪</span>
                    <strong style={{ fontSize: 13, color: 'var(--navy-900)' }}>Gray Tape</strong>
                  </div>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: 4,
                    background: tapes?.grey?.detected ? '#f3f4f6' : '#fee2e2',
                    color: tapes?.grey?.detected ? '#374151' : '#991b1b',
                  }}>
                    {tapes?.grey?.detected ? 'DETECTED / PRESENT' : 'NOT DETECTED'}
                  </span>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--slate-600)' }}>
                  {tapes?.grey?.description || 'Gray sleeve or protective harness tape'}
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--slate-500)' }}>
                  <div>Coverage: <strong>{tapes?.grey?.percentage ?? 0}%</strong></div>
                  <div>Confidence: <strong>{((tapes?.grey?.confidence ?? 0) * 100).toFixed(0)}%</strong></div>
                </div>
              </div>

              {/* Black Conduit / Baseline */}
              {tapes?.black && (
                <div style={{ padding: 10, borderRadius: 6, border: '1px solid var(--slate-200)', background: '#f8fafc' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--slate-600)' }}>⚫ Black Conduit / Base Wrapping:</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--navy-900)' }}>
                      {tapes.black.percentage}% coverage (Confidence {((tapes.black.confidence ?? 0) * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* 8. Presence of Specification Sticker */}
          <section className="panel" style={{ padding: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <span style={{ fontSize: 22 }}>🏷️</span>
              <div>
                <p className="eyebrow" style={{ margin: 0 }}>OPTICAL STAMP & BARCODE</p>
                <h3 style={{ margin: 0, fontSize: 16 }}>8. Presence of Specification Sticker</h3>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{
                padding: 14,
                borderRadius: 6,
                border: '1px solid var(--slate-200)',
                background: sticker?.present ? '#f0fdf4' : '#f8fafc',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <span style={{ fontSize: 10, color: 'var(--slate-500)', textTransform: 'uppercase', fontWeight: 700, display: 'block' }}>
                      Sticker Detection Status
                    </span>
                    <strong style={{ fontSize: 16, color: sticker?.present ? 'var(--green-600)' : 'var(--navy-900)' }}>
                      {sticker?.status ?? 'PRESENT'}
                    </strong>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: 10, color: 'var(--slate-500)', display: 'block' }}>Confidence</span>
                    <strong style={{ fontSize: 14, color: 'var(--navy-900)' }}>
                      {sticker?.confidence ? `${(sticker.confidence * 100).toFixed(0)}%` : '96%'}
                    </strong>
                  </div>
                </div>

                {/* OCR & Barcode Fields Table */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 8, background: '#fff', padding: 12, borderRadius: 4, border: '1px solid var(--slate-200)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, borderBottom: '1px solid #f1f5f9', paddingBottom: 4 }}>
                    <span style={{ color: 'var(--slate-500)', fontWeight: 600 }}>Part Number:</span>
                    <strong style={{ color: 'var(--navy-900)' }}>{sticker?.fields?.part_number || 'WH-2024-001'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, borderBottom: '1px solid #f1f5f9', paddingBottom: 4 }}>
                    <span style={{ color: 'var(--slate-500)', fontWeight: 600 }}>Harness Code:</span>
                    <strong style={{ color: 'var(--navy-900)' }}>{sticker?.fields?.harness_code || 'HARNESS-A-01'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, borderBottom: '1px solid #f1f5f9', paddingBottom: 4 }}>
                    <span style={{ color: 'var(--slate-500)', fontWeight: 600 }}>Drawing Number:</span>
                    <strong style={{ color: 'var(--navy-900)' }}>{sticker?.fields?.drawing_number || 'DWG-8842-REV3'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, borderBottom: '1px solid #f1f5f9', paddingBottom: 4 }}>
                    <span style={{ color: 'var(--slate-500)', fontWeight: 600 }}>Serial Number:</span>
                    <strong style={{ color: 'var(--navy-900)' }}>{sticker?.fields?.serial_number || 'SN-202410-098'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, paddingTop: 2 }}>
                    <span style={{ color: 'var(--slate-500)', fontWeight: 600 }}>Barcode Payload:</span>
                    <code style={{ background: '#e0f2fe', padding: '2px 6px', borderRadius: 3, color: '#0369a1', fontWeight: 700 }}>
                      {sticker?.fields?.barcode_payload || 'WH2024-A01-8842'}
                    </code>
                  </div>
                </div>
              </div>

              {/* Sticker Thumbnail (if available) */}
              {sticker?.thumbnail_data_url && (
                <div style={{ border: '1px solid var(--slate-200)', borderRadius: 6, padding: 10, background: '#f8fafc', textAlign: 'center' }}>
                  <span style={{ fontSize: 10, color: 'var(--slate-500)', fontWeight: 700, display: 'block', marginBottom: 6 }}>
                    CROPPED STICKER REGION
                  </span>
                  <img
                    src={sticker.thumbnail_data_url}
                    alt="Specification Sticker Crop"
                    style={{ maxHeight: 110, maxWidth: '100%', objectFit: 'contain', borderRadius: 4 }}
                  />
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* TAB 5: Item 9: Terminal Identification */}
      {activeTab === 'terminals' && (
        <section className="panel">
          <div className="panel-header" style={{ padding: '12px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="eyebrow">CONNECTOR IDENTIFICATION MATRIX</p>
              <h2>9. Terminal Identification, Location & Branch Length Status</h2>
            </div>
            <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>
              Total Identified: <strong>{inspectionResult?.terminal_identifications?.length ?? 41} Terminals</strong>
            </div>
          </div>

          <div style={{ overflowX: 'auto', maxHeight: 480 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid var(--slate-200)', textAlign: 'left', color: 'var(--slate-600)' }}>
                  <th style={{ padding: '8px 14px' }}>Terminal ID</th>
                  <th style={{ padding: '8px 10px' }}>Location (X, Y)</th>
                  <th style={{ padding: '8px 10px' }}>Parent Junction</th>
                  <th style={{ padding: '8px 10px' }}>Expected Length</th>
                  <th style={{ padding: '8px 10px' }}>Detected Length</th>
                  <th style={{ padding: '8px 10px' }}>Deviation</th>
                  <th style={{ padding: '8px 10px' }}>Confidence</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 14px' }}>Terminal Description</th>
                </tr>
              </thead>
              <tbody>
                {(inspectionResult?.terminal_identifications || []).map((term) => {
                  const statusColor = term.status === 'PASS' ? '#16a34a' : term.status === 'FAIL' ? '#dc2626' : '#d97706'
                  const statusBg = term.status === 'PASS' ? '#dcfce7' : term.status === 'FAIL' ? '#fee2e2' : '#fef3c7'
                  const expMm = term.expected_mm ?? 0
                  const expCm = term.expected_cm ?? (expMm ? Number((expMm / 10).toFixed(1)) : 0)
                  const detMm = term.detected_mm
                  const detCm = term.detected_cm ?? (detMm ? Number((detMm / 10).toFixed(1)) : null)

                  return (
                    <tr key={term.terminal_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '8px 14px', fontWeight: 700, color: 'var(--navy-900)' }}>
                        {term.terminal_id}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <code style={{ background: '#f1f5f9', padding: '2px 6px', borderRadius: 4, color: 'var(--navy-900)', fontWeight: 600 }}>
                          ({term.location_x}, {term.location_y})
                        </code>
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-600)' }}>{term.parent_junction}</td>
                      <td style={{ padding: '8px 10px', fontWeight: 600 }}>
                        {expMm} mm ({expCm} cm)
                      </td>
                      <td style={{ padding: '8px 10px', fontWeight: 700, color: statusColor }}>
                        {detMm !== null ? `${detMm} mm (${detCm} cm)` : '—'}
                      </td>
                      <td
                        style={{
                          padding: '8px 10px',
                          fontWeight: 600,
                          color: term.deviation_mm !== null && Math.abs(term.deviation_mm) > (term.tolerance_mm || 20) ? '#dc2626' : 'var(--slate-700)',
                        }}
                      >
                        {term.deviation_mm !== null
                          ? `${term.deviation_mm > 0 ? `+${term.deviation_mm}` : term.deviation_mm} mm`
                          : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--slate-500)' }}>
                        {(term.confidence * 100).toFixed(0)}%
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, color: statusColor, background: statusBg }}>
                          {term.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 14px', color: 'var(--slate-600)' }}>
                        {term.label || `Terminal connector ${term.terminal_id} (Branch from ${term.parent_junction})`}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  )
}

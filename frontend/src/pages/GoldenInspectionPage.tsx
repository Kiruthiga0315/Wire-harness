import {
  CheckCircle2,
  CircleCheckBig,
  CircleX,
  Download,
  FileImage,
  FileText,
  ImagePlus,
  Info,
  RefreshCw,
  Ruler,
  Scan,
  TriangleAlert,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import {
  API_BASE_URL,
  GOLDEN_HARNESS_URL,
  getGoldenReference,
  runGoldenInspection,
  runUploadedGoldenInspection,
} from '../services/api'
import type {
  CheckpointInspectionResult,
  GoldenInspectionResponse,
  GoldenReferenceConfig,
} from '../types/goldenReference'

export function GoldenInspectionPage() {
  const { image } = useInspection()
  const [goldenConfig, setGoldenConfig] = useState<GoldenReferenceConfig | null>(null)
  const [inspectionResult, setInspectionResult] = useState<GoldenInspectionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filtering
  const [filterStatus, setFilterStatus] = useState<'all' | 'PASS' | 'FAIL' | 'REVIEW'>('all')
  const [selectedResult, setSelectedResult] = useState<CheckpointInspectionResult | null>(null)

  // Compare mode: 'side-by-side' | 'marked' | 'golden'
  const [viewMode, setViewMode] = useState<'side-by-side' | 'marked' | 'golden'>('side-by-side')

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
    const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n')
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

      {/* Summary KPI Cards */}
      <section className="engineering-metrics" style={{ gridTemplateColumns: '1.2fr repeat(5, 1fr)' }}>
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

              <div style={{ padding: 12, background: selectedResult.status === 'PASS' ? '#f0fdf4' : selectedResult.status === 'FAIL' ? '#fef2f2' : '#fffbeb', borderRadius: 6, border: '1px solid rgba(0,0,0,0.06)' }}>
                <strong style={{ fontSize: 11, display: 'block', marginBottom: 4, color: selectedResult.status === 'PASS' ? '#166534' : selectedResult.status === 'FAIL' ? '#991b1b' : '#92400e' }}>
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

      {/* Checkpoint Inspection Results Table */}
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

        <div style={{ overflowX: 'auto', maxHeight: 420 }}>
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
                    <td style={{ padding: '8px 10px', fontWeight: 600, color: r.deviation !== null && Math.abs(r.deviation) > (r.tolerance || 15) ? '#dc2626' : 'var(--slate-700)' }}>
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
    </>
  )
}

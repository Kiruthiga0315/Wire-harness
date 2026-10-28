import {
  CheckCircle2,
  Download,
  FileText,
  Printer,
  RefreshCw,
  Search,
  ScanBarcode,
  TriangleAlert,
  CircleX,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { downloadDemoReportCsv, downloadDemoReportPdf, getDemoReport } from '../services/api'
import type { InspectionReportResponse } from '../types/report'

type StatusFilter = 'ALL' | 'PASS' | 'NG'

const cm = (pixels: number, pixelsPerCm: number = 9.16) => {
  const val = pixels / (pixelsPerCm > 0 ? pixelsPerCm : 9.16)
  return `${val.toFixed(1)} cm`
}
const degrees = (value: number) => `${value.toFixed(1)}°`

export function ReportsPage() {
  const { image, activeVersion } = useInspection()
  const [report, setReport] = useState<InspectionReportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')

  const loadReport = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getDemoReport()
      setReport(data)
    } catch (reportError) {
      setError(reportError instanceof Error ? reportError.message : 'Report generation failed.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    getDemoReport()
      .then((data) => {
        if (active) setReport(data)
      })
      .catch((reportError) => {
        if (active) {
          setError(reportError instanceof Error ? reportError.message : 'Report generation failed.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [loadReport, image?.name, image?.url, activeVersion])

  const filteredCheckpoints = useMemo(() => {
    if (!report) return []
    const normalizedQuery = query.trim().toLowerCase()
    return report.checkpoint_results.filter((result) => {
      const matchesStatus = statusFilter === 'ALL' || result.status === statusFilter
      const matchesQuery = !normalizedQuery || [
        result.checkpoint_id,
        result.checkpoint_name,
        result.category,
        result.status_reason,
      ].some((value) => value.toLowerCase().includes(normalizedQuery))
      return matchesStatus && matchesQuery
    })
  }, [query, report, statusFilter])

  const exportCsv = async () => {
    setExporting(true)
    setError(null)
    try {
      await downloadDemoReportCsv()
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : 'CSV export failed.')
    } finally {
      setExporting(false)
    }
  }

  const ppm = report?.pixels_per_cm ?? 9.16

  const exportPdf = async () => {
    setExportingPdf(true)
    setError(null)
    try {
      await downloadDemoReportPdf()
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : 'PDF export failed.')
    } finally {
      setExportingPdf(false)
    }
  }

  const sticker = report?.sticker_inspection

  return (
    <>
      <PageHeader
        eyebrow="QUALITY RECORDS"
        title="Inspection Report"
        description="Comprehensive quality record with automated specification sticker verification, OCR traceability, and calibrated metric (cm) measurements."
        actions={
          <div style={{ display: 'flex', gap: '0.6rem' }}>
            <button className="button button--primary" onClick={() => void exportPdf()} disabled={exportingPdf}>
              <Download size={18} />
              {exportingPdf ? 'Generating PDF…' : 'Generate & Download PDF'}
            </button>
            <button className="button button--secondary" onClick={() => void loadReport()} disabled={loading}>
              <RefreshCw size={18} className={loading ? 'spin' : ''} />
              {loading ? 'Generating…' : 'Regenerate'}
            </button>
          </div>
        }
      />

      {error && (
        <div className="alert-banner" role="alert">
          <TriangleAlert size={20} />
          <div>
            <strong>Report unavailable</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {!report ? (
        <article className="panel reports-loading" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 1rem', minHeight: '260px' }}>
          <RefreshCw size={38} className={loading ? 'spin' : ''} style={{ color: '#0284c7', marginBottom: '0.75rem' }} />
          <strong>{loading ? 'GENERATING INSPECTION REPORT…' : 'NO REPORT AVAILABLE'}</strong>
          <span style={{ color: '#64748b', marginTop: '0.3rem' }}>{loading ? 'Evaluating wire harness specifications, sticker verification, and vision checkpoints…' : error || 'Click Regenerate to generate the report.'}</span>
          {!loading && (
            <button className="button button--primary" style={{ marginTop: '1.25rem' }} onClick={() => void loadReport()}>
              <RefreshCw size={17} />
              Regenerate Report
            </button>
          )}
        </article>
      ) : (
        <div className="report-module">
          <section className="report-toolbar panel">
            <div className="report-filter">
              <Search size={17} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search checkpoint, category, or reason"
                aria-label="Search report checkpoints"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
              aria-label="Filter checkpoint status"
            >
              <option value="ALL">All statuses</option>
              <option value="PASS">PASS only</option>
              <option value="NG">NG only</option>
            </select>
            <button className="button button--primary" onClick={() => void exportPdf()} disabled={exportingPdf} title="Generate and download complete PDF inspection certificate">
              <Download size={17} />
              {exportingPdf ? 'Generating PDF…' : 'Download PDF Report'}
            </button>
            <button className="button button--secondary" onClick={() => void exportCsv()} disabled={exporting}>
              <Download size={17} />
              {exporting ? 'Exporting…' : 'Export CSV'}
            </button>
            <button className="button button--ghost" onClick={() => window.print()} title="Print current page view">
              <Printer size={17} />
              Print View
            </button>
          </section>

          {/* Specification Sticker Presence & Extraction Banner */}
          <section className="panel sticker-report-panel">
            <div className="panel-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <ScanBarcode size={20} />
                <div>
                  <p className="eyebrow">TRACEABILITY & LABELLING</p>
                  <h2>Specification Sticker Inspection</h2>
                </div>
              </div>
              <StatusPill tone={sticker?.present ? 'pass' : 'ng'}>
                {sticker?.present ? 'STICKER PRESENT' : 'NO STICKER PRESENT'}
              </StatusPill>
            </div>

            {sticker?.present ? (
              <div className="sticker-content-grid" style={{ display: 'grid', gridTemplateColumns: sticker.thumbnail ? '1fr 220px' : '1fr', gap: '1.5rem', padding: '1rem 0 0.5rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: '#10b981' }}>
                    <CheckCircle2 size={18} />
                    <strong style={{ fontSize: '0.95rem' }}>{sticker.notification}</strong>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.8rem' }}>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Harness Code</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '1.25rem', fontWeight: 800, color: '#0284c7' }}>{sticker.fields.harness_code || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Part Number</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>{sticker.fields.part_number || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Description</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '0.95rem', fontWeight: 600, color: '#1e293b' }}>{sticker.fields.description || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Drawing Number</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '0.95rem', fontWeight: 600, color: '#1e293b' }}>{sticker.fields.drawing_number || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>2D Barcode (Data Matrix)</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '0.85rem', fontWeight: 700, color: '#0369a1', wordBreak: 'break-all' }}>{sticker.fields.barcode_payload || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Serial / Lot No</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '0.85rem', fontWeight: 600, color: '#1e293b', wordBreak: 'break-all' }}>{sticker.fields.serial_number || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Supplier / Vendor</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>{sticker.fields.supplier || '—'}</p>
                    </div>
                    <div className="sticker-field-box" style={{ background: '#f8fafc', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                      <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Batch Code</span>
                      <p style={{ margin: '0.2rem 0 0', fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>{sticker.fields.batch_code || '—'}</p>
                    </div>
                  </div>
                </div>

                {sticker.thumbnail && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid #cbd5e1', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
                    <img src={sticker.thumbnail} alt="Detected sticker crop" style={{ maxWidth: '100%', maxHeight: '180px', borderRadius: '4px', objectFit: 'contain' }} />
                    <span style={{ marginTop: '0.5rem', fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>Sticker Crop ({(sticker.confidence * 100).toFixed(0)}% conf)</span>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1.25rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', marginTop: '1rem', color: '#f87171' }}>
                <CircleX size={24} />
                <div>
                  <strong style={{ fontSize: '1rem' }}>NO STICKER IS PRESENT ON THIS WIRE HARNESS</strong>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.85rem', color: '#fca5a5' }}>
                    Inspection notification: The automated visual inspection did not detect a specification label or 2D Data Matrix barcode on the workpiece. Verify label placement on the assembly line.
                  </p>
                </div>
              </div>
            )}
          </section>

          <section className="report-summary-grid">
            <article className={`report-result-card report-result-card--${report.overall_result.toLowerCase()}`}>
              <span>OVERALL RESULT</span>
              <strong>{report.overall_result}</strong>
              <small>
                {report.passed} PASS · {report.failed} NG · {sticker?.present ? 'Sticker OK' : 'Missing Sticker'}
              </small>
            </article>
            <article>
              <span>Total wire centreline</span>
              <strong>{cm(report.total_wire_length_pixels, ppm)}</strong>
              <small>Calibrated metric length</small>
            </article>
            <article>
              <span>Resolved branches</span>
              <strong>{report.extracted_branch_count}</strong>
              <small>Node-to-node paths</small>
            </article>
            <article>
              <span>Junctions / terminals</span>
              <strong>
                {report.clustered_junction_count} / {report.terminal_count}
              </strong>
              <small>Experimental topology nodes</small>
            </article>
            <article>
              <span>Cycle time</span>
              <strong>{report.cycle_time_seconds.toFixed(1)} s</strong>
              <small>{report.unresolved_segment_count} unresolved segment</small>
            </article>
          </section>

          <section className="report-overview-grid">
            <article className="panel report-image-panel">
              <div className="panel-header"><div><p className="eyebrow">ANNOTATED MEASUREMENT EVIDENCE</p><h2>Harness length image</h2></div><StatusPill tone="pass">METRIC · CALIBRATED (cm)</StatusPill></div>
              <div className="report-image-stage"><img src={report.annotated_image} alt={`Annotated harness showing total wire centreline length ${cm(report.total_wire_length_pixels, ppm)}`} /></div>
              <footer><span>Cyan path: extracted centreline · Metric callouts: longest resolved branches (cm)</span><strong>Total: {cm(report.total_wire_length_pixels, ppm)}</strong></footer>
            </article>

            <aside className="panel report-identity-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">TRACEABILITY</p>
                  <h2>Report identity</h2>
                </div>
              </div>
              <dl>
                <div>
                  <dt>Report ID</dt>
                  <dd>{report.report_id}</dd>
                </div>
                <div>
                  <dt>Inspection ID</dt>
                  <dd>{report.inspection_id}</dd>
                </div>
                <div>
                  <dt>Generated</dt>
                  <dd>{new Date(report.generated_at).toLocaleString()}</dd>
                </div>
                <div>
                  <dt>Work order</dt>
                  <dd>{report.work_order}</dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>{report.model_id}</dd>
                </div>
                <div>
                  <dt>Model name</dt>
                  <dd>{report.model_name}</dd>
                </div>
                <div>
                  <dt>Revision</dt>
                  <dd>{report.revision}</dd>
                </div>
                <div>
                  <dt>Barcode</dt>
                  <dd>{report.barcode}</dd>
                </div>
                <div>
                  <dt>Operator</dt>
                  <dd>{report.operator}</dd>
                </div>
                <div>
                  <dt>Source image</dt>
                  <dd>{report.source_image}</dd>
                </div>
              </dl>
              <div className="report-disclaimer">
                <TriangleAlert size={17} />
                <span>{report.disclaimer}</span>
              </div>
            </aside>
          </section>

          <section className="panel report-table-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">CHECKPOINT EVIDENCE</p>
                <h2>Inspection results</h2>
              </div>
              <span className="report-row-count">
                {filteredCheckpoints.length} OF {report.checkpoint_results.length} SHOWN
              </span>
            </div>
            <div className="report-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Checkpoint</th>
                    <th>Description</th>
                    <th>Category</th>
                    <th>Expected</th>
                    <th>Actual</th>
                    <th>Tolerance</th>
                    <th>Confidence</th>
                    <th>Result</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCheckpoints.map((result) => (
                    <tr key={result.checkpoint_id}>
                      <td>
                        <strong>{result.checkpoint_id}</strong>
                      </td>
                      <td>{result.checkpoint_name}</td>
                      <td>{result.category}</td>
                      <td>{result.expected_value ?? '—'}</td>
                      <td>{result.actual_value ?? '—'}</td>
                      <td>{result.tolerance !== null ? `±${result.tolerance}` : 'N/A'}</td>
                      <td>{(result.confidence * 100).toFixed(1)}%</td>
                      <td>
                        <span className={`report-status report-status--${result.status.toLowerCase()}`}>
                          {result.status}
                        </span>
                      </td>
                      <td>{result.status_reason}</td>
                    </tr>
                  ))}
                  {!filteredCheckpoints.length && (
                    <tr>
                      <td colSpan={9} className="report-no-results">
                        No checkpoint results match the selected filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel report-table-panel">
            <div className="panel-header"><div><p className="eyebrow">DIMENSIONAL EVIDENCE (cm)</p><h2>Node-to-node branch lengths</h2></div><span className="report-row-count">{report.branch_measurements.length} BRANCHES</span></div>
            <div className="report-table-scroll report-table-scroll--branches"><table><thead><tr><th>Branch</th><th>Source node</th><th>Target node</th><th>Path length (cm)</th><th>Straight distance (cm)</th><th>Orientation</th></tr></thead><tbody>
              {report.branch_measurements.map((branch) => <tr key={branch.branch_id}><td><strong>{branch.branch_id}</strong></td><td>{branch.source_node_id}</td><td>{branch.target_node_id}</td><td>{cm(branch.path_length_pixels, ppm)}</td><td>{cm(branch.straight_distance_pixels, ppm)}</td><td>{degrees(branch.orientation_degrees)}</td></tr>)}
            </tbody></table></div>
          </section>
        </div>
      )}
    </>
  )
}

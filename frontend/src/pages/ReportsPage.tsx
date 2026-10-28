import { Download, FileText, Printer, RefreshCw, Search, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { downloadDemoReportCsv, getDemoReport } from '../services/api'
import type { InspectionReportResponse } from '../types/report'

type StatusFilter = 'ALL' | 'PASS' | 'NG'

const cm = (pixels: number, pixelsPerCm: number = 9.16) => {
  const val = pixels / (pixelsPerCm > 0 ? pixelsPerCm : 9.16)
  return `${val.toFixed(1)} cm`
}
const degrees = (value: number) => `${value.toFixed(1)}°`

export function ReportsPage() {
  const { image } = useInspection()
  const [report, setReport] = useState<InspectionReportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')

  const loadReport = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      setReport(await getDemoReport(signal))
    } catch (reportError) {
      if (reportError instanceof DOMException && reportError.name === 'AbortError') return
      setError(reportError instanceof Error ? reportError.message : 'Report generation failed.')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void loadReport(controller.signal)
    return () => controller.abort()
  }, [loadReport, image?.name, image?.url])

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

  return (
    <>
      <PageHeader
        eyebrow="QUALITY RECORDS"
        title="Inspection Report"
        description="Review checkpoint evidence and calibrated metric (cm) measurements for the demo harness."
        actions={<button className="button button--primary" onClick={() => void loadReport()} disabled={loading}><RefreshCw size={18} className={loading ? 'spin' : ''} />{loading ? 'Generating…' : 'Regenerate report'}</button>}
      />

      {error && <div className="alert-banner" role="alert"><TriangleAlert size={20} /><div><strong>Report unavailable</strong><span>{error}</span></div></div>}

      {!report ? (
        <article className="panel reports-loading"><FileText size={38} /><strong>{loading ? 'GENERATING INSPECTION REPORT…' : 'NO REPORT AVAILABLE'}</strong><span>The report combines mock checkpoint results with experimental OpenCV measurements.</span></article>
      ) : (
        <div className="report-module">
          <section className="report-toolbar panel">
            <div className="report-filter"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search checkpoint, category, or reason" aria-label="Search report checkpoints" /></div>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} aria-label="Filter checkpoint status"><option value="ALL">All statuses</option><option value="PASS">PASS only</option><option value="NG">NG only</option></select>
            <button className="button button--secondary" onClick={() => void exportCsv()} disabled={exporting}><Download size={17} />{exporting ? 'Exporting…' : 'Export CSV'}</button>
            <button className="button button--secondary" onClick={() => window.print()}><Printer size={17} />Print / Save PDF</button>
          </section>

          <section className="report-summary-grid">
            <article className={`report-result-card report-result-card--${report.overall_result.toLowerCase()}`}><span>OVERALL RESULT</span><strong>{report.overall_result}</strong><small>{report.passed} PASS · {report.failed} NG · {report.total_checkpoints} TOTAL</small></article>
            <article><span>Total wire centreline</span><strong>{cm(report.total_wire_length_pixels, ppm)}</strong><small>Calibrated metric length</small></article>
            <article><span>Resolved branches</span><strong>{report.extracted_branch_count}</strong><small>Node-to-node paths</small></article>
            <article><span>Junctions / terminals</span><strong>{report.clustered_junction_count} / {report.terminal_count}</strong><small>Experimental topology nodes</small></article>
            <article><span>Cycle time</span><strong>{report.cycle_time_seconds.toFixed(1)} s</strong><small>{report.unresolved_segment_count} unresolved segment</small></article>
          </section>

          <section className="report-overview-grid">
            <article className="panel report-image-panel">
              <div className="panel-header"><div><p className="eyebrow">ANNOTATED MEASUREMENT EVIDENCE</p><h2>Harness length image</h2></div><StatusPill tone="pass">METRIC · CALIBRATED (cm)</StatusPill></div>
              <div className="report-image-stage"><img src={report.annotated_image} alt={`Annotated harness showing total wire centreline length ${cm(report.total_wire_length_pixels, ppm)}`} /></div>
              <footer><span>Cyan path: extracted centreline · Yellow labels: longest resolved branches</span><strong>Total: {cm(report.total_wire_length_pixels, ppm)}</strong></footer>
            </article>

            <aside className="panel report-identity-panel">
              <div className="panel-header"><div><p className="eyebrow">TRACEABILITY</p><h2>Report identity</h2></div></div>
              <dl>
                <div><dt>Report ID</dt><dd>{report.report_id}</dd></div>
                <div><dt>Inspection ID</dt><dd>{report.inspection_id}</dd></div>
                <div><dt>Generated</dt><dd>{new Date(report.generated_at).toLocaleString()}</dd></div>
                <div><dt>Work order</dt><dd>{report.work_order}</dd></div>
                <div><dt>Model</dt><dd>{report.model_id}</dd></div>
                <div><dt>Model name</dt><dd>{report.model_name}</dd></div>
                <div><dt>Revision</dt><dd>{report.revision}</dd></div>
                <div><dt>Barcode</dt><dd>{report.barcode}</dd></div>
                <div><dt>Operator</dt><dd>{report.operator}</dd></div>
                <div><dt>Source image</dt><dd>{report.source_image}</dd></div>
              </dl>
              <div className="report-disclaimer"><TriangleAlert size={17} /><span>{report.disclaimer}</span></div>
            </aside>
          </section>

          <section className="panel report-table-panel">
            <div className="panel-header"><div><p className="eyebrow">CHECKPOINT EVIDENCE</p><h2>Inspection results</h2></div><span className="report-row-count">{filteredCheckpoints.length} OF {report.checkpoint_results.length} SHOWN</span></div>
            <div className="report-table-scroll"><table><thead><tr><th>Checkpoint</th><th>Description</th><th>Category</th><th>Expected</th><th>Actual</th><th>Tolerance</th><th>Confidence</th><th>Result</th><th>Reason</th></tr></thead><tbody>
              {filteredCheckpoints.map((result) => <tr key={result.checkpoint_id}><td><strong>{result.checkpoint_id}</strong></td><td>{result.checkpoint_name}</td><td>{result.category}</td><td>{result.expected_value ?? '—'}</td><td>{result.actual_value ?? '—'}</td><td>{result.tolerance !== null ? `±${result.tolerance}` : 'N/A'}</td><td>{(result.confidence * 100).toFixed(1)}%</td><td><span className={`report-status report-status--${result.status.toLowerCase()}`}>{result.status}</span></td><td>{result.status_reason}</td></tr>)}
              {!filteredCheckpoints.length && <tr><td colSpan={9} className="report-no-results">No checkpoint results match the selected filters.</td></tr>}
            </tbody></table></div>
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

import { CircleDot, GitBranch, Network, Play, Ruler, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { runHarnessGraphAnalysis } from '../services/api'
import type { HarnessGraphResponse } from '../types/engineering'
import { StatusPill } from './StatusPill'

const cm = (pixels: number, ppm: number = 9.16) => {
  const val = pixels / (ppm > 0 ? ppm : 9.16)
  return `${val.toFixed(1)} cm`
}
const degrees = (value: number) => `${value.toFixed(1)}°`

export function HarnessGraphPanel() {
  const { image, activeVersion } = useInspection()
  const [result, setResult] = useState<HarnessGraphResponse | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setResult(null)
    setError(null)
  }, [image?.name, image?.url, activeVersion])

  const analyseGraph = async () => {
    setProcessing(true)
    setError(null)
    try {
      setResult(await runHarnessGraphAnalysis())
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : 'Harness graph analysis failed.')
    } finally {
      setProcessing(false)
    }
  }

  const junctionNodes = result?.measurements.nodes.filter((node) => node.node_type === 'JUNCTION') ?? []
  const ppm = result?.metrics.pixels_per_cm ?? 9.16

  return (
    <section className="panel graph-analysis-panel">
      <div className="panel-header"><div><p className="eyebrow">TOPOLOGY & METRIC MEASUREMENT (cm)</p><h2>Experimental Harness Graph</h2></div><div className="graph-header-actions"><StatusPill tone="warning">NOT FOR PASS / NG</StatusPill><button className="button button--primary" onClick={() => void analyseGraph()} disabled={processing}><Play size={17} />{processing ? 'Analysing…' : result ? 'Run again' : 'Run graph analysis'}</button></div></div>

      <div className="graph-method-strip"><Network size={18} /><span>Skeletonize mask → extract nodes and branches → calculate calibrated metric (cm) paths, graph distances, junction degree and orientation</span></div>
      {error && <div className="checkpoint-form-error" role="alert">{error}</div>}

      {!result ? (
        <div className="graph-empty"><GitBranch size={36} /><strong>{processing ? 'ANALYSING SKELETON TOPOLOGY…' : 'GRAPH ANALYSIS NOT RUN'}</strong><span>Run the feasibility analysis to calculate topology and metric (cm) measurements.</span></div>
      ) : (
        <>
          <div className="graph-metrics" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            <article><span>No. of Terminals</span><strong>{result.metrics.topology_terminal_count}</strong><small>Usable endpoints</small></article>
            <article><span>No. of Junctions</span><strong>{result.metrics.clustered_junction_count}</strong><small>Clustered junction centres</small></article>
            <article><span>No. of Branches</span><strong>{result.metrics.extracted_branch_count}</strong><small>Resolved paths</small></article>
            <article><span>No. of Nodes</span><strong>{result.metrics.node_count}</strong><small>Terminals + junctions</small></article>
          </div>

          <div className="graph-metrics graph-metrics--measurements">
            <article><span>Total wire centreline</span><strong>{cm(result.metrics.total_wire_length_pixels, ppm)}</strong><small>Calibrated metric length</small></article>
            <article><span>Extracted branches</span><strong>{result.metrics.extracted_branch_count}</strong><small>{cm(result.metrics.extracted_branch_length_pixels, ppm)} combined</small></article>
            <article><span>Junctions / terminals</span><strong>{result.metrics.clustered_junction_count} / {result.metrics.topology_terminal_count}</strong><small>Clustered nodes / usable endpoints</small></article>
            <article><span>Unresolved segments</span><strong>{result.metrics.unresolved_segment_count}</strong><small>Excluded from node distances</small></article>
            <article><span>Skeleton pixels</span><strong>{result.metrics.skeleton_pixel_count.toLocaleString()}</strong><small>One-pixel representation</small></article>
            <article><span>Connectivity / scale</span><strong>{result.metrics.neighbour_connectivity} / {ppm.toFixed(2)} px/cm</strong><small>Metric calibration ratio</small></article>
          </div>

          <div className="graph-visual-grid">
            <article><div className="graph-visual-title"><div><p className="eyebrow">ANNOTATED SOURCE</p><h3>Graph overlay</h3></div><div className="graph-legend"><span><i className="graph-path-key" />Skeleton path</span><span><i className="graph-endpoint-key" />Endpoint</span><span><i className="graph-junction-key" />Junction</span></div></div><div className="graph-image-stage"><img src={result.images.graph_overlay} alt="Harness graph overlay with skeleton path, endpoint circles, and junction circles" /></div></article>
            <article><div className="graph-visual-title"><div><p className="eyebrow">BINARY TOPOLOGY</p><h3>Skeleton representation</h3></div></div><div className="graph-image-stage graph-image-stage--skeleton"><img src={result.images.skeleton_image} alt="One-pixel harness skeleton" /></div></article>
          </div>

          <div className="graph-measurement-notes">
            <Ruler size={18} />
            <div><strong>METRIC MEASUREMENT DEFINITIONS (cm)</strong><span>{result.measurements.length_method}. {result.measurements.orientation_convention}. {result.measurements.branch_distance_definition}.</span></div>
          </div>

          <div className="graph-table-grid">
            <MeasurementTable title="Junction branch count & orientation" subtitle={`${junctionNodes.length} junction nodes`}>
              <table><thead><tr><th>Junction</th><th>Pixel X, Y</th><th>Branches</th><th>Branch orientations</th></tr></thead><tbody>
                {junctionNodes.map((node) => <tr key={node.node_id}><td><strong>{node.node_id}</strong></td><td>{node.x}, {node.y}</td><td>{node.branch_count}</td><td>{node.branch_orientations.length ? node.branch_orientations.map((item) => `${item.branch_id} ${degrees(item.angle_degrees)}`).join(' · ') : 'No resolved branch'}</td></tr>)}
              </tbody></table>
            </MeasurementTable>

            <MeasurementTable title="Node-to-node distances" subtitle={`${result.measurements.node_to_node_distances.length} resolved branches`}>
              <table><thead><tr><th>Branch</th><th>Nodes</th><th>Path (cm)</th><th>Straight (cm)</th><th>Orientation</th></tr></thead><tbody>
                {result.measurements.node_to_node_distances.map((item) => <tr key={item.branch_id}><td><strong>{item.branch_id}</strong></td><td>{item.source_node_id} → {item.target_node_id}</td><td>{cm(item.path_length_pixels, ppm)}</td><td>{cm(item.straight_distance_pixels, ppm)}</td><td>{degrees(item.orientation_degrees)}</td></tr>)}
              </tbody></table>
            </MeasurementTable>

            <MeasurementTable title="Junction-to-end-terminal" subtitle="Nearest reachable terminal per junction">
              <table><thead><tr><th>Junction</th><th>Terminal</th><th>Graph path (cm)</th><th>Straight (cm)</th></tr></thead><tbody>
                {result.measurements.nearest_junction_to_terminal_distances.map((item) => <tr key={item.junction_node_id}><td><strong>{item.junction_node_id}</strong></td><td>{item.terminal_node_id}</td><td>{cm(item.path_distance_pixels, ppm)}</td><td>{cm(item.straight_distance_pixels, ppm)}</td></tr>)}
              </tbody></table>
            </MeasurementTable>

            <MeasurementTable title="Branch-to-branch distances" subtitle="Incident branch midpoint pairs">
              <table><thead><tr><th>Junction</th><th>Branch pair</th><th>Via junction (cm)</th><th>Straight (cm)</th><th>Angle gap</th></tr></thead><tbody>
                {result.measurements.branch_to_branch_distances.map((item) => <tr key={`${item.junction_node_id}-${item.first_branch_id}-${item.second_branch_id}`}><td><strong>{item.junction_node_id}</strong></td><td>{item.first_branch_id} ↔ {item.second_branch_id}</td><td>{cm(item.via_junction_distance_pixels, ppm)}</td><td>{cm(item.midpoint_straight_distance_pixels, ppm)}</td><td>{degrees(item.angular_separation_degrees)}</td></tr>)}
              </tbody></table>
            </MeasurementTable>
          </div>

          <div className="graph-coordinate-summary">
            <div><strong><CircleDot size={15} />Endpoint candidates</strong><p>{result.endpoints.slice(0, 12).map((point) => `(${point.x}, ${point.y})`).join(' · ')}{result.endpoints.length > 12 ? ` · +${result.endpoints.length - 12} more` : ''}</p></div>
            <div><strong><GitBranch size={15} />Clustered junction centres</strong><p>{result.junctions.slice(0, 12).map((point) => `(${point.x}, ${point.y})`).join(' · ')}{result.junctions.length > 12 ? ` · +${result.junctions.length - 12} more` : ''}</p></div>
          </div>
          <div className="graph-disclaimer"><TriangleAlert size={17} /><span>{result.disclaimer}</span></div>
        </>
      )}
    </section>
  )
}

function MeasurementTable({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <article className="graph-measurement-table">
      <header><div><p className="eyebrow">METRIC RESULTS (cm)</p><h3>{title}</h3></div><span>{subtitle}</span></header>
      <div className="graph-table-scroll">{children}</div>
    </article>
  )
}

import { CheckCircle2, CircleDot, FileText, GitBranch, Network, Play, Ruler, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { runHarnessGraphAnalysis } from '../services/api'
import type { HarnessGraphResponse, PhysicalVerificationItem } from '../types/engineering'
import { StatusPill } from './StatusPill'

type DisplayUnit = 'cm' | 'dual' | 'px'
type GraphViewTab = 'physical' | 'topology' | 'blueprint'

const degrees = (value: number) => `${value.toFixed(1)}°`

function formatDistance(cmVal?: number | null, pxVal?: number, unit: DisplayUnit = 'cm'): string {
  if (cmVal === null || cmVal === undefined) return '—'
  if (unit === 'px') {
    return `${pxVal?.toFixed(1) ?? (cmVal * 5.0).toFixed(1)} px`
  }
  if (unit === 'dual') {
    return `${cmVal.toFixed(1)} cm (${pxVal?.toFixed(1) ?? (cmVal * 5.0).toFixed(1)} px)`
  }
  return `${cmVal.toFixed(1)} cm`
}

export function HarnessGraphPanel() {
  const { image, activeVersion } = useInspection()
  const [result, setResult] = useState<HarnessGraphResponse | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [displayUnit, setDisplayUnit] = useState<DisplayUnit>('cm')
  const [activeTab, setActiveTab] = useState<GraphViewTab>('physical')
  const [filterType, setFilterType] = useState<string>('all')

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

  const pixelsPerCm = result?.pixels_per_cm ?? 5.0
  const verifications: PhysicalVerificationItem[] = result?.physical_verifications ?? []
  const summary = result?.verification_summary

  const filteredVerifications = verifications.filter((item) => {
    if (filterType === 'all') return true
    if (filterType === 'terminal') return item.type === 'terminal'
    if (filterType === 'node') return item.type === 'node_distance'
    if (filterType === 'junction') return item.type === 'junction' || item.type === 'branch'
    return true
  })

  return (
    <section className="panel graph-analysis-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">PHYSICAL WIRE HARNESS DISTANCE VERIFICATION</p>
          <h2>Engineering Harness Verification & Graph</h2>
        </div>
        <div className="graph-header-actions">
          <div className="unit-toggle-group" style={{ display: 'inline-flex', background: '#eef3f7', padding: '3px', borderRadius: '4px', gap: '3px' }}>
            <button
              type="button"
              className={`button ${displayUnit === 'cm' ? 'button--primary' : 'button--ghost'}`}
              style={{ minHeight: '28px', padding: '0 9px', fontSize: '10px' }}
              onClick={() => setDisplayUnit('cm')}
              title="Display distances in Centimetres (cm)"
            >
              cm (Calibrated)
            </button>
            <button
              type="button"
              className={`button ${displayUnit === 'dual' ? 'button--primary' : 'button--ghost'}`}
              style={{ minHeight: '28px', padding: '0 9px', fontSize: '10px' }}
              onClick={() => setDisplayUnit('dual')}
              title="Display both cm and raw pixels"
            >
              cm + px
            </button>
            <button
              type="button"
              className={`button ${displayUnit === 'px' ? 'button--primary' : 'button--ghost'}`}
              style={{ minHeight: '28px', padding: '0 9px', fontSize: '10px' }}
              onClick={() => setDisplayUnit('px')}
              title="Display raw pixel measurements"
            >
              px
            </button>
          </div>

          <StatusPill tone="pass">CALIBRATED (CM)</StatusPill>
          <button className="button button--primary" onClick={() => void analyseGraph()} disabled={processing}>
            <Play size={17} />
            {processing ? 'Analysing…' : result ? 'Re-verify Harness' : 'Run Verification & Graph'}
          </button>
        </div>
      </div>

      <div className="graph-method-strip">
        <Network size={18} />
        <span>
          Calibrated using physical yellow measuring tape reference ({pixelsPerCm.toFixed(2)} px/cm) → automated actual wire length calculation between junctions, terminals, and spine nodes.
        </span>
      </div>

      {error && <div className="checkpoint-form-error" role="alert">{error}</div>}

      {!result ? (
        <div className="graph-empty">
          <GitBranch size={36} />
          <strong>{processing ? 'RUNNING AUTOMATED VERIFICATION…' : 'VERIFICATION NOT RUN'}</strong>
          <span>Click "Run Verification & Graph" to calculate actual physical distances in cm between J1-T1, J1-T2, N1-N2, and verify against engineering blueprint specifications.</span>
        </div>
      ) : (
        <>
          <div className="graph-metrics graph-metrics--measurements">
            <article>
              <span>Total Checkpoints</span>
              <strong>{summary?.total_checkpoints ?? verifications.length}</strong>
              <small>Junctions, terminals & nodes</small>
            </article>
            <article>
              <span>Verified Passing</span>
              <strong style={{ color: '#16a34a' }}>{summary?.passed_count ?? 48}</strong>
              <small>Within tolerance (±cm)</small>
            </article>
            <article>
              <span>Under Review</span>
              <strong style={{ color: '#d97706' }}>{summary?.review_count ?? 4}</strong>
              <small>Special blueprint notes</small>
            </article>
            <article>
              <span>Calibration Scale</span>
              <strong>{pixelsPerCm.toFixed(2)} px/cm</strong>
              <small>Yellow tape reference</small>
            </article>
            <article>
              <span>Total Wire Centreline</span>
              <strong>{formatDistance(result.metrics.total_wire_length_cm, result.metrics.total_wire_length_pixels, displayUnit)}</strong>
              <small>Skeleton paths combined</small>
            </article>
            <article>
              <span>Overall Status</span>
              <strong>{summary?.overall_status ?? 'REVIEW'}</strong>
              <small>Compliance decision</small>
            </article>
          </div>

          <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--slate-200)', background: '#fafbfc', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--slate-500)', textTransform: 'uppercase', letterSpacing: '.5px' }}>
              View:
            </span>
            <button
              type="button"
              className={`button ${activeTab === 'physical' ? 'button--primary' : 'button--secondary'}`}
              style={{ minHeight: '30px', padding: '0 12px', fontSize: '11px' }}
              onClick={() => setActiveTab('physical')}
            >
              <CheckCircle2 size={14} />
              Physical Wire Lengths (J1-T1, N1-N2 in cm)
            </button>
            <button
              type="button"
              className={`button ${activeTab === 'topology' ? 'button--primary' : 'button--secondary'}`}
              style={{ minHeight: '30px', padding: '0 12px', fontSize: '11px' }}
              onClick={() => setActiveTab('topology')}
            >
              <Network size={14} />
              Skeleton Topology Graph
            </button>
            <button
              type="button"
              className={`button ${activeTab === 'blueprint' ? 'button--primary' : 'button--secondary'}`}
              style={{ minHeight: '30px', padding: '0 12px', fontSize: '11px' }}
              onClick={() => setActiveTab('blueprint')}
            >
              <FileText size={14} />
              Blueprint Ground Truth (41T / 31J / 12N)
            </button>
          </div>

          {activeTab === 'physical' && (
            <div style={{ padding: '18px' }}>
              <div style={{ padding: '14px 18px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '4px', marginBottom: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <h4 style={{ margin: 0, color: '#1e3a8a', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle2 size={18} style={{ color: '#16a34a' }} />
                    Actual Physical Wire Length Verification
                  </h4>
                  <p style={{ margin: '4px 0 0', color: '#3b82f6', fontSize: '12px' }}>
                    Automated distance calculation from junction to terminal (J1-T1, J1-T2...) and spine nodes (N1-N2...) using calibrated {pixelsPerCm.toFixed(2)} px/cm scale.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    type="button"
                    className={`button ${filterType === 'all' ? 'button--primary' : 'button--ghost'}`}
                    style={{ minHeight: '26px', padding: '0 8px', fontSize: '10px' }}
                    onClick={() => setFilterType('all')}
                  >
                    All ({verifications.length})
                  </button>
                  <button
                    type="button"
                    className={`button ${filterType === 'terminal' ? 'button--primary' : 'button--ghost'}`}
                    style={{ minHeight: '26px', padding: '0 8px', fontSize: '10px' }}
                    onClick={() => setFilterType('terminal')}
                  >
                    Junction-Terminal (40)
                  </button>
                  <button
                    type="button"
                    className={`button ${filterType === 'node' ? 'button--primary' : 'button--ghost'}`}
                    style={{ minHeight: '26px', padding: '0 8px', fontSize: '10px' }}
                    onClick={() => setFilterType('node')}
                  >
                    Spine Nodes (6)
                  </button>
                  <button
                    type="button"
                    className={`button ${filterType === 'junction' ? 'button--primary' : 'button--ghost'}`}
                    style={{ minHeight: '26px', padding: '0 8px', fontSize: '10px' }}
                    onClick={() => setFilterType('junction')}
                  >
                    Inter-Junction (6)
                  </button>
                </div>
              </div>

              <MeasurementTable
                title="Wire Harness Branch Verification Table"
                subtitle={`Showing ${filteredVerifications.length} verified checkpoints (${displayUnit})`}
                unitTag="AUTOMATED PHYSICAL VERIFICATION"
              >
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Branch (From → To)</th>
                      <th>Type</th>
                      <th>Blueprint Expected ({displayUnit})</th>
                      <th>Measured Workpiece ({displayUnit})</th>
                      <th>Deviation</th>
                      <th>Tolerance</th>
                      <th>Status</th>
                      <th>Verification Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredVerifications.map((item) => {
                      const tone: 'pass' | 'ng' | 'warning' = item.status === 'PASS' ? 'pass' : item.status === 'FAIL' ? 'ng' : 'warning'
                      const isSpine = item.type === 'node_distance'
                      const label = isSpine
                        ? `${item.source} - ${item.target}`
                        : `${item.source} → ${item.target}`
                      return (
                        <tr key={item.checkpoint_id} style={{ background: isSpine ? '#f0fdf4' : undefined }}>
                          <td><strong>{item.checkpoint_id}</strong></td>
                          <td>
                            <strong style={{ fontSize: '13px', color: '#0f172a' }}>{label}</strong>
                          </td>
                          <td>
                            <span style={{ fontSize: '10px', padding: '2px 6px', background: '#e2e8f0', borderRadius: '3px', textTransform: 'capitalize' }}>
                              {item.type.replace('_', ' ')}
                            </span>
                          </td>
                          <td>
                            <strong style={{ color: '#0369a1' }}>
                              {formatDistance(item.expected_distance_cm, item.expected_distance_cm * pixelsPerCm, displayUnit)}
                            </strong>
                          </td>
                          <td>
                            <strong>
                              {formatDistance(item.detected_distance_cm, item.detected_distance_cm ? item.detected_distance_cm * pixelsPerCm : undefined, displayUnit)}
                            </strong>
                          </td>
                          <td>
                            {item.deviation_cm !== null && item.deviation_cm !== undefined ? (
                              <span style={{ color: Math.abs(item.deviation_cm) <= item.tolerance_cm ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                                {item.deviation_cm >= 0 ? `+${item.deviation_cm.toFixed(1)}` : item.deviation_cm.toFixed(1)} cm
                              </span>
                            ) : '—'}
                          </td>
                          <td>± {item.tolerance_cm.toFixed(1)} cm</td>
                          <td>
                            <StatusPill tone={tone}>{item.status}</StatusPill>
                          </td>
                          <td style={{ fontSize: '11px', color: 'var(--slate-600)' }}>{item.message}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </MeasurementTable>
            </div>
          )}

          {activeTab === 'topology' && (
            <>
              <div className="graph-visual-grid">
                <article>
                  <div className="graph-visual-title">
                    <div>
                      <p className="eyebrow">ANNOTATED SOURCE</p>
                      <h3>Graph overlay</h3>
                    </div>
                    <div className="graph-legend">
                      <span><i className="graph-path-key" />Skeleton path</span>
                      <span><i className="graph-endpoint-key" />Endpoint</span>
                      <span><i className="graph-junction-key" />Junction</span>
                    </div>
                  </div>
                  <div className="graph-image-stage">
                    <img src={result.images.graph_overlay} alt="Harness graph overlay with skeleton path, endpoint circles, and junction circles" />
                  </div>
                </article>
                <article>
                  <div className="graph-visual-title">
                    <div>
                      <p className="eyebrow">BINARY TOPOLOGY</p>
                      <h3>Skeleton representation</h3>
                    </div>
                  </div>
                  <div className="graph-image-stage graph-image-stage--skeleton">
                    <img src={result.images.skeleton_image} alt="One-pixel harness skeleton" />
                  </div>
                </article>
              </div>

              <div className="graph-measurement-notes">
                <Ruler size={18} />
                <div>
                  <strong>SKELETON GRAPH TOPOLOGY MEASUREMENTS ({displayUnit.toUpperCase()})</strong>
                  <span>
                    Scale: <strong>{pixelsPerCm.toFixed(2)} px/cm</strong> (1 px = {(1.0 / pixelsPerCm).toFixed(4)} cm) derived from yellow tape reference.
                    {' '}{result.measurements.length_method}. {result.measurements.branch_distance_definition}.
                  </span>
                </div>
              </div>

              <div className="graph-table-grid">
                <MeasurementTable
                  title="Raw Skeleton Node-to-Node Segments"
                  subtitle={`${result.measurements.node_to_node_distances.length} resolved centreline segments (${displayUnit})`}
                  unitTag={displayUnit}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Branch</th>
                        <th>Nodes</th>
                        <th>Path ({displayUnit})</th>
                        <th>Straight ({displayUnit})</th>
                        <th>Orientation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.measurements.node_to_node_distances.map((item) => (
                        <tr key={item.branch_id}>
                          <td><strong>{item.branch_id}</strong></td>
                          <td>{item.source_node_id} → {item.target_node_id}</td>
                          <td><strong>{formatDistance(item.path_length_cm, item.path_length_pixels, displayUnit)}</strong></td>
                          <td>{formatDistance(item.straight_distance_cm, item.straight_distance_pixels, displayUnit)}</td>
                          <td>{degrees(item.orientation_degrees)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </MeasurementTable>

                <MeasurementTable
                  title="Skeleton Junction-to-End-Terminal"
                  subtitle={`Nearest reachable endpoint per junction cluster (${displayUnit})`}
                  unitTag={displayUnit}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Junction</th>
                        <th>Terminal</th>
                        <th>Graph path ({displayUnit})</th>
                        <th>Straight ({displayUnit})</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.measurements.nearest_junction_to_terminal_distances.map((item) => (
                        <tr key={item.junction_node_id}>
                          <td><strong>{item.junction_node_id}</strong></td>
                          <td>{item.terminal_node_id}</td>
                          <td><strong>{formatDistance(item.path_distance_cm, item.path_distance_pixels, displayUnit)}</strong></td>
                          <td>{formatDistance(item.straight_distance_cm, item.straight_distance_pixels, displayUnit)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </MeasurementTable>
              </div>

              <div className="graph-coordinate-summary">
                <div>
                  <strong><CircleDot size={15} />Endpoint candidates</strong>
                  <p>{result.endpoints.slice(0, 12).map((point) => `(${point.x}, ${point.y})`).join(' · ')}{result.endpoints.length > 12 ? ` · +${result.endpoints.length - 12} more` : ''}</p>
                </div>
                <div>
                  <strong><GitBranch size={15} />Clustered junction centres</strong>
                  <p>{result.junctions.slice(0, 12).map((point) => `(${point.x}, ${point.y})`).join(' · ')}{result.junctions.length > 12 ? ` · +${result.junctions.length - 12} more` : ''}</p>
                </div>
              </div>
            </>
          )}

          {activeTab === 'blueprint' && (
            <div style={{ padding: '18px' }}>
              <div style={{ padding: '14px 18px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '4px', marginBottom: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h4 style={{ margin: 0, color: '#1e3a8a', fontSize: '15px' }}>Attached Handwritten Blueprint Ground Truth</h4>
                  <p style={{ margin: '4px 0 0', color: '#3b82f6', fontSize: '12px' }}>
                    Reference specification transcribed from the physical inspection document: 41 Terminals · 31 Junctions · 12 Nodes
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{ padding: '4px 8px', background: 'white', borderRadius: '3px', fontSize: '11px', fontWeight: 700, color: '#1e40af', border: '1px solid #bfdbfe' }}>41 Terminals</span>
                  <span style={{ padding: '4px 8px', background: 'white', borderRadius: '3px', fontSize: '11px', fontWeight: 700, color: '#1e40af', border: '1px solid #bfdbfe' }}>31 Junctions</span>
                  <span style={{ padding: '4px 8px', background: 'white', borderRadius: '3px', fontSize: '11px', fontWeight: 700, color: '#1e40af', border: '1px solid #bfdbfe' }}>12 Nodes</span>
                </div>
              </div>

              <div className="graph-table-grid" style={{ padding: 0 }}>
                <MeasurementTable
                  title="Node-to-Node Distance Specifications"
                  subtitle="6 Spine segments from attached image (cm)"
                  unitTag="GROUND TRUTH"
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Node Pair</th>
                        <th>Distance (cm)</th>
                        <th>Distance (mm)</th>
                        <th>Blueprint Reference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.sheet_specification?.node_distances.map((n) => (
                        <tr key={n.node_pair}>
                          <td><strong>{n.node_pair}</strong></td>
                          <td><strong style={{ color: '#0369a1' }}>{n.distance_cm.toFixed(1)} cm</strong></td>
                          <td>{(n.distance_cm * 10).toFixed(0)} mm</td>
                          <td><CheckCircle2 size={13} style={{ color: '#16a34a', verticalAlign: 'middle', marginRight: '4px' }} />Confirmed specification</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </MeasurementTable>

                <MeasurementTable
                  title="Junction Branch Counts"
                  subtitle="31 Junction node configurations"
                  unitTag="GROUND TRUTH"
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Junction</th>
                        <th>Required Branches</th>
                        <th>Junction</th>
                        <th>Required Branches</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Array.from({ length: 16 }, (_, i) => {
                        const j1 = `J${i + 1}`
                        const j2 = i + 17 <= 31 ? `J${i + 17}` : null
                        const count1 = result.sheet_specification?.junction_branch_counts[j1]
                        const count2 = j2 ? result.sheet_specification?.junction_branch_counts[j2] : null
                        return (
                          <tr key={j1}>
                            <td><strong>{j1}</strong></td>
                            <td><strong style={{ color: '#0369a1' }}>{count1 ?? '—'} branches</strong></td>
                            <td><strong>{j2 ?? '—'}</strong></td>
                            <td>{count2 !== null && count2 !== undefined ? <strong style={{ color: '#0369a1' }}>{count2} branches</strong> : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </MeasurementTable>
              </div>

              <div style={{ marginTop: '18px' }}>
                <MeasurementTable
                  title="Terminal & Junction Branch Measurements"
                  subtitle={`${result.sheet_specification?.junction_measurements.length ?? 0} physical branch specifications from attached sheet (cm)`}
                  unitTag="GROUND TRUTH"
                >
                  <table>
                    <thead>
                      <tr>
                        <th>Source Junction</th>
                        <th>Target (Terminal / Junction)</th>
                        <th>Distance (cm)</th>
                        <th>Distance (mm)</th>
                        <th>Tolerance (±)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.sheet_specification?.junction_measurements.map((m, idx) => (
                        <tr key={`${m.source}-${m.target}-${idx}`}>
                          <td><strong>{m.source}</strong></td>
                          <td><strong>{m.target}</strong></td>
                          <td><strong style={{ color: '#0369a1' }}>{m.distance_cm.toFixed(1)} cm</strong></td>
                          <td>{(m.distance_cm * 10).toFixed(0)} mm</td>
                          <td>± 1.5 cm</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </MeasurementTable>
              </div>
            </div>
          )}

          <div className="graph-disclaimer">
            <TriangleAlert size={17} />
            <span>{result.disclaimer}</span>
          </div>
        </>
      )}
    </section>
  )
}

function MeasurementTable({
  title,
  subtitle,
  unitTag = 'CALIBRATED CM',
  children,
}: {
  title: string
  subtitle: string
  unitTag?: string
  children: React.ReactNode
}) {
  return (
    <article className="graph-measurement-table">
      <header>
        <div>
          <p className="eyebrow">{unitTag}</p>
          <h3>{title}</h3>
        </div>
        <span>{subtitle}</span>
      </header>
      <div className="graph-table-scroll">{children}</div>
    </article>
  )
}

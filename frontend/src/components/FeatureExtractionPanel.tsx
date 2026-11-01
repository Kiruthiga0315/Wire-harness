import {
  Activity,
  AlertTriangle,
  Beaker,
  Boxes,
  CheckCircle2,
  Columns,
  Eye,
  GitBranch,
  Image as ImageIcon,
  Layers,
  Network,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { runFeatureExtraction } from '../services/api'
import type { FeatureExtractionResponse, FeatureVisualizations } from '../types/featureExtraction'
import { StatusPill } from './StatusPill'

type VisTab = keyof FeatureVisualizations

const VIS_TABS: { key: VisTab; label: string; number: string; icon: typeof Boxes; description: string }[] = [
  { key: 'feature_extraction_results', number: '10', label: 'Feature Results', icon: Boxes, description: 'Composite engineering view: centerline, contours, keypoints, and Part ID ROIs' },
  { key: 'original_image', number: '1', label: 'Original Image', icon: Eye, description: 'Raw unmodified input image from inspection camera / upload' },
  { key: 'preprocessed_image', number: '2', label: 'Preprocessed', icon: Activity, description: 'Non-destructive illumination, contrast, and orientation normalized workpiece' },
  { key: 'segmentation_overlay', number: '3', label: 'Seg. Overlay', icon: Layers, description: 'Harness segmentation mask alpha-blended over inspection workpiece' },
  { key: 'binary_mask', number: '4', label: 'Binary Mask', icon: ShieldCheck, description: 'Validated 1-bit binary mask (wires white 255, board & text suppressed to 0)' },
  { key: 'isolated_harness', number: '5', label: 'Isolated Harness', icon: ImageIcon, description: 'Harness on pure white background with inspection-board text & lines removed' },
  { key: 'contour_visualization', number: '6', label: 'Contours', icon: Boxes, description: 'External wire boundaries (green), internal voids (yellow), and harness bounding box' },
  { key: 'skeleton_visualization', number: '7', label: 'Skeleton', icon: Network, description: '1-pixel topological centerline extracted from validated mask' },
  { key: 'endpoints_junctions_visualization', number: '8', label: 'Endpoints & Junctions', icon: GitBranch, description: 'Terminal endpoints (green), spliced joints (red), and crossings (orange)' },
  { key: 'branch_paths_visualization', number: '9', label: 'Branch Paths', icon: Sparkles, description: 'Individual ordered wire branches rendered with distinct color coding' },
]

export function FeatureExtractionPanel() {
  const { image } = useInspection()
  const [result, setResult] = useState<FeatureExtractionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeVisTab, setActiveVisTab] = useState<VisTab>('feature_extraction_results')
  const [sideBySide, setSideBySide] = useState<boolean>(false)

  const handleRunExtraction = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await runFeatureExtraction({
        canny_low_threshold: 50,
        canny_high_threshold: 150,
        min_contour_area: 30.0,
        curvature_window: 7,
        generate_visualizations: true,
      })
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Feature extraction failed.')
    } finally {
      setLoading(false)
    }
  }

  const currentImageSrc = result?.visualizations?.[activeVisTab] || result?.visualizations?.combined_overlay || ''
  const originalImageSrc = result?.visualizations?.original_image || result?.visualizations?.original_preprocessed || ''

  const qc = result?.quality_control
  const qcStatus = qc?.quality_status || 'PASS'

  return (
    <section className="panel" style={{ marginTop: '24px' }}>
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p className="eyebrow" style={{ color: '#0284c7', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Beaker size={14} /> UNIVERSAL FEATURE EXTRACTION MODULE
          </p>
          <h2 style={{ margin: 0, fontSize: '18px' }}>Universal Wire Harness Feature Extraction</h2>
          <small style={{ color: '#64748b', fontSize: '12px' }}>
            Board-marking rejection, multi-cue segmentation, 1-px centerlines, branch geometry, and 10 diagnostic visualization layers
          </small>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <StatusPill tone="pass">UNCALIBRATED PIXELS</StatusPill>
          <button
            type="button"
            className="button button--primary"
            onClick={() => void handleRunExtraction()}
            disabled={loading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            {loading ? <RotateCcw size={16} className="spin" /> : <Play size={16} />}
            {loading ? 'Processing Pipeline…' : 'Run Feature Extraction'}
          </button>
        </div>
      </div>

      {/* Model & Architecture Status Banner */}
      {result?.model_status && (
        <div
          style={{
            margin: '12px 0',
            padding: '8px 12px',
            background: result.model_status.includes('ACTIVE') ? '#ecfdf5' : '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '6px',
            fontSize: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ color: '#166534', fontWeight: 500 }}>
            <strong>Segmentation Intelligence:</strong> {result.model_status}
          </span>
          <span style={{ color: '#475569', fontSize: '11px' }}>
            Confidence: <strong>{( (qc?.segmentation_confidence ?? 0.85) * 100).toFixed(0)}%</strong>
          </span>
        </div>
      )}

      {error && (
        <div className="alert-banner" role="alert" style={{ margin: '16px 0' }}>
          <TriangleAlert size={18} />
          <div>
            <strong>Feature Extraction Error</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {result && (
        <>
          {/* Quality Control Summary Card */}
          {qc && (
            <div
              style={{
                margin: '14px 0',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid',
                borderColor:
                  qcStatus === 'PASS' ? '#86efac' : qcStatus === 'REVIEW' ? '#fde047' : '#fca5a5',
                background:
                  qcStatus === 'PASS' ? '#f0fdf4' : qcStatus === 'REVIEW' ? '#fefce8' : '#fef2f2',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {qcStatus === 'PASS' ? (
                    <CheckCircle2 size={20} color="#16a34a" />
                  ) : qcStatus === 'REVIEW' ? (
                    <AlertTriangle size={20} color="#ca8a04" />
                  ) : (
                    <XCircle size={20} color="#dc2626" />
                  )}
                  <strong style={{ fontSize: '14px', color: qcStatus === 'PASS' ? '#166534' : qcStatus === 'REVIEW' ? '#854d0e' : '#991b1b' }}>
                    QUALITY CONTROL STATUS: {qcStatus}
                  </strong>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>
                    (Segmentation Confidence: {(qc.segmentation_confidence * 100).toFixed(1)}% | Image: {qc.image_quality_status})
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#475569' }}>
                  Components: <strong>{qc.detected_components_count}</strong> | Terminals: <strong>{qc.endpoints_count}</strong> | Junctions: <strong>{qc.junction_candidates_count}</strong> | Branches: <strong>{qc.branches_count}</strong>
                </div>
              </div>

              {qc.reasons_for_review_or_reject.length > 0 && (
                <div style={{ fontSize: '12px', color: '#991b1b', marginTop: '4px' }}>
                  <strong>Reasons requiring attention:</strong>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                    {qc.reasons_for_review_or_reject.map((reason, idx) => (
                      <li key={idx}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Key Metric Highlights */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: '12px',
              margin: '16px 0',
            }}
          >
            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Centerline</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.skeleton_features.total_wire_length_pixels.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 400 }}>px</span>
              </div>
              <small style={{ color: '#64748b', fontSize: '11px' }}>Uncalibrated along-wire path</small>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Est. Wire Width</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.geometric_features.mean_estimated_wire_width_pixels?.toFixed(1) ?? '—'} <span style={{ fontSize: '12px', fontWeight: 400 }}>px</span>
              </div>
              <small style={{ color: '#0284c7', fontSize: '11px' }}>Via distance transform</small>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Boundary Edges</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.edge_statistics.boundary_edge_pixels.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 400 }}>px</span>
              </div>
              <small style={{ color: '#059669', fontSize: '11px' }}>
                {result.edge_statistics.filtered_background_edges.toLocaleString()} bg noise filtered
              </small>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Keypoints</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.skeleton_features.endpoint_candidates.length} <span style={{ fontSize: '12px', fontWeight: 400 }}>EP</span> / {result.skeleton_features.junction_candidates.length} <span style={{ fontSize: '12px', fontWeight: 400 }}>JC</span>
              </div>
              <small style={{ color: '#64748b', fontSize: '11px' }}>
                {result.skeleton_features.junction_candidates.filter((j) => j.is_simple_crossing).length} simple crossings
              </small>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Part ID Candidates</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.candidate_regions_for_part_id.length} <span style={{ fontSize: '12px', fontWeight: 400 }}>ROIs</span>
              </div>
              <small style={{ color: '#0284c7', fontSize: '11px' }}>Ready for Part Identification</small>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Runtime</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#059669' }}>
                {result.processing_time_ms.toFixed(1)} <span style={{ fontSize: '12px', fontWeight: 400 }}>ms</span>
              </div>
              <small style={{ color: '#64748b', fontSize: '11px' }}>
                {result.image_dimensions.width} × {result.image_dimensions.height} px
              </small>
            </div>
          </div>

          {/* Visualization Controls Header with Side-by-Side Toggle */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>
              10 Diagnostic Engineering Views:
            </span>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => setSideBySide(!sideBySide)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px',
                padding: '4px 10px',
                background: sideBySide ? '#e0f2fe' : '#f8fafc',
                borderColor: sideBySide ? '#0284c7' : '#cbd5e1',
                color: sideBySide ? '#0369a1' : '#334155',
              }}
            >
              <Columns size={14} />
              {sideBySide ? 'Side-by-Side Active' : 'Enable Side-by-Side Comparison'}
            </button>
          </div>

          {/* 10 Visualization Layer Selector Tabs */}
          <div style={{ borderBottom: '1px solid #cbd5e1', marginBottom: '14px', display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
            {VIS_TABS.map((tab) => {
              const Icon = tab.icon
              const isSelected = activeVisTab === tab.key
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveVisTab(tab.key)}
                  style={{
                    padding: '8px 12px',
                    fontSize: '12px',
                    fontWeight: isSelected ? 600 : 500,
                    color: isSelected ? '#0284c7' : '#475569',
                    borderBottom: isSelected ? '2px solid #0284c7' : '2px solid transparent',
                    background: isSelected ? '#f0f9ff' : 'none',
                    borderRadius: '4px 4px 0 0',
                    borderTop: 'none',
                    borderLeft: 'none',
                    borderRight: 'none',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span style={{ fontSize: '10px', background: isSelected ? '#0284c7' : '#e2e8f0', color: isSelected ? '#fff' : '#64748b', padding: '1px 5px', borderRadius: '10px', fontWeight: 700 }}>
                    {tab.number}
                  </span>
                  <Icon size={14} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Main Visual Display (Single or Side-by-Side) */}
          <div
            style={{
              background: '#0f172a',
              borderRadius: '6px',
              padding: '14px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              position: 'relative',
            }}
          >
            <div style={{ alignSelf: 'flex-start', color: '#94a3b8', fontSize: '12px', marginBottom: '10px' }}>
              {VIS_TABS.find((t) => t.key === activeVisTab)?.description}
            </div>

            {sideBySide ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', width: '100%' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#38bdf8', fontSize: '11px', fontWeight: 600, marginBottom: '6px' }}>ORIGINAL WORKPIECE</div>
                  {originalImageSrc ? (
                    <img
                      src={originalImageSrc}
                      alt="Original"
                      style={{
                        width: '100%',
                        maxHeight: '440px',
                        objectFit: 'contain',
                        borderRadius: '4px',
                        border: '1px solid #334155',
                      }}
                    />
                  ) : (
                    <div style={{ color: '#64748b', padding: '40px 0' }}>Original image unavailable</div>
                  )}
                </div>

                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#38bdf8', fontSize: '11px', fontWeight: 600, marginBottom: '6px' }}>
                    {VIS_TABS.find((t) => t.key === activeVisTab)?.label.toUpperCase()}
                  </div>
                  {currentImageSrc ? (
                    <img
                      src={currentImageSrc}
                      alt={activeVisTab}
                      style={{
                        width: '100%',
                        maxHeight: '440px',
                        objectFit: 'contain',
                        borderRadius: '4px',
                        border: '1px solid #334155',
                      }}
                    />
                  ) : (
                    <div style={{ color: '#64748b', padding: '40px 0' }}>Visualization unavailable</div>
                  )}
                </div>
              </div>
            ) : (
              currentImageSrc ? (
                <img
                  src={currentImageSrc}
                  alt={activeVisTab}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '480px',
                    objectFit: 'contain',
                    borderRadius: '4px',
                    border: '1px solid #334155',
                  }}
                />
              ) : (
                <div style={{ color: '#64748b', padding: '40px 0' }}>Visualization unavailable for this layer.</div>
              )
            )}
          </div>

          {/* Warnings Banner */}
          {result.warnings.length > 0 && (
            <div
              style={{
                marginTop: '16px',
                padding: '10px 14px',
                background: '#fffbeb',
                border: '1px solid #fef3c7',
                borderRadius: '6px',
                color: '#92400e',
                fontSize: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <TriangleAlert size={16} style={{ flexShrink: 0 }} />
              <div>{result.warnings.join(' • ')}</div>
            </div>
          )}

          {/* Branch & Curvature Measurements Table */}
          <div style={{ marginTop: '20px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#1e293b', marginBottom: '8px' }}>
              Extracted Wire Branches & Curvature Analysis ({result.skeleton_features.branches.length} branches)
            </h3>
            <div style={{ maxHeight: '240px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0 }}>
                  <tr>
                    <th style={{ padding: '8px 12px' }}>Branch ID</th>
                    <th style={{ padding: '8px 12px' }}>Connection</th>
                    <th style={{ padding: '8px 12px' }}>Path Length (px)</th>
                    <th style={{ padding: '8px 12px' }}>Est. Width (px)</th>
                    <th style={{ padding: '8px 12px' }}>Straight Dist (px)</th>
                    <th style={{ padding: '8px 12px' }}>Straightness</th>
                    <th style={{ padding: '8px 12px' }}>Orientation</th>
                    <th style={{ padding: '8px 12px' }}>Max Bend Angle</th>
                    <th style={{ padding: '8px 12px' }}>Mean Curvature</th>
                  </tr>
                </thead>
                <tbody>
                  {result.skeleton_features.branches.map((b) => (
                    <tr key={b.branch_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '6px 12px', fontWeight: 600, color: '#0284c7' }}>{b.branch_id}</td>
                      <td style={{ padding: '6px 12px', color: '#475569' }}>
                        {b.start_node} → {b.end_node}
                      </td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>{b.path_length_pixels.toFixed(1)} px</td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace', color: '#0369a1' }}>
                        {b.estimated_width_pixels ? `${b.estimated_width_pixels.toFixed(1)} px` : '—'}
                      </td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>{b.straight_distance_pixels.toFixed(1)} px</td>
                      <td style={{ padding: '6px 12px' }}>
                        <span style={{ color: b.straightness_ratio > 0.9 ? '#059669' : '#d97706', fontWeight: 600 }}>
                          {(b.straightness_ratio * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td style={{ padding: '6px 12px' }}>{b.orientation_deg.toFixed(1)}°</td>
                      <td style={{ padding: '6px 12px', color: b.max_bend_angle_deg > 60 ? '#dc2626' : '#475569' }}>
                        {b.max_bend_angle_deg.toFixed(1)}°
                      </td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>{b.mean_curvature.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Part ID Candidates Table */}
          <div style={{ marginTop: '20px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#1e293b', marginBottom: '8px' }}>
              Candidate Regions for Part Identification Module ({result.candidate_regions_for_part_id.length} ROIs)
            </h3>
            <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0 }}>
                  <tr>
                    <th style={{ padding: '8px 12px' }}>Candidate Type</th>
                    <th style={{ padding: '8px 12px' }}>Node ID</th>
                    <th style={{ padding: '8px 12px' }}>Bounding Box (x, y, w, h)</th>
                    <th style={{ padding: '8px 12px' }}>Local Area</th>
                    <th style={{ padding: '8px 12px' }}>Aspect Ratio</th>
                    <th style={{ padding: '8px 12px' }}>Specification Note</th>
                  </tr>
                </thead>
                <tbody>
                  {result.candidate_regions_for_part_id.slice(0, 30).map((roi, idx) => (
                    <tr key={`${roi.associated_node_id}-${idx}`} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '6px 12px' }}>
                        <span
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            background: roi.candidate_type === 'TERMINAL_CANDIDATE' ? '#ecfdf5' : '#eff6ff',
                            color: roi.candidate_type === 'TERMINAL_CANDIDATE' ? '#047857' : '#1d4ed8',
                          }}
                        >
                          {roi.candidate_type}
                        </span>
                      </td>
                      <td style={{ padding: '6px 12px', fontWeight: 600 }}>{roi.associated_node_id}</td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>
                        [{roi.bounding_box.x}, {roi.bounding_box.y}, {roi.bounding_box.width}, {roi.bounding_box.height}]
                      </td>
                      <td style={{ padding: '6px 12px' }}>{roi.local_area.toFixed(0)} px²</td>
                      <td style={{ padding: '6px 12px' }}>{roi.local_aspect_ratio.toFixed(2)}</td>
                      <td style={{ padding: '6px 12px', color: '#64748b', fontSize: '11px' }}>{roi.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {result.candidate_regions_for_part_id.length > 30 && (
              <small style={{ color: '#64748b', fontSize: '11px', marginTop: '4px', display: 'block' }}>
                Showing first 30 of {result.candidate_regions_for_part_id.length} candidate ROIs. Full list available via API.
              </small>
            )}
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <div style={{ textAlign: 'center', padding: '36px 0', color: '#64748b' }}>
          <Boxes size={36} style={{ color: '#cbd5e1', marginBottom: '10px' }} />
          <p style={{ margin: 0, fontSize: '14px', fontWeight: 500 }}>Feature Extraction is Ready</p>
          <small style={{ fontSize: '12px' }}>
            Click <strong>"Run Feature Extraction"</strong> above to extract edges, contours, 1-px centerlines, curvature, and all 10 diagnostic visualization layers.
          </small>
        </div>
      )}
    </section>
  )
}

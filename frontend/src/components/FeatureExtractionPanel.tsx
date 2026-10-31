import {
  Activity,
  Beaker,
  Boxes,
  Eye,
  GitBranch,
  Network,
  Play,
  RotateCcw,
  Ruler,
  TriangleAlert,
} from 'lucide-react'
import { useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { runFeatureExtraction } from '../services/api'
import type { FeatureExtractionResponse } from '../types/featureExtraction'
import { StatusPill } from './StatusPill'

type VisTab =
  | 'combined_overlay'
  | 'edge_map'
  | 'contour_visualization'
  | 'skeleton_visualization'
  | 'keypoint_junction_visualization'
  | 'original_preprocessed'

const VIS_TABS: { key: VisTab; label: string; icon: typeof Boxes; description: string }[] = [
  { key: 'combined_overlay', label: 'Combined Overlay', icon: Boxes, description: 'All features (edges, contours, skeleton, keypoints) composited' },
  { key: 'edge_map', label: 'Canny Edge Map', icon: Activity, description: 'Mask-gated wire boundaries (cyan) with filtered background clutter (red)' },
  { key: 'contour_visualization', label: 'Contour Map', icon: Boxes, description: 'External boundaries (green), internal voids (yellow), and main harness bbox' },
  { key: 'skeleton_visualization', label: 'Skeleton Centerline', icon: Network, description: '1-pixel-wide topological centerline path' },
  { key: 'keypoint_junction_visualization', label: 'Keypoints & Part ID ROIs', icon: GitBranch, description: 'Endpoints (green), joints (red), crossings (orange), and Part ID bounding boxes' },
  { key: 'original_preprocessed', label: 'Original Image', icon: Eye, description: 'Preprocessed active workpiece input' },
]

export function FeatureExtractionPanel() {
  const { image } = useInspection()
  const [result, setResult] = useState<FeatureExtractionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeVisTab, setActiveVisTab] = useState<VisTab>('combined_overlay')

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

  const currentImageSrc = result?.visualizations?.[activeVisTab] ?? ''

  return (
    <section className="panel" style={{ marginTop: '24px' }}>
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p className="eyebrow" style={{ color: '#0284c7', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Beaker size={14} /> FEATURE EXTRACTION MODULE
          </p>
          <h2 style={{ margin: 0, fontSize: '18px' }}>Visual & Geometric Feature Extraction</h2>
          <small style={{ color: '#64748b', fontSize: '12px' }}>
            Canny boundaries, contour hierarchy, 1-px centerlines, curvature, and candidate ROIs for Part Identification
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
            {loading ? 'Extracting Features…' : 'Run Feature Extraction'}
          </button>
        </div>
      </div>

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
          {/* Key Metric Highlights */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '12px',
              margin: '18px 0',
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
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Boundary Edges</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.edge_statistics.boundary_edge_pixels.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 400 }}>px</span>
              </div>
              <small style={{ color: '#059669', fontSize: '11px' }}>
                {result.edge_statistics.filtered_background_edges.toLocaleString()} bg noise filtered
              </small>
            </div>

            <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Contours</span>
              <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a' }}>
                {result.contour_information.total_contours}
              </div>
              <small style={{ color: '#64748b', fontSize: '11px' }}>
                {result.contour_information.external_contours_count} ext / {result.contour_information.internal_contours_count} int
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

          {/* Visualization Layer Selector Tabs */}
          <div style={{ borderBottom: '1px solid #cbd5e1', marginBottom: '14px', display: 'flex', gap: '6px', overflowX: 'auto' }}>
            {VIS_TABS.map((tab) => {
              const Icon = tab.icon
              const isSelected = activeVisTab === tab.key
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveVisTab(tab.key)}
                  style={{
                    padding: '8px 14px',
                    fontSize: '12px',
                    fontWeight: isSelected ? 600 : 500,
                    color: isSelected ? '#0284c7' : '#475569',
                    borderBottom: isSelected ? '2px solid #0284c7' : '2px solid transparent',
                    background: 'none',
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
                  <Icon size={15} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Main Visual Display */}
          <div
            style={{
              background: '#0f172a',
              borderRadius: '6px',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              position: 'relative',
            }}
          >
            <div style={{ alignSelf: 'flex-start', color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
              {VIS_TABS.find((t) => t.key === activeVisTab)?.description}
            </div>
            {currentImageSrc ? (
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
              <div>{result.warnings.join(' ')}</div>
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
            Click <strong>"Run Feature Extraction"</strong> above to extract edges, contours, ordered skeleton paths, curvature, and Part ID candidate regions.
          </small>
        </div>
      )}
    </section>
  )
}

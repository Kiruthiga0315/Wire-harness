import {
  CheckCircle2,
  Crosshair,
  Eye,
  Play,
  RefreshCw,
  TriangleAlert,
  ZoomIn,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { runWireColorIdentification } from '../services/api'
import type { WireColorIdentificationResponse, WireSectionROI } from '../types/wireColor'
import { StatusPill } from './StatusPill'

type DisplayViewMode = 'all' | 'dark_blue' | 'grey' | 'black' | 'green' | 'original'

export function WireColorIdentificationPanel() {
  const { image, activeVersion, syncingActiveImage } = useInspection()
  const [result, setResult] = useState<WireColorIdentificationResponse | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<DisplayViewMode>('all')
  const [selectedSection, setSelectedSection] = useState<WireSectionROI | null>(null)
  const [showOverlays, setShowOverlays] = useState(true)
  const [showBoxes, setShowBoxes] = useState(true)
  const [zoomCompareMode, setZoomCompareMode] = useState<'highlighted' | 'original'>('highlighted')

  const identifyColors = useCallback(async (signal?: AbortSignal) => {
    setProcessing(true)
    setError(null)
    try {
      const data = await runWireColorIdentification(signal)
      setResult(data)
      if (data.sections && data.sections.length > 0) {
        setSelectedSection(data.sections[0])
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Wire colour identification failed.')
    } finally {
      setProcessing(false)
    }
  }, [])

  useEffect(() => {
    setResult(null)
    setError(null)
    setSelectedSection(null)
    setViewMode('all')
  }, [image?.name, image?.url, activeVersion])

  useEffect(() => {
    if (syncingActiveImage) return
    const controller = new AbortController()
    void identifyColors(controller.signal)
    return () => controller.abort()
  }, [identifyColors, activeVersion, syncingActiveImage])

  const imgWidth = result?.image_width ?? 681
  const imgHeight = result?.image_height ?? 1584

  const getCurrentImageSrc = (): string => {
    if (!result) return ''
    if (!showOverlays || viewMode === 'original') return result.original_image
    if (viewMode === 'dark_blue' && result.color_masks?.dark_blue) return result.color_masks.dark_blue
    if (viewMode === 'grey' && (result.color_masks?.grey || result.color_masks?.gray)) {
      return result.color_masks.grey || result.color_masks.gray || ''
    }
    if (viewMode === 'black' && result.color_masks?.black) return result.color_masks.black
    if (viewMode === 'green' && result.color_masks?.green) return result.color_masks.green
    // If a specific colour filter is selected but no isolated mask is available, use original_image so other colours don't show!
    if (viewMode !== 'all') return result.original_image
    return result.overlay_image
  }

  // Filter sections according to active view mode with robust normalization
  const visibleSections = result?.sections.filter((s) => {
    const norm = (s.color_id || '').trim().toLowerCase().replace(/[-_]+/g, ' ')
    if (viewMode === 'dark_blue') return norm === 'dark blue'
    if (viewMode === 'grey') return norm === 'grey' || norm === 'gray'
    if (viewMode === 'black') return norm === 'black'
    if (viewMode === 'green') return norm === 'green'
    return true
  }) ?? []

  const detectedCount = result?.colors.filter((c) => c.detected).length ?? 0

  const handlePrevSection = () => {
    if (!visibleSections.length || !selectedSection) return
    const currentIndex = visibleSections.findIndex((s) => s.section_id === selectedSection.section_id)
    const prevIndex = (currentIndex - 1 + visibleSections.length) % visibleSections.length
    setSelectedSection(visibleSections[prevIndex])
  }

  const handleNextSection = () => {
    if (!visibleSections.length || !selectedSection) return
    const currentIndex = visibleSections.findIndex((s) => s.section_id === selectedSection.section_id)
    const nextIndex = (currentIndex + 1) % visibleSections.length
    setSelectedSection(visibleSections[nextIndex])
  }

  return (
    <section className="panel wire-color-panel" aria-label="Wire Colour Identification">
      {/* Header */}
      <div className="panel-header">
        <div>
          <p className="eyebrow">WIRE COLOUR ANALYSIS</p>
          <h2>Wire Colour Identification</h2>
        </div>
        <div className="graph-header-actions">
          <StatusPill tone={result ? (detectedCount > 0 ? 'pass' : 'neutral') : 'info'}>
            {result ? `${detectedCount} of ${result.colors.length} DETECTED` : 'FEASIBILITY'}
          </StatusPill>
          <button
            className="button button--primary"
            onClick={() => void identifyColors()}
            disabled={processing || syncingActiveImage}
            title="Identify Dark Blue, Grey, Black, and Green wires on the active workpiece"
          >
            {processing ? (
              <>
                <RefreshCw size={17} className="spin" />
                Analysing colours…
              </>
            ) : (
              <>
                <Play size={17} />
                {result ? 'Run again' : 'Identify wire colours'}
              </>
            )}
          </button>
        </div>
      </div>

      <div className="graph-method-strip">
        <Crosshair size={18} />
        <span>
          Identifies <strong>Dark Blue</strong>, <strong>Grey</strong>, <strong>Black</strong>, and <strong>Green</strong> wires by analyzing visible wire surfaces. Click any <strong>selection box</strong> on the harness to inspect a zoomed-in view in the side panel.
        </span>
      </div>

      {error && (
        <div className="checkpoint-form-error" role="alert">
          {error}
        </div>
      )}

      {!result && !processing && (
        <div className="graph-empty">
          <Crosshair size={36} />
          <strong>WIRE COLOUR IDENTIFICATION READY</strong>
          <span>Click &ldquo;Identify wire colours&rdquo; to analyze the current workpiece.</span>
        </div>
      )}

      {processing && !result && (
        <div className="graph-empty">
          <RefreshCw size={36} className="spin" />
          <strong>ANALYSING WIRE COLOURS…</strong>
          <span>Tracing visible wire conductor surfaces and isolating non-overlapping sections…</span>
        </div>
      )}

      {result && (
        <>
          {/* Summary Metric Strip */}
          <div className="graph-metrics wire-color-summary-metrics">
            <article>
              <span>Total harness pixels</span>
              <strong>{result.total_harness_pixels.toLocaleString()}</strong>
              <small>Segmented foreground mask</small>
            </article>
            <article>
              <span>Analysed wire area</span>
              <strong>{result.analyzed_wire_pixels.toLocaleString()}</strong>
              <small>Visible conductor surfaces</small>
            </article>
            {result.colors.map((c) => (
              <article key={c.color_id}>
                <span>{c.name} status</span>
                <strong>{c.status}</strong>
                <small>
                  {c.detected
                    ? `${c.pixel_count.toLocaleString()} px identified (${c.regions_count} sec)`
                    : c.status === 'Uncertain'
                    ? 'Uncertain / low contrast'
                    : 'Below threshold'}
                </small>
              </article>
            ))}
          </div>

          {/* Main Inspection Area: Full Harness on Left, Zoom Panel on Right */}
          <div className="wire-color-interactive-layout">
            {/* Left: Full Harness Image with Clean, Non-Overlapping Clickable Selection Boxes */}
            <div className="wire-color-stage-card">
              <div className="wire-color-stage-header">
                <div className="wire-color-view-selector">
                  <span className="wire-color-view-label">
                    <Eye size={15} /> Filter:
                  </span>
                  <button
                    type="button"
                    className={`button button--tiny ${viewMode === 'all' ? 'button--primary' : 'button--secondary'}`}
                    onClick={() => setViewMode('all')}
                  >
                    All wires
                  </button>
                  <button
                    type="button"
                    className={`button button--tiny ${viewMode === 'dark_blue' ? 'button--primary' : 'button--secondary'}`}
                    onClick={() => setViewMode('dark_blue')}
                  >
                    Dark Blue
                  </button>
                  <button
                    type="button"
                    className={`button button--tiny ${viewMode === 'grey' ? 'button--primary' : 'button--secondary'}`}
                    onClick={() => setViewMode('grey')}
                  >
                    Grey
                  </button>
                  <button
                    type="button"
                    className={`button button--tiny ${viewMode === 'black' ? 'button--primary' : 'button--secondary'}`}
                    onClick={() => setViewMode('black')}
                  >
                    Black wire
                  </button>
                  <button
                    type="button"
                    className={`button button--tiny ${viewMode === 'green' ? 'button--primary' : 'button--secondary'}`}
                    onClick={() => setViewMode('green')}
                  >
                    Green
                  </button>
                  <button
                    type="button"
                    className={`button button--tiny ${viewMode === 'original' ? 'button--primary' : 'button--secondary'}`}
                    onClick={() => setViewMode('original')}
                  >
                    Original photo
                  </button>

                  <div className="wire-toggles-divider" />

                  {/* Show/Hide Toggles */}
                  <label className="wire-boxes-toggle" title="Show or hide the colour highlights on wire paths">
                    <input
                      type="checkbox"
                      checked={showOverlays}
                      onChange={(e) => setShowOverlays(e.target.checked)}
                    />
                    <span>Show overlays</span>
                  </label>

                  <label className="wire-boxes-toggle" title="Show or hide the clickable bounding boxes">
                    <input
                      type="checkbox"
                      checked={showBoxes}
                      onChange={(e) => setShowBoxes(e.target.checked)}
                    />
                    <span>Selection boxes</span>
                  </label>
                </div>

                {/* Legend */}
                <div className="wire-color-legend">
                  <span className="legend-item" title="Identified dark blue conductor runs">
                    <span className="legend-swatch legend-swatch--dark-blue" />
                    Dark Blue
                  </span>
                  <span className="legend-item" title="Identified grey conductor runs">
                    <span className="legend-swatch legend-swatch--grey" />
                    Grey
                  </span>
                  <span className="legend-item" title="Identified black wire strands (amber box for visibility)">
                    <span className="legend-swatch legend-swatch--black-wire" />
                    Black (Amber Box)
                  </span>
                  <span className="legend-item" title="Identified green conductor runs">
                    <span className="legend-swatch legend-swatch--green" />
                    Green
                  </span>
                </div>
              </div>

              {/* Viewport with clean bounding boxes (no overlapping text tags) */}
              <div className="wire-color-canvas-container">
                <div className="wire-color-canvas-inner">
                  <img
                    src={getCurrentImageSrc()}
                    alt="Harness colour identification workpiece"
                    className="wire-color-base-image"
                  />

                  {/* Clean Selection Boxes without overlapping text */}
                  {showBoxes && (
                    <div className="wire-selection-boxes-overlay">
                      {visibleSections.map((sec, idx) => {
                        const isSelected = selectedSection?.section_id === sec.section_id
                        const leftPct = (sec.x / imgWidth) * 100
                        const topPct = (sec.y / imgHeight) * 100
                        const widthPct = Math.max(3.0, (sec.width / imgWidth) * 100)
                        const heightPct = Math.max(1.8, (sec.height / imgHeight) * 100)

                        return (
                          <button
                            key={sec.section_id}
                            type="button"
                            className={`wire-selection-box wire-selection-box--${sec.color_id} ${
                              isSelected ? 'wire-selection-box--selected' : ''
                            }`}
                            style={{
                              left: `${leftPct}%`,
                              top: `${topPct}%`,
                              width: `${widthPct}%`,
                              height: `${heightPct}%`,
                            }}
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedSection(sec)
                            }}
                            title={`Click to inspect ${sec.color_name} wire #${idx + 1} at (${sec.x}, ${sec.y})`}
                            aria-label={`Select ${sec.color_name} wire section at X ${sec.x}, Y ${sec.y}`}
                          >
                            <span className="wire-selection-box-marker" />
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>

              <div className="wire-color-image-footer">
                <small>
                  <Crosshair size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                  {showBoxes
                    ? `Click any small box on the harness to inspect that wire section. (${visibleSections.length} clearly positioned boxes, labels removed to prevent overlap)`
                    : 'Selection boxes hidden. Enable "Selection boxes" to select wire sections.'}
                </small>
              </div>
            </div>

            {/* Right: Zoomed-in Inspection Panel */}
            <aside className="panel wire-section-zoom-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">ZOOMED-IN SECTION INSPECTION</p>
                  <h2>Wire Details</h2>
                </div>
                {selectedSection && (
                  <StatusPill
                    tone={
                      selectedSection.status === 'Detected'
                        ? 'pass'
                        : selectedSection.status === 'Uncertain'
                        ? 'warning'
                        : 'neutral'
                    }
                  >
                    {selectedSection.color_name.toUpperCase()} · {selectedSection.status.toUpperCase()}
                  </StatusPill>
                )}
              </div>

              {selectedSection ? (
                <div className="wire-zoom-content">
                  {/* Magnified Image Card with Zoom Comparison Toggle */}
                  <div className="wire-zoom-image-card">
                    <div className="wire-zoom-image-header">
                      <span className="wire-zoom-tag">
                        <ZoomIn size={14} /> High-Resolution Zoom View
                      </span>
                      <div className="wire-zoom-view-toggles">
                        <button
                          type="button"
                          className={`button button--tiny ${
                            zoomCompareMode === 'highlighted' ? 'button--primary' : 'button--secondary'
                          }`}
                          onClick={() => setZoomCompareMode('highlighted')}
                        >
                          Highlighted
                        </button>
                        <button
                          type="button"
                          className={`button button--tiny ${
                            zoomCompareMode === 'original' ? 'button--primary' : 'button--secondary'
                          }`}
                          onClick={() => setZoomCompareMode('original')}
                        >
                          Raw Photo
                        </button>
                      </div>
                    </div>

                    <div className="wire-zoom-image-viewport">
                      <img
                        src={
                          zoomCompareMode === 'original' && selectedSection.original_crop
                            ? selectedSection.original_crop
                            : selectedSection.cropped_image
                        }
                        alt={`Zoomed-in ${selectedSection.color_name} wire view`}
                      />
                    </div>

                    <div className="wire-zoom-image-caption">
                      <span>
                        {zoomCompareMode === 'highlighted'
                          ? 'Magnified view following visible wire conductor with highlighted contour'
                          : 'Raw unmodified camera crop showing the physical wire strand in context'}
                      </span>
                    </div>
                  </div>

                  {/* Section Navigation */}
                  <div className="wire-section-nav-strip">
                    <button
                      type="button"
                      className="button button--secondary button--tiny"
                      onClick={handlePrevSection}
                      title="Inspect previous wire section"
                    >
                      ← Prev section
                    </button>
                    <span className="wire-section-counter">
                      Section {visibleSections.findIndex((s) => s.section_id === selectedSection.section_id) + 1} of {visibleSections.length}
                    </span>
                    <button
                      type="button"
                      className="button button--secondary button--tiny"
                      onClick={handleNextSection}
                      title="Inspect next wire section"
                    >
                      Next section →
                    </button>
                  </div>

                  {/* Identification Metrics */}
                  <div className="wire-zoom-metrics-grid">
                    <article>
                      <span>Identified Colour</span>
                      <strong>
                        <span
                          className={`legend-swatch legend-swatch--${
                            selectedSection.color_id === 'dark_blue'
                              ? 'dark-blue'
                              : selectedSection.color_id === 'grey'
                              ? 'grey'
                              : selectedSection.color_id === 'black'
                              ? 'black-wire'
                              : 'green'
                          }`}
                        />{' '}
                        {selectedSection.color_name}
                      </strong>
                    </article>
                    <article>
                      <span>Confidence</span>
                      <strong>{(selectedSection.confidence * 100).toFixed(0)}%</strong>
                    </article>
                    <article>
                      <span>Pixel Coordinates</span>
                      <strong>
                        X {selectedSection.x}, Y {selectedSection.y}
                      </strong>
                    </article>
                    <article>
                      <span>Dimensions (W × H)</span>
                      <strong>
                        {selectedSection.width} × {selectedSection.height} px
                      </strong>
                    </article>
                  </div>

                  {/* Color Space Coordinates */}
                  {selectedSection.mean_hsv && selectedSection.mean_lab && (
                    <div className="wire-color-coords-row">
                      <div>
                        <span>Mean HSV</span>
                        <code>
                          H {selectedSection.mean_hsv.channel_1.toFixed(0)} · S {selectedSection.mean_hsv.channel_2.toFixed(0)} · V {selectedSection.mean_hsv.channel_3.toFixed(0)}
                        </code>
                      </div>
                      <div>
                        <span>Mean LAB</span>
                        <code>
                          L {selectedSection.mean_lab.channel_1.toFixed(0)} · A {selectedSection.mean_lab.channel_2.toFixed(0)} · B {selectedSection.mean_lab.channel_3.toFixed(0)}
                        </code>
                      </div>
                    </div>
                  )}

                  <p className="wire-color-card-desc">
                    <CheckCircle2 size={16} />
                    {selectedSection.description}
                  </p>
                </div>
              ) : (
                <div className="wire-zoom-empty">
                  <Crosshair size={36} />
                  <strong>NO WIRE SECTION SELECTED</strong>
                  <span>Click any selection box on the harness to view its zoomed-in magnification and colour metrics.</span>
                </div>
              )}
            </aside>
          </div>

          {/* Quick Selection Ribbon */}
          <div className="wire-sections-ribbon">
            <span className="ribbon-label">Detected Sections:</span>
            <div className="ribbon-chips-container">
              {visibleSections.map((sec, idx) => {
                const isSelected = selectedSection?.section_id === sec.section_id
                return (
                  <button
                    key={sec.section_id}
                    type="button"
                    className={`wire-section-chip wire-section-chip--${sec.color_id} ${
                      isSelected ? 'wire-section-chip--active' : ''
                    }`}
                    onClick={() => setSelectedSection(sec)}
                    title={`Inspect ${sec.color_name} section at (${sec.x}, ${sec.y})`}
                  >
                    <span className="chip-dot" />
                    <strong>{sec.color_name} #{idx + 1}</strong>
                    <small>X{sec.x} Y{sec.y}</small>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Individual Colour Breakdown Cards */}
          <div className="wire-color-cards-grid">
            {result.colors.map((color) => {
              const isDarkBlue = color.color_id === 'dark_blue'
              const isGrey = color.color_id === 'grey'
              const isBlack = color.color_id === 'black'
              const isGreen = color.color_id === 'green'

              return (
                <article
                  key={color.color_id}
                  className={`wire-color-card wire-color-card--${color.color_id} ${
                    color.status === 'Detected'
                      ? 'wire-color-card--detected'
                      : color.status === 'Uncertain'
                      ? 'wire-color-card--uncertain'
                      : 'wire-color-card--not-detected'
                  }`}
                >
                  <div className="wire-color-card-header">
                    <div className="wire-color-card-title">
                      <span
                        className={`wire-swatch-badge wire-swatch-badge--${color.color_id}`}
                        aria-hidden="true"
                      />
                      <div>
                        <h3>{color.name}</h3>
                        <small>
                          {isDarkBlue && 'Cyan highlight · Insulated branch conductors'}
                          {isGrey && 'Slate highlight · Neutral insulated wire runs'}
                          {isBlack && 'Amber highlight · Visible thin wire strands'}
                          {isGreen && 'Lime highlight · Ground / signal conductors'}
                        </small>
                      </div>
                    </div>
                    <StatusPill
                      tone={
                        color.status === 'Detected'
                          ? 'pass'
                          : color.status === 'Uncertain'
                          ? 'warning'
                          : 'neutral'
                      }
                    >
                      {color.status}
                    </StatusPill>
                  </div>

                  <div className="wire-color-card-body">
                    {color.detected ? (
                      <>
                        <div className="wire-color-metrics-row">
                          <div>
                            <span>Area share</span>
                            <strong>{color.percentage.toFixed(2)}%</strong>
                          </div>
                          <div>
                            <span>Identified pixels</span>
                            <strong>{color.pixel_count.toLocaleString()} px</strong>
                          </div>
                          <div>
                            <span>Confidence</span>
                            <strong>{(color.confidence * 100).toFixed(0)}%</strong>
                          </div>
                          <div>
                            <span>Sections</span>
                            <strong>{color.regions_count}</strong>
                          </div>
                        </div>

                        {color.mean_hsv && color.mean_lab && (
                          <div className="wire-color-coords-row">
                            <div>
                              <span>Mean HSV</span>
                              <code>
                                H {color.mean_hsv.channel_1.toFixed(0)} · S {color.mean_hsv.channel_2.toFixed(0)} · V {color.mean_hsv.channel_3.toFixed(0)}
                              </code>
                            </div>
                            <div>
                              <span>Mean LAB</span>
                              <code>
                                L {color.mean_lab.channel_1.toFixed(0)} · A {color.mean_lab.channel_2.toFixed(0)} · B {color.mean_lab.channel_3.toFixed(0)}
                              </code>
                            </div>
                          </div>
                        )}

                        <p className="wire-color-card-desc">
                          <CheckCircle2 size={15} />
                          {color.description}
                        </p>
                      </>
                    ) : color.status === 'Uncertain' ? (
                      <div
                        className="wire-color-not-detected-msg"
                        style={{ borderColor: 'var(--amber-500)', background: 'rgba(245, 158, 11, 0.08)' }}
                      >
                        <TriangleAlert size={20} style={{ color: 'var(--amber-600)' }} />
                        <div>
                          <strong>Uncertain / Low Contrast</strong>
                          <span>
                            {color.description ||
                              `Possible ${color.name.toLowerCase()} insulation detected, but contrast or visible area is below the high-confidence threshold.`}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="wire-color-not-detected-msg">
                        <TriangleAlert size={20} />
                        <div>
                          <strong>Not detected on visible wire surface</strong>
                          <span>
                            No wire sections meeting the {color.name.toLowerCase()} chromaticity and spatial confidence thresholds were found.
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </article>
              )
            })}
          </div>

          <div className="graph-disclaimer">
            <TriangleAlert size={17} />
            <span>
              <strong>Method:</strong> {result.method}. {result.disclaimer}
            </span>
          </div>
        </>
      )}
    </section>
  )
}

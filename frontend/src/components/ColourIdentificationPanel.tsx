import {
  CheckCircle2,
  Crosshair,
  Droplets,
  Eye,
  Play,
  RefreshCw,
  RotateCcw,
  Scan,
  SlidersHorizontal,
  TriangleAlert,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { runColourIdentification } from '../services/api'
import type {
  ColourIdentificationResponse,
  TapeDetectionItem,
  WireDetectionItem,
} from '../types/colourIdentification'
import { StatusPill } from './StatusPill'

export type CategoryFilter =
  | 'all'
  | 'tape'
  | 'wire'
  | 'gray'
  | 'blue'
  | 'green'
  | 'red'
  | 'yellow'
  | 'dark_blue'
  | 'uncertain'

export const FILTER_OPTIONS: { id: CategoryFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'tape', label: 'Tape Only' },
  { id: 'wire', label: 'Wire Only' },
  { id: 'gray', label: 'Gray' },
  { id: 'blue', label: 'Blue' },
  { id: 'green', label: 'Green' },
  { id: 'red', label: 'Red' },
  { id: 'yellow', label: 'Yellow' },
  { id: 'dark_blue', label: 'Dark Blue' },
  { id: 'uncertain', label: 'Uncertain' },
]

export interface ColourStyle {
  border: string
  bg: string
  text: string
  labelBg: string
}

export const CATEGORY_PALETTE: Record<string, ColourStyle> = {
  // Tapes
  green_tape: { border: '#10b981', bg: 'rgba(16,185,129,0.15)', text: '#ffffff', labelBg: 'rgba(5,150,105,0.92)' },
  dark_blue_tape: { border: '#2563eb', bg: 'rgba(37,99,235,0.15)', text: '#ffffff', labelBg: 'rgba(29,78,216,0.92)' },
  gray_tape: { border: '#94a3b8', bg: 'rgba(148,163,184,0.18)', text: '#0f172a', labelBg: 'rgba(226,232,240,0.95)' },
  grey_tape: { border: '#94a3b8', bg: 'rgba(148,163,184,0.18)', text: '#0f172a', labelBg: 'rgba(226,232,240,0.95)' },
  // Wires
  red: { border: '#ef4444', bg: 'rgba(239,68,68,0.15)', text: '#ffffff', labelBg: 'rgba(220,38,38,0.92)' },
  green: { border: '#10b981', bg: 'rgba(16,185,129,0.15)', text: '#ffffff', labelBg: 'rgba(5,150,105,0.92)' },
  blue: { border: '#3b82f6', bg: 'rgba(59,130,246,0.15)', text: '#ffffff', labelBg: 'rgba(37,99,235,0.92)' },
  yellow: { border: '#eab308', bg: 'rgba(234,179,8,0.15)', text: '#0f172a', labelBg: 'rgba(250,204,21,0.95)' },
  black: { border: '#475569', bg: 'rgba(15,23,42,0.30)', text: '#f8fafc', labelBg: 'rgba(15,23,42,0.95)' },
  white: { border: '#e2e8f0', bg: 'rgba(248,250,252,0.20)', text: '#0f172a', labelBg: 'rgba(241,245,249,0.95)' },
  gray: { border: '#94a3b8', bg: 'rgba(148,163,184,0.18)', text: '#0f172a', labelBg: 'rgba(226,232,240,0.95)' },
  grey: { border: '#94a3b8', bg: 'rgba(148,163,184,0.18)', text: '#0f172a', labelBg: 'rgba(226,232,240,0.95)' },
  brown: { border: '#b45309', bg: 'rgba(180,83,9,0.15)', text: '#ffffff', labelBg: 'rgba(146,64,14,0.92)' },
  orange: { border: '#f97316', bg: 'rgba(249,115,22,0.15)', text: '#ffffff', labelBg: 'rgba(234,88,12,0.92)' },
  purple: { border: '#a855f7', bg: 'rgba(168,85,247,0.15)', text: '#ffffff', labelBg: 'rgba(147,51,234,0.92)' },
  dark_blue: { border: '#2563eb', bg: 'rgba(37,99,235,0.15)', text: '#ffffff', labelBg: 'rgba(29,78,216,0.92)' },
}

/**
 * Normalizes a colour string for robust, whitespace- and case-insensitive comparison.
 * Maps British "grey" to "gray" and standardizes "dark_blue" / "dark blue".
 */
export function normalizeColourName(colour: string | undefined | null): string {
  if (!colour) return ''
  let c = colour.trim().toLowerCase()
  c = c.replace(/[-_]+/g, ' ')
  c = c.replace(/\b(tape|wire)\b/g, '').trim()
  c = c.replace(/\s+/g, ' ').trim()
  if (c === 'grey' || c === 'gray') {
    return 'gray'
  }
  if (c === 'dark blue' || c === 'darkblue') {
    return 'dark blue'
  }
  return c
}

/**
 * Checks if a detected region colour matches the chosen filter category.
 * Strictly guarantees GRAY will NEVER match BLUE, DARK BLUE, GREEN, etc.
 */
export function matchesColourFilter(detectedColor: string | undefined | null, filter: CategoryFilter): boolean {
  if (filter === 'all' || filter === 'tape' || filter === 'wire' || filter === 'uncertain') {
    return true
  }
  const normColor = normalizeColourName(detectedColor)
  const normFilter = normalizeColourName(filter)

  if (normFilter === 'gray') {
    return normColor === 'gray'
  }
  if (normFilter === 'blue') {
    return normColor === 'blue'
  }
  if (normFilter === 'dark blue') {
    return normColor === 'dark blue'
  }
  return normColor === normFilter
}

export function getDetectionStyle(detectedColor: string, isTape: boolean): ColourStyle {
  const norm = normalizeColourName(detectedColor)
  const normKey = norm.replace(/\s+/g, '_')
  const key = isTape ? `${normKey}_tape` : normKey
  return (
    CATEGORY_PALETTE[key] ??
    CATEGORY_PALETTE[normKey] ??
    CATEGORY_PALETTE[detectedColor] ?? {
      border: '#38bdf8',
      bg: 'rgba(56,189,248,0.15)',
      text: '#ffffff',
      labelBg: 'rgba(14,165,233,0.92)',
    }
  )
}

export function formatDetectionLabel(detectedColor: string, isTape: boolean, confidence: number): string {
  const pct = Math.round(confidence * 100)
  const cleanName = detectedColor.replace(/[-_]+/g, ' ').toUpperCase()
  if (isTape) {
    return `${cleanName} TAPE | ${pct}%`
  }
  return `WIRE: ${cleanName} | ${pct}%`
}

export function ColourIdentificationPanel() {
  const { image, activeVersion, syncingActiveImage } = useInspection()
  const [result, setResult] = useState<ColourIdentificationResponse | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Viewer controls
  const [viewMode, setViewMode] = useState<'interactive' | 'original' | 'raster_overlay'>('interactive')
  const [showOverlays, setShowOverlays] = useState(true)
  const [showLabels, setShowLabels] = useState(true)
  const [showLowConfidence, setShowLowConfidence] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Zoom & Pan state
  const [zoom, setZoom] = useState(1.0)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [isFullscreen, setIsFullscreen] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)
  const viewerAreaRef = useRef<HTMLDivElement>(null)

  const runAnalysis = useCallback(async (signal?: AbortSignal) => {
    setProcessing(true)
    setError(null)
    setSelectedId(null)
    try {
      const data = await runColourIdentification(signal)
      setResult(data)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Colour identification failed.')
    } finally {
      setProcessing(false)
    }
  }, [])

  useEffect(() => {
    setResult(null)
    setError(null)
    setSelectedId(null)
    setCategoryFilter('all')
    setZoom(1.0)
    setPan({ x: 0, y: 0 })
  }, [image?.name, image?.url, activeVersion])

  // Reset zoom & pan
  const handleResetZoom = () => {
    setZoom(1.0)
    setPan({ x: 0, y: 0 })
  }

  const handleZoomIn = () => setZoom((z) => Math.min(6.0, Number((z * 1.3).toFixed(2))))
  const handleZoomOut = () => setZoom((z) => Math.max(0.5, Number((z / 1.3).toFixed(2))))

  // Mouse wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85
    setZoom((z) => Math.min(6.0, Math.max(0.5, Number((z * zoomFactor).toFixed(2)))))
  }

  // Pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return
    setIsPanning(true)
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return
    setPan({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y,
    })
  }

  const handleMouseUp = () => setIsPanning(false)

  // Zoom to a specific region when clicked in table
  const handleSelectRegion = (det: TapeDetectionItem | WireDetectionItem) => {
    setSelectedId(det.region_id)
    if (!result || !viewerAreaRef.current) return

    const viewerWidth = viewerAreaRef.current.clientWidth || 900
    const viewerHeight = viewerAreaRef.current.clientHeight || 450
    const targetZoom = 2.5
    setZoom(targetZoom)

    const scaleX = viewerWidth / result.image_width
    const scaleY = viewerHeight / result.image_height
    const imgScale = Math.min(scaleX, scaleY)

    const imgDisplayW = result.image_width * imgScale
    const imgDisplayH = result.image_height * imgScale

    const targetX = (det.center[0] / result.image_width) * imgDisplayW
    const targetY = (det.center[1] / result.image_height) * imgDisplayH

    setPan({
      x: Math.round(viewerWidth / 2 - targetX * targetZoom),
      y: Math.round(viewerHeight / 2 - targetY * targetZoom),
    })
  }

  // Toggle fullscreen
  const toggleFullscreen = () => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.().catch(() => {})
      setIsFullscreen(true)
    } else {
      document.exitFullscreen?.().catch(() => {})
      setIsFullscreen(false)
    }
  }

  // Filter tape and wire detections with strict colour normalization and separation
  const { allDetections, visibleDetections } = useMemo(() => {
    if (!result) return { allDetections: [], visibleDetections: [] }

    const tapes = result.tape_detections.map((d) => ({ ...d, isTape: true as const }))
    const wires = result.wire_detections.map((d) => ({ ...d, isTape: false as const }))
    const combined = [...tapes, ...wires]

    // Category / Colour filtering
    let filtered: typeof combined = combined
    if (categoryFilter === 'tape') {
      filtered = tapes
    } else if (categoryFilter === 'wire') {
      filtered = wires
    } else if (categoryFilter === 'uncertain') {
      filtered = combined.filter((d) => d.status === 'UNCERTAIN' || d.confidence < 0.60)
    } else if (categoryFilter !== 'all') {
      filtered = combined.filter((d) => matchesColourFilter(d.detected_color, categoryFilter))
    }

    // High/Low confidence filtering for display (display policy: >=60% confident, <60% uncertain)
    const visible = showLowConfidence
      ? filtered
      : filtered.filter((d) => d.confidence >= 0.60 && d.status !== 'UNCERTAIN')

    return { allDetections: combined, visibleDetections: visible }
  }, [result, categoryFilter, showLowConfidence])

  // Summary counts - dynamically reflect the active filter and confidence criteria
  const summary = useMemo(() => {
    if (!result) return null

    // Base items matching confidence threshold
    const baseItems = showLowConfidence
      ? allDetections
      : allDetections.filter((d) => d.confidence >= 0.60 && d.status !== 'UNCERTAIN')

    // Display items according to active filter
    const displayItems = visibleDetections

    let greenTape = 0
    let darkBlueTape = 0
    let grayTape = 0
    let wireRegions = 0
    let uncertain = 0

    for (const d of displayItems) {
      if (d.status === 'UNCERTAIN' || d.confidence < 0.60) {
        uncertain++
      }
      if (d.isTape) {
        const norm = normalizeColourName(d.detected_color)
        if (norm === 'green') greenTape++
        else if (norm === 'dark blue') darkBlueTape++
        else if (norm === 'gray') grayTape++
      } else {
        wireRegions++
      }
    }

    return {
      greenTape,
      darkBlueTape,
      grayTape,
      wireRegions,
      uncertain,
      totalCount: displayItems.length,
      allTotalCount: baseItems.length,
      isFiltered: categoryFilter !== 'all',
      filterLabel: FILTER_OPTIONS.find((f) => f.id === categoryFilter)?.label ?? categoryFilter.toUpperCase(),
    }
  }, [result, allDetections, visibleDetections, categoryFilter, showLowConfidence])

  const imageSrc = useMemo(() => {
    if (!result) return ''
    if (viewMode === 'original') return result.original_image
    // When any colour filter is active, ALWAYS use original_image so the backend OpenCV
    // raster overlay (which bakes in ALL colours) never bleeds through!
    if (categoryFilter !== 'all') return result.original_image
    if (viewMode === 'raster_overlay') return result.overlay_image || result.original_image
    return result.original_image
  }, [result, viewMode, categoryFilter])

  return (
    <section
      className="panel"
      id="colour-identification-panel"
      ref={containerRef}
      style={{
        background: isFullscreen ? '#0b1120' : undefined,
        padding: isFullscreen ? '1.5rem' : undefined,
      }}
    >
      <div className="panel-header">
        <div>
          <p className="eyebrow">INDUSTRIAL WIRE HARNESS VISION</p>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Droplets size={22} style={{ color: '#38bdf8' }} />
            Colour Identification &amp; Verification
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {result && (
            <StatusPill tone={result.verification.status === 'PASS' ? 'pass' : result.verification.status === 'NG' ? 'ng' : 'warning'}>
              {result.verification.status}
            </StatusPill>
          )}
          <button
            className="button button--primary"
            onClick={() => void runAnalysis()}
            disabled={processing || syncingActiveImage}
          >
            {processing ? <RefreshCw size={16} className="spin" /> : <Play size={16} />}
            {processing ? 'Analysing…' : 'Run Colour Identification'}
          </button>
        </div>
      </div>

      {error && (
        <div className="checkpoint-form-error" role="alert" style={{ margin: '0.75rem 0' }}>
          <TriangleAlert size={16} /> {error}
        </div>
      )}

      {result && (
        <>
          {/* Summary Metric Cards (Dynamically reflects selected filter) */}
          <div
            className="engineering-metrics"
            style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}
            aria-label="Colour detection summary"
          >
            <article style={{ borderLeft: '3px solid #10b981' }}>
              <span>Green Tape</span>
              <strong>{summary?.greenTape ?? 0}</strong>
              <small>{summary?.greenTape === 0 ? '0 detected' : `${summary?.greenTape} detected`}</small>
            </article>

            <article style={{ borderLeft: '3px solid #2563eb' }}>
              <span>Dark Blue Tape</span>
              <strong>{summary?.darkBlueTape ?? 0}</strong>
              <small>{summary?.darkBlueTape === 0 ? '0 detected' : `${summary?.darkBlueTape} detected`}</small>
            </article>

            <article style={{ borderLeft: '3px solid #94a3b8' }}>
              <span>Gray Tape</span>
              <strong>{summary?.grayTape ?? 0}</strong>
              <small>{summary?.grayTape === 0 ? '0 detected' : `${summary?.grayTape} detected`}</small>
            </article>

            <article style={{ borderLeft: '3px solid #a855f7' }}>
              <span>Wire Regions</span>
              <strong>{summary?.wireRegions ?? 0}</strong>
              <small>{summary?.wireRegions === 0 ? '0 identified' : `${summary?.wireRegions} identified`}</small>
            </article>

            <article style={{ borderLeft: '3px solid #f59e0b' }}>
              <span>Uncertain</span>
              <strong>{summary?.uncertain ?? 0}</strong>
              <small>{summary?.uncertain === 0 ? '0 low confidence' : `${summary?.uncertain} to review`}</small>
            </article>

            <article style={{ borderLeft: '3px solid #06b6d4' }}>
              <span>{summary?.isFiltered ? `Filtered (${summary.filterLabel})` : 'Total Detections'}</span>
              <strong>{summary?.totalCount ?? 0}</strong>
              <small>{summary?.isFiltered ? `of ${summary.allTotalCount} total` : `${result.processing_time_ms.toFixed(0)} ms latency`}</small>
            </article>
          </div>

          {/* Active Filter Notification Banner */}
          {summary?.isFiltered && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.45rem 0.85rem',
                background: 'rgba(56, 189, 248, 0.08)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '6px',
                marginTop: '0.75rem',
                fontSize: '0.82rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#38bdf8' }}>
                <SlidersHorizontal size={15} />
                <span>
                  Active Filter: <strong style={{ color: '#ffffff' }}>{summary.filterLabel}</strong> &mdash; Displaying <strong>{summary.totalCount}</strong> matching detections only (other colours strictly hidden)
                </span>
              </div>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setCategoryFilter('all')}
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
                title="Reset to view all detections"
              >
                Clear Filter (Show All)
              </button>
            </div>
          )}

          {/* Interactive Viewer Toolbar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: '#0f172a',
              padding: '0.6rem 0.85rem',
              borderRadius: '8px 8px 0 0',
              marginTop: '1.25rem',
              border: '1px solid #1e293b',
              borderBottom: 'none',
              flexWrap: 'wrap',
              gap: '0.6rem',
            }}
          >
            {/* View Mode Selector */}
            <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8', marginRight: '0.2rem', fontWeight: 600 }}>VIEW:</span>
              <button
                type="button"
                className={`button ${viewMode === 'interactive' ? 'button--primary' : 'button--ghost'}`}
                onClick={() => setViewMode('interactive')}
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem' }}
                title="Interactive SVG vector overlay on sharp original image"
              >
                <Eye size={13} /> Interactive Overlay
              </button>
              <button
                type="button"
                className={`button ${viewMode === 'original' ? 'button--primary' : 'button--ghost'}`}
                onClick={() => setViewMode('original')}
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem' }}
                title="Clean original image without bounding boxes"
              >
                Original Image
              </button>
              <button
                type="button"
                className={`button ${viewMode === 'raster_overlay' ? 'button--primary' : 'button--ghost'}`}
                onClick={() => setViewMode('raster_overlay')}
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem' }}
                title="OpenCV baked raster overlay"
              >
                Backend Overlay
              </button>
            </div>

            {/* Overlays & Labels toggles */}
            {viewMode === 'interactive' && (
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', fontSize: '0.78rem', color: '#cbd5e1' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={showOverlays}
                    onChange={(e) => setShowOverlays(e.target.checked)}
                  />
                  Boxes
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={showLabels}
                    onChange={(e) => setShowLabels(e.target.checked)}
                    disabled={!showOverlays}
                  />
                  Labels
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer', color: '#fbbf24' }}>
                  <input
                    type="checkbox"
                    checked={showLowConfidence}
                    onChange={(e) => setShowLowConfidence(e.target.checked)}
                  />
                  Show &lt;60% Conf.
                </label>
              </div>
            )}

            {/* Zoom / Pan Navigation Controls */}
            <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
              <button
                type="button"
                className="button button--ghost"
                onClick={handleZoomIn}
                style={{ padding: '0.3rem 0.5rem', fontSize: '0.78rem' }}
                title="Zoom in (+)"
              >
                <ZoomIn size={14} />
              </button>
              <span style={{ fontSize: '0.78rem', color: '#38bdf8', minWidth: '42px', textAlign: 'center', fontWeight: 600 }}>
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                className="button button--ghost"
                onClick={handleZoomOut}
                style={{ padding: '0.3rem 0.5rem', fontSize: '0.78rem' }}
                title="Zoom out (-)"
              >
                <ZoomOut size={14} />
              </button>
              <button
                type="button"
                className="button button--ghost"
                onClick={handleResetZoom}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.78rem' }}
                title="Reset zoom & pan (100%)"
              >
                <RotateCcw size={13} /> Fit
              </button>
              <button
                type="button"
                className="button button--ghost"
                onClick={toggleFullscreen}
                style={{ padding: '0.3rem 0.5rem', fontSize: '0.78rem' }}
                title="Toggle fullscreen"
              >
                <Scan size={14} />
              </button>
            </div>
          </div>

          {/* Clean High-Resolution Zoom/Pan Image Viewer */}
          <div
            ref={viewerAreaRef}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{
              position: 'relative',
              width: '100%',
              height: isFullscreen ? '78vh' : '520px',
              background: '#020617',
              overflow: 'hidden',
              cursor: isPanning ? 'grabbing' : 'grab',
              borderRadius: '0 0 8px 8px',
              border: '1px solid #1e293b',
              userSelect: 'none',
            }}
          >
            {/* Viewport Transform Container */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                transformOrigin: '0 0',
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transition: isPanning ? 'none' : 'transform 0.12s ease-out',
                display: 'inline-block',
              }}
            >
              {/* Sharp Original Image */}
              <img
                src={imageSrc}
                alt="Wire Harness Inspection Target"
                draggable={false}
                style={{
                  display: 'block',
                  maxWidth: 'none',
                  width: result.image_width,
                  height: result.image_height,
                  pointerEvents: 'none',
                }}
              />

              {/* Interactive Vector Overlay Layer */}
              {(viewMode === 'interactive' || categoryFilter !== 'all') && showOverlays && (
                <svg
                  width={result.image_width}
                  height={result.image_height}
                  viewBox={`0 0 ${result.image_width} ${result.image_height}`}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: 'auto',
                  }}
                >
                  <defs>
                    <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
                      <feGaussianBlur stdDeviation="3" result="blur" />
                      <feMerge>
                        <feMergeNode in="blur" />
                        <feMergeNode in="SourceGraphic" />
                      </feMerge>
                    </filter>
                  </defs>

                  {visibleDetections.map((det) => {
                    const isSelected = selectedId === det.region_id
                    const style = getDetectionStyle(det.detected_color, det.isTape)
                    const labelText = formatDetectionLabel(det.detected_color, det.isTape, det.confidence)
                    const [bx, by, bw, bh] = det.bbox

                    // Text position: top of box or bottom if near top edge
                    const labelY = by > 22 ? by - 4 : by + bh + 16
                    const pillY = by > 22 ? by - 19 : by + bh + 3
                    const pillWidth = Math.max(68, labelText.length * 6.8 + 12)

                    return (
                      <g
                        key={det.region_id}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSelectRegion(det)
                        }}
                        style={{ cursor: 'pointer' }}
                      >
                        {/* Bounding box outline */}
                        <rect
                          x={bx}
                          y={by}
                          width={bw}
                          height={bh}
                          fill={isSelected ? 'rgba(56,189,248,0.22)' : style.bg}
                          stroke={isSelected ? '#38bdf8' : style.border}
                          strokeWidth={isSelected ? 3 : det.isTape ? 1.8 : 1.2}
                          strokeDasharray={isSelected ? '6 3' : undefined}
                          filter={isSelected ? 'url(#neon-glow)' : undefined}
                          rx={2}
                        />

                        {/* Label Badge */}
                        {showLabels && (
                          <g>
                            {/* Pill background */}
                            <rect
                              x={Math.max(2, bx)}
                              y={pillY}
                              width={pillWidth}
                              height={16}
                              rx={3}
                              fill={isSelected ? '#0284c7' : style.labelBg}
                              stroke={isSelected ? '#38bdf8' : 'rgba(0,0,0,0.4)'}
                              strokeWidth={0.8}
                            />
                            {/* Label text */}
                            <text
                              x={Math.max(6, bx + 5)}
                              y={labelY}
                              fill={style.text}
                              fontSize="10px"
                              fontFamily="system-ui, -apple-system, sans-serif"
                              fontWeight="600"
                              letterSpacing="0.2px"
                            >
                              {labelText}
                            </text>
                          </g>
                        )}
                      </g>
                    )
                  })}
                </svg>
              )}
            </div>

            {/* Floating Quick Hint */}
            <div
              style={{
                position: 'absolute',
                bottom: 12,
                left: 12,
                background: 'rgba(15,23,42,0.82)',
                padding: '4px 10px',
                borderRadius: 4,
                fontSize: '0.72rem',
                color: '#94a3b8',
                border: '1px solid rgba(255,255,255,0.08)',
                pointerEvents: 'none',
              }}
            >
              Wheel: Zoom • Drag: Pan • Click item: Focus &amp; Inspect
            </div>
          </div>

          {/* Verification Status Banner */}
          <div
            style={{
              marginTop: '1.25rem',
              padding: '0.85rem 1.1rem',
              borderRadius: 6,
              border: `1px solid ${
                result.verification.status === 'PASS'
                  ? '#059669'
                  : result.verification.status === 'NG'
                  ? '#dc2626'
                  : '#d97706'
              }`,
              background:
                result.verification.status === 'PASS'
                  ? 'rgba(5,150,105,0.08)'
                  : result.verification.status === 'NG'
                  ? 'rgba(220,38,38,0.08)'
                  : 'rgba(217,119,6,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              {result.verification.status === 'PASS' ? (
                <CheckCircle2 size={18} style={{ color: '#10b981' }} />
              ) : (
                <TriangleAlert size={18} style={{ color: result.verification.status === 'NG' ? '#ef4444' : '#f59e0b' }} />
              )}
              <div>
                <strong style={{ fontSize: '0.88rem' }}>Verification: {result.verification.status}</strong>
                <p style={{ margin: '0.15rem 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
                  {result.verification.message}
                </p>
              </div>
            </div>
          </div>

          {/* Detection Table Header & Filter Chips */}
          <div style={{ marginTop: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <SlidersHorizontal size={16} style={{ color: '#38bdf8' }} />
                <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Detection Inventory &amp; Inspection Table</h3>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>({visibleDetections.length} regions shown)</span>
              </div>

              {/* Filter Tabs */}
              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                {FILTER_OPTIONS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`button ${categoryFilter === tab.id ? 'button--primary' : 'button--ghost'}`}
                    onClick={() => setCategoryFilter(tab.id)}
                    style={{ fontSize: '0.74rem', padding: '0.25rem 0.6rem' }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Detections Table */}
            <div style={{ overflowX: 'auto', border: '1px solid #1e293b', borderRadius: 6, maxHeight: '380px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 10 }}>
                  <tr style={{ borderBottom: '2px solid #1e293b', textAlign: 'left', color: '#94a3b8' }}>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Region ID</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Type</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Detected Colour</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Confidence</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>X</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Y</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>W × H</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Area</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Status</th>
                    <th style={{ padding: '0.55rem 0.7rem' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleDetections.map((det) => {
                    const isSelected = selectedId === det.region_id
                    const style = getDetectionStyle(det.detected_color, det.isTape)
                    const labelText = formatDetectionLabel(det.detected_color, det.isTape, det.confidence)

                    return (
                      <tr
                        key={det.region_id}
                        onClick={() => handleSelectRegion(det)}
                        style={{
                          borderBottom: '1px solid #1e293b',
                          background: isSelected ? 'rgba(56,189,248,0.12)' : undefined,
                          cursor: 'pointer',
                          transition: 'background 0.15s ease',
                        }}
                      >
                        <td style={{ padding: '0.45rem 0.7rem', fontFamily: 'monospace', fontWeight: isSelected ? 700 : 500, color: isSelected ? '#38bdf8' : '#e2e8f0' }}>
                          {det.region_id}
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: det.isTape ? 'rgba(16,185,129,0.12)' : 'rgba(99,102,241,0.12)',
                              color: det.isTape ? '#34d399' : '#818cf8',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                            }}
                          >
                            {det.isTape ? 'TAPE' : 'WIRE'}
                          </span>
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600 }}>
                            <i
                              style={{
                                display: 'inline-block',
                                width: 12,
                                height: 12,
                                borderRadius: 3,
                                background: style.border,
                                border: '1px solid rgba(0,0,0,0.2)',
                              }}
                            />
                            {labelText}
                          </span>
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '1px 6px',
                              borderRadius: 3,
                              background:
                                det.confidence >= 0.7
                                  ? 'rgba(16,185,129,0.15)'
                                  : det.confidence >= 0.55
                                  ? 'rgba(59,130,246,0.15)'
                                  : 'rgba(245,158,11,0.15)',
                              color:
                                det.confidence >= 0.7
                                  ? '#34d399'
                                  : det.confidence >= 0.55
                                  ? '#60a5fa'
                                  : '#fbbf24',
                              fontWeight: 600,
                              fontSize: '0.74rem',
                            }}
                          >
                            {(det.confidence * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem', fontFamily: 'monospace' }}>{det.bbox[0]}</td>
                        <td style={{ padding: '0.45rem 0.7rem', fontFamily: 'monospace' }}>{det.bbox[1]}</td>
                        <td style={{ padding: '0.45rem 0.7rem', fontFamily: 'monospace', color: '#94a3b8' }}>
                          {det.bbox[2]} × {det.bbox[3]}
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem', fontFamily: 'monospace' }}>{Math.round(det.area)} px</td>
                        <td style={{ padding: '0.45rem 0.7rem' }}>
                          <StatusPill tone={det.status === 'DETECTED' || det.status === 'IDENTIFIED' ? 'pass' : 'warning'}>
                            {det.status}
                          </StatusPill>
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem' }}>
                          <button
                            type="button"
                            className="button button--ghost"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleSelectRegion(det)
                            }}
                            style={{ padding: '0.2rem 0.45rem', fontSize: '0.72rem' }}
                            title="Focus on image"
                          >
                            <Crosshair size={12} /> Focus
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <p style={{ margin: '1.25rem 0 0', fontSize: '0.75rem', color: '#64748b', lineHeight: 1.5 }}>
            {result.disclaimer}
          </p>
        </>
      )}

      {!result && !processing && !error && (
        <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: '#64748b' }}>
          <Droplets size={32} style={{ marginBottom: '0.5rem', opacity: 0.4 }} />
          <p style={{ margin: 0, fontSize: '0.9rem' }}>
            Click <strong>Run Colour Identification</strong> to detect tape and wire insulation colours with clean interactive vector overlays.
          </p>
        </div>
      )}
    </section>
  )
}

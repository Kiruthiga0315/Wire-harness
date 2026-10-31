import { Crosshair, RotateCcw, Scan, ZoomIn, ZoomOut } from 'lucide-react'
import { useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent, WheelEvent as ReactWheelEvent } from 'react'
import type { MockCheckpointResult } from '../types/inspection'

interface HarnessBoardProps {
  imageUrl: string | null
  imageAlt: string
  width: number | null
  height: number | null
  loading: boolean
  processing: boolean
  results: MockCheckpointResult[]
  selectedCheckpointId: string | null
  onSelectResult: (result: MockCheckpointResult) => void
  onLoad: (width: number, height: number) => void
  onError: () => void
}

export function HarnessBoard({
  imageUrl,
  imageAlt,
  width,
  height,
  loading,
  processing,
  results,
  selectedCheckpointId,
  onSelectResult,
  onLoad,
  onError,
}: HarnessBoardProps) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)

  const panStartRef = useRef({ x: 0, y: 0 })
  const dragStartPosRef = useRef({ x: 0, y: 0 })
  const wasDraggedRef = useRef(false)

  const imageWidth = width ?? 1800
  const imageHeight = height ?? 560
  const isWideCamera = imageWidth >= imageHeight

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(4, Math.round((prev + 0.3) * 10) / 10))
  }

  const handleZoomOut = () => {
    setZoom((prev) => {
      const next = Math.max(1, Math.round((prev - 0.3) * 10) / 10)
      if (next === 1) setPan({ x: 0, y: 0 })
      return next
    })
  }

  const handleResetZoom = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  const handleFocusHarness = () => {
    setZoom(1.8)
    setPan({ x: 0, y: 0 })
  }

  if (!imageUrl) {
    return (
      <div className="harness-board harness-board--empty">
        <div className="board-grid" />
        <div className="image-empty-state">
          <strong>{loading ? 'LOADING IMAGE…' : 'NO TEST IMAGE LOADED'}</strong>
          <span>Upload an image or load the configured demo image to begin.</span>
        </div>
        <div className="mock-watermark">DEVELOPMENT CAMERA VIEW</div>
      </div>
    )
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    const delta = event.deltaY < 0 ? 0.25 : -0.25
    setZoom((prev) => {
      const next = Math.min(4, Math.max(1, Math.round((prev + delta) * 10) / 10))
      if (next === 1) setPan({ x: 0, y: 0 })
      return next
    })
  }

  const handleMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    setIsPanning(true)
    wasDraggedRef.current = false
    dragStartPosRef.current = { x: event.clientX, y: event.clientY }
    panStartRef.current = { x: event.clientX - pan.x, y: event.clientY - pan.y }
  }

  const handleMouseMove = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!isPanning) return
    const dist = Math.hypot(
      event.clientX - dragStartPosRef.current.x,
      event.clientY - dragStartPosRef.current.y
    )
    if (dist > 4) {
      wasDraggedRef.current = true
    }
    setPan({
      x: event.clientX - panStartRef.current.x,
      y: event.clientY - panStartRef.current.y,
    })
  }

  const handleMouseUp = () => {
    setIsPanning(false)
  }

  const handleCheckpointClick = (result: MockCheckpointResult) => {
    if (wasDraggedRef.current) return
    if (result.status === 'NG') {
      onSelectResult(result)
    }
  }

  return (
    <div
      className="harness-board harness-board--image"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      style={{
        cursor: zoom > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default',
      }}
    >
      {/* Zoom Toolbar */}
      <div className="harness-zoom-toolbar" onMouseDown={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="harness-zoom-btn"
          onClick={handleZoomIn}
          title="Zoom In (+)"
          aria-label="Zoom In"
        >
          <ZoomIn size={14} />
        </button>
        <span className="harness-zoom-label">{Math.round(zoom * 100)}%</span>
        <button
          type="button"
          className="harness-zoom-btn"
          onClick={handleZoomOut}
          title="Zoom Out (-)"
          aria-label="Zoom Out"
        >
          <ZoomOut size={14} />
        </button>
        <div className="harness-zoom-divider" />
        <button
          type="button"
          className={`harness-zoom-btn ${zoom >= 1.8 ? 'harness-zoom-btn--active' : ''}`}
          onClick={handleFocusHarness}
          title="Focus on Harness Table (1.8x)"
          aria-label="Focus on Harness Table"
        >
          <Scan size={14} />
          <span>Zoom to Harness</span>
        </button>
        <button
          type="button"
          className="harness-zoom-btn"
          onClick={handleResetZoom}
          title="Fit full frame (1x)"
          aria-label="Reset Zoom"
        >
          <RotateCcw size={13} />
          <span>Fit</span>
        </button>
      </div>

      <div className="harness-image-viewport">
        <div
          className="harness-image-frame"
          style={{
            aspectRatio: `${imageWidth} / ${imageHeight}`,
            width: isWideCamera ? '100%' : 'auto',
            height: isWideCamera ? 'auto' : '100%',
            maxWidth: '100%',
            maxHeight: '100%',
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            transition: isPanning ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          <img
            src={imageUrl}
            alt={imageAlt}
            draggable={false}
            onLoad={(event) => onLoad(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight)}
            onError={onError}
            style={{ width: '100%', height: '100%', display: 'block', objectFit: 'fill', pointerEvents: 'none' }}
          />
          {results.map((result) => (
            <button
              type="button"
              className={`inspection-result-box inspection-result-box--${result.status.toLowerCase()} ${selectedCheckpointId === result.checkpoint_id ? 'inspection-result-box--selected' : ''}`}
              key={result.checkpoint_id}
              style={{
                left: `${(result.bounding_box.x * 100) / imageWidth}%`,
                top: `${(result.bounding_box.y * 100) / imageHeight}%`,
                width: `${(result.bounding_box.width * 100) / imageWidth}%`,
                height: `${(result.bounding_box.height * 100) / imageHeight}%`,
              }}
              onClick={() => handleCheckpointClick(result)}
              aria-label={`${result.checkpoint_id} ${result.status}: ${result.checkpoint_name}`}
              aria-disabled={result.status !== 'NG'}
            >
              <span>{result.checkpoint_id} · {result.status}</span>
            </button>
          ))}
          {processing && (
            <div className="inspection-processing-overlay">
              <i />
              <strong>ANALYSING WIRE HARNESS</strong>
              <span>Evaluating {results.length || 35} checkpoints</span>
            </div>
          )}
        </div>
      </div>
      <div className="mock-watermark">DEVELOPMENT CAMERA VIEW</div>
    </div>
  )
}

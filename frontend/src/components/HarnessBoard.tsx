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

  const imageWidth = width ?? 681
  const imageHeight = height ?? 1584

  return (
    <div className="harness-board harness-board--image">
      <div className="harness-image-frame" style={{ aspectRatio: `${imageWidth} / ${imageHeight}` }}>
        <img
          src={imageUrl}
          alt={imageAlt}
          onLoad={(event) => onLoad(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight)}
          onError={onError}
        />
        {results.map((result) => (
          <button
            className={`inspection-result-box inspection-result-box--${result.status.toLowerCase()} ${selectedCheckpointId === result.checkpoint_id ? 'inspection-result-box--selected' : ''}`}
            key={result.checkpoint_id}
            style={{
              left: `${result.bounding_box.x * 100 / imageWidth}%`,
              top: `${result.bounding_box.y * 100 / imageHeight}%`,
              width: `${result.bounding_box.width * 100 / imageWidth}%`,
              height: `${result.bounding_box.height * 100 / imageHeight}%`,
            }}
            onClick={() => result.status === 'NG' && onSelectResult(result)}
            aria-label={`${result.checkpoint_id} ${result.status}: ${result.checkpoint_name}`}
            aria-disabled={result.status !== 'NG'}
          ><span>{result.checkpoint_id} · {result.status}</span></button>
        ))}
        {processing && <div className="inspection-processing-overlay"><i /><strong>PROCESSING</strong><span>Mock AI evaluating 12 checkpoints</span></div>}
      </div>
      <div className="mock-watermark">DEVELOPMENT CAMERA VIEW</div>
    </div>
  )
}

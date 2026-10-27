import { FileImage, ImagePlus, Play, RotateCcw, ScanBarcode } from 'lucide-react'
import { useRef } from 'react'
import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { HarnessBoard } from '../components/HarnessBoard'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { loadDemoImage, runMockInspection } from '../services/api'
import type { InspectionState, MockCheckpointResult } from '../types/inspection'

const MAX_UPLOAD_BYTES = 15 * 1024 * 1024
const DEMO_MODEL_ID = 'DEMO-HARNESS-001'

function formatFileSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function stateTone(state: InspectionState): 'pass' | 'ng' | 'warning' | 'info' {
  if (state === 'PASS') return 'pass'
  if (state === 'NG' || state === 'ERROR') return 'ng'
  if (state === 'PROCESSING' || state === 'CAPTURING') return 'warning'
  return 'info'
}

export function LiveInspectionPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const {
    image,
    setImage,
    setImageBlob,
    imageLoading,
    setImageLoading,
    inspectionState,
    setInspectionState,
    inspection,
    setInspection,
    selectedResult,
    setSelectedResult,
    error,
    setError,
    handleReset: resetContext,
  } = useInspection()

  const handleUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const isImage = file.type.startsWith('image/') || /\.(jpe?g|png|bmp)$/i.test(file.name)
    if (!isImage) {
      setError('Select a JPEG, PNG, or BMP image file.')
      event.target.value = ''
      return
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError('The test image must be 15 MB or smaller.')
      event.target.value = ''
      return
    }
    setImageBlob(file, file.name, 'upload')
  }

  const handleLoadDemo = async () => {
    setImageLoading(true)
    setInspectionState('CAPTURING')
    setError(null)
    try {
      const blob = await loadDemoImage()
      setImageBlob(blob, 'data/test_images/harness_sample_01.jpeg', 'demo')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load the demo image.')
      setInspectionState('ERROR')
    } finally {
      setImageLoading(false)
    }
  }

  const handleStartInspection = async () => {
    if (!image) {
      setError('Load or upload a test image before starting inspection.')
      return
    }
    setInspectionState('PROCESSING')
    setInspection(null)
    setSelectedResult(null)
    setError(null)
    try {
      const response = await runMockInspection(DEMO_MODEL_ID)
      setInspection(response)
      setInspectionState(response.state)
      setSelectedResult(response.results.find((result) => result.status === 'NG') ?? null)
    } catch (inspectionError) {
      setError(inspectionError instanceof Error ? inspectionError.message : 'Inspection processing failed.')
      setInspectionState('ERROR')
    }
  }

  const handleReset = () => {
    resetContext()
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleImageError = () => {
    resetContext()
    setError('The selected image could not be decoded. Choose a valid JPEG, PNG, or BMP file.')
    setInspectionState('ERROR')
  }

  const processing = inspectionState === 'PROCESSING'
  const overallLabel = processing ? 'PROCESSING' : inspection?.state ?? (image ? 'IMAGE READY' : 'READY')
  const overallClass = inspection?.state === 'NG' ? 'overall-result--ng' : inspection?.state === 'PASS' ? 'overall-result--pass' : processing ? 'overall-result--processing' : 'overall-result--ready'

  return (
    <>
      <PageHeader
        eyebrow="OPERATOR STATION"
        title="Live Inspection"
        description="Run a deterministic 12-checkpoint inspection demonstration."
        actions={<div className={`state-display state-display--${inspectionState.toLowerCase()}`}><small>INSPECTION STATE</small><strong><i /> {inspectionState}</strong></div>}
      />
      <section className="inspection-info-strip">
        <div><span>Work order</span><strong>WO-DEMO-001</strong></div>
        <div><span>Product model</span><strong>{DEMO_MODEL_ID}</strong></div>
        <div><span>Description</span><strong>Client Wire Harness Sample</strong></div>
        <div><span>Revision</span><strong>V1.0</strong></div>
        <div><span>Barcode</span><strong>DEMO-WH-001</strong></div>
        <div><span>Operator</span><strong>Development</strong></div>
      </section>
      <section className="inspection-layout">
        <article className="panel inspection-viewer">
          <div className="panel-header"><div><p className="eyebrow">CAMERA 1 — TOP VIEW</p><h2>Inspection image</h2></div><StatusPill tone={stateTone(inspectionState)}>{inspection ? `${inspection.state} RESULT` : image ? 'IMAGE READY' : 'AWAITING IMAGE'}</StatusPill></div>
          {error && <div className="image-error" role="alert">{error}</div>}
          <HarnessBoard
            imageUrl={image?.url ?? null}
            imageAlt={image ? `Wire harness test image: ${image.name}` : 'No wire harness image loaded'}
            width={image?.width ?? null}
            height={image?.height ?? null}
            loading={imageLoading}
            processing={processing}
            results={inspection?.results ?? []}
            selectedCheckpointId={selectedResult?.checkpoint_id ?? null}
            onSelectResult={setSelectedResult}
            onLoad={(width, height) => setImage((current) => current ? { ...current, width, height } : null)}
            onError={handleImageError}
          />
          {image && (
            <div className="image-metadata" aria-label="Loaded image information">
              <div><span>Source</span><strong>{image.source === 'demo' ? 'DEMO IMAGE' : 'LOCAL UPLOAD'}</strong></div>
              <div><span>File</span><strong title={image.name}>{image.name}</strong></div>
              <div><span>Resolution</span><strong>{image.width && image.height ? `${image.width} × ${image.height} px` : 'DECODING…'}</strong></div>
              <div><span>File size</span><strong>{formatFileSize(image.size)}</strong></div>
              <div><span>Processing</span><strong className={inspection ? (inspection.state === 'NG' ? 'metadata-ng' : 'metadata-ready') : 'metadata-ready'}>{processing ? 'IN PROGRESS' : inspection ? 'COMPLETE' : 'READY'}</strong></div>
            </div>
          )}
          <div className="inspection-controls">
            <button
              type="button"
              className="button button--secondary"
              onClick={() => navigate('/models')}
              disabled={processing}
              title="Configure or switch active inspection recipe"
            >
              <ScanBarcode size={19} />
              Model: {DEMO_MODEL_ID}
            </button>
            <input ref={inputRef} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/bmp,.bmp,.jpg,.jpeg,.png" onChange={handleUpload} />
            <button className="button button--secondary" onClick={() => inputRef.current?.click()} disabled={imageLoading || processing}><ImagePlus size={19} />Upload test image</button>
            <button className="button button--secondary" onClick={handleLoadDemo} disabled={imageLoading || processing}><FileImage size={19} />{imageLoading ? 'Loading demo…' : 'Load demo image'}</button>
            <button className="button button--primary" onClick={() => void handleStartInspection()} disabled={!image || imageLoading || processing}><Play size={19} />{processing ? 'Processing…' : 'Start inspection'}</button>
            <button className="button button--ghost" onClick={handleReset} disabled={processing || (!image && !error)}><RotateCcw size={19} />Reset</button>
          </div>
        </article>
        <aside className="inspection-summary panel">
          <p className="eyebrow">OVERALL RESULT</p>
          <div className={`overall-result ${overallClass}`}>{overallLabel}</div>
          <p className="summary-help">{processing ? 'MockInspectionService is evaluating the configured demo recipe.' : inspection ? `${inspection.passed} checkpoints passed and ${inspection.failed} require attention.` : image ? 'Image ready. Press START INSPECTION to run the mock evaluation.' : 'Upload a test image or load the configured demo image to begin.'}</p>
          <div className="summary-stat"><span>Total checkpoints</span><strong>{inspection?.total_checkpoints ?? 12}</strong></div>
          <div className="summary-stat summary-stat--pass"><span>Passed</span><strong>{inspection?.passed ?? '—'}</strong></div>
          <div className="summary-stat summary-stat--ng"><span>Failed</span><strong>{inspection?.failed ?? '—'}</strong></div>
          <div className="summary-stat summary-stat--warning"><span>Warnings</span><strong>{inspection?.warnings ?? '—'}</strong></div>
          <div className="summary-stat"><span>Cycle time</span><strong>{inspection ? `${inspection.cycle_time_seconds.toFixed(1)} s` : '—'}</strong></div>

          {selectedResult && <div className="ng-detail-panel"><div className="ng-detail-title"><span>NG DETAIL</span><strong>{selectedResult.checkpoint_id}</strong></div><h3>{selectedResult.checkpoint_name}</h3><dl><div><dt>Category</dt><dd>{selectedResult.category}</dd></div><div><dt>Inspection type</dt><dd>{selectedResult.inspection_type}</dd></div><div><dt>Expected</dt><dd>{selectedResult.expected_value ?? '—'}</dd></div><div><dt>Actual</dt><dd>{selectedResult.actual_value ?? '—'}</dd></div><div><dt>Tolerance</dt><dd>{selectedResult.tolerance !== null ? `±${selectedResult.tolerance}` : 'N/A'}</dd></div><div><dt>Deviation</dt><dd>{selectedResult.deviation ?? 'N/A'}</dd></div><div><dt>Confidence</dt><dd>{(selectedResult.confidence * 100).toFixed(1)}%</dd></div></dl><div className="ng-reason">{selectedResult.status_reason}</div></div>}

          <div className="phase-notice"><strong>DETERMINISTIC MOCK RESULT</strong><span>Results are generated from checkpoint metadata by MockInspectionService. The source image is never modified.</span></div>
        </aside>
      </section>
    </>
  )
}

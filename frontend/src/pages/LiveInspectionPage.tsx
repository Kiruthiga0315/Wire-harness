import {
  CheckCircle2,
  FileImage,
  FileText,
  ImagePlus,
  Play,
  RotateCcw,
  ScanBarcode,
  CircleX,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { HarnessBoard } from '../components/HarnessBoard'
import { ColourIdentificationPanel } from '../components/ColourIdentificationPanel'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { API_BASE_URL, loadDemoImage, runMockInspection, runStickerInspection } from '../services/api'
import type { InspectionState, MockCheckpointResult } from '../types/inspection'
import type { StickerInspectionReport } from '../types/report'

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
    syncingActiveImage,
    activeVersion,
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

  const [sticker, setSticker] = useState<StickerInspectionReport | null>(null)
  const [checkingSticker, setCheckingSticker] = useState(false)

  // Fetch sticker status whenever active image changes
  useEffect(() => {
    let active = true
    if (!image) {
      setSticker(null)
      return
    }
    setCheckingSticker(true)
    runStickerInspection()
      .then((res) => {
        if (active) setSticker(res)
      })
      .catch(() => {
        // Fallback
      })
      .finally(() => {
        if (active) setCheckingSticker(false)
      })
    return () => {
      active = false
    }
  }, [image?.name, image?.url, activeVersion])

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
    void setImageBlob(file, file.name, 'upload')
    event.target.value = ''
  }

  const handleLoadDemo = async () => {
    setImageLoading(true)
    setInspectionState('CAPTURING')
    setError(null)
    try {
      const blob = await loadDemoImage()
      await setImageBlob(blob, 'data/test_images/harness_sample_01.jpeg', 'demo')
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
      if (response.sticker_inspection) {
        setSticker(response.sticker_inspection)
      }
      setInspectionState(response.state)
      setSelectedResult(response.results.find((result) => result.status === 'NG') ?? null)
    } catch (inspectionError) {
      setError(inspectionError instanceof Error ? inspectionError.message : 'Inspection processing failed.')
      setInspectionState('ERROR')
    }
  }

  const handleReset = () => {
    resetContext()
    setSticker(null)
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

  const isCroppedView = Boolean(inspection?.is_cropped && inspection.cropped_image_url)
  const displayImageUrl = isCroppedView
    ? `${API_BASE_URL}${inspection!.cropped_image_url}?v=${activeVersion}`
    : image?.url ?? null
  const displayWidth = isCroppedView ? (inspection?.crop_width ?? image?.width ?? null) : image?.width ?? null
  const displayHeight = isCroppedView ? (inspection?.crop_height ?? image?.height ?? null) : image?.height ?? null

  return (
    <>
      <PageHeader
        eyebrow="OPERATOR STATION"
        title="Live Inspection"
        description="Run automated vision inspection with specification sticker verification and checkpoint evaluation."
        actions={<div className={`state-display state-display--${inspectionState.toLowerCase()}`}><small>INSPECTION STATE</small><strong><i /> {inspectionState}</strong></div>}
      />
      <section className="inspection-info-strip">
        <div><span>Work order</span><strong>WO-DEMO-001</strong></div>
        <div><span>Product model</span><strong>{DEMO_MODEL_ID}</strong></div>
        <div><span>Description</span><strong>Client Wire Harness Sample</strong></div>
        <div><span>Revision</span><strong>V1.0</strong></div>
        <div><span>Barcode</span><strong>{sticker?.fields?.barcode_payload || 'DEMO-WH-001'}</strong></div>
        <div><span>Operator</span><strong>Development</strong></div>
      </section>

      {/* Specification Sticker Verification Card */}
      <section className="panel" style={{ marginBottom: '1.25rem', borderLeft: !image ? '4px solid #64748b' : sticker?.present ? '4px solid #10b981' : '4px solid #ef4444' }}>
        <div className="panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <ScanBarcode size={20} />
            <div>
              <p className="eyebrow">AUTOMATED TRACEABILITY INSPECTION</p>
              <h2>Specification Sticker Verification</h2>
            </div>
          </div>
          <StatusPill tone={!image ? 'neutral' : sticker?.present ? 'pass' : checkingSticker ? 'warning' : 'ng'}>
            {!image ? 'AWAITING IMAGE' : checkingSticker ? 'CHECKING STICKER…' : sticker?.present ? 'STICKER PRESENT' : 'NO STICKER PRESENT'}
          </StatusPill>
        </div>

        {!image ? (
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
            Upload a wire harness photo or load demo image to verify whether the specification sticker is attached and extract traceability fields.
          </p>
        ) : sticker?.present ? (
          <div style={{ display: 'grid', gridTemplateColumns: sticker.thumbnail ? '1fr 180px' : '1fr', gap: '1rem', padding: '0.5rem 0' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.9rem', color: '#10b981' }}>
                <CheckCircle2 size={18} />
                <strong style={{ fontSize: '0.95rem' }}>{sticker.notification}</strong>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Harness Code</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '1.25rem', fontWeight: 800, color: '#0284c7' }}>{sticker.fields.harness_code || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Part Number</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>{sticker.fields.part_number || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Description</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.95rem', fontWeight: 600, color: '#1e293b' }}>{sticker.fields.description || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Drawing Number</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.95rem', fontWeight: 600, color: '#1e293b' }}>{sticker.fields.drawing_number || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Data Matrix / Barcode</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.85rem', fontWeight: 700, color: '#0369a1', wordBreak: 'break-all' }}>{sticker.fields.barcode_payload || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Serial Number</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.85rem', fontWeight: 600, color: '#1e293b', wordBreak: 'break-all' }}>{sticker.fields.serial_number || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Supplier</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>{sticker.fields.supplier || '—'}</p>
                </div>
                <div style={{ background: '#f8fafc', padding: '0.65rem 0.85rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                  <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Batch Date Code</span>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '1.05rem', fontWeight: 700, color: '#0f172a' }}>{sticker.fields.batch_code || '—'}</p>
                </div>
              </div>
            </div>

            {sticker.thumbnail && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', padding: '0.65rem', borderRadius: '6px', border: '1px solid #cbd5e1', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
                <img src={sticker.thumbnail} alt="Detected sticker crop" style={{ maxWidth: '100%', maxHeight: '140px', borderRadius: '4px', objectFit: 'contain' }} />
                <span style={{ marginTop: '0.5rem', fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>Detected Sticker Crop</span>
              </div>
            )}
          </div>
        ) : !checkingSticker && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#f87171' }}>
            <CircleX size={22} />
            <div>
              <strong style={{ fontSize: '0.95rem' }}>NO STICKER IS PRESENT ON THIS WIRE HARNESS</strong>
              <p style={{ margin: '0.2rem 0 0', fontSize: '0.82rem', color: '#fca5a5' }}>
                Inspection alert: No specification label or barcode was detected on this workpiece. Ensure the label is attached.
              </p>
            </div>
          </div>
        )}
      </section>

      <section className="inspection-layout">
        <article className="panel inspection-viewer">
          <div className="panel-header"><div><p className="eyebrow">CAMERA 1 — TOP VIEW</p><h2>Inspection image</h2></div><StatusPill tone={stateTone(inspectionState)}>{inspection ? `${inspection.state} RESULT` : image ? 'IMAGE READY' : 'AWAITING IMAGE'}</StatusPill></div>
          {error && <div className="image-error" role="alert">{error}</div>}
          <HarnessBoard
            imageUrl={displayImageUrl}
            imageAlt={image ? `Wire harness test image: ${image.name}` : 'No wire harness image loaded'}
            width={displayWidth}
            height={displayHeight}
            loading={imageLoading}
            processing={processing}
            results={inspection?.results ?? []}
            selectedCheckpointId={selectedResult?.checkpoint_id ?? null}
            onSelectResult={setSelectedResult}
            onLoad={(width, height) => {
              if (!isCroppedView) {
                setImage((current) => current ? { ...current, width, height } : null)
              }
            }}
            onError={handleImageError}
          />
          {image && (
            <div className="image-metadata" aria-label="Loaded image information">
              <div><span>Source</span><strong>{image.source === 'demo' ? 'DEMO IMAGE' : 'LOCAL UPLOAD'}</strong></div>
              <div><span>File</span><strong title={image.name}>{image.name}{isCroppedView ? ' (Table Crop)' : ''}</strong></div>
              <div><span>Resolution</span><strong>{displayWidth && displayHeight ? `${displayWidth} × ${displayHeight} px ${isCroppedView ? '(CROP)' : ''}` : 'DECODING…'}</strong></div>
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
            <button className="button button--secondary" onClick={() => inputRef.current?.click()} disabled={imageLoading || processing || syncingActiveImage}><ImagePlus size={19} />{syncingActiveImage ? 'Syncing image…' : 'Upload test image'}</button>
            <button className="button button--secondary" onClick={handleLoadDemo} disabled={imageLoading || processing || syncingActiveImage}><FileImage size={19} />{imageLoading ? 'Loading demo…' : 'Load demo image'}</button>
            <button className="button button--primary" onClick={() => void handleStartInspection()} disabled={!image || imageLoading || processing || syncingActiveImage}><Play size={19} />{processing ? 'Processing…' : 'Start inspection'}</button>
            {inspection && (
              <button
                type="button"
                className="button button--secondary"
                onClick={() => navigate('/reports')}
                title="Open comprehensive inspection report and download PDF"
              >
                <FileText size={19} />
                View & Export Report (PDF)
              </button>
            )}
            <button className="button button--ghost" onClick={handleReset} disabled={processing || syncingActiveImage || (!image && !error)}><RotateCcw size={19} />Reset</button>
          </div>
        </article>
        <aside className="inspection-summary panel">
          <p className="eyebrow">OVERALL RESULT</p>
          <div className={`overall-result ${overallClass}`}>{overallLabel}</div>
          <p className="summary-help">{processing ? 'Evaluating checkpoints and specification sticker…' : inspection ? `${inspection.passed} checkpoints passed and ${inspection.failed} require attention.` : image ? 'Image ready. Press START INSPECTION to run the evaluation.' : 'Upload a test image or load the configured demo image to begin.'}</p>
          <div className="summary-stat"><span>Total checkpoints</span><strong>{inspection?.total_checkpoints ?? 12}</strong></div>
          <div className="summary-stat summary-stat--pass"><span>Passed</span><strong>{inspection?.passed ?? '—'}</strong></div>
          <div className="summary-stat summary-stat--ng"><span>Failed</span><strong>{inspection?.failed ?? '—'}</strong></div>
          <div className="summary-stat summary-stat--warning"><span>Warnings</span><strong>{inspection?.warnings ?? '—'}</strong></div>
          <div className="summary-stat"><span>Cycle time</span><strong>{inspection ? `${inspection.cycle_time_seconds.toFixed(1)} s` : '—'}</strong></div>
          <div className="summary-stat" style={{ borderTop: '1px solid rgba(255,255,255,0.08)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
            <span>Sticker Status</span>
            <strong style={{ color: sticker?.present ? '#10b981' : checkingSticker ? '#f59e0b' : '#f87171' }}>
              {checkingSticker ? 'CHECKING…' : sticker?.present ? 'PRESENT' : 'NOT PRESENT'}
            </strong>
          </div>
          {sticker?.present && (
            <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '6px', padding: '0.6rem 0.75rem', marginTop: '0.5rem', fontSize: '0.75rem' }}>
              <div style={{ color: '#10b981', fontWeight: 700, marginBottom: '0.2rem' }}>✓ SPECIFICATION VERIFIED</div>
              <div style={{ color: '#e2e8f0' }}>Code: <strong>{sticker.fields.harness_code}</strong> | Part: <strong>{sticker.fields.part_number}</strong></div>
              <div style={{ color: '#94a3b8', fontSize: '0.7rem', marginTop: '0.2rem' }}>Supplier: {sticker.fields.supplier} · Batch: {sticker.fields.batch_code}</div>
            </div>
          )}
          {image && sticker && !sticker.present && !checkingSticker && (
            <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: '6px', padding: '0.6rem 0.75rem', marginTop: '0.5rem', fontSize: '0.75rem', color: '#f87171' }}>
              <div style={{ fontWeight: 700, marginBottom: '0.2rem' }}>⚠️ NO STICKER DETECTED</div>
              <div style={{ color: '#fca5a5', fontSize: '0.7rem' }}>Specification label missing on workpiece.</div>
            </div>
          )}

          {selectedResult && <div className="ng-detail-panel"><div className="ng-detail-title"><span>NG DETAIL</span><strong>{selectedResult.checkpoint_id}</strong></div><h3>{selectedResult.checkpoint_name}</h3><dl><div><dt>Category</dt><dd>{selectedResult.category}</dd></div><div><dt>Inspection type</dt><dd>{selectedResult.inspection_type}</dd></div><div><dt>Expected</dt><dd>{selectedResult.expected_value ?? '—'}</dd></div><div><dt>Actual</dt><dd>{selectedResult.actual_value ?? '—'}</dd></div><div><dt>Tolerance</dt><dd>{selectedResult.tolerance !== null ? `±${selectedResult.tolerance}` : 'N/A'}</dd></div><div><dt>Deviation</dt><dd>{selectedResult.deviation ?? 'N/A'}</dd></div><div><dt>Confidence</dt><dd>{(selectedResult.confidence * 100).toFixed(1)}%</dd></div></dl><div className="ng-reason">{selectedResult.status_reason}</div></div>}

          <div className="phase-notice"><strong>INSPECTION STATION</strong><span>Visual inspection results and automated sticker OCR verification.</span></div>
        </aside>
      </section>

      {image && <ColourIdentificationPanel />}
    </>
  )
}

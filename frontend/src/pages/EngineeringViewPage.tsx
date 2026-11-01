import {
  Beaker,
  Binary,
  Boxes,
  CheckCircle2,
  CircleDot,
  FileImage,
  GitBranch,
  ImagePlus,
  Network,
  RefreshCw,
  Scan,
  TriangleAlert,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { EngineeringCheckpointEditor } from '../components/EngineeringCheckpointEditor'
import { ColorInspectionPanel } from '../components/ColorInspectionPanel'
import { HarnessGraphPanel } from '../components/HarnessGraphPanel'
import { WireColorIdentificationPanel } from '../components/WireColorIdentificationPanel'
import { FeatureExtractionPanel } from '../components/FeatureExtractionPanel'
import { RuleEngineVerdictPanel } from '../components/RuleEngineVerdictPanel'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import {
  ACTIVE_IMAGE_URL,
  loadDemoImage,
  runDemoSegmentation,
  runGoldenInspection,
  syncCheckpointsFromGolden,
} from '../services/api'
import type { SegmentationResponse } from '../types/engineering'
import type { HarnessVerdict } from '../types/rules'
import type { GoldenInspectionResponse } from '../types/goldenReference'

const MAX_UPLOAD_BYTES = 15 * 1024 * 1024

const resultPanels = [
  { key: 'isolated_harness', title: 'Isolated harness', description: 'Harness isolated from background markings', icon: Beaker },
  { key: 'binary_mask', title: 'Binary mask', description: 'Cleaned dark-object segmentation', icon: Binary },
  { key: 'contour_image', title: 'Contour image', description: 'Wire contours in red', icon: Boxes },
  { key: 'skeleton_image', title: 'Skeleton', description: 'Single-pixel centreline representation', icon: Network },
] as const

export function EngineeringViewPage() {
  const { image, activeVersion, syncingActiveImage, uploadActiveImageFile, setImageBlob } = useInspection()
  const [result, setResult] = useState<SegmentationResponse | null>(null)
  const [overview, setOverview] = useState<GoldenInspectionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingOverview, setLoadingOverview] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [syncingCheckpoints, setSyncingCheckpoints] = useState(false)
  const [syncSuccessMessage, setSyncSuccessMessage] = useState<string | null>(null)
  const [editorRefreshTrigger, setEditorRefreshTrigger] = useState(0)
  const [colorRefreshTrigger, setColorRefreshTrigger] = useState(0)
  const [ruleVerdict, setRuleVerdict] = useState<HarnessVerdict | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const processImage = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setLoadingOverview(true)
    setError(null)
    try {
      const [segResponse, ovResponse] = await Promise.all([
        runDemoSegmentation(signal),
        runGoldenInspection().catch((err) => {
          console.warn('Topology overview warning:', err)
          return null
        }),
      ])
      setResult(segResponse)
      if (ovResponse) {
        setOverview(ovResponse)
      }
      // Automatically refresh checkpoints and trigger colour inspection
      setEditorRefreshTrigger((v) => v + 1)
      setColorRefreshTrigger((v) => v + 1)
    } catch (processingError) {
      if (processingError instanceof DOMException && processingError.name === 'AbortError') return
      setError(processingError instanceof Error ? processingError.message : 'Segmentation failed.')
    } finally {
      setLoading(false)
      setLoadingOverview(false)
    }
  }, [])

  useEffect(() => {
    if (syncingActiveImage) return
    const controller = new AbortController()
    void processImage(controller.signal)
    return () => controller.abort()
  }, [processImage, activeVersion, syncingActiveImage])

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
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
    try {
      await uploadActiveImageFile(file)
      // Automatically synchronize checkpoints to the new workpiece dimensions and feature points
      try {
        await syncCheckpointsFromGolden('DEMO-HARNESS-001', true, true)
        setEditorRefreshTrigger((v) => v + 1)
        setColorRefreshTrigger((v) => v + 1)
      } catch (syncErr) {
        console.warn('Auto checkpoint sync warning:', syncErr)
      }
    } catch (uploadErr) {
      setError(uploadErr instanceof Error ? uploadErr.message : 'Image upload failed.')
    } finally {
      event.target.value = ''
    }
  }

  const handleLoadDemo = async () => {
    try {
      const blob = await loadDemoImage()
      await setImageBlob(blob, 'data/test_images/harness_sample_01.jpeg', 'demo')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load the demo image.')
    }
  }

  const handleSyncGoldenCheckpoints = async () => {
    setSyncingCheckpoints(true)
    setError(null)
    setSyncSuccessMessage(null)
    try {
      const synced = await syncCheckpointsFromGolden('DEMO-HARNESS-001', true, true)
      setEditorRefreshTrigger((v) => v + 1)
      setColorRefreshTrigger((v) => v + 1)
      setSyncSuccessMessage(
        `Synchronized ${synced.length} checkpoints from Golden Reference & Checkpoints (Terminals, Spine Nodes, Junctions).`
      )
      setTimeout(() => setSyncSuccessMessage(null), 7000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync checkpoints from Golden Reference.')
    } finally {
      setSyncingCheckpoints(false)
    }
  }

  const handleEditorCheckpointsChanged = useCallback(() => {
    setColorRefreshTrigger((v) => v + 1)
  }, [])

  const imageWidth = image?.width ?? result?.metrics.image_width ?? 1800
  const imageHeight = image?.height ?? result?.metrics.image_height ?? 560
  const activeWorkpieceUrl = image?.url || `${ACTIVE_IMAGE_URL}?v=${activeVersion}`

  const topSummary = overview?.topology_summary
  const tapes = overview?.colored_tapes
  const sticker = overview?.sticker

  return (
    <>
      <PageHeader
        eyebrow="VISION ENGINEERING"
        title="Engineering View"
        description="Configure checkpoints and inspect intermediate computer-vision metric outputs (cm)."
        actions={
          <div className="button-group">
            <input
              ref={fileInputRef}
              type="file"
              className="visually-hidden"
              accept="image/jpeg,image/png,image/bmp,.bmp,.jpg,.jpeg,.png"
              onChange={handleUpload}
            />
            <button
              className="button button--secondary"
              onClick={() => void handleSyncGoldenCheckpoints()}
              disabled={loading || syncingActiveImage || syncingCheckpoints}
              title="Synchronize checkpoints from Golden Reference & Checkpoints"
            >
              <RefreshCw size={18} className={syncingCheckpoints ? 'spin' : ''} />
              {syncingCheckpoints ? 'Syncing checkpoints…' : 'Sync from Golden Reference'}
            </button>
            <button
              className="button button--secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading || syncingActiveImage || syncingCheckpoints}
              title="Upload any JPEG, PNG, or BMP wire harness image"
            >
              <ImagePlus size={18} />
              {syncingActiveImage ? 'Syncing image…' : 'Upload test image'}
            </button>
            <button
              className="button button--secondary"
              onClick={() => void handleLoadDemo()}
              disabled={loading || syncingActiveImage || syncingCheckpoints}
              title="Reset workpiece to standard demo harness"
            >
              <FileImage size={18} />
              Load demo image
            </button>
            <button
              className="button button--primary"
              onClick={() => void processImage()}
              disabled={loading || syncingActiveImage || syncingCheckpoints}
            >
              <RefreshCw size={18} className={loading || syncingActiveImage ? 'spin' : ''} />
              {loading ? 'Processing…' : syncingActiveImage ? 'Syncing…' : 'Run segmentation'}
            </button>
          </div>
        }
      />

      {syncSuccessMessage && (
        <div
          className="alert-banner"
          role="status"
          style={{
            background: '#ecfdf5',
            borderColor: '#a7f3d0',
            color: '#065f46',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 18px',
            marginBottom: '18px',
            borderRadius: '4px',
            border: '1px solid #a7f3d0',
          }}
        >
          <CheckCircle2 size={20} style={{ color: '#059669', flexShrink: 0 }} />
          <div>
            <strong style={{ display: 'block', fontSize: '13px', color: '#065f46' }}>
              Golden Reference Checkpoints Synchronized
            </strong>
            <span style={{ fontSize: '12px', color: '#047857' }}>{syncSuccessMessage}</span>
          </div>
        </div>
      )}

      <div className="engineering-warning">
        <TriangleAlert size={20} />
        <div><strong>EXPERIMENTAL FEASIBILITY PIPELINE</strong><span>Checkpoint configuration is persistent, but segmentation output is not production-ready and must not drive PASS/NG decisions.</span></div>
        <StatusPill tone="warning">ENGINEERING ONLY</StatusPill>
      </div>

      {/* Harness Feature & Topology Overview (Items 1-4, 7-8) */}
      <section className="engineering-metrics" style={{ gridTemplateColumns: 'repeat(6, 1fr)', marginBottom: 20 }}>
        {/* 1. No of terminals */}
        <article style={{ borderLeft: '3px solid #16a34a' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#16a34a', marginBottom: 4 }}>
            <CircleDot size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>1. Terminals</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {loadingOverview ? '…' : (topSummary?.terminal_count ?? '—')}
          </strong>
          <small>Detected connectors / endpoints</small>
        </article>

        {/* 2. No of junctions */}
        <article style={{ borderLeft: '3px solid #0284c7' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0284c7', marginBottom: 4 }}>
            <GitBranch size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>2. Junctions</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {loadingOverview ? '…' : (topSummary?.junction_count ?? '—')}
          </strong>
          <small>Branching splits (J01–J31)</small>
        </article>

        {/* 3. No of branches */}
        <article style={{ borderLeft: '3px solid #9333ea' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#9333ea', marginBottom: 4 }}>
            <Network size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>3. Branches</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {loadingOverview ? '…' : (topSummary?.branch_count ?? '—')}
          </strong>
          <small>Extracted wire segments</small>
        </article>

        {/* 4. No of spine nodes / joints */}
        <article style={{ borderLeft: '3px solid #d97706' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#d97706', marginBottom: 4 }}>
            <Scan size={14} />
            <span style={{ margin: 0, fontWeight: 700 }}>4. Spine Nodes</span>
          </div>
          <strong style={{ color: 'var(--navy-900)' }}>
            {loadingOverview ? '…' : (topSummary?.node_count ?? '—')}
          </strong>
          <small>Trunk joints (N01–N12)</small>
        </article>

        {/* 7. Presence of colored tapes */}
        <article style={{ borderLeft: '3px solid #0d9488' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0d9488', marginBottom: 4 }}>
            <span style={{ fontSize: 13 }}>🎨</span>
            <span style={{ margin: 0, fontWeight: 700 }}>7. Colored Tapes</span>
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: '2px 5px',
                borderRadius: 3,
                background: tapes?.green?.detected ? '#dcfce7' : '#f1f5f9',
                color: tapes?.green?.detected ? '#166534' : '#64748b',
              }}
              title={`Green Tape: ${tapes?.green?.detected ? 'PRESENT' : 'NOT DETECTED'} (${tapes?.green?.percentage ?? 0}%)`}
            >
              🟢 {tapes?.green?.detected ? `${tapes.green.percentage}%` : 'Green'}
            </span>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: '2px 5px',
                borderRadius: 3,
                background: tapes?.dark_blue?.detected ? '#dbeafe' : '#f1f5f9',
                color: tapes?.dark_blue?.detected ? '#1e40af' : '#64748b',
              }}
              title={`Dark Blue Tape: ${tapes?.dark_blue?.detected ? 'PRESENT' : 'NOT DETECTED'} (${tapes?.dark_blue?.percentage ?? 0}%)`}
            >
              🔵 {tapes?.dark_blue?.detected ? `${tapes.dark_blue.percentage}%` : 'Blue'}
            </span>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: '2px 5px',
                borderRadius: 3,
                background: tapes?.grey?.detected ? '#f3f4f6' : '#f1f5f9',
                color: tapes?.grey?.detected ? '#374151' : '#64748b',
              }}
              title={`Gray Tape: ${tapes?.grey?.detected ? 'PRESENT' : 'NOT DETECTED'} (${tapes?.grey?.percentage ?? 0}%)`}
            >
              ⚪ {tapes?.grey?.detected ? `${tapes.grey.percentage}%` : 'Gray'}
            </span>
          </div>
          <small style={{ marginTop: 4 }}>Green / Dark Blue / Gray tapes</small>
        </article>

        {/* 8. Presence of sticker */}
        <article style={{ borderLeft: '3px solid #2563eb' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#2563eb', marginBottom: 4 }}>
            <span style={{ fontSize: 13 }}>🏷️</span>
            <span style={{ margin: 0, fontWeight: 700 }}>8. Spec Sticker</span>
          </div>
          <strong
            style={{
              fontSize: 14,
              color: sticker?.present ? 'var(--green-600)' : sticker ? 'var(--red-600)' : 'var(--navy-900)',
            }}
          >
            {sticker?.status ?? (overview ? 'PRESENT' : 'READY')}
          </strong>
          <small style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
            {sticker?.fields?.part_number ? `Part: ${sticker.fields.part_number}` : 'OCR & Barcode verified'}
          </small>
        </article>
      </section>

      <EngineeringCheckpointEditor
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        imageUrl={activeWorkpieceUrl}
        refreshTrigger={editorRefreshTrigger}
        onCheckpointsChanged={handleEditorCheckpointsChanged}
      />

      <ColorInspectionPanel refreshTrigger={colorRefreshTrigger} />

      <div className="engineering-section-title">
        <div>
          <p className="eyebrow">SEGMENTATION DIAGNOSTICS</p>
          <h2>Image-processing outputs</h2>
        </div>
        <span>
          Input: {image ? `${image.name} (${image.source === 'upload' ? 'Active upload' : 'Demo'})` : 'harness_sample_01.jpeg'}
          {syncingActiveImage && ' · Syncing to vision engine…'}
        </span>
      </div>

      {error && <div className="alert-banner" role="alert"><TriangleAlert size={20} /><div><strong>Segmentation unavailable</strong><span>{error}</span></div></div>}

      <section className="engineering-metrics" aria-label="Segmentation metrics">
        <article><span>Harness occupancy</span><strong>{result ? `${result.metrics.harness_occupied_percentage.toFixed(3)}%` : '—'}</strong><small>Foreground mask area</small></article>
        <article><span>Contours generated</span><strong>{result?.metrics.contour_count ?? '—'}</strong><small>External structures</small></article>
        <article><span>Otsu threshold</span><strong>{result?.metrics.otsu_threshold ?? '—'}</strong><small>Grayscale intensity</small></article>
        <article><span>Small components removed</span><strong>{result?.metrics.removed_component_count ?? '—'}</strong><small>Noise filter</small></article>
        <article><span>Border artifacts excluded</span><strong>{result?.metrics.excluded_border_component_count ?? '—'}</strong><small>Frame-edge regions</small></article>
      </section>

      <section className="engineering-grid engineering-grid--outputs">
        {resultPanels.map(({ key, title, description, icon: Icon }) => {
          const source = result?.images[key] ?? ''
          return (
            <article className="panel engineering-image-card" key={key}>
              <div className="panel-header"><div><p className="eyebrow">PROCESSING OUTPUT</p><h2>{title}</h2></div><Icon size={21} /></div>
              <div className="engineering-image-stage">
                {source ? (
                  <img
                    src={source}
                    alt={`${title}: ${description}`}
                    style={{ aspectRatio: `${result?.metrics.image_width ?? 681} / ${result?.metrics.image_height ?? 1584}` }}
                  />
                ) : (
                  <div className="engineering-loading">
                    <Beaker size={30} className={loading || syncingActiveImage ? 'spin' : ''} />
                    <span>{syncingActiveImage ? 'SYNCING WORKPIECE…' : loading ? 'PROCESSING IMAGE…' : 'NO OUTPUT'}</span>
                  </div>
                )}
              </div>
              <footer><span>{description}</span>{result && <small>{result.metrics.image_width} × {result.metrics.image_height} px</small>}</footer>
            </article>
          )
        })}
      </section>

      <WireColorIdentificationPanel />

      <HarnessGraphPanel />

      <FeatureExtractionPanel />

      <section style={{ marginTop: '2rem' }}>
        <RuleEngineVerdictPanel
          verdict={ruleVerdict}
          onVerdictChange={setRuleVerdict}
        />
      </section>

      {result && <article className="panel method-panel"><p className="eyebrow">CURRENT METHOD</p><h2>OpenCV feasibility pipeline</h2><p>{result.method}.</p><div className="pipeline-steps"><span>1 · Grayscale</span><span>2 · Gaussian blur</span><span>3 · Inverted Otsu</span><span>4 · Morphological close</span><span>5 · Component cleanup</span><span>6 · Contours</span><span>7 · Skeletonize</span></div><small>{result.disclaimer}</small></article>}
    </>
  )
}

import { Beaker, Binary, Boxes, FileImage, ImagePlus, Network, RefreshCw, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { EngineeringCheckpointEditor } from '../components/EngineeringCheckpointEditor'
import { ColorInspectionPanel } from '../components/ColorInspectionPanel'
import { HarnessGraphPanel } from '../components/HarnessGraphPanel'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { ACTIVE_IMAGE_URL, loadDemoImage, runDemoSegmentation } from '../services/api'
import type { SegmentationResponse } from '../types/engineering'

const MAX_UPLOAD_BYTES = 15 * 1024 * 1024

const resultPanels = [
  { key: 'binary_mask', title: 'Binary mask', description: 'Cleaned dark-object segmentation', icon: Binary },
  { key: 'contour_image', title: 'Contour image', description: 'External contours in red', icon: Boxes },
  { key: 'skeleton_image', title: 'Skeleton', description: 'Single-pixel centreline representation', icon: Network },
] as const

export function EngineeringViewPage() {
  const { image, activeVersion, syncingActiveImage, uploadActiveImageFile, setImageBlob } = useInspection()
  const [result, setResult] = useState<SegmentationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const processImage = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const response = await runDemoSegmentation(signal)
      setResult(response)
    } catch (processingError) {
      if (processingError instanceof DOMException && processingError.name === 'AbortError') return
      setError(processingError instanceof Error ? processingError.message : 'Segmentation failed.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (syncingActiveImage) return
    const controller = new AbortController()
    void processImage(controller.signal)
    return () => controller.abort()
  }, [processImage, activeVersion, syncingActiveImage])

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
    void uploadActiveImageFile(file)
    event.target.value = ''
  }

  const handleLoadDemo = async () => {
    try {
      const blob = await loadDemoImage()
      await setImageBlob(blob, 'data/test_images/harness_sample_01.jpeg', 'demo')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load the demo image.')
    }
  }

  const imageWidth = image?.width ?? result?.metrics.image_width ?? 681
  const imageHeight = image?.height ?? result?.metrics.image_height ?? 1584
  const activeWorkpieceUrl = image?.url || `${ACTIVE_IMAGE_URL}?v=${activeVersion}`

  return (
    <>
      <PageHeader
        eyebrow="VISION ENGINEERING"
        title="Engineering View"
        description="Configure pixel checkpoints and inspect intermediate computer-vision outputs."
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
              onClick={() => fileInputRef.current?.click()}
              disabled={loading || syncingActiveImage}
              title="Upload any JPEG, PNG, or BMP wire harness image"
            >
              <ImagePlus size={18} />
              {syncingActiveImage ? 'Syncing image…' : 'Upload test image'}
            </button>
            <button
              className="button button--secondary"
              onClick={() => void handleLoadDemo()}
              disabled={loading || syncingActiveImage}
              title="Reset workpiece to standard demo harness"
            >
              <FileImage size={18} />
              Load demo image
            </button>
            <button
              className="button button--primary"
              onClick={() => void processImage()}
              disabled={loading || syncingActiveImage}
            >
              <RefreshCw size={18} className={loading || syncingActiveImage ? 'spin' : ''} />
              {loading ? 'Processing…' : syncingActiveImage ? 'Syncing…' : 'Run segmentation'}
            </button>
          </div>
        }
      />

      <div className="engineering-warning">
        <TriangleAlert size={20} />
        <div><strong>EXPERIMENTAL FEASIBILITY PIPELINE</strong><span>Checkpoint configuration is persistent, but segmentation output is not production-ready and must not drive PASS/NG decisions.</span></div>
        <StatusPill tone="warning">ENGINEERING ONLY</StatusPill>
      </div>

      <EngineeringCheckpointEditor
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        imageUrl={activeWorkpieceUrl}
      />

      <ColorInspectionPanel />

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

      <HarnessGraphPanel />

      {result && <article className="panel method-panel"><p className="eyebrow">CURRENT METHOD</p><h2>OpenCV feasibility pipeline</h2><p>{result.method}.</p><div className="pipeline-steps"><span>1 · Grayscale</span><span>2 · Gaussian blur</span><span>3 · Inverted Otsu</span><span>4 · Morphological close</span><span>5 · Component cleanup</span><span>6 · Contours</span><span>7 · Skeletonize</span></div><small>{result.disclaimer}</small></article>}
    </>
  )
}

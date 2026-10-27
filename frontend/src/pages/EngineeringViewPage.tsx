import { Beaker, Binary, Boxes, Network, RefreshCw, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { EngineeringCheckpointEditor } from '../components/EngineeringCheckpointEditor'
import { ColorInspectionPanel } from '../components/ColorInspectionPanel'
import { HarnessGraphPanel } from '../components/HarnessGraphPanel'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { runDemoSegmentation } from '../services/api'
import type { SegmentationResponse } from '../types/engineering'

const resultPanels = [
  { key: 'binary_mask', title: 'Binary mask', description: 'Cleaned dark-object segmentation', icon: Binary },
  { key: 'contour_image', title: 'Contour image', description: 'External contours in red', icon: Boxes },
  { key: 'skeleton_image', title: 'Skeleton', description: 'Single-pixel centreline representation', icon: Network },
] as const

export function EngineeringViewPage() {
  const { image } = useInspection()
  const [result, setResult] = useState<SegmentationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const processImage = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      setResult(await runDemoSegmentation(signal))
    } catch (processingError) {
      if (processingError instanceof DOMException && processingError.name === 'AbortError') return
      setError(processingError instanceof Error ? processingError.message : 'Segmentation failed.')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void processImage(controller.signal)
    return () => controller.abort()
  }, [processImage, image?.name, image?.url])

  const imageWidth = image?.width ?? result?.metrics.image_width ?? 681
  const imageHeight = image?.height ?? result?.metrics.image_height ?? 1584

  return (
    <>
      <PageHeader
        eyebrow="VISION ENGINEERING"
        title="Engineering View"
        description="Configure pixel checkpoints and inspect intermediate computer-vision outputs."
        actions={<button className="button button--primary" onClick={() => void processImage()} disabled={loading}><RefreshCw size={18} className={loading ? 'spin' : ''} />{loading ? 'Processing…' : 'Run segmentation'}</button>}
      />

      <div className="engineering-warning">
        <TriangleAlert size={20} />
        <div><strong>EXPERIMENTAL FEASIBILITY PIPELINE</strong><span>Checkpoint configuration is persistent, but segmentation output is not production-ready and must not drive PASS/NG decisions.</span></div>
        <StatusPill tone="warning">ENGINEERING ONLY</StatusPill>
      </div>

      <EngineeringCheckpointEditor
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        imageUrl={image?.url}
      />

      <ColorInspectionPanel />

      <div className="engineering-section-title"><div><p className="eyebrow">SEGMENTATION DIAGNOSTICS</p><h2>Image-processing outputs</h2></div><span>Input: {image ? `${image.name} (${image.source === 'upload' ? 'Local upload' : 'Demo'})` : 'harness_sample_01.jpeg'}</span></div>

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
                {source ? <img src={source} alt={`${title}: ${description}`} /> : <div className="engineering-loading"><Beaker size={30} /><span>{loading ? 'PROCESSING IMAGE…' : 'NO OUTPUT'}</span></div>}
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

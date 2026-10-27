import { Droplets, RefreshCw, ScanSearch } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { getCheckpoints, runColorInspection } from '../services/api'
import type { EngineeringCheckpoint } from '../types/checkpoint'
import type { ColorInspectionResponse } from '../types/colorInspection'
import { StatusPill } from './StatusPill'

const MODEL_ID = 'DEMO-HARNESS-001'
const supportedColours = new Set(['BLACK', 'WHITE', 'BLUE', 'RED', 'GREEN', 'YELLOW', 'ORANGE', 'GREY', 'GRAY'])

export function ColorInspectionPanel() {
  const { image, activeVersion } = useInspection()
  const [checkpoints, setCheckpoints] = useState<EngineeringCheckpoint[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [debug, setDebug] = useState(false)
  const [result, setResult] = useState<ColorInspectionResponse | null>(null)
  const [loadingCheckpoints, setLoadingCheckpoints] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setResult(null)
    setError(null)
  }, [image?.name, image?.url, activeVersion])

  const loadColourCheckpoints = useCallback(async () => {
    setLoadingCheckpoints(true)
    setError(null)
    try {
      const records = await getCheckpoints(MODEL_ID)
      const colourRecords = records.filter((checkpoint) =>
        checkpoint.expected_value && supportedColours.has(checkpoint.expected_value.trim().toUpperCase()),
      )
      setCheckpoints(colourRecords)
      setSelectedId((current) => colourRecords.some((checkpoint) => checkpoint.checkpoint_id === current)
        ? current
        : colourRecords[0]?.checkpoint_id ?? '')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load colour checkpoints.')
    } finally {
      setLoadingCheckpoints(false)
    }
  }, [])

  useEffect(() => { void loadColourCheckpoints() }, [loadColourCheckpoints])

  const selectedCheckpoint = useMemo(
    () => checkpoints.find((checkpoint) => checkpoint.checkpoint_id === selectedId) ?? null,
    [checkpoints, selectedId],
  )

  const inspectColour = async () => {
    if (!selectedId) {
      setError('Configure a checkpoint with a supported expected colour first.')
      return
    }
    setProcessing(true)
    setError(null)
    setResult(null)
    try {
      setResult(await runColorInspection(MODEL_ID, selectedId, debug))
    } catch (inspectionError) {
      setError(inspectionError instanceof Error ? inspectionError.message : 'Colour inspection failed.')
    } finally {
      setProcessing(false)
    }
  }

  return (
    <section className="panel color-inspection-panel">
      <div className="panel-header"><div><p className="eyebrow">ROI COLOUR ANALYSIS</p><h2>Colour Inspection Service</h2></div><StatusPill tone={result ? (result.status === 'PASS' ? 'pass' : 'ng') : 'info'}>{result ? result.status : 'DEVELOPMENT'}</StatusPill></div>
      <div className="color-inspection-controls">
        <label className="color-checkpoint-select"><span>Configured colour checkpoint</span><select value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setResult(null) }} disabled={loadingCheckpoints}>{checkpoints.length ? checkpoints.map((checkpoint) => <option value={checkpoint.checkpoint_id} key={checkpoint.checkpoint_id}>{checkpoint.checkpoint_id} · {checkpoint.checkpoint_name} · Expected {checkpoint.expected_value?.toUpperCase()}</option>) : <option value="">No colour checkpoints found</option>}</select></label>
        <label className="debug-toggle"><input type="checkbox" checked={debug} onChange={(event) => { setDebug(event.target.checked); setResult(null) }} /><span>Show extracted ROI</span></label>
        <button className="button button--ghost color-refresh" onClick={() => void loadColourCheckpoints()} disabled={loadingCheckpoints || processing} title="Reload checkpoints"><RefreshCw size={17} className={loadingCheckpoints ? 'spin' : ''} />Refresh</button>
        <button className="button button--primary" onClick={() => void inspectColour()} disabled={!selectedId || processing}><ScanSearch size={18} />{processing ? 'Analysing…' : 'Inspect colour'}</button>
      </div>

      {selectedCheckpoint && <div className="selected-roi-summary"><Droplets size={17} /><span><strong>{selectedCheckpoint.checkpoint_id}</strong> uses ROI {selectedCheckpoint.roi_width} × {selectedCheckpoint.roi_height} px centred at X {selectedCheckpoint.reference_x}, Y {selectedCheckpoint.reference_y}.</span></div>}
      {error && <div className="checkpoint-form-error" role="alert">{error}</div>}

      {result ? (
        <div className={`color-result color-result--${result.status.toLowerCase()}`}>
          <div className="color-result-metrics">
            <article><span>Expected colour</span><strong><i className={`colour-swatch colour-swatch--${result.expected_colour.toLowerCase()}`} />{result.expected_colour}</strong></article>
            <article><span>Detected colour</span><strong><i className={`colour-swatch colour-swatch--${result.detected_colour.toLowerCase()}`} />{result.detected_colour}</strong></article>
            <article><span>Mean HSV</span><strong>H {result.mean_hsv.channel_1.toFixed(2)}</strong><small>S {result.mean_hsv.channel_2.toFixed(2)} · V {result.mean_hsv.channel_3.toFixed(2)}</small></article>
            <article><span>Mean LAB</span><strong>L {result.mean_lab.channel_1.toFixed(2)}</strong><small>A {result.mean_lab.channel_2.toFixed(2)} · B {result.mean_lab.channel_3.toFixed(2)}</small></article>
            <article><span>Confidence</span><strong>{(result.confidence * 100).toFixed(1)}%</strong><small>Dominant-class estimate</small></article>
            <article className="color-result-status"><span>Result</span><strong>{result.status}</strong><small>{result.expected_colour === result.detected_colour ? 'Expected colour matched' : 'Colour mismatch detected'}</small></article>
          </div>
          {result.debug_roi_image && <div className="roi-debug-view"><div><p className="eyebrow">DEBUG OUTPUT</p><h3>Extracted checkpoint ROI</h3><span>X {result.roi.x} · Y {result.roi.y} · {result.roi.width} × {result.roi.height} px</span></div><figure><img src={result.debug_roi_image} alt={`Extracted ROI for ${result.checkpoint_id}`} /><figcaption>Read-only PNG preview</figcaption></figure></div>}
          <p className="color-disclaimer">{result.disclaimer}</p>
        </div>
      ) : (
        <div className="color-result-empty"><Droplets size={29} /><span>Select a configured checkpoint and run colour inspection.</span></div>
      )}
    </section>
  )
}

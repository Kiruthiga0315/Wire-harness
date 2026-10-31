import { Droplets, RefreshCw, ScanSearch } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useInspection } from '../context/InspectionContext'
import { getCheckpoints, runColorInspection, syncCheckpointsFromGolden } from '../services/api'
import type { EngineeringCheckpoint } from '../types/checkpoint'
import type { ColorInspectionResponse } from '../types/colorInspection'
import { StatusPill } from './StatusPill'

const MODEL_ID = 'DEMO-HARNESS-001'
const SUPPORTED_COLOURS = ['BLUE', 'BLACK', 'GREY', 'WHITE', 'RED', 'GREEN', 'YELLOW', 'ORANGE']
const colourSet = new Set(SUPPORTED_COLOURS)

interface ColorInspectionPanelProps {
  refreshTrigger?: number
}

export function ColorInspectionPanel({ refreshTrigger }: ColorInspectionPanelProps = {}) {
  const { image, activeVersion } = useInspection()
  const [checkpoints, setCheckpoints] = useState<EngineeringCheckpoint[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [expectedColour, setExpectedColour] = useState<string>('BLUE')
  const [debug, setDebug] = useState(false)
  const [result, setResult] = useState<ColorInspectionResponse | null>(null)
  const [loadingCheckpoints, setLoadingCheckpoints] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const inspectColour = useCallback(
    async (cpId?: string, col?: string) => {
      const targetId = cpId || selectedId
      if (!targetId) {
        setError('Select a checkpoint to inspect colour.')
        return
      }
      const targetCol = col || expectedColour
      setProcessing(true)
      setError(null)
      try {
        const resp = await runColorInspection(MODEL_ID, targetId, debug, targetCol)
        setResult(resp)
      } catch (inspectionError) {
        setError(inspectionError instanceof Error ? inspectionError.message : 'Colour inspection failed.')
      } finally {
        setProcessing(false)
      }
    },
    [selectedId, expectedColour, debug],
  )

  const loadColourCheckpoints = useCallback(
    async (autoInspect = true) => {
      setLoadingCheckpoints(true)
      setError(null)
      try {
        let records = await getCheckpoints(MODEL_ID)
        if (records.length === 0) {
          try {
            records = await syncCheckpointsFromGolden(MODEL_ID, true, true)
          } catch {
            // ignore
          }
        }
        setCheckpoints(records)

        // Priority: CP-008 (Tape T1 Blue), or explicit colour checkpoint, or first available
        let chosen = records.find((c) => c.checkpoint_id === 'CP-008')
        if (!chosen && records.length > 0) {
          chosen =
            records.find((c) => c.expected_value && colourSet.has(c.expected_value.trim().toUpperCase())) ||
            records[0]
        }

        if (chosen) {
          const chosenId = chosen.checkpoint_id
          setSelectedId(chosenId)
          let chosenCol = 'BLUE'
          if (chosen.expected_value && colourSet.has(chosen.expected_value.trim().toUpperCase())) {
            chosenCol = chosen.expected_value.trim().toUpperCase()
          }
          setExpectedColour(chosenCol)
          if (autoInspect) {
            void runColorInspection(MODEL_ID, chosenId, debug, chosenCol)
              .then((resp) => {
                setResult(resp)
              })
              .catch(() => {})
          }
        }
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load colour checkpoints.')
      } finally {
        setLoadingCheckpoints(false)
      }
    },
    [debug],
  )

  useEffect(() => {
    void loadColourCheckpoints(true)
  }, [loadColourCheckpoints, refreshTrigger, activeVersion])

  const selectedCheckpoint = useMemo(
    () => checkpoints.find((checkpoint) => checkpoint.checkpoint_id === selectedId) ?? null,
    [checkpoints, selectedId],
  )

  const handleCheckpointChange = (newId: string) => {
    setSelectedId(newId)
    const cp = checkpoints.find((c) => c.checkpoint_id === newId)
    let col = expectedColour
    if (cp?.expected_value && colourSet.has(cp.expected_value.trim().toUpperCase())) {
      col = cp.expected_value.trim().toUpperCase()
      setExpectedColour(col)
    }
    void inspectColour(newId, col)
  }

  const handleColourChange = (newColour: string) => {
    setExpectedColour(newColour)
    void inspectColour(selectedId, newColour)
  }

  return (
    <section className="panel color-inspection-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">ROI COLOUR ANALYSIS</p>
          <h2>Colour Inspection Service</h2>
        </div>
        <StatusPill tone={result ? (result.status === 'PASS' ? 'pass' : 'ng') : 'info'}>
          {result ? result.status : 'DEVELOPMENT'}
        </StatusPill>
      </div>

      <div className="color-inspection-controls">
        <label className="color-checkpoint-select">
          <span>Configured Checkpoint</span>
          <select
            value={selectedId}
            onChange={(event) => handleCheckpointChange(event.target.value)}
            disabled={loadingCheckpoints}
          >
            {checkpoints.length ? (
              checkpoints.map((checkpoint) => (
                <option value={checkpoint.checkpoint_id} key={checkpoint.checkpoint_id}>
                  {checkpoint.checkpoint_id} — {checkpoint.checkpoint_name}
                  {checkpoint.expected_value ? ` (${checkpoint.expected_value})` : ''}
                </option>
              ))
            ) : (
              <option value="">No checkpoints found</option>
            )}
          </select>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#4b5563', textTransform: 'uppercase' }}>
            Expected Colour
          </span>
          <select
            value={expectedColour}
            onChange={(event) => handleColourChange(event.target.value)}
            style={{
              padding: '6px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              backgroundColor: '#fff',
            }}
          >
            {SUPPORTED_COLOURS.map((c) => (
              <option value={c} key={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label className="debug-toggle">
          <input
            type="checkbox"
            checked={debug}
            onChange={(event) => {
              setDebug(event.target.checked)
              void inspectColour(selectedId, expectedColour)
            }}
          />
          <span>Show extracted ROI</span>
        </label>

        <button
          className="button button--ghost color-refresh"
          onClick={() => void loadColourCheckpoints(true)}
          disabled={loadingCheckpoints || processing}
          title="Reload checkpoints"
        >
          <RefreshCw size={17} className={loadingCheckpoints ? 'spin' : ''} />
          Refresh
        </button>

        <button
          className="button button--primary"
          onClick={() => void inspectColour()}
          disabled={!selectedId || processing}
        >
          <ScanSearch size={18} />
          {processing ? 'Analysing…' : 'Inspect colour'}
        </button>
      </div>

      {selectedCheckpoint && (
        <div className="selected-roi-summary">
          <Droplets size={17} />
          <span>
            <strong>{selectedCheckpoint.checkpoint_id}</strong> ({selectedCheckpoint.checkpoint_name}) uses ROI{' '}
            {selectedCheckpoint.roi_width} × {selectedCheckpoint.roi_height} px centred at X{' '}
            {selectedCheckpoint.reference_x}, Y {selectedCheckpoint.reference_y}.
          </span>
        </div>
      )}

      {error && (
        <div className="checkpoint-form-error" role="alert">
          {error}
        </div>
      )}

      {result ? (
        <div className={`color-result color-result--${result.status.toLowerCase()}`}>
          <div className="color-result-metrics">
            <article>
              <span>Expected colour</span>
              <strong>
                <i className={`colour-swatch colour-swatch--${result.expected_colour.toLowerCase()}`} />
                {result.expected_colour}
              </strong>
            </article>
            <article>
              <span>Detected colour</span>
              <strong>
                <i className={`colour-swatch colour-swatch--${result.detected_colour.toLowerCase()}`} />
                {result.detected_colour}
              </strong>
            </article>
            <article>
              <span>Mean HSV</span>
              <strong>H {result.mean_hsv.channel_1.toFixed(2)}</strong>
              <small>
                S {result.mean_hsv.channel_2.toFixed(2)} · V {result.mean_hsv.channel_3.toFixed(2)}
              </small>
            </article>
            <article>
              <span>Mean LAB</span>
              <strong>L {result.mean_lab.channel_1.toFixed(2)}</strong>
              <small>
                A {result.mean_lab.channel_2.toFixed(2)} · B {result.mean_lab.channel_3.toFixed(2)}
              </small>
            </article>
            <article>
              <span>Confidence</span>
              <strong>{(result.confidence * 100).toFixed(1)}%</strong>
              <small>Dominant-class estimate</small>
            </article>
            <article className="color-result-status">
              <span>Result</span>
              <strong>{result.status}</strong>
              <small>
                {result.expected_colour === result.detected_colour
                  ? 'Expected colour matched'
                  : 'Colour mismatch detected'}
              </small>
            </article>
          </div>
          {result.debug_roi_image && (
            <div className="roi-debug-view">
              <div>
                <p className="eyebrow">DEBUG OUTPUT</p>
                <h3>Extracted checkpoint ROI</h3>
                <span>
                  X {result.roi.x} · Y {result.roi.y} · {result.roi.width} × {result.roi.height} px
                </span>
              </div>
              <figure>
                <img src={result.debug_roi_image} alt={`Extracted ROI for ${result.checkpoint_id}`} />
                <figcaption>Read-only PNG preview</figcaption>
              </figure>
            </div>
          )}
          <p className="color-disclaimer">{result.disclaimer}</p>
        </div>
      ) : (
        <div className="color-result-empty">
          <Droplets size={29} />
          <span>
            {processing ? 'Analysing checkpoint colour…' : 'Select a configured checkpoint and run colour inspection.'}
          </span>
        </div>
      )}
    </section>
  )
}

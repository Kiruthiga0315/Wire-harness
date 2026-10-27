import { Crosshair, Pencil, Save, Trash2, X } from 'lucide-react'
import { Fragment, useEffect, useState } from 'react'
import type { MouseEvent } from 'react'
import { StatusPill } from './StatusPill'
import { DEMO_IMAGE_URL, createCheckpoint, deleteCheckpoint, getCheckpoints, updateCheckpoint } from '../services/api'
import type { CheckpointPayload, EngineeringCheckpoint } from '../types/checkpoint'

const MODEL_ID = 'DEMO-HARNESS-001'
const categories = ['Harness', 'Connector', 'Terminal', 'Branch', 'Junction', 'Clip', 'Sleeve', 'Tape', 'Cable Tie', 'Label', 'Barcode', 'Colour', 'Routing', 'Orientation', 'Dimension', 'Quality']
const inspectionTypes = ['Presence', 'Position', 'Orientation', 'Type', 'Colour', 'Length', 'Distance', 'Routing', 'Quality']

interface EngineeringCheckpointEditorProps {
  imageWidth: number
  imageHeight: number
  imageUrl?: string
}

interface EditorDraft extends CheckpointPayload {
  checkpoint_id?: string
}

function newDraft(x: number, y: number, sequence: number): EditorDraft {
  return {
    checkpoint_name: `Engineering Checkpoint ${sequence}`,
    category: 'Connector',
    inspection_type: 'Presence',
    expected_value: 'Present',
    tolerance: null,
    reference_x: x,
    reference_y: y,
    roi_width: 100,
    roi_height: 100,
    enabled: true,
  }
}

export function EngineeringCheckpointEditor({ imageWidth, imageHeight, imageUrl }: EngineeringCheckpointEditorProps) {
  const [checkpoints, setCheckpoints] = useState<EngineeringCheckpoint[]>([])
  const [draft, setDraft] = useState<EditorDraft | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getCheckpoints(MODEL_ID)
      .then(setCheckpoints)
      .catch((loadError: Error) => setError(loadError.message))
      .finally(() => setLoading(false))
  }, [])

  const updateDraft = <K extends keyof EditorDraft>(key: K, value: EditorDraft[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current)
  }

  const handleImageClick = (event: MouseEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = Math.max(0, Math.min(imageWidth, Math.round((event.clientX - bounds.left) * imageWidth / bounds.width)))
    const y = Math.max(0, Math.min(imageHeight, Math.round((event.clientY - bounds.top) * imageHeight / bounds.height)))
    setEditingId(null)
    setDraft(newDraft(x, y, checkpoints.length + 1))
    setError(null)
  }

  const editCheckpoint = (checkpoint: EngineeringCheckpoint) => {
    setEditingId(checkpoint.checkpoint_id)
    setDraft({
      checkpoint_id: checkpoint.checkpoint_id,
      checkpoint_name: checkpoint.checkpoint_name,
      category: checkpoint.category,
      inspection_type: checkpoint.inspection_type,
      expected_value: checkpoint.expected_value,
      tolerance: checkpoint.tolerance,
      reference_x: checkpoint.reference_x,
      reference_y: checkpoint.reference_y,
      roi_width: checkpoint.roi_width,
      roi_height: checkpoint.roi_height,
      enabled: checkpoint.enabled,
    })
    setError(null)
  }

  const cancelEdit = () => {
    setDraft(null)
    setEditingId(null)
    setError(null)
  }

  const saveDraft = async () => {
    if (!draft || !draft.checkpoint_name.trim()) {
      setError('Checkpoint name is required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload: CheckpointPayload = { ...draft, checkpoint_name: draft.checkpoint_name.trim() }
      const saved = editingId
        ? await updateCheckpoint(MODEL_ID, editingId, payload)
        : await createCheckpoint(MODEL_ID, payload)
      setCheckpoints((current) => {
        const exists = current.some((checkpoint) => checkpoint.checkpoint_id === saved.checkpoint_id)
        return exists
          ? current.map((checkpoint) => checkpoint.checkpoint_id === saved.checkpoint_id ? saved : checkpoint)
          : [...current, saved]
      })
      setDraft(null)
      setEditingId(null)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save checkpoint.')
    } finally {
      setSaving(false)
    }
  }

  const removeCheckpoint = async (checkpoint: EngineeringCheckpoint) => {
    if (!window.confirm(`Delete ${checkpoint.checkpoint_id} — ${checkpoint.checkpoint_name}?`)) return
    setError(null)
    try {
      await deleteCheckpoint(MODEL_ID, checkpoint.checkpoint_id)
      setCheckpoints((current) => current.filter((item) => item.checkpoint_id !== checkpoint.checkpoint_id))
      if (editingId === checkpoint.checkpoint_id) cancelEdit()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete checkpoint.')
    }
  }

  const displayCheckpoints = checkpoints.map((checkpoint) => {
    if (editingId === checkpoint.checkpoint_id && draft) return { ...checkpoint, ...draft }
    return checkpoint
  })

  return (
    <section className="checkpoint-editor-layout">
      <article className="panel checkpoint-canvas-panel">
        <div className="panel-header"><div><p className="eyebrow">REFERENCE IMAGE</p><h2>Checkpoint placement</h2></div><div className="checkpoint-legend"><span><i className="legend-checkpoint" />Configured checkpoint</span><span><i className="legend-roi" />ROI boundary</span></div></div>
        <div className="checkpoint-canvas-stage">
          <div
            className="checkpoint-image-layer"
            style={{ aspectRatio: `${imageWidth} / ${imageHeight}` }}
            onClick={handleImageClick}
            role="application"
            aria-label="Click the harness image to add an engineering checkpoint"
          >
            <img src={imageUrl || DEMO_IMAGE_URL} alt="Harness sample for checkpoint placement" draggable={false} />
            {displayCheckpoints.map((checkpoint) => (
              <Fragment key={checkpoint.checkpoint_id}>
                <span
                  className={`checkpoint-roi ${editingId === checkpoint.checkpoint_id ? 'checkpoint-roi--selected' : ''}`}
                  style={{
                    left: `${(checkpoint.reference_x - checkpoint.roi_width / 2) * 100 / imageWidth}%`,
                    top: `${(checkpoint.reference_y - checkpoint.roi_height / 2) * 100 / imageHeight}%`,
                    width: `${checkpoint.roi_width * 100 / imageWidth}%`,
                    height: `${checkpoint.roi_height * 100 / imageHeight}%`,
                  }}
                />
                <button
                  className={`configured-checkpoint ${editingId === checkpoint.checkpoint_id ? 'configured-checkpoint--selected' : ''}`}
                  style={{ left: `${checkpoint.reference_x * 100 / imageWidth}%`, top: `${checkpoint.reference_y * 100 / imageHeight}%` }}
                  onClick={(event) => { event.stopPropagation(); const original = checkpoints.find((item) => item.checkpoint_id === checkpoint.checkpoint_id); if (original) editCheckpoint(original) }}
                  title={`${checkpoint.checkpoint_id}: ${checkpoint.checkpoint_name}`}
                  aria-label={`Edit ${checkpoint.checkpoint_id}: ${checkpoint.checkpoint_name}`}
                ><i /><span>{checkpoint.checkpoint_id}</span></button>
              </Fragment>
            ))}
            {!editingId && draft && (
              <>
                <span className="checkpoint-roi checkpoint-roi--draft" style={{ left: `${(draft.reference_x - draft.roi_width / 2) * 100 / imageWidth}%`, top: `${(draft.reference_y - draft.roi_height / 2) * 100 / imageHeight}%`, width: `${draft.roi_width * 100 / imageWidth}%`, height: `${draft.roi_height * 100 / imageHeight}%` }} />
                <span className="draft-checkpoint" style={{ left: `${draft.reference_x * 100 / imageWidth}%`, top: `${draft.reference_y * 100 / imageHeight}%` }}><i />NEW</span>
              </>
            )}
          </div>
        </div>
        <footer className="checkpoint-canvas-footer"><span><Crosshair size={15} />Click anywhere on the image to create a checkpoint.</span><strong>{imageWidth} × {imageHeight} px</strong></footer>
      </article>

      <aside className="panel checkpoint-editor-panel">
        <div className="panel-header"><div><p className="eyebrow">MODEL {MODEL_ID}</p><h2>{draft ? (editingId ? `Edit ${editingId}` : 'New checkpoint') : 'Checkpoint editor'}</h2></div><StatusPill tone="info">{checkpoints.length} SAVED</StatusPill></div>
        {error && <div className="checkpoint-form-error" role="alert">{error}</div>}
        {!draft ? (
          <div className="checkpoint-editor-empty"><Crosshair size={34} /><strong>{loading ? 'LOADING CHECKPOINTS…' : 'SELECT A POSITION'}</strong><span>Click the image or select a saved checkpoint below.</span></div>
        ) : (
          <div className="checkpoint-form">
            <label className="form-field form-field--wide"><span>Checkpoint name</span><input value={draft.checkpoint_name} onChange={(event) => updateDraft('checkpoint_name', event.target.value)} maxLength={180} /></label>
            <label className="form-field"><span>Category</span><input list="checkpoint-categories" value={draft.category} onChange={(event) => updateDraft('category', event.target.value)} /><datalist id="checkpoint-categories">{categories.map((category) => <option key={category} value={category} />)}</datalist></label>
            <label className="form-field"><span>Inspection type</span><input list="inspection-types" value={draft.inspection_type} onChange={(event) => updateDraft('inspection_type', event.target.value)} /><datalist id="inspection-types">{inspectionTypes.map((type) => <option key={type} value={type} />)}</datalist></label>
            <label className="form-field form-field--wide"><span>Expected value</span><input value={draft.expected_value ?? ''} onChange={(event) => updateDraft('expected_value', event.target.value || null)} placeholder="Present, Blue, 90°, etc." /></label>
            <label className="form-field"><span>Tolerance</span><input type="number" min="0" step="0.1" value={draft.tolerance ?? ''} onChange={(event) => updateDraft('tolerance', event.target.value === '' ? null : Number(event.target.value))} placeholder="Optional" /></label>
            <div className="form-field coordinate-readout"><span>Pixel position</span><strong>X {draft.reference_x} / Y {draft.reference_y}</strong></div>
            <label className="form-field"><span>Pixel X</span><input type="number" min="0" max={imageWidth} value={draft.reference_x} onChange={(event) => updateDraft('reference_x', Number(event.target.value))} /></label>
            <label className="form-field"><span>Pixel Y</span><input type="number" min="0" max={imageHeight} value={draft.reference_y} onChange={(event) => updateDraft('reference_y', Number(event.target.value))} /></label>
            <label className="form-field"><span>ROI width (px)</span><input type="number" min="1" max={imageWidth} value={draft.roi_width} onChange={(event) => updateDraft('roi_width', Number(event.target.value))} /></label>
            <label className="form-field"><span>ROI height (px)</span><input type="number" min="1" max={imageHeight} value={draft.roi_height} onChange={(event) => updateDraft('roi_height', Number(event.target.value))} /></label>
            <div className="checkpoint-form-actions"><button className="button button--primary" onClick={() => void saveDraft()} disabled={saving}><Save size={17} />{saving ? 'Saving…' : editingId ? 'Update checkpoint' : 'Save checkpoint'}</button><button className="button button--ghost" onClick={cancelEdit}><X size={17} />Cancel</button></div>
          </div>
        )}

        <div className="saved-checkpoints">
          <div className="saved-checkpoints-title"><span>SAVED CHECKPOINTS</span><small>{MODEL_ID}</small></div>
          {checkpoints.length === 0 && !loading ? <p>No checkpoints configured.</p> : checkpoints.map((checkpoint) => (
            <div className={`saved-checkpoint-row ${editingId === checkpoint.checkpoint_id ? 'saved-checkpoint-row--active' : ''}`} key={checkpoint.checkpoint_id}>
              <button className="saved-checkpoint-main" onClick={() => editCheckpoint(checkpoint)}><i /><span><strong>{checkpoint.checkpoint_id} · {checkpoint.checkpoint_name}</strong><small>{checkpoint.category} / {checkpoint.inspection_type} · X{checkpoint.reference_x} Y{checkpoint.reference_y}</small></span></button>
              <button className="row-icon-button" onClick={() => editCheckpoint(checkpoint)} aria-label={`Edit ${checkpoint.checkpoint_id}`}><Pencil size={15} /></button>
              <button className="row-icon-button row-icon-button--delete" onClick={() => void removeCheckpoint(checkpoint)} aria-label={`Delete ${checkpoint.checkpoint_id}`}><Trash2 size={15} /></button>
            </div>
          ))}
        </div>
      </aside>
    </section>
  )
}

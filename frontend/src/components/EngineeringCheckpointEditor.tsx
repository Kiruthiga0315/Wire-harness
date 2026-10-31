import { CheckCircle2, Crosshair, Pencil, RefreshCw, Save, Search, Trash2, X } from 'lucide-react'
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import type { MouseEvent } from 'react'
import { StatusPill } from './StatusPill'
import {
  ACTIVE_IMAGE_URL,
  createCheckpoint,
  deleteCheckpoint,
  getCheckpoints,
  syncCheckpointsFromGolden,
  updateCheckpoint,
} from '../services/api'
import type { CheckpointPayload, EngineeringCheckpoint } from '../types/checkpoint'

const MODEL_ID = 'DEMO-HARNESS-001'
const categories = ['Harness', 'Connector', 'Terminal', 'Branch', 'Junction', 'Clip', 'Sleeve', 'Tape', 'Cable Tie', 'Label', 'Barcode', 'Colour', 'Routing', 'Orientation', 'Dimension', 'Quality']
const inspectionTypes = ['Presence', 'Position', 'Orientation', 'Type', 'Colour', 'Length', 'Distance', 'Routing', 'Quality']

interface EngineeringCheckpointEditorProps {
  imageWidth: number
  imageHeight: number
  imageUrl?: string
  refreshTrigger?: number
  onCheckpointsChanged?: (checkpoints: EngineeringCheckpoint[]) => void
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

export function EngineeringCheckpointEditor({
  imageWidth,
  imageHeight,
  imageUrl,
  refreshTrigger,
  onCheckpointsChanged,
}: EngineeringCheckpointEditorProps) {
  const [checkpoints, setCheckpoints] = useState<EngineeringCheckpoint[]>([])
  const [draft, setDraft] = useState<EditorDraft | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterCategory, setFilterCategory] = useState<string>('all')
  const [naturalDimensions, setNaturalDimensions] = useState<{ width: number; height: number } | null>(null)

  const effectiveW = naturalDimensions?.width || (imageWidth > 0 ? imageWidth : 1800)
  const effectiveH = naturalDimensions?.height || (imageHeight > 0 ? imageHeight : 560)

  const fetchCheckpoints = useCallback(async () => {
    setLoading(true)
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
      onCheckpointsChanged?.(records)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load checkpoints.')
    } finally {
      setLoading(false)
    }
  }, [onCheckpointsChanged])

  useEffect(() => {
    void fetchCheckpoints()
  }, [fetchCheckpoints, refreshTrigger])

  const handleSyncGolden = async () => {
    setSyncing(true)
    setError(null)
    setSyncFeedback(null)
    try {
      const synced = await syncCheckpointsFromGolden(MODEL_ID, true, true)
      setCheckpoints(synced)
      onCheckpointsChanged?.(synced)
      setSyncFeedback(`Synced ${synced.length} checkpoints from Golden Reference & Checkpoints`)
      cancelEdit()
      setTimeout(() => setSyncFeedback(null), 6000)
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : 'Failed to sync from Golden Reference.')
    } finally {
      setSyncing(false)
    }
  }

  const updateDraft = <K extends keyof EditorDraft>(key: K, value: EditorDraft[K]) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current))
  }

  const handleImageClick = (event: MouseEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = Math.max(0, Math.min(effectiveW, Math.round(((event.clientX - bounds.left) * effectiveW) / bounds.width)))
    const y = Math.max(0, Math.min(effectiveH, Math.round(((event.clientY - bounds.top) * effectiveH) / bounds.height)))
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
        const updated = exists
          ? current.map((checkpoint) => (checkpoint.checkpoint_id === saved.checkpoint_id ? saved : checkpoint))
          : [...current, saved]
        onCheckpointsChanged?.(updated)
        return updated
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
      setCheckpoints((current) => {
        const filtered = current.filter((item) => item.checkpoint_id !== checkpoint.checkpoint_id)
        onCheckpointsChanged?.(filtered)
        return filtered
      })
      if (editingId === checkpoint.checkpoint_id) cancelEdit()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete checkpoint.')
    }
  }

  const displayCheckpoints = useMemo(() => {
    return checkpoints.map((checkpoint) => {
      if (editingId === checkpoint.checkpoint_id && draft) return { ...checkpoint, ...draft }
      return checkpoint
    })
  }, [checkpoints, editingId, draft])

  const filteredCheckpoints = useMemo(() => {
    return displayCheckpoints.filter((checkpoint) => {
      if (filterCategory !== 'all') {
        if (filterCategory === 'Terminal' && checkpoint.category !== 'Terminal') return false
        if (filterCategory === 'Dimension' && checkpoint.category !== 'Dimension') return false
        if (filterCategory === 'Junction' && checkpoint.category !== 'Junction') return false
        if (filterCategory === 'Tape' && checkpoint.category !== 'Tape') return false
        if (
          filterCategory === 'Other' &&
          ['Terminal', 'Dimension', 'Junction', 'Tape'].includes(checkpoint.category)
        )
          return false
      }
      if (!searchTerm.trim()) return true
      const term = searchTerm.toLowerCase().trim()
      return (
        checkpoint.checkpoint_id.toLowerCase().includes(term) ||
        checkpoint.checkpoint_name.toLowerCase().includes(term) ||
        checkpoint.category.toLowerCase().includes(term) ||
        (checkpoint.expected_value && checkpoint.expected_value.toLowerCase().includes(term))
      )
    })
  }, [displayCheckpoints, filterCategory, searchTerm])

  const isGoldenSynced = useMemo(() => {
    return checkpoints.some((c) => c.checkpoint_id.startsWith('CP-T') || c.checkpoint_id.startsWith('CP-NODE-'))
  }, [checkpoints])

  return (
    <section className="checkpoint-editor-layout">
      <article className="panel checkpoint-canvas-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">REFERENCE IMAGE</p>
            <h2>Checkpoint placement</h2>
          </div>
          <div className="checkpoint-legend">
            <span>
              <i className="legend-checkpoint" />
              Configured checkpoint
            </span>
            <span>
              <i className="legend-roi" />
              ROI boundary
            </span>
          </div>
        </div>
        <div className="checkpoint-canvas-stage">
          <div
            className="checkpoint-image-layer"
            style={{ aspectRatio: `${effectiveW} / ${effectiveH}` }}
            onClick={handleImageClick}
            role="application"
            aria-label="Click the harness image to add an engineering checkpoint"
          >
            <img
              src={imageUrl || ACTIVE_IMAGE_URL}
              alt="Harness sample for checkpoint placement"
              draggable={false}
              onLoad={(e) => {
                if (e.currentTarget.naturalWidth && e.currentTarget.naturalHeight) {
                  setNaturalDimensions({
                    width: e.currentTarget.naturalWidth,
                    height: e.currentTarget.naturalHeight,
                  })
                }
              }}
              style={{ width: '100%', height: '100%', display: 'block', objectFit: 'fill', pointerEvents: 'none' }}
            />
            {displayCheckpoints.map((checkpoint) => (
              <Fragment key={checkpoint.checkpoint_id}>
                <span
                  className={`checkpoint-roi ${editingId === checkpoint.checkpoint_id ? 'checkpoint-roi--selected' : ''}`}
                  style={{
                    left: `${((checkpoint.reference_x - checkpoint.roi_width / 2) * 100) / effectiveW}%`,
                    top: `${((checkpoint.reference_y - checkpoint.roi_height / 2) * 100) / effectiveH}%`,
                    width: `${(checkpoint.roi_width * 100) / effectiveW}%`,
                    height: `${(checkpoint.roi_height * 100) / effectiveH}%`,
                  }}
                />
                <button
                  className={`configured-checkpoint ${editingId === checkpoint.checkpoint_id ? 'configured-checkpoint--selected' : ''}`}
                  style={{
                    left: `${(checkpoint.reference_x * 100) / effectiveW}%`,
                    top: `${(checkpoint.reference_y * 100) / effectiveH}%`,
                  }}
                  onClick={(event) => {
                    event.stopPropagation()
                    const original = checkpoints.find((item) => item.checkpoint_id === checkpoint.checkpoint_id)
                    if (original) editCheckpoint(original)
                  }}
                  title={`${checkpoint.checkpoint_id}: ${checkpoint.checkpoint_name}`}
                  aria-label={`Edit ${checkpoint.checkpoint_id}: ${checkpoint.checkpoint_name}`}
                >
                  <i />
                  <span>{checkpoint.checkpoint_id}</span>
                </button>
              </Fragment>
            ))}
            {!editingId && draft && (
              <>
                <span
                  className="checkpoint-roi checkpoint-roi--draft"
                  style={{
                    left: `${((draft.reference_x - draft.roi_width / 2) * 100) / effectiveW}%`,
                    top: `${((draft.reference_y - draft.roi_height / 2) * 100) / effectiveH}%`,
                    width: `${(draft.roi_width * 100) / effectiveW}%`,
                    height: `${(draft.roi_height * 100) / effectiveH}%`,
                  }}
                />
                <span
                  className="draft-checkpoint"
                  style={{
                    left: `${(draft.reference_x * 100) / effectiveW}%`,
                    top: `${(draft.reference_y * 100) / effectiveH}%`,
                  }}
                >
                  <i />
                  NEW
                </span>
              </>
            )}
          </div>
        </div>
        <footer className="checkpoint-canvas-footer">
          <span>
            <Crosshair size={15} />
            Click anywhere on the image to create a checkpoint.
          </span>
          <strong>
            {effectiveW} × {effectiveH} px
          </strong>
        </footer>
      </article>

      <aside className="panel checkpoint-editor-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">MODEL {MODEL_ID}</p>
            <h2>{draft ? (editingId ? `Edit ${editingId}` : 'New checkpoint') : 'Checkpoint editor'}</h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
            <button
              type="button"
              className="button button--secondary"
              style={{
                minHeight: '26px',
                height: '26px',
                padding: '0 8px',
                fontSize: '10px',
                gap: '4px',
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}
              onClick={() => void handleSyncGolden()}
              disabled={syncing || loading}
              title="Synchronize all checkpoints from Golden Reference & Checkpoints"
            >
              <RefreshCw size={12} className={syncing ? 'spin' : ''} />
              <span>{syncing ? 'Syncing…' : 'Sync from Golden'}</span>
            </button>
            <StatusPill tone={isGoldenSynced ? 'pass' : 'info'}>
              {checkpoints.length} {isGoldenSynced ? 'SYNCED' : 'SAVED'}
            </StatusPill>
          </div>
        </div>

        {syncFeedback && (
          <div
            className="checkpoint-sync-feedback"
            style={{
              margin: '10px 14px 0',
              padding: '8px 12px',
              background: '#ecfdf5',
              border: '1px solid #a7f3d0',
              borderRadius: '4px',
              color: '#065f46',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <CheckCircle2 size={15} style={{ color: '#059669', flexShrink: 0 }} />
            <span>{syncFeedback}</span>
          </div>
        )}

        {error && (
          <div className="checkpoint-form-error" role="alert">
            {error}
          </div>
        )}

        {!draft ? (
          <div className="checkpoint-editor-empty">
            <Crosshair size={34} />
            <strong>{loading ? 'LOADING CHECKPOINTS…' : 'SELECT A POSITION'}</strong>
            <span>Click the image or select a saved checkpoint below.</span>
          </div>
        ) : (
          <div className="checkpoint-form">
            <label className="form-field form-field--wide">
              <span>Checkpoint name</span>
              <input
                value={draft.checkpoint_name}
                onChange={(event) => updateDraft('checkpoint_name', event.target.value)}
                maxLength={180}
              />
            </label>
            <label className="form-field">
              <span>Category</span>
              <input
                list="checkpoint-categories"
                value={draft.category}
                onChange={(event) => updateDraft('category', event.target.value)}
              />
              <datalist id="checkpoint-categories">
                {categories.map((category) => (
                  <option key={category} value={category} />
                ))}
              </datalist>
            </label>
            <label className="form-field">
              <span>Inspection type</span>
              <input
                list="inspection-types"
                value={draft.inspection_type}
                onChange={(event) => updateDraft('inspection_type', event.target.value)}
              />
              <datalist id="inspection-types">
                {inspectionTypes.map((type) => (
                  <option key={type} value={type} />
                ))}
              </datalist>
            </label>
            <label className="form-field form-field--wide">
              <span>Expected value</span>
              <input
                value={draft.expected_value ?? ''}
                onChange={(event) => updateDraft('expected_value', event.target.value || null)}
                placeholder="Present, Blue, 90°, etc."
              />
            </label>
            <label className="form-field">
              <span>Tolerance</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={draft.tolerance ?? ''}
                onChange={(event) =>
                  updateDraft('tolerance', event.target.value === '' ? null : Number(event.target.value))
                }
                placeholder="Optional"
              />
            </label>
            <div className="form-field coordinate-readout">
              <span>Pixel position</span>
              <strong>
                X {draft.reference_x} / Y {draft.reference_y}
              </strong>
            </div>
            <label className="form-field">
              <span>Pixel X</span>
              <input
                type="number"
                min="0"
                max={effectiveW}
                value={draft.reference_x}
                onChange={(event) => updateDraft('reference_x', Number(event.target.value))}
              />
            </label>
            <label className="form-field">
              <span>Pixel Y</span>
              <input
                type="number"
                min="0"
                max={effectiveH}
                value={draft.reference_y}
                onChange={(event) => updateDraft('reference_y', Number(event.target.value))}
              />
            </label>
            <label className="form-field">
              <span>ROI width (px)</span>
              <input
                type="number"
                min="1"
                max={effectiveW}
                value={draft.roi_width}
                onChange={(event) => updateDraft('roi_width', Number(event.target.value))}
              />
            </label>
            <label className="form-field">
              <span>ROI height (px)</span>
              <input
                type="number"
                min="1"
                max={effectiveH}
                value={draft.roi_height}
                onChange={(event) => updateDraft('roi_height', Number(event.target.value))}
              />
            </label>
            <div className="checkpoint-form-actions">
              <button className="button button--primary" onClick={() => void saveDraft()} disabled={saving}>
                <Save size={17} />
                {saving ? 'Saving…' : editingId ? 'Update checkpoint' : 'Save checkpoint'}
              </button>
              <button className="button button--ghost" onClick={cancelEdit}>
                <X size={17} />
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="saved-checkpoints">
          <div className="saved-checkpoints-title">
            <span>SAVED CHECKPOINTS</span>
            <small>
              {isGoldenSynced ? 'GOLDEN SYNCED · ' : ''}
              {filteredCheckpoints.length} / {checkpoints.length}
            </small>
          </div>

          <div
            style={{
              padding: '8px 12px',
              background: '#fafbfc',
              borderBottom: '1px solid #edf0f3',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ position: 'relative', width: '100%' }}>
              <Search
                size={13}
                style={{ position: 'absolute', left: '8px', top: '8px', color: '#94a3b8' }}
              />
              <input
                type="text"
                placeholder="Filter checkpoints (e.g. T01, J01, Node)..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: '100%',
                  height: '28px',
                  paddingLeft: '26px',
                  paddingRight: '8px',
                  fontSize: '11px',
                  border: '1px solid #ccd6e0',
                  borderRadius: '3px',
                  background: 'white',
                  outline: 'none',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
              {[
                { key: 'all', label: 'All', count: checkpoints.length },
                {
                  key: 'Terminal',
                  label: 'Terminals',
                  count: checkpoints.filter((c) => c.category === 'Terminal').length,
                },
                {
                  key: 'Dimension',
                  label: 'Nodes',
                  count: checkpoints.filter((c) => c.category === 'Dimension').length,
                },
                {
                  key: 'Junction',
                  label: 'Junctions',
                  count: checkpoints.filter((c) => c.category === 'Junction').length,
                },
                {
                  key: 'Tape',
                  label: 'Tape',
                  count: checkpoints.filter((c) => c.category === 'Tape').length,
                },
              ].map(({ key, label, count }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilterCategory(key)}
                  style={{
                    fontSize: '10px',
                    padding: '2px 7px',
                    borderRadius: '3px',
                    border: '1px solid',
                    borderColor: filterCategory === key ? 'var(--blue-600)' : '#d0d9e2',
                    background: filterCategory === key ? 'var(--blue-600)' : 'white',
                    color: filterCategory === key ? 'white' : 'var(--slate-700)',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    fontWeight: filterCategory === key ? 700 : 500,
                  }}
                >
                  {label} ({count})
                </button>
              ))}
            </div>
          </div>

          {filteredCheckpoints.length === 0 && !loading ? (
            <p>
              {searchTerm || filterCategory !== 'all'
                ? 'No checkpoints match the filter.'
                : 'No checkpoints configured. Click "Sync from Golden" above.'}
            </p>
          ) : (
            filteredCheckpoints.map((checkpoint) => (
              <div
                className={`saved-checkpoint-row ${editingId === checkpoint.checkpoint_id ? 'saved-checkpoint-row--active' : ''}`}
                key={checkpoint.checkpoint_id}
              >
                <button className="saved-checkpoint-main" onClick={() => editCheckpoint(checkpoint)}>
                  <i />
                  <span>
                    <strong>
                      {checkpoint.checkpoint_id} · {checkpoint.checkpoint_name}
                    </strong>
                    <small>
                      {checkpoint.category} / {checkpoint.inspection_type}
                      {checkpoint.expected_value ? ` · ${checkpoint.expected_value}` : ''} · X
                      {checkpoint.reference_x} Y{checkpoint.reference_y}
                    </small>
                  </span>
                </button>
                <button
                  className="row-icon-button"
                  onClick={() => editCheckpoint(checkpoint)}
                  aria-label={`Edit ${checkpoint.checkpoint_id}`}
                >
                  <Pencil size={15} />
                </button>
                <button
                  className="row-icon-button row-icon-button--delete"
                  onClick={() => void removeCheckpoint(checkpoint)}
                  aria-label={`Delete ${checkpoint.checkpoint_id}`}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>
    </section>
  )
}


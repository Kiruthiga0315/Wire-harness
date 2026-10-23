import { CheckCircle2, Copy, Eye, Info, Pencil, Play, Plus, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { DEMO_IMAGE_URL, getCheckpoints } from '../services/api'
import type { EngineeringCheckpoint } from '../types/checkpoint'

export interface RecipeModel {
  id: string
  name: string
  revision: string
  checkpointsCount: number
  referenceImage: string
  created: string
  status: 'ACTIVE' | 'DRAFT' | 'INACTIVE'
  description?: string
}

const DEFAULT_MODELS: RecipeModel[] = [
  {
    id: 'DEMO-HARNESS-001',
    name: 'Client Wire Harness Sample',
    revision: 'V1.0',
    checkpointsCount: 12,
    referenceImage: 'harness_sample_01.jpeg',
    created: '12 Aug 2026',
    status: 'ACTIVE',
    description: 'Deterministic demo recipe with 12 CP-* checkpoints for connectors, terminals, and routing.',
  },
]

const STORAGE_KEY = 'harnessvision_configured_models'

export function ModelsPage() {
  const navigate = useNavigate()
  const [models, setModels] = useState<RecipeModel[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored) as RecipeModel[]
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch {
      // fallback
    }
    return DEFAULT_MODELS
  })

  // Modals state
  const [viewModel, setViewModel] = useState<RecipeModel | null>(null)
  const [viewCheckpoints, setViewCheckpoints] = useState<EngineeringCheckpoint[]>([])
  const [loadingCheckpoints, setLoadingCheckpoints] = useState(false)
  const [editModel, setEditModel] = useState<RecipeModel | null>(null)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'info' } | null>(null)

  // New model draft
  const [newModel, setNewModel] = useState<RecipeModel>({
    id: '',
    name: '',
    revision: 'V1.0',
    checkpointsCount: 12,
    referenceImage: 'harness_sample_01.jpeg',
    created: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
    status: 'ACTIVE',
    description: '',
  })

  // Save to localStorage whenever models change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(models))
    } catch {
      // storage quota or private mode
    }
  }, [models])

  // Toast timer
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(timer)
  }, [toast])

  const showToast = (message: string, type: 'success' | 'info' = 'success') => {
    setToast({ message, type })
  }

  // Load checkpoints when view modal opens
  const handleOpenView = (model: RecipeModel) => {
    setViewModel(model)
    setLoadingCheckpoints(true)
    getCheckpoints(model.id)
      .then((data) => setViewCheckpoints(data))
      .catch(() => setViewCheckpoints([]))
      .finally(() => setLoadingCheckpoints(false))
  }

  // Duplicate model
  const handleCloneModel = (model: RecipeModel) => {
    const cloneId = `${model.id}-COPY-${Date.now().toString().slice(-4)}`
    const cloned: RecipeModel = {
      ...model,
      id: cloneId,
      name: `${model.name} (Copy)`,
      revision: 'V1.0-draft',
      status: 'DRAFT',
      created: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
    }
    setModels((prev) => [...prev, cloned])
    showToast(`Recipe duplicated as ${cloneId}`)
  }

  // Delete model
  const handleDeleteModel = (id: string) => {
    if (models.length <= 1) {
      showToast('Cannot delete the last remaining model recipe.', 'info')
      return
    }
    setModels((prev) => prev.filter((m) => m.id !== id))
    showToast(`Model ${id} removed.`, 'info')
  }

  // Save edits
  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editModel) return
    setModels((prev) => prev.map((m) => (m.id === editModel.id ? editModel : m)))
    showToast(`Recipe ${editModel.id} updated successfully.`)
    setEditModel(null)
  }

  // Create new model
  const handleCreateModel = (e: React.FormEvent) => {
    e.preventDefault()
    const id = newModel.id.trim().toUpperCase()
    if (!id || !newModel.name.trim()) return

    if (models.some((m) => m.id === id)) {
      showToast(`Model ID ${id} already exists.`, 'info')
      return
    }

    const createdItem: RecipeModel = {
      ...newModel,
      id,
      name: newModel.name.trim(),
    }
    setModels((prev) => [...prev, createdItem])
    showToast(`Recipe ${id} created.`)
    setIsAddOpen(false)
    setNewModel({
      id: '',
      name: '',
      revision: 'V1.0',
      checkpointsCount: 12,
      referenceImage: 'harness_sample_01.jpeg',
      created: new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
      status: 'ACTIVE',
      description: '',
    })
  }

  return (
    <>
      <PageHeader
        eyebrow="CONFIGURATION"
        title="Models / Recipes"
        description="Manage product-specific inspection recipes, revisions, and reference standards."
        actions={
          <button
            className="button button--primary"
            onClick={() => setIsAddOpen(true)}
            aria-label="Add new model"
          >
            <Plus size={18} />
            Add model
          </button>
        }
      />

      <article className="panel placeholder-table-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">PRODUCT LIBRARY</p>
            <h2>Configured models ({models.length})</h2>
          </div>
          <span className="mock-tag">DEMO & PRODUCTION</span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model ID</th>
                <th>Model name</th>
                <th>Revision</th>
                <th>Checkpoints</th>
                <th>Reference</th>
                <th>Created</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <tr key={model.id}>
                  <td><strong>{model.id}</strong></td>
                  <td>{model.name}</td>
                  <td>{model.revision}</td>
                  <td>{model.checkpointsCount} checkpoints</td>
                  <td>{model.referenceImage}</td>
                  <td>{model.created}</td>
                  <td>
                    <StatusPill tone={model.status === 'ACTIVE' ? 'pass' : model.status === 'DRAFT' ? 'warning' : 'neutral'}>
                      {model.status}
                    </StatusPill>
                  </td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="action--view"
                        aria-label={`View ${model.id}`}
                        title="View recipe details"
                        onClick={() => handleOpenView(model)}
                      >
                        <Eye size={17} />
                      </button>
                      <button
                        type="button"
                        className="action--edit"
                        aria-label={`Edit ${model.id}`}
                        title="Edit recipe parameters"
                        onClick={() => setEditModel({ ...model })}
                      >
                        <Pencil size={17} />
                      </button>
                      <button
                        type="button"
                        className="action--clone"
                        aria-label={`Clone ${model.id}`}
                        title="Duplicate recipe"
                        onClick={() => handleCloneModel(model)}
                      >
                        <Copy size={17} />
                      </button>
                      {models.length > 1 && (
                        <button
                          type="button"
                          className="action--delete"
                          aria-label={`Delete ${model.id}`}
                          title="Delete model"
                          onClick={() => handleDeleteModel(model.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="empty-footer">
          Click the <Eye size={12} style={{ verticalAlign: 'middle', margin: '0 2px' }} /> View button to inspect checkpoints, <Pencil size={12} style={{ verticalAlign: 'middle', margin: '0 2px' }} /> to edit metadata, or <Copy size={12} style={{ verticalAlign: 'middle', margin: '0 2px' }} /> to duplicate a recipe.
        </div>
      </article>

      {/* VIEW MODEL MODAL */}
      {viewModel && (
        <div className="modal-backdrop" onClick={() => setViewModel(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="modal-header">
              <h3>
                <Eye size={20} color="var(--blue-600)" />
                <span>{viewModel.id} — Recipe Details</span>
                <StatusPill tone={viewModel.status === 'ACTIVE' ? 'pass' : 'warning'}>{viewModel.status}</StatusPill>
              </h3>
              <button className="icon-button" onClick={() => setViewModel(null)} aria-label="Close modal">
                <X size={19} />
              </button>
            </div>
            <div className="modal-body">
              <dl className="model-spec-grid">
                <div className="model-spec-item">
                  <dt>Model Name</dt>
                  <dd>{viewModel.name}</dd>
                </div>
                <div className="model-spec-item">
                  <dt>Revision</dt>
                  <dd>{viewModel.revision}</dd>
                </div>
                <div className="model-spec-item">
                  <dt>Reference Master File</dt>
                  <dd>{viewModel.referenceImage}</dd>
                </div>
                <div className="model-spec-item">
                  <dt>Created Date</dt>
                  <dd>{viewModel.created}</dd>
                </div>
              </dl>

              <div>
                <p className="eyebrow" style={{ marginBottom: 6 }}>GOLDEN REFERENCE HARNESS IMAGE</p>
                <img
                  src={DEMO_IMAGE_URL}
                  alt={viewModel.referenceImage}
                  className="model-preview-image"
                  onError={(e) => {
                    e.currentTarget.src = '/harness_sample_01.jpeg'
                  }}
                />
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <p className="eyebrow" style={{ margin: 0 }}>
                    REGISTERED CHECKPOINTS ({loadingCheckpoints ? 'Loading…' : viewCheckpoints.length || viewModel.checkpointsCount})
                  </p>
                  <small style={{ color: 'var(--slate-500)', fontSize: 10 }}>Target tolerance: ±1.5 mm / Strict</small>
                </div>

                <div className="checkpoint-mini-wrap">
                  <table className="checkpoint-mini-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Category</th>
                        <th>Type</th>
                        <th>Expected</th>
                        <th>ROI (X, Y)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {viewCheckpoints.length > 0 ? (
                        viewCheckpoints.map((cp) => (
                          <tr key={cp.checkpoint_id}>
                            <td><strong>{cp.checkpoint_id}</strong></td>
                            <td>{cp.checkpoint_name}</td>
                            <td>{cp.category}</td>
                            <td>{cp.inspection_type}</td>
                            <td><StatusPill tone="info">{cp.expected_value || 'Present'}</StatusPill></td>
                            <td><code>{cp.reference_x}, {cp.reference_y}</code></td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} style={{ textAlign: 'center', color: 'var(--slate-500)', padding: 14 }}>
                            {loadingCheckpoints ? 'Fetching checkpoints from backend database…' : '12 default deterministic checkpoints (CP-001 through CP-012) assigned.'}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="button button--secondary"
                onClick={() => {
                  setEditModel({ ...viewModel })
                  setViewModel(null)
                }}
              >
                <Pencil size={15} />
                Edit recipe
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={() => {
                  navigate('/live')
                }}
              >
                <Play size={15} />
                Inspect in Live View
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT MODEL MODAL */}
      {editModel && (
        <div className="modal-backdrop" onClick={() => setEditModel(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <form onSubmit={handleSaveEdit}>
              <div className="modal-header">
                <h3>
                  <Pencil size={20} color="var(--amber-600)" />
                  <span>Edit Recipe: {editModel.id}</span>
                </h3>
                <button type="button" className="icon-button" onClick={() => setEditModel(null)} aria-label="Close modal">
                  <X size={19} />
                </button>
              </div>
              <div className="modal-body">
                <label className="form-field form-field--wide">
                  <span>Model ID (Identifier)</span>
                  <input type="text" value={editModel.id} disabled style={{ background: '#f5f7f9', cursor: 'not-allowed' }} />
                </label>
                <label className="form-field form-field--wide">
                  <span>Model Name</span>
                  <input
                    type="text"
                    required
                    value={editModel.name}
                    onChange={(e) => setEditModel({ ...editModel, name: e.target.value })}
                  />
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <label className="form-field">
                    <span>Revision</span>
                    <input
                      type="text"
                      required
                      value={editModel.revision}
                      onChange={(e) => setEditModel({ ...editModel, revision: e.target.value })}
                    />
                  </label>
                  <label className="form-field">
                    <span>Status</span>
                    <select
                      value={editModel.status}
                      onChange={(e) => setEditModel({ ...editModel, status: e.target.value as RecipeModel['status'] })}
                      style={{
                        width: '100%',
                        height: 35,
                        padding: '0 9px',
                        borderRadius: 3,
                        border: '1px solid #bcc8d4',
                        background: 'white',
                        fontSize: 11,
                        color: 'var(--navy-900)',
                      }}
                    >
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="DRAFT">DRAFT</option>
                      <option value="INACTIVE">INACTIVE</option>
                    </select>
                  </label>
                </div>
                <label className="form-field form-field--wide">
                  <span>Reference Image File</span>
                  <input
                    type="text"
                    value={editModel.referenceImage}
                    onChange={(e) => setEditModel({ ...editModel, referenceImage: e.target.value })}
                  />
                </label>
              </div>
              <div className="modal-footer">
                <button type="button" className="button button--ghost" onClick={() => setEditModel(null)}>
                  Cancel
                </button>
                <button type="submit" className="button button--primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD MODEL MODAL */}
      {isAddOpen && (
        <div className="modal-backdrop" onClick={() => setIsAddOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <form onSubmit={handleCreateModel}>
              <div className="modal-header">
                <h3>
                  <Plus size={20} color="var(--blue-600)" />
                  <span>Add New Inspection Model Recipe</span>
                </h3>
                <button type="button" className="icon-button" onClick={() => setIsAddOpen(false)} aria-label="Close modal">
                  <X size={19} />
                </button>
              </div>
              <div className="modal-body">
                <label className="form-field form-field--wide">
                  <span>Model ID (e.g. HARNESS-MOD-002)</span>
                  <input
                    type="text"
                    required
                    placeholder="HARNESS-MOD-002"
                    value={newModel.id}
                    onChange={(e) => setNewModel({ ...newModel, id: e.target.value })}
                  />
                </label>
                <label className="form-field form-field--wide">
                  <span>Model Name</span>
                  <input
                    type="text"
                    required
                    placeholder="Powertrain Low Voltage Harness"
                    value={newModel.name}
                    onChange={(e) => setNewModel({ ...newModel, name: e.target.value })}
                  />
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <label className="form-field">
                    <span>Revision</span>
                    <input
                      type="text"
                      required
                      placeholder="V1.0"
                      value={newModel.revision}
                      onChange={(e) => setNewModel({ ...newModel, revision: e.target.value })}
                    />
                  </label>
                  <label className="form-field">
                    <span>Initial Status</span>
                    <select
                      value={newModel.status}
                      onChange={(e) => setNewModel({ ...newModel, status: e.target.value as RecipeModel['status'] })}
                      style={{
                        width: '100%',
                        height: 35,
                        padding: '0 9px',
                        borderRadius: 3,
                        border: '1px solid #bcc8d4',
                        background: 'white',
                        fontSize: 11,
                        color: 'var(--navy-900)',
                      }}
                    >
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="DRAFT">DRAFT</option>
                      <option value="INACTIVE">INACTIVE</option>
                    </select>
                  </label>
                </div>
                <label className="form-field form-field--wide">
                  <span>Reference Image File</span>
                  <input
                    type="text"
                    value={newModel.referenceImage}
                    onChange={(e) => setNewModel({ ...newModel, referenceImage: e.target.value })}
                  />
                </label>
              </div>
              <div className="modal-footer">
                <button type="button" className="button button--ghost" onClick={() => setIsAddOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="button button--primary">
                  Create Recipe
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* OPERATOR TOAST NOTIFICATION */}
      {toast && (
        <div className="toast-container">
          <div className={`toast-pill ${toast.type === 'info' ? 'toast-pill--info' : 'toast-pill--success'}`}>
            {toast.type === 'info' ? <Info size={16} /> : <CheckCircle2 size={16} />}
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </>
  )
}

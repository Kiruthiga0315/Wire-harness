import {
  CheckCircle2,
  Crosshair,
  Download,
  FileText,
  Info,
  Plus,
  RefreshCw,
  RotateCcw,
  Ruler,
  SlidersHorizontal,
  Trash2,
  TriangleAlert,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import {
  API_BASE_URL,
  GOLDEN_HARNESS_URL,
  addGoldenCheckpoint,
  clearGoldenCheckpoints,
  deleteGoldenCheckpoint,
  getGoldenReference,
  resetGoldenReference,
  syncGoldenWithActiveImage,
  updateGoldenCalibration,
  updateGoldenCheckpoint,
} from '../services/api'
import type { GoldenCalibration, GoldenCheckpoint, GoldenReferenceConfig } from '../types/goldenReference'

export function GoldenReferencePage() {
  const { image: activeImage } = useInspection()
  const [config, setConfig] = useState<GoldenReferenceConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [syncingActive, setSyncingActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [imageTimestamp, setImageTimestamp] = useState(Date.now())

  // Active view: 'harness' | 'calibration'
  const [activeTab, setActiveTab] = useState<'harness' | 'calibration'>('harness')

  // Selected checkpoint for editing
  const [selectedId, setSelectedId] = useState<string | null>('CP-T01')
  const [isCreatingNew, setIsCreatingNew] = useState(false)
  const [isRepositioningExisting, setIsRepositioningExisting] = useState(false)
  const [filterCategory, setFilterCategory] = useState<'all' | 'terminal' | 'node_distance' | 'unconfirmed'>('all')
  const [searchTerm, setSearchTerm] = useState('')

  // Calibration state
  const [calibStart, setCalibStart] = useState<{ x: number; y: number } | null>(null)
  const [calibEnd, setCalibEnd] = useState<{ x: number; y: number } | null>(null)
  const [knownMm, setKnownMm] = useState<number>(500)

  // Checkpoint edit draft
  const [draft, setDraft] = useState<GoldenCheckpoint | null>(null)
  const imageContainerRef = useRef<HTMLDivElement>(null)

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getGoldenReference()
      setConfig(data)
      if (data.checkpoints.length > 0 && !selectedId) {
        setSelectedId(data.checkpoints[0].checkpoint_id)
        setDraft(data.checkpoints[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load golden reference.')
    } finally {
      setLoading(false)
    }
  }, [selectedId])

  useEffect(() => {
    void fetchConfig()
  }, [fetchConfig])

  const selectedCheckpoint = useMemo(() => {
    if (!config || !selectedId) return null
    return config.checkpoints.find((c) => c.checkpoint_id === selectedId) || null
  }, [config, selectedId])

  useEffect(() => {
    if (selectedCheckpoint) {
      setDraft({ ...selectedCheckpoint })
    }
  }, [selectedCheckpoint])

  const filteredCheckpoints = useMemo(() => {
    if (!config) return []
    return config.checkpoints.filter((cp) => {
      if (filterCategory === 'terminal' && cp.type !== 'terminal') return false
      if (filterCategory === 'node_distance' && cp.type !== 'node_distance') return false
      if (filterCategory === 'unconfirmed' && cp.status !== 'NEEDS_CONFIRMATION') return false
      if (searchTerm) {
        const term = searchTerm.toLowerCase()
        const matchId = cp.checkpoint_id.toLowerCase().includes(term)
        const matchTid = cp.terminal_id?.toLowerCase().includes(term)
        const matchNid = cp.node_id?.toLowerCase().includes(term)
        const matchNotes = cp.notes?.toLowerCase().includes(term)
        if (!matchId && !matchTid && !matchNid && !matchNotes) return false
      }
      return true
    })
  }, [config, filterCategory, searchTerm])

  const isDuplicateId = useMemo(() => {
    if (!isCreatingNew || !config || !draft?.checkpoint_id) return false
    const trimmed = draft.checkpoint_id.trim().toUpperCase()
    return config.checkpoints.some((c) => c.checkpoint_id.toUpperCase() === trimmed)
  }, [isCreatingNew, config, draft?.checkpoint_id])

  const handleSaveDraft = async () => {
    if (!draft || !config) return
    const cid = draft.checkpoint_id.trim()
    if (!cid) {
      setError('Please provide a Checkpoint ID.')
      return
    }

    const existingCp = config.checkpoints.find(
      (c) => c.checkpoint_id.toUpperCase() === cid.toUpperCase()
    )

    if (isCreatingNew && existingCp) {
      setError(`Checkpoint ID '${cid}' already exists. Choose a unique ID or update the existing checkpoint.`)
      return
    }

    setSaving(true)
    setError(null)
    try {
      if (isCreatingNew || !existingCp) {
        // Save as a brand new checkpoint!
        const payload: GoldenCheckpoint = {
          ...draft,
          checkpoint_id: cid,
          status: draft.status || 'CONFIRMED',
        }
        const added = await addGoldenCheckpoint(payload)
        setConfig((prev) => (prev ? { ...prev, checkpoints: [...prev.checkpoints, added] } : null))
        setSelectedId(added.checkpoint_id)
        setDraft({ ...added })
        setIsCreatingNew(false)
        setIsRepositioningExisting(false)
        setSuccessMessage(`Created new checkpoint ${added.checkpoint_id}`)
      } else {
        // Update existing checkpoint
        const updated = await updateGoldenCheckpoint(existingCp.checkpoint_id, draft)
        setConfig((prev) => {
          if (!prev) return null
          return {
            ...prev,
            checkpoints: prev.checkpoints.map((c) => (c.checkpoint_id === updated.checkpoint_id ? updated : c)),
          }
        })
        setDraft({ ...updated })
        setIsRepositioningExisting(false)
        setSuccessMessage(`Saved checkpoint ${updated.checkpoint_id}`)
      }
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error saving checkpoint.')
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmStatus = async (cp: GoldenCheckpoint) => {
    setSaving(true)
    setError(null)
    try {
      const updated = await updateGoldenCheckpoint(cp.checkpoint_id, { status: 'CONFIRMED' })
      setConfig((prev) => {
        if (!prev) return null
        return {
          ...prev,
          checkpoints: prev.checkpoints.map((c) => (c.checkpoint_id === updated.checkpoint_id ? updated : c)),
        }
      })
      if (draft?.checkpoint_id === cp.checkpoint_id) {
        setDraft((d) => (d ? { ...d, status: 'CONFIRMED' } : null))
      }
      setSuccessMessage(`Approved specification for ${cp.checkpoint_id}`)
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error confirming checkpoint.')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCheckpoint = async (id: string) => {
    if (!window.confirm(`Are you sure you want to delete checkpoint ${id}?`)) return
    setSaving(true)
    try {
      await deleteGoldenCheckpoint(id)
      setConfig((prev) => {
        if (!prev) return null
        return {
          ...prev,
          checkpoints: prev.checkpoints.filter((c) => c.checkpoint_id !== id),
        }
      })
      setSelectedId(null)
      setDraft(null)
      setIsCreatingNew(false)
      setSuccessMessage(`Deleted checkpoint ${id}`)
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete.')
    } finally {
      setSaving(false)
    }
  }

  const handleSyncWithActiveImage = async () => {
    setSyncingActive(true)
    setError(null)
    try {
      const updated = await syncGoldenWithActiveImage()
      setConfig(updated)
      setImageTimestamp(Date.now())
      setSuccessMessage(
        `Successfully synchronized Golden Reference with active workpiece (${updated.image_width} × ${updated.image_height} px, ${updated.checkpoints.length} checkpoints).`
      )
      setTimeout(() => setSuccessMessage(null), 6000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync with active workpiece.')
    } finally {
      setSyncingActive(false)
    }
  }

  const handleClearAllCheckpoints = async () => {
    if (!window.confirm('Are you sure you want to remove ALL checkpoints so you can place them manually?')) return
    setLoading(true)
    setError(null)
    try {
      const updated = await clearGoldenCheckpoints()
      setConfig(updated)
      setSelectedId(null)
      setDraft(null)
      setIsCreatingNew(false)
      setIsRepositioningExisting(false)
      setSuccessMessage('All checkpoints removed. Click anywhere on the workpiece or use "+ Add Checkpoint" to place checkpoints manually.')
      setTimeout(() => setSuccessMessage(null), 6000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear checkpoints.')
    } finally {
      setLoading(false)
    }
  }

  const handleResetBaseline = async () => {
    if (!window.confirm('Reset Golden Reference to baseline specifications and coordinates?')) return
    setLoading(true)
    try {
      const def = await resetGoldenReference()
      setConfig(def)
      setImageTimestamp(Date.now())
      setSuccessMessage('Reset golden reference to baseline.')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleStartAddNew = (initialX?: number, initialY?: number) => {
    if (!config) return
    setIsCreatingNew(true)
    setSelectedId(null)
    setIsRepositioningExisting(false)
    const existingIds = new Set(config.checkpoints.map((c) => c.checkpoint_id.toUpperCase()))
    let nextNum = 1
    while (existingIds.has(`CP-T${String(nextNum).padStart(2, '0')}`) || existingIds.has(`CP-T${nextNum}`)) {
      nextNum++
    }
    const termId = `T${String(nextNum).padStart(2, '0')}`
    const defaultX = initialX ?? Math.round(config.image_width / 2)
    const defaultY = initialY ?? Math.round(config.image_height / 2)
    setDraft({
      checkpoint_id: `CP-${termId}`,
      type: 'terminal',
      terminal_id: termId,
      node_id: 'J01',
      branch_id: null,
      measurement_type: 'branch_length',
      expected_value: 150.0,
      unit: 'mm',
      tolerance: 15.0,
      reference_x: defaultX,
      reference_y: defaultY,
      roi_width: 45,
      roi_height: 45,
      confidence: 0.95,
      status: 'CONFIRMED',
      notes: 'Manually placed checkpoint',
    })
  }

  const handleCancelNew = () => {
    setIsCreatingNew(false)
    if (config && config.checkpoints.length > 0) {
      setSelectedId(config.checkpoints[0].checkpoint_id)
      setDraft({ ...config.checkpoints[0] })
    } else {
      setSelectedId(null)
      setDraft(null)
      setIsCreatingNew(false)
    }
  }

  const handleImageClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!config || (activeTab !== 'harness' && activeTab !== 'calibration')) return
    const rect = e.currentTarget.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const clickY = e.clientY - rect.top
    const scaleX = config.image_width / rect.width
    const scaleY = config.image_height / rect.height
    const imgX = Math.round(clickX * scaleX)
    const imgY = Math.round(clickY * scaleY)

    if (activeTab === 'calibration') {
      if (!calibStart) {
        setCalibStart({ x: imgX, y: imgY })
      } else if (!calibEnd) {
        setCalibEnd({ x: imgX, y: imgY })
      }
      return
    }

    // If explicitly moving the currently selected checkpoint
    if (isRepositioningExisting && draft) {
      setDraft({
        ...draft,
        reference_x: imgX,
        reference_y: imgY,
      })
      setIsRepositioningExisting(false)
      return
    }

    // If currently creating a new checkpoint, move the marker to the clicked position
    if (isCreatingNew && draft) {
      setDraft({
        ...draft,
        reference_x: imgX,
        reference_y: imgY,
      })
      return
    }

    // Otherwise, clicking on the canvas starts adding a NEW checkpoint at that location!
    // This leaves existing checkpoints (like T01) completely in place!
    handleStartAddNew(imgX, imgY)
  }

  const handleSaveCalibration = async () => {
    if (!calibStart || !calibEnd || knownMm <= 0) return
    const dx = calibEnd.x - calibStart.x
    const dy = calibEnd.y - calibStart.y
    const pixelDist = Math.round(Math.sqrt(dx * dx + dy * dy))
    const ppm = pixelDist / knownMm

    const newCalib: GoldenCalibration = {
      calibrated: true,
      method: 'manual_two_point',
      known_distance_mm: knownMm,
      pixel_distance: pixelDist,
      pixels_per_mm: Math.round(ppm * 10000) / 10000,
      endpoint1: calibStart,
      endpoint2: calibEnd,
      unit: 'mm',
    }
    try {
      await updateGoldenCalibration(newCalib)
      setConfig((prev) => (prev ? { ...prev, calibration: newCalib } : null))
      setSuccessMessage(`Calibration saved: ${newCalib.pixels_per_mm.toFixed(4)} px/mm`)
      setTimeout(() => setSuccessMessage(null), 3000)
      setActiveTab('harness')
      setCalibStart(null)
      setCalibEnd(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save calibration')
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="ENGINEERING GROUND TRUTH"
        title="Golden Reference & Checkpoints"
        description={`Reference harness ground truth (${config?.image_width ?? 1800} × ${config?.image_height ?? 560} px) with ${config?.checkpoints.length ?? 34} specification checkpoints.`}
        actions={
          <div className="button-group">
            <button
              className="button button--primary"
              onClick={handleSyncWithActiveImage}
              disabled={loading || saving || syncingActive}
              title="Synchronize Golden Reference to the current active uploaded workpiece image"
            >
              <RefreshCw size={16} className={syncingActive ? 'spin' : ''} />
              Sync Active Image
            </button>
            <a
              href={`${API_BASE_URL}/api/golden-reference/export/csv`}
              download="golden_measurements.csv"
              className="button button--secondary"
              title="Export complete checkpoint specifications as CSV"
            >
              <FileText size={16} />
              Export CSV
            </a>
            <a
              href={`${API_BASE_URL}/api/golden-reference/export/json`}
              download="golden_measurements.json"
              className="button button--secondary"
              title="Export complete configuration as JSON"
            >
              <FileText size={16} />
              Export JSON
            </a>
            <button
              className="button button--secondary"
              onClick={handleClearAllCheckpoints}
              disabled={loading || saving}
              title="Remove all checkpoints so you can add them manually"
              style={{ color: '#ef4444', borderColor: '#fca5a5' }}
            >
              <Trash2 size={16} />
              Clear Checkpoints
            </button>
            <button
              className="button button--secondary"
              onClick={handleResetBaseline}
              disabled={loading || saving || syncingActive}
              title="Reset golden reference to initial ground-truth baseline"
            >
              <RotateCcw size={16} />
              Reset Reference
            </button>
          </div>
        }
      />

      {activeImage && config && (config.image_width !== activeImage.width || config.image_height !== activeImage.height) && (
        <div
          className="alert-banner"
          style={{ background: 'var(--blue-50, #eff6ff)', color: 'var(--blue-700, #1d4ed8)', border: '1px solid #bfdbfe', marginBottom: 16 }}
        >
          <Info size={20} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <strong>Active Workpiece Detected: {activeImage.name} ({activeImage.width} × {activeImage.height} px)</strong>
              <div>Golden Reference is currently displaying baseline data ({config.image_width} × {config.image_height} px). Click "Sync Active Image" to synchronize.</div>
            </div>
            <button
              className="button button--primary"
              style={{ whiteSpace: 'nowrap', padding: '6px 14px', fontSize: 12 }}
              onClick={handleSyncWithActiveImage}
              disabled={syncingActive}
            >
              <RefreshCw size={14} className={syncingActive ? 'spin' : ''} />
              Sync Active Image
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="alert-banner" role="alert">
          <TriangleAlert size={20} />
          <div>
            <strong>Error</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {successMessage && (
        <div
          className="alert-banner"
          style={{ background: 'var(--green-100)', color: 'var(--green-600)', border: '1px solid #c2ecd5' }}
        >
          <CheckCircle2 size={20} />
          <div>
            <strong>Success</strong>
            <span>{successMessage}</span>
          </div>
        </div>
      )}

      {/* Summary Metrics Bar */}
      <section className="engineering-metrics" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        <article>
          <span>Total Checkpoints</span>
          <strong>{config?.checkpoints.length ?? 0}</strong>
          <small>Marked features</small>
        </article>
        <article>
          <span>Terminals</span>
          <strong>{config?.specification_summary.total_terminals ?? 41}</strong>
          <small>T01 - T41 connectors</small>
        </article>
        <article>
          <span>Spine Nodes</span>
          <strong>{config?.specification_summary.total_nodes ?? 12}</strong>
          <small>N01 - N12 junctions</small>
        </article>
        <article>
          <span>Confirmed Specs</span>
          <strong style={{ color: 'var(--green-600)' }}>
            {config?.specification_summary.confirmed_count ?? 50}
          </strong>
          <small>Approved measurements</small>
        </article>
        <article>
          <span>Need Confirmation</span>
          <strong style={{ color: config?.specification_summary.unconfirmed_count ? 'var(--amber-600)' : 'inherit' }}>
            {config?.specification_summary.unconfirmed_count ?? 4}
          </strong>
          <small>Pending review</small>
        </article>
        <article>
          <span>Calibration Scale</span>
          <strong>{config?.calibration ? `${config.calibration.pixels_per_mm.toFixed(3)}` : '0.916'}</strong>
          <small>pixels / mm</small>
        </article>
      </section>

      {/* Main Workspace Layout */}
      <div className="checkpoint-editor-layout" style={{ gridTemplateColumns: 'minmax(0, 1fr) 420px', gap: 20, alignItems: 'start' }}>
        {/* Left Column: Visual Stage */}
        <article className="panel checkpoint-canvas-panel">
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                className={`button ${activeTab === 'harness' ? 'button--primary' : 'button--secondary'}`}
                style={{ padding: '6px 12px', fontSize: 11 }}
                onClick={() => setActiveTab('harness')}
              >
                <FileText size={14} /> Golden Harness (Annotated)
              </button>
              <button
                className={`button ${activeTab === 'calibration' ? 'button--primary' : 'button--secondary'}`}
                style={{ padding: '6px 12px', fontSize: 11 }}
                onClick={() => {
                  setActiveTab('calibration')
                  setCalibStart(null)
                  setCalibEnd(null)
                }}
              >
                <Ruler size={14} /> Calibrate (mm)
              </button>
            </div>
            <div className="checkpoint-legend">
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <i style={{ width: 10, height: 10, borderRadius: '50%', background: '#dc2626' }} /> Joints & Nodes (Red)
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <i style={{ width: 10, height: 10, borderRadius: '50%', background: '#16a34a' }} /> Terminals (Green)
              </span>
            </div>
          </div>

          {activeTab === 'harness' && (
            <div
              className="checkpoint-canvas-stage"
              style={{
                width: '100%',
                padding: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#101922',
                overflow: 'hidden',
                position: 'relative',
                borderRadius: 6,
              }}
            >
              <div
                ref={imageContainerRef}
                style={{
                  position: 'relative',
                  width: '100%',
                  aspectRatio: `${config?.image_width ?? 1800} / ${config?.image_height ?? 560}`,
                  cursor: draft || isCreatingNew || isRepositioningExisting ? 'crosshair' : 'default',
                  userSelect: 'none',
                }}
                onClick={handleImageClick}
              >
                <img
                  src={`${GOLDEN_HARNESS_URL}?v=${imageTimestamp}`}
                  alt="Golden reference wire harness layout"
                  style={{ width: '100%', height: '100%', display: 'block', objectFit: 'fill', pointerEvents: 'none' }}
                />

                {filteredCheckpoints.length === 0 && (
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(15, 23, 42, 0.45)',
                      color: '#f8fafc',
                      pointerEvents: 'none',
                      borderRadius: 4,
                      zIndex: 2,
                    }}
                  >
                    <Crosshair size={32} style={{ marginBottom: 8, opacity: 0.85 }} />
                    <strong style={{ fontSize: 14 }}>Click anywhere on the harness to place a checkpoint</strong>
                    <span style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                      Set Checkpoint ID, Terminal/Node ID, Expected Length (mm), and Tolerance in the inspector
                    </span>
                  </div>
                )}

                {/* Overlaid Checkpoint Markers: Joints=RED, Terminals=GREEN */}
                {filteredCheckpoints.map((cp) => {
                  const isSelected = selectedId === cp.checkpoint_id
                  const isJoint =
                    cp.type === 'node_distance' ||
                    cp.type === 'junction' ||
                    Boolean(cp.node_id && !cp.terminal_id) ||
                    cp.checkpoint_id.startsWith('CP-NODE') ||
                    cp.checkpoint_id.includes('J')
                  const color = isJoint ? '#dc2626' : '#16a34a'
                  const badgeBg = isSelected
                    ? isJoint
                      ? '#991b1b'
                      : '#14532d'
                    : isJoint
                      ? 'rgba(185, 28, 28, 0.92)'
                      : 'rgba(21, 128, 61, 0.92)'
                  const posX = isSelected && isRepositioningExisting && draft ? draft.reference_x : cp.reference_x
                  const posY = isSelected && isRepositioningExisting && draft ? draft.reference_y : cp.reference_y
                  const leftPct = (posX / (config?.image_width ?? 1800)) * 100
                  const topPct = (posY / (config?.image_height ?? 560)) * 100
                  const label = cp.terminal_id || cp.node_id || cp.checkpoint_id

                  return (
                    <div
                      key={cp.checkpoint_id}
                      onClick={(e) => {
                        e.stopPropagation()
                        setIsCreatingNew(false)
                        setIsRepositioningExisting(false)
                        setSelectedId(cp.checkpoint_id)
                        setDraft({ ...cp })
                      }}
                      style={{
                        position: 'absolute',
                        left: `${leftPct}%`,
                        top: `${topPct}%`,
                        transform: 'translate(-50%, -50%)',
                        cursor: 'pointer',
                        zIndex: isSelected ? 30 : 10,
                      }}
                    >
                      <div
                        style={{
                          width: isSelected ? 16 : 12,
                          height: isSelected ? 16 : 12,
                          borderRadius: '50%',
                          background: color,
                          border: isSelected ? '2px solid #ffffff' : '2px solid #ffffff',
                          boxShadow: isSelected
                            ? `0 0 0 3px ${isJoint ? '#fca5a5' : '#86efac'}`
                            : '0 1px 4px rgba(0,0,0,0.6)',
                        }}
                      />
                      <span
                        style={{
                          position: 'absolute',
                          left: 14,
                          top: -7,
                          background: badgeBg,
                          color: '#ffffff',
                          fontSize: 9,
                          fontWeight: 700,
                          padding: '1px 5px',
                          borderRadius: 3,
                          whiteSpace: 'nowrap',
                          pointerEvents: 'none',
                          border: `1px solid ${color}`,
                        }}
                      >
                        {label}
                      </span>
                    </div>
                  )
                })}

                {/* Live Preview for New Checkpoint being placed */}
                {isCreatingNew && draft && (
                  <div
                    style={{
                      position: 'absolute',
                      left: `${(draft.reference_x / (config?.image_width ?? 1800)) * 100}%`,
                      top: `${(draft.reference_y / (config?.image_height ?? 560)) * 100}%`,
                      transform: 'translate(-50%, -50%)',
                      zIndex: 40,
                      pointerEvents: 'none',
                    }}
                  >
                    <div
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: '50%',
                        background: draft.type === 'node_distance' ? '#ef4444' : '#22c55e',
                        border: '3px solid #ffffff',
                        boxShadow: '0 0 0 4px #0284c7, 0 2px 8px rgba(0,0,0,0.8)',
                      }}
                    />
                    <span
                      style={{
                        position: 'absolute',
                        left: 16,
                        top: -8,
                        background: '#0284c7',
                        color: '#ffffff',
                        fontSize: 10,
                        fontWeight: 800,
                        padding: '2px 6px',
                        borderRadius: 4,
                        whiteSpace: 'nowrap',
                        border: '1px solid #ffffff',
                        boxShadow: '0 2px 6px rgba(0,0,0,0.6)',
                      }}
                    >
                      + NEW: {draft.terminal_id || draft.node_id || draft.checkpoint_id}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'calibration' && (
            <div style={{ padding: 24, background: '#f8fafc', height: 720, overflowY: 'auto' }}>
              <div style={{ maxWidth: 600, margin: '0 auto', background: '#ffffff', padding: 24, borderRadius: 8, border: '1px solid var(--slate-200)' }}>
                <h3 style={{ margin: '0 0 10px', fontSize: 18, color: 'var(--navy-900)' }}>Pixel-to-Millimetre Calibration</h3>
                <p style={{ fontSize: 12, color: 'var(--slate-500)', lineHeight: 1.5, marginBottom: 18 }}>
                  The reference image contains a yellow measuring tape along the top edge (from x=0 to x=458 px).
                  500 mm corresponds to 458 pixels, yielding <strong>0.9160 px/mm</strong> (or 1 mm ≈ 0.92 pixels).
                </p>

                <div style={{ display: 'grid', gap: 14, marginBottom: 20 }}>
                  <label className="form-field">
                    <span>Known Physical Distance (mm)</span>
                    <input
                      type="number"
                      value={knownMm}
                      onChange={(e) => setKnownMm(Number(e.target.value))}
                      style={{ padding: '8px 12px', border: '1px solid var(--slate-300)', borderRadius: 4 }}
                    />
                  </label>

                  <div style={{ padding: 12, background: 'var(--blue-100)', borderRadius: 4, fontSize: 11, color: '#0369a1' }}>
                    <Info size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                    Default Tape Calibration: 500 mm across 458 px = <strong>0.9160 px/mm</strong>.
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    className="button button--primary"
                    onClick={() => {
                      setCalibStart({ x: 0, y: 15 })
                      setCalibEnd({ x: 458, y: 15 })
                      void handleSaveCalibration()
                    }}
                  >
                    Apply Yellow Tape Calibration (0.9160 px/mm)
                  </button>
                  <button className="button button--secondary" onClick={() => setActiveTab('harness')}>
                    Back to Harness
                  </button>
                </div>
              </div>
            </div>
          )}

          <footer className="checkpoint-canvas-footer" style={{ padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: 'var(--slate-500)' }}>
              Click any marker to inspect. Click canvas to reposition the selected marker, or click &quot;+ Add Checkpoint&quot; to place a new one.
            </span>
            <strong style={{ fontSize: 11, color: 'var(--slate-700)' }}>
              {config?.image_width} × {config?.image_height} px
            </strong>
          </footer>
        </article>

        {/* Right Column: Checkpoint Details & Table */}
        <aside className="panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="panel-header">
            <div>
              <p className="eyebrow">{isCreatingNew ? 'NEW CHECKPOINT PLACEMENT' : 'SPECIFICATION INSPECTOR'}</p>
              <h2>{draft ? draft.checkpoint_id : 'Select Checkpoint'}</h2>
            </div>
            {draft && !isCreatingNew && (
              <StatusPill tone={draft.status === 'CONFIRMED' ? 'pass' : 'warning'}>
                {draft.status === 'CONFIRMED' ? 'CONFIRMED' : 'NEEDS CONFIRMATION'}
              </StatusPill>
            )}
            {isCreatingNew && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: '3px 8px',
                  borderRadius: 4,
                  background: '#0284c7',
                  color: '#ffffff',
                }}
              >
                PLACING MARKER
              </span>
            )}
          </div>

          {draft ? (
            <div style={{ padding: 18, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {isCreatingNew && (
                <div style={{ padding: '8px 12px', background: '#e0f2fe', borderRadius: 4, border: '1px solid #bae6fd', fontSize: 11, color: '#0369a1', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Info size={14} style={{ flexShrink: 0 }} />
                  <span>Click on the harness image to reposition this marker ({draft.reference_x}, {draft.reference_y}).</span>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <label className="form-field">
                  <span>Checkpoint ID</span>
                  <input
                    type="text"
                    value={draft.checkpoint_id}
                    onChange={(e) => setDraft({ ...draft, checkpoint_id: e.target.value })}
                    style={isDuplicateId ? { borderColor: '#ef4444', background: '#fef2f2' } : {}}
                  />
                </label>
                <label className="form-field">
                  <span>Type</span>
                  <select
                    value={draft.type}
                    onChange={(e) => setDraft({ ...draft, type: e.target.value as any })}
                    style={{ padding: '6px 10px', fontSize: 11, border: '1px solid var(--slate-300)', borderRadius: 3 }}
                  >
                    <option value="terminal">Terminal</option>
                    <option value="node_distance">Joint / Node</option>
                  </select>
                </label>
              </div>

              {isDuplicateId && (
                <div style={{ padding: '8px 12px', background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 4, color: '#991b1b', fontSize: 11 }}>
                  <strong>⚠️ ID &quot;{draft.checkpoint_id}&quot; already exists!</strong>
                  <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="button button--secondary"
                      style={{ padding: '3px 8px', fontSize: 10, background: '#ffffff' }}
                      onClick={() => {
                        const existing = config?.checkpoints.find((c) => c.checkpoint_id.toUpperCase() === draft.checkpoint_id.trim().toUpperCase())
                        if (existing) {
                          setIsCreatingNew(false)
                          setSelectedId(existing.checkpoint_id)
                          setDraft({ ...existing, reference_x: draft.reference_x, reference_y: draft.reference_y })
                        }
                      }}
                    >
                      Update Existing {draft.checkpoint_id} Coordinates
                    </button>
                    <button
                      type="button"
                      className="button button--secondary"
                      style={{ padding: '3px 8px', fontSize: 10, background: '#ffffff' }}
                      onClick={() => {
                        const existingIds = new Set(config?.checkpoints.map((c) => c.checkpoint_id.toUpperCase()))
                        let nextNum = (config?.checkpoints.length ?? 0) + 1
                        while (existingIds.has(`CP-T${String(nextNum).padStart(2, '0')}`) || existingIds.has(`CP-T${nextNum}`)) {
                          nextNum++
                        }
                        const termId = `T${String(nextNum).padStart(2, '0')}`
                        setDraft({ ...draft, checkpoint_id: `CP-${termId}`, terminal_id: termId })
                      }}
                    >
                      Auto-Assign Unique ID
                    </button>
                  </div>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <label className="form-field">
                  <span>Terminal ID</span>
                  <input
                    type="text"
                    value={draft.terminal_id || ''}
                    placeholder="e.g. T43"
                    onChange={(e) => {
                      const raw = e.target.value.trim()
                      const val = raw || null
                      const term = val ? (val.toUpperCase().startsWith('T') ? val.toUpperCase() : `T${val}`) : null
                      setDraft({
                        ...draft,
                        terminal_id: val,
                        ...(term ? { checkpoint_id: `CP-${term}` } : {}),
                      })
                    }}
                  />
                </label>
                <label className="form-field">
                  <span>Node / Junction ID</span>
                  <input
                    type="text"
                    value={draft.node_id || ''}
                    onChange={(e) => setDraft({ ...draft, node_id: e.target.value || null })}
                  />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <label className="form-field">
                  <span>Expected Length (mm)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={draft.expected_value ?? ''}
                    onChange={(e) => setDraft({ ...draft, expected_value: Number(e.target.value) })}
                  />
                </label>
                <label className="form-field">
                  <span>Tolerance (± mm)</span>
                  <input
                    type="number"
                    step="0.5"
                    value={draft.tolerance ?? 15}
                    onChange={(e) => setDraft({ ...draft, tolerance: Number(e.target.value) })}
                  />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <label className="form-field">
                  <span>Pixel Coordinate X</span>
                  <input
                    type="number"
                    value={draft.reference_x}
                    onChange={(e) => setDraft({ ...draft, reference_x: Number(e.target.value) })}
                  />
                </label>
                <label className="form-field">
                  <span>Pixel Coordinate Y</span>
                  <input
                    type="number"
                    value={draft.reference_y}
                    onChange={(e) => setDraft({ ...draft, reference_y: Number(e.target.value) })}
                  />
                </label>
                {!isCreatingNew && (
                  <div style={{ gridColumn: 'span 2' }}>
                    <button
                      type="button"
                      className={`button ${isRepositioningExisting ? 'button--primary' : 'button--secondary'}`}
                      style={{ width: '100%', padding: '5px 10px', fontSize: 11, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                      onClick={() => setIsRepositioningExisting(!isRepositioningExisting)}
                    >
                      <Crosshair size={13} />
                      {isRepositioningExisting
                        ? `📍 Click canvas to place ${draft.checkpoint_id}`
                        : `Move Existing ${draft.checkpoint_id} Marker`}
                    </button>
                  </div>
                )}
              </div>

              <label className="form-field">
                <span>Engineering Notes</span>
                <textarea
                  rows={2}
                  value={draft.notes || ''}
                  onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                  style={{ width: '100%', padding: '6px 10px', fontSize: 11, border: '1px solid var(--slate-300)', borderRadius: 3 }}
                />
              </label>

              {draft.status === 'NEEDS_CONFIRMATION' && (
                <div style={{ padding: 12, background: 'var(--amber-100)', borderRadius: 4, border: '1px solid #fde68a' }}>
                  <strong style={{ display: 'block', fontSize: 11, color: '#92400e', marginBottom: 4 }}>
                    Engineering Confirmation Required
                  </strong>
                  <span style={{ fontSize: 10, color: '#b45309', display: 'block', marginBottom: 8 }}>
                    {draft.notes || 'This measurement was flagged for manual confirmation before driving PASS/FAIL decisions.'}
                  </span>
                  <button
                    className="button button--primary"
                    style={{ padding: '4px 10px', fontSize: 10 }}
                    onClick={() => handleConfirmStatus(draft)}
                  >
                    Confirm & Approve Specification
                  </button>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                {isCreatingNew ? (
                  <>
                    <button
                      className="button button--primary"
                      onClick={handleSaveDraft}
                      disabled={saving || isDuplicateId}
                      style={{ flex: 1, opacity: isDuplicateId ? 0.6 : 1, cursor: isDuplicateId ? 'not-allowed' : 'pointer' }}
                    >
                      + Add Checkpoint
                    </button>
                    <button className="button button--secondary" onClick={handleCancelNew} style={{ flex: 1 }}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <button className="button button--primary" onClick={handleSaveDraft} disabled={saving} style={{ flex: 1 }}>
                      Save Checkpoint
                    </button>
                    <button
                      className="button button--secondary"
                      style={{ color: 'var(--red-600)', display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px' }}
                      onClick={() => handleDeleteCheckpoint(draft.checkpoint_id)}
                      title="Delete checkpoint"
                    >
                      <Trash2 size={15} /> Delete Checkpoint
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--slate-500)', fontSize: 12 }}>
              Select a checkpoint marker on the image or from the table below to inspect.
            </div>
          )}

          {/* Quick Filter & Checkpoint List */}
          <div style={{ borderTop: '1px solid var(--slate-200)', flex: 1, display: 'flex', flexDirection: 'column', minHeight: 240 }}>
            <div style={{ padding: '8px 12px', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--slate-200)' }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--slate-700)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                All Checkpoints ({config?.checkpoints.length ?? 0})
              </span>
              <button
                className="button button--primary"
                style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => handleStartAddNew()}
              >
                <Plus size={13} /> Add Checkpoint
              </button>
            </div>
            <div style={{ padding: '8px 12px', background: '#f8fafc', display: 'flex', gap: 8, borderBottom: '1px solid var(--slate-200)' }}>
              <input
                type="text"
                placeholder="Filter ID (e.g. T01, N01)..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ flex: 1, padding: '4px 8px', fontSize: 11, border: '1px solid var(--slate-300)', borderRadius: 3 }}
              />
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value as any)}
                style={{ padding: '4px 8px', fontSize: 11, border: '1px solid var(--slate-300)', borderRadius: 3 }}
              >
                <option value="all">All ({config?.checkpoints.length ?? 0})</option>
                <option value="terminal">Terminals ({config?.checkpoints.filter((c) => c.type === 'terminal').length ?? 0})</option>
                <option value="node_distance">Nodes ({config?.checkpoints.filter((c) => c.type === 'node_distance').length ?? 0})</option>
                <option value="unconfirmed">Unconfirmed ({config?.specification_summary.unconfirmed_count ?? 0})</option>
              </select>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <tbody>
                  {filteredCheckpoints.map((cp) => {
                    const isSelected = selectedId === cp.checkpoint_id
                    return (
                      <tr
                        key={cp.checkpoint_id}
                        onClick={() => {
                          setIsCreatingNew(false)
                          setSelectedId(cp.checkpoint_id)
                          setDraft({ ...cp })
                        }}
                        style={{
                          cursor: 'pointer',
                          background: isSelected ? '#e0f2fe' : 'transparent',
                          borderBottom: '1px solid #f1f5f9',
                        }}
                      >
                        <td style={{ padding: '6px 12px', fontWeight: 600 }}>
                          <span
                            style={{
                              display: 'inline-block',
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              background:
                                cp.type === 'node_distance' ||
                                cp.type === 'junction' ||
                                Boolean(cp.node_id && !cp.terminal_id) ||
                                cp.checkpoint_id.startsWith('CP-NODE') ||
                                cp.checkpoint_id.includes('J')
                                  ? '#dc2626'
                                  : '#16a34a',
                              marginRight: 6,
                            }}
                          />
                          {cp.terminal_id || cp.node_id || cp.checkpoint_id}
                        </td>
                        <td style={{ padding: '6px 8px', color: 'var(--slate-600)' }}>{cp.expected_value} mm</td>
                        <td style={{ padding: '6px 8px', color: 'var(--slate-500)' }}>±{cp.tolerance} mm</td>
                        <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 700,
                              padding: '2px 6px',
                              borderRadius: 3,
                              color: cp.status === 'CONFIRMED' ? '#166534' : '#92400e',
                              background: cp.status === 'CONFIRMED' ? '#dcfce7' : '#fef3c7',
                            }}
                          >
                            {cp.status === 'CONFIRMED' ? 'OK' : 'CONFIRM'}
                          </span>
                        </td>
                        <td style={{ padding: '6px 8px', textAlign: 'center', width: 28 }}>
                          <button
                            type="button"
                            title={`Delete ${cp.checkpoint_id}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteCheckpoint(cp.checkpoint_id)
                            }}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--slate-400)',
                              cursor: 'pointer',
                              padding: 2,
                              borderRadius: 3,
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.color = '#dc2626')}
                            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--slate-400)')}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </aside>
      </div>
    </>
  )
}

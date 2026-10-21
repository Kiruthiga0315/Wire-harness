import { Copy, Eye, Pencil, Plus } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'

export function ModelsPage() {
  return (
    <>
      <PageHeader eyebrow="CONFIGURATION" title="Models / Recipes" description="Manage product-specific inspection recipes, revisions, and reference standards." actions={<button className="button button--primary" disabled><Plus size={18} />Add model</button>} />
      <article className="panel placeholder-table-panel">
        <div className="panel-header"><div><p className="eyebrow">PRODUCT LIBRARY</p><h2>Configured models</h2></div><span className="mock-tag">DEMO RECIPE</span></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Model ID</th><th>Model name</th><th>Revision</th><th>Checkpoints</th><th>Reference</th><th>Created</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody><tr><td><strong>DEMO-HARNESS-001</strong></td><td>Client Wire Harness Sample</td><td>V1.0</td><td>12 demo checkpoints</td><td>harness_sample_01.jpeg</td><td>12 Aug 2026</td><td><StatusPill tone="pass">ACTIVE</StatusPill></td><td><div className="table-actions"><button aria-label="View model"><Eye size={17} /></button><button aria-label="Edit model" disabled><Pencil size={17} /></button><button aria-label="Clone model" disabled><Copy size={17} /></button></div></td></tr></tbody>
          </table>
        </div>
        <div className="empty-footer">The deterministic demo recipe contains 12 CP-* checkpoints. Engineering ENG-* checkpoints remain preserved separately.</div>
      </article>
    </>
  )
}

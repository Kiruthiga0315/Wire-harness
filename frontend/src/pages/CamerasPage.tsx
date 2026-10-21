import { Camera, CircleDot, Video } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'

const cameras = [
  { name: 'Camera 1 — Top View', status: 'CONNECTED', purpose: 'Overall geometry, routing, component presence, colour and calibrated measurement', icon: Camera },
  { name: 'Camera 2 — Angled View', status: 'DISCONNECTED', purpose: 'Connector seating, terminal orientation, lock features and raised components', icon: Video },
]

export function CamerasPage() {
  return (
    <>
      <PageHeader eyebrow="DEVICE MANAGEMENT" title="Camera Setup" description="Monitor logical acquisition devices and their assigned inspection duties." />
      <section className="camera-grid">
        {cameras.map(({ name, status, purpose, icon: Icon }) => <article className="panel camera-card" key={name}><div className="camera-card-top"><div className="camera-icon"><Icon size={29} /></div><StatusPill tone={status === 'CONNECTED' ? 'pass' : 'neutral'}>{status}</StatusPill></div><h2>{name}</h2><p>{purpose}</p><dl><div><dt>Camera type</dt><dd>Mock industrial GigE</dd></div><div><dt>Resolution</dt><dd>4096 × 3000</dd></div><div><dt>Trigger mode</dt><dd>Software</dd></div><div><dt>Calibration</dt><dd><CircleDot size={15} /> Development mock</dd></div></dl></article>)}
      </section>
    </>
  )
}

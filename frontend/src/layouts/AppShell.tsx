import {
  Activity,
  Boxes,
  Camera,
  ChartNoAxesCombined,
  ClipboardCheck,
  FileChartColumn,
  FlaskConical,
  Gauge,
  History,
  Menu,
  Ruler,
  ScanLine,
  Settings,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { StatusPill } from '../components/StatusPill'
import { useInspection } from '../context/InspectionContext'
import { useSystemHealth } from '../hooks/useSystemHealth'

const navigation = [
  { label: 'Dashboard', path: '/', icon: Gauge },
  { label: 'Live Inspection', path: '/live', icon: ScanLine },
  { label: 'Engineering View', path: '/engineering', icon: FlaskConical },
  { label: 'Models / Recipes', path: '/models', icon: Boxes },
  { label: 'Checkpoints', path: '/checkpoints', icon: ClipboardCheck },
  { label: 'Measurements', path: '/measurements', icon: Ruler },
  { label: 'Cameras', path: '/cameras', icon: Camera },
  { label: 'Calibration', path: '/calibration', icon: SlidersHorizontal },
  { label: 'Reports', path: '/reports', icon: FileChartColumn },
  { label: 'History', path: '/history', icon: History },
  { label: 'Settings', path: '/settings', icon: Settings },
]

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { image } = useInspection()
  const { health, loading, error } = useSystemHealth()
  const systemOnline = health?.status === 'healthy'

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? 'sidebar--open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><Activity size={25} /></div>
          <div><strong>HARNESS<span>VISION</span></strong><small>FINAL INSPECTION</small></div>
          <button className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation">
            <X size={20} />
          </button>
        </div>
        <div className="nav-label">OPERATIONS</div>
        <nav aria-label="Primary navigation">
          {navigation.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => isActive ? 'nav-item nav-item--active' : 'nav-item'}
            >
              <Icon size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        {image && (
          <div className="sidebar-footer" style={{ borderTop: '1px solid rgba(255,255,255,0.08)', marginBottom: 0 }}>
            <span className="sidebar-footer-label">ACTIVE TEST IMAGE</span>
            <div style={{ padding: '4px 0' }}>
              <strong style={{ display: 'block', fontSize: '0.82rem', color: '#ffffff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={image.name}>{image.name}</strong>
              <small style={{ color: image.source === 'upload' ? '#56b6ec' : '#35ca7a', fontWeight: 600 }}>{image.source === 'upload' ? 'LOCAL UPLOAD' : 'DEMO SAMPLE'} · SYNCED</small>
            </div>
          </div>
        )}
        <div className="sidebar-footer">
          <span className="sidebar-footer-label">SYSTEM CONNECTION</span>
          <div className="connection-state">
            <span className={`connection-dot ${systemOnline ? 'connection-dot--online' : ''}`} />
            <div>
              <strong>{loading ? 'CHECKING' : systemOnline ? 'ONLINE' : 'OFFLINE'}</strong>
              <small>{error ? 'Backend unavailable' : health ? `API v${health.version}` : 'Awaiting response'}</small>
            </div>
          </div>
        </div>
      </aside>

      {sidebarOpen && <button className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}

      <div className="main-area">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
            <Menu size={22} />
          </button>
          <div className="topbar-title">
            <ChartNoAxesCombined size={20} />
            <span>AI VISION SYSTEM — FINAL WIRE HARNESS INSPECTION</span>
          </div>
          <div className="topbar-status">
            <StatusPill tone={systemOnline ? 'pass' : loading ? 'warning' : 'ng'}>
              {loading ? 'CONNECTING' : systemOnline ? 'SYSTEM READY' : 'SYSTEM OFFLINE'}
            </StatusPill>
            <div className="operator"><span>OP</span><div><strong>Operator</strong><small>Development Mode</small></div></div>
          </div>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  )
}

import { Activity, CircleCheckBig, CircleX, Clock3, TriangleAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { MetricCard } from '../components/MetricCard'
import { PageHeader } from '../components/PageHeader'
import { StatusPill } from '../components/StatusPill'
import { useSystemHealth } from '../hooks/useSystemHealth'

const recentInspections = [
  { id: 'INS-240812-0142', model: 'MOD-12345-A', time: '14:32:08', result: 'PASS', cycle: '4.6 s' },
  { id: 'INS-240812-0141', model: 'MOD-12345-A', time: '14:29:51', result: 'NG', cycle: '5.1 s' },
  { id: 'INS-240812-0140', model: 'MOD-12345-A', time: '14:27:12', result: 'PASS', cycle: '4.7 s' },
  { id: 'INS-240812-0139', model: 'MOD-12345-A', time: '14:24:42', result: 'PASS', cycle: '4.5 s' },
]

export function DashboardPage() {
  const navigate = useNavigate()
  const { health, loading, error } = useSystemHealth()

  return (
    <>
      <PageHeader
        eyebrow="MANAGEMENT OVERVIEW"
        title="Production Dashboard"
        description="Live visibility across final inspection performance and system readiness."
        actions={<StatusPill tone={health?.status === 'healthy' ? 'pass' : loading ? 'warning' : 'ng'}>{loading ? 'CHECKING SERVICES' : error ? 'ACTION REQUIRED' : 'ALL SYSTEMS NOMINAL'}</StatusPill>}
      />

      {error && <div className="alert-banner"><TriangleAlert size={20} /><div><strong>Backend connection unavailable</strong><span>{error}</span></div></div>}

      <section className="metric-grid" aria-label="Daily inspection summary">
        <MetricCard icon={Activity} label="Inspections today" value="142" detail="18 in the last hour" />
        <MetricCard icon={CircleCheckBig} label="Pass today" value="136" detail="95.8% first pass yield" tone="green" />
        <MetricCard icon={CircleX} label="NG today" value="6" detail="4.2% defect rate" tone="red" />
        <MetricCard icon={Clock3} label="Average cycle" value="4.8 s" detail="Target ≤ 6.0 seconds" tone="amber" />
      </section>

      <section className="dashboard-grid">
        <article className="panel trend-panel">
          <div className="panel-header"><div><p className="eyebrow">SHIFT PERFORMANCE</p><h2>Inspection trend</h2></div><span className="mock-tag">MOCK DATA</span></div>
          <div className="chart-area" aria-label="Mock hourly inspection chart">
            {[58, 72, 66, 84, 76, 92, 87, 78, 95, 88, 83, 91].map((height, index) => (
              <div className="bar-group" key={index}>
                <div className="bar-stack"><span className="bar-pass" style={{ height: `${height}%` }} /><span className="bar-ng" style={{ height: `${Math.max(5, 100 - height) / 2}%` }} /></div>
                <small>{String(7 + index).padStart(2, '0')}:00</small>
              </div>
            ))}
          </div>
          <div className="chart-legend"><span><i className="legend-pass" />PASS</span><span><i className="legend-ng" />NG</span></div>
        </article>

        <article className="panel readiness-panel">
          <div className="panel-header"><div><p className="eyebrow">CELL READINESS</p><h2>System health</h2></div></div>
          <div className="readiness-list">
            <div><span>Backend API</span><StatusPill tone={health ? 'pass' : 'ng'}>{health ? 'ONLINE' : 'OFFLINE'}</StatusPill></div>
            <div><span>Inspection database</span><StatusPill tone={health?.database === 'connected' ? 'pass' : 'ng'}>{health?.database?.toUpperCase() ?? 'UNKNOWN'}</StatusPill></div>
            <div><span>AI processing engine</span><StatusPill tone="info">{health?.ai_mode?.toUpperCase() ?? 'MOCK'}</StatusPill></div>
            <div><span>Camera acquisition</span><StatusPill tone="info">{health?.camera_mode?.toUpperCase() ?? 'MOCK'}</StatusPill></div>
          </div>
          <div className="system-note"><TriangleAlert size={18} /><span>Phase 1 development environment. Camera and AI results are simulated.</span></div>
        </article>

        <article className="panel recent-panel">
          <div className="panel-header"><div><p className="eyebrow">LATEST ACTIVITY</p><h2>Recent inspections</h2></div><button className="text-button" onClick={() => navigate('/history')}>View history</button></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Inspection ID</th><th>Model</th><th>Time</th><th>Cycle</th><th>Result</th></tr></thead>
              <tbody>{recentInspections.map((item) => <tr key={item.id}><td><strong>{item.id}</strong></td><td>{item.model}</td><td>{item.time}</td><td>{item.cycle}</td><td><StatusPill tone={item.result === 'PASS' ? 'pass' : 'ng'}>{item.result}</StatusPill></td></tr>)}</tbody>
            </table>
          </div>
        </article>
      </section>
    </>
  )
}

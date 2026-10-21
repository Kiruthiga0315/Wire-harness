import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: string
  detail: string
  icon: LucideIcon
  tone?: 'blue' | 'green' | 'red' | 'amber'
}

export function MetricCard({ label, value, detail, icon: Icon, tone = 'blue' }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-icon"><Icon size={22} strokeWidth={2} /></div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <span>{detail}</span>
      </div>
    </article>
  )
}

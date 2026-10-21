import { Construction } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'

interface ComingSoonPageProps { title: string; description: string }

export function ComingSoonPage({ title, description }: ComingSoonPageProps) {
  return <><PageHeader eyebrow="PLANNED MODULE" title={title} description={description} /><article className="panel coming-soon"><Construction size={38} /><h2>Module placeholder</h2><p>This screen is intentionally reserved for the next implementation phase.</p></article></>
}

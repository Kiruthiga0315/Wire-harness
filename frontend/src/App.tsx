import { Route, Routes } from 'react-router-dom'
import { InspectionProvider } from './context/InspectionContext'
import { AppShell } from './layouts/AppShell'
import { CamerasPage } from './pages/CamerasPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { DashboardPage } from './pages/DashboardPage'
import { EngineeringViewPage } from './pages/EngineeringViewPage'
import { GoldenInspectionPage } from './pages/GoldenInspectionPage'
import { GoldenReferencePage } from './pages/GoldenReferencePage'
import { LiveInspectionPage } from './pages/LiveInspectionPage'
import { ModelsPage } from './pages/ModelsPage'
import { ReportsPage } from './pages/ReportsPage'

export default function App() {
  return (
    <InspectionProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="live" element={<LiveInspectionPage />} />
          <Route path="engineering" element={<EngineeringViewPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="cameras" element={<CamerasPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="checkpoints" element={<GoldenReferencePage />} />
          <Route path="golden" element={<GoldenReferencePage />} />
          <Route path="measurements" element={<GoldenInspectionPage />} />
          <Route path="calibration" element={<GoldenReferencePage />} />
          <Route path="history" element={<ComingSoonPage title="Inspection History" description="Search and revisit complete historical inspection evidence." />} />
          <Route path="settings" element={<ComingSoonPage title="System Settings" description="Configure local station preferences and future integrations." />} />
          <Route path="*" element={<ComingSoonPage title="Page Not Found" description="The requested inspection module does not exist." />} />
        </Route>
      </Routes>
    </InspectionProvider>
  )
}

import { Route, Routes } from 'react-router-dom'
import { AppShell } from './layouts/AppShell'
import { CamerasPage } from './pages/CamerasPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { DashboardPage } from './pages/DashboardPage'
import { EngineeringViewPage } from './pages/EngineeringViewPage'
import { LiveInspectionPage } from './pages/LiveInspectionPage'
import { ModelsPage } from './pages/ModelsPage'
import { ReportsPage } from './pages/ReportsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="live" element={<LiveInspectionPage />} />
        <Route path="engineering" element={<EngineeringViewPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="cameras" element={<CamerasPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="checkpoints" element={<ComingSoonPage title="Checkpoint Configuration" description="Define model-specific visual and dimensional inspection requirements." />} />
        <Route path="measurements" element={<ComingSoonPage title="Measurements" description="Review calibrated harness lengths, paths, angles, and deviations." />} />
        <Route path="calibration" element={<ComingSoonPage title="Camera Calibration" description="Manage board perspective, lens correction, fiducials, and pixel-to-mm scale." />} />
        <Route path="history" element={<ComingSoonPage title="Inspection History" description="Search and revisit complete historical inspection evidence." />} />
        <Route path="settings" element={<ComingSoonPage title="System Settings" description="Configure local station preferences and future integrations." />} />
        <Route path="*" element={<ComingSoonPage title="Page Not Found" description="The requested inspection module does not exist." />} />
      </Route>
    </Routes>
  )
}

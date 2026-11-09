import { Routes, Route } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import { Overview, Gallery, Workspace, AgentWorkspace, SourcePage, TestsPage, ReportsPage, GithubPage, SettingsPage } from './pages/Pages'
export default function App() {
  return <Routes><Route element={<AppLayout />}>
    <Route index element={<Overview />} /><Route path="gallery" element={<Gallery />} /><Route path="projects/:id" element={<Workspace />} /><Route path="agent" element={<AgentWorkspace />} />
    <Route path="source" element={<SourcePage />} /><Route path="tests" element={<TestsPage />} /><Route path="reports" element={<ReportsPage />} /><Route path="github" element={<GithubPage />} /><Route path="settings" element={<SettingsPage />} />
    <Route path="*" element={<div className="text-sm text-muted">Page not found.</div>} /></Route></Routes>
}

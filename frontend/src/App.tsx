import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth.store'
import AppLayout from '@/components/layout/AppLayout'
import { LoginPage } from '@/pages/Login'
import { DashboardPage } from '@/pages/Dashboard'
import { EngagementPage } from '@/pages/Engagement'
import { AuditProgramPage } from '@/pages/AuditProgram'
import { ExceptionsPage } from '@/pages/Exceptions'
import { SUAMPage } from '@/pages/SUAM'
import { RiskPage } from '@/pages/Risk'
import { RegulatoryPage } from '@/pages/Regulatory'
import { AnalyticsPage } from '@/pages/Analytics'
import { CreditPolicyPage } from '@/pages/CreditPolicy'
import { FinancialPage } from '@/pages/Financial'
import { ECLPage } from '@/pages/ECL'
import { EvidencePage } from '@/pages/Evidence'
import { CompletionPage } from '@/pages/Completion'
import { TeamPage } from '@/pages/Team'
import { ImportExportPage } from '@/pages/ImportExport'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="engagement" element={<EngagementPage />} />
        <Route path="audit-program" element={<AuditProgramPage />} />
        <Route path="exceptions" element={<ExceptionsPage />} />
        <Route path="suam" element={<SUAMPage />} />
        <Route path="risk" element={<RiskPage />} />
        <Route path="regulatory" element={<RegulatoryPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="credit-policy" element={<CreditPolicyPage />} />
        <Route path="financial" element={<FinancialPage />} />
        <Route path="ecl" element={<ECLPage />} />
        <Route path="evidence" element={<EvidencePage />} />
        <Route path="completion" element={<CompletionPage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="import-export" element={<ImportExportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

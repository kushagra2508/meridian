import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { Dashboard } from './routes/Dashboard'
import { Home } from './routes/Home'
import { Intelligence } from './routes/Intelligence'
import { Placeholder } from './routes/Placeholder'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />

      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/intelligence" element={<Intelligence />} />
        <Route
          path="/portfolio"
          element={
            <Placeholder
              icon="account_balance_wallet"
              title="Portfolio"
              description="Holdings, lot-level tax detail, and allocation drift will live here."
            />
          }
        />
        <Route
          path="/reports"
          element={
            <Placeholder
              icon="assessment"
              title="Reports"
              description="Scheduled statements and on-demand performance attribution will live here."
            />
          }
        />
        <Route
          path="/settings"
          element={
            <Placeholder
              icon="settings"
              title="Settings"
              description="Risk mandate, notification preferences, and linked institutions will live here."
            />
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

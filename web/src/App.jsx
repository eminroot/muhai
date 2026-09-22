import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout.jsx'
import ProtectedRoute from './components/auth/ProtectedRoute.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Invoices from './pages/Invoices.jsx'
import Tax from './pages/Tax.jsx'
import Inventory from './pages/Inventory.jsx'
import Payroll from './pages/Payroll.jsx'
import Assistant from './pages/Assistant.jsx'
import Settings from './pages/Settings.jsx'

import './styles/dock.css'
import './styles/components.css'
import './styles/layout.css'
import './styles/chat.css'
import './styles/landing.css'
import './styles/pages.css'
import './styles/auth.css'
import './styles/site-chat.css'
// Last, so the console skin wins over the component defaults it overrides.
// Scoped to `.app-shell`; the landing page and auth screens are unaffected.
import './styles/console.css'

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="invoices" element={<Invoices />} />
            <Route path="tax" element={<Tax />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="payroll" element={<Payroll />} />
            <Route path="assistant" element={<Assistant />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

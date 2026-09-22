import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { useLang } from '../../i18n/LanguageContext.jsx'
import CompanySetup from '../../pages/CompanySetup.jsx'

/**
 * Gate for /app.
 *
 * Three states, not two: signed out → /login; signed in but with no company
 * document → the setup screen (a registration that half-completed must not
 * strand the account); otherwise → the app.
 */
export default function ProtectedRoute() {
  const { user, profile, loading } = useAuth()
  const { t } = useLang()
  const location = useLocation()

  if (loading) {
    return (
      <div className="route-splash">
        <span className="route-splash__spinner" />
        <span>{t('common.loading')}</span>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  if (!profile?.companyId) return <CompanySetup />

  return <Outlet />
}

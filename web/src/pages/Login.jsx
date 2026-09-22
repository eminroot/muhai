import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Loader2, Lock, Mail } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { authErrorMessage, useAuth } from '../context/AuthContext.jsx'
import AuthShell from '../components/auth/AuthShell.jsx'
import GoogleButton from '../components/auth/GoogleButton.jsx'

export default function Login() {
  const { t, lang } = useLang()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const from = location.state?.from?.pathname || '/app'

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login({ email: email.trim(), password })
      navigate(from, { replace: true })
    } catch (err) {
      setError(authErrorMessage(err, lang))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title={t('auth.loginTitle')} subtitle={t('auth.loginSub')}>
      <GoogleButton onDone={() => navigate(from, { replace: true })} />

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span className="field__label">{t('auth.email')}</span>
          <span className="field__wrap">
            <Mail size={16} strokeWidth={1.9} />
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ornek@sirket.com"
            />
          </span>
        </label>

        <label className="field">
          <span className="field__label">{t('auth.password')}</span>
          <span className="field__wrap">
            <Lock size={16} strokeWidth={1.9} />
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </span>
        </label>

        {error && (
          <motion.div className="auth-alert auth-alert--error" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>
            {error}
          </motion.div>
        )}

        <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
          {busy ? <Loader2 size={16} className="spin" /> : null}
          {busy ? t('auth.loggingIn') : t('auth.login')}
          {!busy && <ArrowRight size={16} strokeWidth={1.9} />}
        </button>

      </form>

      <div className="auth-foot">
        {t('auth.noAccount')} <Link to="/register">{t('auth.createOne')}</Link>
      </div>
    </AuthShell>
  )
}

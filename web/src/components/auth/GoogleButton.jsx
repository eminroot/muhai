import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'
import { authErrorMessage, useAuth } from '../../context/AuthContext.jsx'
import { CANCELLED } from '../../lib/firebase.js'

/** Google's mark, in its own four colours — the one place brand colour
 *  other than the accent is allowed, because it is not ours to restyle. */
function GoogleMark() {
  return (
    <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

/**
 * "Continue with Google", above the email form on both auth screens.
 *
 * It does not navigate on success: the account may have no company yet — a
 * Google profile carries no tax id or legal form — and `ProtectedRoute`
 * already routes a company-less session to the setup screen. Letting the
 * router decide keeps one rule for where a new session lands.
 */
export default function GoogleButton({ onDone }) {
  const { t, lang } = useLang()
  const { loginWithGoogle } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setError(null)
    setBusy(true)
    try {
      const user = await loginWithGoogle()
      // null means the browser fell back to a redirect and is already
      // navigating away; leave the spinner up rather than flashing a state.
      if (user && onDone) onDone(user)
    } catch (err) {
      // Closing the popup is a decision, not a failure. Saying "something
      // went wrong" to someone who just changed their mind is noise.
      if (!CANCELLED.has(err?.code)) {
        setError(err?.code?.startsWith('auth/') ? t('auth.googleFailed') : authErrorMessage(err, lang))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {error && <div className="auth-alert auth-alert--error" role="alert">{error}</div>}

      <button type="button" className="btn btn--google btn--block" onClick={run} disabled={busy}>
        {busy ? <Loader2 size={16} className="spin" /> : <GoogleMark />}
        {busy ? t('auth.googleBusy') : t('auth.google')}
      </button>

      <div className="auth-or"><span>{t('auth.or')}</span></div>
    </>
  )
}

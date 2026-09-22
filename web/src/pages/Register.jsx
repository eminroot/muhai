import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Building2, Loader2, Lock, Mail, User } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { authErrorMessage, useAuth } from '../context/AuthContext.jsx'
import AuthShell from '../components/auth/AuthShell.jsx'
import GoogleButton from '../components/auth/GoogleButton.jsx'

const SECTORS = ['general', 'retail', 'manufacturing', 'services', 'logistics', 'food', 'tech', 'construction']
const LEGAL_FORMS = ['ltd', 'as', 'sahis', 'koop']

export default function Register() {
  const { t, lang } = useLang()
  const { register } = useAuth()
  const navigate = useNavigate()

  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    displayName: '',
    email: '',
    password: '',
    companyName: '',
    taxId: '',
    taxOffice: '',
    city: '',
    sector: 'general',
    legalForm: 'ltd',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  function goToStep2(e) {
    e.preventDefault()
    setError(null)
    if (!form.email.trim() || form.password.length < 6 || !form.displayName.trim()) {
      setError(t('auth.required'))
      return
    }
    setStep(2)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    if (!form.companyName.trim()) {
      setError(t('auth.required'))
      return
    }
    // VKN is optional, but if it is given it must be well-formed — a wrong one
    // silently breaks e-beyanname later, which is worse than rejecting it now.
    if (form.taxId && !/^\d{10}$/.test(form.taxId.trim())) {
      setError(t('auth.invalidTaxId'))
      return
    }

    setBusy(true)
    try {
      await register({
        email: form.email.trim(),
        password: form.password,
        displayName: form.displayName.trim(),
        company: {
          name: form.companyName.trim(),
          taxId: form.taxId.trim(),
          taxOffice: form.taxOffice.trim(),
          city: form.city.trim(),
          sector: form.sector,
          legalForm: form.legalForm,
        },
      })
      navigate('/app', { replace: true })
    } catch (err) {
      setError(authErrorMessage(err, lang))
      setStep(1)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title={t('auth.registerTitle')} subtitle={t('auth.registerSub')} wide>
      <div className="auth-steps">
        <span className={`auth-steps__item ${step === 1 ? 'is-active' : 'is-done'}`}>
          <b>1</b> {t('auth.step1')}
        </span>
        <span className="auth-steps__bar" />
        <span className={`auth-steps__item ${step === 2 ? 'is-active' : ''}`}>
          <b>2</b> {t('auth.step2')}
        </span>
      </div>

      {step === 1 ? (
        <>
        {/* Step one only. Past it an account is half-made, and Google would
            start a second one beside it. */}
        <GoogleButton onDone={() => navigate('/app', { replace: true })} />

        <form className="auth-form" onSubmit={goToStep2} noValidate>
          <label className="field">
            <span className="field__label">{t('auth.fullName')}</span>
            <span className="field__wrap">
              <User size={16} strokeWidth={1.9} />
              <input value={form.displayName} onChange={set('displayName')} autoComplete="name" required placeholder="Emin Baytar" />
            </span>
          </label>

          <label className="field">
            <span className="field__label">{t('auth.email')}</span>
            <span className="field__wrap">
              <Mail size={16} strokeWidth={1.9} />
              <input type="email" value={form.email} onChange={set('email')} autoComplete="email" required placeholder="ornek@sirket.com" />
            </span>
          </label>

          <label className="field">
            <span className="field__label">{t('auth.password')}</span>
            <span className="field__wrap">
              <Lock size={16} strokeWidth={1.9} />
              <input
                type="password"
                value={form.password}
                onChange={set('password')}
                autoComplete="new-password"
                required
                minLength={6}
                placeholder="••••••••"
              />
            </span>
            <span className="field__hint">{t('auth.passwordHint')}</span>
          </label>

          {error && (
            <motion.div className="auth-alert auth-alert--error" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>
              {error}
            </motion.div>
          )}

          <button className="btn btn--primary btn--block" type="submit">
            {t('auth.next')} <ArrowRight size={16} strokeWidth={1.9} />
          </button>
        </form>
        </>
      ) : (
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span className="field__label">{t('auth.companyName')}</span>
            <span className="field__wrap">
              <Building2 size={16} strokeWidth={1.9} />
              <input value={form.companyName} onChange={set('companyName')} required placeholder="Atlas Ticaret Ltd. Şti." />
            </span>
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field__label">{t('auth.taxId')}</span>
              <span className="field__wrap">
                <input value={form.taxId} onChange={set('taxId')} inputMode="numeric" maxLength={10} placeholder="4830027561" />
              </span>
            </label>
            <label className="field">
              <span className="field__label">{t('auth.taxOffice')}</span>
              <span className="field__wrap">
                <input value={form.taxOffice} onChange={set('taxOffice')} placeholder="Kadıköy" />
              </span>
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span className="field__label">{t('auth.city')}</span>
              <span className="field__wrap">
                <input value={form.city} onChange={set('city')} placeholder="İstanbul" />
              </span>
            </label>
            <label className="field">
              <span className="field__label">{t('auth.legalForm')}</span>
              <span className="field__wrap">
                <select value={form.legalForm} onChange={set('legalForm')}>
                  {LEGAL_FORMS.map((k) => (
                    <option key={k} value={k}>
                      {t(`auth.legalOptions.${k}`)}
                    </option>
                  ))}
                </select>
              </span>
            </label>
          </div>

          <label className="field">
            <span className="field__label">{t('auth.sector')}</span>
            <span className="field__wrap">
              <select value={form.sector} onChange={set('sector')}>
                {SECTORS.map((k) => (
                  <option key={k} value={k}>
                    {t(`auth.sectorOptions.${k}`)}
                  </option>
                ))}
              </select>
            </span>
          </label>

          {error && (
            <motion.div className="auth-alert auth-alert--error" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>
              {error}
            </motion.div>
          )}

          <div className="auth-actions">
            <button className="btn btn--ghost" type="button" onClick={() => setStep(1)} disabled={busy}>
              <ArrowLeft size={16} strokeWidth={1.9} /> {t('auth.back')}
            </button>
            <button className="btn btn--primary" type="submit" disabled={busy}>
              {busy && <Loader2 size={16} className="spin" />}
              {busy ? t('auth.registering') : t('auth.register')}
            </button>
          </div>
        </form>
      )}

      <div className="auth-foot">
        {t('auth.haveAccount')} <Link to="/login">{t('auth.signIn')}</Link>
      </div>
    </AuthShell>
  )
}

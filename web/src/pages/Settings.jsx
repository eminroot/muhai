import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Building2, Database, Loader2, Plug, Settings as SettingsIcon, Sparkles, Trash2, X } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useData } from '../context/DataContext.jsx'
import {
  COLLECTIONS,
  VENDOR_CATEGORIES,
  clearCollection,
  forgetVendorCategory,
  updateCompany,
} from '../lib/db.js'
import { apiBaseUrl, ping } from '../lib/api.js'
import PageSkeleton from '../components/ui/PageSkeleton.jsx'

const SECTORS = ['general', 'retail', 'manufacturing', 'services', 'logistics', 'food', 'tech', 'construction']
const LEGAL_FORMS = ['ltd', 'as', 'sahis', 'koop']

export default function Settings() {
  const { t } = useLang()
  const { company, companyId, refreshCompany } = useAuth()
  const {
    invoices, transactions, products, employees, taxObligations,
    vendorCategories, loading,
  } = useData()

  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [forgetting, setForgetting] = useState(null)
  const [flash, setFlash] = useState(null)
  const [apiUp, setApiUp] = useState(null)

  useEffect(() => {
    if (company && !form) {
      setForm({
        name: company.name || '',
        taxId: company.taxId || '',
        taxOffice: company.taxOffice || '',
        city: company.city || '',
        sector: company.sector || 'general',
        legalForm: company.legalForm || 'ltd',
      })
    }
  }, [company, form])

  useEffect(() => {
    ping().then(setApiUp)
  }, [])

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  function notify(message, tone = 'info') {
    setFlash({ message, tone })
    setTimeout(() => setFlash(null), 4000)
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await updateCompany(form)
      await refreshCompany()
      notify(t('settings.saved'))
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleClear() {
    if (!window.confirm(t('settings.clearConfirm'))) return
    setClearing(true)
    try {
      for (const name of Object.values(COLLECTIONS)) {
        await clearCollection(name)
      }
      await updateCompany({ seeded: false, cashBalance: 0 })
      await refreshCompany()
      notify(t('settings.cleared'))
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setClearing(false)
    }
  }

  async function handleForget(id) {
    setForgetting(id)
    try {
      await forgetVendorCategory(id)
      notify(t('settings.vendorForgotten'))
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setForgetting(null)
    }
  }

  async function handleForgetAll() {
    if (!window.confirm(t('settings.vendorForgetAllConfirm'))) return
    setForgetting('all')
    try {
      await clearCollection(VENDOR_CATEGORIES)
      notify(t('settings.vendorForgotten'))
    } catch (err) {
      notify(err.message, 'error')
    } finally {
      setForgetting(null)
    }
  }

  if (loading || !form) return <PageSkeleton rows={3} />

  const counts = [
    [t('nav.invoices'), invoices.length],
    ['İşlem / Transactions', transactions.length],
    [t('nav.inventory'), products.length],
    [t('nav.payroll'), employees.length],
    [t('nav.tax'), taxObligations.length],
  ]

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-eyebrow">
          <SettingsIcon size={14} strokeWidth={1.9} />
          <span className="label">{t('nav.settings')}</span>
        </div>
        <h1 className="page-title">{t('settings.title')}</h1>
        <p className="page-sub">{t('settings.subtitle')}</p>
      </div>

      {flash && (
        <motion.div
          className={`notice notice--${flash.tone === 'error' ? 'error' : 'info'}`}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ marginBottom: 18 }}
        >
          {flash.message}
        </motion.div>
      )}

      <div className="settings-grid">
        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><Building2 size={15} strokeWidth={1.9} />{t('settings.companySection')}</div>
              <div className="panel-sub">PostgreSQL · companies/{companyId?.slice(0, 8)}…</div>
            </div>
            <Building2 size={20} color="var(--ink-4)" />
          </div>

          <form onSubmit={handleSave} className="auth-form">
            <label className="field">
              <span className="field__label">{t('auth.companyName')}</span>
              <span className="field__wrap">
                <input value={form.name} onChange={set('name')} required />
              </span>
            </label>
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('auth.taxId')}</span>
                <span className="field__wrap">
                  <input value={form.taxId} onChange={set('taxId')} maxLength={10} inputMode="numeric" />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('auth.taxOffice')}</span>
                <span className="field__wrap">
                  <input value={form.taxOffice} onChange={set('taxOffice')} />
                </span>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('auth.city')}</span>
                <span className="field__wrap">
                  <input value={form.city} onChange={set('city')} />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('auth.legalForm')}</span>
                <span className="field__wrap">
                  <select value={form.legalForm} onChange={set('legalForm')}>
                    {LEGAL_FORMS.map((k) => (
                      <option key={k} value={k}>{t(`auth.legalOptions.${k}`)}</option>
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
                    <option key={k} value={k}>{t(`auth.sectorOptions.${k}`)}</option>
                  ))}
                </select>
              </span>
            </label>
            <button className="btn btn--primary" type="submit" disabled={saving} style={{ alignSelf: 'flex-start' }}>
              {saving && <Loader2 size={15} className="spin" />}
              {t('common.save')}
            </button>
          </form>
        </motion.section>

        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.08 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><Plug size={15} strokeWidth={1.9} />{t('settings.connSection')}</div>
              <div className="panel-sub">{t('settings.counts')}</div>
            </div>
            <Plug size={20} color="var(--ink-4)" />
          </div>

          <div className="kdv-rows">
            <div className="kdv-row">
              <span>{t('settings.firestore')}</span>
              <strong className="mono" style={{ fontSize: 12.5 }}>PostgreSQL 15</strong>
            </div>
            <div className="kdv-row">
              <span>{t('settings.apiUrl')}</span>
              <strong className="mono" style={{ fontSize: 12.5 }}>
                {apiBaseUrl || window.location.origin}
              </strong>
            </div>
            <div className="kdv-row">
              <span>{t('common.status')}</span>
              <strong style={{ color: apiUp ? 'var(--ok)' : 'var(--stop)' }}>
                {apiUp == null ? '…' : apiUp ? t('common.online') : t('common.offline')}
              </strong>
            </div>
          </div>

          <div className="panel-head" style={{ marginTop: 26 }}>
            <div>
              <div className="panel-title"><Database size={15} strokeWidth={1.9} />{t('settings.counts')}</div>
            </div>
            <Database size={20} color="var(--ink-4)" />
          </div>
          <div className="legend">
            {counts.map(([label, n]) => (
              <div className="legend__row" key={label}>
                <span className="legend__left">{label}</span>
                <span className="legend__val tnum">{n}</span>
              </div>
            ))}
          </div>

          <div className="panel-head" style={{ marginTop: 26 }}>
            <div>
              <div className="panel-title"><Sparkles size={15} strokeWidth={1.9} />{t('settings.vendorSection')}</div>
              <div className="panel-sub">{t('settings.vendorSectionSub')}</div>
            </div>
            <Sparkles size={20} color="var(--ink-4)" />
          </div>
          {vendorCategories.length ? (
            <>
              <ul className="learned-list">
                {vendorCategories.map((v) => (
                  <li className="learned-row" key={v.id}>
                    <span className="learned-row__vendor" title={v.vendor}>{v.vendor || v.vendorKey}</span>
                    <span className="learned-row__cat">{t(`dashboard.cat.${v.category}`)}</span>
                    {v.corrected && <span className="learned-row__flag">{t('settings.vendorCorrected')}</span>}
                    <button
                      className="icon-btn icon-btn--danger"
                      onClick={() => handleForget(v.id)}
                      disabled={forgetting !== null}
                      aria-label={t('settings.vendorForget')}
                      title={t('settings.vendorForget')}
                    >
                      {forgetting === v.id ? <Loader2 size={13} className="spin" /> : <X size={13} strokeWidth={1.9} />}
                    </button>
                  </li>
                ))}
              </ul>
              <button
                className="btn btn--ghost btn--sm"
                style={{ marginTop: 12 }}
                onClick={handleForgetAll}
                disabled={forgetting !== null}
              >
                {forgetting === 'all' ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} strokeWidth={1.9} />}
                {t('settings.vendorForgetAll')}
              </button>
            </>
          ) : (
            <p className="learned-empty">{t('settings.vendorEmpty')}</p>
          )}

          <div className="panel-head" style={{ marginTop: 26 }}>
            <div>
              <div className="panel-title"><Trash2 size={15} strokeWidth={1.9} />{t('settings.dataSection')}</div>
              <div className="panel-sub">{t('settings.dataSectionHint')}</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn btn--ghost btn--sm" onClick={handleClear} disabled={clearing}>
              {clearing ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} strokeWidth={1.9} />}
              {t('settings.clearBtn')}
            </button>
          </div>
        </motion.section>
      </div>
    </div>
  )
}

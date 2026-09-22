import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, Loader2, Sparkles, X } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'
import { useData } from '../../context/DataContext.jsx'
import { splitVat } from '../../lib/vat.js'
import { classifyExpenses } from '../../lib/api.js'
import { rememberVendorCategory, vendorKey } from '../../lib/db.js'

const CATEGORIES = [
  'sales', 'raw_materials', 'office_supplies', 'marketing', 'software', 'rent',
  'utilities', 'shipping', 'travel', 'fuel', 'equipment', 'maintenance',
  'insurance', 'payroll', 'bank_fees', 'tax_payments', 'restaurant', 'other',
]
const CONFIDENCE_THRESHOLD = 0.7

/**
 * Create / edit an invoice.
 *
 * Fields whose OCR confidence fell below 0.7 are highlighted — that is the
 * review queue the backend's per-field confidence was always for. Net, VAT
 * and gross stay consistent: editing the gross re-derives the split.
 */
export default function InvoiceModal({ invoice, mode, onClose, onSave }) {
  const { t, lang } = useLang()
  const { vendorCategories, learnedCategories } = useData()
  const [form, setForm] = useState(invoice)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // What the classifier proposed, and whether it came from this company's own
  // corrections or from the generic keyword rules.
  const [suggestion, setSuggestion] = useState(null)

  const conf = invoice.fieldConfidence || null
  const lowFields = useMemo(
    () =>
      conf
        ? Object.entries(conf)
            .filter(([, c]) => c < CONFIDENCE_THRESHOLD)
            .map(([k]) => k)
        : [],
    [conf],
  )

  // Suggest a category from the vendor + number. The company's own learned
  // corrections go with the request and outrank the keyword rules there.
  useEffect(() => {
    if (mode !== 'create' || !form.vendor || form.category !== 'other') return
    let cancelled = false
    classifyExpenses(
      [{ id: 'draft', vendor: form.vendor, description: form.number }],
      learnedCategories,
    )
      .then((res) => {
        const hit = res.items?.[0]
        if (cancelled || !hit?.category) return
        setSuggestion(hit)
        setForm((f) => (f.category === 'other' ? { ...f, category: hit.category } : f))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
    // Only re-run when the vendor changes; category is read, not tracked.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.vendor, mode, learnedCategories])

  const set = (key) => (e) => {
    const raw = e.target.value
    setForm((f) => ({ ...f, [key]: raw }))
  }

  function setGross(value) {
    const gross = Number(value) || 0
    const { net, vat } = splitVat(gross, Number(form.vatRate) || 0.2)
    setForm((f) => ({ ...f, amount: gross, netAmount: net, vatAmount: vat }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    if (!form.vendor.trim()) {
      setError(t('auth.required'))
      return
    }
    setBusy(true)
    try {
      const payload = {
        ...form,
        vendor: form.vendor.trim(),
        number: form.number.trim() || `MUH-${Date.now().toString().slice(-8)}`,
        amount: Number(form.amount) || 0,
        netAmount: Number(form.netAmount) || 0,
        vatAmount: Number(form.vatAmount) || 0,
        vatRate: Number(form.vatRate) || 0.2,
        // Saving is the review: once a human has confirmed the fields the
        // invoice leaves the queue.
        needsReview: false,
        paidDate: form.status === 'paid' ? form.paidDate || form.issueDate : null,
      }
      delete payload.fieldConfidence
      await onSave(payload, mode)

      // Only once the invoice is safely saved. A correction recorded against a
      // save that then failed would teach the classifier from an event the
      // user never actually committed to.
      const chosen = payload.category
      const known = learnedCategories[vendorKey(payload.vendor)]
      if (chosen && chosen !== 'other' && chosen !== known) {
        // "Corrected" means a human disagreed with the suggestion. Accepting
        // what the rules proposed is worth caching but is not a correction.
        const corrected = mode !== 'create' || chosen !== suggestion?.category
        await rememberVendorCategory(vendorCategories, payload.vendor, chosen, corrected)
          .catch((e) => console.error('[muhai] could not remember the vendor category', e))
      }
    } catch (err) {
      console.error('[muhai] invoice save failed', err)
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const fieldClass = (key) => (lowFields.includes(key) ? 'field field--flag' : 'field')

  return (
    <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.div
        className="modal modal--wide"
        initial={{ x: 28, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.24, ease: [0.22, 0.8, 0.3, 1] }}
      >
        <div className="modal__head">
          <div>
            <div className="modal__title">
              {mode === 'create' ? t('invoices.newInvoice') : t('invoices.editInvoice')}
            </div>
            {invoice.ocrConfidence != null && (
              <div className="modal__sub">
                OCR {lang === 'en' ? 'confidence' : 'güveni'} %{Math.round(invoice.ocrConfidence * 100)}
                {invoice.source === 'ocr'
                  ? lang === 'en' ? ' · on the server' : ' · sunucuda'
                  : lang === 'en' ? ' · on this device' : ' · cihaz üstünde'}
              </div>
            )}
          </div>
          {/* type="button" is not optional: a <button> inside a <form> defaults
              to type="submit", which made this X the form's default button —
              so Enter anywhere in the form activated *close*, not save. */}
          <button type="button" className="icon-btn" onClick={onClose} aria-label={t('common.close')}>
            <X size={16} strokeWidth={1.9} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal__body">
            {lowFields.length > 0 && (
              <div className="review-banner" style={{ margin: 0 }}>
                <AlertTriangle size={17} strokeWidth={1.9} />
                <span>
                  {lowFields.length} {t('invoices.reviewBody')}
                </span>
              </div>
            )}

            <div className="field-row">
              <label className={fieldClass('vendor')}>
                <span className="field__label">{t('invoices.vendor')}</span>
                <span className="field__wrap">
                  <input value={form.vendor} onChange={set('vendor')} required placeholder="Anadolu Tedarik A.Ş." />
                </span>
              </label>
              <label className={fieldClass('number')}>
                <span className="field__label">{t('invoices.invoiceNo')}</span>
                <span className="field__wrap">
                  <input value={form.number} onChange={set('number')} placeholder="MUH-2026-0001" />
                </span>
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('invoices.taxId')}</span>
                <span className="field__wrap">
                  <input value={form.taxId || ''} onChange={set('taxId')} inputMode="numeric" maxLength={11} />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('invoices.direction')}</span>
                <span className="field__wrap">
                  <select value={form.direction} onChange={set('direction')}>
                    <option value="purchase">{t('invoices.dirPurchase')}</option>
                    <option value="sales">{t('invoices.dirSales')}</option>
                  </select>
                </span>
              </label>
            </div>

            <div className="field-row">
              <label className={fieldClass('date')}>
                <span className="field__label">{t('invoices.issueDate')}</span>
                <span className="field__wrap">
                  <input type="date" value={form.issueDate || ''} onChange={set('issueDate')} />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('invoices.dueDate')}</span>
                <span className="field__wrap">
                  <input type="date" value={form.dueDate || ''} onChange={set('dueDate')} />
                </span>
              </label>
            </div>

            <div className="field-row">
              <label className={fieldClass('amount')}>
                <span className="field__label">{t('invoices.total')}</span>
                <span className="field__wrap">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.amount}
                    onChange={(e) => setGross(e.target.value)}
                    required
                  />
                </span>
                <span className="field__hint">
                  {t('invoices.netAmount')} {Number(form.netAmount).toFixed(2)} · {t('invoices.vat')}{' '}
                  {Number(form.vatAmount).toFixed(2)}
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('invoices.category')}</span>
                <span className="field__wrap">
                  <select value={form.category} onChange={set('category')}>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {t(`dashboard.cat.${c}`)}
                      </option>
                    ))}
                  </select>
                </span>
                {suggestion && (
                  <span className="field__hint field__hint--learn">
                    <Sparkles size={12} strokeWidth={1.9} />
                    {suggestion.source === 'learned'
                      ? t('invoices.catLearned')
                      : t('invoices.catSuggested')}
                  </span>
                )}
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('common.status')}</span>
                <span className="field__wrap">
                  <select value={form.status} onChange={set('status')}>
                    <option value="pending">{t('invoices.stPending')}</option>
                    <option value="paid">{t('invoices.stPaid')}</option>
                    <option value="overdue">{t('invoices.stOverdue')}</option>
                  </select>
                </span>
              </label>
              {form.status === 'paid' && (
                <label className="field">
                  <span className="field__label">{t('invoices.stPaid')}</span>
                  <span className="field__wrap">
                    <input type="date" value={form.paidDate || form.issueDate || ''} onChange={set('paidDate')} />
                  </span>
                </label>
              )}
            </div>

            {invoice.rawText && (
              <details className="raw-text">
                <summary>{t('invoices.rawText')}</summary>
                <pre>{invoice.rawText.slice(0, 3000)}</pre>
              </details>
            )}

            {error && <div className="auth-alert auth-alert--error">{error}</div>}
          </div>

          <div className="modal__foot">
            <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {busy && <Loader2 size={15} className="spin" />}
              {busy ? t('invoices.saving') : t('invoices.saveInvoice')}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

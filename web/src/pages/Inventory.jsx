import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, Boxes, Loader2, Minus, Plus, Search, Timer, Trash2, X } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useData } from '../context/DataContext.jsx'
import { formatCurrency, formatNumber } from '../lib/format.js'
import { COLLECTIONS, addItem, removeItem, updateItem } from '../lib/db.js'
import { inventoryValue, lowStock, monthsOfCover } from '../lib/analytics.js'
import Badge from '../components/ui/Badge.jsx'
import BarChart from '../components/charts/BarChart.jsx'
import PageSkeleton from '../components/ui/PageSkeleton.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'

const emptyProduct = () => ({
  name: '',
  sku: '',
  stock: 0,
  minStock: 0,
  unitPrice: 0,
  unit: 'adet',
  monthlyUsage: 0,
})

function statusOf(p) {
  const stock = Number(p.stock) || 0
  const min = Number(p.minStock) || 0
  if (stock <= 0) return 'out'
  if (stock <= min) return 'low'
  return 'in'
}

const TONE = { in: 'green', low: 'amber', out: 'red' }

export default function Inventory() {
  const { t, lang } = useLang()
  const { companyId, products, loading, isEmpty } = useData()
  const cur = (v) => formatCurrency(v, lang)

  const [query, setQuery] = useState('')
  const [modal, setModal] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const critical = useMemo(() => lowStock(products), [products])
  const totalValue = useMemo(() => inventoryValue(products), [products])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return products
      .filter((p) => !q || `${p.name} ${p.sku || ''}`.toLowerCase().includes(q))
      .sort((a, b) => statusOf(a).localeCompare(statusOf(b)) || a.name.localeCompare(b.name))
  }, [products, query])

  // Stock relative to the reorder point, so the chart shows headroom rather
  // than raw counts that are not comparable across units.
  const coverChart = useMemo(
    () =>
      products
        .map((p) => ({ label: p.name, value: monthsOfCover(p) ?? 0 }))
        .filter((d) => d.value > 0)
        .sort((a, b) => a.value - b.value)
        .slice(0, 8),
    [products],
  )

  async function adjustStock(product, delta) {
    setBusyId(product.id)
    try {
      const next = Math.max(0, (Number(product.stock) || 0) + delta)
      await updateItem(COLLECTIONS.products, product.id, { stock: next })
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(product) {
    if (!window.confirm(`${product.name} — ${t('common.delete')}?`)) return
    setBusyId(product.id)
    try {
      await removeItem(COLLECTIONS.products, product.id)
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <PageSkeleton />
  if (isEmpty) return <EmptyState />

  return (
    <div className="page">
      <div className="page-head page-head-row">
        <div>
          <div className="page-eyebrow">
            <Boxes size={14} strokeWidth={1.9} />
            <span className="label">{t('nav.inventory')}</span>
          </div>
          <h1 className="page-title">{t('inventory.title')}</h1>
          <p className="page-sub">{t('inventory.subtitle')}</p>
        </div>
        <button className="btn btn--primary btn--sm" onClick={() => setModal(emptyProduct())}>
          <Plus size={14} strokeWidth={1.9} /> {t('inventory.addProduct')}
        </button>
      </div>

      <div className="mini-stats" style={{ marginBottom: 20 }}>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('inventory.kpiSku')}</div>
          <div className="mini-stats__value tnum">{products.length}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('inventory.kpiValue')}</div>
          <div className="mini-stats__value tnum">{cur(totalValue)}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('inventory.kpiLow')}</div>
          <div className={`mini-stats__value tnum ${critical.length ? 'mini-stats__value--neg' : ''}`}>
            {critical.length}
          </div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{lang === 'en' ? 'Units in stock' : 'Toplam adet'}</div>
          <div className="mini-stats__value tnum">
            {formatNumber(products.reduce((s, p) => s + (Number(p.stock) || 0), 0), lang)}
          </div>
        </div>
      </div>

      {critical.length > 0 && (
        <div className="review-banner">
          <Boxes size={18} strokeWidth={1.9} />
          <span>
            <strong>{t('inventory.kpiLow')}</strong> — {critical.map((p) => p.name).join(', ')}
          </span>
        </div>
      )}

      <div className="dash-grid">
        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">
                <Timer size={15} strokeWidth={1.9} />
                {lang === 'en' ? 'Months of cover' : 'Kaç aylık stok'}
              </div>
              <div className="panel-sub">
                {lang === 'en' ? 'Stock ÷ recorded monthly usage' : 'Stok ÷ aylık kullanım'}
              </div>
            </div>
          </div>
          {coverChart.length ? (
            <BarChart
              data={coverChart}
              labels={coverChart.map((d) => d.label.split(' ')[0])}
              keys={['value']}
              colors={['var(--d1)']}
              seriesNames={[lang === 'en' ? 'Months' : 'Ay']}
              formatValue={(v) => `${v} ${lang === 'en' ? 'mo' : 'ay'}`}
              height={220}
            />
          ) : (
            <div className="chart-empty" style={{ height: 200 }}>{t('common.none')}</div>
          )}
        </motion.section>

        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.08 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><BarChart3 size={15} strokeWidth={1.9} />{t('inventory.topTitle')}</div>
              <div className="panel-sub">{lang === 'en' ? 'By stock value' : 'Stok değerine göre'}</div>
            </div>
          </div>
          <div className="legend">
            {[...products]
              .sort((a, b) => (b.stock * b.unitPrice) - (a.stock * a.unitPrice))
              .slice(0, 6)
              .map((p) => (
                <div className="legend__row" key={p.id}>
                  <span className="legend__left">
                    <span className="legend__swatch" style={{ background: statusOf(p) === 'in' ? 'var(--ok)' : 'var(--warn)' }} />
                    {p.name}
                  </span>
                  <span className="legend__val">{cur((Number(p.stock) || 0) * (Number(p.unitPrice) || 0))}</span>
                </div>
              ))}
          </div>
        </motion.section>

        <motion.section className="panel dash-invoices" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.14 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><Boxes size={15} strokeWidth={1.9} />{t('inventory.tableTitle')}</div>
              <div className="panel-sub">{visible.length} / {products.length}</div>
            </div>
            <label className="search-inline">
              <Search size={15} strokeWidth={1.9} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('common.search')} />
            </label>
          </div>

          {visible.length ? (
            <div className="tbl-scroll">
              <table className="tbl">
              <thead>
                <tr>
                  <th style={{ paddingLeft: 22 }}>{t('inventory.colProduct')}</th>
                  <th>{t('inventory.colSku')}</th>
                  <th className="num">{t('inventory.colStock')}</th>
                  <th className="num">{lang === 'en' ? 'Reorder at' : 'Kritik'}</th>
                  <th className="num">{t('inventory.colPrice')}</th>
                  <th className="num">{t('common.total')}</th>
                  <th>{t('inventory.colStatus')}</th>
                  <th style={{ paddingRight: 22, textAlign: 'right' }}>{t('common.action')}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((p) => {
                  const st = statusOf(p)
                  return (
                    <tr key={p.id}>
                      <td className="strong" style={{ paddingLeft: 22 }}>{p.name}</td>
                      <td className="mono" style={{ fontSize: 12.5 }}>{p.sku || '—'}</td>
                      <td className="num tnum strong">{formatNumber(p.stock, lang)}</td>
                      <td className="num tnum" style={{ color: 'var(--ink-3)' }}>{formatNumber(p.minStock, lang)}</td>
                      <td className="num tnum">{cur(p.unitPrice)}</td>
                      <td className="num tnum strong">{cur((Number(p.stock) || 0) * (Number(p.unitPrice) || 0))}</td>
                      <td>
                        <Badge tone={TONE[st]}>
                          {st === 'in' ? t('inventory.stIn') : st === 'low' ? t('inventory.stLow') : t('inventory.stOut')}
                        </Badge>
                      </td>
                      <td style={{ paddingRight: 22 }}>
                        <div className="row-actions">
                          <button className="icon-btn" onClick={() => adjustStock(p, -1)} disabled={busyId === p.id} title="-1">
                            <Minus size={14} strokeWidth={1.9} />
                          </button>
                          <button className="icon-btn" onClick={() => adjustStock(p, 1)} disabled={busyId === p.id} title="+1">
                            <Plus size={14} strokeWidth={1.9} />
                          </button>
                          <button className="icon-btn icon-btn--danger" onClick={() => handleDelete(p)} disabled={busyId === p.id} title={t('common.delete')}>
                            <Trash2 size={14} strokeWidth={1.9} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              </table>
            </div>
          ) : (
            <div className="chart-empty" style={{ height: 160, margin: '0 22px' }}>{t('common.none')}</div>
          )}
        </motion.section>
      </div>

      {modal && (
        <ProductModal
          product={modal}
          onClose={() => setModal(null)}
          onSave={async (data) => {
            await addItem(COLLECTIONS.products, data)
            setModal(null)
          }}
        />
      )}
    </div>
  )
}

function ProductModal({ product, onClose, onSave }) {
  const { t } = useLang()
  const [form, setForm] = useState(product)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      setError(t('auth.required'))
      return
    }
    setBusy(true)
    try {
      await onSave({
        ...form,
        name: form.name.trim(),
        sku: form.sku.trim(),
        stock: Number(form.stock) || 0,
        minStock: Number(form.minStock) || 0,
        unitPrice: Number(form.unitPrice) || 0,
        monthlyUsage: Number(form.monthlyUsage) || 0,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.div className="modal" initial={{ x: 28, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.24, ease: [0.22, 0.8, 0.3, 1] }}>
        <div className="modal__head">
          <div className="modal__title">{t('inventory.addProduct')}</div>
          <button className="icon-btn" onClick={onClose} aria-label={t('common.close')}>
            <X size={16} strokeWidth={1.9} />
          </button>
        </div>
        <form onSubmit={submit}>
          <div className="modal__body">
            <label className="field">
              <span className="field__label">{t('inventory.colProduct')}</span>
              <span className="field__wrap">
                <input value={form.name} onChange={set('name')} required />
              </span>
            </label>
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('inventory.colSku')}</span>
                <span className="field__wrap">
                  <input value={form.sku} onChange={set('sku')} />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('inventory.units')}</span>
                <span className="field__wrap">
                  <input value={form.unit} onChange={set('unit')} />
                </span>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('inventory.colStock')}</span>
                <span className="field__wrap">
                  <input type="number" min="0" value={form.stock} onChange={set('stock')} />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('inventory.kpiLow')}</span>
                <span className="field__wrap">
                  <input type="number" min="0" value={form.minStock} onChange={set('minStock')} />
                </span>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('inventory.colPrice')}</span>
                <span className="field__wrap">
                  <input type="number" min="0" step="0.01" value={form.unitPrice} onChange={set('unitPrice')} />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('inventory.kpiTurnover')}</span>
                <span className="field__wrap">
                  <input type="number" min="0" value={form.monthlyUsage} onChange={set('monthlyUsage')} />
                </span>
              </label>
            </div>
            {error && <div className="auth-alert auth-alert--error">{error}</div>}
          </div>
          <div className="modal__foot">
            <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {busy && <Loader2 size={15} className="spin" />}
              {t('common.save')}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

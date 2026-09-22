import { useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Pencil,
  Plus,
  ReceiptText,
  ScanLine,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useData } from '../context/DataContext.jsx'
import { formatCurrency, formatDate } from '../lib/format.js'
import { COLLECTIONS, markInvoicePaid, removeItem, saveInvoiceWithLedger, updateItem } from '../lib/db.js'
import { scanInvoice } from '../lib/api.js'
import { runOcr } from '../lib/ocr.js'
import { isOverdue } from '../lib/analytics.js'
import { splitVat } from '../lib/vat.js'
import Badge from '../components/ui/Badge.jsx'
import InvoiceModal from '../components/invoices/InvoiceModal.jsx'
import PageSkeleton from '../components/ui/PageSkeleton.jsx'

const STATUS_TONE = { paid: 'green', pending: 'amber', overdue: 'red' }
const CONFIDENCE_THRESHOLD = 0.7

const emptyInvoice = () => {
  const today = new Date().toISOString().slice(0, 10)
  return {
    number: '',
    vendor: '',
    taxId: '',
    direction: 'purchase',
    issueDate: today,
    dueDate: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
    paidDate: null,
    amount: 0,
    netAmount: 0,
    vatAmount: 0,
    vatRate: 0.2,
    status: 'pending',
    category: 'other',
    source: 'manual',
    ocrConfidence: null,
    needsReview: false,
    currency: 'TRY',
  }
}

export default function Invoices() {
  const { t, lang } = useLang()
  const { companyId, invoices, loading } = useData()
  const cur = (v) => formatCurrency(v, lang)

  const fileRef = useRef(null)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [modal, setModal] = useState(null) // { invoice, mode, ocr }
  const [scanning, setScanning] = useState(false)
  const [scanMode, setScanMode] = useState('server')
  const [progress, setProgress] = useState(0)
  const [flash, setFlash] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const reviewCount = invoices.filter((i) => i.needsReview).length

  const stats = useMemo(() => {
    const paid = invoices.filter((i) => i.status === 'paid')
    const pending = invoices.filter((i) => i.status !== 'paid')
    const scanned = invoices.filter((i) => i.ocrConfidence != null)
    const avgConfidence = scanned.length
      ? (scanned.reduce((s, i) => s + i.ocrConfidence, 0) / scanned.length) * 100
      : null
    return {
      total: invoices.length,
      pending: pending.length,
      pendingValue: pending.reduce((s, i) => s + (Number(i.amount) || 0), 0),
      paid: paid.length,
      paidValue: paid.reduce((s, i) => s + (Number(i.amount) || 0), 0),
      avgConfidence,
    }
  }, [invoices])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return invoices
      .filter((i) => {
        if (filter === 'review') return Boolean(i.needsReview)
        if (filter !== 'all') {
          const status = isOverdue(i) ? 'overdue' : i.status
          if (status !== filter) return false
        }
        if (!q) return true
        return `${i.vendor} ${i.number}`.toLowerCase().includes(q)
      })
      .sort((a, b) => String(b.issueDate).localeCompare(String(a.issueDate)))
  }, [invoices, filter, query])

  function notify(message, tone = 'ok') {
    setFlash({ message, tone })
    setTimeout(() => setFlash(null), 4000)
  }

  // ── OCR ─────────────────────────────────────────────────────────────
  async function handleFile(file) {
    if (!file) return
    setScanning(true)
    setProgress(0)
    try {
      const draft = emptyInvoice()

      if (scanMode === 'server') {
        const res = await scanInvoice(file)
        const value = (f) => res[f]?.value ?? null
        const conf = (f) => res[f]?.confidence ?? 0

        const total = Number(value('total_amount')) || 0
        const vat = Number(value('vat_amount')) || splitVat(total).vat

        Object.assign(draft, {
          vendor: value('vendor_name') || '',
          number: value('invoice_number') || '',
          issueDate: value('date') || draft.issueDate,
          amount: total,
          vatAmount: vat,
          netAmount: Math.max(total - vat, 0),
          source: 'ocr',
          ocrConfidence: Math.min(
            conf('vendor_name'),
            conf('invoice_number'),
            conf('total_amount'),
          ),
          needsReview: res.needs_review,
          rawText: res.raw_text || '',
          fieldConfidence: {
            vendor: conf('vendor_name'),
            number: conf('invoice_number'),
            date: conf('date'),
            amount: conf('total_amount'),
            vat: conf('vat_amount'),
          },
        })
      } else {
        const res = await runOcr(file, setProgress)
        const total = res.fields.total || 0
        const vat = res.fields.vat ?? splitVat(total).vat
        const confidence = res.confidence / 100
        Object.assign(draft, {
          vendor: res.fields.vendor === '—' ? '' : res.fields.vendor,
          number: res.fields.invoiceNo === '—' ? '' : res.fields.invoiceNo,
          taxId: res.fields.taxId === '—' ? '' : res.fields.taxId,
          amount: total,
          vatAmount: vat,
          netAmount: res.fields.subtotal ?? Math.max(total - vat, 0),
          source: 'ocr-browser',
          ocrConfidence: confidence,
          needsReview: confidence < CONFIDENCE_THRESHOLD || !total,
          rawText: res.text,
          fieldConfidence: null,
        })
      }

      setModal({ invoice: draft, mode: 'create' })
      notify(t('invoices.ocrDone'))
    } catch (err) {
      console.error('[muhai] OCR failed', err)
      notify(err.message || t('invoices.ocrError'), 'error')
    } finally {
      setScanning(false)
      setProgress(0)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  // ── Persistence ─────────────────────────────────────────────────────
  async function handleSave(invoice, mode) {
    if (mode === 'create') {
      await saveInvoiceWithLedger(invoice)
    } else {
      const { id, ...patch } = invoice
      await updateItem(COLLECTIONS.invoices, id, patch)
    }
    setModal(null)
    notify(t('invoices.saved'))
  }

  async function handleDelete(invoice) {
    if (!window.confirm(t('invoices.deleteConfirm'))) return
    setBusyId(invoice.id)
    try {
      await removeItem(COLLECTIONS.invoices, invoice.id)
    } finally {
      setBusyId(null)
    }
  }

  async function handleMarkPaid(invoice) {
    setBusyId(invoice.id)
    try {
      await markInvoicePaid(invoice)
    } finally {
      setBusyId(null)
    }
  }

  function exportCsv() {
    const header = ['number', 'vendor', 'direction', 'issueDate', 'dueDate', 'net', 'vat', 'amount', 'status']
    const rows = visible.map((i) =>
      [i.number, i.vendor, i.direction, i.issueDate, i.dueDate, i.netAmount, i.vatAmount, i.amount, i.status]
        .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`)
        .join(','),
    )
    const blob = new Blob(['﻿' + [header.join(','), ...rows].join('\n')], {
      type: 'text/csv;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `muhai-faturalar-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <PageSkeleton />

  return (
    <div className="page">
      <div className="page-head page-head-row">
        <div>
          <div className="page-eyebrow">
            <ReceiptText size={14} strokeWidth={1.9} />
            <span className="label">{t('nav.invoices')}</span>
          </div>
          <h1 className="page-title">{t('invoices.title')}</h1>
          <p className="page-sub">{t('invoices.subtitle')}</p>
        </div>
        <div className="page-actions">
          <button className="btn btn--ghost btn--sm" onClick={exportCsv} disabled={!visible.length}>
            <Download size={14} strokeWidth={1.9} /> {t('invoices.exportCsv')}
          </button>
          <button className="btn btn--ghost btn--sm" onClick={() => setModal({ invoice: emptyInvoice(), mode: 'create' })}>
            <Plus size={14} strokeWidth={1.9} /> {t('invoices.addManual')}
          </button>
          <button className="btn btn--primary btn--sm" onClick={() => fileRef.current?.click()} disabled={scanning}>
            {scanning ? <Loader2 size={14} className="spin" /> : <Upload size={14} strokeWidth={1.9} />}
            {scanning ? t('invoices.scanning') : t('invoices.upload')}
          </button>
        </div>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*,.pdf"
        hidden
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {flash && (
        <motion.div
          className={`notice notice--${flash.tone === 'error' ? 'error' : 'info'}`}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ marginBottom: 16 }}
        >
          {flash.message}
        </motion.div>
      )}

      {reviewCount > 0 && (
        <div className="review-banner">
          <AlertTriangle size={18} strokeWidth={1.9} />
          <span>
            <strong>{t('invoices.reviewTitle')}</strong> — {reviewCount} {t('invoices.reviewBody')}
          </span>
          <span className="review-banner__spacer" />
          <button className="btn btn--ghost btn--sm" onClick={() => setFilter('review')}>
            {t('invoices.reviewOpen')}
          </button>
        </div>
      )}

      <div className="mini-stats" style={{ marginBottom: 20 }}>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('invoices.kpiTotal')}</div>
          <div className="mini-stats__value tnum">{stats.total}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('invoices.kpiPending')}</div>
          <div className="mini-stats__value tnum">{cur(stats.pendingValue)}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('invoices.kpiPaid')}</div>
          <div className="mini-stats__value tnum">{cur(stats.paidValue)}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('invoices.kpiOcr')}</div>
          <div className="mini-stats__value tnum">
            {stats.avgConfidence != null ? `%${stats.avgConfidence.toFixed(1)}` : '—'}
          </div>
        </div>
      </div>

      <div className="toolbar">
        <div className="seg">
          {['all', 'pending', 'paid', 'overdue', 'review'].map((k) => (
            <button key={k} className={filter === k ? 'is-active' : ''} onClick={() => setFilter(k)}>
              {k === 'all'
                ? t('invoices.filterAll')
                : k === 'review'
                  ? t('invoices.needsReview')
                  : t(`invoices.st${k[0].toUpperCase()}${k.slice(1)}`)}
            </button>
          ))}
        </div>
        <label className="search-inline">
          <Search size={15} strokeWidth={1.9} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('invoices.searchPlaceholder')} />
        </label>
        <span className="toolbar__spacer" />
        <div className="seg">
          <button className={scanMode === 'server' ? 'is-active' : ''} onClick={() => setScanMode('server')} title={t('invoices.scanServer')}>
            <ScanLine size={13} strokeWidth={1.9} style={{ verticalAlign: -2, marginRight: 5 }} />
            {lang === 'en' ? 'On server' : 'Sunucuda'}
          </button>
          <button className={scanMode === 'browser' ? 'is-active' : ''} onClick={() => setScanMode('browser')} title={t('invoices.scanBrowser')}>
            {lang === 'en' ? 'On-device' : 'Cihaz üstü'}
          </button>
        </div>
      </div>

      {scanning && scanMode === 'browser' && (
        <div className="notice notice--info" style={{ marginBottom: 16 }}>
          {t('invoices.recognizing')} — %{Math.round(progress * 100)}
        </div>
      )}

      <section className="panel" style={{ paddingLeft: 0, paddingRight: 0 }}>
        <div className="panel-head" style={{ padding: '0 22px' }}>
          <div>
            <div className="panel-title"><FileText size={15} strokeWidth={1.9} />{t('invoices.tableTitle')}</div>
            <div className="panel-sub">
              {visible.length} / {invoices.length}
            </div>
          </div>
        </div>

        {visible.length === 0 ? (
          <div className="chart-empty" style={{ height: 180, margin: '0 22px' }}>
            {t('invoices.noInvoices')}
          </div>
        ) : (
          <div className="tbl-scroll">
            <table className="tbl">
            <thead>
              <tr>
                <th style={{ paddingLeft: 22 }}>{t('invoices.colVendor')}</th>
                <th>{t('invoices.colNo')}</th>
                <th>{t('invoices.colDate')}</th>
                <th>{t('invoices.colDue')}</th>
                <th className="num">{t('invoices.vat')}</th>
                <th className="num">{t('invoices.colAmount')}</th>
                <th>{t('invoices.colStatus')}</th>
                <th style={{ paddingRight: 22, textAlign: 'right' }}>{t('common.action')}</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((inv) => {
                const status = isOverdue(inv) ? 'overdue' : inv.status
                return (
                  <tr key={inv.id}>
                    <td className="strong" style={{ paddingLeft: 22 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {inv.vendor}
                        {inv.source?.startsWith('ocr') && (
                          <span className={`conf ${inv.ocrConfidence >= CONFIDENCE_THRESHOLD ? 'conf--ok' : 'conf--low'}`}>
                            OCR %{Math.round((inv.ocrConfidence ?? 0) * 100)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="mono" style={{ fontSize: 12.5 }}>{inv.number}</td>
                    <td>{formatDate(inv.issueDate, lang)}</td>
                    <td>{inv.dueDate ? formatDate(inv.dueDate, lang) : '—'}</td>
                    <td className="num tnum">{cur(inv.vatAmount || 0)}</td>
                    <td className="num strong tnum">{cur(inv.amount)}</td>
                    <td>
                      <Badge tone={STATUS_TONE[status]}>
                        {t(`invoices.st${status[0].toUpperCase()}${status.slice(1)}`)}
                      </Badge>
                    </td>
                    <td style={{ paddingRight: 22 }}>
                      <div className="row-actions">
                        {inv.status !== 'paid' && (
                          <button
                            className="icon-btn"
                            title={t('invoices.markPaid')}
                            onClick={() => handleMarkPaid(inv)}
                            disabled={busyId === inv.id}
                          >
                            <CheckCircle2 size={15} strokeWidth={1.9} />
                          </button>
                        )}
                        <button className="icon-btn" title={t('common.edit')} onClick={() => setModal({ invoice: inv, mode: 'edit' })}>
                          <Pencil size={14} strokeWidth={1.9} />
                        </button>
                        <button
                          className="icon-btn icon-btn--danger"
                          title={t('common.delete')}
                          onClick={() => handleDelete(inv)}
                          disabled={busyId === inv.id}
                        >
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
        )}
      </section>

      {!invoices.length && (
        <p className="page-sub" style={{ marginTop: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={15} /> {t('invoices.dropOr')}
        </p>
      )}

      {modal && (
        <InvoiceModal
          invoice={modal.invoice}
          mode={modal.mode}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}
    </div>
  )
}

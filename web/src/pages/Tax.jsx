import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { CalendarClock, Calculator, CheckCircle2, FileText, Landmark, PieChart } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useData } from '../context/DataContext.jsx'
import { formatCurrency, formatDate, MONTHS } from '../lib/format.js'
import { COLLECTIONS, updateItem } from '../lib/db.js'
import Badge from '../components/ui/Badge.jsx'
import BarChart from '../components/charts/BarChart.jsx'
import PageSkeleton from '../components/ui/PageSkeleton.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'

const VAT_RATES = [
  { key: 'standard', value: 0.2, label: '%20' },
  { key: 'reduced', value: 0.1, label: '%10' },
  { key: 'basic', value: 0.01, label: '%1' },
]

export default function Tax() {
  const { t, lang } = useLang()
  const { companyId, taxSummary, dashboard, taxObligations, loading, isEmpty, apiOnline } = useData()
  const cur = (v) => formatCurrency(v, lang)
  const compact = (v) => formatCurrency(v, lang, { compact: true })

  // Local calculator — the same 2026 split the backend applies, run instantly
  // as the user types rather than round-tripping every keystroke.
  const [amount, setAmount] = useState(100000)
  const [rate, setRate] = useState(0.2)
  const [busyId, setBusyId] = useState(null)

  const calc = useMemo(() => {
    const gross = Number(amount) || 0
    const net = gross / (1 + rate)
    return { net, vat: gross - net, gross }
  }, [amount, rate])

  const burden = useMemo(() => {
    if (!taxSummary) return []
    return [
      { label: 'KDV', value: taxSummary.kdv_payable },
      { label: lang === 'en' ? 'Corporate (Q)' : 'Geçici vergi', value: taxSummary.corporate_quarterly },
      { label: lang === 'en' ? 'Withholding' : 'Stopaj', value: taxSummary.stopaj_rent },
    ].filter((b) => b.value > 0)
  }, [taxSummary, lang])

  const nextDeadline = taxSummary?.deadlines?.[0] ?? dashboard?.deadlines?.[0] ?? null

  async function markFiled(obligation) {
    setBusyId(obligation.id)
    try {
      await updateItem(COLLECTIONS.taxObligations, obligation.id, {
        status: 'filed',
        paidDate: new Date().toISOString().slice(0, 10),
      })
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <PageSkeleton />
  if (isEmpty) return <EmptyState />

  return (
    <div className="page">
      <div className="page-head">
        <div className="page-eyebrow">
          <Landmark size={14} strokeWidth={1.9} />
          <span className="label">{t('nav.tax')}</span>
        </div>
        <h1 className="page-title">{t('tax.title')}</h1>
        <p className="page-sub">{t('tax.subtitle')}</p>
      </div>

      {!apiOnline && (
        <div className="notice notice--warn" style={{ marginBottom: 18 }}>
          <strong>{t('common.offline')}</strong> — {t('common.offlineHint')}
        </div>
      )}

      <div className="mini-stats" style={{ marginBottom: 20 }}>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('tax.kpiVat')}</div>
          <div className="mini-stats__value tnum">{taxSummary ? cur(taxSummary.kdv_payable) : '—'}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{lang === 'en' ? 'Corporate advance' : 'Geçici vergi'}</div>
          <div className="mini-stats__value tnum">{taxSummary ? cur(taxSummary.corporate_quarterly) : '—'}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('tax.kpiWithholding')}</div>
          <div className="mini-stats__value tnum">{taxSummary ? cur(taxSummary.stopaj_rent) : '—'}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('tax.kpiNext')}</div>
          <div className="mini-stats__value tnum">
            {nextDeadline ? `${nextDeadline.days_remaining} ${t('tax.days')}` : '—'}
          </div>
        </div>
      </div>

      <div className="dash-grid">
        {/* KDV position */}
        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title">
                <Landmark size={15} strokeWidth={1.9} />
                {lang === 'en' ? 'VAT position' : 'KDV pozisyonu'} · {taxSummary?.period ?? '—'}
              </div>
              <div className="panel-sub">
                {lang === 'en'
                  ? 'Output VAT on sales less input VAT on purchases'
                  : 'Hesaplanan KDV eksi indirilecek KDV'}
              </div>
            </div>
          </div>

          {taxSummary ? (
            <>
              <div className="kdv-rows">
                <div className="kdv-row">
                  <span>{lang === 'en' ? 'Output VAT (sales)' : 'Hesaplanan KDV (satış)'}</span>
                  <strong className="tnum">{cur(taxSummary.kdv_collected)}</strong>
                </div>
                <div className="kdv-row">
                  <span>{lang === 'en' ? 'Input VAT (purchases)' : 'İndirilecek KDV (alış)'}</span>
                  <strong className="tnum" style={{ color: 'var(--stop)' }}>
                    −{cur(taxSummary.kdv_paid)}
                  </strong>
                </div>
                <div className="kdv-row kdv-row--total">
                  <span>{lang === 'en' ? 'VAT payable' : 'Ödenecek KDV'}</span>
                  <strong className="tnum">{cur(taxSummary.kdv_payable)}</strong>
                </div>
              </div>

              <div className="panel-head" style={{ marginTop: 26 }}>
                <div>
                  <div className="panel-title"><PieChart size={15} strokeWidth={1.9} />{t('tax.breakdownTitle')}</div>
                  <div className="panel-sub">
                    {lang === 'en' ? 'Total due this period' : 'Bu dönem toplam yük'} · {cur(taxSummary.total_due)}
                  </div>
                </div>
              </div>
              {burden.length ? (
                <BarChart
                  data={burden}
                  labels={burden.map((b) => b.label)}
                  keys={['value']}
                  colors={['var(--d1)']}
                  seriesNames={[lang === 'en' ? 'Amount' : 'Tutar']}
                  formatValue={cur}
                  height={180}
                />
              ) : (
                <div className="chart-empty" style={{ height: 140 }}>{t('common.none')}</div>
              )}
            </>
          ) : (
            <div className="chart-empty" style={{ height: 260 }}>{t('common.offline')}</div>
          )}
        </motion.section>

        {/* Calculator */}
        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.08 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><Calculator size={15} strokeWidth={1.9} />{t('tax.calcTitle')}</div>
              <div className="panel-sub">{t('tax.calcSub')}</div>
            </div>
            <Calculator size={20} color="var(--ink-4)" />
          </div>

          <label className="field">
            <span className="field__label">{t('tax.calcAmount')}</span>
            <span className="field__wrap">
              <input type="number" min="0" step="100" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <span style={{ color: 'var(--ink-3)' }}>₺</span>
            </span>
          </label>

          <div style={{ marginTop: 16 }}>
            <span className="field__label">{t('tax.calcRate')}</span>
            <div className="seg" style={{ marginTop: 8, width: '100%' }}>
              {VAT_RATES.map((r) => (
                <button key={r.key} className={rate === r.value ? 'is-active' : ''} onClick={() => setRate(r.value)} style={{ flex: 1 }}>
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          <div className="kdv-rows" style={{ marginTop: 22 }}>
            <div className="kdv-row">
              <span>{t('tax.calcNet')}</span>
              <strong className="tnum">{cur(calc.net)}</strong>
            </div>
            <div className="kdv-row">
              <span>{t('tax.calcVat')}</span>
              <strong className="tnum" style={{ color: 'var(--ink)' }}>{cur(calc.vat)}</strong>
            </div>
            <div className="kdv-row kdv-row--total">
              <span>{t('tax.calcGross')}</span>
              <strong className="tnum">{cur(calc.gross)}</strong>
            </div>
          </div>

          <p className="score-reco" style={{ marginTop: 20 }}>
            {lang === 'en'
              ? 'Official 2026 rates: VAT 20/10/1%, corporate 25%, rent withholding 20%.'
              : 'Resmi 2026 oranları: KDV %20/%10/%1, kurumlar %25, kira stopajı %20.'}
          </p>
        </motion.section>

        {/* Obligations */}
        <motion.section className="panel dash-invoices" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.14 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><FileText size={15} strokeWidth={1.9} />{t('tax.filingsTitle')}</div>
              <div className="panel-sub">{t('tax.timelineSub')}</div>
            </div>
            <CalendarClock size={20} color="var(--ink-4)" />
          </div>

          {taxObligations.length ? (
            <div className="tbl-scroll">
              <table className="tbl">
              <thead>
                <tr>
                  <th>{t('tax.colType')}</th>
                  <th>{t('tax.colPeriod')}</th>
                  <th>{t('invoices.colDue')}</th>
                  <th className="num">{t('tax.colAmount')}</th>
                  <th>{t('tax.colStatus')}</th>
                  <th style={{ textAlign: 'right' }}>{t('common.action')}</th>
                </tr>
              </thead>
              <tbody>
                {taxObligations.map((o) => {
                  const overdue = o.status !== 'filed' && o.dueDate < new Date().toISOString().slice(0, 10)
                  return (
                    <tr key={o.id}>
                      <td className="strong">{o.name}</td>
                      <td className="mono" style={{ fontSize: 12.5 }}>{o.period}</td>
                      <td>{formatDate(o.dueDate, lang)}</td>
                      <td className="num strong tnum">{cur(o.amount)}</td>
                      <td>
                        <Badge tone={o.status === 'filed' ? 'green' : overdue ? 'red' : 'amber'}>
                          {o.status === 'filed' ? t('tax.stFiled') : overdue ? t('tax.stDue') : t('tax.stDraft')}
                        </Badge>
                      </td>
                      <td>
                        <div className="row-actions">
                          {o.status !== 'filed' && (
                            <button className="icon-btn" onClick={() => markFiled(o)} disabled={busyId === o.id} title={t('tax.stFiled')}>
                              <CheckCircle2 size={15} strokeWidth={1.9} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              </table>
            </div>
          ) : (
            <div className="chart-empty" style={{ height: 140, margin: '0 22px' }}>{t('common.none')}</div>
          )}
        </motion.section>

        {/* Statutory calendar from the backend */}
        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.2 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><CalendarClock size={15} strokeWidth={1.9} />{t('tax.timelineTitle')}</div>
              <div className="panel-sub">
                {lang === 'en' ? 'Statutory deadlines (2026 calendar)' : 'Yasal son tarihler (2026 takvimi)'}
              </div>
            </div>
          </div>
          <div className="tax-timeline">
            {(taxSummary?.deadlines ?? dashboard?.deadlines ?? []).map((d) => (
              <div className="tax-timeline__row" key={`${d.type}-${d.due_date}`}>
                <div className="tax-timeline__date">
                  <span className="tax-timeline__day">{new Date(d.due_date).getDate()}</span>
                  <span className="tax-timeline__mon">{MONTHS[lang][new Date(d.due_date).getMonth()]}</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 13.5 }}>{d.name}</div>
                  <div className="tnum" style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>
                    {d.days_remaining} {t('tax.days')}
                  </div>
                </div>
                <Badge tone={d.is_due_soon ? 'red' : 'gray'}>
                  {d.is_due_soon ? t('tax.stDue') : t('tax.stDraft')}
                </Badge>
              </div>
            ))}
            {!(taxSummary?.deadlines ?? dashboard?.deadlines ?? []).length && (
              <div className="chart-empty" style={{ height: 140 }}>{t('common.offline')}</div>
            )}
          </div>
        </motion.section>
      </div>
    </div>
  )
}

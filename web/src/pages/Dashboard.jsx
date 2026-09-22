import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  ArrowUpRight,
  CalendarClock,
  CalendarDays,
  Clock,
  CreditCard,
  Gauge,
  Landmark,
  LayoutGrid,
  LineChart,
  PieChart,
  Plus,
  ReceiptText,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useData } from '../context/DataContext.jsx'
import { formatCurrency, formatDate, MONTHS } from '../lib/format.js'
import { isOverdue } from '../lib/analytics.js'
import { FigureBand } from '../components/ui/Figures.jsx'
import Badge from '../components/ui/Badge.jsx'
import TrendChart from '../components/charts/TrendChart.jsx'
import DonutChart from '../components/charts/DonutChart.jsx'
import ForecastChart from '../components/charts/ForecastChart.jsx'
import ScoreGauge from '../components/charts/ScoreGauge.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import PageSkeleton from '../components/ui/PageSkeleton.jsx'

const STATUS_TONE = { paid: 'green', pending: 'amber', overdue: 'red' }
const SEVERITY_TONE = { high: 'red', medium: 'amber', low: 'gray' }

// The card is a prompt to act, not a register. Four rows keep it the height of
// the score panel beside it; the rest are counted off underneath.
const ALERTS_SHOWN = 4

// The cash-flow card's range switch. Twelve months is the default because the
// seasonality is the point; the shorter windows are for reading a trend.
const RANGES = [
  { key: 'm3', months: 3 },
  { key: 'm6', months: 6 },
  { key: 'm12', months: 12 },
]

// Stable colours per category so the donut and legend never re-shuffle.
const CATEGORY_COLORS = [
  'var(--d1)',
  'var(--d2)',
  'var(--d3)',
  'var(--d4)',
  'var(--d5)',
  'var(--d6)',
  'var(--d7)',
  'var(--d8)',
]

/**
 * The day's three counts, as a strip across the page.
 *
 * This was a card in a fixed 340px rail down the right-hand side. The rail
 * cost every chart beside it a third of its width — and of its four cards,
 * two only repeated links the navigation already carries and one was a
 * second way to reach the assistant. What was worth keeping is this: how
 * much falls due today, what is coming, and what is already late.
 */
function TodayStrip({ counts, onOpen, t }) {
  const items = [
    { key: 'today', icon: CalendarDays, value: counts.today },
    { key: 'upcoming', icon: Clock, value: counts.upcoming },
    { key: 'overdue', icon: TriangleAlert, value: counts.overdue, alert: counts.overdue > 0 },
  ]
  return (
    <div className="today-strip">
      {items.map(({ key, icon: Icon, value, alert }) => (
        <button
          key={key}
          className={`today-strip__item${alert ? ' is-alert' : ''}`}
          onClick={onOpen}
        >
          <Icon size={16} strokeWidth={1.9} />
          <span className="today-strip__label">{t(`dashboard.rail.${key}`)}</span>
          <span className="today-strip__count tnum">{value}</span>
        </button>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { t, lang } = useLang()
  const { company } = useAuth()
  const navigate = useNavigate()
  const { dashboard, score, forecast, compliance, invoices, loading, isEmpty, apiOnline, computing, refresh } = useData()

  const [range, setRange] = useState('m12')

  const cur = (v, o) => formatCurrency(v, lang, o)
  const compact = (v) => formatCurrency(v, lang, { compact: true })

  const monthly = dashboard?.monthly ?? []
  const kpis = dashboard?.kpis

  const monthLabels = useMemo(
    () => monthly.map((m) => MONTHS[lang][Number(m.month.slice(5, 7)) - 1]),
    [monthly, lang],
  )

  // The range switch trims the tail of the same series rather than
  // refetching: the dashboard response already carries twelve months.
  const windowed = useMemo(() => {
    const months = RANGES.find((r) => r.key === range)?.months ?? 12
    return { data: monthly.slice(-months), labels: monthLabels.slice(-months) }
  }, [monthly, monthLabels, range])

  // Net profit is what the month comes down to, so it is the one figure the
  // page leads with; the other three are context beside it.
  const figures = useMemo(() => {
    if (!kpis) return null
    return {
      hero: {
        icon: TrendingUp,
        label: t('dashboard.kpiProfit'),
        value: kpis.profit,
        delta: kpis.profit_delta,
        positive: kpis.profit_delta >= 0,
        spark: monthly.map((m) => m.profit),
      },
      rows: [
        { icon: Wallet, label: t('dashboard.kpiRevenue'), value: kpis.revenue, delta: kpis.revenue_delta, positive: kpis.revenue_delta >= 0 },
        { icon: CreditCard, label: t('dashboard.kpiExpense'), value: kpis.expense, delta: kpis.expense_delta, positive: kpis.expense_delta <= 0 },
        { icon: Landmark, label: t('dashboard.kpiTax'), value: kpis.tax, delta: kpis.tax_delta, positive: kpis.tax_delta <= 0 },
      ],
    }
  }, [kpis, monthly, t])

  // Only the largest categories get their own slice, but the tail is rolled
  // into "other" rather than dropped — the donut's centre is labelled as the
  // month's total expense, so it has to actually be the total.
  const donutData = useMemo(() => {
    const all = dashboard?.expense_breakdown ?? []
    const TOP = 7
    const head = all.slice(0, TOP)
    const tail = all.slice(TOP)
    const slices = [...head]
    if (tail.length) {
      slices.push({ key: 'other', value: tail.reduce((s, e) => s + e.value, 0) })
    }
    return slices.map((e, i) => ({
      ...e,
      label: t(`dashboard.cat.${e.key}`),
      color: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
    }))
  }, [dashboard?.expense_breakdown, t])

  // Alerts name an invoice by id; the row shows its number so the user knows
  // which document is meant before clicking through.
  const invoiceById = useMemo(
    () => new Map(invoices.map((i) => [i.id, i])),
    [invoices],
  )

  const recent = useMemo(
    () =>
      [...invoices]
        .sort((a, b) => String(b.issueDate).localeCompare(String(a.issueDate)))
        .slice(0, 5),
    [invoices],
  )

  // What the rail counts. All three are read off the workspace the page
  // already holds — the rail is a shortcut to work, not another fetch.
  const todayIso = new Date().toISOString().slice(0, 10)
  const rail = useMemo(() => {
    const open = invoices.filter((i) => i.status !== 'paid')
    return {
      today: open.filter((i) => i.dueDate === todayIso).length,
      upcoming: open.filter((i) => i.dueDate && i.dueDate > todayIso).length,
      overdue: open.filter((i) => isOverdue(i)).length,
    }
  }, [invoices, todayIso])

  // The banner calls out the nearest statutory deadline, and only while it is
  // actually close — a permanent banner is furniture, not a warning.
  const urgent = (dashboard?.deadlines ?? []).find((d) => d.is_due_soon)

  if (loading) return <PageSkeleton />
  if (isEmpty) return <EmptyState />

  return (
    <div className="page">
      {/* No greeting. "Welcome back" over "your financial pulse at a glance"
          is a banner that says nothing and costs the first screenful — the
          rail already says which room this is, and the cards name
          themselves. What stays is the date, the company and the actions. */}
      <div className="page-head page-head-row">
        <div>
          <div className="page-eyebrow">
            <LayoutGrid size={14} strokeWidth={1.9} />
            <span className="label">
              {formatDate(new Date(), lang)} · {company?.name || '—'}
            </span>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn--ghost btn--sm" onClick={refresh} disabled={computing}>
            <RefreshCw size={14} strokeWidth={1.9} className={computing ? 'spin' : ''} />
            {computing ? t('common.computing') : t('common.refresh')}
          </button>
          <button className="btn btn--primary btn--sm" onClick={() => navigate('/app/invoices')}>
            {t('invoices.upload')}
          </button>
        </div>
      </div>

      {!apiOnline && (
        <div className="banner banner--warn">
          <span className="banner__icon"><TriangleAlert size={17} strokeWidth={2} /></span>
          <span className="banner__text">
            <strong>{t('common.offline')}</strong> — {t('common.offlineHint')}
          </span>
        </div>
      )}

      {urgent && (
        <div className="banner banner--warn">
          <span className="banner__icon"><TriangleAlert size={17} strokeWidth={2} /></span>
          <span className="banner__text">
            <strong>{urgent.name}</strong>{' '}
            {urgent.days_remaining <= 0
              ? t('dashboard.deadlineBannerToday')
              : t('dashboard.deadlineBanner').replace('{days}', urgent.days_remaining)}
          </span>
          <button className="btn btn--go btn--sm" onClick={() => navigate('/app/tax')}>
            {t('dashboard.deadlineBtn')}
          </button>
        </div>
      )}

      {figures && (
        // Exact figures below a million: a business owner reads these as money,
        // and "₺218 B" hides ₺218.430. Compact only when it would overflow.
        <FigureBand
          hero={figures.hero}
          rows={figures.rows}
          format={(v) => cur(v, { compact: Math.abs(v) >= 1e6 })}
          vsLabel={t('common.vsLast')}
        />
      )}

        {/* Assistant insight — generated from this month's actual figures */}
        <motion.section className="insight-card" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.34 }}>
          <div className="insight-card__glow" />
          <div className="insight-card__head">
            <span className="insight-card__icon">
              <Sparkles size={17} strokeWidth={1.9} />
            </span>
            <span>{t('dashboard.insightTitle')}</span>
            <Badge tone="gray" dot={false}>{t('common.ai')}</Badge>
          </div>
          <p className="insight-card__body">{dashboard?.insight || t('dashboard.insightBody')}</p>
          <button className="insight-card__action" onClick={() => navigate('/app/assistant')}>
            {t('dashboard.insightAction')}
            <ArrowRight size={15} strokeWidth={1.9} />
          </button>
        </motion.section>

      {/* The day's work, as a strip. It was a card in a 340px rail down
          the right, which cost every chart beside it a third of its
          width — and two of that rail's four cards only repeated links
          the navigation already carries. */}
      <TodayStrip counts={rail} onOpen={() => navigate('/app/invoices')} t={t} />

      {/* The cash-flow chart runs the full width: at half of it the month
          labels and the axis figures are too small to read, which is the
          whole job of the card. */}
        {/* Cash flow */}
        <motion.section className="panel dash-cashflow" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><TrendingUp size={15} strokeWidth={1.9} />{t('dashboard.cashflowTitle')}</div>
              <div className="panel-sub">{t('dashboard.cashflowSub')}</div>
            </div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div className="seg" role="group">
                {RANGES.map((r) => (
                  <button
                    key={r.key}
                    type="button"
                    className={range === r.key ? 'is-active' : undefined}
                    aria-pressed={range === r.key}
                    onClick={() => setRange(r.key)}
                  >
                    {t(`dashboard.range.${r.key}`)}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <TrendChart
            data={windowed.data}
            labels={windowed.labels}
            keys={['income', 'expense']}
            seriesNames={[t('dashboard.income'), t('dashboard.expense')]}
            formatValue={(v) => cur(v)}
            formatAxis={compact}
            height={360}
          />
        </motion.section>

      <div className="dash-cols">
        <div className="dash-col">
          {/* Muhai Score */}
          <motion.section className="panel dash-score" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.38 }}>
            <div className="panel-head">
              <div>
                <div className="panel-title"><Gauge size={15} strokeWidth={1.9} />Muhai Score</div>
                <div className="panel-sub">
                  {score
                    ? `${lang === 'en' ? 'Cash runway' : 'Nakit pisti'} · ${Math.round(score.cash_runway_days)} ${lang === 'en' ? 'days' : 'gün'}`
                    : t('common.computing')}
                </div>
              </div>
            </div>
            {score ? (
              <div className="score-row">
                <ScoreGauge score={score.total_score} rating={score.rating} label="/ 100" />
                <ul className="score-cats">
                  {score.categories
                    .slice()
                    .sort((a, b) => a.score - b.score)
                    .slice(0, 4)
                    .map((c) => (
                      <li key={c.key}>
                        <span className="score-cats__label">{c.label}</span>
                        <span className="score-cats__bar">
                          <motion.i
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.round(c.score * 100)}%` }}
                            transition={{ duration: 0.8, delay: 0.4 }}
                            style={{
                              background:
                                c.score > 0.75 ? 'var(--ok)' : c.score > 0.45 ? 'var(--warn)' : 'var(--stop)',
                            }}
                          />
                        </span>
                        <span className="score-cats__val tnum">{Math.round(c.score * 100)}</span>
                      </li>
                    ))}
                </ul>
              </div>
            ) : (
              <div className="chart-empty" style={{ height: 160 }}>{t('common.offline')}</div>
            )}
            {score?.recommendations?.length ? (
              <p className="score-reco">{score.recommendations[0]}</p>
            ) : null}
          </motion.section>
          {/* Tax calendar */}
          <motion.section className="panel" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.46 }}>
            <div className="panel-head">
              <div>
                <div className="panel-title"><CalendarClock size={15} strokeWidth={1.9} />{t('dashboard.taxWidgetTitle')}</div>
                <div className="panel-sub">{t('dashboard.taxWidgetSub')}</div>
              </div>
            </div>
            <div className="tax-timeline">
              {(dashboard?.deadlines ?? []).map((it) => (
                <div className="tax-timeline__row" key={`${it.type}-${it.due_date}`}>
                  <div className="tax-timeline__date">
                    <span className="tax-timeline__day">{new Date(it.due_date).getDate()}</span>
                    <span className="tax-timeline__mon">{MONTHS[lang][new Date(it.due_date).getMonth()]}</span>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: 13.5 }}>{it.name}</div>
                    <div className="tnum" style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>
                      {it.days_remaining} {lang === 'en' ? 'days left' : 'gün kaldı'}
                    </div>
                  </div>
                  <Badge tone={it.is_due_soon ? 'red' : 'amber'}>
                    {it.is_due_soon ? t('tax.stDue') : t('tax.stDraft')}
                  </Badge>
                </div>
              ))}
              {!dashboard?.deadlines?.length && <div className="chart-empty" style={{ height: 120 }}>{t('common.offline')}</div>}
            </div>
          </motion.section>
        </div>
        <div className="dash-col">
          {/* Expense split */}
          <motion.section className="panel" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.28 }}>
            <div className="panel-head">
              <div>
                <div className="panel-title"><PieChart size={15} strokeWidth={1.9} />{t('dashboard.breakdownTitle')}</div>
                <div className="panel-sub">{t('dashboard.breakdownSub')}</div>
              </div>
            </div>
            {donutData.length ? (
              <>
                <DonutChart data={donutData} centerLabel={t('dashboard.kpiExpense')} formatValue={compact} />
                <div className="legend" style={{ marginTop: 22 }}>
                  {donutData.map((d) => (
                    <div className="legend__row" key={d.key}>
                      <span className="legend__left">
                        <span className="legend__swatch" style={{ background: d.color }} />
                        {d.label}
                      </span>
                      <span className="legend__val">{cur(d.value)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="chart-empty" style={{ height: 200 }}>{t('common.none')}</div>
            )}
          </motion.section>
          {/* Compliance & risk — rule checks over the same snapshot. Nothing is
              stored, so an alert disappears as soon as the invoice is corrected. */}
          <motion.section className="panel dash-compliance" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.36 }}>
            <div className="panel-head">
              <div>
                <div className="panel-title"><ShieldAlert size={15} strokeWidth={1.9} />{t('dashboard.compliance.title')}</div>
                <div className="panel-sub">{t('dashboard.compliance.sub')}</div>
              </div>
              {compliance?.total ? (
                <Badge tone={compliance.high ? 'red' : 'amber'}>{compliance.total}</Badge>
              ) : (
                <ShieldCheck size={18} strokeWidth={1.9} color={compliance ? 'var(--ok)' : 'var(--ink-4)'} />
              )}
            </div>

            {!compliance ? (
              <div className="chart-empty" style={{ height: 120 }}>
                {t('dashboard.compliance.offline')}
              </div>
            ) : compliance.total === 0 ? (
              <div className="alert-clean">
                <ShieldCheck size={18} strokeWidth={1.9} />
                <span>{t('dashboard.compliance.clean')}</span>
              </div>
            ) : (
              <>
                <ul className="alert-list">
                  {compliance.alerts.slice(0, ALERTS_SHOWN).map((a, i) => {
                    const invoice = a.ref_id ? invoiceById.get(a.ref_id) : null
                    return (
                      <li className={`alert-row alert-row--${a.severity}`} key={`${a.type}-${a.ref_id ?? ''}-${i}`}>
                        <span className="alert-row__mark" />
                        <div className="alert-row__body">
                          <div className="alert-row__head">
                            <ShieldAlert size={14} strokeWidth={1.9} />
                            <span className="alert-row__type">{t(`dashboard.compliance.type.${a.type}`)}</span>
                            <Badge tone={SEVERITY_TONE[a.severity]}>
                              {t(`dashboard.compliance.sev.${a.severity}`)}
                            </Badge>
                          </div>
                          <p className="alert-row__text">{a.description}</p>
                          {invoice && (
                            <button className="link-btn" onClick={() => navigate('/app/invoices')}>
                              {t('dashboard.compliance.openInvoice')}
                              {invoice.number && <span className="alert-row__ref">· {invoice.number}</span>}
                              <ArrowUpRight size={13} strokeWidth={1.9} />
                            </button>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
                {compliance.total > ALERTS_SHOWN && (
                  <p className="alert-more">
                    +{compliance.total - ALERTS_SHOWN} {t('dashboard.compliance.more')}
                  </p>
                )}
              </>
            )}
          </motion.section>
        </div>
      </div>

      {/* Prophet forecast */}
      <motion.section className="panel dash-forecast" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.42 }}>
        <div className="panel-head">
          <div>
            <div className="panel-title">
              <LineChart size={15} strokeWidth={1.9} />
              {lang === 'en' ? '30-day cash-flow forecast' : '30 günlük nakit akışı tahmini'}
            </div>
            <div className="panel-sub">
              {forecast
                ? `${forecast.engine === 'prophet' ? 'Prophet' : lang === 'en' ? 'Moving average' : 'Hareketli ortalama'} · ${forecast.history_points} ${lang === 'en' ? 'points' : 'veri noktası'} · %80 ${lang === 'en' ? 'interval' : 'güven aralığı'}`
                : t('common.computing')}
            </div>
          </div>
          {forecast && (
            <span className={`delta ${forecast.projected_net >= 0 ? 'delta--pos' : 'delta--neg'}`}>
              {cur(forecast.projected_net, { compact: true })}
            </span>
          )}
        </div>
        <ForecastChart
          points={forecast?.points ?? []}
          formatValue={(v) => cur(v)}
          formatAxis={compact}
          formatDate={(d) => {
            const dt = new Date(d)
            return `${dt.getDate()} ${MONTHS[lang][dt.getMonth()]}`
          }}
          emptyLabel={t('common.offline')}
          seriesLabel={t('dashboard.forecastSeries')}
          bandLabel={t('dashboard.forecastBand')}
          rangeLabel={t('dashboard.forecastRange')}
          height={270}
        />
      </motion.section>

      {/* Recent invoices */}
      <motion.section className="panel dash-invoices" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.5 }}>
        <div className="panel-head">
          <div>
            <div className="panel-title"><ReceiptText size={15} strokeWidth={1.9} />{t('dashboard.recentTitle')}</div>
            <div className="panel-sub">{t('dashboard.recentSub')}</div>
          </div>
          <button className="link-btn" onClick={() => navigate('/app/invoices')}>
            {t('common.viewAll')} <ArrowUpRight size={14} strokeWidth={1.9} />
          </button>
        </div>
        <div className="tbl-scroll">
          <table className="tbl">
          <thead>
            <tr>
              <th>{t('invoices.colVendor')}</th>
              <th>{t('invoices.colNo')}</th>
              <th>{t('invoices.colDate')}</th>
              <th className="num">{t('invoices.colAmount')}</th>
              <th>{t('invoices.colStatus')}</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((inv) => (
              <tr key={inv.id}>
                <td className="strong">{inv.vendor}</td>
                <td className="mono" style={{ fontSize: 12.5 }}>{inv.number}</td>
                <td>{formatDate(inv.issueDate, lang)}</td>
                <td className="num strong">{cur(inv.amount)}</td>
                <td>
                  <Badge tone={STATUS_TONE[inv.status]}>
                    {t(`invoices.st${inv.status[0].toUpperCase()}${inv.status.slice(1)}`)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
          </table>
        </div>
      </motion.section>

      <button
        className="fab"
        onClick={() => navigate('/app/invoices')}
        aria-label={t('dashboard.newInvoice')}
        title={t('dashboard.newInvoice')}
      >
        <Plus size={24} strokeWidth={2.2} />
      </button>
    </div>
  )
}

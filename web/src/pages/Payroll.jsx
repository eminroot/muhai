import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, PieChart, PiggyBank, Plus, Trash2, Users, X } from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useData } from '../context/DataContext.jsx'
import { formatCurrency, formatDate } from '../lib/format.js'
import { COLLECTIONS, addItem, removeItem } from '../lib/db.js'
import DonutChart from '../components/charts/DonutChart.jsx'
import PageSkeleton from '../components/ui/PageSkeleton.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'

const emptyEmployee = () => ({
  name: '',
  role: '',
  grossSalary: 0,
  startDate: new Date().toISOString().slice(0, 10),
  sgkNo: '',
})

export default function Payroll() {
  const { t, lang } = useLang()
  const { companyId, employees, payroll, loading, isEmpty, apiOnline } = useData()
  const cur = (v) => formatCurrency(v, lang)
  const compact = (v) => formatCurrency(v, lang, { compact: true })

  const [modal, setModal] = useState(null)
  const [busyId, setBusyId] = useState(null)

  // The API returns payslips in the order employees were sent, so joining by
  // index would break the moment the list is reordered. Match on name instead.
  const rows = useMemo(() => {
    const slips = new Map((payroll?.payslips ?? []).map((p) => [p.name, p]))
    return employees.map((e) => ({ employee: e, slip: slips.get(e.name) || null }))
  }, [employees, payroll])

  const costSplit = useMemo(() => {
    if (!payroll) return []
    const net = payroll.total_net
    const sgkEmployee = payroll.payslips.reduce((s, p) => s + p.sgk_employee + p.unemployment_employee, 0)
    const sgkEmployer = payroll.payslips.reduce((s, p) => s + p.sgk_employer + p.unemployment_employer, 0)
    const incomeTax = payroll.payslips.reduce((s, p) => s + p.income_tax, 0)
    const stamp = payroll.payslips.reduce((s, p) => s + p.stamp_tax, 0)
    return [
      { key: 'net', label: t('payroll.net'), value: Math.round(net), color: 'var(--d1)' },
      { key: 'sgkE', label: t('payroll.sgkEmployee'), value: Math.round(sgkEmployee), color: 'var(--d2)' },
      { key: 'sgkR', label: t('payroll.sgkEmployer'), value: Math.round(sgkEmployer), color: 'var(--d3)' },
      { key: 'tax', label: t('payroll.incomeTax'), value: Math.round(incomeTax), color: 'var(--d4)' },
      { key: 'stamp', label: t('payroll.stampTax'), value: Math.round(stamp), color: 'var(--d5)' },
    ].filter((d) => d.value > 0)
  }, [payroll, t])

  async function handleDelete(employee) {
    if (!window.confirm(`${employee.name} — ${t('common.delete')}?`)) return
    setBusyId(employee.id)
    try {
      await removeItem(COLLECTIONS.employees, employee.id)
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
            <Users size={14} strokeWidth={1.9} />
            <span className="label">{t('nav.payroll')}</span>
          </div>
          <h1 className="page-title">{t('payroll.title')}</h1>
          <p className="page-sub">{t('payroll.subtitle')}</p>
        </div>
        <button className="btn btn--primary btn--sm" onClick={() => setModal(emptyEmployee())}>
          <Plus size={14} strokeWidth={1.9} /> {lang === 'en' ? 'Add employee' : 'Çalışan ekle'}
        </button>
      </div>

      {!apiOnline && (
        <div className="notice notice--warn" style={{ marginBottom: 18 }}>
          <strong>{t('common.offline')}</strong> — {t('common.offlineHint')}
        </div>
      )}

      <div className="mini-stats" style={{ marginBottom: 20 }}>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('payroll.kpiEmployees')}</div>
          <div className="mini-stats__value tnum">{employees.length}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('payroll.kpiGross')}</div>
          <div className="mini-stats__value tnum">{payroll ? cur(payroll.total_gross) : '—'}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{t('payroll.kpiNet')}</div>
          <div className="mini-stats__value tnum">{payroll ? cur(payroll.total_net) : '—'}</div>
        </div>
        <div className="mini-stats__item">
          <div className="mini-stats__label">{lang === 'en' ? 'Employer cost' : 'İşveren maliyeti'}</div>
          <div className="mini-stats__value tnum">{payroll ? cur(payroll.total_employer_cost) : '—'}</div>
        </div>
      </div>

      <div className="dash-grid">
        <motion.section className="panel dash-cashflow" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><Users size={15} strokeWidth={1.9} />{t('payroll.tableTitle')}</div>
              <div className="panel-sub">
                {lang === 'en'
                  ? '2026 rates: SGK, income tax and stamp duty'
                  : '2026 oranlarıyla: SGK, gelir vergisi ve damga'}
              </div>
            </div>
            <Users size={20} color="var(--ink-4)" />
          </div>

          {employees.length ? (
            <div className="tbl-scroll">
              <table className="tbl">
              <thead>
                <tr>
                  <th>{t('payroll.colName')}</th>
                  <th>{t('payroll.colRole')}</th>
                  <th className="num">{t('payroll.colGross')}</th>
                  <th className="num">{t('payroll.colDeductions')}</th>
                  <th className="num">{t('payroll.colNet')}</th>
                  <th className="num">{lang === 'en' ? 'Leave' : 'İzin'}</th>
                  <th style={{ textAlign: 'right' }}>{t('common.action')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ employee, slip }) => (
                  <tr key={employee.id}>
                    <td className="strong">
                      {employee.name}
                      <div style={{ fontSize: 11.5, color: 'var(--ink-4)' }}>
                        {employee.startDate ? formatDate(employee.startDate, lang) : ''}
                      </div>
                    </td>
                    <td>{employee.role || '—'}</td>
                    <td className="num tnum">{cur(employee.grossSalary)}</td>
                    <td className="num tnum" style={{ color: 'var(--stop)' }}>
                      {slip ? `−${cur(slip.total_deductions)}` : '—'}
                    </td>
                    <td className="num tnum strong">{slip ? cur(slip.net_salary) : '—'}</td>
                    <td className="num tnum">{slip ? `${slip.annual_leave_days} ${lang === 'en' ? 'd' : 'gün'}` : '—'}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-btn icon-btn--danger"
                          onClick={() => handleDelete(employee)}
                          disabled={busyId === employee.id}
                          title={t('common.delete')}
                        >
                          <Trash2 size={14} strokeWidth={1.9} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              </table>
            </div>
          ) : (
            <div className="chart-empty" style={{ height: 180 }}>{t('common.none')}</div>
          )}
        </motion.section>

        <motion.section className="panel" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.1 }}>
          <div className="panel-head">
            <div>
              <div className="panel-title"><PieChart size={15} strokeWidth={1.9} />{t('payroll.breakdownTitle')}</div>
              <div className="panel-sub">{t('payroll.breakdownSub')}</div>
            </div>
          </div>
          {costSplit.length ? (
            <>
              <DonutChart
                data={costSplit}
                centerLabel={lang === 'en' ? 'Employer cost' : 'İşveren maliyeti'}
                formatValue={compact}
              />
              <div className="legend" style={{ marginTop: 22 }}>
                {costSplit.map((d) => (
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
            <div className="chart-empty" style={{ height: 220 }}>{t('common.offline')}</div>
          )}
        </motion.section>

        {payroll?.payslips?.length > 0 && (
          <motion.section className="panel dash-forecast" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.16 }}>
            <div className="panel-head">
              <div>
                <div className="panel-title">
                  <PiggyBank size={15} strokeWidth={1.9} />
                  {lang === 'en' ? 'Severance provision' : 'Kıdem tazminatı karşılığı'}
                </div>
                <div className="panel-sub">
                  {lang === 'en'
                    ? 'Accrued liability if every contract ended today'
                    : 'Tüm sözleşmeler bugün sona erseydi doğacak yükümlülük'}
                </div>
              </div>
              <strong className="tnum" style={{ fontFamily: 'var(--font-display)', fontSize: 22 }}>
                {cur(payroll.payslips.reduce((s, p) => s + p.severance_estimate, 0))}
              </strong>
            </div>
            <div className="legend">
              {payroll.payslips.map((p) => (
                <div className="legend__row" key={p.name}>
                  <span className="legend__left">
                    {p.name}
                    <span style={{ color: 'var(--ink-4)', fontSize: 12 }}>
                      · {p.tenure_years.toFixed(1)} {lang === 'en' ? 'yrs' : 'yıl'}
                    </span>
                  </span>
                  <span className="legend__val">{cur(p.severance_estimate)}</span>
                </div>
              ))}
            </div>
          </motion.section>
        )}
      </div>

      {modal && (
        <EmployeeModal
          employee={modal}
          onClose={() => setModal(null)}
          onSave={async (data) => {
            await addItem(COLLECTIONS.employees, data)
            setModal(null)
          }}
        />
      )}
    </div>
  )
}

function EmployeeModal({ employee, onClose, onSave }) {
  const { t, lang } = useLang()
  const [form, setForm] = useState(employee)
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
        role: form.role.trim(),
        grossSalary: Number(form.grossSalary) || 0,
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
          <div className="modal__title">{lang === 'en' ? 'Add employee' : 'Çalışan ekle'}</div>
          <button className="icon-btn" onClick={onClose} aria-label={t('common.close')}>
            <X size={16} strokeWidth={1.9} />
          </button>
        </div>
        <form onSubmit={submit}>
          <div className="modal__body">
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('payroll.colName')}</span>
                <span className="field__wrap">
                  <input value={form.name} onChange={set('name')} required />
                </span>
              </label>
              <label className="field">
                <span className="field__label">{t('payroll.colRole')}</span>
                <span className="field__wrap">
                  <input value={form.role} onChange={set('role')} />
                </span>
              </label>
            </div>
            <div className="field-row">
              <label className="field">
                <span className="field__label">{t('payroll.colGross')}</span>
                <span className="field__wrap">
                  <input type="number" min="0" step="100" value={form.grossSalary} onChange={set('grossSalary')} required />
                  <span style={{ color: 'var(--ink-3)' }}>₺</span>
                </span>
              </label>
              <label className="field">
                <span className="field__label">{lang === 'en' ? 'Start date' : 'İşe giriş'}</span>
                <span className="field__wrap">
                  <input type="date" value={form.startDate} onChange={set('startDate')} />
                </span>
              </label>
            </div>
            <label className="field">
              <span className="field__label">SGK No</span>
              <span className="field__wrap">
                <input value={form.sgkNo} onChange={set('sgkNo')} inputMode="numeric" />
              </span>
            </label>
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

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bell,
  Gauge,
  LogOut,
  Search,
  Settings as SettingsIcon,
  WifiOff,
} from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { useData } from '../../context/DataContext.jsx'
import { formatCurrency, formatDate } from '../../lib/format.js'
import { isOverdue } from '../../lib/analytics.js'
import LanguageToggle from './LanguageToggle.jsx'
import Logo from '../ui/Logo.jsx'

function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return 'MU'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

/**
 * Identity on the left, the facts that must stay visible on the right.
 *
 * There is no navigation here on purpose — it all lives in the dock, which is
 * what hands the full width of the window back to the work.
 */
export default function Topbar() {
  const { t, lang } = useLang()
  const navigate = useNavigate()
  const { profile, company, user, logout } = useAuth()
  const { invoices, products, score, apiOnline } = useData()

  const [query, setQuery] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const rootRef = useRef(null)

  // One outside-click listener closes whichever popover is open.
  useEffect(() => {
    if (!menuOpen && !notifOpen) return
    const onDown = (e) => {
      if (!rootRef.current?.contains(e.target)) {
        setMenuOpen(false)
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [menuOpen, notifOpen])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    const inv = invoices
      .filter((i) => `${i.vendor} ${i.number}`.toLowerCase().includes(q))
      .slice(0, 5)
      .map((i) => ({
        key: `inv-${i.id}`,
        label: i.vendor,
        meta: `${i.number} · ${formatCurrency(i.amount, lang)}`,
        to: '/app/invoices',
      }))
    const prod = products
      .filter((p) => `${p.name} ${p.sku || ''}`.toLowerCase().includes(q))
      .slice(0, 4)
      .map((p) => ({
        key: `prd-${p.id}`,
        label: p.name,
        meta: `${p.stock} ${p.unit || ''}`.trim(),
        to: '/app/inventory',
      }))
    return [...inv, ...prod]
  }, [query, invoices, products, lang])

  const alerts = useMemo(() => {
    const overdue = invoices.filter((i) => isOverdue(i))
    const low = products.filter((p) => (p.stock ?? 0) <= (p.minStock ?? 0))
    return [
      ...overdue.map((i) => ({
        key: `o-${i.id}`,
        tone: 'stop',
        title: lang === 'en' ? 'Invoice overdue' : 'Vadesi geçen fatura',
        body: `${i.vendor} · ${formatCurrency(i.amount, lang)} · ${formatDate(i.dueDate, lang)}`,
        to: '/app/invoices',
      })),
      ...low.map((p) => ({
        key: `l-${p.id}`,
        tone: 'warn',
        title: lang === 'en' ? 'Low stock' : 'Kritik stok',
        body: `${p.name} · ${p.stock}/${p.minStock}`,
        to: '/app/inventory',
      })),
    ]
  }, [invoices, products, lang])

  const displayName = profile?.displayName || user?.displayName || user?.email || 'Muhai'

  function go(to) {
    setQuery('')
    setNotifOpen(false)
    setMenuOpen(false)
    navigate(to)
  }

  return (
    <header className="topbar" ref={rootRef}>
      <Link to="/app" className="brand">
        <span className="brand-glyph">
          <Logo size={15} />
        </span>
        <span>
          <span className="brand-name">Muhai</span>
          <span className="brand-tag">{t('common.tagline')}</span>
        </span>
      </Link>

      <div className="topbar__search-wrap">
        <label className="topbar__search">
          <Search size={15} strokeWidth={1.9} />
          <input
            placeholder={t('common.search')}
            aria-label={t('common.search')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <AnimatePresence>
          {results.length > 0 && (
            <motion.div
              className="popover popover--search"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.16, ease: [0.22, 0.8, 0.3, 1] }}
            >
              {results.map((r) => (
                <button key={r.key} className="popover__row" onClick={() => go(r.to)}>
                  <span className="grow">
                    <span className="popover__title">{r.label}</span>
                    <span className="popover__meta num">{r.meta}</span>
                  </span>
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="topbar-meta">
        {!apiOnline && (
          <span className="pill warn pill--icon" title={`${t('common.offline')} — ${t('common.offlineHint')}`}>
            <WifiOff size={12} strokeWidth={1.9} />
            <span className="pill__text">{t('common.offline')}</span>
          </span>
        )}

        {score && (
          <span className="chip optional" title="Muhai Score">
            <Gauge size={13} strokeWidth={1.9} />
            Muhai Score <b>{score.total_score}</b>
          </span>
        )}

        <LanguageToggle />

        <div className="topbar__pop-anchor">
          <button
            className="topbar__icon-btn"
            aria-label="Notifications"
            onClick={() => {
              setNotifOpen((v) => !v)
              setMenuOpen(false)
            }}
          >
            <Bell size={15} strokeWidth={1.9} />
            {alerts.length > 0 && <span className="topbar__notif-dot" />}
          </button>
          <AnimatePresence>
            {notifOpen && (
              <motion.div
                className="popover popover--right"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.16, ease: [0.22, 0.8, 0.3, 1] }}
              >
                {alerts.length === 0 ? (
                  <div className="popover__empty">{t('common.none')}</div>
                ) : (
                  alerts.slice(0, 6).map((a) => (
                    <button key={a.key} className="popover__row" onClick={() => go(a.to)}>
                      <span className={`popover__dot popover__dot--${a.tone}`} />
                      <span className="grow">
                        <span className="popover__title">{a.title}</span>
                        <span className="popover__meta">{a.body}</span>
                      </span>
                    </button>
                  ))
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="topbar__pop-anchor">
          <button
            className="topbar__avatar"
            onClick={() => {
              setMenuOpen((v) => !v)
              setNotifOpen(false)
            }}
          >
            <span className="topbar__avatar-img">{initials(displayName)}</span>
            <span>
              <span className="topbar__avatar-name">{displayName}</span>
              <span className="topbar__avatar-role">{company?.name || '—'}</span>
            </span>
          </button>
          <AnimatePresence>
            {menuOpen && (
              <motion.div
                className="popover popover--right"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.16, ease: [0.22, 0.8, 0.3, 1] }}
              >
                <button className="popover__row" onClick={() => go('/app/settings')}>
                  <SettingsIcon size={14} strokeWidth={1.9} />
                  <span className="popover__title">{t('nav.settings')}</span>
                </button>
                <button
                  className="popover__row popover__row--danger"
                  onClick={async () => {
                    await logout()
                    navigate('/login', { replace: true })
                  }}
                >
                  <LogOut size={14} strokeWidth={1.9} />
                  <span className="popover__title">{t('auth.logout')}</span>
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  )
}

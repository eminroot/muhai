import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  ArrowUpRight,
  Bot,
  Boxes,
  Landmark,
  LineChart,
  Lock,
  Moon,
  Plus,
  ReceiptText,
  ScanLine,
  Sparkles,
  Sun,
  Users,
  WifiOff,
  Zap,
} from 'lucide-react'
import { useLang } from '../i18n/LanguageContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import LanguageToggle from '../components/layout/LanguageToggle.jsx'
import Logo from '../components/ui/Logo.jsx'
import AnimatedNumber from '../components/ui/AnimatedNumber.jsx'
import Reveal from '../components/ui/Reveal.jsx'
import AreaChart from '../components/charts/AreaChart.jsx'
import SiteChat from '../components/chatbot/SiteChat.jsx'
import { MONTHS } from '../lib/format.js'

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.44, 0, 0.56, 1], delay: i * 0.05 },
  }),
}

/* The six modules, as tabs over one feature slab. Each carries the pastel
   bed it sits on and a small card standing in for the screen itself. */
const MODULES = [
  { key: 'f1', icon: ReceiptText, to: '/app/invoices', bed: 'steel' },
  { key: 'f2', icon: Landmark, to: '/app/tax', bed: 'iris' },
  { key: 'f3', icon: Boxes, to: '/app/inventory', bed: 'blush' },
  { key: 'f4', icon: Users, to: '/app/payroll', bed: 'mauve' },
  { key: 'f5', icon: Sparkles, to: '/app/assistant', bed: 'iris' },
  { key: 'f6', icon: LineChart, to: '/app', bed: 'steel' },
]

// Illustrative series for the marketing mock only. Real figures come from the
// workspace and the compute API once you are signed in.
const PREVIEW_CASHFLOW = [
  { income: 183000, expense: 118000 },
  { income: 176000, expense: 109000 },
  { income: 198000, expense: 124000 },
  { income: 211000, expense: 131000 },
  { income: 205000, expense: 127000 },
  { income: 228000, expense: 138000 },
  { income: 241000, expense: 142000 },
  { income: 263000, expense: 151000 },
]

export default function Landing() {
  const { t, lang } = useLang()
  const { theme, toggle } = useTheme()
  const en = lang === 'en'

  // The header is transparent over the hero and glass once you scroll past it.
  const [stuck, setStuck] = useState(false)
  const [tab, setTab] = useState(0)
  const [openQ, setOpenQ] = useState(0)

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const facts = [
    { icon: ScanLine, label: en ? 'Reads the invoice' : 'Faturayı okur' },
    { icon: LineChart, label: en ? '30-day forecast' : '30 günlük tahmin' },
    { icon: Landmark, label: en ? '2026 rates built in' : '2026 oranları yerleşik' },
    { icon: WifiOff, label: en ? 'Works without internet' : 'İnternetsiz de çalışır' },
  ]

  const active = MODULES[tab]

  const queue = en
    ? [
        ['Anadolu Textiles', 'Invoice arrived · ₺48,200'],
        ['Marmara Logistics', 'Due in 6 days'],
        ['Aegean Chemicals', 'VAT rate looks wrong'],
        ['Başak Packaging', 'Duplicate of FT-0141?'],
        ['Yıldız Food', 'Payment recorded'],
        ['Toros Energy', 'Category corrected'],
      ]
    : [
        ['Anadolu Tekstil', 'Fatura geldi · ₺48.200'],
        ['Marmara Lojistik', 'Vadesine 6 gün'],
        ['Ege Kimya', 'KDV oranı tutmuyor'],
        ['Başak Ambalaj', 'FT-0141 ile mükerrer mi?'],
        ['Yıldız Gıda', 'Ödeme kaydedildi'],
        ['Toros Enerji', 'Kategori düzeltildi'],
      ]

  const faqs = [1, 2, 3, 4, 5, 6].map((n) => ({ q: t(`landing.faq${n}Q`), a: t(`landing.faq${n}A`) }))

  return (
    <div className="lp">
      {/* ---------------------------------------------------- nav -- */}
      <nav className={`lp-nav${stuck ? ' lp-nav--stuck' : ''}`}>
        <div className="lp-nav__pill">
          <Link to="/" className="brand">
            <span className="brand-glyph"><Logo size={15} /></span>
            <span className="brand-name">Muhai</span>
          </Link>

          <div className="lp-nav__links">
            <a href="#modules">{t('nav.modules')}</a>
            <a href="#how">{t('landing.howEyebrow')}</a>
            <a href="#faq">{t('landing.faqTitle')}</a>
          </div>

          <div className="lp-nav__right">
            <LanguageToggle />
            <button
              className="topbar__icon-btn"
              onClick={toggle}
              aria-label={t(theme === 'dark' ? 'common.lightMode' : 'common.darkMode')}
            >
              {theme === 'dark' ? <Sun size={15} strokeWidth={1.9} /> : <Moon size={15} strokeWidth={1.9} />}
            </button>
            <Link to="/login" className="lp-nav__login">{t('nav.login')}</Link>
            <Link to="/register" className="btn btn--primary btn--sm">
              {t('nav.launch')}
              <ArrowRight size={13} strokeWidth={1.9} />
            </Link>
          </div>
        </div>
      </nav>

      {/* --------------------------------------------------- hero -- */}
      <header className="lp-hero">
        <div className="lp-hero__copy">
          <motion.span className="label lp-hero__eyebrow" variants={fadeUp} initial="hidden" animate="show">
            {t('landing.badge')}
          </motion.span>

          <motion.h1 className="lp-hero__title" variants={fadeUp} initial="hidden" animate="show" custom={1}>
            {t('landing.heroLine1')}{' '}
            <span className="lp-hero__rule">
              {t('landing.heroLine2')}
              <UnderStroke />
            </span>
          </motion.h1>

          <motion.p className="lp-hero__sub" variants={fadeUp} initial="hidden" animate="show" custom={2}>
            {t('landing.heroSub')}
          </motion.p>

          <motion.div className="lp-hero__cta" variants={fadeUp} initial="hidden" animate="show" custom={3}>
            <Link to="/register" className="btn btn--primary btn--lg">
              {t('landing.ctaPrimary')}
              <ArrowRight size={15} strokeWidth={1.9} />
            </Link>
            <a href="#modules" className="btn btn--ghost btn--lg">{t('landing.ctaSecondary')}</a>
          </motion.div>
        </div>

        {/* Figures in a tray — three white cards at an 8px gutter. */}
        <motion.div className="tray lp-figures" variants={fadeUp} initial="hidden" animate="show" custom={4}>
          <Stat value={2.4} suffix="M+" label={t('landing.statInvoices')} fmt={(v) => v.toFixed(1)} />
          <Stat value={98.6} suffix="%" label={t('landing.statAccuracy')} fmt={(v) => v.toFixed(1)} />
          <Stat value={1200} suffix="+" label={t('landing.statBusinesses')} fmt={(v) => Math.round(v).toString()} />
        </motion.div>

        {/* The product, shown rather than described. */}
        <div className="lp-hero__visual lp-settle">
          <div className="lp-hero__clip">
            <div className="tray tray--lifted">
              <div className="lp-mock">
                <div className="lp-mock__head">
                  <span className="lp-mock__glyph"><Logo size={13} /></span>
                  <span className="lp-mock__title">Muhai · {t('nav.dashboard')}</span>
                  <span className="pill ok lp-mock__live">{t('common.live')}</span>
                </div>

                <div className="lp-mock__kpis">
                  {[
                    { label: t('dashboard.kpiRevenue'), val: '₺263.400', up: '+9,1%' },
                    { label: t('dashboard.kpiProfit'), val: '₺112.180', up: '+12,8%' },
                  ].map((k) => (
                    <div className="lp-mock__kpi" key={k.label}>
                      <span className="label">{k.label}</span>
                      <div className="lp-mock__kpi-val num">{k.val}</div>
                      <span className="delta delta--pos">{k.up}</span>
                    </div>
                  ))}
                </div>

                <div className="lp-mock__chart">
                  <div className="lp-mock__chart-head">
                    <span className="label">{t('dashboard.cashflowTitle')}</span>
                    <span className="lp-mock__legend">
                      <i style={{ background: 'var(--d3)' }} />{t('dashboard.income')}
                      <i style={{ background: 'var(--d2)' }} />{t('dashboard.expense')}
                    </span>
                  </div>
                  <AreaChart
                    data={PREVIEW_CASHFLOW}
                    labels={MONTHS[lang].slice(4)}
                    keys={['income', 'expense']}
                    colors={['var(--d3)', 'var(--d2)']}
                    height={148}
                    formatValue={(v) => `₺${Math.round(v / 1000)}K`}
                    seriesNames={[t('dashboard.income'), t('dashboard.expense')]}
                  />
                </div>

                {/* The mock ends on a calm list rather than mid-chart: the
                    fade over the foot smears anything busy underneath it. */}
                <div className="lp-mock__rows">
                  {(en
                    ? [
                        ['Anadolu Textiles', 'FT-2026-0148', '₺48,200', 'ok'],
                        ['Marmara Logistics', 'FT-2026-0147', '₺12,940', 'warn'],
                        ['Aegean Chemicals', 'FT-2026-0146', '₺31,500', 'stop'],
                        ['Başak Packaging', 'FT-2026-0145', '₺7,310', 'ok'],
                      ]
                    : [
                        ['Anadolu Tekstil', 'FT-2026-0148', '₺48.200', 'ok'],
                        ['Marmara Lojistik', 'FT-2026-0147', '₺12.940', 'warn'],
                        ['Ege Kimya', 'FT-2026-0146', '₺31.500', 'stop'],
                        ['Başak Ambalaj', 'FT-2026-0145', '₺7.310', 'ok'],
                      ]
                  ).map(([name, no, amount, tone]) => (
                    <div className="lp-mock__row" key={no}>
                      <span className="lp-mock__row-av">{name.slice(0, 2).toUpperCase()}</span>
                      <span className="lp-mock__row-body">
                        <span className="lp-mock__row-name">{name}</span>
                        <span className="lp-mock__row-meta">{no}</span>
                      </span>
                      <span className="lp-mock__row-amt num">{amount}</span>
                      <span className={`pill ${tone}`} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <span className="lp-hero__fade" aria-hidden="true"><span /><span /><span /></span>
        </div>

        <Reveal className="lp-facts" variants={fadeUp}>
          {facts.map((f) => (
            <span className="lp-fact" key={f.label}>
              <f.icon size={14} strokeWidth={1.9} />
              {f.label}
            </span>
          ))}
        </Reveal>
      </header>

      {/* ------------------------------------------------ modules --
          A tab rail over one feature slab, rather than six cards. */}
      <section className="lp-section" id="modules">
        <div className="lp-inner lp-stack">
          <Reveal className="lp-head" variants={fadeUp}>
            <h2>{t('landing.featuresTitle')}</h2>
            <p>{t('landing.featuresSub')}</p>
          </Reveal>

          <div className="tray lp-tabs" role="tablist">
            {MODULES.map((m, i) => (
              <button
                key={m.key}
                role="tab"
                aria-selected={i === tab}
                className={`lp-tab${i === tab ? ' is-active' : ''}`}
                onClick={() => setTab(i)}
              >
                <m.icon size={15} strokeWidth={1.9} />
                {t(`landing.${m.key}Eyebrow`)}
              </button>
            ))}
          </div>

          <div className="tray lp-slab">
            <div className="lp-slab__grid">
              <div className={`lp-slab__bed lp-slab__bed--${active.bed}`}>
                <div className="lp-slab__card">
                  <ModuleCard which={active.key} en={en} />
                </div>
              </div>

              <div className="lp-slab__copy">
                <p className="label">{t(`landing.${active.key}Tag`)}</p>
                <h3>{t(`landing.${active.key}Title`)}</h3>
                <p>{t(`landing.${active.key}Desc`)}</p>
                <Link to={active.to} className="lp-slab__link">
                  {t('landing.modulesPanelCta')}
                  <ArrowUpRight size={16} strokeWidth={1.9} />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* -------------------------------------------------- proof -- */}
      <section className="lp-section">
        <div className="lp-inner lp-stack">
          <Reveal className="lp-head" variants={fadeUp}>
            <h2>{t('landing.proofTitle')}</h2>
            <p>{t('landing.proofSub')}</p>
          </Reveal>

          <Reveal className="tray lp-proof" variants={fadeUp}>
            <div className="lp-proof__figures">
              {[1, 2, 3, 4].map((n) => (
                <div className="lp-proof__fig" key={n}>
                  <span className="label">{t(`landing.proofStat${n}`)}</span>
                  <span className="lp-proof__fig-val">{t(`landing.proofStat${n}Val`)}</span>
                </div>
              ))}
            </div>

            <div className="lp-proof__panels">
              {/* The bar length IS the rate, so the chart carries a real number. */}
              <div className="lp-panel">
                <h3>{t('landing.proofRatesTitle')}</h3>
                <ul>
                  {[
                    { label: t('landing.proofRate1'), pct: 20 },
                    { label: t('landing.proofRate2'), pct: 10 },
                    { label: t('landing.proofRate3'), pct: 1 },
                  ].map((r) => (
                    <li className="lp-bar-row" key={r.label}>
                      <span className="lp-bar-row__head">
                        <span>{r.label}</span>
                        <b>%{r.pct}</b>
                      </span>
                      <span className="lp-bar">
                        <i style={{ width: `${Math.max(r.pct * 4, 6)}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="lp-panel">
                <h3>{t('landing.proofFieldsTitle')}</h3>
                <ul>
                  {[
                    { icon: ReceiptText, n: 1 },
                    { icon: Landmark, n: 2 },
                    { icon: Bot, n: 3 },
                  ].map((f) => (
                    <li className="lp-list-row" key={f.n}>
                      <span className="lp-list-row__glyph"><f.icon size={15} strokeWidth={1.9} /></span>
                      <span className="lp-list-row__body">
                        <span className="lp-list-row__name">{t(`landing.proofField${f.n}`)}</span>
                        <span className="lp-list-row__note">{t(`landing.proofField${f.n}Note`)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Reveal>

          <p className="lp-note">{t('landing.proofNote')}</p>
        </div>
      </section>

      {/* ------------------------------------------------- problem -- */}
      <section className="lp-section">
        <div className="lp-inner" style={{ display: 'flex', flexDirection: 'column', gap: 64 }}>
          <div className="lp-pain__grid">
            <Reveal className="lp-head lp-head--left" variants={fadeUp}>
              <h2>{t('landing.painTitle')}</h2>
              <p>{t('landing.painSub')}</p>
            </Reveal>

            {/* The queue drifts, so the section moves without anything blinking. */}
            <div className="lp-drift" aria-hidden="true">
              <ul>
                {[...queue, ...queue].map(([name, meta], i) => (
                  <li key={`${name}-${i}`}>
                    <span className="lp-drift__av">{name.slice(0, 2).toUpperCase()}</span>
                    <span className="lp-drift__body">
                      <span className="lp-drift__name">{name}</span>
                      <span className="lp-drift__meta">{meta}</span>
                    </span>
                  </li>
                ))}
              </ul>
              <span className="lp-drift__veil lp-drift__veil--top" />
              <span className="lp-drift__wash lp-drift__wash--top" />
              <span className="lp-drift__veil lp-drift__veil--bot" />
              <span className="lp-drift__wash lp-drift__wash--bot" />
            </div>
          </div>

          <Reveal className="tray lp-three" variants={fadeUp}>
            <div className="lp-three__grid">
              {[
                { icon: Zap, n: 1 },
                { icon: WifiOff, n: 2 },
                { icon: Lock, n: 3 },
              ].map((c) => (
                <div className="lp-three__card" key={c.n}>
                  <span className="lp-three__glyph"><c.icon size={17} strokeWidth={1.9} /></span>
                  <h4>{t(`landing.pain${c.n}Title`)}</h4>
                  <p>{t(`landing.pain${c.n}Desc`)}</p>
                </div>
              ))}
            </div>
          </Reveal>

          <p className="lp-note">{t('landing.painNote')}</p>
        </div>
      </section>

      {/* ----------------------------------------------------- how -- */}
      <section className="lp-section" id="how">
        <div className="lp-inner lp-stack">
          <Reveal className="lp-head" variants={fadeUp}>
            <h2>{t('landing.howTitle')}</h2>
          </Reveal>
          <div className="lp-steps">
            {['how1', 'how2', 'how3'].map((s, i) => (
              <Reveal key={s} className="lp-step" variants={fadeUp} custom={i}>
                <span className="lp-step__num">{String(i + 1).padStart(2, '0')}</span>
                <h4>{t(`landing.${s}Title`)}</h4>
                <p>{t(`landing.${s}Desc`)}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------- faq -- */}
      <section className="lp-section" id="faq">
        <div className="lp-inner">
          <div className="lp-faq__grid">
            <Reveal className="lp-head lp-head--left lp-faq__aside" variants={fadeUp}>
              <h2>{t('landing.faqTitle')}</h2>
              <p>{t('landing.faqSub')}</p>
              <a href="mailto:destek@muhai.com" className="btn btn--ghost btn--lg">
                {t('landing.faqCta')}
                <ArrowUpRight size={15} strokeWidth={1.9} />
              </a>
            </Reveal>

            <div className="tray lp-faq__list">
              {faqs.map((f, i) => (
                <div className={`lp-faq__item${openQ === i ? ' is-open' : ''}`} key={f.q}>
                  <h3>
                    <button
                      className="lp-faq__q"
                      aria-expanded={openQ === i}
                      onClick={() => setOpenQ(openQ === i ? -1 : i)}
                    >
                      <span>{f.q}</span>
                      <span className="lp-faq__mark"><Plus size={16} strokeWidth={2.2} /></span>
                    </button>
                  </h3>
                  <motion.div
                    className="lp-faq__a"
                    initial={false}
                    animate={{ height: openQ === i ? 'auto' : 0, opacity: openQ === i ? 1 : 0 }}
                    transition={{ duration: 0.3, ease: [0.44, 0, 0.56, 1] }}
                  >
                    <p>{f.a}</p>
                  </motion.div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------- cta -- */}
      <section className="lp-cta">
        <Reveal className="lp-cta__inner" variants={fadeUp}>
          <h2>{t('landing.ctaTitle')}</h2>
          <p>{t('landing.ctaSub')}</p>
          <Link to="/register" className="btn btn--lg lp-cta__btn">
            {t('landing.ctaButton')}
            <ArrowRight size={15} strokeWidth={1.9} />
          </Link>
        </Reveal>
      </section>

      {/* -------------------------------------------------- footer -- */}
      <footer className="lp-footer">
        <div className="lp-footer__main">
          <div className="lp-footer__brand">
            <span className="brand">
              <span className="brand-glyph"><Logo size={15} /></span>
              <span className="brand-name">Muhai</span>
            </span>
            <p>{t('landing.footerTagline')}</p>
          </div>
          <div className="lp-footer__cols">
            <FooterCol
              title={t('landing.footerProduct')}
              items={[t('nav.invoices'), t('nav.tax'), t('nav.inventory'), t('nav.payroll')]}
            />
            <FooterCol title={t('landing.footerCompany')} items={[t('nav.about'), 'Blog', t('nav.pricing')]} />
            <FooterCol title={t('landing.footerLegal')} items={['KVKK', 'Gizlilik', 'Şartlar']} />
          </div>
        </div>

        <div className="lp-footer__contact">
          <a href="mailto:destek@muhai.com">destek@muhai.com</a>
        </div>

        <div className="lp-footer__bar">
          <span>© 2026 Muhai. {t('landing.footerRights')}</span>
          <span>{t('landing.madeWith')}</span>
        </div>
      </footer>

      <SiteChat />
    </div>
  )
}

/* A hand-drawn stroke under the claim — one stroke, drawn in, never a
   straight rule. `pathLength="1"` makes the dash animation unit-based, so it
   works at any width. */
function UnderStroke() {
  return (
    <svg className="lp-hero__stroke" viewBox="0 0 300 12" preserveAspectRatio="none" aria-hidden="true">
      <path d="M4 8.4C58 3.6 126 2.4 296 5.6" pathLength="1" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/* The small card standing on the pastel bed.

   Three rows, and that is all: an avatar, a name, a quiet second line and
   a tint pill. Theirs is this spare on purpose — the card stands in for a
   screen rather than reproducing one, so a dense replica reads as clutter
   at this size. */
function ModuleCard({ which, en }) {
  const rows = {
    f1: [
      { av: 'AT', name: 'Anadolu Tekstil', meta: 'FT-2026-0148', pill: '0,96' },
      { av: 'ML', name: 'Marmara Lojistik', meta: 'FT-2026-0147', pill: '0,94' },
      { av: 'EK', name: 'Ege Kimya', meta: 'FT-2026-0146', pill: '0,61', tone: 'amber' },
    ],
    f2: [
      { av: 'KDV', name: en ? 'VAT return' : 'KDV Beyannamesi', meta: '26.09.2026', pill: en ? '6 days' : '6 gün', tone: 'amber' },
      { av: 'MUH', name: en ? 'Withholding' : 'Muhtasar', meta: '26.09.2026', pill: en ? '6 days' : '6 gün', tone: 'amber' },
      { av: 'SGK', name: en ? 'SGK premium' : 'SGK Primi', meta: '30.09.2026', pill: en ? '10 days' : '10 gün', tone: 'slate' },
    ],
    f3: [
      { av: '14', name: en ? 'Cotton yarn 40/1' : 'Pamuk iplik 40/1', meta: 'SKU-014', pill: '78' },
      { av: '21', name: en ? 'Dye — indigo' : 'Boya — indigo', meta: 'SKU-021', pill: '41' },
      { av: '36', name: en ? 'Packing tape' : 'Koli bandı', meta: 'SKU-036', pill: '12', tone: 'red' },
    ],
    f4: [
      { av: 'AD', name: 'Ayşe Demir', meta: en ? 'Accounting' : 'Muhasebe', pill: '₺38.610' },
      { av: 'MK', name: 'Mert Kaya', meta: en ? 'Production' : 'Üretim', pill: '₺31.240' },
      { av: 'ZA', name: 'Zeynep Arslan', meta: en ? 'Sales' : 'Satış', pill: '₺35.180' },
    ],
    f6: [
      { av: '₺', name: en ? 'Net profit' : 'Net kâr', meta: en ? 'This month' : 'Bu ay', pill: '+12,8%' },
      { av: '↑', name: en ? 'Revenue' : 'Gelir', meta: en ? 'This month' : 'Bu ay', pill: '+9,1%' },
      { av: '↓', name: en ? 'Expense' : 'Gider', meta: en ? 'This month' : 'Bu ay', pill: '+4,2%', tone: 'slate' },
    ],
  }

  if (which === 'f5') {
    return (
      <div className="lp-mini">
        <div className="lp-mini__ask">
          {en ? 'What are the 2026 VAT rates?' : '2026 KDV oranları nedir?'}
        </div>
        <div className="lp-mini__reply">
          {en
            ? 'Three rates apply: standard 20%, reduced 10%, super-reduced 1%.'
            : 'Üç oran uygulanır: genel %20, indirimli %10, süper indirimli %1.'}
        </div>
        <span className="lp-mini__src">
          {en ? 'Source: VAT rates (2026)' : 'Kaynak: KDV oranları (2026)'}
        </span>
      </div>
    )
  }

  return (
    <div className="lp-mini">
      {(rows[which] || rows.f1).map((r) => (
        <div className="lp-mini__row" key={r.name}>
          <span className="lp-mini__av">{r.av}</span>
          <span className="lp-mini__body">
            <span className="lp-mini__label">{r.name}</span>
            <span className="lp-mini__meta">{r.meta}</span>
          </span>
          <span className={`lp-mini__pill${r.tone ? ` lp-mini__pill--${r.tone}` : ''}`}>{r.pill}</span>
        </div>
      ))}
    </div>
  )
}

function Stat({ value, suffix, label, fmt }) {
  return (
    <div className="lp-stat">
      <div className="lp-stat__val num">
        <AnimatedNumber value={value} format={fmt} />
        {suffix}
      </div>
      <div className="lp-stat__label label">{label}</div>
    </div>
  )
}

function FooterCol({ title, items }) {
  return (
    <div className="lp-footer__col">
      <h5 className="label">{title}</h5>
      {items.map((it) => (
        <a key={it} href="#">{it}</a>
      ))}
    </div>
  )
}

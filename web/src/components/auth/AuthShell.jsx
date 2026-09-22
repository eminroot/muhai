import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BarChart3, Bot, Check, ScanLine, ShieldCheck } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'
import LanguageToggle from '../layout/LanguageToggle.jsx'
import Logo from '../ui/Logo.jsx'

const HIGHLIGHTS = [
  { icon: ScanLine, tr: 'Fatura OCR', en: 'Invoice OCR', trSub: 'Tutar, KDV ve tarih otomatik okunur', enSub: 'Amount, VAT and dates read automatically' },
  { icon: BarChart3, tr: 'Nakit akışı tahmini', en: 'Cash-flow forecast', trSub: '30 günlük nakit projeksiyonu', enSub: 'A 30-day cash projection' },
  { icon: ShieldCheck, tr: '2026 vergi motoru', en: '2026 tax engine', trSub: 'KDV, stopaj, SGK, kurumlar', enSub: 'VAT, withholding, SGK, corporate' },
  { icon: Bot, tr: 'Finansal asistan', en: 'Financial assistant', trSub: 'İşletme verinize dayalı yanıtlar', enSub: 'Answers grounded in your data' },
]

/**
 * The auth shell: a centred tray holding two cards — the pitch on the left,
 * the form on the right. Below 1000px the pitch drops and the form card
 * carries the tray on its own.
 */
export default function AuthShell({ title, subtitle, wide = false, children }) {
  const { lang } = useLang()

  return (
    <div className="auth-page">
      <div className="auth-page__bar">
        <Link to="/" className="brand">
          <span className="brand-glyph">
            <Logo size={15} />
          </span>
          <span className="brand-name">Muhai</span>
        </Link>
        <LanguageToggle />
      </div>

      <div className="auth-page__body">
        <motion.div
          className={`tray auth-tray ${wide ? 'auth-tray--wide' : ''}`}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.44, 0, 0.56, 1] }}
        >
          <div className="auth-pitch">
            <h2 className="auth-pitch__title">
              {lang === 'en'
                ? 'Your accounting, already done by the time you look at it.'
                : 'Muhasebeniz, siz bakmadan önce yapılmış olsun.'}
            </h2>

            <ul className="auth-highlights">
              {HIGHLIGHTS.map((h, i) => (
                <motion.li
                  key={h.tr}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.45, delay: 0.1 + i * 0.08 }}
                >
                  <span className="auth-highlights__icon">
                    <Check size={12} strokeWidth={2.4} />
                  </span>
                  <span>
                    <strong>{lang === 'en' ? h.en : h.tr}</strong>
                    <em>{lang === 'en' ? h.enSub : h.trSub}</em>
                  </span>
                </motion.li>
              ))}
            </ul>

            <p className="auth-pitch__foot">TEKNOFEST 2026 · Team Nasimi BHOS</p>
          </div>

          <div className="auth-card">
            <h1 className="auth-card__title">{title}</h1>
            <p className="auth-card__sub">{subtitle}</p>
            {children}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

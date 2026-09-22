import { motion } from 'framer-motion'
import { useLang } from '../../i18n/LanguageContext.jsx'

export default function LanguageToggle() {
  const { lang, setLanguage } = useLang()
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <motion.span
        className="lang-toggle__pill"
        animate={{ left: lang === 'tr' ? '3px' : 'calc(50%)' }}
        transition={{ type: 'spring', stiffness: 420, damping: 34 }}
      />
      <button className={lang === 'tr' ? 'active' : ''} onClick={() => setLanguage('tr')} aria-pressed={lang === 'tr'}>
        TR
      </button>
      <button className={lang === 'en' ? 'active' : ''} onClick={() => setLanguage('en')} aria-pressed={lang === 'en'}>
        EN
      </button>
    </div>
  )
}

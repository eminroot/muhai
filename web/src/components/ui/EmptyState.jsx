import { motion } from 'framer-motion'
import { Database } from 'lucide-react'
import { useLang } from '../../i18n/LanguageContext.jsx'

/**
 * Shown when a company has no data yet.
 *
 * It used to offer a "load demo data" button that manufactured a year of
 * trading in the browser. Nothing invents business data on the client any
 * more — a real account starts empty and fills up as its owner works. The
 * seeded dataset lives in one demo account, written by the backend's
 * `scripts/seed_demo.py`.
 */
export default function EmptyState({ title, body }) {
  const { t } = useLang()

  return (
    <div className="page">
      <motion.div className="empty-state" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
        <span className="empty-state__icon">
          <Database size={19} strokeWidth={1.6} />
        </span>
        <h2>{title || t('common.emptyTitle')}</h2>
        <p>{body || t('common.emptyBody')}</p>
      </motion.div>
    </div>
  )
}

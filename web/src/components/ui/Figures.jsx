import { motion } from 'framer-motion'
import { TrendingDown, TrendingUp } from 'lucide-react'
import AnimatedNumber from './AnimatedNumber.jsx'

/**
 * The month's figures, as one band rather than a row of tiles.
 *
 * A dashboard leads with exactly one number. That one gets the hero
 * treatment — large, proportional figures, its own trend — and the rest sit
 * beside it as ruled rows with their values in a tabular column. Four equal
 * cards say nothing about which figure matters.
 *
 * Two independent signals, deliberately not conflated:
 *   - the arrow follows the *sign* of the change (did it go up or down?)
 *   - the tone follows `positive` (is that good or bad?)
 * Expenses falling is a green down-arrow; tax accruing is a red up-arrow.
 */
function Delta({ value, label, positive, className = '' }) {
  const numeric = Number.isFinite(value) ? value : 0
  const Arrow = numeric >= 0 ? TrendingUp : TrendingDown
  const sign = numeric > 0 ? '+' : ''

  return (
    <span className={`figure-delta ${positive ? 'is-good' : 'is-bad'} ${className}`.trim()}>
      <Arrow size={13} strokeWidth={1.9} />
      {sign}
      {numeric}%{label ? <small>{label}</small> : null}
    </span>
  )
}

export function FigureBand({ hero, rows, format, vsLabel }) {
  return (
    <motion.section
      className="panel figures"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 0.8, 0.3, 1] }}
    >
      <div className="figure-hero">
        <div className="figure-hero__head">
          {hero.icon ? <hero.icon size={14} strokeWidth={1.9} /> : null}
          <span className="label">{hero.label}</span>
        </div>

        {/* Proportional figures, not tabular: at this size tabular-nums gives
            every digit the width of a zero and the number reads loose. */}
        <div className="figure-hero__value">
          <AnimatedNumber value={hero.value} format={format} />
        </div>

        <Delta value={hero.delta} positive={hero.positive} label={vsLabel} />
      </div>

      <ol className="figure-rows">
        {rows.map((r) => (
          <li className="figure-row" key={r.label}>
            {r.icon ? <r.icon size={14} strokeWidth={1.9} className="figure-row__icon" /> : null}
            <span className="figure-row__label label">{r.label}</span>
            <span className="figure-row__value num">{format(r.value)}</span>
            <Delta value={r.delta} positive={r.positive} className="figure-row__delta" />
          </li>
        ))}
      </ol>
    </motion.section>
  )
}

export default FigureBand

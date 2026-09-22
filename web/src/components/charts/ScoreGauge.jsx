import { motion } from 'framer-motion'
import { useReveal } from '../../lib/useReveal.js'

const RATING_COLOR = {
  green: 'var(--ok)',
  yellow: 'var(--warn)',
  red: 'var(--stop)',
}

/** 0–100 Muhai Score as a 240° arc gauge. */
export default function ScoreGauge({ score = 0, rating = 'yellow', size = 168, label }) {
  const [ref, inView] = useReveal({ once: true, margin: '-40px' })

  const stroke = 13
  const r = (size - stroke) / 2
  const cx = size / 2
  const cy = size / 2
  const SWEEP = 240 // degrees of arc
  const START = 150 // degrees, clockwise from +x axis

  const point = (angleDeg) => {
    const rad = (angleDeg * Math.PI) / 180
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)]
  }

  const arc = (fromDeg, toDeg) => {
    const [x1, y1] = point(fromDeg)
    const [x2, y2] = point(toDeg)
    const large = Math.abs(toDeg - fromDeg) > 180 ? 1 : 0
    return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
  }

  const clamped = Math.max(0, Math.min(100, score))
  const color = RATING_COLOR[rating] || RATING_COLOR.yellow

  // Dash-based reveal: one full-length path, animated via strokeDashoffset,
  // so the arc grows along its own curve rather than being redrawn each frame.
  const arcLength = (SWEEP / 360) * 2 * Math.PI * r
  const filled = (clamped / 100) * arcLength

  return (
    <div ref={ref} className="gauge" style={{ width: size, height: size * 0.78 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
        <path d={arc(START, START + SWEEP)} fill="none" stroke="var(--surface-inset)" strokeWidth={stroke} strokeLinecap="round" />
        <motion.path
          d={arc(START, START + SWEEP)}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${arcLength}`}
          initial={{ strokeDashoffset: arcLength }}
          animate={inView ? { strokeDashoffset: arcLength - filled } : {}}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        />
      </svg>
      <div className="gauge__center">
        <motion.span
          className="gauge__value tnum"
          initial={{ opacity: 0, y: 8 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          {Math.round(clamped)}
        </motion.span>
        {label && <span className="gauge__label">{label}</span>}
      </div>
    </div>
  )
}

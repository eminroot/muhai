import { useState } from 'react'
import { motion } from 'framer-motion'
import { useReveal } from '../../lib/useReveal.js'

/**
 * Animated donut. Segments sweep in clockwise; hovering a segment
 * lifts it and shows its share in the center.
 */
export default function DonutChart({ data, size = 200, thickness = 26, centerLabel, formatValue = (v) => v }) {
  const [ref, inView] = useReveal({ once: true, margin: '-40px' })
  const [hover, setHover] = useState(null)

  const total = data.reduce((s, d) => s + d.value, 0)
  const r = (size - thickness) / 2
  const cx = size / 2
  const cy = size / 2
  const C = 2 * Math.PI * r

  // A hairline of surface between neighbouring arcs, so two similar hues
  // still read as two slices rather than one long one.
  const GAP = 3

  let acc = 0
  const segments = data.map((d) => {
    const frac = d.value / total
    const seg = { ...d, frac, offset: acc, dash: Math.max(frac * C - GAP, 1) }
    acc += frac
    return seg
  })

  const active = hover != null ? segments[hover] : null

  return (
    <div ref={ref} style={{ display: 'flex', justifyContent: 'center', position: 'relative' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface-inset)" strokeWidth={thickness} />
        {segments.map((seg, i) => (
          <motion.circle
            key={i}
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth={hover === i ? thickness + 5 : thickness}
            strokeLinecap="butt"
            strokeDasharray={`${seg.dash} ${C - seg.dash}`}
            strokeDashoffset={-seg.offset * C}
            initial={{ opacity: 0, strokeDasharray: `0 ${C}` }}
            animate={inView ? { opacity: 1, strokeDasharray: `${seg.dash} ${C - seg.dash}` } : {}}
            transition={{ duration: 1, ease: [0.16, 1, 0.3, 1], delay: 0.15 + i * 0.12 }}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{ cursor: 'pointer', transition: 'stroke-width 0.2s' }}
          />
        ))}
      </svg>

      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'none',
        }}
      >
        {active ? (
          <>
            <span className="tnum" style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 600 }}>
              {Math.round(active.frac * 100)}%
            </span>
            <span style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>{active.label}</span>
          </>
        ) : (
          <>
            <span className="tnum" style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600 }}>
              {formatValue(total)}
            </span>
            <span style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>{centerLabel}</span>
          </>
        )}
      </div>
    </div>
  )
}

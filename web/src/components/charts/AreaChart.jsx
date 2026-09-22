import { useId, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useReveal } from '../../lib/useReveal.js'

/**
 * Multi-series area chart with a real value axis.
 *
 * Ticks are placed on "nice" round numbers rather than at the data extremes,
 * so the gridlines read as money (0 / 50K / 100K) instead of arbitrary
 * fractions of the maximum. Hovering snaps a guideline to the nearest point
 * and floats a tooltip beside the cursor.
 */

function niceCeil(value) {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const scaled = value / magnitude
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10
  return step * magnitude
}

export default function AreaChart({
  data = [],
  labels = [],
  height = 260,
  colors = ['var(--d1)', 'var(--d2)'],
  keys = ['income', 'expense'],
  formatValue = (v) => v,
  formatAxis,
  seriesNames = [],
  emptyLabel = '—',
}) {
  const gid = useId().replace(/:/g, '')
  const [ref, inView] = useReveal({ once: true, margin: '-60px' })
  const [hover, setHover] = useState(null)

  const W = 760
  const H = height
  const padLeft = 56
  const padRight = 14
  const padTop = 18
  const padBottom = 30
  const plotH = H - padTop - padBottom
  const plotW = W - padLeft - padRight

  const { max, ticks } = useMemo(() => {
    const values = data.flatMap((d) => keys.map((k) => Number(d[k]) || 0))
    const peak = values.length ? Math.max(...values) : 0
    if (peak <= 0) return { max: 1, ticks: [0, 1] }
    const top = niceCeil(peak * 1.08)
    const TICKS = 4
    return {
      max: top,
      ticks: Array.from({ length: TICKS + 1 }, (_, i) => (top / TICKS) * i),
    }
  }, [data, keys])

  if (!data.length) {
    return (
      <div className="chart-empty" style={{ height }}>
        {emptyLabel}
      </div>
    )
  }

  const x = (i) => (data.length === 1 ? padLeft + plotW / 2 : padLeft + (i / (data.length - 1)) * plotW)
  const y = (v) => padTop + plotH - ((Number(v) || 0) / max) * plotH

  const linePath = (key) =>
    data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(d[key]).toFixed(1)}`).join(' ')

  const areaPath = (key) =>
    `${linePath(key)} L ${x(data.length - 1).toFixed(1)} ${(padTop + plotH).toFixed(1)} L ${x(0).toFixed(1)} ${(
      padTop + plotH
    ).toFixed(1)} Z`

  const axisFormat = formatAxis || formatValue

  const handleMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const idx = Math.round(((px - padLeft) / plotW) * (data.length - 1))
    setHover(Math.max(0, Math.min(data.length - 1, idx)))
  }

  // Flip the tooltip to the left half once the cursor passes the midpoint,
  // so it never runs off the panel edge.
  const tipLeft = hover != null ? (x(hover) / W) * 100 : 0
  const tipFlip = tipLeft > 62

  return (
    <div ref={ref} className="chart-wrap" style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height={H}
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
        style={{ display: 'block', overflow: 'visible' }}
        role="img"
      >
        <defs>
          {keys.map((k, ki) => (
            <linearGradient key={k} id={`${gid}-fill-${ki}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors[ki]} stopOpacity="0.26" />
              <stop offset="70%" stopColor={colors[ki]} stopOpacity="0.05" />
              <stop offset="100%" stopColor={colors[ki]} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {/* value axis */}
        {ticks.map((tick, i) => {
          const gy = y(tick)
          return (
            <g key={i}>
              <line
                x1={padLeft}
                x2={W - padRight}
                y1={gy}
                y2={gy}
                stroke="var(--line)"
                strokeWidth="1"
                strokeDasharray={i === 0 ? '0' : '2 6'}
              />
              <text
                x={padLeft - 10}
                y={gy + 3.5}
                textAnchor="end"
                fontSize="10.5"
                fontFamily="var(--font-mono)"
                fill="var(--ink-4)"
              >
                {axisFormat(tick)}
              </text>
            </g>
          )
        })}

        {keys.map((k, ki) => (
          <g key={k}>
            <motion.path
              d={areaPath(k)}
              fill={`url(#${gid}-fill-${ki})`}
              initial={{ opacity: 0 }}
              animate={inView ? { opacity: 1 } : {}}
              transition={{ duration: 0.8, delay: 0.45 + ki * 0.1 }}
            />
            <motion.path
              d={linePath(k)}
              fill="none"
              stroke={colors[ki]}
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={inView ? { pathLength: 1 } : {}}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: ki * 0.12 }}
            />
          </g>
        ))}

        {hover != null && (
          <g>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={padTop}
              y2={padTop + plotH}
              stroke="var(--ink-4)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            {keys.map((k, ki) => (
              <circle
                key={k}
                cx={x(hover)}
                cy={y(data[hover][k])}
                r="4.5"
                fill="var(--surface)"
                stroke={colors[ki]}
                strokeWidth="2.5"
              />
            ))}
          </g>
        )}

        {labels.map((lab, i) => (
          <text
            key={i}
            x={x(i)}
            y={H - 9}
            textAnchor="middle"
            fontSize="10.5"
            fontFamily="var(--font-mono)"
            fontWeight={hover === i ? 700 : 400}
            fill={hover === i ? 'var(--ink)' : 'var(--ink-4)'}
          >
            {lab}
          </text>
        ))}
      </svg>

      {hover != null && (
        <div
          className="chart-tip"
          style={{
            left: `${tipLeft}%`,
            transform: tipFlip ? 'translate(-108%, 0)' : 'translate(8%, 0)',
          }}
        >
          <div className="chart-tip__head">{labels[hover] ?? ''}</div>
          {keys.map((k, ki) => (
            <div className="chart-tip__row" key={k}>
              <span className="chart-tip__swatch" style={{ background: colors[ki] }} />
              <span className="chart-tip__name">{seriesNames[ki] || k}</span>
              <span className="chart-tip__val tnum">{formatValue(data[hover][k])}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

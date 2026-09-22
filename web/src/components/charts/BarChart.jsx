import { useState } from 'react'
import { motion } from 'framer-motion'
import { useReveal } from '../../lib/useReveal.js'

/**
 * Grouped/animated bar chart. Bars grow from the baseline with a
 * staggered spring. Supports one or two series per category.
 */
export default function BarChart({
  data,
  labels = [],
  keys = ['value'],
  colors = ['var(--d1)'],
  height = 220,
  formatValue = (v) => v,
  seriesNames = [],
}) {
  const [ref, inView] = useReveal({ once: true, margin: '-60px' })
  const [hover, setHover] = useState(null)

  const max = Math.max(...data.flatMap((d) => keys.map((k) => d[k]))) * 1.1
  const padTop = 14
  const padBottom = 26
  const plotH = height - padTop - padBottom

  return (
    <div ref={ref} style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 0, height, position: 'relative' }}>
        {data.map((d, i) => (
          <div
            key={i}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'flex-end',
              height: '100%',
              position: 'relative',
              cursor: 'default',
            }}
          >
            {hover === i && (
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  background: 'var(--ink)',
                  color: '#fff',
                  padding: '6px 10px',
                  borderRadius: 8,
                  fontSize: 11,
                  whiteSpace: 'nowrap',
                  zIndex: 5,
                  boxShadow: 'var(--sh-md)',
                  pointerEvents: 'none',
                }}
              >
                {keys.map((k, ki) => (
                  <div key={k} className="tnum" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{ width: 7, height: 7, borderRadius: 2, background: colors[ki] }} />
                    {seriesNames[ki] ? `${seriesNames[ki]}: ` : ''}
                    {formatValue(d[k])}
                  </div>
                ))}
              </div>
            )}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-end',
                gap: keys.length > 1 ? 3 : 0,
                height: plotH,
                width: '100%',
                justifyContent: 'center',
                paddingTop: padTop,
              }}
            >
              {keys.map((k, ki) => {
                const h = (d[k] / max) * plotH
                return (
                  <motion.div
                    key={k}
                    initial={{ height: 0 }}
                    animate={inView ? { height: h } : {}}
                    transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.05 * i + ki * 0.08 }}
                    style={{
                      width: keys.length > 1 ? 13 : '62%',
                      maxWidth: 38,
                      background: colors[ki],
                      borderRadius: '5px 5px 2px 2px',
                      opacity: hover == null || hover === i ? 1 : 0.4,
                      transition: 'opacity 0.2s',
                    }}
                  />
                )
              })}
            </div>
            <span
              style={{
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                color: hover === i ? 'var(--ink)' : 'var(--ink-4)',
                marginTop: 8,
                transition: 'color 0.2s',
              }}
            >
              {labels[i]}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

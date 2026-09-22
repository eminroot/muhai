import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChartLegend, ChartTooltip, PeriodChip, ValueChip, gridTicks } from './chartKit.jsx'

/**
 * Income against expense over time.
 *
 * The anatomy is `chartKit`'s, shared with the forecast: a centred legend
 * above the plot, a left value axis over hairline gridlines, a crosshair
 * chipped on both axes, and a readout card beside the cursor.
 *
 * Three things keep it from reading as generated:
 *
 *   · **The scale fits the window.** Padding out to zero puts a year of
 *     trading in the top third of the frame and flattens it.
 *   · **No fills.** Two translucent washes over each other make a third
 *     colour that means nothing.
 *   · **Straight segments.** A spline through monthly totals invents
 *     values between the months that nobody measured.
 *
 * Wheel zooms about the pointer, drag pans, double-click resets.
 */

const MIN_SPAN = 2

export default function TrendChart({
  data = [],
  labels = [],
  keys = ['income', 'expense'],
  colors = ['var(--trend-up)', 'var(--trend-down)'],
  seriesNames = [],
  height = 300,
  formatValue = (v) => v,
  formatAxis,
  emptyLabel = '—',
}) {
  const svgRef = useRef(null)
  const n = data.length

  const [view, setView] = useState({ lo: 0, hi: Math.max(n - 1, 1) })
  const [cursor, setCursor] = useState(null)
  const drag = useRef(null)

  useEffect(() => {
    setView({ lo: 0, hi: Math.max(n - 1, 1) })
    setCursor(null)
  }, [n])

  const W = 880
  const H = height
  const padLeft = 60
  const padRight = 18
  const padTop = 16
  const padBottom = 34
  const plotW = W - padLeft - padRight
  const plotH = H - padTop - padBottom

  const lo = Math.max(0, Math.min(view.lo, Math.max(n - MIN_SPAN, 0)))
  const hi = Math.min(n - 1, Math.max(view.hi, lo + MIN_SPAN - 1))
  const span = Math.max(hi - lo, 1)

  const scale = useMemo(() => {
    // Round to the points actually in frame. Reaching one past the window
    // lets a single off-screen spike set the scale for a window it is not
    // even in, and zooming away from it then changes nothing.
    const slice = data.slice(Math.max(0, Math.round(lo)), Math.round(hi) + 1)
    if (!slice.length) return { min: 0, max: 1, ticks: [0, 1] }

    let min = Infinity
    let max = -Infinity
    for (const row of slice) {
      for (const k of keys) {
        const v = Number(row[k]) || 0
        if (v < min) min = v
        if (v > max) max = v
      }
    }
    const pad = (max - min) * 0.12 || Math.abs(max || 1) * 0.1
    return { min: min - pad, max: max + pad, ticks: gridTicks(min - pad, max + pad) }
  }, [data, keys, lo, hi])

  const x = useCallback((i) => padLeft + ((i - lo) / span) * plotW, [lo, span, plotW])
  const y = useCallback(
    (v) => padTop + plotH - (((Number(v) || 0) - scale.min) / (scale.max - scale.min || 1)) * plotH,
    [scale, plotH],
  )

  const indexAt = useCallback(
    (clientX) => {
      const rect = svgRef.current?.getBoundingClientRect()
      if (!rect) return lo
      const px = ((clientX - rect.left) / rect.width) * W
      return lo + ((px - padLeft) / plotW) * span
    },
    [lo, span, plotW],
  )

  // Native listener: React registers wheel passively, and a passive handler
  // cannot preventDefault — the page would scroll out from under the chart.
  useEffect(() => {
    const el = svgRef.current
    if (!el || n < 3) return undefined

    const onWheel = (e) => {
      e.preventDefault()
      const anchor = indexAt(e.clientX)
      const factor = e.deltaY > 0 ? 1.18 : 1 / 1.18

      setView((v) => {
        const curLo = Math.max(0, v.lo)
        const curHi = Math.min(n - 1, v.hi)
        const curSpan = Math.max(curHi - curLo, 1)
        const nextSpan = Math.min(Math.max(curSpan * factor, MIN_SPAN), n - 1)
        const frac = curSpan > 0 ? (anchor - curLo) / curSpan : 0.5
        let nextLo = anchor - frac * nextSpan
        let nextHi = nextLo + nextSpan
        if (nextLo < 0) { nextHi -= nextLo; nextLo = 0 }
        if (nextHi > n - 1) { nextLo -= nextHi - (n - 1); nextHi = n - 1 }
        return { lo: Math.max(0, nextLo), hi: Math.min(n - 1, nextHi) }
      })
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [indexAt, n])

  const onPointerDown = (e) => {
    if (n < 3) return
    drag.current = { x: e.clientX, lo, hi }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const onPointerMove = (e) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return

    if (drag.current) {
      const dxPx = ((e.clientX - drag.current.x) / rect.width) * W
      const shift = (dxPx / plotW) * (drag.current.hi - drag.current.lo)
      let nextLo = drag.current.lo - shift
      let nextHi = drag.current.hi - shift
      if (nextLo < 0) { nextHi -= nextLo; nextLo = 0 }
      if (nextHi > n - 1) { nextLo -= nextHi - (n - 1); nextHi = n - 1 }
      setView({ lo: Math.max(0, nextLo), hi: Math.min(n - 1, nextHi) })
      return
    }

    const idx = Math.round(Math.max(lo, Math.min(hi, indexAt(e.clientX))))
    const py = ((e.clientY - rect.top) / rect.height) * H
    setCursor({ idx, py: Math.max(padTop, Math.min(padTop + plotH, py)) })
  }

  // `releasePointerCapture` throws NotFoundError when the pointer was never
  // captured — which is every plain mouse-out, since only a drag captures.
  // Unguarded, that exception aborted the leave handler before it could
  // clear the cursor, and the crosshair and tooltip stayed on screen.
  const endDrag = (e) => {
    if (!drag.current) return
    drag.current = null
    try {
      e.currentTarget.releasePointerCapture?.(e.pointerId)
    } catch {
      /* not captured */
    }
  }

  if (!n) return <div className="chart-empty" style={{ height }}>{emptyLabel}</div>

  const axisFormat = formatAxis || formatValue
  const zoomed = lo > 0.01 || hi < n - 1.01

  const from = Math.max(0, Math.floor(lo) - 1)
  const to = Math.min(n - 1, Math.ceil(hi) + 1)

  const linePath = (key) => {
    let d = ''
    for (let i = from; i <= to; i++) {
      d += `${i === from ? 'M' : 'L'} ${x(i).toFixed(2)} ${y(data[i][key]).toFixed(2)} `
    }
    return d.trim()
  }

  const maxLabels = Math.max(2, Math.floor(plotW / 62))
  const step = Math.max(1, Math.ceil((hi - lo + 1) / maxLabels))
  const tickIdx = []
  for (let i = Math.ceil(lo); i <= Math.floor(hi); i++) {
    if ((i - Math.ceil(lo)) % step === 0) tickIdx.push(i)
  }

  const cursorValue = cursor
    ? scale.min + ((padTop + plotH - cursor.py) / plotH) * (scale.max - scale.min)
    : null

  return (
    <div className="ck">
      <div className="ck__top">
        <ChartLegend series={keys.map((k, ki) => ({ name: seriesNames[ki] || k, color: colors[ki] }))} />
        {zoomed && (
          <button type="button" className="ck__reset" onClick={() => setView({ lo: 0, hi: n - 1 })}>
            {labels[Math.round(lo)] ?? ''} – {labels[Math.round(hi)] ?? ''} ✕
          </button>
        )}
      </div>

      <div className="ck__plot">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          height={H}
          role="img"
          className="ck__svg"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onPointerLeave={(e) => { endDrag(e); setCursor(null) }}
          onDoubleClick={() => setView({ lo: 0, hi: n - 1 })}
        >
          <defs>
            <clipPath id="trend-plot">
              <rect x={padLeft} y={padTop - 6} width={plotW} height={plotH + 12} />
            </clipPath>
          </defs>

          {/* Solid hairlines. Dashing a grid adds noise and reads as
              "threshold" when it is only a grid. */}
          {scale.ticks.map((tick, i) => (
            <g key={i}>
              <line
                x1={padLeft} x2={padLeft + plotW}
                y1={y(tick)} y2={y(tick)}
                stroke="var(--ck-grid)" strokeWidth="1" shapeRendering="crispEdges"
              />
              <text x={padLeft - 11} y={y(tick) + 3.5} textAnchor="end" className="ck-axis-text">
                {axisFormat(tick)}
              </text>
            </g>
          ))}

          <g clipPath="url(#trend-plot)">
            {keys.map((k, ki) => (
              <path
                key={k}
                d={linePath(k)}
                fill="none"
                stroke={colors[ki]}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            ))}

            {cursor && keys.map((k, ki) => (
              <circle
                key={`cur-${k}`}
                cx={x(cursor.idx)}
                cy={y(data[cursor.idx]?.[k])}
                r="4"
                fill="var(--surface-card)"
                stroke={colors[ki]}
                strokeWidth="2.5"
              />
            ))}
          </g>

          {cursor && (
            <g pointerEvents="none">
              <line
                x1={x(cursor.idx)} x2={x(cursor.idx)} y1={padTop} y2={padTop + plotH}
                stroke="var(--ck-cross)" strokeWidth="1" strokeDasharray="4 4"
              />
              <line
                x1={padLeft} x2={padLeft + plotW} y1={cursor.py} y2={cursor.py}
                stroke="var(--ck-cross)" strokeWidth="1" strokeDasharray="4 4"
              />
              <ValueChip x={padLeft} y={cursor.py} text={axisFormat(cursorValue)} />
              <PeriodChip x={x(cursor.idx)} y={padTop + plotH + 6} text={labels[cursor.idx] ?? ''} />
            </g>
          )}

          {tickIdx.map((i) => (
            <text key={i} x={x(i)} y={H - 10} textAnchor="middle" className="ck-axis-text">
              {labels[i] ?? ''}
            </text>
          ))}
        </svg>

        {cursor && (
          <ChartTooltip
            leftPct={(x(cursor.idx) / W) * 100}
            title={labels[cursor.idx] ?? ''}
            rows={keys.map((k, ki) => ({
              label: seriesNames[ki] || k,
              value: formatValue(data[cursor.idx]?.[k]),
            }))}
          />
        )}
      </div>
    </div>
  )
}

import { useMemo, useRef, useState } from 'react'
import { ChartLegend, ChartTooltip, PeriodChip, ValueChip, gridTicks } from './chartKit.jsx'

/**
 * The Prophet forecast: predicted daily net as a line, inside its 80%
 * confidence interval.
 *
 * Same anatomy as the cash-flow chart — centred legend, left axis over
 * hairline gridlines, crosshair chipped on both axes, readout card beside
 * the cursor — so the two read as one system.
 *
 * **The band stays, and it is flat.** A forecast without its uncertainty is
 * a guess presented as a fact, so the interval is not decoration and does
 * not come off. It is a single low-opacity tint rather than the gradient it
 * used to be: a wash that fades out implies the uncertainty fades with it,
 * which is the opposite of what a widening interval means.
 *
 * Zero is drawn as a real rule whenever the interval crosses it — on a net
 * cash-flow forecast, "which side of zero" is the whole question.
 */
export default function ForecastChart({
  points = [],
  height = 270,
  color = 'var(--trend-line)',
  formatValue = (v) => v,
  formatAxis,
  formatDate = (d) => d,
  emptyLabel = '—',
  seriesLabel = 'Tahmin',
  bandLabel = '%80 aralık',
  rangeLabel = 'Aralık',
}) {
  const svgRef = useRef(null)
  const [cursor, setCursor] = useState(null)
  const n = points.length

  const W = 880
  const H = height
  const padLeft = 60
  const padRight = 18
  const padTop = 16
  const padBottom = 34
  const plotW = W - padLeft - padRight
  const plotH = H - padTop - padBottom

  const scale = useMemo(() => {
    if (!n) return null
    let min = Infinity
    let max = -Infinity
    for (const p of points) {
      if (p.yhat_lower < min) min = p.yhat_lower
      if (p.yhat_upper > max) max = p.yhat_upper
    }
    if (max === min) { max += 1; min -= 1 }
    const pad = (max - min) * 0.1
    min -= pad
    max += pad
    return { min, max, ticks: gridTicks(min, max) }
  }, [points, n])

  if (!n || !scale) return <div className="chart-empty" style={{ height }}>{emptyLabel}</div>

  const x = (i) => (n === 1 ? padLeft + plotW / 2 : padLeft + (i / (n - 1)) * plotW)
  const y = (v) => padTop + plotH - ((v - scale.min) / (scale.max - scale.min)) * plotH

  const axisFormat = formatAxis || formatValue

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(2)} ${y(p.yhat).toFixed(2)}`).join(' ')
  const band = [
    ...points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(2)} ${y(p.yhat_upper).toFixed(2)}`),
    ...points.slice().reverse().map((p, i) => `L ${x(n - 1 - i).toFixed(2)} ${y(p.yhat_lower).toFixed(2)}`),
    'Z',
  ].join(' ')

  const showZero = scale.min < 0 && scale.max > 0

  const onMove = (e) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    const px = ((e.clientX - rect.left) / rect.width) * W
    const idx = Math.round(((px - padLeft) / plotW) * (n - 1))
    const py = ((e.clientY - rect.top) / rect.height) * H
    setCursor({
      idx: Math.max(0, Math.min(n - 1, idx)),
      py: Math.max(padTop, Math.min(padTop + plotH, py)),
    })
  }

  const labelStep = Math.max(1, Math.round(n / 6))
  const cursorValue = cursor
    ? scale.min + ((padTop + plotH - cursor.py) / plotH) * (scale.max - scale.min)
    : null
  const active = cursor ? points[cursor.idx] : null

  return (
    <div className="ck">
      <div className="ck__top">
        <ChartLegend
          series={[
            { name: seriesLabel, color },
            { name: bandLabel, color: 'var(--ck-band)', band: true },
          ]}
        />
      </div>

      <div className="ck__plot">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          height={H}
          role="img"
          className="ck__svg"
          onPointerMove={onMove}
          onPointerLeave={() => setCursor(null)}
        >
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

          <path d={band} fill="var(--ck-band)" />

          {/* Zero is the question on a net forecast, so it is a real rule
              rather than whichever gridline happens to land near it. */}
          {showZero && (
            <line
              x1={padLeft} x2={padLeft + plotW} y1={y(0)} y2={y(0)}
              stroke="var(--ck-zero)" strokeWidth="1.5" shapeRendering="crispEdges"
            />
          )}

          <path
            d={line}
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />

          {cursor && (
            <g>
              <line
                x1={x(cursor.idx)} x2={x(cursor.idx)} y1={padTop} y2={padTop + plotH}
                stroke="var(--ck-cross)" strokeWidth="1" strokeDasharray="4 4"
              />
              <line
                x1={padLeft} x2={padLeft + plotW} y1={cursor.py} y2={cursor.py}
                stroke="var(--ck-cross)" strokeWidth="1" strokeDasharray="4 4"
              />
              <circle
                cx={x(cursor.idx)} cy={y(active.yhat)} r="4"
                fill="var(--surface-card)" stroke={color} strokeWidth="2.5"
              />
              <ValueChip x={padLeft} y={cursor.py} text={axisFormat(cursorValue)} />
              <PeriodChip x={x(cursor.idx)} y={padTop + plotH + 6} text={formatDate(active.ds)} />
            </g>
          )}

          {points.map((p, i) =>
            i % labelStep === 0 || i === n - 1 ? (
              <text key={p.ds} x={x(i)} y={H - 10} textAnchor="middle" className="ck-axis-text">
                {formatDate(p.ds)}
              </text>
            ) : null,
          )}
        </svg>

        {cursor && (
          <ChartTooltip
            leftPct={(x(cursor.idx) / W) * 100}
            title={formatDate(active.ds)}
            rows={[
              { label: seriesLabel, value: formatValue(active.yhat) },
              {
                label: rangeLabel,
                value: `${formatValue(active.yhat_lower)} … ${formatValue(active.yhat_upper)}`,
              },
            ]}
          />
        )}
      </div>
    </div>
  )
}

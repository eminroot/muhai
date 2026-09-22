/* ============================================================
   The pieces every chart on the console is made of.

   One anatomy, shared, so the cash-flow chart and the forecast are
   the same object with different data rather than two charts that
   happen to sit on the same page:

     · a centred legend above the plot, each series marked by a rule
       with a dot through it
     · a left value axis over solid hairline gridlines
     · a crosshair on both axes, each arm ending in a filled chip —
       the value on the left, the period underneath
     · a floating card beside the crosshair carrying the figures

   Kept here rather than duplicated because the two charts drifting
   apart is exactly how a dashboard starts looking assembled.
   ============================================================ */

/** A "nice" axis step: 1, 2, 2.5 or 5 times a power of ten. */
export function niceStep(range, count) {
  const raw = range / count
  const magnitude = 10 ** Math.floor(Math.log10(raw || 1))
  const scaled = raw / magnitude
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10
  return step * magnitude
}

/**
 * Gridlines across a range, aiming for five and never fewer than four.
 * Rounding a step up can otherwise leave two rules on the plot, which is
 * not a grid.
 */
export function gridTicks(min, max) {
  let step = niceStep(max - min, 5)
  const count = () => Math.floor(max / step) - Math.ceil(min / step) + 1
  let guard = 0
  while (count() < 4 && guard++ < 4) step /= 2
  const ticks = []
  for (let v = Math.ceil(min / step) * step; v <= max; v += step) ticks.push(v)
  return ticks
}

/**
 * The legend, centred over the plot.
 *
 * A rule with a dot through it, not a bare swatch: it is the mark the
 * chart actually draws, so the legend and the plot say the same thing.
 * `band` entries get a filled block instead, for an interval rather than
 * a line.
 */
export function ChartLegend({ series = [] }) {
  return (
    <div className="ck-legend">
      {series.map((s) => (
        <span className="ck-legend__item" key={s.name}>
          {s.band ? (
            <span className="ck-legend__band" style={{ background: s.color }} />
          ) : (
            <svg width="22" height="12" aria-hidden="true" className="ck-legend__mark">
              <line x1="0" y1="6" x2="22" y2="6" stroke={s.color} strokeWidth="2.5" strokeLinecap="round" />
              <circle cx="11" cy="6" r="4.5" fill={s.color} />
            </svg>
          )}
          <span className="ck-legend__name">{s.name}</span>
        </span>
      ))}
    </div>
  )
}

/** The chip pinned to the value axis, at the cursor's height. */
export function ValueChip({ x, y, text, width = 62 }) {
  return (
    <g transform={`translate(${x}, ${y})`} pointerEvents="none">
      <rect x={-width} y="-10" width={width} height="20" rx="4" fill="var(--ck-chip)" />
      <text x={-width / 2} y="4" textAnchor="middle" className="ck-chip-text">{text}</text>
    </g>
  )
}

/** The chip pinned under the time axis, at the hovered period. */
export function PeriodChip({ x, y, text, width = 56 }) {
  return (
    <g transform={`translate(${x}, ${y})`} pointerEvents="none">
      <rect x={-width / 2} y="0" width={width} height="20" rx="4" fill="var(--ck-chip)" />
      <text x="0" y="14" textAnchor="middle" className="ck-chip-text">{text}</text>
    </g>
  )
}

/**
 * The readout card beside the crosshair.
 *
 * Flips to the left of the cursor past the midpoint so it never leaves the
 * card, and never sits under the pointer — `pointer-events: none`, or it
 * would steal the move events that position it.
 */
export function ChartTooltip({ leftPct, title, rows = [] }) {
  const flip = leftPct > 58
  return (
    <div
      className="ck-tip"
      style={{
        left: `${leftPct}%`,
        transform: flip ? 'translate(calc(-100% - 14px), -50%)' : 'translate(14px, -50%)',
      }}
    >
      <div className="ck-tip__head">{title}</div>
      {rows.map((r) => (
        <div className="ck-tip__row" key={r.label}>
          <span className="ck-tip__label">{r.label}:</span>
          <span className="ck-tip__value tnum">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

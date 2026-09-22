import { useEffect, useRef, useState } from 'react'
import { useInView } from 'framer-motion'

/**
 * Counts up to `value`, ideally when scrolled into view.
 *
 * The count-up is decoration; the number is the point. Both halves of it are
 * unreliable in an embedded or occluded tab, so both have a timer behind them:
 *
 *   - IntersectionObserver can simply never fire, so the animation starts on a
 *     timer whether or not the element is reported in view.
 *   - requestAnimationFrame can never fire either — a tab that reports
 *     `visibilityState === 'visible'` is still not painting when it is
 *     occluded or backgrounded, and rAF callbacks then queue forever. That
 *     left the count-up stranded at its starting zero, which on a dashboard is
 *     the one failure that matters: every other figure on the page reads
 *     correctly while the headline says ₺0.
 *
 * So a settle timer writes the exact target once the animation's own duration
 * has passed, whether a single frame was painted or none. When frames do run
 * it lands on the same value the last frame already set, and React drops the
 * no-op render.
 *
 * `prefers-reduced-motion` skips the animation entirely.
 */
const START_FALLBACK_MS = 400

// A little past the animation's own duration, so the settle only ever lands
// after the frames would have.
const SETTLE_GRACE_MS = 80

export default function AnimatedNumber({ value, format = (n) => Math.round(n).toString(), duration = 1.2, className }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  const [started, setStarted] = useState(false)
  const [display, setDisplay] = useState(0)
  const rafRef = useRef()

  useEffect(() => {
    if (inView) {
      setStarted(true)
      return undefined
    }
    const timer = setTimeout(() => setStarted(true), START_FALLBACK_MS)
    return () => clearTimeout(timer)
  }, [inView])

  useEffect(() => {
    if (!started) return undefined

    const target = Number.isFinite(value) ? value : 0

    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced || duration <= 0) {
      setDisplay(target)
      return undefined
    }

    const start = performance.now()
    const from = 0
    const ease = (t) => 1 - Math.pow(1 - t, 3) // easeOutCubic

    const tick = (now) => {
      const p = Math.min((now - start) / 1000 / duration, 1)
      // Land on the exact target rather than the eased approximation.
      setDisplay(p >= 1 ? target : from + (target - from) * ease(p))
      if (p < 1) rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)

    const settle = setTimeout(() => setDisplay(target), duration * 1000 + SETTLE_GRACE_MS)

    return () => {
      cancelAnimationFrame(rafRef.current)
      clearTimeout(settle)
    }
  }, [started, value, duration])

  return (
    <span ref={ref} className={className}>
      {format(display)}
    </span>
  )
}

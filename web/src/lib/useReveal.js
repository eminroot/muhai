import { useEffect, useRef, useState } from 'react'
import { useInView } from 'framer-motion'

/**
 * "Has this element been revealed yet?" — for scroll-triggered chart animations.
 *
 * Wraps framer-motion's `useInView` with a guarantee: it always turns true.
 * IntersectionObserver does not fire reliably in embedded or iframed contexts
 * (previews, screenshot capture, some webviews), and a chart whose line
 * animates in from `pathLength: 0` stays *invisible* when the trigger never
 * arrives. A blank chart is a far worse failure than one that animates a
 * fraction of a second early, so a fallback timer forces the reveal.
 *
 * @returns {[React.RefObject, boolean]} ref to attach, and whether to animate.
 */
const FALLBACK_MS = 400

export function useReveal(options = { once: true, margin: '-60px' }) {
  const ref = useRef(null)
  const inView = useInView(ref, options)
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    if (inView) {
      setRevealed(true)
      return undefined
    }
    const timer = setTimeout(() => setRevealed(true), FALLBACK_MS)
    return () => clearTimeout(timer)
  }, [inView])

  return [ref, revealed]
}

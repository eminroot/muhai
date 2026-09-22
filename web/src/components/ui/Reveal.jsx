import { motion } from 'framer-motion'
import { useReveal } from '../../lib/useReveal.js'

/**
 * Scroll-reveal wrapper — use this instead of framer-motion's `whileInView`.
 *
 * `whileInView` is driven by IntersectionObserver, which does not fire in
 * embedded or iframed contexts (previews, screenshot capture, some webviews).
 * When it never fires the element stays at its `initial` variant, and since
 * every variant here starts at `opacity: 0` that renders as a *blank section*
 * rather than an un-animated one. `useReveal` guarantees the reveal with a
 * fallback timer, so the content is always eventually visible (N6 / F13).
 *
 * Closes the same bug the charts had, for the marketing page.
 */
export default function Reveal({ as = 'div', children, ...rest }) {
  const [ref, revealed] = useReveal({ once: true, margin: '-60px' })
  const Comp = motion[as] ?? motion.div

  return (
    <Comp ref={ref} initial="hidden" animate={revealed ? 'show' : 'hidden'} {...rest}>
      {children}
    </Comp>
  )
}

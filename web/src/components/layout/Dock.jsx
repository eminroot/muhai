/**
 * A magnifying dock, in the macOS manner.
 *
 * Ported from the motion-primitives Dock to a plain-CSS setup: same physics,
 * same tooltip behaviour, no Tailwind. Each item's width is a spring driven by
 * how far the pointer is from its centre, so the row swells around the cursor
 * and settles back on its own.
 *
 * Needs `framer-motion`, and dock.css alongside it. Drop both into any React
 * app — there are no imports from the host project.
 *
 *   <Dock>
 *     <DockItem href="/" active onClick={follow('/')}>
 *       <DockLabel>Overview</DockLabel>
 *       <DockIcon><LayoutGrid strokeWidth={1.75} /></DockIcon>
 *     </DockItem>
 *     <span className="dock-sep" aria-hidden="true" />
 *     <DockItem onClick={toggleTheme} aria-label="Switch theme">
 *       <DockLabel>Dark mode</DockLabel>
 *       <DockIcon><Moon strokeWidth={1.75} /></DockIcon>
 *     </DockItem>
 *   </Dock>
 */

import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
  useTransform,
} from 'framer-motion';
import {
  Children,
  cloneElement,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

const DEFAULT_SIZE = 44;
const DEFAULT_MAGNIFICATION = 74;
const DEFAULT_DISTANCE = 140;
const SPRING = { mass: 0.1, stiffness: 170, damping: 13 };

const DockContext = createContext(null);

function useDock() {
  const context = useContext(DockContext);
  if (!context) throw new Error('Dock parts must be used inside a <Dock>');
  return context;
}

/** True while the query matches, and it keeps matching as the window changes. */
function useMediaQuery(query) {
  const [matches, setMatches] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const sync = () => setMatches(media.matches);
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, [query]);

  return matches;
}

export function Dock({ children, className = '', spring = SPRING }) {
  const mouseX = useMotionValue(Infinity);

  // Below the breakpoint the bar scrolls sideways and there is no pointer to
  // magnify towards, so the tiles shrink and hold one size.
  const compact = useMediaQuery('(max-width: 760px)');
  const size = compact ? 38 : DEFAULT_SIZE;
  const magnification = compact ? 38 : DEFAULT_MAGNIFICATION;
  const distance = compact ? 90 : DEFAULT_DISTANCE;

  const value = useMemo(
    () => ({ mouseX, spring, magnification, distance, size }),
    [mouseX, spring, magnification, distance, size],
  );

  return (
    <div className="dock-rail">
      <motion.div
        className={`dock ${className}`.trim()}
        style={{ height: size + 16 }}
        role="toolbar"
        aria-label="Primary navigation"
        onMouseMove={(event) => mouseX.set(event.clientX)}
        onMouseLeave={() => mouseX.set(Infinity)}
      >
        <DockContext.Provider value={value}>{children}</DockContext.Provider>
      </motion.div>
    </div>
  );
}

/**
 * One tile. Given an `href` it is a real anchor — middle-click and copy-link
 * keep working — and otherwise a button, so a dock full of destinations plus
 * one toggle still reads correctly to a screen reader.
 */
export function DockItem({ children, className = '', active = false, href, ...rest }) {
  const ref = useRef(null);
  const { mouseX, spring, magnification, distance, size } = useDock();
  const isHovered = useMotionValue(0);

  const mouseDistance = useTransform(mouseX, (value) => {
    const rect = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 };
    return value - rect.x - rect.width / 2;
  });

  const widthTransform = useTransform(
    mouseDistance,
    [-distance, 0, distance],
    [size, magnification, size],
  );
  const width = useSpring(widthTransform, spring);

  const Tag = href ? motion.a : motion.button;

  return (
    <Tag
      ref={ref}
      href={href}
      type={href ? undefined : 'button'}
      style={{ width, height: width }}
      onHoverStart={() => isHovered.set(1)}
      onHoverEnd={() => isHovered.set(0)}
      onFocus={() => isHovered.set(1)}
      onBlur={() => isHovered.set(0)}
      className={`dock-item${active ? ' active' : ''} ${className}`.trim()}
      aria-current={href && active ? 'page' : undefined}
      {...rest}
    >
      {Children.map(children, (child) =>
        child ? cloneElement(child, { width, isHovered }) : child,
      )}
    </Tag>
  );
}

export function DockLabel({ children, isHovered }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!isHovered) return undefined;
    return isHovered.on('change', (latest) => setVisible(latest === 1));
  }, [isHovered]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          role="tooltip"
          className="dock-label"
          initial={{ opacity: 0, y: 6, scale: 0.94 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 6, scale: 0.94 }}
          transition={{ duration: 0.16, ease: [0.22, 0.8, 0.3, 1] }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function DockIcon({ children, width }) {
  // The glyph tracks the tile at a fixed ratio, so magnifying the tile
  // magnifies the icon with it rather than leaving it stranded in the middle.
  const iconSize = useTransform(width, (value) => value * 0.42);

  return (
    <motion.span className="dock-icon" style={{ width: iconSize, height: iconSize }}>
      {children}
    </motion.span>
  );
}

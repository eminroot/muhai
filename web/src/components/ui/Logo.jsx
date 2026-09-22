/**
 * The Muhai mark — an "M" ruled like a ledger bracket, with the decimal point
 * that follows every figure in the app.
 *
 * Drawn in `currentColor` so the same file works white-on-ink in the chrome
 * and ink-on-paper everywhere else.
 */
export default function Logo({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path
        d="M7 23V9.5C7 9.22 7.22 9 7.5 9C7.66 9 7.8 9.07 7.9 9.2L13.6 16.4C13.8 16.66 14.2 16.66 14.4 16.4L20.1 9.2C20.2 9.07 20.34 9 20.5 9C20.78 9 21 9.22 21 9.5V23"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="24" cy="22.5" r="2" fill="currentColor" />
    </svg>
  )
}

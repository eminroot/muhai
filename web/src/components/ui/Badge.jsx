const TONE = {
  green: 'badge--green',
  amber: 'badge--amber',
  red: 'badge--red',
  gray: 'badge--gray',
  sky: 'badge--sky',
}

export default function Badge({ tone = 'gray', dot = true, children }) {
  return (
    <span className={`badge ${TONE[tone] || TONE.gray}`}>
      {dot && <span className="badge__dot" style={{ background: 'currentColor' }} />}
      {children}
    </span>
  )
}

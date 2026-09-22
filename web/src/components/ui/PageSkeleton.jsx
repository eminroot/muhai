/** Shimmer placeholder shown while the workspace loads. */
export default function PageSkeleton({ rows = 4 }) {
  return (
    <div className="page">
      <div className="skel skel--title" />
      <div className="skel skel--sub" />
      <div className="skel skel--band" style={{ marginTop: 26 }} />
      <div style={{ display: 'grid', gap: 18, marginTop: 18 }}>
        {Array.from({ length: rows - 3 || 1 }).map((_, i) => (
          <div key={i} className="skel skel--panel" />
        ))}
      </div>
    </div>
  )
}

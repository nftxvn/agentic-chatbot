import './SourceReference.css'

function SourceReference({ sources }) {
  if (!sources || sources.length === 0) return null

  return (
    <div className="source-references">
      <span className="source-label">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
        Sumber Referensi
      </span>
      <div className="source-badges">
        {sources.map((src, idx) => (
          <span key={idx} className="source-badge" title={src.doc_name}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {src.doc_name}
            {src.page != null && (
              <span className="source-page">hal. {src.page}</span>
            )}
          </span>
        ))}
      </div>
    </div>
  )
}

export default SourceReference

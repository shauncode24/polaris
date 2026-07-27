import './ResumeHeader.css'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function scoreBadgeClass(score) {
  if (score == null) return ''
  if (score >= 75) return 'rh__badge--score'
  if (score >= 50) return 'rh__badge--score warn'
  return 'rh__badge--score danger'
}

function FileIcon() {
  return (
    <svg viewBox="0 0 40 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="48" rx="6" fill="var(--accent-soft)" />
      <path d="M8 14h18l8 8v20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V16a2 2 0 0 1 2-2z" fill="var(--surface)" stroke="var(--border)" strokeWidth="1" />
      <path d="M26 14v8h8" stroke="var(--border)" strokeWidth="1" fill="none" />
      <text x="12" y="34" fill="var(--accent)" fontSize="8" fontWeight="700" fontFamily="sans-serif">PDF</text>
    </svg>
  )
}

export default function ResumeHeader({ workspace, onUpload, onReview, reviewLoading, uploadInputRef }) {
  const { current_resume, latest_review, ats_flags = [], versions = [] } = workspace
  const score = latest_review?.overall_score
  const atsPassed = ats_flags.filter(f => f.severity !== 'low').length === 0

  return (
    <div className="rh">
      <div className="rh__left">
        <div className="rh__file-icon">
          <FileIcon />
        </div>
        <div className="rh__meta">
          <div className="rh__filename">{current_resume.filename}</div>
          <div className="rh__sub">
            <span>Uploaded {formatDate(current_resume.created_at)}</span>
            {versions.length > 1 && (
              <>
                <span className="rh__sep" />
                <span>{versions.length} versions</span>
              </>
            )}
          </div>
          <div className="rh__badges">
            {versions.length > 0 && (
              <span className="rh__badge rh__badge--version">
                {versions[0]?.version || 'v1'} (current)
              </span>
            )}
            {score != null && (
              <span className={`rh__badge ${scoreBadgeClass(score)}`}>
                ★ {score}/100 review score
              </span>
            )}
            <span className={`rh__badge rh__badge--ats`}
              style={{
                background: atsPassed ? 'var(--success-soft)' : 'var(--warning-soft)',
                color: atsPassed ? 'var(--success)' : 'var(--warning)',
              }}
            >
              {atsPassed ? '✓ ATS checks passed' : `${ats_flags.filter(f => f.severity !== 'low').length} ATS flags`}
            </span>
          </div>
        </div>
      </div>

      <div className="rh__right">
        <input
          ref={uploadInputRef}
          type="file"
          accept=".pdf,.docx"
          hidden
          onChange={(e) => onUpload(e.target.files?.[0])}
        />
        <button
          type="button"
          className="rh__btn"
          onClick={() => uploadInputRef.current?.click()}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 15V4" /><path d="M7.5 8.5L12 4l4.5 4.5" />
            <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
          </svg>
          Re-upload
        </button>
        <button
          type="button"
          className="rh__btn rh__btn--primary"
          onClick={onReview}
          disabled={reviewLoading}
        >
          {reviewLoading ? (
            <>
              <span style={{ width: 12, height: 12, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
              Reviewing…
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
              </svg>
              Run Review
            </>
          )}
        </button>
      </div>
    </div>
  )
}

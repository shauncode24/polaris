import './ResumeHeader.css'

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}


export default function ResumeHeader({
  workspace,
  onUpload,
  onReview,
  reviewLoading,
  onAnalyze,
  analyzeLoading,
  uploadInputRef,
  showPreview,
  onTogglePreview,
}) {
  const { current_resume, latest_analysis, latest_review, ats_flags = [], versions = [] } = workspace
  const analysisScore = latest_analysis?.overall_score
  const reviewScore = latest_review?.overall_score
  const atsPassed = ats_flags.filter(f => f.severity !== 'low').length === 0

  const atsScore = latest_analysis?.overall_score ?? null


  function getScoreTone(score) {
    if (score == null) return ''
    if (score >= 75) return 'strong'
    if (score >= 50) return 'partial'
    return 'weak'
  }

  return (
    <div className="rh">
      <div className="rh__left">
        <div className="rh__meta" style={{ paddingLeft: 0 }}>
          <div className="rh__filename-row">
            <div className="rh__filename">{current_resume.filename}</div>
            {versions.length > 0 && (
              <span className="rh__version-badge">
                {versions[0]?.version || 'v1'}
              </span>
            )}
          </div>
          <div className="rh__sub">
            <span>Uploaded {formatDate(current_resume.created_at)}</span>
            {versions.length > 1 && (
              <>
                <span className="rh__sep" />
                <span>{versions.length} versions</span>
              </>
            )}
          </div>
        </div>

        <div className="rh__divider" />

        <div className="rh__stats-strip">
          <div className={`rh__stat-item rh__stat-item--primary tone-${getScoreTone(atsScore)}`}>
            <span className="rh__stat-val">{atsScore != null ? `${atsScore}` : '—'}</span>
            <span className="rh__stat-lbl">ATS SCORE</span>
          </div>

          {reviewScore != null && (
            <div className={`rh__stat-item tone-${getScoreTone(reviewScore)}`}>
              <span className="rh__stat-val">{reviewScore}</span>
              <span className="rh__stat-lbl">AI REVIEW</span>
            </div>
          )}

          {analysisScore != null && (
            <div className={`rh__stat-item tone-${getScoreTone(analysisScore)}`}>
              <span className="rh__stat-val">{analysisScore}</span>
              <span className="rh__stat-lbl">ANALYSIS</span>
            </div>
          )}
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
          className={`rh__btn ${showPreview ? 'rh__btn--active' : ''}`}
          onClick={onTogglePreview}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          {showPreview ? 'Hide Preview' : 'Resume Preview'}
        </button>

        <button
          type="button"
          className="rh__btn rh__btn--primary"
          onClick={onReview}
          disabled={reviewLoading}
        >
          {reviewLoading ? 'Reviewing…' : 'AI Review'}
        </button>

        <button
          type="button"
          className="rh__btn rh__btn--primary"
          onClick={() => onAnalyze()}
          disabled={analyzeLoading}
        >
          {analyzeLoading ? (
            <>
              <span style={{ width: 12, height: 12, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
              Analyzing…
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
              </svg>
              Run Analysis
            </>
          )}
        </button>
      </div>
    </div>
  )
}

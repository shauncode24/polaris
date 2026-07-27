import { IconDocument, IconGithub, IconCode } from '../icons/Icons'
import { IconAward } from '../icons/OnboardingIcons'
import Button from '../common/Button'
import './onboarding-shared.css'
import './ReviewStep.css'

function ReviewRow({ icon: Icon, title, badge, badgeTone = 'info', sub, onEdit, editLabel = 'Edit' }) {
  return (
    <div className="onb-card review-row">
      <div className="review-row__main">
        <span className="review-row__icon"><Icon size={18} /></span>
        <div>
          <div className="review-row__title-line">
            <span className="review-row__title">{title}</span>
            {badge && <span className={`onb-badge onb-badge--${badgeTone}`}>{badge}</span>}
          </div>
          {sub && <div className="review-row__sub">{sub}</div>}
        </div>
      </div>
      <button type="button" className="onb-link-btn" onClick={onEdit}>✎ {editLabel}</button>
    </div>
  )
}

function ReviewStep({ resume, github, leetcode, certificates, goal, onEditStep, onFinish }) {
  return (
    <div>
      <p className="onb-eyebrow">Step 6 of 6 · Review</p>
      <h1 className="onb-title">Anything look wrong?</h1>
      <p className="onb-lead">
        Here's everything we've built. Fix or re-sync any section before we take you in — you can
        also change all of this later from your dashboard.
      </p>

      <div className="review-rows">
        <ReviewRow
          icon={IconDocument} title="Resume"
          badge={resume ? 'Uploaded' : undefined} badgeTone="success"
          onEdit={() => onEditStep(1)}
        />
        <ReviewRow
          icon={IconGithub} title="GitHub"
          badge={github ? 'Synced' : undefined} badgeTone="success"
          sub={github ? `${github.summary.repos_synced} repos · top project ${
            [...github.repositories].sort((a, b) => (b.project_score?.overall || 0) - (a.project_score?.overall || 0))[0]?.name || '—'
          }` : undefined}
          editLabel="Re-sync"
          onEdit={() => onEditStep(2)}
        />
        <ReviewRow
          icon={IconCode} title="LeetCode"
          badge={leetcode ? 'Added' : undefined} badgeTone="success"
          sub={leetcode ? `${leetcode.summary?.total_solved ?? 0} solved across ${
            (leetcode.insights?.topic_mastery || []).filter((t) => t.problems > 0).length
          } topics` : undefined}
          editLabel="Re-sync"
          onEdit={() => onEditStep(3)}
        />
        <ReviewRow
          icon={IconAward} title="Certificates"
          badge={certificates.length > 0 ? String(certificates.length) : undefined} badgeTone="info"
          sub={certificates.map((c) => c.name).join(', ') || undefined}
          onEdit={() => onEditStep(4)}
        />
        <ReviewRow
          icon={IconAward} title="Target goal"
          badge={goal?.role ? 'Set' : undefined} badgeTone="info"
          sub={goal?.role ? `${goal.role}${goal.company ? ` at ${goal.company}` : ''}${goal.date ? ` · by ${goal.date}` : ''}` : undefined}
          onEdit={() => onEditStep(5)}
        />
      </div>

      <div className="onb-footer" style={{ justifyContent: 'flex-end' }}>
        <Button variant="primary" onClick={onFinish}>Looks good — go to dashboard →</Button>
      </div>
    </div>
  )
}

export default ReviewStep
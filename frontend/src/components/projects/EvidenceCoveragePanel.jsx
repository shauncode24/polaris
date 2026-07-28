import InfoCard from '../common/InfoCard'
import { IconWorkflow } from '../icons/Icons'
import './EvidenceCoveragePanel.css'

function Row({ label, done, detail }) {
  return (
    <div className="evidence-coverage__row">
      <span className={`evidence-coverage__mark ${done ? 'is-done' : ''}`}>{done ? '✓' : ''}</span>
      <span className="evidence-coverage__label">{label}</span>
      <span className="evidence-coverage__detail">{detail}</span>
    </div>
  )
}

function EvidenceCoveragePanel({ coverage, interviewReadyCount }) {
  const resumeCount = coverage?.resume_uploads ?? 0
  const repoCount = coverage?.connected_repositories ?? 0
  const capCount = coverage?.capabilities_evidenced ?? 0

  return (
    <InfoCard icon={IconWorkflow} iconTone="accent" title="Evidence Coverage">
      <div className="evidence-coverage__list">
        <Row label="Resume" done={resumeCount > 0} detail={resumeCount > 0 ? `${resumeCount} project(s)` : 'Not linked'} />
        <Row label="GitHub" done={repoCount > 0} detail={repoCount > 0 ? `${repoCount} repos` : 'Not synced'} />
        <Row label="Skills" done={capCount > 0} detail={capCount > 0 ? `${capCount} evidenced` : 'None yet'} />
        <Row
          label="Interview Ready"
          done={(interviewReadyCount ?? 0) > 0}
          detail={`${interviewReadyCount ?? 0} project(s)`}
        />
      </div>
    </InfoCard>
  )
}

export default EvidenceCoveragePanel
import InfoCard from '../common/InfoCard'
import { IconWorkflow } from '../icons/Icons'
import './SourceCoveragePanel.css'

function SourceCoveragePanel({ coverage }) {
  const items = [
    {
      label: 'Resume',
      value: `${coverage?.resume_uploads ?? 0} project${coverage?.resume_uploads === 1 ? '' : 's'} represented`,
    },
    { label: 'GitHub', value: `${coverage?.connected_repositories ?? 0} repositories connected` },
    { label: 'Skills', value: `${coverage?.capabilities_evidenced ?? 0} capabilities evidenced` },
  ]

  return (
    <InfoCard icon={IconWorkflow} iconTone="accent" title="Source coverage">
      <div className="source-coverage__list">
        {items.map((item) => (
          <div className="source-coverage__row" key={item.label}>
            <span className="source-coverage__label">{item.label}</span>
            <span className="source-coverage__value">{item.value}</span>
          </div>
        ))}
      </div>
    </InfoCard>
  )
}

export default SourceCoveragePanel
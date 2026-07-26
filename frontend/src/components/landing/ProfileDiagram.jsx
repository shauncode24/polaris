import { IconDocument, IconGithub, IconCode, IconUser, IconBriefcase, IconFlag, IconMic } from '../icons/Icons'
import './ProfileDiagram.css'

const OUTER_NODES = [
  { icon: IconDocument, label: 'Resume', x: 14, y: 20 },
  { icon: IconGithub, label: 'GitHub', x: 50, y: 12 },
  { icon: IconCode, label: 'LeetCode', x: 86, y: 20 },
  { icon: IconBriefcase, label: 'Job Descriptions', x: 14, y: 82 },
  { icon: IconFlag, label: 'Career Goals', x: 50, y: 90 },
  { icon: IconMic, label: 'Interview History', x: 86, y: 82 },
]

const CENTER = { x: 50, y: 51 }

// Three straight lines through the center — Resume<->Interview History,
// LeetCode<->Job Descriptions, GitHub<->Career Goals — instead of six
// separate spokes. Matches the asterisk pattern in the reference design.
const LINES = [
  [OUTER_NODES[0], OUTER_NODES[5]],
  [OUTER_NODES[2], OUTER_NODES[3]],
  [OUTER_NODES[1], OUTER_NODES[4]],
]

function ProfileDiagram() {
  return (
    <section className="profile-diagram">
      <div className="container">
        <h2 className="profile-diagram__heading">Polaris builds a living profile from</h2>

        <div className="profile-diagram__canvas">
          <svg className="profile-diagram__lines" viewBox="0 0 100 100" preserveAspectRatio="none">
            {LINES.map(([a, b]) => (
              <line key={`${a.label}-${b.label}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
            ))}
          </svg>

          {OUTER_NODES.map(({ icon: Icon, label, x, y }) => (
            <div className="profile-diagram__node" key={label} style={{ left: `${x}%`, top: `${y}%` }}>
              <span className="profile-diagram__node-icon">
                <Icon size={18} />
              </span>
              <span className="profile-diagram__node-label">{label}</span>
            </div>
          ))}

          <div
            className="profile-diagram__node profile-diagram__node--center"
            style={{ left: `${CENTER.x}%`, top: `${CENTER.y}%` }}
          >
            <span className="profile-diagram__node-icon profile-diagram__node-icon--center">
              <IconUser size={20} />
            </span>
            <span className="profile-diagram__node-label profile-diagram__node-label--strong">Profile</span>
          </div>
        </div>

        <p className="profile-diagram__caption">Everything contributes to one profile.</p>
      </div>
    </section>
  )
}

export default ProfileDiagram

import { useState } from 'react'
import EvidenceList from './EvidenceList'
import LineEditor from './LineEditor'

const TITLES = {
  summary: 'Summary',
  experience: 'Experience',
  projects: 'Projects',
  education: 'Education',
  skills: 'Skills',
}

function hasContent(document, section) {
  return section === 'summary' ? Boolean(document.summary) : document[section].length > 0
}

// The wording stated in the evidence; a date without any is shown by month.
function dateText(text, date) {
  if (text) return text
  if (!date) return ''
  return new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}

function dateRange(entry) {
  const start = dateText(entry.start_date_text, entry.start_date)
  const end = dateText(entry.end_date_text, entry.end_date) || (entry.is_current ? 'Present' : '')
  return [start, end].filter(Boolean).join(' – ')
}

function Entry({ title, subtitle, dates, entry, lineProps, evidence }) {
  const [showEvidence, setShowEvidence] = useState(false)
  return (
    <div className="tr-entry">
      <div className="tr-entry__head">
        <div>
          <h4>{title}</h4>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <div className="tr-entry__side">
          {dates && <span>{dates}</span>}
          <button type="button" aria-expanded={showEvidence} onClick={() => setShowEvidence((shown) => !shown)}>
            {showEvidence ? 'Hide source' : 'Source'}
          </button>
        </div>
      </div>
      {showEvidence && <EvidenceList sources={entry.sources} evidence={evidence} />}
      {entry.bullets.length > 0 && (
        <ul className="tr-lines">
          {entry.bullets.map((line) => <LineEditor key={line.id} {...lineProps(line)} />)}
        </ul>
      )}
    </div>
  )
}

function Skills({ skills, evidence }) {
  const [open, setOpen] = useState(null) // the canonical name whose evidence is shown
  const selected = skills.find((skill) => skill.canonical === open)
  return (
    <>
      <p className="tr-hint">Select a skill to see its evidence.</p>
      <div className="tr-skills">
        {skills.map((skill) => (
          <button
            type="button"
            key={skill.canonical}
            className="tr-skill"
            aria-pressed={skill.canonical === open}
            onClick={() => setOpen(skill.canonical === open ? null : skill.canonical)}
          >
            {skill.name}
          </button>
        ))}
      </div>
      {selected && <EvidenceList sources={selected.sources} evidence={evidence} />}
    </>
  )
}

function SectionBody({ section, document, evidence, lineProps }) {
  if (section === 'summary') {
    return <ul className="tr-lines"><LineEditor {...lineProps(document.summary)} /></ul>
  }
  if (section === 'skills') {
    return <Skills skills={document.skills} evidence={evidence} />
  }
  return document[section].map((entry, index) => {
    const heading = {
      experience: () => ({ title: entry.role, subtitle: entry.company, dates: dateRange(entry) }),
      projects: () => ({ title: entry.name, subtitle: entry.technologies.join(', ') }),
      education: () => ({
        title: entry.institution,
        subtitle: [entry.degree, entry.field_of_study].filter(Boolean).join(', '),
        dates: dateRange(entry),
      }),
    }[section]()
    const key = `${entry.sources[0].id}-${index}`
    return <Entry key={key} {...heading} entry={entry} evidence={evidence} lineProps={lineProps} />
  })
}

// The sections that have something in them, in the document's order, each of
// which can be moved up or down.
export default function ResumeSections({ document, evidence, busy, lineProps, onReorder }) {
  const visible = document.section_order.filter((section) => hasContent(document, section))

  function move(section, step) {
    const other = visible[visible.indexOf(section) + step]
    onReorder(document.section_order.map((name) => {
      if (name === section) return other
      return name === other ? section : name
    }))
  }

  if (visible.length === 0) {
    return (
      <p className="tr-hint">
        There is nothing to put on this resume yet. Upload your resume or sync GitHub on your profile,
        then generate a new version.
      </p>
    )
  }

  return visible.map((section, index) => (
    <section className="tr-section" key={section}>
      <div className="tr-section__head">
        <h3>{TITLES[section]}</h3>
        <div>
          <button
            type="button"
            aria-label={`Move ${TITLES[section]} up`}
            title="Move up"
            disabled={busy || index === 0}
            onClick={() => move(section, -1)}
          >
            ↑
          </button>
          <button
            type="button"
            aria-label={`Move ${TITLES[section]} down`}
            title="Move down"
            disabled={busy || index === visible.length - 1}
            onClick={() => move(section, 1)}
          >
            ↓
          </button>
        </div>
      </div>
      <SectionBody section={section} document={document} evidence={evidence} lineProps={lineProps} />
    </section>
  ))
}

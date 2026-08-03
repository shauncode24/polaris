import './PracticeDiversity.css'

function PracticeDiversity({ diversity }) {
  if (!diversity) return null

  const { new_topics_touched, is_grinding, message, total_new_solves } = diversity

  return (
    <section className="lc-card">
      <h3>Practice diversity</h3>

      {total_new_solves === 0 ? (
        <p className="lc-empty-text">{message}</p>
      ) : (
        <>
          <p className={`pd-message ${is_grinding ? 'pd-message--warn' : 'pd-message--good'}`}>{message}</p>
          {new_topics_touched.length > 0 && (
            <div className="pd-pills">
              {new_topics_touched.slice(0, 3).map((t) => <span key={t} className="pd-pill">+ {t}</span>)}
            </div>
          )}
        </>
      )}
    </section>
  )
}

export default PracticeDiversity
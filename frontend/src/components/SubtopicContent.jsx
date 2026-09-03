import React, { useState, useEffect } from 'react'
import SubtopicNotes from './notes/SubtopicNotes.jsx'
import { getNotesForSubtopic, getQuestionCount } from '../api/content.js'
import { Link } from 'react-router-dom'

function ContentList({ title, items, numbered = false }) {
  if (!items || !items.length) return null
  return (
    <section className={`content-section ${numbered ? 'outcome-section' : 'notes-section'}`}>
      <h2>{title}</h2>
      {numbered ? (
        <ol className="outcome-list">
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <p>{item}</p>
            </li>
          ))}
        </ol>
      ) : (
        <ul className="notes-list">
          {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      )}
    </section>
  )
}

export default function SubtopicContent({ subtopic }) {
  const topicNumber = subtopic.code.split('.')[0]
  const [notesData, setNotesData] = useState(null)
  const [questionCount, setQuestionCount] = useState(0)
  const [notesLoading, setNotesLoading] = useState(true)
  const [notesError, setNotesError] = useState('')
  const hasNotes = Boolean(notesData && notesData.sections?.length)
  const [activeTab, setActiveTab] = useState('notes')

  useEffect(() => {
    let cancelled = false
    setNotesData(null)
    setNotesLoading(true)
    setNotesError('')
    Promise.all([
      getNotesForSubtopic(subtopic.code),
      getQuestionCount(topicNumber).catch(() => 0),
    ])
      .then(([notes, count]) => {
        if (cancelled) return
        setNotesData(notes)
        setQuestionCount(count)
        setActiveTab(notes?.sections?.length ? 'notes' : 'syllabus')
      })
      .catch((error) => {
        if (cancelled) return
        setNotesError(error.message)
        setActiveTab('syllabus')
      })
      .finally(() => {
        if (!cancelled) setNotesLoading(false)
      })
    return () => { cancelled = true }
  }, [subtopic.code, topicNumber])

  return (
    <article className="subtopic-content">
      <header className="detail-heading">
        <p>{subtopic.code}</p>
        <h1>{subtopic.title}</h1>

        <div className="subtopic-tabs-nav" role="tablist" aria-label="Subtopic view mode">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'notes'}
            className={`subtopic-tab-btn ${activeTab === 'notes' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('notes')}
          >
            <span>Revision Notes</span>
            {(hasNotes || notesLoading) && (
              <span className="tab-count-badge">
                {notesLoading ? '…' : `${notesData.sections.reduce((acc, s) => acc + s.pages.length, 0)} pages`}
              </span>
            )}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'syllabus'}
            className={`subtopic-tab-btn ${activeTab === 'syllabus' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('syllabus')}
          >
            <span>Syllabus Spec</span>
          </button>
          <Link className="subtopic-tab-btn" to={`/topic/${topicNumber}/practice`}>
            <span>Practice Questions</span>
            <span className="tab-count-badge">{questionCount || 'Soon'}</span>
          </Link>
        </div>
      </header>

      {activeTab === 'notes' ? (
        <SubtopicNotes notesData={notesData} subtopic={subtopic} />
      ) : (
        <>
          {notesError && <p role="status">Revision notes could not be loaded from the content API.</p>}
          <ContentList title="Learning outcomes" items={subtopic.outcomes} numbered />
          <ContentList title="Notes and examples" items={subtopic.notes} />
        </>
      )}
    </article>
  )
}

import React, { useState, useEffect } from 'react'
import SubtopicNotes from './notes/SubtopicNotes.jsx'
import { getNotesForSubtopic } from '../data/notes/index.js'
import { getQuestionCount } from '../data/questions/index.js'
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
  const notesData = getNotesForSubtopic(subtopic.code)
  const topicNumber = subtopic.code.split('.')[0]
  const questionCount = getQuestionCount(topicNumber)
  const hasNotes = Boolean(notesData && notesData.sections?.length)
  const [activeTab, setActiveTab] = useState(hasNotes ? 'notes' : 'syllabus')

  useEffect(() => {
    setActiveTab(hasNotes ? 'notes' : 'syllabus')
  }, [subtopic.code, hasNotes])

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
            {hasNotes && (
              <span className="tab-count-badge">
                {notesData.sections.reduce((acc, s) => acc + s.pages.length, 0)} pages
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
          <ContentList title="Learning outcomes" items={subtopic.outcomes} numbered />
          <ContentList title="Notes and examples" items={subtopic.notes} />
        </>
      )}
    </article>
  )
}

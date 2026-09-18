import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getQuestionCount } from '../api/content.js'

export default function SyllabusSidebar({ topic, activeCode }) {
  const navigate = useNavigate()
  const [questionCount, setQuestionCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    getQuestionCount(topic.number)
      .then((count) => { if (!cancelled) setQuestionCount(count) })
      .catch(() => { if (!cancelled) setQuestionCount(0) })
    return () => { cancelled = true }
  }, [topic.number])
  return (
    <>
      <div className="mobile-selector">
        <label htmlFor="subtopic-select">Subtopic</label>
        <select
          id="subtopic-select"
          value={activeCode || ''}
          onChange={(event) => navigate(event.target.value === 'practice' ? `/topic/${topic.number}/practice` : event.target.value ? `/topic/${topic.number}/${event.target.value}` : `/topic/${topic.number}`)}
        >
          <option value="">{topic.number.padStart(2, '0')} · {topic.title} overview</option>
          {topic.subtopics.map((subtopic) => <option key={subtopic.code} value={subtopic.code}>{subtopic.code} {subtopic.title}</option>)}
          <option value="practice">Practice questions</option>
        </select>
      </div>

      <aside className="syllabus-sidebar" id="syllabus-sidebar" aria-label={`${topic.title} subtopics`}>
        <div className="sidebar-heading">
          <span>{topic.number.padStart(2, '0')}</span>
          <Link to={`/topic/${topic.number}`} aria-current={!activeCode ? 'page' : undefined}>{topic.title}</Link>
        </div>
        <nav>
          {topic.subtopics.map((subtopic) => (
            <Link
              key={subtopic.code}
              to={`/topic/${topic.number}/${subtopic.code}`}
              className={activeCode === subtopic.code ? 'active' : ''}
              aria-current={activeCode === subtopic.code ? 'page' : undefined}
              aria-label={`${subtopic.code} ${subtopic.title}`}
              title={`${subtopic.code} ${subtopic.title}`}
            >
              <span>{subtopic.code}</span>
              <span className="sidebar-link-title">{subtopic.title}</span>
            </Link>
          ))}
          <Link to={`/topic/${topic.number}/practice`} className={activeCode === 'practice' ? 'active practice-sidebar-link' : 'practice-sidebar-link'} aria-current={activeCode === 'practice' ? 'page' : undefined} aria-label="Practice questions" title="Practice questions">
            <span>{questionCount || '—'}</span>
            <span className="sidebar-link-title">Practice questions</span>
          </Link>
        </nav>
      </aside>
    </>
  )
}

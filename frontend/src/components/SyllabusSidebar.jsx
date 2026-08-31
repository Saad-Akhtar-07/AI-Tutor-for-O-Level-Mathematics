import { Link, useNavigate } from 'react-router-dom'

export default function SyllabusSidebar({ topic, activeCode }) {
  const navigate = useNavigate()
  return (
    <>
      <div className="mobile-selector">
        <label htmlFor="subtopic-select">Subtopic</label>
        <select
          id="subtopic-select"
          value={activeCode || ''}
          onChange={(event) => navigate(event.target.value === 'practice' ? '/topic/8/practice' : event.target.value ? `/topic/${topic.number}/${event.target.value}` : `/topic/${topic.number}`)}
        >
          <option value="">{topic.number.padStart(2, '0')} · {topic.title} overview</option>
          {topic.subtopics.map((subtopic) => <option key={subtopic.code} value={subtopic.code}>{subtopic.code} {subtopic.title}</option>)}
          {topic.number === '8' && <option value="practice">Practice questions</option>}
        </select>
      </div>

      <aside className="syllabus-sidebar" aria-label={`${topic.title} subtopics`}>
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
            >
              <span>{subtopic.code}</span>
              {subtopic.title}
            </Link>
          ))}
          {topic.number === '8' && (
            <Link to="/topic/8/practice" className={activeCode === 'practice' ? 'active practice-sidebar-link' : 'practice-sidebar-link'} aria-current={activeCode === 'practice' ? 'page' : undefined}>
              <span>20</span>
              Practice questions
            </Link>
          )}
        </nav>
      </aside>
    </>
  )
}

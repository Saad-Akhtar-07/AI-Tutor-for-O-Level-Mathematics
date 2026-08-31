import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Breadcrumbs({ topic, subtopic }) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        <li><Link to="/">Syllabus</Link></li>
        <li><ChevronRight size={14} aria-hidden="true" /></li>
        <li>
          {subtopic ? <Link to={`/topic/${topic.number}`}>{topic.number} {topic.title}</Link> : <span aria-current="page">{topic.number} {topic.title}</span>}
        </li>
        {subtopic && <>
          <li><ChevronRight size={14} aria-hidden="true" /></li>
          <li><span aria-current="page">{subtopic.code} {subtopic.title}</span></li>
        </>}
      </ol>
    </nav>
  )
}

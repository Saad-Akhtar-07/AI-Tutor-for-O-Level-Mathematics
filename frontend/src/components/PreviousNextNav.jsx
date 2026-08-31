import { ArrowLeft, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { syllabus } from '../data/syllabus.js'

const flattened = syllabus.flatMap((topic) => topic.subtopics.map((subtopic) => ({ topic, subtopic })))

export default function PreviousNextNav({ code }) {
  const index = flattened.findIndex((item) => item.subtopic.code === code)
  const previous = flattened[index - 1]
  const next = flattened[index + 1]

  const pathFor = (item) => `/topic/${item.topic.number}/${item.subtopic.code}`

  return (
    <nav className="previous-next" aria-label="Previous and next subtopics">
      {previous ? (
        <Link to={pathFor(previous)} className="previous-link">
          <span><ArrowLeft size={16} /> Previous</span>
          <strong>{previous.subtopic.code} {previous.subtopic.title}</strong>
        </Link>
      ) : <span />}
      {next && (
        <Link to={pathFor(next)} className="next-link">
          <span>Next <ArrowRight size={16} /></span>
          <strong>{next.subtopic.code} {next.subtopic.title}</strong>
        </Link>
      )}
    </nav>
  )
}

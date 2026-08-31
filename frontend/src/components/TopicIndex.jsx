import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function TopicIndex({ topics }) {
  return (
    <div className="topic-index">
      {topics.map((topic) => (
        <article className="topic-index-item" key={topic.number}>
          <div className="topic-number">{topic.number.padStart(2, '0')}</div>
          <div className="topic-heading">
            <h3><Link to={`/topic/${topic.number}`}>{topic.title}</Link></h3>
            <p>{topic.subtopics.length} subtopics</p>
          </div>
          <ol className="topic-preview">
            {topic.subtopics.slice(0, 5).map((subtopic) => (
              <li key={subtopic.code}>
                <span>{subtopic.code}</span>
                <Link to={`/topic/${topic.number}/${subtopic.code}`}>{subtopic.title}</Link>
              </li>
            ))}
            {topic.subtopics.length > 5 && <li className="preview-more">+ {topic.subtopics.length - 5} more</li>}
          </ol>
          <Link className="topic-link" to={`/topic/${topic.number}`}>
            View topic <ArrowUpRight size={16} aria-hidden="true" />
          </Link>
        </article>
      ))}
    </div>
  )
}

import { ArrowRight } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import Breadcrumbs from '../components/Breadcrumbs.jsx'
import SyllabusSidebar from '../components/SyllabusSidebar.jsx'
import { getQuestionCount } from '../data/questions/index.js'
import { syllabus } from '../data/syllabus.js'
import NotFound from './NotFound.jsx'

export default function TopicPage() {
  const { topicNumber } = useParams()
  const topic = syllabus.find((item) => item.number === topicNumber)
  const questionCount = getQuestionCount(topicNumber)

  useEffect(() => {
    if (topic) document.title = `${topic.number} ${topic.title} · Mathematics 4024`
    window.scrollTo(0, 0)
  }, [topic])

  if (!topic) return <NotFound />

  return (
    <main className="reader-shell" id="main-content" tabIndex="-1">
      <SyllabusSidebar topic={topic} />
      <div className="reader-main">
        <Breadcrumbs topic={topic} />
        <header className="topic-page-heading">
          <p>{topic.number.padStart(2, '0')}</p>
          <h1>{topic.title}</h1>
          <span>Cambridge syllabus content · {topic.subtopics.length} subtopics</span>
          <Link className="topic-practice-link" to={`/topic/${topic.number}/practice`}>
            {questionCount ? `Open ${questionCount} practice questions` : 'Open practice workspace'} <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </header>
        <section className="subtopic-directory" aria-labelledby="subtopics-heading">
          <h2 id="subtopics-heading">Subtopics</h2>
          {topic.subtopics.map((subtopic) => (
            <Link key={subtopic.code} to={`/topic/${topic.number}/${subtopic.code}`}>
              <span>{subtopic.code}</span>
              <div>
                <h3>{subtopic.title}</h3>
                <p>{subtopic.outcomes[0]}</p>
              </div>
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          ))}
        </section>
      </div>
    </main>
  )
}

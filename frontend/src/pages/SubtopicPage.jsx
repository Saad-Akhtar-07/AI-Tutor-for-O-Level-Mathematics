import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import Breadcrumbs from '../components/Breadcrumbs.jsx'
import PreviousNextNav from '../components/PreviousNextNav.jsx'
import SubtopicContent from '../components/SubtopicContent.jsx'
import SyllabusSidebar from '../components/SyllabusSidebar.jsx'
import { syllabus } from '../data/syllabus.js'
import NotFound from './NotFound.jsx'

export default function SubtopicPage() {
  const { topicNumber, subtopicNumber } = useParams()
  const topic = syllabus.find((item) => item.number === topicNumber)
  const subtopic = topic?.subtopics.find((item) => item.code === subtopicNumber)

  useEffect(() => {
    if (subtopic) document.title = `${subtopic.code} ${subtopic.title} · Mathematics 4024`
    window.scrollTo(0, 0)
  }, [subtopic])

  if (!topic || !subtopic) return <NotFound />

  return (
    <main className="reader-shell" id="main-content" tabIndex="-1">
      <SyllabusSidebar topic={topic} activeCode={subtopic.code} />
      <div className="reader-main">
        <Breadcrumbs topic={topic} subtopic={subtopic} />
        <SubtopicContent subtopic={subtopic} />
        <PreviousNextNav code={subtopic.code} />
      </div>
    </main>
  )
}

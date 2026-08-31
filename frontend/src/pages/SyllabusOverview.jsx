import { useEffect } from 'react'
import TopicIndex from '../components/TopicIndex.jsx'
import VersionNotice from '../components/VersionNotice.jsx'
import { syllabus } from '../data/syllabus.js'

export default function SyllabusOverview() {
  useEffect(() => {
    document.title = 'O Level Mathematics 4024 · Syllabus Explorer'
    window.scrollTo(0, 0)
  }, [])

  return (
    <main id="main-content" tabIndex="-1">
      <section className="overview-hero">
        <div className="overview-kicker">O Level Mathematics</div>
        <h1>Cambridge Mathematics<br />(Syllabus D) 4024</h1>
        <p>A structured view of the syllabus for examinations in<br className="desktop-break" /> 2025, 2026 and 2027.</p>
        <VersionNotice />
      </section>

      <section className="syllabus-index-section" aria-labelledby="explore-heading">
        <div className="section-intro">
          <p>Subject content</p>
          <h2 id="explore-heading">Explore the syllabus</h2>
          <span>{syllabus.length} topics · {syllabus.reduce((sum, topic) => sum + topic.subtopics.length, 0)} subtopics</span>
        </div>
        <TopicIndex topics={syllabus} />
      </section>
    </main>
  )
}

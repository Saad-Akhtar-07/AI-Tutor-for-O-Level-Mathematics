import { Route, Routes } from 'react-router-dom'
import AppHeader from './components/AppHeader.jsx'
import SyllabusOverview from './pages/SyllabusOverview.jsx'
import TopicPage from './pages/TopicPage.jsx'
import SubtopicPage from './pages/SubtopicPage.jsx'
import NotFound from './pages/NotFound.jsx'
import QuestionPracticePage from './pages/QuestionPracticePage.jsx'

export default function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <AppHeader />
      <Routes>
        <Route path="/" element={<SyllabusOverview />} />
        <Route path="/topic/:topicNumber" element={<TopicPage />} />
        <Route path="/topic/:topicNumber/practice" element={<QuestionPracticePage />} />
        <Route path="/topic/:topicNumber/:subtopicNumber" element={<SubtopicPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  )
}

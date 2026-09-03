import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import AppHeader from './components/AppHeader.jsx'

const SyllabusOverview = lazy(() => import('./pages/SyllabusOverview.jsx'))
const TopicPage = lazy(() => import('./pages/TopicPage.jsx'))
const SubtopicPage = lazy(() => import('./pages/SubtopicPage.jsx'))
const QuestionPracticePage = lazy(() => import('./pages/QuestionPracticePage.jsx'))
const NotFound = lazy(() => import('./pages/NotFound.jsx'))

function RouteLoadingState() {
  return (
    <main className="reader-main" id="main-content" tabIndex="-1">
      <p role="status">Loading page…</p>
    </main>
  )
}

export default function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <AppHeader />
      <Suspense fallback={<RouteLoadingState />}>
        <Routes>
          <Route path="/" element={<SyllabusOverview />} />
          <Route path="/topic/:topicNumber" element={<TopicPage />} />
          <Route path="/topic/:topicNumber/practice" element={<QuestionPracticePage />} />
          <Route path="/topic/:topicNumber/:subtopicNumber" element={<SubtopicPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </div>
  )
}

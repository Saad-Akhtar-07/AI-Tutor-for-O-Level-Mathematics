import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <main className="not-found" id="main-content" tabIndex="-1">
      <p>404</p>
      <h1>This syllabus page could not be found.</h1>
      <Link to="/"><ArrowLeft size={16} /> Return to the syllabus</Link>
    </main>
  )
}

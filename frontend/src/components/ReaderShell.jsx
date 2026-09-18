import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import SyllabusSidebar from './SyllabusSidebar.jsx'
import './ReaderShell.css'

// Keep the existing preference when moving between lessons and practice.
const SIDEBAR_STORAGE_KEY = 'practice-sidebar-collapsed-v1'

function storedSidebarCollapsed() {
  try { return localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true' }
  catch { return false }
}

export default function ReaderShell({ topic, activeCode, className = '', children }) {
  const [collapsed, setCollapsed] = useState(storedSidebarCollapsed)
  useEffect(() => {
    try { localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed)) }
    catch { /* The sidebar can still toggle without browser storage. */ }
  }, [collapsed])

  const label = collapsed ? 'Expand syllabus sidebar' : 'Collapse syllabus sidebar'
  return <main className={`reader-shell collapsible-reader-shell ${className}${collapsed ? ' is-sidebar-collapsed' : ''}`} id="main-content" tabIndex="-1">
    <div className="reader-sidebar">
      <SyllabusSidebar topic={topic} activeCode={activeCode} />
      <button type="button" className="sidebar-edge-toggle" aria-label={label} title={label} aria-expanded={!collapsed} aria-controls="syllabus-sidebar" onClick={() => setCollapsed(value => !value)}>
        {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>
    </div>
    {children}
  </main>
}

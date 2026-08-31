import { Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { syllabus } from '../data/syllabus.js'
import ThemeToggle from './ThemeToggle.jsx'

const searchableItems = syllabus.flatMap((topic) => [
  { label: topic.title, code: topic.number, type: 'Topic', path: `/topic/${topic.number}` },
  ...topic.subtopics.map((subtopic) => ({
    label: subtopic.title,
    code: subtopic.code,
    type: topic.title,
    path: `/topic/${topic.number}/${subtopic.code}`,
  })),
])

export default function AppHeader() {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const location = useLocation()
  const navigate = useNavigate()
  const searchRef = useRef(null)
  const searchContainerRef = useRef(null)

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return []
    return searchableItems.filter((item) => `${item.code} ${item.label}`.toLowerCase().includes(normalized)).slice(0, 8)
  }, [query])

  useEffect(() => {
    setQuery('')
    setOpen(false)
    setActiveIndex(-1)
  }, [location.pathname])

  useEffect(() => {
    const handleKeyDown = (event) => {
      const target = event.target
      const isTyping = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable
      if (event.key === '/' && !isTyping) {
        event.preventDefault()
        searchRef.current?.focus()
        setOpen(true)
      }
      if (event.key === 'Escape') {
        setOpen(false)
        searchRef.current?.blur()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (!searchContainerRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [])

  useEffect(() => setActiveIndex(-1), [query])

  const handleSearchKeyDown = (event) => {
    if (!results.length) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActiveIndex((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      navigate(results[activeIndex >= 0 ? activeIndex : 0].path)
    }
  }

  const syllabusIsCurrent = location.pathname === '/' || location.pathname.startsWith('/topic/')

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" to="/" aria-label="O Level Mathematics 4024 syllabus home">
          <span className="brand-mark">4024</span>
          <span className="brand-name">O Level Mathematics</span>
        </Link>

        <nav className="header-nav" aria-label="Primary navigation">
          <Link to="/" aria-current={syllabusIsCurrent ? 'page' : undefined}>Syllabus</Link>
          <span className="version-label">Version 2</span>
        </nav>

        <div className="header-search" role="search" ref={searchContainerRef}>
          <Search aria-hidden="true" size={16} />
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setOpen(true) }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search syllabus"
            aria-label="Search topics and subtopics"
            aria-expanded={open && query.length > 0}
            aria-controls="syllabus-search-results"
            aria-autocomplete="list"
            aria-activedescendant={activeIndex >= 0 ? `search-result-${activeIndex}` : undefined}
            role="combobox"
          />
          {query ? (
            <button className="search-clear" type="button" aria-label="Clear search" onClick={() => { setQuery(''); setOpen(true); searchRef.current?.focus() }}>
              <X size={15} />
            </button>
          ) : <kbd aria-hidden="true">/</kbd>}

          {open && query && (
            <div className="search-results" id="syllabus-search-results" role="listbox" aria-label="Search results">
              {results.length ? results.map((result, index) => (
                <Link
                  id={`search-result-${index}`}
                  key={result.path}
                  to={result.path}
                  className={`search-result ${index === activeIndex ? 'is-active' : ''}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  onMouseEnter={() => setActiveIndex(index)}
                  onFocus={() => setActiveIndex(index)}
                >
                  <span className="search-code">{result.code}</span>
                  <span>
                    <strong>{result.label}</strong>
                    <small>{result.type}</small>
                  </span>
                </Link>
              )) : (
                <p className="search-empty">No matching topics or subtopics.</p>
              )}
            </div>
          )}
        </div>

        <ThemeToggle />
        <span className="years-label">2025–2027</span>
      </div>
    </header>
  )
}

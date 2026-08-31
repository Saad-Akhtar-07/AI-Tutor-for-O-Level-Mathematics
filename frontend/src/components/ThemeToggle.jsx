import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

function getInitialTheme() {
  if (typeof document === 'undefined') return 'light'
  return document.documentElement.dataset.theme || 'light'
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(getInitialTheme)
  const nextTheme = theme === 'light' ? 'dark' : 'light'

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    try { localStorage.setItem('syllabus-theme', theme) } catch { /* Theme still works for this session. */ }
  }, [theme])

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={() => setTheme(nextTheme)}
      aria-label={`Switch to ${nextTheme} mode`}
      title={`Switch to ${nextTheme} mode`}
    >
      {theme === 'light' ? <Moon size={17} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
      <span>{theme === 'light' ? 'Dark' : 'Light'}</span>
    </button>
  )
}

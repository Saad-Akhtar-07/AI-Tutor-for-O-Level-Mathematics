import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

export default function VersionNotice() {
  const [open, setOpen] = useState(false)
  return (
    <section className={`version-notice ${open ? 'is-open' : ''}`} aria-labelledby="version-notice-title">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-controls="version-changes">
        <span className="version-dot" aria-hidden="true" />
        <span>
          <strong id="version-notice-title">Version 2</strong>
          <small>February 2024</small>
        </span>
        <ChevronDown size={17} aria-hidden="true" />
      </button>
      {open && (
        <div className="version-content" id="version-changes">
          <h3>Changes in Version 2</h3>
          <ul>
            <li>The term <code>prism</code> was clarified in the notes and guidance for 5.4.</li>
            <li>Expectations for drawing reciprocal and exponential graphs were clarified in 2.11.</li>
            <li>The term <code>random</code> was added to the guidance for 8.2.2.</li>
          </ul>
        </div>
      )}
    </section>
  )
}

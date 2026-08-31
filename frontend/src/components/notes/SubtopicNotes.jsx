import { BookOpenText, FileText, Layers3 } from 'lucide-react'
import React from 'react'
import NoteBlockRenderer from './NoteBlockRenderer.jsx'

export default function SubtopicNotes({ notesData, subtopic }) {
  if (!notesData || !notesData.sections || notesData.sections.length === 0) {
    return (
      <div className="notes-empty-state">
        <p className="empty-kicker">Study & Revision Notes</p>
        <h3>Notes in Preparation</h3>
        <p>
          Detailed step-by-step revision notes for <strong>{subtopic.code} {subtopic.title}</strong> are
          being formatted according to the Cambridge 4024 specification.
        </p>
      </div>
    )
  }

  const totalPages = notesData.sections.reduce((total, section) => total + section.pages.length, 0)
  const totalBlocks = notesData.sections.reduce(
    (total, section) => total + section.pages.reduce((pageTotal, page) => pageTotal + page.blocks.length, 0),
    0,
  )

  return (
    <div className="subtopic-notes-viewer">
      <header className="notes-study-header">
        <div className="notes-study-heading">
          <span className="notes-study-icon"><BookOpenText size={22} aria-hidden="true" /></span>
          <div>
            <p>Probability study guide</p>
            <h2>{subtopic.code} {subtopic.title}</h2>
            <span>Structured explanations, worked examples, examiner guidance and KaTeX mathematics.</span>
          </div>
        </div>
        <div className="notes-study-stats" aria-label="Study guide summary">
          <div><FileText size={17} aria-hidden="true" /><strong>{totalPages}</strong><span>pages</span></div>
          <div><Layers3 size={17} aria-hidden="true" /><strong>{totalBlocks}</strong><span>content blocks</span></div>
          <div><BookOpenText size={17} aria-hidden="true" /><strong>{notesData.sections.length}</strong><span>{notesData.sections.length === 1 ? 'source' : 'sources'}</span></div>
        </div>
      </header>

      <nav className="notes-page-index" aria-label="Study guide pages">
        <span>Jump to</span>
        <div>
          {notesData.sections.flatMap((section, sectionIndex) => section.pages.map((page) => (
            <a key={`${sectionIndex}-${page.page_number}`} href={`#note-${subtopic.code}-${sectionIndex}-${page.page_number}`}>
              {notesData.sections.length > 1 ? `${sectionIndex + 1}.` : ''}{page.page_number}
            </a>
          )))}
        </div>
      </nav>

      {notesData.sections.map((section, sIdx) => {
        return (
          <section key={`sec-${sIdx}`} className="note-source-section">
              <div className="source-section-header">
                <div>
                  <span className="source-part-label">Source {sIdx + 1}</span>
                <h2 className="source-title">{section.source_label || section.document_title}</h2>
                </div>
                <span className="source-page-count">{section.pages.length} {section.pages.length === 1 ? 'page' : 'pages'}</span>
              </div>

            <div className="note-pages-container">
              {section.pages.map((page) => {
                return (
                  <article
                    key={`p-${page.page_number}`}
                    id={`note-${subtopic.code}-${sIdx}-${page.page_number}`}
                    className="note-page-content"
                  >
                    <div className="note-page-label"><span>Source page</span><strong>{page.page_number}</strong></div>
                    <div className="note-blocks-list">
                      {page.blocks.map((block, bIdx) => (
                        <NoteBlockRenderer
                          key={`b-${page.page_number}-${bIdx}`}
                          block={block}
                          index={bIdx}
                        />
                      ))}
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        )
      })}
    </div>
  )
}

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

  return (
    <div className="subtopic-notes-viewer">
      {notesData.sections.map((section, sIdx) => {
        return (
          <section key={`sec-${sIdx}`} className="note-source-section">
            {notesData.sections.length > 1 && (
              <div className="source-section-header">
                <span className="source-part-label">Part {sIdx + 1}</span>
                <h2 className="source-title">{section.source_label || section.document_title}</h2>
              </div>
            )}

            <div className="note-pages-container">
              {section.pages.map((page) => {
                return (
                  <article key={`p-${page.page_number}`} className="note-page-content">
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

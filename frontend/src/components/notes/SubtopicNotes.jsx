import { BookOpenText, Calculator, Lightbulb } from 'lucide-react'
import React from 'react'
import NoteBlockRenderer, { renderHeadingText } from './NoteBlockRenderer.jsx'

function normaliseText(value = '') {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

function slugify(value = '') {
  return normaliseText(value).replace(/\s+/g, '-')
}

function isLessonHeading(block, text) {
  if (block.type !== 'heading' || block.level > 2) return false
  return !/^(contents|answer:?|method\s*\d*:?)$/i.test(text.trim())
    && !/^(examiner tips?( and tricks)?|worked example)$/i.test(text.trim())
}

function prepareSection(section, sectionIndex) {
  const sectionTitle = section.source_label || section.document_title || `Chapter ${sectionIndex + 1}`
  const hasOpeningContents = section.pages[0]?.blocks.some(
    (block) => block.type === 'heading' && /^contents$/i.test(renderHeadingText(block.content).trim()),
  )
  const entries = []
  const topics = []
  const usedAnchors = new Map()
  let skippingContents = false
  let checkedOpeningTitle = false

  section.pages.forEach((page) => {
    page.blocks.forEach((block, blockIndex) => {
      const headingText = block.type === 'heading' ? renderHeadingText(block.content).trim() : ''

      if (block.type === 'heading' && /^contents$/i.test(headingText)) {
        skippingContents = true
        return
      }

      if (skippingContents) {
        if (block.type !== 'heading') return
        skippingContents = false
      }

      if (!checkedOpeningTitle && block.type === 'heading') {
        checkedOpeningTitle = true
        if (hasOpeningContents || normaliseText(headingText) === normaliseText(sectionTitle)) return
      }

      let anchorId
      if (isLessonHeading(block, headingText)) {
        const base = `lesson-${sectionIndex + 1}-${slugify(headingText) || topics.length + 1}`
        const duplicateCount = usedAnchors.get(base) || 0
        usedAnchors.set(base, duplicateCount + 1)
        anchorId = duplicateCount ? `${base}-${duplicateCount + 1}` : base
        topics.push({ id: anchorId, title: headingText })
      }

      entries.push({
        block,
        anchorId,
        key: `s${sectionIndex}-p${page.page_number}-b${blockIndex}`,
      })
    })
  })

  return { ...section, sectionTitle, entries, topics }
}

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

  const preparedSections = notesData.sections.map(prepareSection)
  const allBlocks = preparedSections.flatMap((section) => section.entries.map((entry) => entry.block))
  const lessonTopics = preparedSections.flatMap((section) => section.topics)
  const workedExamples = allBlocks.filter((block) => block.type === 'heading' && /worked\s+example/i.test(renderHeadingText(block.content))).length
  const examinerTips = allBlocks.filter((block) => block.type === 'heading' && /examiner\s+tips?/i.test(renderHeadingText(block.content))).length

  return (
    <div className="subtopic-notes-viewer">
      <header className="notes-study-header">
        <div className="notes-study-heading">
          <span className="notes-study-icon"><BookOpenText size={22} aria-hidden="true" /></span>
          <div>
            <p>Probability study guide</p>
            <h2>{subtopic.code} {subtopic.title}</h2>
            <span>Learn the key ideas, follow worked examples, then apply them in practice.</span>
          </div>
        </div>
        <div className="notes-study-stats" aria-label="Study guide summary">
          <div><BookOpenText size={17} aria-hidden="true" /><strong>{lessonTopics.length}</strong><span>key concepts</span></div>
          <div><Calculator size={17} aria-hidden="true" /><strong>{workedExamples}</strong><span>worked examples</span></div>
          <div><Lightbulb size={17} aria-hidden="true" /><strong>{examinerTips}</strong><span>examiner tips</span></div>
        </div>
      </header>

      {lessonTopics.length > 0 && (
        <nav className="notes-lesson-outline" aria-label="Lesson outline">
          <div className="lesson-outline-heading">
            <span>Lesson outline</span>
            <p>Choose a concept or read straight through.</p>
          </div>
          <div className="lesson-outline-links">
            {lessonTopics.map((topic, index) => (
              <a key={topic.id} href={`#${topic.id}`}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <strong>{topic.title}</strong>
              </a>
            ))}
          </div>
        </nav>
      )}

      {preparedSections.map((section, sectionIndex) => (
        <section key={`section-${sectionIndex}`} className="note-source-section">
          <div className="source-section-header">
            <div>
              <span className="source-part-label">
                {preparedSections.length > 1 ? `Chapter ${sectionIndex + 1}` : 'Study chapter'}
              </span>
              <h2 className="source-title">{section.sectionTitle}</h2>
            </div>
            <span className="source-page-count">
              {section.topics.length} {section.topics.length === 1 ? 'concept' : 'concepts'}
            </span>
          </div>

          <article className="note-lesson-content">
            {section.entries.map((entry, index) => (
              <NoteBlockRenderer
                key={entry.key}
                block={entry.block}
                index={index}
                anchorId={entry.anchorId}
              />
            ))}
          </article>
        </section>
      ))}
    </div>
  )
}

import React from 'react'
import InlineContent from './InlineContent.jsx'
import MathRenderer from './MathRenderer.jsx'

export function renderHeadingText(content) {
  if (!content) return ''
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content
      .map((c) => (c.type === 'text' ? c.text : c.latex || ''))
      .join('')
  }
  return ''
}

export default function NoteBlockRenderer({ block, index = 0 }) {
  if (!block) return null

  switch (block.type) {
    case 'heading': {
      const headingText = renderHeadingText(block.content)
      const isExaminerTip = /examiner\s+tips?/i.test(headingText)
      const isWorkedExample = /worked\s+example/i.test(headingText)
      const isAnswer = /^answer/i.test(headingText)

      const Tag = block.level === 1 ? 'h2' : block.level === 2 ? 'h3' : 'h4'

      return (
        <div
          className={`note-heading-wrapper level-${block.level} ${
            isExaminerTip ? 'is-examiner-tip-header' : ''
          } ${isWorkedExample ? 'is-worked-example-header' : ''} ${
            isAnswer ? 'is-answer-header' : ''
          }`}
        >
          {isExaminerTip && <span className="note-badge tip-badge">Examiner Tip</span>}
          {isWorkedExample && <span className="note-badge example-badge">Worked Example</span>}
          {isAnswer && <span className="note-badge answer-badge">Solution Step</span>}
          <Tag className={`note-heading note-h${block.level}`}>
            <InlineContent content={block.content} />
          </Tag>
        </div>
      )
    }

    case 'paragraph': {
      const pText = renderHeadingText(block.content)
      const isAnswerLabel = /^(Answer|Method\s+\d+):?$/i.test(pText.trim())
      return (
        <p className={`note-paragraph ${isAnswerLabel ? 'note-step-label' : ''}`}>
          <InlineContent content={block.content} />
        </p>
      )
    }

    case 'math': {
      return (
        <div className="note-math-card">
          <MathRenderer latex={block.latex} display={block.display !== false} />
        </div>
      )
    }

    case 'bullet_list': {
      return (
        <ul className="note-list note-bullet-list">
          {block.items.map((item, i) => (
            <li key={`bullet-${i}`}>
              <div className="list-item-content">
                <InlineContent content={item.content} />
              </div>
              {item.children && item.children.length > 0 && (
                <ul className="note-sublist">
                  {item.children.map((sub, j) => (
                    <li key={`bullet-${i}-${j}`}>
                      <InlineContent content={sub.content} />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )
    }

    case 'numbered_list': {
      return (
        <ol className="note-list note-numbered-list">
          {block.items.map((item, i) => (
            <li key={`num-${i}`}>
              <div className="list-item-content">
                <InlineContent content={item.content} />
              </div>
              {item.children && item.children.length > 0 && (
                <ol className="note-sublist">
                  {item.children.map((sub, j) => (
                    <li key={`num-${i}-${j}`}>
                      <InlineContent content={sub.content} />
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ol>
      )
    }

    case 'table': {
      const rows = block.rows || []
      if (!rows.length) return null

      return (
        <div className="note-table-container">
          <table className="note-table">
            <tbody>
              {rows.map((row, rIdx) => {
                const isHeader = row.is_header || rIdx === 0
                return (
                  <tr key={`r-${rIdx}`} className={isHeader ? 'table-header-row' : 'table-body-row'}>
                    {row.cells.map((cell, cIdx) => {
                      const CellTag = isHeader ? 'th' : 'td'
                      return (
                        <CellTag key={`c-${rIdx}-${cIdx}`} className="note-table-cell">
                          {cell.blocks && cell.blocks.length > 0 ? (
                            cell.blocks.map((b, bIdx) => (
                              <NoteBlockRenderer key={`tb-${rIdx}-${cIdx}-${bIdx}`} block={b} />
                            ))
                          ) : (
                            <span>&nbsp;</span>
                          )}
                        </CellTag>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )
    }

    case 'figure': {
      return (
        <figure className="note-figure-card">
          <div className="figure-header">
            <span className="figure-type-tag">{block.figure_type || 'Diagram'}</span>
            {block.caption && <span className="figure-caption">{block.caption}</span>}
          </div>
          <div className="figure-body">
            <p className="figure-desc">{block.description}</p>
          </div>
        </figure>
      )
    }

    default:
      return null
  }
}

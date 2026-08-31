import React from 'react'
import MathRenderer from './MathRenderer.jsx'

/**
 * Parses a string that may contain embedded $...$ inline LaTeX expressions.
 */
function renderMixedText(text, keyPrefix) {
  if (!text || typeof text !== 'string') return text

  // Split on $...$ patterns
  const parts = text.split(/(\$[^$]+\$)/g)
  if (parts.length === 1) return text

  return parts.map((part, i) => {
    if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
      const mathContent = part.slice(1, -1)
      return <MathRenderer key={`${keyPrefix}-m-${i}`} latex={mathContent} display={false} />
    }
    return <React.Fragment key={`${keyPrefix}-t-${i}`}>{part}</React.Fragment>
  })
}

export default function InlineContent({ content }) {
  if (!content) return null

  if (typeof content === 'string') {
    return <>{renderMixedText(content, 's')}</>
  }

  if (!Array.isArray(content)) return null

  return (
    <>
      {content.map((node, index) => {
        if (!node) return null
        if (node.type === 'text') {
          return (
            <React.Fragment key={`inline-${index}`}>
              {renderMixedText(node.text, `n-${index}`)}
            </React.Fragment>
          )
        }
        if (node.type === 'math') {
          return <MathRenderer key={`inline-${index}`} latex={node.latex} display={false} />
        }
        return null
      })}
    </>
  )
}

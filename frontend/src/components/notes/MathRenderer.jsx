import React, { useMemo } from 'react'
import katex from 'katex'

export default function MathRenderer({ latex, display = false, className = '' }) {
  const html = useMemo(() => {
    if (!latex) return ''
    try {
      return katex.renderToString(latex.trim(), {
        throwOnError: false,
        displayMode: display,
        strict: false,
        output: 'htmlAndMathml',
      })
    } catch (err) {
      console.warn('KaTeX rendering error:', err, 'LaTeX:', latex)
      return null
    }
  }, [latex, display])

  if (!html) {
    return <code className={`latex-fallback ${className}`}>{latex}</code>
  }

  if (display) {
    return (
      <div
        className={`math-display-wrapper ${className}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    )
  }

  return (
    <span
      className={`math-inline-wrapper ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

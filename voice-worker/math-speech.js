import katex from 'katex'
import sre from 'speech-rule-engine'

await sre.setupEngine({ locale: 'en', domain: 'mathspeak', style: 'default' })
await sre.engineReady()
export const NORMALIZER_VERSION = '2'
const MATH_CHECK = 'Please check the mathematical expression shown in the text.'

// Parse plain expressions before rendering: a slash must keep its operands.
export function plainToLatex(input) {
  const source = input.replaceAll('²', '^2').replaceAll('³', '^3').replaceAll('−', '-')
    .replaceAll('×', '*').replaceAll('÷', '/').replaceAll('≤', '<=').replaceAll('≥', '>=')
    .replaceAll('≠', '!=').replaceAll('∩', '&').replaceAll('∪', '@')
  const tokens = source.match(/sqrt|\d+(?:\.\d+)?|[A-Za-z]|<=|>=|!=|[+*/^=<>(),|!%:&@'{}_-]/g) || []
  if (tokens.join('') !== source.replace(/\s/g, '')) throw new Error('Unsupported expression')
  let i = 0
  const precedence = { '=': 1, '<': 1, '>': 1, '<=': 1, '>=': 1, '!=': 1, '|': 2, '@': 3, '&': 3, '+': 4, '-': 4, '*': 5, '/': 5, ':': 5, '^': 6 }
  const symbols = { '<=': '\\le', '>=': '\\ge', '!=': '\\ne', '|': '\\mid', '@': '\\cup', '&': '\\cap', '*': '\\times', ':': ':' }
  function expression(min = 0) {
    const token = tokens[i++]
    let left
    if (token === '-' || token === '+') left = token + expression(6)
    else if (token === 'sqrt') {
      if (tokens[i++] !== '(') throw new Error('Square root needs brackets')
      left = '\\sqrt{' + expression() + '}'
      if (tokens[i++] !== ')') throw new Error('Unclosed square root')
    } else if (token === '(' || token === '{') {
      left = '\\left(' + expression() + '\\right)'
      if (tokens[i++] !== (token === '(' ? ')' : '}')) throw new Error('Unclosed group')
    } else if (/^(?:\d+(?:\.\d+)?|[A-Za-z])$/.test(token || '')) {
      left = token
      if (token === 'P' && tokens[i] === '(') {
        i++
        left = '\\operatorname{probability}\\left(' + expression() + '\\right)'
        if (tokens[i++] !== ')') throw new Error('Unclosed probability')
      }
    } else throw new Error('Missing operand')
    while (i < tokens.length) {
      const op = tokens[i]
      if (['%', '!', "'"].includes(op)) { i++; left = `{${left}}${op === '%' ? '\\%' : op === "'" ? '^{\\mathrm{complement}}' : op}`; continue }
      if (op === '_') { i++; left = `{${left}}_{${expression(7)}}`; continue }
      const implicit = /^(?:[A-Za-z]|\()$/.test(op)
      const level = implicit ? 5 : precedence[op]
      if (level === undefined || level < min) break
      if (!implicit) i++
      const right = expression(level + (op === '^' ? 0 : 1))
      left = op === '/' ? `\\frac{${left}}{${right}}` : op === '^' ? `{${left}}^{${right}}` : `${left} ${implicit ? '\\,' : symbols[op] || op} ${right}`
    }
    return left
  }
  const result = expression()
  if (i !== tokens.length) throw new Error('Unexpected token')
  return result
}

export function speakMath(expression, latex = false) {
  const tex = (latex ? expression : plainToLatex(expression)).replace(/\bP\s*(?=\\left\(|\()/g, '\\operatorname{probability}')
  const markup = katex.renderToString(tex, { output: 'mathml', throwOnError: true, trust: false, strict: 'error', maxExpand: 100 })
  const mathml = markup.match(/<math[\s\S]*?<\/math>/)?.[0]
  if (!mathml) throw new Error('No maths representation')
  const digits = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
  return sre.toSpeech(mathml).replace(/\b(\d+)\.(\d+)/g, (_, whole, fraction) => `${whole === '0' ? 'zero' : whole} point ${[...fraction].map(digit => digits[Number(digit)]).join(' ')}`)
    .replace(/StartFraction/g, 'the fraction').replace(/Over/g, 'over').replace(/EndFraction/g, 'end fraction')
    .replace(/left parenthesis/gi, 'open bracket').replace(/right parenthesis/gi, 'close bracket')
    .replace(/Superscript/gi, 'to the power of').replace(/Baseline/gi, 'end power').replace(/percent sign/gi, 'percent')
    .replace(/probability open bracket ([\s\S]*?) close bracket/gi, (_, body) => 'probability of ' + body.replace(/vertical-bar|vertical bar/gi, 'given'))
}

// Keep sentence boundaries out of LaTeX and decimals. Chunk only validated text.
export function prepareSpeech(text) {
  let warning = false
  const protectedMath = []
  const protect = (expression, latex, unsupported = false) => {
    let speech
    if (unsupported) { warning = true; speech = MATH_CHECK }
    else {
      try { speech = speakMath(expression, latex) }
      catch { warning = true; speech = MATH_CHECK }
    }
    protectedMath.push(speech)
    return ` MATHPLACEHOLDER${protectedMath.length - 1}END `
  }
  let spoken = text.replace(/\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$|\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]/g,
    (_, a, b, c, d) => protect(a ?? b ?? c ?? d, true))
  spoken = extractPlainMath(spoken, protect)
    .replace(/MATHPLACEHOLDER(\d+)END/g, (_, index) => protectedMath[Number(index)])
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[*#`_]/g, '').replace(/\s+/g, ' ').trim()
  // Never send unhandled TeX/symbols to a voice that may confidently omit them.
  if (/[\\{}√∑∞∈∉⊂∅]/u.test(spoken)) {
    warning = true
    spoken = spoken.split(/(?<=[.!?])\s+/).map(part => /[\\{}√∑∞∈∉⊂∅]/u.test(part) ? MATH_CHECK : part).join(' ')
  }
  // Symbols, punctuation and line breaks do not start another maths block.
  // Spoken words between reminders do, so each explanation keeps its place.
  spoken = spoken.replace(/(?:Please check the mathematical expression shown in the text\.[^\p{L}\p{N}]*){2,}/gu, `${MATH_CHECK} `).trim()
  const sentences = spoken.match(/[^.!?]+(?:[.!?]+|$)/g) || [spoken]
  const segments = []
  for (const sentence of sentences) {
    if (!/[\p{L}\p{N}]/u.test(sentence)) continue
    // Bound model work even when a reply has no punctuation.
    const words = sentence.trim().split(/\s+/)
    let chunk = ''
    for (const word of words) {
      if (chunk && chunk.length + word.length > 240) { segments.push(chunk); chunk = '' }
      chunk += (chunk ? ' ' : '') + word
    }
    if (chunk) segments.push(chunk)
  }
  return { segments, warning: warning ? 'Some notation needs visual checking. The voice will identify it instead of guessing.' : null, normalizer_version: NORMALIZER_VERSION }
}

function extractPlainMath(text, protect) {
  const lexer = /\s*(sqrt|[A-Za-z]+|\d+(?:\.\d+)?|<=|>=|!=|[(){}+*/^=<>≤≥≠×÷−∩∪:|!%²³'_\-])/y
  let output = ''
  for (let start = 0; start < text.length;) {
    if (!/[A-Za-z0-9(√+\-]/.test(text[start]) || (start > 0 && /[A-Za-z0-9]/.test(text[start - 1]))) { output += text[start++]; continue }
    // Words inside a probability call label the outcomes, rather than prose
    // between expressions. Keep the whole call together if it is unsupported.
    if (text.startsWith('P(', start)) {
      let end = start + 2
      let depth = 1
      while (end < text.length && depth) {
        if (text[end] === '(') depth++
        else if (text[end] === ')') depth--
        end++
      }
      const call = text.slice(start, end)
      if (!depth && call.match(/[A-Za-z]{2,}/g)?.some(word => word !== 'sqrt')) {
        output += protect(call, false, true)
        start = end
        continue
      }
    }
    let end = start
    let tokens = 0
    while (end < text.length) {
      lexer.lastIndex = end
      const match = lexer.exec(text)
      if (!match || (/^[A-Za-z]{2,}$/.test(match[1]) && match[1] !== 'sqrt')) break
      end = lexer.lastIndex
      tokens++
    }
    const candidate = text.slice(start, end).trimEnd()
    const minusOrFactorial = tokens > 1 && ((candidate.includes('-') && !candidate.endsWith('-')) || candidate.endsWith('!'))
    if (tokens && (minusOrFactorial || /[+*/^=<>≤≥≠×÷−∩∪:|%²³_]/.test(candidate) || /^P\(/.test(candidate) || /^sqrt\(/.test(candidate) || /\d\.\d/.test(candidate))) {
      output += protect(candidate, false)
      start = end
    } else { output += text[start++]; }
  }
  return output
}

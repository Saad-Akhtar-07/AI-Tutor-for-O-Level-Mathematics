const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API_PREFIX = '/api/v1'
const REQUEST_TIMEOUT_MS = 10000

const questionBankCache = new Map()
const questionSummaryCache = new Map()
const notesCache = new Map()

async function fetchContent(path) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
    if (response.status === 404) return null
    if (!response.ok) throw new Error(`Content API request failed (${response.status})`)
    return response.json()
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Content API request timed out')
    }
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

function cachedFetch(cache, key, path) {
  if (!cache.has(key)) {
    const request = fetchContent(path).catch((error) => {
      cache.delete(key)
      throw error
    })
    cache.set(key, request)
  }
  return cache.get(key)
}

export function getQuestionBank(topicNumber) {
  const key = String(topicNumber)
  return cachedFetch(questionBankCache, key, `/topics/${encodeURIComponent(key)}/questions`)
}

export function getQuestionPartSolution(questionPartId) {
  return fetchContent(`/question-parts/${encodeURIComponent(questionPartId)}/solution`)
}

export async function getQuestionCount(topicNumber) {
  const key = String(topicNumber)
  const summary = await cachedFetch(
    questionSummaryCache,
    key,
    `/topics/${encodeURIComponent(key)}/question-summary`,
  )
  return summary?.question_count || 0
}

export function getNotesForSubtopic(code) {
  const key = String(code)
  return cachedFetch(notesCache, key, `/subtopics/${encodeURIComponent(key)}/notes`)
}

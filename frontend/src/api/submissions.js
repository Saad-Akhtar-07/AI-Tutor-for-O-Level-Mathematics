const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API_PREFIX = '/api/v1'
const REQUEST_TIMEOUT_MS = 15000
const SESSION_STORAGE_KEY = 'ai-tutor-learner-session-v1'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

let sessionPromise = null

async function apiRequest(path, options = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...options.headers,
      },
      signal: controller.signal,
    })
    if (!response.ok) {
      let message = `Request failed (${response.status})`
      try {
        const body = await response.json()
        if (typeof body.detail === 'string') message = body.detail
      } catch { /* Keep the status-based message for non-JSON errors. */ }
      const error = new Error(message)
      error.status = response.status
      throw error
    }
    if (response.status === 204) return null
    return response.json()
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Saving timed out. Please try again.')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

function storedSessionId() {
  try {
    const value = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!value || UUID_PATTERN.test(value)) return value
    localStorage.removeItem(SESSION_STORAGE_KEY)
    return null
  }
  catch { return null }
}

function rememberSession(id) {
  try { localStorage.setItem(SESSION_STORAGE_KEY, id) }
  catch { /* The session remains usable until this tab is closed. */ }
}

function forgetSession() {
  try { localStorage.removeItem(SESSION_STORAGE_KEY) }
  catch { /* Nothing else to clean up. */ }
}

async function createSession() {
  const session = await apiRequest('/learner-sessions', { method: 'POST' })
  rememberSession(session.id)
  return session.id
}

async function getSessionId() {
  const existing = storedSessionId()
  if (existing) return existing
  if (!sessionPromise) sessionPromise = createSession().finally(() => { sessionPromise = null })
  return sessionPromise
}

async function withSession(operation, canRetry = true) {
  const sessionId = await getSessionId()
  try {
    return await operation(sessionId)
  } catch (error) {
    if (canRetry && error.status === 404 && error.message === 'Learner session not found') {
      forgetSession()
      sessionPromise = null
      return withSession(operation, false)
    }
    throw error
  }
}

export function getStudentResponses(topicNumber) {
  return withSession(async (sessionId) => {
    const data = await apiRequest(`/learner-sessions/${sessionId}/responses?topic_number=${encodeURIComponent(topicNumber)}`)
    return data.responses
  })
}

export function saveStudentResponse(questionPartId, typedWork, status = 'draft') {
  return withSession((sessionId) => apiRequest(
    `/learner-sessions/${sessionId}/responses/${encodeURIComponent(questionPartId)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ typed_work: typedWork, status }),
    },
  ))
}

export function uploadSolutionImage(questionPartId, file) {
  return withSession((sessionId) => {
    const form = new FormData()
    form.append('image', file)
    return apiRequest(
      `/learner-sessions/${sessionId}/responses/${encodeURIComponent(questionPartId)}/attachments`,
      { method: 'POST', body: form },
    )
  })
}

export function removeSolutionImage(attachmentId) {
  return withSession((sessionId) => apiRequest(
    `/learner-sessions/${sessionId}/attachments/${attachmentId}`,
    { method: 'DELETE' },
  ))
}

export function attachmentContentUrl(contentUrl) {
  return `${API_BASE_URL}${contentUrl}`
}

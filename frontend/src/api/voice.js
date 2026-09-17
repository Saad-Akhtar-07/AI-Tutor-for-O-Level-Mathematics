import { getSessionId } from './submissions.js'

const BASE = (import.meta.env?.VITE_API_URL || '').replace(/\/$/, '')

export async function voiceRequest(path, body, signal, binary = false) {
  const session = await getSessionId()
  signal?.throwIfAborted()
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timer = setTimeout(abort, 22000)
  try {
    const response = await fetch(`${BASE}/api/v1/learner-sessions/${session}/voice/${path}`, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
      headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
      signal: controller.signal,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Voice is unavailable. Please try again.')
    }
    return await (binary ? response.blob() : response.json())
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('Voice took too long. Please retry or use device voice.')
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', abort)
  }
}

export function transcribeRecording(blob, partId, accurate, signal) {
  const form = new FormData()
  form.append('recording', blob, 'recording')
  form.append('question_part_id', partId)
  form.append('accurate', String(accurate))
  return voiceRequest('transcriptions', form, signal)
}

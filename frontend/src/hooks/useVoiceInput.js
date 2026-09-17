import { useEffect, useRef, useState } from 'react'
import { transcribeRecording } from '../api/voice.js'

export default function useVoiceInput(partId, beforeRecording) {
  const [state, setState] = useState('idle')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState(null)
  const [canRetry, setCanRetry] = useState(false)
  const generation = useRef(0)
  const media = useRef(null)
  const stream = useRef(null)
  const timer = useRef(null)
  const controller = useRef(null)
  const recording = useRef(null)

  function release() {
    clearInterval(timer.current)
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
  }
  function cancel() {
    generation.current++
    controller.current?.abort()
    if (media.current?.state === 'recording') media.current.stop()
    release()
    recording.current = null
    setCanRetry(false)
    setState('idle')
    setDraft(null)
    setError('')
  }
  useEffect(() => { cancel(); return cancel }, [partId]) // All late callbacks are fenced by generation.

  async function transcribe(accurate = false, version = generation.current) {
    if (!recording.current) return
    setState('transcribing')
    setError('')
    controller.current?.abort()
    controller.current = new AbortController()
    try {
      const result = await transcribeRecording(recording.current, partId, accurate, controller.current.signal)
      if (version !== generation.current) return
      setDraft(result)
    } catch (failure) {
      if (version === generation.current) setError(failure.name === 'TimeoutError' ? 'Transcription took too long. Retry the recording or type your question.' : failure.message)
    } finally { if (version === generation.current) setState('idle') }
  }
  async function start() {
    if (state !== 'idle') return
    cancel()
    beforeRecording()
    const version = generation.current
    setState('permission')
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Microphone recording needs HTTPS (or localhost) and a supported browser. You can still type.')
      const acquired = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false })
      if (version !== generation.current) { acquired.getTracks().forEach(track => track.stop()); return }
      stream.current = acquired
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(acquired, mimeType ? { mimeType } : undefined)
      media.current = recorder
      const chunks = []
      let size = 0
      recorder.ondataavailable = event => {
        if (version !== generation.current) return
        size += event.data.size
        if (size > 4 * 1024 * 1024) { cancel(); setError('Recording is too large. Please record a shorter question.'); return }
        if (event.data.size) chunks.push(event.data)
      }
      recorder.onerror = () => { if (version === generation.current) { cancel(); setError('Recording failed. Check your microphone and try again.') } }
      recorder.onstop = () => {
        if (version !== generation.current) return
        release()
        recording.current = new Blob(chunks, { type: recorder.mimeType })
        setCanRetry(true)
        transcribe(false, version)
      }
      recorder.start(250)
      setState('recording')
      setSeconds(0)
      const started = Date.now()
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000)
        setSeconds(elapsed)
        if (elapsed >= 30 && recorder.state === 'recording') recorder.stop()
      }, 200)
    } catch (failure) {
      if (version !== generation.current) return
      release()
      setState('idle')
      setError(failure.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow it in browser settings or keep typing.' : failure.message)
    }
  }
  return { state, seconds, error, draft, setDraft, canRetry, start, cancel, retry: () => transcribe(true), stop: () => { if (media.current?.state === 'recording') media.current.stop() } }
}

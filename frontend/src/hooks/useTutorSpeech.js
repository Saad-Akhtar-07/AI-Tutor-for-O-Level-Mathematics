import { useEffect, useRef, useState } from 'react'
import { voiceRequest } from '../api/voice.js'

export default function useTutorSpeech(partId) {
  const [active, setActive] = useState(null)
  const [status, setStatus] = useState('')
  const [spoken, setSpoken] = useState('')
  const [notice, setNotice] = useState('')
  const [voice, setVoice] = useState('device')
  const [speed, setSpeed] = useState(1)
  const [autoRead, setAutoRead] = useState(false)
  const run = useRef(0)
  const controller = useRef(null)
  const player = useRef(null)
  const objectUrl = useRef(null)
  const resolvePlayback = useRef(null)
  const rate = useRef(speed)
  rate.current = speed

  function stop() {
    run.current++
    controller.current?.abort()
    player.current?.pause()
    player.current = null
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
    objectUrl.current = null
    window.speechSynthesis?.cancel()
    resolvePlayback.current?.()
    resolvePlayback.current = null
    setActive(null)
    setStatus('')
    setSpoken('')
  }
  useEffect(() => { stop(); setNotice(''); return stop }, [partId])
  useEffect(() => { if (player.current) player.current.playbackRate = speed }, [speed])

  function deviceSpeak(text, version) {
    return new Promise((resolve, reject) => {
      if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) return reject(new Error('Device speech is unavailable in this browser.'))
      if (version !== run.current) return resolve()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'en-GB'
      utterance.rate = rate.current
      const voices = window.speechSynthesis.getVoices()
      utterance.voice = voices.find(v => v.lang === 'en-GB') || voices.find(v => v.lang.startsWith('en')) || null
      utterance.onend = resolve
      utterance.onerror = () => reject(new Error('Device speech could not start. Press Read aloud again.'))
      resolvePlayback.current = resolve
      window.speechSynthesis.speak(utterance)
    })
  }
  function playBlob(blob, version) {
    return new Promise((resolve, reject) => {
      if (version !== run.current) return resolve()
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
      objectUrl.current = URL.createObjectURL(blob)
      const audio = new Audio(objectUrl.current)
      player.current = audio
      audio.playbackRate = rate.current
      audio.onended = resolve
      audio.onerror = () => reject(new Error('Audio playback failed. Try device voice.'))
      resolvePlayback.current = resolve
      audio.play().catch(() => reject(new Error('Your browser needs a tap to play audio. Press Read aloud again.')))
    })
  }
  async function play(sourceType, sourceId, device = false) {
    stop()
    const version = run.current
    controller.current = new AbortController()
    const signal = controller.current.signal
    const source = { source_type: sourceType, source_id: sourceId, voice: voice === 'device' ? 'af_heart' : voice }
    setActive(`${sourceType}:${sourceId}`)
    setStatus('Preparing voice…')
    setNotice('')
    try {
      const prepared = await voiceRequest('prepare', source, signal)
      if (version !== run.current) return
      setNotice(prepared.warning || '')
      let useDevice = device || voice === 'device' || prepared.device_only
      // At most one clip ahead: hide generation behind playback without
      // filling a server queue with speech the learner may cancel.
      const fetchClip = index => voiceRequest('speech', { ...source, segment: index }, signal, true)
        .then(blob => ({ blob }), error => ({ error }))
      let nextClip = !useDevice && prepared.segments.length ? fetchClip(0) : null
      for (let index = 0; index < prepared.segments.length; index++) {
        if (version !== run.current) return
        setStatus(useDevice ? 'Reading with device voice' : 'Preparing voice…')
        const text = prepared.segments[index]
        let blob
        if (!useDevice) {
          try {
            const next = await nextClip
            if (next.error) throw next.error
            blob = next.blob
          }
          catch (failure) {
            if (signal.aborted) throw failure
            useDevice = true
            setNotice('Local voice is unavailable or busy. Using your device voice. ' + (prepared.warning || ''))
          }
        }
        if (version !== run.current) return
        if (!useDevice && index + 1 < prepared.segments.length) nextClip = fetchClip(index + 1)
        setStatus(useDevice ? 'Reading with device voice' : 'Reading aloud')
        setSpoken(text)
        if (useDevice) await deviceSpeak(text, version)
        else await playBlob(blob, version)
      }
    } catch (failure) {
      if (version === run.current) setNotice(failure.message || 'Read-aloud is unavailable. Your reply is still saved.')
    } finally { if (version === run.current) stop() }
  }
  return { active, status, spoken, notice, voice, setVoice, speed, setSpeed, autoRead, setAutoRead, play, stop }
}

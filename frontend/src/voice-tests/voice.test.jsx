// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import useVoiceInput from '../hooks/useVoiceInput.js'
import useTutorSpeech from '../hooks/useTutorSpeech.js'
import { transcribeRecording, voiceRequest } from '../api/voice.js'

vi.mock('../api/voice.js', () => ({ transcribeRecording: vi.fn(), voiceRequest: vi.fn() }))
let track
let recorder
class Recorder {
  static isTypeSupported() { return true }
  constructor() { recorder = this; this.state = 'inactive'; this.mimeType = 'audio/webm' }
  start() { this.state = 'recording' }
  stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['audio']) }); this.onstop?.() }
}
beforeEach(() => {
  vi.clearAllMocks()
  track = { stop: vi.fn() }
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [track] }) } })
  vi.stubGlobal('MediaRecorder', Recorder)
  vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), getVoices: () => [], speak: vi.fn() })
  vi.stubGlobal('SpeechSynthesisUtterance', class { constructor(text) { this.text = text } })
  transcribeRecording.mockResolvedValue({ text: 'one over x plus two', warning: 'Check grouping' })
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })

test('stopping a recording releases the mic and creates a draft only', async () => {
  const stopSpeech = vi.fn()
  const { result } = renderHook(() => useVoiceInput('part-one', stopSpeech))
  await act(() => result.current.start())
  expect(stopSpeech).toHaveBeenCalledOnce()
  expect(result.current.state).toBe('recording')
  await act(() => result.current.stop())
  expect(track.stop).toHaveBeenCalledOnce()
  expect(result.current.draft.text).toBe('one over x plus two')
  expect(transcribeRecording).toHaveBeenCalledOnce()
})
test('question navigation discards late transcripts and stops tracks', async () => {
  let resolve
  transcribeRecording.mockImplementation(() => new Promise(done => { resolve = done }))
  const { result, rerender } = renderHook(({ part }) => useVoiceInput(part, vi.fn()), { initialProps: { part: 'one' } })
  await act(() => result.current.start())
  act(() => result.current.stop())
  rerender({ part: 'two' })
  await act(() => resolve({ text: 'stale', warning: '' }))
  expect(result.current.draft).toBeNull()
  expect(result.current.state).toBe('idle')
  expect(track.stop).toHaveBeenCalled()
  expect(transcribeRecording.mock.calls[0][3].aborted).toBe(true)
})
test('late microphone permission after cancel cannot start recording', async () => {
  let resolve
  navigator.mediaDevices.getUserMedia.mockImplementation(() => new Promise(done => { resolve = done }))
  const { result } = renderHook(() => useVoiceInput('one', vi.fn()))
  let pending
  act(() => { pending = result.current.start() })
  act(() => result.current.cancel())
  await act(async () => { resolve({ getTracks: () => [track] }); await pending })
  expect(track.stop).toHaveBeenCalledOnce()
  expect(result.current.state).toBe('idle')
})
test('permission denial leaves typing available with a useful error', async () => {
  navigator.mediaDevices.getUserMedia.mockRejectedValue(new DOMException('Denied', 'NotAllowedError'))
  const { result } = renderHook(() => useVoiceInput('one', vi.fn()))
  await act(() => result.current.start())
  expect(result.current.error).toMatch(/permission was denied/)
  expect(result.current.state).toBe('idle')
})
test('recordings stop automatically at thirty seconds', async () => {
  vi.useFakeTimers()
  const { result } = renderHook(() => useVoiceInput('one', vi.fn()))
  await act(() => result.current.start())
  await act(() => vi.advanceTimersByTimeAsync(30000))
  expect(recorder.state).toBe('inactive')
  expect(track.stop).toHaveBeenCalledOnce()
  expect(transcribeRecording).toHaveBeenCalledOnce()
})
test('cancelled playback cannot speak after preparation finishes', async () => {
  let resolve
  voiceRequest.mockImplementation(() => new Promise(done => { resolve = done }))
  const { result } = renderHook(() => useTutorSpeech('one'))
  let pending
  act(() => { pending = result.current.play('chat', 'id', true) })
  act(() => result.current.stop())
  await act(async () => { resolve({ segments: ['Late text'] }); await pending })
  expect(speechSynthesis.speak).not.toHaveBeenCalled()
  expect(result.current.active).toBeNull()
})
test('worker failure uses prepared maths speech with the device voice', async () => {
  voiceRequest.mockImplementation(path => path === 'prepare' ? Promise.resolve({ segments: ['three fifths'], warning: null }) : Promise.reject(new Error('busy')))
  speechSynthesis.speak.mockImplementation(utterance => queueMicrotask(() => utterance.onend()))
  const { result } = renderHook(() => useTutorSpeech('one'))
  await act(() => result.current.play('chat', 'id'))
  expect(speechSynthesis.speak.mock.calls[0][0].text).toBe('three fifths')
  expect(result.current.notice).toMatch(/Using your device voice/)
  expect(result.current.active).toBeNull()
})
test('stopping device speech settles playback and cancels the utterance', async () => {
  voiceRequest.mockResolvedValue({ segments: ['First sentence', 'Second sentence'] })
  const { result } = renderHook(() => useTutorSpeech('one'))
  let pending
  await act(async () => { pending = result.current.play('chat', 'id', true); await Promise.resolve() })
  act(() => result.current.stop())
  await act(() => pending)
  expect(speechSynthesis.speak).toHaveBeenCalledOnce()
  expect(speechSynthesis.cancel).toHaveBeenCalled()
})

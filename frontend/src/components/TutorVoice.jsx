import { Mic, Square, Volume2 } from 'lucide-react'
import './TutorVoice.css'

export function VoicePreferences({ speech }) {
  return <div className="tutor-voice-preferences">
    <label><input type="checkbox" checked={speech.autoRead} onChange={e => speech.setAutoRead(e.target.checked)} /> Read new replies</label>
    <label><span className="sr-only">Tutor voice</span><select aria-label="Tutor voice" value={speech.voice} onChange={e => { speech.stop(); speech.setVoice(e.target.value) }}><option value="af_heart">Heart · US</option><option value="bf_emma">Emma · UK</option></select></label>
    <label><span className="sr-only">Reading speed</span><select aria-label="Reading speed" value={speech.speed} onChange={e => speech.setSpeed(Number(e.target.value))}><option value="0.8">0.8× speed</option><option value="1">1× speed</option><option value="1.2">1.2× speed</option></select></label>
    {speech.active && <button type="button" onClick={speech.stop}><Square size={13} /> Stop reading</button>}
  </div>
}

export function VoiceStatus({ speech }) {
  if (!speech.status && !speech.notice) return null
  return <div className="voice-playback-status">
    {speech.status && <span className="voice-status" role="status">{speech.status}</span>}
    {speech.spoken && <p className="voice-spoken"><span>Reading now</span>{speech.spoken}</p>}
    {speech.notice && <p className="voice-notice" role="status">{speech.notice}</p>}
  </div>
}

export function ReadAloud({ speech, type, id, disabled }) {
  const playing = speech.active === `${type}:${id}`
  return <div className={`voice-reply-actions${playing ? ' is-reading' : ''}`}>
    <button type="button" disabled={disabled} onClick={() => playing ? speech.stop() : speech.play(type, id)} aria-label={playing ? 'Stop reading this reply' : 'Read this reply aloud'}>{playing ? <Square size={13} /> : <Volume2 size={14} />}{playing ? 'Stop' : 'Read aloud'}</button>
    <button type="button" disabled={disabled} onClick={() => speech.play(type, id, true)}>Device voice</button>
  </div>
}

export function VoiceInput({ input, disabled, onUseDraft }) {
  const busy = input.state !== 'idle'
  return <div className="tutor-voice-input">
    <div className="voice-input-actions">
      <button type="button" className={input.state === 'recording' ? 'is-recording' : ''} disabled={input.state !== 'recording' && (disabled || busy)} onClick={input.state === 'recording' ? input.stop : input.start}>
        {input.state === 'recording' ? <Square size={15} /> : <Mic size={15} />}
        {input.state === 'recording' ? `Stop · ${input.seconds}/30s` : input.state === 'transcribing' ? 'Transcribing…' : input.state === 'permission' ? 'Allow microphone…' : 'Ask by voice'}
      </button>
      {(busy || input.canRetry) && <button type="button" onClick={input.cancel}>Cancel</button>}
      {input.canRetry && !busy && <button type="button" disabled={disabled} onClick={input.retry}>Retry for accuracy</button>}
    </div>
    <small>English · Up to 30 seconds. Audio goes to Groq for transcription; this app does not save recordings.</small>
    {input.error && <p className="voice-notice" role="alert">{input.error}</p>}
    {input.draft && <div className="voice-draft">
      <label htmlFor="voice-transcript">Check your transcript</label>
      <textarea id="voice-transcript" rows={3} maxLength={1000} value={input.draft.text} onChange={e => input.setDraft({ ...input.draft, text: e.target.value })} />
      <p>{input.draft.warning} For “one over x plus two”, specify which terms are in the denominator.</p>
      <button type="button" disabled={disabled || busy || !input.draft.text.trim()} onClick={() => onUseDraft(input.draft.text)}>Use in message</button>
    </div>}
  </div>
}

# Voice tutor implementation plan

Research date: 16 September 2026. Status: implemented on 17 September 2026. See [the voice guide](voice-worker/README.md) for actual controls, verification, measured performance, and remaining hands-on evaluation. The proposal below records the original design targets, not performance promises.

The deployment assumption is a laptop or server controlled by the project team, as confirmed by the user. Language scope is provisionally English, including Pakistani accents, pending confirmation. Existing text chat, immutable reviews, and provider recovery remain the source of tutoring decisions.

## Recommended stack

| Responsibility | Initial choice | Recovery path |
| --- | --- | --- |
| Record a question | Browser microphone + MediaRecorder | Existing typed composer |
| Transcribe speech | Groq `whisper-large-v3-turbo` | Retry the saved recording explicitly; offer `whisper-large-v3` for a difficult recording |
| Tutor reasoning | Existing Groq/OpenRouter text tutor | Existing provider failover and saved turns |
| Read tutor replies | Kokoro-82M in a separate, preloaded local service | Browser/device speech synthesis |
| Read mathematical notation | Deterministic maths-to-speech conversion | Preserve visible notation and flag unsupported expressions |

Groq documents both Whisper models and accepts common recording formats, including WebM and MP4. Use transcription rather than translation. For an English-only release, specify English and provide a short vocabulary prompt containing terms such as numerator, denominator, probability, and mutually exclusive. Do not put private answers or anticipated numerical results in that prompt. [Groq speech documentation](https://console.groq.com/docs/speech-to-text)

Kokoro has 82 million parameters and Apache-2.0 licensed weights. Its official implementation provides a practical starting point for a model hosted on a machine we control. This removes a hosted TTS request quota, but consumes local compute and does not imply unlimited concurrency or free cloud hosting. Audition a small selection of stock voices with students before choosing the default. [Official model card](https://huggingface.co/hexgrad/Kokoro-82M)

Start with one dedicated Kokoro worker and a bounded queue. Load the model once, warm it up before the demo, and keep model downloads out of the request path. Benchmark CPU performance on the actual machine; add GPU acceleration only if available and useful. Keep inference outside FastAPI's main process so speech cannot block saving work or text tutoring. A Node sidecar using the official Kokoro.js implementation is an option that fits the existing Node environment; its documented runtime targets include Node CPU and browser WASM/WebGPU. Pin tested versions. [Kokoro.js](https://github.com/hexgrad/kokoro/tree/main/kokoro.js)

## Alternatives considered

| Option | What is attractive | Why it is not the initial default |
| --- | --- | --- |
| Groq Orpheus | Expressive hosted English voice; existing provider account | Current 200-character input limit and small free quotas make full-reply narration expensive in requests. Keep as an optional short-response experiment. |
| Azure Speech F0 | Hosted neural voices; published allowance of 500,000 TTS characters/month | Requires another account/resource. Worth considering if local performance is inadequate or Urdu is required. |
| ElevenLabs Free | Hosted voice generation; 10,000 monthly credits listed | Small allowance; its free-plan publication/commercial-use restrictions need to fit the intended app. |
| Deepgram | Hosted speech stack with introductory credit | Promotional credit is not a recurring free operating model. |
| Browser speech recognition | Little backend integration | Uneven browser support and browser-dependent processing make it unsuitable as the sole input engine. |
| Browser speech synthesis | Straightforward read-aloud recovery | Voice availability and quality depend on the device. Test a suitable voice; do not promise every voice works offline. |
| Local faster-whisper | A way to remove the hosted transcription dependency | Additional CPU/GPU load and deployment work. Evaluate after the initial speech flow works. |

Sources: [Groq Orpheus](https://console.groq.com/docs/text-to-speech/orpheus), [Groq limits](https://console.groq.com/docs/rate-limits), [Azure F0 pricing](https://azure.microsoft.com/en-us/pricing/details/speech/), [ElevenLabs pricing](https://elevenlabs.io/pricing), [ElevenLabs publication policy](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform), [Deepgram pricing](https://deepgram.com/pricing), [browser recognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition), [browser synthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis), [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

The currently displayed Groq free-plan table lists Whisper Turbo at 20 requests/minute, 2,000/day, 7,200 audio seconds/hour and 28,800/day. Orpheus is listed at 10 requests/minute, 100/day, 1,200 tokens/minute and 3,600/day. These are shared organization limits, not allowances for each student; the account's Limits page is authoritative. A 600-character spoken reply needs at least three Orpheus requests, so 100 requests allow at most 33 such uncached replies before other limits. This is the main reason to prefer local TTS. [Groq limits](https://console.groq.com/docs/rate-limits)

## Student experience

1. A microphone button sits beside the existing chat composer. The learner clicks to start and clicks again to stop, or cancels. Include a visible recording indicator and a keyboard-accessible control. Cap a recording at approximately 30 seconds for this MVP.
2. The transcript appears as an editable draft. Sending remains an explicit action. Students can correct a misheard number or mathematical term before the tutor responds.
3. Sending uses the existing chat endpoint and one client-message UUID. Retrying transcription must not create a chat turn; retrying narration must not regenerate the tutor answer.
4. The validated tutor reply appears immediately. A speaker button reads it aloud. An opt-in setting enables automatic reading of new replies.
5. Students can stop, replay, or change playback speed. Starting another recording stops current playback first to avoid the microphone transcribing the tutor's own voice.
6. Switching question parts, leaving the page, or cancelling stops pending playback and releases microphone tracks. A late result must not play over a different question or restore text into the wrong draft.

Khanmigo documents microphone input, text appearing before speech, highlighted spoken sections, voice selection, and replay controls. These are useful interaction precedents. Duolingo describes learning-designer instructions and purposeful conversation structure behind its voice experience. Our application should similarly preserve the current question context and one-step Socratic teaching policy. [Khanmigo voice experience](https://support.khanacademy.org/hc/en-us/articles/23772334788365-Does-Khanmigo-have-a-read-aloud-or-Text-to-speech-feature), [Duolingo learning design](https://blog.duolingo.com/ai-and-video-call/)

A natural voice should deliver short, clear teaching turns. Keep the written response available throughout. Identify it as an AI tutor; a human-sounding voice does not establish human-level judgement or replace teacher review.

## Mathematical speech

Speech must verbalize the approved reply without adding a new answer or changing the learner's mathematics. Do not ask a separate language model to rewrite every reply for speech: that adds latency and another opportunity to alter its meaning.

Build tests for conversions such as:

| Visible notation | Intended speech |
| --- | --- |
| `3/5` | three fifths |
| `x²` | x squared |
| `P(A)` | probability of A |
| `P(A \| B)` | probability of A given B |
| `0.25` | zero point two five |
| `≤` | less than or equal to |
| `(a+b)/c` | the quantity a plus b, divided by c |

Use structured parsing for fractions, grouping, powers and equations; plain slash replacement loses meaning. Speech Rule Engine can verbalize MathML and is a candidate alongside the project's existing KaTeX rendering. Initially support and test the Probability notation actually used by this question bank. Do not imply that arbitrary handwritten or malformed notation is solved. [Speech Rule Engine](https://github.com/Speech-Rule-Engine/speech-rule-engine)

For input, retain the recognizer's transcript and allow edits. Do not silently convert ambiguous speech such as “one over x plus two” into a specific grouped expression. Never correct a student's mistaken calculation before assessment.

## Repository integration

Proposed backend additions:

- `backend/app/routers/voice.py`: session-scoped transcription and narration endpoints.
- `backend/app/services/transcription.py`: Groq audio transport, short deadlines, metadata handling and bounded uploads.
- `backend/app/services/speech.py`: private Kokoro worker client, audio caching and cancellation.
- A separate local speech worker with one warmed model instance and health/readiness checks.

Proposed frontend additions:

- `frontend/src/api/voice.js` for audio transport.
- `frontend/src/hooks/useVoiceInput.js` for recording, draft association and cancellation.
- `frontend/src/hooks/useTutorSpeech.js` for one playback queue and fallback.
- Small microphone and playback components integrated into `AiTutorPanel` in `QuestionPracticePage.jsx`.

Suggested API contracts:

- `POST /api/v1/learner-sessions/{session_id}/voice/transcriptions`: multipart recording, request UUID, language and question-part ID; returns a draft transcript and any quality warning. It does not submit chat or award marks.
- `POST /api/v1/learner-sessions/{session_id}/voice/speech`: source type, source ID, allowlisted voice and speed; returns an audio clip or a bounded generation response. For chat and review narration, the server resolves the saved public message itself.

A narration source is a completed tutor turn or public review feedback. The endpoint must not access private marking criteria or synthesize arbitrary caller-supplied hidden content. Later, public question text can be a separate authorized source type. Narrating the learner's own draft can be added as an explicit composer preview.

For the first release, short complete replies can be returned as WAV clips. If full-clip generation misses the latency target, split the already validated reply at sentence boundaries and play ordered clips while preparing the next. This is audio chunking after validation, not streaming unfinished model JSON. Highlight the active sentence; exact word highlighting requires genuine alignment metadata.

Cache repeated narration by learner/session, source ID and content version, model version, voice, speed and maths-normalization version. Replaying should reuse audio. Use a bounded cache with expiration, enforce ownership on reads, and keep learner-specific clips out of public/shared caches.

## Reliability and privacy

- Preserve the existing text workflow if recording, transcription or narration fails. Show a specific action: retry transcription, edit the draft, or use device read-aloud.
- Use HTTPS on deployed/mobile URLs; microphone access requires a secure context. Localhost development is a special case. Select recording formats with feature detection and test Safari separately. [Microphone API](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- Limit upload bytes and decoded duration server-side; do not trust MIME labels or a client timer. Release database connections before transcription or synthesis.
- Apply separate text/STT/TTS admission limits and cooldowns. A speech quota failure must not disable text chat. Respect provider retry headers and cap retries.
- Add request IDs and cancellation tokens. Ignore stale responses after a question change, stop button or newer request.
- Keep raw recordings in temporary memory/storage only for processing and explicit immediate retry, then discard them. Persist the student-approved text, not raw voice by default. Do not log recordings, credentials or full learner messages.
- Explain that recordings go to Groq for transcription. Local Kokoro keeps synthesis on the project-controlled machine, not necessarily on the student's device. Configure provider data controls before real student use; application deletion alone does not control provider retention. [Groq data controls](https://console.groq.com/docs/your-data)
- If all network services fail, local read-aloud may still work for available text; this does not make the Groq-backed tutor itself offline.

## Implementation order and acceptance

1. **Capability and voice trial.** Check the actual Groq account limits, run short STT samples, install a pinned Kokoro build in an isolated worker, compare two stock voices, and record cold/warm timings on the target laptop. Select the default only after this trial.
2. **Input milestone.** Add microphone capture, cancel, duration limit, editable transcript and normal chat submission. Test permission denial, silence, noise, format differences, duplicate clicks and navigation during transcription.
3. **Read-aloud milestone.** Narrate existing completed turns and public review feedback. Add stop/replay/speed controls, device-voice recovery and a cache. Voice is optional and never blocks text.
4. **Teaching polish.** Add tested mathematical verbalization, sentence highlighting and optional auto-read. Check that audio and displayed content express the same mathematics.
5. **Demo and student evaluation.** Use 30-50 short recordings spanning Pakistani English accents, fraction/decimal wording, background noise, and “I don't understand” questions. Add consented student samples later; synthetic recordings alone do not validate accent performance. Evaluate critical-number/operator accuracy separately from general word error rate.

Engineering targets, not measured promises: warm transcription within about 1-2 seconds after Stop; first playable narration within about 1-2 seconds after the validated reply; median end-of-recording to spoken response around 3-5 seconds under light load. Record p50/p95 and cold starts independently. The existing text-chat timing does not establish voice latency. If hardware misses targets, use the device voice promptly and evaluate Azure F0 or browser-side Kokoro instead of hiding the delay.

Test simultaneous users, a stalled speech worker, a forced Groq 429, audio playback failure, and returning from a backgrounded phone browser. Set the supported concurrency from measured capacity, not an assumed number.

For the judge demonstration: ask a real spoken probability question, show the editable transcript, send it, hear one focused hint with the corresponding text highlighted, replay more slowly, then show that turning off speech still leaves a fully working saved conversation. Preload the model and check microphones/speakers beforehand; use genuinely generated tutor answers.

Full hands-free conversation with silence detection, automatic turn submission and interruption while speaking should follow this MVP. It needs additional testing around background noise, pauses while thinking and accidental sends.

If Urdu output is required, revisit the TTS choice before implementation. Groq's documented Orpheus variants are English and Saudi Arabic; neither should be represented as an Urdu voice. Azure lists Pakistani Urdu neural voices and is a candidate for that branch. [Groq TTS languages](https://console.groq.com/docs/text-to-speech), [Azure voice languages](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)

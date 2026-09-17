# Voice for the maths tutor

English voice input uses the existing server-side Groq key and Whisper Turbo.
“Retry for accuracy” explicitly uses Whisper Large v3 on the same in-memory
recording. It never submits a chat message. The student edits the transcript,
adds it to the composer, and presses Send.

Read-aloud uses Kokoro-82M q8 on CPU in a separate Node process. Heart is the
default stock voice; Emma is the British alternative. Both are selectable.
The UI highlights the active reply and shows the spoken segment. This is
segment-level feedback, not fabricated word timing.

## Run

This workspace has already been set up. Restart `backend/start.cmd`, run
`npm run dev` in `frontend`, and open a Probability practice question.
Wait for `Local tutor voice ready` in the backend terminal before a demo.

For a fresh checkout:

1. Complete the normal database/backend/frontend setup in the root README.
2. Run `voice-setup.cmd` from the project root. This installs the pinned worker
   and downloads its model once into `voice-worker/.models` (gitignored).
3. Keep `GROQ_API_KEY` in `backend/.env`. No additional paid service is needed.
4. Start the backend normally. It starts and stops its private voice worker.

Use one Uvicorn process with this MVP worker. Its default port is 8765 on
loopback, protected by a randomly generated internal bearer token. Change
`VOICE_WORKER_PORT` if necessary. `VOICE_WORKER_ENABLED=false` disables the
worker; device speech can still read prose, with explicit visual-check prompts
for maths that cannot be normalized while the worker is down.

On Linux/macOS, install backend requirements, run `npm ci && npm run setup`
inside `voice-worker`, and start the backend using the existing Python command.
Node 22 is recommended. Startup uses the local cache and never downloads models.

## Try it

- Press **Ask by voice**, speak, and press Stop. Check the transcript, choose
  **Use in message**, then Send. An existing typed draft is preserved.
- Press **Read aloud** on a completed tutor reply or review. Try stop, replay,
  the speed selector, Emma, and **Device voice**.
- Opt into **Read new replies**. Existing restored history is not auto-read.
- Start recording while audio plays: playback should stop. Switch question
  parts during recording or preparation: late results should be discarded.
- Try “one over x plus two”, “zero point zero five”, negatives, and conditional
  probability. Correct the transcript yourself if needed; the app does not
  guess the intended grouping or correct a student's calculation.

HTTPS or localhost is required for the microphone. Browser/device voices and
autoplay policies vary. If playback is blocked, tap Read aloud again. Chrome
and Edge are the initial targets; actual microphone and Safari/mobile behaviour
still need hands-on testing. No browser surface was available in the automated
development environment; hook lifecycle tests use a simulated DOM.

## Maths and teaching

Speech is derived deterministically from the saved public reply. Plain
expressions are parsed with precedence and grouping, rendered to MathML using
KaTeX, then verbalized by Speech Rule Engine. Delimited LaTeX uses the same
MathML path. There is no extra LLM rewrite and no new assessment during replay.

Regression cases cover fractions, nested grouping, squared/cubed and negative
powers, scientific notation, decimals with leading zeroes, inequalities,
percentages, roots, subscripts, factorials, probability, union/intersection,
and conditional probability. Unsupported or malformed expressions receive a
visual-check prompt. This is not a guarantee for arbitrary mathematical notation.
The written reply always remains available.

## Capacity and privacy

- Recording: 30-second client cap; 4 MB upload cap enforced before multipart
  parsing; server decodes/resamples audio and rejects silence, invalid input,
  and decoded duration over 31 seconds (one second of encoder/timer tolerance).
- Transcription: two concurrent jobs, eight requests/minute per learner session,
  explicit retries, separate Groq quota cooldown. Account free limits still apply.
- Synthesis: one model job; no unbounded queue. One next segment is prefetched
  during playback. Local failure falls back to device speech.
- Replay cache: server memory only, 10-minute TTL, maximum 80 clips/32 MB, scoped
  by learner, source, content, voice and model/normalizer version. Playback speed
  is applied by the player, so it does not require another synthesis request.
- Ownership is checked before every narration request. Only completed public
  chat messages and review feedback can be narrated; private snapshots and
  marking criteria are not narration sources. Existing anonymous session UUIDs
  act as bearer credentials, as elsewhere in the MVP; this is not account login.
- Raw recordings remain only for processing and immediate retry, then are
  discarded. Groq receives recordings; its retention settings are controlled
  separately in the Groq account. Device speech may use the browser/OS vendor's
  online voice service. Kokoro generation stays on the project-controlled host.

## Verification and measured limits

`verify.cmd` runs backend, frontend API, voice lifecycle, maths speech, content,
and production-build checks. For a real local model smoke test:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.smoke_voice
# Optional: also send a synthetic sample to the configured Groq account.
backend/.venv/Scripts/python.exe -m backend.scripts.smoke_voice --live-transcription
```

Run the smoke test with the normal backend stopped (it temporarily owns the
worker port). It never uses student recordings or changes learner data.

Measured on this i5-1235U environment on 17 September 2026: startup plus warmup
4.36 seconds, two short local clips 4.55 and 6.37 seconds, cached replay below
1 ms, and an approximately eight-second synthetic recording transcribed by Groq
in 2.02 seconds. These are individual samples, not p50/p95 claims. Other short
clip trials ranged around 2–4 seconds; CPU load matters. The 1–2-second synthesis
target is not met consistently here. Use Device voice for the lowest wait, or
benchmark a stronger host. Prepared text appears immediately while voice loads.

Student accents, noise, real microphones, perceived voice quality, and simultaneous
real users still need evaluation. Synthetic transcription does not validate those.
Stock sample WAVs for Heart and Emma are in `.models` for local listening.

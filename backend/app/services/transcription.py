"""Short, ephemeral recordings. Never persists audio or logs provider payloads."""
import io
import threading
import time
import wave

import av
import numpy as np
import requests
from fastapi import HTTPException

from ..config import get_settings

MAX_BYTES = 4 * 1024 * 1024
_slots = threading.BoundedSemaphore(2)
_lock = threading.Lock()
_cooldown_until = 0.0


def decode_recording(data: bytes) -> bytes:
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, "Record up to 30 seconds (maximum 4 MB).")
    samples = []
    count = 0
    try:
        with av.open(io.BytesIO(data), options={
            "protocol_whitelist": "pipe",
            "format_whitelist": "wav,matroska,webm,mov,ogg,mp3,flac,aac",
        }) as container:
            if len(container.streams.audio) != 1:
                raise ValueError("Expected one audio stream")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    count += converted.samples
                    if count > 31 * 16000:
                        raise HTTPException(413, "Please keep recordings under 30 seconds.")
                    samples.append(converted.to_ndarray().reshape(-1))
            for converted in resampler.resample(None):
                count += converted.samples
                samples.append(converted.to_ndarray().reshape(-1))
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(422, "This recording could not be decoded. Please record again.") from error
    if count > 31 * 16000:
        raise HTTPException(413, "Please keep recordings under 30 seconds.")
    if count < 4000:
        raise HTTPException(422, "The recording was too short. Please try again.")
    pcm = np.concatenate(samples)
    if np.sqrt(np.mean(pcm.astype(np.float32) ** 2)) < 35:
        raise HTTPException(422, "No audible speech was detected. Check your microphone and try again.")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm.astype('<i2').tobytes())
    return output.getvalue()


def transcribe(data: bytes, accurate: bool = False) -> dict:
    global _cooldown_until
    key = get_settings().groq_api_key
    if not key:
        raise HTTPException(503, "Voice input needs a Groq key on the server. You can still type.")
    with _lock:
        if time.monotonic() < _cooldown_until:
            raise HTTPException(429, "Voice input is temporarily at its free limit. Please type or retry shortly.")
    if not _slots.acquire(blocking=False):
        raise HTTPException(429, "Voice input is busy. Please retry shortly or type your question.")
    try:
        audio = decode_recording(data)
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": ("recording.wav", audio, "audio/wav")},
                data={"model": "whisper-large-v3" if accurate else "whisper-large-v3-turbo",
                      "language": "en", "temperature": "0", "response_format": "verbose_json",
                      "prompt": "Mathematics, probability, numerator, denominator, mutually exclusive, independent events, squared, fraction."},
                timeout=(4, 15),
            )
        except requests.RequestException as error:
            raise HTTPException(503, "Transcription is unavailable. Retry your recording or type your question.") from error
        if response.status_code == 429:
            try:
                delay = min(120, max(5, float(response.headers.get("retry-after", "20"))))
            except ValueError:
                delay = 20
            with _lock:
                _cooldown_until = time.monotonic() + delay
            raise HTTPException(429, "The free transcription limit was reached. Please type or retry shortly.")
        if not response.ok:
            raise HTTPException(503, "Transcription is unavailable. Retry your recording or type your question.")
        try:
            result = response.json()
            text = result.get("text", "").strip()
            segments = result.get("segments") or []
            probabilities = [float(segment.get("no_speech_prob", 0)) for segment in segments]
            logprobs = [float(segment.get("avg_logprob", 0)) for segment in segments]
            uncertain = any(p > .6 for p in probabilities) or any(p < -1 for p in logprobs)
        except (ValueError, TypeError, AttributeError) as error:
            raise HTTPException(502, "The transcription was incomplete. Please try again.") from error
        if not text or (probabilities and all(p > .85 for p in probabilities)):
            raise HTTPException(422, "Speech was not clear enough. Please record again.")
        if len(text) > 1000:
            raise HTTPException(422, "That question is too long. Please record a shorter question.")
        return {"text": text, "warning": ("Some words were unclear. " if uncertain else "") + "Check numbers, signs and grouping before sending."}
    finally:
        _slots.release()

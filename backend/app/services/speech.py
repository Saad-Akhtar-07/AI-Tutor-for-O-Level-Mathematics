"""Private local worker, started with the API. One CPU job; bounded private cache."""
import hashlib
import os
import re
from pathlib import Path
import secrets
import subprocess
import threading
import time
from collections import OrderedDict

import requests
from fastapi import HTTPException

_root = Path(__file__).resolve().parents[3] / "voice-worker"
_token = secrets.token_urlsafe(32)
_port = int(os.getenv("VOICE_WORKER_PORT", "8765"))
_process = None
_cache = OrderedDict()
_cache_bytes = 0
_cache_lock = threading.Lock()
_slot = threading.BoundedSemaphore(1)


def start_worker():
    global _process
    if os.getenv("VOICE_WORKER_ENABLED", "true").lower() == "false" or not (_root / "node_modules").exists():
        return
    try:
        _process = subprocess.Popen(["node", "server.js"], cwd=_root,
            env={**os.environ, "VOICE_WORKER_TOKEN": _token, "VOICE_WORKER_PORT": str(_port)},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except OSError:
        _process = None


def stop_worker():
    global _process
    if _process is not None:
        _process.terminate()
        try:
            _process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait()
        _process = None


def worker(path: str, payload: dict, timeout: float = 3):
    try:
        response = requests.post(f"http://127.0.0.1:{_port}/{path}", json=payload,
            headers={"Authorization": f"Bearer {_token}"}, timeout=(1, timeout))
        response.raise_for_status()
        return response
    except requests.RequestException as error:
        raise HTTPException(503, "Local voice is warming up or busy. Choose device voice, or retry shortly.") from error


def prepare(text: str) -> dict:
    if len(text) > 6000:
        raise HTTPException(422, "This reply is too long to read aloud.")
    try:
        return worker("prepare", {"text": text}).json()
    except HTTPException:
        # Device speech can still read prose when the whole worker is down.
        # Never let a browser silently drop unfamiliar mathematical notation.
        segments = []
        omitted = False
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            if re.search(r"[0-9\\$^=<>+*/{}|≤≥²³√∩∪−]", sentence):
                segments.append("Please check the mathematical expression shown in the text.")
                omitted = True
            elif sentence.strip():
                segments.append(sentence.strip())
        return {"segments": segments, "warning": "Maths pronunciation is unavailable; expressions need visual checking." if omitted else None, "normalizer_version": "prose-only-1", "device_only": True}


def synthesize(session_id, source_id, text: str, voice: str) -> bytes:
    global _cache_bytes
    key = hashlib.sha256(f"{session_id}:{source_id}:kokoro-q8-v1:normalizer-1:{voice}:{text}".encode()).hexdigest()
    now = time.monotonic()
    with _cache_lock:
        for old_key, (expires, audio) in list(_cache.items()):
            if expires < now:
                _cache_bytes -= len(audio)
                del _cache[old_key]
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key][1]
    if not _slot.acquire(blocking=False):
        raise HTTPException(503, "Local voice is busy. Choose device voice or retry shortly.")
    try:
        audio = worker("synthesize", {"text": text, "voice": voice}, timeout=12).content
        if not audio.startswith(b"RIFF") or len(audio) > 4 * 1024 * 1024:
            raise HTTPException(502, "Local voice returned invalid audio. Try device voice.")
        with _cache_lock:
            while _cache and (_cache_bytes + len(audio) > 32 * 1024 * 1024 or len(_cache) >= 80):
                _, (_, old) = _cache.popitem(last=False)
                _cache_bytes -= len(old)
            _cache[key] = (now + 600, audio)
            _cache_bytes += len(audio)
        return audio
    finally:
        _slot.release()

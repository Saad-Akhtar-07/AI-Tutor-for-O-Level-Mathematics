"""Short voice-specific limits; text tutoring has independent capacity."""
from collections import OrderedDict, deque
import threading
import time

from fastapi import HTTPException

_lock = threading.Lock()
_requests = OrderedDict()


def admit(session_id, operation: str):
    limit = 8 if operation == 'transcription' else 90
    now = time.monotonic()
    key = (str(session_id), operation)
    with _lock:
        if key not in _requests:
            if len(_requests) >= 2048:
                _requests.popitem(last=False)
            _requests[key] = deque()
        recent = _requests[key]
        _requests.move_to_end(key)
        while recent and recent[0] <= now - 60:
            recent.popleft()
        if len(recent) >= limit:
            raise HTTPException(429, "Please pause briefly before another voice request. You can still type.", headers={"Retry-After": "60"})
        recent.append(now)

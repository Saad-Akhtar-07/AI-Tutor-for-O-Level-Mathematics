"""Bound multipart bodies before Starlette spools them to disk."""
from starlette.responses import JSONResponse


class VoiceBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or "/voice/" not in scope.get("path", ""):
            return await self.app(scope, receive, send)
        limit = 4 * 1024 * 1024 + 16384 if scope["path"].endswith("/transcriptions") else 4096
        # Buffer only this bounded voice body, then let the usual form parser run.
        parts = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                return await JSONResponse({"detail": "Voice upload is too large. Record a shorter question."}, status_code=413)(scope, receive, send)
            parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": b"".join(parts), "more_body": False}

        await self.app(scope, bounded_receive, send)

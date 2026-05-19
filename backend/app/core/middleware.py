"""HTTP middleware: request context + access log.

Implemented as a pure ASGI middleware rather than `BaseHTTPMiddleware`
because the latter spawns extra tasks and has well-known issues with
streaming responses and exception propagation.
"""

import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger

REQUEST_ID_HEADER = b"x-request-id"
_log = get_logger("http")


class RequestContextMiddleware:
    """Bind request context, emit one access-log line per request.

    - Honors an incoming `X-Request-ID` so a caller can stitch traces
      across services; otherwise mints a UUID4.
    - Clears contextvars at the start of every request so a previous
      request's bindings can never leak into a new one on the same loop.
    - Echoes the request ID back in the response header so the client can
      surface it in errors / support tickets.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _extract_request_id(scope)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=scope.get("method", ""),
            path=scope.get("path", ""),
        )

        start = time.perf_counter()
        status_holder: dict[str, int] = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message.get("status", 0))
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            _log.exception("http.request.error")
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _log.info(
                "http.request",
                status=status_holder["status"],
                duration_ms=duration_ms,
            )


def _extract_request_id(scope: Scope) -> str:
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for name, value in headers:
        if name.lower() == REQUEST_ID_HEADER:
            decoded = value.decode("latin-1").strip()
            if decoded:
                return decoded
    return str(uuid.uuid4())


__all__ = ["RequestContextMiddleware", "REQUEST_ID_HEADER"]

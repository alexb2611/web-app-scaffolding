"""Structured logging configuration.

structlog is configured once at app startup. The renderer is chosen by
environment: pretty/colorful in development, JSON in production so logs
ship cleanly to aggregators.

Context is propagated via `structlog.contextvars` — bind `request_id`,
`user_id`, etc. early in the request and they appear on every subsequent
log line in that request.
"""

import logging
import sys

import structlog

from app.core.config import settings
from app.core.observability import inject_trace_context


def configure_logging() -> None:
    """Configure structlog + the stdlib root logger.

    Idempotent: safe to call from app startup or from tests.
    """
    is_production = settings.environment == "production"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        # OTel trace correlation — `trace_id`/`span_id` appear on every
        # log line whenever an OTel span is active. With OTel disabled
        # this is a single attribute lookup per log call, no overhead.
        inject_trace_context,
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        # `cache_logger_on_first_use=False` lets tests swap the processor
        # chain in a fixture and have it actually take effect on already-
        # imported module-level loggers. The runtime cost is negligible.
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Convenience wrapper so callers don't need to import structlog directly."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]

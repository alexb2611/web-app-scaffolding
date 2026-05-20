"""OpenTelemetry + Sentry observability bootstrap.

The scaffold's invariant: observability is **opt-in**. Importing this
module costs only the import cost of the OTel API. The exporters,
background span processors, and Sentry SDK only initialise when the
relevant env vars (`OTEL_EXPORTER_OTLP_ENDPOINT`, `SENTRY_DSN`, etc.)
are set, so a fresh `cp .env.example .env` boots a clean scaffold with
no outbound network traffic and no surprise telemetry.

Public surface:

- ``configure_observability(app, settings=None)`` — call once at startup
  after FastAPI is constructed but before requests are served.
- ``inject_trace_context`` — structlog processor that surfaces the
  current OTel trace_id/span_id on every log line, so log search and
  trace search share an ID.
"""

from __future__ import annotations

from typing import Any

import sentry_sdk
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from structlog.types import EventDict, WrappedLogger

from app.core.config import Settings
from app.core.config import settings as default_settings


def configure_observability(app: FastAPI, *, settings: Settings | None = None) -> None:
    """Install OpenTelemetry tracing + Sentry — both opt-in.

    Safe to call once at application startup. Idempotency is not
    guaranteed (auto-instrumentation libraries patch globals) so callers
    should not invoke this on every test; the test suite resets the OTel
    tracer provider via a fixture.
    """
    s = settings or default_settings

    _configure_opentelemetry(app, s)
    _configure_sentry(s)


# ---------------------------------------------------------------------------
# OpenTelemetry
# ---------------------------------------------------------------------------
def _configure_opentelemetry(app: FastAPI, s: Settings) -> None:
    has_otlp = bool(s.otel_exporter_otlp_endpoint)
    has_console = s.otel_console_exporter

    if not has_otlp and not has_console:
        # Nothing configured — leave the global NoOpTracerProvider in
        # place so spans are silently dropped rather than buffered.
        return

    resource = Resource.create(
        {
            "service.name": s.otel_service_name or s.app_name,
            "deployment.environment": s.environment,
        }
    )
    provider = TracerProvider(resource=resource)

    if has_otlp:
        # Batched exporter — production posture. Buffers spans and ships
        # in the background; the OTLP HTTP exporter respects standard
        # OTEL_* env vars for headers, timeouts, etc.
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{s.otel_exporter_otlp_endpoint}/v1/traces")
            )
        )

    if has_console:
        # SimpleSpanProcessor flushes synchronously to stdout — only ever
        # use this in dev. With Batch you wouldn't see spans until shutdown.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    # Instrument FastAPI, the SQLAlchemy engine, asyncpg, and httpx. Each
    # is a no-op when the global tracer provider is NoOp, so the import
    # cost paid above is the entirety of the overhead when OTel is off.
    # The OTel instrumentation libraries don't ship type stubs, hence the
    # narrowly-scoped ignores on the constructor calls.
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()  # type: ignore[no-untyped-call]
    # SQLAlchemy instrumentation needs to attach to a specific engine.
    # Importing lazily avoids a circular import via db.session.
    from app.db.session import engine

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------
def _configure_sentry(s: Settings) -> None:
    if not s.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=s.sentry_dsn,
        environment=s.environment,
        traces_sample_rate=s.sentry_traces_sample_rate,
        send_default_pii=s.sentry_send_default_pii,
        # FastAPI integration is auto-discovered by sentry-sdk[fastapi];
        # we leave the default integration set alone so the user gets the
        # full Starlette / FastAPI / SQLAlchemy / logging hookups for free.
    )


# ---------------------------------------------------------------------------
# structlog ↔ OTel trace correlation
# ---------------------------------------------------------------------------
def inject_trace_context(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """structlog processor that adds `trace_id` / `span_id` to each log.

    Without an active span (or with the NoOp tracer provider), the
    current span is invalid and we leave the event_dict untouched —
    no stray empty fields cluttering JSON logs in tests or dev.
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return event_dict

    event_dict["trace_id"] = f"{span_context.trace_id:032x}"
    event_dict["span_id"] = f"{span_context.span_id:016x}"
    return event_dict


__all__ = ["configure_observability", "inject_trace_context"]


# Suppress unused-import warning — kept here so future contributors can
# see the public-typed Any in IDEs; doesn't affect runtime behaviour.
_: Any = None

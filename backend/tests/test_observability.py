"""Tests for the OpenTelemetry + Sentry observability boot path.

The scaffold's invariant: observability is **opt-in**. With no env vars
set, `configure_observability()` must not start any background exporters,
must not reach out to the network, and must not install a global tracer
provider that would override what the host application might want.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util._once import Once

from app.core.config import Settings
from app.core.observability import (
    configure_observability,
    inject_trace_context,
)


@pytest.fixture(autouse=True)
def _reset_tracer_provider() -> Iterator[None]:
    """OpenTelemetry's global tracer provider is process-wide state and
    is guarded by an internal `Once` flag — calling `set_tracer_provider`
    a second time is a no-op with a warning. We reset both the provider
    and the Once guard so each test starts from a clean slate.
    """
    original_provider = trace._TRACER_PROVIDER  # noqa: SLF001
    original_once = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
    trace._TRACER_PROVIDER = None  # noqa: SLF001
    trace._TRACER_PROVIDER_SET_ONCE = Once()  # noqa: SLF001
    yield
    trace._TRACER_PROVIDER = original_provider  # noqa: SLF001
    trace._TRACER_PROVIDER_SET_ONCE = original_once  # noqa: SLF001


def _make_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    configure_observability(app, settings=settings)
    return app


# ---------------------------------------------------------------------------
# Opt-in posture — nothing configured means nothing happens
# ---------------------------------------------------------------------------
def test_configure_is_noop_when_no_endpoint_or_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With neither OTel endpoint nor Sentry DSN set: no provider, no init."""
    settings = Settings(_env_file=None)
    assert settings.otel_exporter_otlp_endpoint is None
    assert settings.sentry_dsn is None

    with patch("app.core.observability.sentry_sdk.init") as sentry_init:
        _make_app(settings)

    # Sentry not initialised because no DSN.
    sentry_init.assert_not_called()
    # No SDK TracerProvider installed — `get_tracer_provider()` falls back
    # to the ProxyTracerProvider when nothing has been set, which is the
    # `is not an instance of the SDK TracerProvider` invariant.
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)


def test_console_exporter_installs_tracer_provider() -> None:
    """`OTEL_CONSOLE_EXPORTER=true` is the local-dev visibility path —
    spans go to stdout and the tracer provider is the real SDK one."""
    settings = Settings(_env_file=None, otel_console_exporter=True)

    _make_app(settings)

    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_otlp_endpoint_installs_tracer_provider() -> None:
    """Setting an OTLP endpoint also installs the real provider."""
    settings = Settings(
        _env_file=None,
        otel_exporter_otlp_endpoint="http://localhost:4318",
    )

    _make_app(settings)

    assert isinstance(trace.get_tracer_provider(), TracerProvider)


# ---------------------------------------------------------------------------
# Sentry initialises only on DSN
# ---------------------------------------------------------------------------
def test_sentry_initialises_when_dsn_set() -> None:
    settings = Settings(
        _env_file=None,
        sentry_dsn="https://public@example.ingest.sentry.io/123",
        environment="staging",
    )

    with patch("app.core.observability.sentry_sdk.init") as sentry_init:
        _make_app(settings)

    sentry_init.assert_called_once()
    kwargs = sentry_init.call_args.kwargs
    assert kwargs["dsn"] == settings.sentry_dsn
    assert kwargs["environment"] == "staging"
    # send_default_pii must default to False — RFC: log capture is on but PII off.
    assert kwargs["send_default_pii"] is False


def test_sentry_pii_can_be_enabled_explicitly() -> None:
    settings = Settings(
        _env_file=None,
        sentry_dsn="https://public@example.ingest.sentry.io/123",
        sentry_send_default_pii=True,
    )

    with patch("app.core.observability.sentry_sdk.init") as sentry_init:
        _make_app(settings)

    assert sentry_init.call_args.kwargs["send_default_pii"] is True


# ---------------------------------------------------------------------------
# structlog ↔ OpenTelemetry trace correlation
# ---------------------------------------------------------------------------
def test_trace_context_processor_is_passthrough_when_no_span() -> None:
    """Without an active span, the processor mustn't add stray fields."""
    event: dict[str, object] = {"event": "hello"}
    out = inject_trace_context(MagicMock(), "info", event)
    assert "trace_id" not in out
    assert "span_id" not in out


def test_trace_context_processor_adds_ids_when_span_active() -> None:
    """With an SDK tracer + active span, the processor surfaces ids on each log."""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("test")

    with tracer.start_as_current_span("unit"):
        event: dict[str, object] = {"event": "inside"}
        out = inject_trace_context(MagicMock(), "info", event)

    # Both fields present and formatted as hex strings.
    assert "trace_id" in out
    assert "span_id" in out
    assert isinstance(out["trace_id"], str)
    assert isinstance(out["span_id"], str)
    assert len(out["trace_id"]) == 32  # 128-bit trace id as hex
    assert len(out["span_id"]) == 16  # 64-bit span id as hex


def test_trace_context_processor_is_idempotent_with_contextvars() -> None:
    """Existing structlog contextvars (request_id, user_id) must not be clobbered."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="abc-123", user_id="u-1")

    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("test")

    with tracer.start_as_current_span("unit"):
        event: dict[str, object] = {
            "event": "inside",
            "request_id": "abc-123",
            "user_id": "u-1",
        }
        out = inject_trace_context(MagicMock(), "info", event)

    # Pre-existing keys preserved; new keys added alongside.
    assert out["request_id"] == "abc-123"
    assert out["user_id"] == "u-1"
    assert "trace_id" in out
    assert "span_id" in out

    structlog.contextvars.clear_contextvars()

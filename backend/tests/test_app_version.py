"""The FastAPI app's version must track `pyproject.toml`.

Without this link, the OpenAPI `info.version` field stays at FastAPI's
"0.1.0" default forever and the generated TypeScript types have no
release-signal. The single source of truth is `pyproject.toml`'s
`[project] version`, read at runtime via `importlib.metadata`.

CI enforces the corollary: any change to `frontend/openapi.json`
without a matching version bump is a hard fail. See the
`api-contract` job in `.github/workflows/ci.yml`.
"""

from importlib.metadata import version as _pkg_version

from app.main import app


def test_fastapi_app_version_matches_installed_package() -> None:
    """`app.version` must equal the installed package's version."""
    assert app.version == _pkg_version("app")


def test_openapi_schema_exposes_the_same_version() -> None:
    """The schema FastAPI emits must reflect the wired version,
    so the committed `frontend/openapi.json` is honest about what
    contract clients are coding against."""
    schema = app.openapi()
    assert schema["info"]["version"] == _pkg_version("app")

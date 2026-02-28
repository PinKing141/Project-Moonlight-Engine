import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _is_e2e_test(request: pytest.FixtureRequest) -> bool:
    return "tests/e2e/" in str(request.node.fspath).replace("\\", "/")


@pytest.fixture(autouse=True)
def disable_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)


@pytest.fixture(autouse=True)
def e2e_fast_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if not _is_e2e_test(request):
        return

    monkeypatch.setenv("RPG_CREATION_EXTERNAL_CONTENT", "0")
    monkeypatch.setenv("RPG_FLAVOUR_DATAMUSE_ENABLED", "0")
    monkeypatch.setenv("RPG_MECHANICAL_FLAVOUR_DATAMUSE_ENABLED", "0")

    monkeypatch.setenv("RPG_CONTENT_RETRIES", "0")
    monkeypatch.setenv("RPG_CONTENT_BACKOFF_S", "0")
    monkeypatch.setenv("RPG_CONTENT_TIMEOUT_S", "0.05")
    monkeypatch.setenv("RPG_FLAVOUR_RETRIES", "0")
    monkeypatch.setenv("RPG_FLAVOUR_BACKOFF_S", "0")
    monkeypatch.setenv("RPG_FLAVOUR_TIMEOUT_S", "0.05")


@pytest.fixture(autouse=True)
def e2e_block_external_http(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if not _is_e2e_test(request):
        return

    import httpx

    def _deny_external_http(self, method, url, *args, **kwargs):
        candidate = str(url)
        if candidate.startswith(("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost")):
            return _original_request(self, method, url, *args, **kwargs)
        raise RuntimeError(f"External HTTP disabled during e2e tests: {candidate}")

    _original_request = httpx.Client.request
    monkeypatch.setattr(httpx.Client, "request", _deny_external_http)


@pytest.fixture(autouse=True)
def e2e_minimal_world_simulation(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if not _is_e2e_test(request):
        return

    monkeypatch.setattr("rpg.infrastructure.legacy_cli_compat.register_story_director_handlers", lambda **_kwargs: None)

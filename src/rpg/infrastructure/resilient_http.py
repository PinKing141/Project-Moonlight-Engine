import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class _CircuitState:
    failures: int = 0
    opened_until_epoch: float = 0.0


_CIRCUIT_STATES: dict[str, _CircuitState] = {}


def _is_truthy(value: str | None, *, default: str) -> bool:
    normalized = str(value if value is not None else default).strip().lower()
    return normalized in {"1", "true", "yes"}


def _circuit_enabled() -> bool:
    return _is_truthy(os.getenv("RPG_HTTP_CIRCUIT_BREAKER_ENABLED"), default="1")


def _failure_threshold() -> int:
    return max(1, int(os.getenv("RPG_HTTP_CIRCUIT_FAILURE_THRESHOLD", "3")))


def _reset_seconds() -> float:
    return max(0.0, float(os.getenv("RPG_HTTP_CIRCUIT_RESET_SECONDS", "120")))


def _circuit_key(client: httpx.Client) -> str:
    return str(getattr(client, "base_url", "unknown") or "unknown")


def _before_attempt(client: httpx.Client) -> None:
    if not _circuit_enabled():
        return
    key = _circuit_key(client)
    state = _CIRCUIT_STATES.get(key)
    if state is None:
        return

    now = time.time()
    if state.opened_until_epoch > now:
        raise CircuitOpenError(f"HTTP circuit open for {key} until {int(state.opened_until_epoch)}")

    if state.opened_until_epoch > 0:
        _CIRCUIT_STATES[key] = _CircuitState()


def _record_success(client: httpx.Client) -> None:
    if not _circuit_enabled():
        return
    key = _circuit_key(client)
    if key in _CIRCUIT_STATES:
        _CIRCUIT_STATES[key] = _CircuitState()


def _record_failure(client: httpx.Client) -> None:
    if not _circuit_enabled():
        return
    key = _circuit_key(client)
    state = _CIRCUIT_STATES.setdefault(key, _CircuitState())
    state.failures += 1
    if state.failures >= _failure_threshold():
        state.opened_until_epoch = time.time() + _reset_seconds()


def reset_circuit_breakers() -> None:
    _CIRCUIT_STATES.clear()


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


def get_json_with_retry(
    client: httpx.Client,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 0,
    backoff_seconds: float = 0.2,
) -> dict[str, Any]:
    attempts = max(0, int(retries)) + 1

    for attempt_index in range(attempts):
        try:
            _before_attempt(client)
            response = client.get(path, params=params, headers=headers)
            if response.status_code in _RETRYABLE_STATUS_CODES:
                raise httpx.HTTPStatusError(
                    f"Retryable HTTP status: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            payload = response.json()
            _record_success(client)
            return payload if isinstance(payload, dict) else {"results": payload}
        except Exception as exc:
            should_retry = _is_retryable_exception(exc)
            if should_retry:
                _record_failure(client)
            is_last_attempt = attempt_index >= attempts - 1
            if not should_retry or is_last_attempt:
                raise
            delay = max(0.0, backoff_seconds) * (2 ** attempt_index)
            if delay > 0:
                time.sleep(delay)

    return {}

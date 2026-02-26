import time
from typing import Any

import httpx


_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


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
            response = client.get(path, params=params, headers=headers)
            if response.status_code in _RETRYABLE_STATUS_CODES:
                raise httpx.HTTPStatusError(
                    f"Retryable HTTP status: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {"results": payload}
        except Exception as exc:
            should_retry = _is_retryable_exception(exc)
            is_last_attempt = attempt_index >= attempts - 1
            if not should_retry or is_last_attempt:
                raise
            delay = max(0.0, backoff_seconds) * (2 ** attempt_index)
            if delay > 0:
                time.sleep(delay)

    return {}

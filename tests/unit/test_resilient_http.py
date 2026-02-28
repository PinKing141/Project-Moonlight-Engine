import os
import sys
from pathlib import Path
import unittest
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.resilient_http import CircuitOpenError, get_json_with_retry, reset_circuit_breakers


class _AlwaysTimeoutClient:
    def __init__(self) -> None:
        self.base_url = "https://example.invalid"
        self.calls = 0

    def get(self, path, params=None, headers=None):
        self.calls += 1
        raise httpx.TimeoutException("timeout")


class _SuccessClient:
    def __init__(self) -> None:
        self.base_url = "https://example.invalid"
        self.calls = 0

    def get(self, path, params=None, headers=None):
        self.calls += 1
        request = httpx.Request("GET", f"https://example.invalid{path}")
        return httpx.Response(200, json={"results": [{"name": "ok"}]}, request=request)


class ResilientHttpTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_circuit_breakers()

    def test_returns_json_payload_on_success(self) -> None:
        client = _SuccessClient()
        payload = get_json_with_retry(client, "/ok", retries=0)
        self.assertEqual("ok", payload["results"][0]["name"])
        self.assertEqual(1, client.calls)

    def test_circuit_opens_after_threshold_and_short_circuits_next_call(self) -> None:
        client = _AlwaysTimeoutClient()
        env = {
            "RPG_HTTP_CIRCUIT_BREAKER_ENABLED": "1",
            "RPG_HTTP_CIRCUIT_FAILURE_THRESHOLD": "3",
            "RPG_HTTP_CIRCUIT_RESET_SECONDS": "600",
        }

        with mock.patch.dict(os.environ, env, clear=False):
            for _ in range(3):
                with self.assertRaises(httpx.TimeoutException):
                    get_json_with_retry(client, "/timeout", retries=0)

            calls_before = client.calls
            with self.assertRaises(CircuitOpenError):
                get_json_with_retry(client, "/timeout", retries=0)
            self.assertEqual(calls_before, client.calls)


if __name__ == "__main__":
    unittest.main()

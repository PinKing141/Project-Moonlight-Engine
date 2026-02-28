import sys
from pathlib import Path
import tempfile
import time
import json
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.content_cache import FileContentCache
from rpg.infrastructure.content_provider_client import FallbackContentClient


class _FakeProvider:
    def __init__(self, races_payload=None, should_fail: bool = False):
        self.races_payload = races_payload or {"results": []}
        self.should_fail = should_fail
        self.calls = 0

    def list_races(self, page: int = 1) -> dict:
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("provider unavailable")
        return self.races_payload

    def close(self) -> None:
        return None


class _UnavailableProvider:
    def __init__(self):
        self.calls = 0

    def list_races(self, page: int = 1) -> dict:
        self.calls += 1
        raise FileNotFoundError("local dataset missing")

    def close(self) -> None:
        return None


class FallbackContentClientTests(unittest.TestCase):
    def test_prefers_cache_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileContentCache(tmp)
            cache.set("content:list_races|page=1", {"results": [{"name": "Cached Elf"}]})
            primary = _FakeProvider(races_payload={"results": [{"name": "Network Elf"}]})
            fallback = _FakeProvider(races_payload={"results": [{"name": "Fallback Elf"}]})

            client = FallbackContentClient(
                primary_client=primary,
                fallback_client=fallback,
                cache=cache,
                cache_ttl_seconds=3600,
            )
            payload = client.list_races(page=1)

            self.assertEqual("Cached Elf", payload["results"][0]["name"])
            self.assertEqual(0, primary.calls)
            self.assertEqual(0, fallback.calls)

    def test_uses_fallback_when_primary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileContentCache(tmp)
            primary = _FakeProvider(should_fail=True)
            fallback = _FakeProvider(races_payload={"results": [{"name": "Fallback Elf"}]})

            client = FallbackContentClient(
                primary_client=primary,
                fallback_client=fallback,
                cache=cache,
                cache_ttl_seconds=3600,
            )
            payload = client.list_races(page=1)

            self.assertEqual("Fallback Elf", payload["results"][0]["name"])
            self.assertEqual(1, primary.calls)
            self.assertEqual(1, fallback.calls)

    def test_uses_stale_cache_if_providers_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileContentCache(tmp)
            cache.set("content:list_races|page=1", {"results": [{"name": "Stale Elf"}]})
            stale_path = cache._path_for_key("content:list_races|page=1")
            envelope = json.loads(stale_path.read_text(encoding="utf-8"))
            envelope["stored_at"] = 0
            stale_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
            primary = _FakeProvider(should_fail=True)
            fallback = _FakeProvider(should_fail=True)

            client = FallbackContentClient(
                primary_client=primary,
                fallback_client=fallback,
                cache=cache,
                cache_ttl_seconds=0,
            )
            payload = client.list_races(page=1)

            self.assertEqual("Stale Elf", payload["results"][0]["name"])
            self.assertEqual(1, primary.calls)
            self.assertEqual(1, fallback.calls)

    def test_ordered_providers_advance_until_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileContentCache(tmp)
            local = _UnavailableProvider()
            primary = _FakeProvider(should_fail=True)
            fallback = _FakeProvider(races_payload={"results": [{"name": "Remote Elf"}]})

            client = FallbackContentClient(
                providers=[local, primary, fallback],
                cache=cache,
                cache_ttl_seconds=3600,
            )
            payload = client.list_races(page=1)

            self.assertEqual("Remote Elf", payload["results"][0]["name"])
            self.assertEqual(1, local.calls)
            self.assertEqual(1, primary.calls)
            self.assertEqual(1, fallback.calls)


if __name__ == "__main__":
    unittest.main()

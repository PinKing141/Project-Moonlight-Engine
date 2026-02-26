import sys
from pathlib import Path
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.datamuse_client import DatamuseClient


class DatamuseClientTests(unittest.TestCase):
    def _client_with_handler(self, handler):
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(base_url="https://api.test", transport=transport)
        return DatamuseClient(base_url="https://api.test", http_client=http_client)

    def test_related_adjectives_calls_words_endpoint(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json=[{"word": "shadowy"}, {"word": "mossy"}])

        client = self._client_with_handler(handler)
        words = client.related_adjectives("ruins", max_words=4)

        self.assertEqual("/words", captured["path"])
        self.assertEqual("ruins", captured["params"].get("rel_jjb"))
        self.assertEqual("4", captured["params"].get("max"))
        self.assertEqual(["shadowy", "mossy"], words)
        client.close()

    def test_filters_invalid_words(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"word": "ok"}, {"word": "123"}, {"word": "!!!"}])

        client = self._client_with_handler(handler)
        words = client.related_adjectives("beast")
        self.assertEqual(["ok"], words)
        client.close()


if __name__ == "__main__":
    unittest.main()

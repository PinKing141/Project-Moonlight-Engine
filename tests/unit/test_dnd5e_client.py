import sys
from pathlib import Path
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.dnd5e_client import DnD5eClient


class DnD5eClientTests(unittest.TestCase):
    def _client_with_handler(self, handler):
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(base_url="https://api.test", transport=transport)
        return DnD5eClient(base_url="https://api.test", http_client=http_client)

    def test_list_races_uses_2014_endpoint(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            captured["accept"] = request.headers.get("accept")
            return httpx.Response(200, json={"results": [{"name": "Elf"}]})

        client = self._client_with_handler(handler)
        payload = client.list_races(page=3)

        self.assertEqual("/api/2014/races", captured["path"])
        self.assertEqual({"page": "3"}, captured["params"])
        self.assertEqual("application/json", captured["accept"])
        self.assertEqual("Elf", payload["results"][0]["name"])

        client.close()

    def test_get_monster_uses_slug_path(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200, json={"name": "Goblin"})

        client = self._client_with_handler(handler)
        payload = client.get_monster("goblin")

        self.assertEqual("/api/2014/monsters/goblin", captured["path"])
        self.assertEqual("Goblin", payload["name"])

        client.close()

    def test_get_api_index_uses_2014_root(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200, json={"races": "/api/2014/races"})

        client = self._client_with_handler(handler)
        payload = client.get_api_index()

        self.assertEqual("/api/2014", captured["path"])
        self.assertIn("races", payload)

        client.close()

    def test_list_endpoint_uses_dynamic_supported_endpoint(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"results": [{"index": "lawful-good"}]})

        client = self._client_with_handler(handler)
        payload = client.list_endpoint("alignments", page=2)

        self.assertEqual("/api/2014/alignments", captured["path"])
        self.assertEqual({"page": "2"}, captured["params"])
        self.assertEqual("lawful-good", payload["results"][0]["index"])

        client.close()

    def test_get_endpoint_resource_uses_dynamic_supported_endpoint(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200, json={"index": "blinded"})

        client = self._client_with_handler(handler)
        payload = client.get_endpoint_resource("conditions", "blinded")

        self.assertEqual("/api/2014/conditions/blinded", captured["path"])
        self.assertEqual("blinded", payload["index"])

        client.close()

    def test_list_endpoint_rejects_unknown_endpoint(self) -> None:
        client = self._client_with_handler(lambda _request: httpx.Response(200, json={}))
        with self.assertRaises(ValueError):
            client.list_endpoint("totally-unknown-endpoint")
        client.close()


if __name__ == "__main__":
    unittest.main()

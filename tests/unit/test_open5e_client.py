import sys
from pathlib import Path
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.open5e_client import Open5eClient


class Open5eClientRaceApiTests(unittest.TestCase):
    def _client_with_handler(self, handler):
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(base_url="https://api.test", transport=transport)
        return Open5eClient(base_url="https://api.test", http_client=http_client)

    def test_list_races_requests_races_endpoint(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"results": [{"name": "Elf", "slug": "elf"}]})

        client = self._client_with_handler(handler)
        payload = client.list_races(page=2)

        self.assertEqual("/races/", captured["path"])
        self.assertEqual({"page": "2"}, captured["params"])
        self.assertEqual("Elf", payload["results"][0]["name"])

        client.close()

    def test_get_race_requests_specific_slug(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200, json={"name": "High Elf", "speed": 35})

        client = self._client_with_handler(handler)
        payload = client.get_race("high-elf")

        self.assertEqual("/races/high-elf/", captured["path"])
        self.assertEqual("High Elf", payload["name"])
        self.assertEqual(35, payload["speed"])

        client.close()


if __name__ == "__main__":
    unittest.main()

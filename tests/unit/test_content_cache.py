import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.content_cache import FileContentCache


class FileContentCacheTests(unittest.TestCase):
    def test_writes_manifest_with_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileContentCache(tmp, data_version="1.2.3")
            manifest_path = Path(tmp) / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("1.2.3", manifest.get("data_version"))
            cache.set("content:key", {"ok": True})
            self.assertEqual({"ok": True}, cache.get("content:key", ttl_seconds=3600))

    def test_version_mismatch_invalidates_existing_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_cache = FileContentCache(tmp, data_version="1.0.0")
            first_cache.set("content:key", {"name": "old"})
            self.assertEqual({"name": "old"}, first_cache.get("content:key", ttl_seconds=3600))

            second_cache = FileContentCache(tmp, data_version="2.0.0")
            self.assertIsNone(second_cache.get("content:key", ttl_seconds=3600, allow_stale=True))
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("2.0.0", manifest.get("data_version"))


if __name__ == "__main__":
    unittest.main()

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.world_import.build_unified_reference_world import build_payload


class UnifiedReferenceWorldBuilderTests(unittest.TestCase):
    def test_build_payload_includes_dataset_and_counts(self) -> None:
        reference_dir = Path(__file__).resolve().parents[2] / "data" / "reference_world"

        payload = build_payload(reference_dir)

        self.assertIn("generated_at", payload)
        self.assertIn("counts", payload)
        self.assertIn("dataset", payload)

        counts = dict(payload.get("counts", {}) or {})
        self.assertGreaterEqual(int(counts.get("source_files", 0)), 1)
        self.assertGreaterEqual(int(counts.get("states", 0)), 1)
        self.assertGreaterEqual(int(counts.get("biome_rows", 0)), 1)
        self.assertGreaterEqual(int(counts.get("burg_rows", 0)), 1)
        self.assertGreaterEqual(int(counts.get("marker_rows", 0)), 1)
        self.assertGreaterEqual(int(counts.get("religion_rows", 0)), 1)
        self.assertGreaterEqual(int(counts.get("river_rows", 0)), 1)
        self.assertGreaterEqual(int(counts.get("route_rows", 0)), 1)

        dataset = dict(payload.get("dataset", {}) or {})
        self.assertIn("states_by_slug", dataset)
        self.assertIn("relations_matrix", dataset)
        self.assertIn("biome_severity_index", dataset)
        self.assertIn("burg_rows", dataset)
        self.assertIn("marker_rows", dataset)
        self.assertIn("religion_rows", dataset)
        self.assertIn("river_rows", dataset)
        self.assertIn("route_rows", dataset)


if __name__ == "__main__":
    unittest.main()

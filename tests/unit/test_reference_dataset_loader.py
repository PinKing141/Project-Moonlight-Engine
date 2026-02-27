import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.game_service import GameService
from rpg.infrastructure.world_import.reference_dataset_loader import (
    discover_reference_files,
    load_reference_world_dataset,
)


class ReferenceDatasetLoaderTests(unittest.TestCase):
    def test_discover_reference_files_returns_latest_snapshot_per_prefix(self) -> None:
        reference_dir = Path(__file__).resolve().parents[2] / "reference_"

        files = discover_reference_files(reference_dir)

        self.assertIn("biomes", files)
        self.assertIn("states", files)
        self.assertIn("relations", files)
        self.assertTrue(str(files["biomes"].name).startswith("Pres Biomes "))

    def test_load_reference_world_dataset_parses_relations_matrix_and_biome_index(self) -> None:
        reference_dir = Path(__file__).resolve().parents[2] / "reference_"

        dataset = load_reference_world_dataset(reference_dir)

        self.assertTrue(bool(dataset.source_files))
        self.assertIn("temperate_deciduous_forest", dataset.biome_severity_index)
        self.assertIn("grirongria", dataset.relations_matrix)
        self.assertEqual(
            "Friendly",
            str(dataset.relations_matrix["grirongria"].get("ortarith", "")),
        )

    def test_biome_severity_values_are_bounded(self) -> None:
        reference_dir = Path(__file__).resolve().parents[2] / "reference_"

        dataset = load_reference_world_dataset(reference_dir)

        self.assertTrue(dataset.biome_severity_index)
        for value in dataset.biome_severity_index.values():
            self.assertGreaterEqual(int(value), 0)
            self.assertLessEqual(int(value), 100)

    def test_game_service_reference_dataset_intent_exposes_biome_index(self) -> None:
        payload = GameService.get_reference_world_dataset_intent()

        self.assertIn("available", payload)
        self.assertIn("source_files", payload)
        self.assertIn("biome_severity_index", payload)
        if bool(payload.get("available")):
            self.assertTrue(bool(payload.get("biome_severity_index")))

    def test_game_service_reference_dataset_intent_uses_default_biome_index_without_reference_data(self) -> None:
        with mock.patch.object(GameService, "_load_reference_world_dataset_cached", return_value=None):
            payload = GameService.get_reference_world_dataset_intent()

        self.assertFalse(bool(payload.get("available")))
        biome_index = dict(payload.get("biome_severity_index", {}) or {})
        self.assertTrue(bool(biome_index))
        self.assertIn("glacier", biome_index)

    def test_game_service_reference_dataset_intent_uses_file_backed_defaults(self) -> None:
        with mock.patch.object(GameService, "_load_reference_world_dataset_cached", return_value=None):
            with mock.patch.object(GameService, "_load_default_biome_severity_index", return_value={"obsidian_wastes": 88}):
                payload = GameService.get_reference_world_dataset_intent()

        biome_index = dict(payload.get("biome_severity_index", {}) or {})
        self.assertEqual(88, int(biome_index.get("obsidian_wastes", 0)))


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.infrastructure.name_generation import DnDCorpusNameGenerator


class NameGenerationProviderTests(unittest.TestCase):
    def test_suggest_character_name_is_deterministic_for_same_context(self) -> None:
        provider = DnDCorpusNameGenerator()

        first = provider.suggest_character_name(
            race_name="Elf",
            context={"class_index": 0, "existing_count": 1},
        )
        second = provider.suggest_character_name(
            race_name="Elf",
            context={"class_index": 0, "existing_count": 1},
        )

        self.assertTrue(first)
        self.assertEqual(first, second)

    def test_non_humanoid_entity_falls_back_to_default_name(self) -> None:
        provider = DnDCorpusNameGenerator()

        name = provider.generate_entity_name(
            default_name="Wolf",
            kind="beast",
            entity_id=2,
            level=1,
        )

        self.assertEqual("Wolf", name)

    def test_missing_corpus_uses_built_in_fallback_pool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            provider = DnDCorpusNameGenerator(data_dir=missing)

            first = provider.suggest_character_name(
                race_name="Human",
                context={"class_index": 0, "existing_count": 0},
            )
            second = provider.suggest_character_name(
                race_name="Human",
                context={"class_index": 0, "existing_count": 0},
            )

        self.assertTrue(first)
        self.assertNotEqual("Nameless One", first)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

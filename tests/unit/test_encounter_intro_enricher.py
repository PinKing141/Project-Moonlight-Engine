import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.encounter_intro_enricher import EncounterIntroEnricher
from rpg.domain.models.entity import Entity


class _FakeLexicalClient:
    def __init__(self, words=None, should_fail: bool = False):
        self.words = words or []
        self.should_fail = should_fail

    def related_adjectives(self, noun: str, max_words: int = 8) -> list[str]:
        if self.should_fail:
            raise RuntimeError("lexical down")
        return list(self.words)


def _enemy(name: str = "Goblin Raider", kind: str = "humanoid") -> Entity:
    return Entity(
        id=1,
        name=name,
        level=1,
        hp=6,
        attack_min=1,
        attack_max=3,
        armor=0,
        kind=kind,
    )


class EncounterIntroEnricherTests(unittest.TestCase):
    def test_disabled_returns_base_intro(self) -> None:
        enricher = EncounterIntroEnricher(enabled=False)
        intro = enricher.build_intro(_enemy())
        self.assertTrue(intro)
        self.assertNotIn("The moment feels", intro)

    def test_enabled_appends_single_flavour_sentence(self) -> None:
        enricher = EncounterIntroEnricher(
            lexical_client=_FakeLexicalClient(words=["grim", "ashen"]),
            enabled=True,
            max_extra_lines=1,
        )
        intro = enricher.build_intro(_enemy(name="Bone Knight", kind="undead"))
        self.assertIn("The moment feels", intro)
        self.assertEqual(1, intro.count("The moment feels"))

    def test_lexical_failure_falls_back_cleanly(self) -> None:
        enricher = EncounterIntroEnricher(
            lexical_client=_FakeLexicalClient(should_fail=True),
            enabled=True,
            max_extra_lines=1,
        )
        intro = enricher.build_intro(_enemy())
        self.assertTrue(intro)
        self.assertNotIn("The moment feels", intro)


if __name__ == "__main__":
    unittest.main()

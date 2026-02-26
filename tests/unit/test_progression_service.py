import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.progression_service import ProgressionService
from rpg.domain.events import LevelUpAppliedEvent, LevelUpPendingEvent
from rpg.domain.models.character import Character


class ProgressionServiceTests(unittest.TestCase):
    def test_preview_pending_returns_next_level_when_threshold_met(self) -> None:
        service = ProgressionService()
        character = Character(id=1, name="Ayla", level=1, xp=25)

        pending = service.preview_pending(character)

        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(1, pending.current_level)
        self.assertEqual(2, pending.next_level)
        self.assertIn("vitality", pending.growth_choices)

    def test_apply_level_progression_emits_pending_and_applied_events(self) -> None:
        emitted: list[object] = []
        service = ProgressionService(event_publisher=lambda event: emitted.append(event))
        character = Character(id=7, name="Bran", level=1, xp=55)

        messages = service.apply_level_progression(character, growth_choice="vitality")

        self.assertEqual(3, character.level)
        self.assertGreater(character.hp_max, 10)
        self.assertTrue(messages)
        self.assertTrue(any(isinstance(event, LevelUpPendingEvent) for event in emitted))
        self.assertTrue(any(isinstance(event, LevelUpAppliedEvent) for event in emitted))

    def test_apply_level_progression_tracks_feature_unlock_choice(self) -> None:
        service = ProgressionService()
        character = Character(id=4, name="Nira", level=1, xp=25)

        messages = service.apply_level_progression(character, growth_choice="feat")

        self.assertTrue(messages)
        flags = character.flags if isinstance(character.flags, dict) else {}
        unlocks = flags.get("progression_unlocks", {})
        self.assertTrue(unlocks.get("level_2_feat"))


if __name__ == "__main__":
    unittest.main()

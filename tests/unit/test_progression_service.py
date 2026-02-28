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
        self.assertIn("adventurer", pending.class_options)

    def test_preview_pending_includes_existing_and_available_class_options(self) -> None:
        service = ProgressionService()
        character = Character(
            id=2,
            name="Cato",
            class_name="fighter",
            class_levels={"fighter": 2, "wizard": 1},
            level=3,
            xp=75,
        )

        pending = service.preview_pending(character, available_classes=["rogue", "fighter"])

        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertIn("fighter", pending.class_options)
        self.assertIn("wizard", pending.class_options)
        self.assertIn("rogue", pending.class_options)

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

    def test_apply_level_progression_advances_selected_multiclass(self) -> None:
        service = ProgressionService()
        character = Character(
            id=18,
            name="Mira",
            class_name="fighter",
            class_levels={"fighter": 2, "wizard": 1},
            level=3,
            xp=75,
        )

        messages = service.apply_level_progression(
            character,
            growth_choice="vitality",
            class_choice="wizard",
        )

        self.assertTrue(messages)
        self.assertEqual(4, int(character.level))
        self.assertEqual(2, int(character.class_levels.get("wizard", 0)))
        self.assertEqual(2, int(character.class_levels.get("fighter", 0)))

    def test_level_up_awards_skill_points_from_proficiency_bonus(self) -> None:
        service = ProgressionService()
        character = Character(id=10, name="Kade", class_name="fighter", level=1, xp=25)

        service.apply_level_progression(character, growth_choice="vitality")

        flags = character.flags if isinstance(character.flags, dict) else {}
        training = flags.get("skill_training", {}) if isinstance(flags.get("skill_training", {}), dict) else {}
        self.assertEqual(2, int(training.get("points_available", 0) or 0))
        self.assertEqual(2, int(training.get("points_source_level", 0) or 0))

    def test_new_skill_requires_intent_and_starts_at_two(self) -> None:
        service = ProgressionService()
        character = Character(id=11, name="Vale", class_name="fighter", level=2, xp=25)
        character.flags = {
            "skill_training": {
                "points_available": 2,
                "points_source_level": 2,
                "intent": [],
                "modifiers": {},
            }
        }

        with self.assertRaises(ValueError):
            service.spend_skill_proficiency_points(character, {"athletics": 1})

        service.declare_skill_training_intent(character, ["athletics"])
        messages = service.spend_skill_proficiency_points(character, {"athletics": 1})

        self.assertTrue(messages)
        training = character.flags.get("skill_training", {})
        modifiers = training.get("modifiers", {}) if isinstance(training.get("modifiers", {}), dict) else {}
        self.assertEqual(2, int(modifiers.get("athletics", 0) or 0))

    def test_skill_cap_is_proficiency_bonus_plus_one_max_six(self) -> None:
        service = ProgressionService()
        character = Character(id=12, name="Iris", class_name="wizard", level=2, xp=25)
        character.flags = {
            "skill_training": {
                "points_available": 3,
                "points_source_level": 2,
                "intent": ["arcana"],
                "modifiers": {"arcana": 3},
            }
        }

        with self.assertRaises(ValueError):
            service.spend_skill_proficiency_points(character, {"arcana": 1})

    def test_unspent_points_expire_when_next_level_is_applied(self) -> None:
        service = ProgressionService()
        character = Character(id=13, name="Rook", class_name="rogue", level=1, xp=55)
        character.flags = {
            "skill_training": {
                "points_available": 5,
                "points_source_level": 1,
                "intent": [],
                "modifiers": {},
            }
        }

        service.apply_level_progression(character, growth_choice="vitality")

        training = character.flags.get("skill_training", {})
        self.assertEqual(2, int(training.get("points_available", 0) or 0))
        self.assertEqual(3, int(training.get("points_source_level", 0) or 0))

    def test_rejects_new_skill_outside_class_and_background_categories(self) -> None:
        service = ProgressionService()
        character = Character(
            id=14,
            name="Pax",
            class_name="fighter",
            level=2,
            xp=25,
            proficiencies=["Athletics"],
            flags={
                "skill_training": {
                    "points_available": 2,
                    "points_source_level": 2,
                    "intent": ["arcana"],
                    "modifiers": {},
                }
            },
        )

        with self.assertRaises(ValueError):
            service.spend_skill_proficiency_points(character, {"arcana": 1})

    def test_special_skill_requires_explicit_special_approval(self) -> None:
        service = ProgressionService()
        character = Character(id=15, name="Mira", class_name="cleric", level=2, xp=25)
        character.flags = {
            "skill_training": {
                "points_available": 2,
                "points_source_level": 2,
                "intent": ["language"],
                "modifiers": {},
            }
        }

        with self.assertRaises(ValueError):
            service.spend_skill_proficiency_points(character, {"language": 1})

        messages = service.spend_skill_proficiency_points(character, {"language": 1}, allow_special=True)
        self.assertTrue(messages)

    def test_subclass_advancement_unlocks_on_class_tier_level(self) -> None:
        service = ProgressionService()
        character = Character(id=16, name="Dren", class_name="fighter", level=2, xp=50)
        character.flags = {
            "subclass_slug": "paragon",
            "subclass_name": "The Paragon",
        }

        messages = service.apply_level_progression(character, growth_choice="vitality")

        self.assertTrue(any("Subclass advancement unlocked" in line for line in messages))
        flags = character.flags if isinstance(character.flags, dict) else {}
        unlocks = flags.get("progression_unlocks", {}) if isinstance(flags.get("progression_unlocks", {}), dict) else {}
        self.assertTrue(bool(unlocks.get("subclass_paragon_tier_1")))

    def test_subclass_advancement_unlocks_multiple_tiers_when_leveling_past_breakpoints(self) -> None:
        service = ProgressionService()
        character = Character(id=17, name="Ila", class_name="wizard", level=1, xp=55)
        character.flags = {
            "subclass_slug": "crimson_spire",
            "subclass_name": "School of Evocation",
        }

        service.apply_level_progression(character, growth_choice="spell")

        flags = character.flags if isinstance(character.flags, dict) else {}
        unlocks = flags.get("progression_unlocks", {}) if isinstance(flags.get("progression_unlocks", {}), dict) else {}
        self.assertTrue(bool(unlocks.get("subclass_crimson_spire_tier_1")))
        progression = flags.get("subclass_progression", {}) if isinstance(flags.get("subclass_progression", {}), dict) else {}
        unlocked_tiers = list(progression.get("unlocked_tiers", []) or [])
        self.assertIn(1, unlocked_tiers)


if __name__ == "__main__":
    unittest.main()

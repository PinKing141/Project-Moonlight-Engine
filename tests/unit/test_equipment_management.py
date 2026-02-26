import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.event_bus import EventBus
from rpg.application.services.game_service import GameService
from rpg.application.services.combat_service import CombatService
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character import Character
from rpg.domain.models.location import Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class EquipmentManagementTests(unittest.TestCase):
    def _build_service(self):
        event_bus = EventBus()
        world_repo = InMemoryWorldRepository(seed=21)
        character = Character(
            id=808,
            name="Rook",
            location_id=1,
            inventory=["Longsword", "Shield", "Healing Herbs", "Holy Symbol"],
        )
        character_repo = InMemoryCharacterRepository({character.id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository({1: Location(id=1, name="Town")})
        progression = WorldProgression(world_repo, entity_repo, event_bus)
        service = GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
        )
        return service, character_repo, character.id

    def test_equipment_view_flags_equipable_items(self):
        service, _character_repo, character_id = self._build_service()

        view = service.get_equipment_view_intent(character_id)
        by_name = {row.name: row for row in view.inventory_items}

        self.assertTrue(by_name["Longsword"].equipable)
        self.assertEqual("weapon", by_name["Longsword"].slot)
        self.assertTrue(by_name["Shield"].equipable)
        self.assertEqual("armor", by_name["Shield"].slot)
        self.assertFalse(by_name["Healing Herbs"].equipable)

    def test_equip_inventory_item_updates_equipment_flags(self):
        service, character_repo, character_id = self._build_service()

        result = service.equip_inventory_item_intent(character_id, "Longsword")
        updated = character_repo.get(character_id)

        self.assertIn("Equipped Longsword", " ".join(result.messages))
        self.assertEqual("Longsword", updated.flags.get("equipment", {}).get("weapon"))

    def test_non_equipable_item_returns_message(self):
        service, character_repo, character_id = self._build_service()

        result = service.equip_inventory_item_intent(character_id, "Healing Herbs")
        updated = character_repo.get(character_id)

        self.assertIn("cannot be equipped", " ".join(result.messages).lower())
        self.assertEqual({}, updated.flags.get("equipment", {}))

    def test_unequip_slot_clears_equipped_item(self):
        service, character_repo, character_id = self._build_service()
        service.equip_inventory_item_intent(character_id, "Longsword")

        result = service.unequip_slot_intent(character_id, "weapon")
        updated = character_repo.get(character_id)

        self.assertIn("Unequipped Longsword", " ".join(result.messages))
        self.assertNotIn("weapon", updated.flags.get("equipment", {}))

    def test_drop_inventory_item_removes_item(self):
        service, character_repo, character_id = self._build_service()

        result = service.drop_inventory_item_intent(character_id, "Healing Herbs")
        updated = character_repo.get(character_id)

        self.assertIn("Dropped Healing Herbs", " ".join(result.messages))
        self.assertNotIn("Healing Herbs", updated.inventory)

    def test_drop_equipped_item_unequips_when_last_copy_removed(self):
        service, character_repo, character_id = self._build_service()
        service.equip_inventory_item_intent(character_id, "Longsword")

        result = service.drop_inventory_item_intent(character_id, "Longsword")
        updated = character_repo.get(character_id)

        self.assertNotIn("Longsword", updated.inventory)
        self.assertNotIn("weapon", updated.flags.get("equipment", {}))
        self.assertIn("also unequipped", " ".join(result.messages))

    def test_combat_stats_use_equipped_slots_over_inventory(self):
        service, character_repo, character_id = self._build_service()
        hero = character_repo.get(character_id)
        hero.class_name = "fighter"
        hero.attributes["strength"] = 14
        hero.attributes["dexterity"] = 10
        hero.inventory.extend(["Chain Mail", "Shield"])
        character_repo.save(hero)

        service.equip_inventory_item_intent(character_id, "Longsword")
        updated = character_repo.get(character_id)
        stats = CombatService().derive_player_stats(updated)

        self.assertEqual("d8", stats["weapon_die"])
        self.assertEqual(10, stats["ac"], "Inventory armor should not apply once equipped-state exists.")

    def test_combat_stats_fallback_when_no_equipment_state(self):
        service, character_repo, character_id = self._build_service()
        hero = character_repo.get(character_id)
        hero.class_name = "fighter"
        hero.attributes["dexterity"] = 10
        hero.inventory.extend(["Chain Mail", "Shield"])
        hero.flags = {}
        character_repo.save(hero)

        stats = CombatService().derive_player_stats(character_repo.get(character_id))

        self.assertGreaterEqual(stats["ac"], 18)


if __name__ == "__main__":
    unittest.main()

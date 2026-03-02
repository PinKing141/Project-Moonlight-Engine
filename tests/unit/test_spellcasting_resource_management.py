import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg.application.services.combat_service import CombatLogEntry, CombatService
from rpg.application.services.game_service import GameService
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import Location
from rpg.domain.models.spell import Spell
from rpg.domain.repositories import SpellRepository
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)


class _StubSpellRepository(SpellRepository):
    def __init__(self, spells: dict[str, Spell]) -> None:
        self._spells = dict(spells)

    def get_by_slug(self, slug: str):
        return self._spells.get(str(slug))

    def list_by_class(self, class_slug: str, max_level: int):
        _ = class_slug
        _ = max_level
        return []


class SpellcastingResourceManagementTests(unittest.TestCase):
    def _build_game_service(self, *, character: Character, spell_repo: SpellRepository) -> GameService:
        character_id = int(character.id or 0)
        character_repo = InMemoryCharacterRepository({character_id: character})
        entity_repo = InMemoryEntityRepository([])
        location_repo = InMemoryLocationRepository(
            {
                1: Location(id=1, name="Town"),
                2: Location(id=2, name="Wilds", biome="forest"),
            }
        )
        world_repo = InMemoryWorldRepository(seed=11)
        return GameService(
            character_repo=character_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            spell_repo=spell_repo,
        )

    def test_list_spell_options_uses_slot_ledger_levels(self) -> None:
        spells = {
            "magic-missile": Spell(slug="magic-missile", name="Magic Missile", level_int=1, components="V,S"),
            "fire-bolt": Spell(slug="fire-bolt", name="Fire Bolt", level_int=0, components="V,S"),
        }
        character = Character(id=1, name="Ari", class_name="wizard", location_id=1)
        character.known_spells = ["Magic Missile", "Fire Bolt"]
        character.flags["spell_slot_ledger"] = {
            "max": {"1": 2, "2": 1},
            "current": {"1": 0, "2": 1},
        }
        service = self._build_game_service(character=character, spell_repo=_StubSpellRepository(spells))

        options = service.list_spell_options(character)
        by_slug = {row.slug: row for row in options}

        self.assertTrue(by_slug["magic-missile"].playable)
        self.assertEqual([2], by_slug["magic-missile"].cast_levels)
        self.assertTrue(by_slug["fire-bolt"].playable)
        self.assertEqual([], by_slug["fire-bolt"].cast_levels)

    def test_submit_combat_action_intent_encodes_cast_metadata(self) -> None:
        options = ["Attack", "Cast Spell", "Dodge"]
        choice = GameService.submit_combat_action_intent(
            options,
            1,
            spell_slug="magic-missile",
            cast_level=2,
            use_ritual=True,
        )
        self.assertEqual(("Cast Spell", "slug=magic-missile|level=2|ritual=1"), choice)

    def test_combat_spell_cast_blocks_verbal_components_when_silenced(self) -> None:
        spells = {
            "magic-missile": Spell(slug="magic-missile", name="Magic Missile", level_int=1, components="V,S"),
        }
        service = CombatService(spell_repo=_StubSpellRepository(spells), verbosity="compact")
        player = Character(id=2, name="Iris", class_name="wizard", hp_current=12, hp_max=12)
        player.known_spells = ["Magic Missile"]
        player.flags["spell_slot_ledger"] = {"max": {"1": 1}, "current": {"1": 1}}
        player.flags["combat_statuses"] = [{"id": "silenced", "rounds": 2, "potency": 1}]
        foe = Entity(id=7, name="Bandit", level=1, hp=10, hp_current=10, hp_max=10, armour_class=10)
        log: list[CombatLogEntry] = []

        service._resolve_spell_cast(player, foe, "magic-missile", spell_mod=3, prof=2, log=log)

        self.assertEqual(10, foe.hp_current)
        self.assertEqual(1, player.flags["spell_slot_ledger"]["current"]["1"])
        self.assertTrue(any("silenced" in row.text.lower() for row in log))

    def test_combat_spell_cast_consumes_requested_upcast_slot_level(self) -> None:
        spells = {
            "magic-missile": Spell(slug="magic-missile", name="Magic Missile", level_int=1, components="V,S"),
        }
        service = CombatService(spell_repo=_StubSpellRepository(spells), verbosity="compact")
        player = Character(id=3, name="Nyx", class_name="wizard", hp_current=12, hp_max=12)
        player.known_spells = ["Magic Missile"]
        player.flags["spell_slot_ledger"] = {"max": {"1": 1, "2": 1}, "current": {"1": 1, "2": 1}}
        foe = Entity(id=8, name="Raider", level=1, hp=14, hp_current=14, hp_max=14, armour_class=10)
        log: list[CombatLogEntry] = []

        service._resolve_spell_cast(player, foe, "slug=magic-missile|level=2", spell_mod=3, prof=2, log=log)

        self.assertEqual(1, player.flags["spell_slot_ledger"]["current"]["1"])
        self.assertEqual(0, player.flags["spell_slot_ledger"]["current"]["2"])

    def test_attunement_requires_safe_location_and_enforces_cap(self) -> None:
        spells: dict[str, Spell] = {}
        character = Character(id=4, name="Kara", class_name="wizard", location_id=2)
        character.inventory = ["Arcane Focus Ring"]
        service = self._build_game_service(character=character, spell_repo=_StubSpellRepository(spells))

        blocked = service.equip_inventory_item_intent(4, "Arcane Focus Ring")
        self.assertTrue(any("safe location" in row.lower() for row in blocked.messages))

        character.location_id = 1
        character.flags["attuned_items"] = ["Moon Charm", "Sun Relic", "Storm Talisman"]
        capped = service.equip_inventory_item_intent(4, "Arcane Focus Ring")
        self.assertTrue(any("attunement cap" in row.lower() for row in capped.messages))

    def test_ritual_cast_advances_world_time_by_minutes(self) -> None:
        spells = {
            "detect-magic": Spell(slug="detect-magic", name="Detect Magic", level_int=1, ritual=True, components="V,S"),
        }
        character = Character(id=5, name="Mira", class_name="wizard", location_id=1)
        character.known_spells = ["Detect Magic"]
        character.flags["spell_slot_ledger"] = {"max": {"1": 1}, "current": {"1": 1}}
        service = self._build_game_service(character=character, spell_repo=_StubSpellRepository(spells))

        result = service.cast_world_spell_intent(5, "detect-magic", as_ritual=True)
        world = service._require_world()

        self.assertTrue(any("ritual casting" in row.lower() for row in result.messages))
        self.assertEqual(0, int(getattr(world, "current_turn", 0) or 0))
        self.assertEqual(10, int(getattr(world, "flags", {}).get("time_minutes_remainder", 0) or 0))


if __name__ == "__main__":
    unittest.main()

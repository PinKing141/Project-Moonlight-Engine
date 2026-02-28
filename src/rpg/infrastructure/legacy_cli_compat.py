import os

from sqlalchemy import text

from rpg.application.services.character_creation_service import CharacterCreationService
from rpg.application.services.encounter_intro_enricher import EncounterIntroEnricher
from rpg.application.services.mechanical_flavour_enricher import MechanicalFlavourEnricher
from rpg.application.services.event_bus import EventBus
from rpg.application.services.faction_influence_service import register_faction_influence_handlers
from rpg.application.services.game_service import GameService
from rpg.application.services.quest_service import register_quest_handlers
from rpg.application.services.story_director import register_story_director_handlers
from rpg.application.services.world_progression import WorldProgression
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.entity import Entity
from rpg.domain.models.location import EncounterTableEntry, Location
from rpg.infrastructure.db.inmemory.repos import (
    InMemoryCharacterRepository,
    InMemoryClassRepository,
    InMemoryEntityRepository,
    InMemoryLocationRepository,
    InMemoryWorldRepository,
)
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository
from rpg.infrastructure.inmemory.atomic_persistence import create_inmemory_atomic_persistor
from rpg.infrastructure.content_provider_factory import create_content_client
from rpg.infrastructure.datamuse_client import DatamuseClient
from rpg.infrastructure.name_generation import DnDCorpusNameGenerator
from rpg.infrastructure.db.mysql.connection import SessionLocal
from rpg.infrastructure.db.mysql.repos import (
    MysqlCharacterRepository,
    MysqlClassRepository,
    MysqlEntityRepository,
    MysqlEncounterDefinitionRepository,
    MysqlFactionRepository,
    MysqlLocationRepository,
    MysqlNarrativeStateRepository,
    MysqlSpellRepository,
    MysqlWorldRepository,
)
from rpg.infrastructure.db.mysql.atomic_persistence import save_character_and_world_atomic


def _build_encounter_intro_builder():
    enabled = os.getenv("RPG_FLAVOUR_DATAMUSE_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return EncounterIntroEnricher(enabled=False).build_intro

    timeout = float(os.getenv("RPG_FLAVOUR_TIMEOUT_S", "0.4"))
    retries = int(os.getenv("RPG_FLAVOUR_RETRIES", "0"))
    backoff_seconds = float(os.getenv("RPG_FLAVOUR_BACKOFF_S", "0.1"))
    max_lines = int(os.getenv("RPG_FLAVOUR_MAX_LINES", "1"))

    lexical = DatamuseClient(timeout=timeout, retries=retries, backoff_seconds=backoff_seconds)
    enricher = EncounterIntroEnricher(
        lexical_client=lexical,
        enabled=True,
        max_extra_lines=max_lines,
    )
    return enricher.build_intro


def _build_mechanical_flavour_builder():
    enabled = os.getenv("RPG_MECHANICAL_FLAVOUR_DATAMUSE_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return None

    timeout = float(os.getenv("RPG_FLAVOUR_TIMEOUT_S", "0.4"))
    retries = int(os.getenv("RPG_FLAVOUR_RETRIES", "0"))
    backoff_seconds = float(os.getenv("RPG_FLAVOUR_BACKOFF_S", "0.1"))
    max_words = int(os.getenv("RPG_FLAVOUR_MAX_WORDS", "8"))

    lexical = DatamuseClient(timeout=timeout, retries=retries, backoff_seconds=backoff_seconds)
    enricher = MechanicalFlavourEnricher(lexical_client=lexical, enabled=True, max_words=max_words)

    def _build(**kwargs) -> str:
        if "actor" in kwargs:
            return enricher.build_combat_line(
                actor=str(kwargs.get("actor", "combatant")),
                action=str(kwargs.get("action", "act")),
                enemy_kind=str(kwargs.get("enemy_kind", "creature")),
                terrain=str(kwargs.get("terrain", "open")),
                round_no=int(kwargs.get("round_no", 1)),
            )
        return enricher.build_environment_line(
            event_kind=str(kwargs.get("event_kind", "event")),
            biome=str(kwargs.get("biome", "wilderness")),
            hazard_name=str(kwargs.get("hazard_name", "hazard")),
            world_turn=int(kwargs.get("world_turn", 0)),
        )

    return _build


def bootstrap() -> tuple[GameService, CharacterCreationService]:
    try:
        return bootstrap_mysql()
    except Exception as exc:  # pragma: no cover - safety fallback
        print(f"MySQL bootstrap failed ({exc}); falling back to in-memory state.")
    return bootstrap_inmemory()


def bootstrap_inmemory() -> tuple[GameService, CharacterCreationService]:
    event_bus = EventBus()
    world_repo = InMemoryWorldRepository(seed=42)
    char_repo = InMemoryCharacterRepository({})
    base = {
        "fighter": {"STR": 15, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "rogue": {"STR": 10, "DEX": 16, "CON": 12, "INT": 12, "WIS": 10, "CHA": 12},
        "wizard": {"STR": 8, "DEX": 12, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
    }
    class_repo = InMemoryClassRepository(
        [
            CharacterClass(
                id=1,
                name="Fighter",
                slug="fighter",
                hit_die="d10",
                primary_ability="strength",
                base_attributes=base["fighter"],
            ),
            CharacterClass(
                id=2,
                name="Rogue",
                slug="rogue",
                hit_die="d8",
                primary_ability="dexterity",
                base_attributes=base["rogue"],
            ),
            CharacterClass(
                id=3,
                name="Wizard",
                slug="wizard",
                hit_die="d6",
                primary_ability="intelligence",
                base_attributes=base["wizard"],
            ),
        ]
    )
    entity_repo = InMemoryEntityRepository(
        [
            Entity(
                id=1,
                name="Goblin Skirmisher",
                level=1,
                hp=8,
                attack_min=1,
                attack_max=4,
                armor=0,
                faction_id="mire_clan",
                tags=["raider", "skirmisher"],
                traits=["cowardly"],
                loot_tags=["scrap", "coin"],
            ),
            Entity(
                id=2,
                name="Dire Rat",
                level=1,
                hp=6,
                attack_min=1,
                attack_max=3,
                armor=0,
                faction_id="vermin_swarm",
                tags=["beast", "disease"],
                traits=["pack"],
                loot_tags=["pelt"],
            ),
            Entity(
                id=3,
                name="Cult Adept",
                level=2,
                hp=10,
                attack_min=2,
                attack_max=5,
                armor=1,
                faction_id="ashen_court",
                tags=["cult", "caster"],
                traits=["fanatic"],
                loot_tags=["relic", "ritual notes"],
            ),
        ]
    )
    faction_repo = InMemoryFactionRepository()
    entity_repo.set_location_entities(1, [1, 2, 3])
    location_repo = InMemoryLocationRepository(
        {
            1: Location(
                id=1,
                name="Old Ruins",
                base_level=1,
                recommended_level=1,
                biome="crumbling keep",
                factions=["ashen_court", "mire_clan"],
                tags=["ancient", "damp", "echoing"],
                encounters=[
                    EncounterTableEntry(entity_id=1, weight=4, max_level=3, tags=["raider"]),
                    EncounterTableEntry(entity_id=2, weight=3, max_level=2, tags=["beast"]),
                    EncounterTableEntry(entity_id=3, weight=2, min_level=2, max_level=4, faction_bias="ashen_court"),
                ],
            )
        }
    )
    progression = WorldProgression(world_repo, entity_repo, event_bus)
    register_faction_influence_handlers(event_bus, faction_repo=faction_repo, entity_repo=entity_repo, character_repo=char_repo)
    register_quest_handlers(event_bus, world_repo=world_repo, character_repo=char_repo)
    register_story_director_handlers(event_bus=event_bus, world_repo=world_repo)

    use_external_creation_content = os.getenv("RPG_CREATION_EXTERNAL_CONTENT", "0").strip().lower() in {"1", "true", "yes"}
    name_generator = DnDCorpusNameGenerator()
    creation_service = CharacterCreationService(
        char_repo,
        class_repo,
        location_repo,
        open5e_client=create_content_client() if use_external_creation_content else None,
        name_generator=name_generator,
    )

    atomic_persistor = create_inmemory_atomic_persistor(char_repo, world_repo)

    return (
        GameService(
            character_repo=char_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            faction_repo=faction_repo,
            atomic_state_persistor=atomic_persistor,
            encounter_intro_builder=_build_encounter_intro_builder(),
            mechanical_flavour_builder=_build_mechanical_flavour_builder(),
        ),
        creation_service,
    )


def bootstrap_mysql() -> tuple[GameService, CharacterCreationService]:
    event_bus = EventBus()
    world_repo = MysqlWorldRepository()
    char_repo = MysqlCharacterRepository()
    class_repo = MysqlClassRepository()
    entity_repo = MysqlEntityRepository()
    definition_repo = MysqlEncounterDefinitionRepository()
    faction_repo = MysqlFactionRepository()
    narrative_state_repo = MysqlNarrativeStateRepository()
    location_repo = MysqlLocationRepository()
    spell_repo = MysqlSpellRepository()
    ensure_mysql_seed()
    progression = WorldProgression(world_repo, entity_repo, event_bus)
    register_faction_influence_handlers(event_bus, faction_repo=faction_repo, entity_repo=entity_repo, character_repo=char_repo)
    register_quest_handlers(event_bus, world_repo=world_repo, character_repo=char_repo)
    register_story_director_handlers(event_bus=event_bus, world_repo=world_repo)

    use_external_creation_content = os.getenv("RPG_CREATION_EXTERNAL_CONTENT", "0").strip().lower() in {"1", "true", "yes"}
    name_generator = DnDCorpusNameGenerator()
    creation_service = CharacterCreationService(
        char_repo,
        class_repo,
        location_repo,
        open5e_client=create_content_client() if use_external_creation_content else None,
        name_generator=name_generator,
    )

    return (
        GameService(
            character_repo=char_repo,
            entity_repo=entity_repo,
            location_repo=location_repo,
            world_repo=world_repo,
            progression=progression,
            definition_repo=definition_repo,
            faction_repo=faction_repo,
            quest_state_repo=narrative_state_repo,
            location_state_repo=narrative_state_repo,
            spell_repo=spell_repo,
            encounter_intro_builder=_build_encounter_intro_builder(),
            mechanical_flavour_builder=_build_mechanical_flavour_builder(),
        ),
        creation_service,
    )


def ensure_mysql_seed() -> None:
    """Ensure minimal data exists for the CLI to run against MySQL."""
    with SessionLocal() as session:
        world_id = session.execute(text("SELECT world_id FROM world LIMIT 1")).scalar()
        if not world_id:
            session.execute(
                text(
                    """
                    INSERT INTO world (name, current_turn, threat_level, flags)
                    VALUES ('Default World', 0, 0, '{}')
                    """
                )
            )

        place_id = session.execute(text("SELECT place_id FROM place LIMIT 1")).scalar()
        if not place_id:
            session.execute(text("INSERT INTO place (name) VALUES (:name)"), {"name": "Starting Town"})
            place_id = session.execute(text("SELECT place_id FROM place LIMIT 1")).scalar()

        location_id = session.execute(text("SELECT location_id FROM location LIMIT 1")).scalar()
        if not location_id:
            session.execute(
                text("INSERT INTO location (x, y, place_id) VALUES (0, 0, :pid)"),
                {"pid": place_id},
            )

        player_type_id = session.execute(
            text("SELECT character_type_id FROM character_type WHERE name = :name LIMIT 1"),
            {"name": "player"},
        ).scalar()
        if not player_type_id:
            session.execute(text("INSERT INTO character_type (name) VALUES ('player')"))

        starters = [
            {"name": "Fighter", "slug": "fighter", "hit_die": "d10", "primary": "strength"},
            {"name": "Rogue", "slug": "rogue", "hit_die": "d8", "primary": "dexterity"},
            {"name": "Wizard", "slug": "wizard", "hit_die": "d6", "primary": "intelligence"},
        ]

        for entry in starters:
            session.execute(
                text(
                    """
                    INSERT INTO class (name, open5e_slug, hit_die, primary_ability, source)
                    VALUES (:name, :slug, :hit_die, :primary, 'seed')
                    ON DUPLICATE KEY UPDATE
                        hit_die = VALUES(hit_die),
                        primary_ability = VALUES(primary_ability),
                        source = VALUES(source)
                    """
                ),
                entry,
            )

        session.commit()


def main_menu_loop(
    game: GameService, creation_service: CharacterCreationService
) -> int | None:
    """Allow the player to pick an existing character or create a new one."""

    while True:
        characters = game.list_characters()

        print("=== MAIN MENU ===")
        if characters:
            print("Select a character to continue:")
            for idx, char in enumerate(characters, start=1):
                status = " (DEAD)" if not char.alive else ""
                print(
                    f"  {idx}) {char.name} — level {char.level} "
                    f"{char.class_name or 'Adventurer'}{status}"
                )
            print("  N) Create new character")
            print("  Q) Quit")

            choice = input("> ").strip().lower()
            if choice == "q":
                return None
            if choice == "n":
                return run_character_creator(creation_service)
            if choice.isdigit() and 1 <= int(choice) <= len(characters):
                return characters[int(choice) - 1].id or 0

            print("Invalid choice. Try again.\n")
        else:
            print("No characters found. Let's create a new hero!\n")
            return run_character_creator(creation_service)


def run_game_loop(game: GameService, player_id: int) -> None:
    game_over = False
    while not game_over:
        view = game.get_player_view(player_id)
        print(view)
        choice = input(">>> ")
        result = game.make_choice(player_id, choice)
        for msg in result.messages:
            print(msg)
        game_over = result.game_over


def run_character_creator(character_creation_service: CharacterCreationService) -> int:
    print("=== Character Creation ===")
    name = input("Enter your character's name: ").strip()

    available = character_creation_service.list_classes()
    for idx, cls in enumerate(available, start=1):
        ability = f" ({cls.primary_ability})" if cls.primary_ability else ""
        print(f"{idx}) {cls.name}{ability}")

    choice = input("> ").strip()
    selected_idx = int(choice) - 1 if choice.isdigit() else 0
    selected_idx = max(0, min(selected_idx, len(available) - 1))
    chosen = available[selected_idx]

    character = character_creation_service.create_character(name, selected_idx)

    print(f"\nCreated {character.name}, a level {character.level} {chosen.name}")
    print(f"HP: {character.hp_current}/{character.hp_max}")
    print(f"Starting at location ID {character.location_id}")
    return character.id or 0

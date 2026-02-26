import os
import socket
from urllib.parse import urlparse
from rpg.domain.models.feature import Feature
from rpg.application.services.encounter_intro_enricher import EncounterIntroEnricher
from rpg.application.services.mechanical_flavour_enricher import MechanicalFlavourEnricher
from rpg.application.services.event_bus import EventBus
from rpg.application.services.faction_influence_service import register_faction_influence_handlers
from rpg.application.services.game_service import GameService
from rpg.application.services.quest_service import register_quest_handlers
from rpg.application.services.story_director import register_story_director_handlers
from rpg.application.services.world_progression import WorldProgression
from rpg.infrastructure.inmemory.inmemory_character_repo import InMemoryCharacterRepository
from rpg.infrastructure.inmemory.inmemory_class_repo import InMemoryClassRepository
from rpg.infrastructure.inmemory.inmemory_entity_repo import InMemoryEntityRepository
from rpg.infrastructure.inmemory.inmemory_encounter_definition_repo import (
    InMemoryEncounterDefinitionRepository,
)
from rpg.infrastructure.inmemory.inmemory_faction_repo import InMemoryFactionRepository
from rpg.infrastructure.inmemory.inmemory_feature_repo import InMemoryFeatureRepository
from rpg.infrastructure.inmemory.inmemory_location_repo import InMemoryLocationRepository
from rpg.infrastructure.inmemory.inmemory_world_repo import InMemoryWorldRepository
from rpg.infrastructure.content_provider_factory import create_content_client_factory
from rpg.infrastructure.datamuse_client import DatamuseClient
from rpg.infrastructure.name_generation import DnDCorpusNameGenerator


def _looks_like_local_mysql_unreachable(database_url: str) -> bool:
    if not database_url:
        return False

    parsed = urlparse(database_url)
    if not parsed.scheme.startswith("mysql"):
        return False

    host = (parsed.hostname or "").strip().lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        return False

    port = parsed.port or 3306
    timeout = float(os.getenv("RPG_DB_CONNECT_PROBE_TIMEOUT_S", "0.35"))

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return False
    except OSError:
        return True


def _build_encounter_intro_builder():
    enabled = os.getenv("RPG_FLAVOUR_DATAMUSE_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return EncounterIntroEnricher(enabled=False).build_intro

    timeout = float(os.getenv("RPG_FLAVOUR_TIMEOUT_S", "2"))
    retries = int(os.getenv("RPG_FLAVOUR_RETRIES", "1"))
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

    timeout = float(os.getenv("RPG_FLAVOUR_TIMEOUT_S", "2"))
    retries = int(os.getenv("RPG_FLAVOUR_RETRIES", "1"))
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


def _build_inmemory_game_service() -> GameService:
    verbosity = os.getenv("RPG_VERBOSITY", "compact").lower()
    use_external_creation_content = os.getenv("RPG_CREATION_EXTERNAL_CONTENT", "0").strip().lower() in {"1", "true", "yes"}
    content_client_factory = create_content_client_factory() if use_external_creation_content else None
    char_repo = InMemoryCharacterRepository()
    loc_repo = InMemoryLocationRepository()
    cls_repo = InMemoryClassRepository()
    name_generator = DnDCorpusNameGenerator()
    entity_repo = InMemoryEntityRepository(name_generator=name_generator)
    faction_repo = InMemoryFactionRepository()
    feature_repo = InMemoryFeatureRepository(
        {
            "feature.sneak_attack": Feature(
                id=1,
                slug="feature.sneak_attack",
                name="Sneak Attack",
                trigger_key="on_attack_hit",
                effect_kind="bonus_damage",
                effect_value=2,
                source="seed",
            ),
            "feature.darkvision": Feature(
                id=2,
                slug="feature.darkvision",
                name="Darkvision",
                trigger_key="on_initiative",
                effect_kind="initiative_bonus",
                effect_value=2,
                source="seed",
            ),
            "feature.martial_precision": Feature(
                id=3,
                slug="feature.martial_precision",
                name="Martial Precision",
                trigger_key="on_attack_roll",
                effect_kind="attack_bonus",
                effect_value=2,
                source="seed",
            ),
        }
    )
    definition_repo = InMemoryEncounterDefinitionRepository()
    world_repo = InMemoryWorldRepository()
    event_bus = EventBus()
    progression = WorldProgression(world_repo, entity_repo, event_bus)
    encounter_intro_builder = _build_encounter_intro_builder()
    mechanical_flavour_builder = _build_mechanical_flavour_builder()
    register_faction_influence_handlers(event_bus, faction_repo=faction_repo, entity_repo=entity_repo)
    register_quest_handlers(event_bus, world_repo=world_repo, character_repo=char_repo)
    register_story_director_handlers(event_bus=event_bus, world_repo=world_repo)

    return GameService(
        char_repo,
        location_repo=loc_repo,
        class_repo=cls_repo,
        entity_repo=entity_repo,
        world_repo=world_repo,
        progression=progression,
        definition_repo=definition_repo,
        faction_repo=faction_repo,
        feature_repo=feature_repo,
        open5e_client_factory=content_client_factory,
        name_generator=name_generator,
        encounter_intro_builder=encounter_intro_builder,
        mechanical_flavour_builder=mechanical_flavour_builder,
    )


def _build_mysql_game_service():
    # Attempt to hydrate from MySQL when RPG_DATABASE_URL is set
    from rpg.infrastructure.db.mysql.repos import (
        MysqlCharacterRepository,
        MysqlClassRepository,
        MysqlEntityRepository,
        MysqlFactionRepository,
        MysqlFeatureRepository,
        MysqlLocationRepository,
        MysqlNarrativeStateRepository,
        MysqlWorldRepository,
        MysqlSpellRepository,
    )
    from rpg.infrastructure.db.mysql.atomic_persistence import save_character_and_world_atomic

    char_repo = MysqlCharacterRepository()
    loc_repo = MysqlLocationRepository()
    cls_repo = MysqlClassRepository()
    entity_repo = MysqlEntityRepository()
    faction_repo = MysqlFactionRepository()
    narrative_state_repo = MysqlNarrativeStateRepository()
    feature_repo = MysqlFeatureRepository()
    world_repo = MysqlWorldRepository()
    name_generator = DnDCorpusNameGenerator()
    use_external_creation_content = os.getenv("RPG_CREATION_EXTERNAL_CONTENT", "0").strip().lower() in {"1", "true", "yes"}
    content_client_factory = create_content_client_factory() if use_external_creation_content else None
    encounter_intro_builder = _build_encounter_intro_builder()
    mechanical_flavour_builder = _build_mechanical_flavour_builder()
    spell_repo = MysqlSpellRepository()

    event_bus = EventBus()
    progression = WorldProgression(world_repo, entity_repo, event_bus)
    register_faction_influence_handlers(event_bus, faction_repo=faction_repo, entity_repo=entity_repo)
    register_quest_handlers(event_bus, world_repo=world_repo, character_repo=char_repo)
    register_story_director_handlers(event_bus=event_bus, world_repo=world_repo)

    # Force an early connectivity check so fallback happens before entering menus.
    try:
        world_repo.load_default()
    except Exception as exc:
        raise RuntimeError(f"MySQL bootstrap probe failed: {exc}") from exc

    return GameService(
        char_repo,
        location_repo=loc_repo,
        class_repo=cls_repo,
        entity_repo=entity_repo,
        faction_repo=faction_repo,
        quest_state_repo=narrative_state_repo,
        location_state_repo=narrative_state_repo,
        feature_repo=feature_repo,
        spell_repo=spell_repo,
        world_repo=world_repo,
        progression=progression,
        atomic_state_persistor=save_character_and_world_atomic,
        open5e_client_factory=content_client_factory,
        name_generator=name_generator,
        encounter_intro_builder=encounter_intro_builder,
        mechanical_flavour_builder=mechanical_flavour_builder,
    )


def create_game_service() -> GameService:
    use_mysql = os.getenv("RPG_DATABASE_URL")
    if use_mysql:
        if _looks_like_local_mysql_unreachable(use_mysql):
            print("MySQL appears unreachable, falling back to in-memory.")
            return _build_inmemory_game_service()
        try:
            return _build_mysql_game_service()
        except Exception as exc:  # pragma: no cover - best-effort fallback
            print(f"MySQL unavailable, falling back to in-memory. Reason: {exc}")

    return _build_inmemory_game_service()

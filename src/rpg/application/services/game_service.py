import json
import random
from collections.abc import Callable, Sequence
from typing import Optional, cast

from rpg.application.dtos import (
    ActionResult,
    CharacterSheetView,
    CombatRoundView,
    CharacterCreationSummaryView,
    CharacterSummaryView,
    EncounterPlan,
    EquipmentView,
    EnemyView,
    ExploreView,
    LevelUpPendingView,
    FactionStandingsView,
    GameLoopView,
    LocationContextView,
    NpcInteractionView,
    QuestBoardView,
    QuestJournalSectionView,
    QuestJournalView,
    QuestStateView,
    RewardOutcomeView,
    SellInventoryView,
    RumourBoardView,
    RumourItemView,
    SocialOutcomeView,
    ShopView,
    SpellOptionView,
    TravelDestinationView,
    TravelPrepView,
    TrainingView,
    TownView,
)
from rpg.application.mappers.game_service_mapper import (
    to_combat_enemy_panel_view,
    to_combat_player_panel_view,
    to_combat_round_view,
    to_combat_scene_view,
    to_quest_board_view,
    to_quest_state_view,
    to_rumour_board_view,
    to_rumour_item_view,
    to_sell_inventory_view,
    to_sell_item_view,
    to_shop_item_view,
    to_shop_view,
    to_town_npc_view,
    to_town_view,
    to_travel_prep_option_view,
    to_travel_prep_view,
    to_equipment_item_view,
    to_equipment_view,
    to_training_option_view,
    to_training_view,
)
from rpg.application.services.seed_policy import derive_seed
from rpg.application.services.settlement_naming import generate_settlement_name
from rpg.application.services.settlement_layering import generate_town_layer_tags
from rpg.application.services.balance_tables import (
    LEVEL_CAP,
    FIRST_HUNT_QUEST_ID,
    monster_kill_gold,
    monster_kill_xp,
    rest_heal_amount,
    xp_required_for_level,
)
from rpg.application.services.world_progression import WorldProgression
from rpg.application.services.encounter_flavour import random_intro
from rpg.application.services.progression_service import ProgressionService
from rpg.domain.events import FactionReputationChangedEvent, MonsterSlain
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.faction import calculate_price_modifier
from rpg.domain.models.location import Location
from rpg.domain.models.world import World
from rpg.domain.repositories import (
    CharacterRepository,
    ClassRepository,
    EncounterDefinitionRepository,
    EntityRepository,
    FeatureRepository,
    FactionRepository,
    LocationRepository,
    LocationStateRepository,
    QuestStateRepository,
    WorldRepository,
    SpellRepository,
)


class GameService:
    _RUMOUR_HISTORY_MAX = 12
    _RUMOUR_HISTORY_TURN_WINDOW = 8
    _QUEST_TITLES = {
        FIRST_HUNT_QUEST_ID: "First Hunt",
        "trail_patrol": "Trail Patrol",
        "supply_drop": "Supply Drop",
        "crown_hunt_order": "Crown Hunt Order",
        "syndicate_route_run": "Syndicate Route Run",
        "forest_path_clearance": "Forest Path Clearance",
        "ruins_wayfinding": "Ruins Wayfinding",
    }
    _TOWN_NPCS = (
        {
            "id": "innkeeper_mara",
            "name": "Mara",
            "role": "Innkeeper",
            "temperament": "warm",
            "openness": 7,
            "aggression": 2,
        },
        {
            "id": "captain_ren",
            "name": "Captain Ren",
            "role": "Watch Captain",
            "temperament": "stern",
            "openness": 4,
            "aggression": 6,
        },
        {
            "id": "broker_silas",
            "name": "Silas",
            "role": "Rumour Broker",
            "temperament": "cynical",
            "openness": 5,
            "aggression": 3,
        },
    )
    _SHOP_ITEMS = (
        {
            "id": "healing_herbs",
            "name": "Healing Herbs",
            "description": "Common tonic ingredients.",
            "base_price": 6,
        },
        {
            "id": "sturdy_rations",
            "name": "Sturdy Rations",
            "description": "Field rations for long patrols.",
            "base_price": 4,
        },
        {
            "id": "focus_potion",
            "name": "Focus Potion",
            "description": "Restores one spell slot during combat.",
            "base_price": 14,
        },
        {
            "id": "whetstone",
            "name": "Whetstone",
            "description": "Sharpens your weapon for +1 damage this encounter.",
            "base_price": 11,
        },
        {
            "id": "wardens_token",
            "name": "Wardens Token",
            "description": "Recognized by local wardens and scouts.",
            "base_price": 10,
            "requires_faction": "wardens",
            "required_reputation": 3,
        },
    )
    _TRAVEL_PREP_ITEMS = (
        {
            "id": "trail_guards",
            "title": "Hire Trail Guards",
            "price": 8,
            "effect": "Safer route coverage; lowers risk and event pressure.",
            "risk_shift": -10,
            "event_roll_shift": -8,
            "event_cap_shift": -1,
            "day_shift": 0,
        },
        {
            "id": "packed_supplies",
            "title": "Pack Sturdy Supplies",
            "price": 6,
            "effect": "Better pace and fewer setbacks; shortens travel.",
            "risk_shift": -4,
            "event_roll_shift": -4,
            "event_cap_shift": 0,
            "day_shift": -1,
        },
        {
            "id": "caravan_contract",
            "title": "Secure Caravan Contract",
            "price": 10,
            "effect": "Heavier escort and scheduling; much safer but slower.",
            "risk_shift": -12,
            "event_roll_shift": -10,
            "event_cap_shift": -1,
            "day_shift": 1,
        },
    )
    _TRAINING_OPTIONS = (
        {
            "id": "streetwise_briefing",
            "title": "Streetwise Briefing",
            "cost": 8,
            "effect": "Unlocks Leverage Intel approach with Silas.",
            "unlock_key": "intel_leverage",
        },
        {
            "id": "watch_liaison_drills",
            "title": "Watch Liaison Drills",
            "cost": 12,
            "effect": "Unlocks Call In Favor approach with Captain Ren.",
            "unlock_key": "captain_favor",
            "requires_faction": "wardens",
            "required_reputation": 4,
        },
    )
    _RUMOUR_TEMPLATES = (
        {
            "id": "tracks_north",
            "text": "Hunters report fresh tracks north of town.",
            "source": "Hunters",
            "confidence": "credible",
            "faction_id": "wild",
        },
        {
            "id": "bridge_toll",
            "text": "A new bridge toll may be coming from the wardens.",
            "source": "Market chatter",
            "confidence": "uncertain",
            "faction_id": "wardens",
        },
        {
            "id": "crypt_lights",
            "text": "Blue lights were seen over the old crypt at dusk.",
            "source": "Night watch",
            "confidence": "credible",
            "faction_id": "undead",
        },
        {
            "id": "black_fletch",
            "text": "A black-fletched arrow was found near the river bend.",
            "source": "Scouts",
            "confidence": "uncertain",
            "faction_id": "wardens",
        },
        {
            "id": "grain_shortage",
            "text": "Merchants whisper about a short grain convoy this week.",
            "source": "Merchants",
            "confidence": "speculative",
            "faction_id": "wild",
        },
    )
    _EQUIPMENT_SLOT_KEYWORDS = {
        "weapon": (
            "sword",
            "axe",
            "bow",
            "dagger",
            "staff",
            "hammer",
            "mace",
            "spear",
            "rod",
            "scimitar",
            "rapier",
            "quarterstaff",
            "javelin",
            "dart",
            "wand",
        ),
        "armor": (
            "armor",
            "armour",
            "shield",
            "mail",
            "leather",
            "scale",
            "shirt",
            "cloak",
        ),
        "trinket": (
            "symbol",
            "amulet",
            "token",
            "ring",
            "kit",
            "tools",
            "pouch",
            "spellbook",
            "lute",
        ),
    }
    _EXPLORE_CACHE_ITEMS = (
        "Old Coin Pouch",
        "Scout Notes",
        "Traveler's Charm",
    )

    def __init__(
        self,
        character_repo: CharacterRepository,
        entity_repo: EntityRepository | None = None,
        location_repo: LocationRepository | None = None,
        world_repo: WorldRepository | None = None,
        progression: WorldProgression | None = None,
        class_repo: ClassRepository | None = None,
        definition_repo: EncounterDefinitionRepository | None = None,
        faction_repo: FactionRepository | None = None,
        quest_state_repo: QuestStateRepository | None = None,
        location_state_repo: LocationStateRepository | None = None,
        feature_repo: FeatureRepository | None = None,
        spell_repo: SpellRepository | None = None,
        atomic_state_persistor: Callable[..., None] | None = None,
        verbose_level: str = "compact",
        open5e_client_factory: Callable[[], object] | None = None,
        name_generator=None,
        encounter_intro_builder: Callable[[Entity], str] | None = None,
        mechanical_flavour_builder: Callable[..., str] | None = None,
    ) -> None:
        from rpg.application.services.character_creation_service import CharacterCreationService
        from rpg.application.services.encounter_service import EncounterService
        from rpg.application.services.combat_service import CombatService

        self.character_repo = character_repo
        self.entity_repo = entity_repo
        self.location_repo = location_repo
        self.world_repo = world_repo
        self.progression = progression
        self.definition_repo = definition_repo
        self.faction_repo = faction_repo
        self.quest_state_repo = quest_state_repo
        self.location_state_repo = location_state_repo
        self.feature_repo = feature_repo
        self.character_creation_service = None
        self.encounter_service = None
        self.combat_service = None
        self.spell_repo = spell_repo
        self.atomic_state_persistor = atomic_state_persistor
        self.verbose_level = verbose_level
        self.encounter_intro_builder = encounter_intro_builder or random_intro
        self.mechanical_flavour_builder = mechanical_flavour_builder
        event_publisher = None
        if self.progression and getattr(self.progression, "event_bus", None):
            event_publisher = self.progression.event_bus.publish
        self.progression_service = ProgressionService(event_publisher=event_publisher)

        if class_repo and location_repo:
            client = None
            if open5e_client_factory:
                try:
                    client = open5e_client_factory()
                except Exception:
                    client = None
            self.character_creation_service = CharacterCreationService(
                character_repo,
                class_repo,
                location_repo,
                open5e_client=client,
                name_generator=name_generator,
                feature_repo=feature_repo,
            )

        if entity_repo:
            self.encounter_service = EncounterService(
                entity_repo,
                definition_repo=definition_repo,
                faction_repo=faction_repo,
                rng_factory=lambda seed: random.Random(seed),
            )
            self.combat_service = CombatService(feature_repo=feature_repo, event_publisher=event_publisher)
            if self.combat_service is not None and mechanical_flavour_builder is not None:
                self.combat_service.mechanical_flavour_builder = mechanical_flavour_builder

    @staticmethod
    def _world_flag_projection(world: World) -> dict[str, object]:
        if not isinstance(getattr(world, "flags", None), dict):
            return {}
        flags = world.flags
        projected: dict[str, object] = {}

        stored_world_flags = flags.get("world_flags")
        if isinstance(stored_world_flags, dict):
            for key, value in stored_world_flags.items():
                projected[str(key)] = value

        quest_flags = flags.get("quest_world_flags")
        if isinstance(quest_flags, dict):
            for key, value in quest_flags.items():
                projected[f"quest:{key}"] = value

        return projected

    def rest(self, character_id: int) -> tuple[Character, Optional[World]]:
        character = self._require_character(character_id)
        heal_amount = rest_heal_amount(character.hp_max)
        character.hp_current = min(character.hp_current + heal_amount, character.hp_max)
        character.alive = True
        if hasattr(character, "spell_slots_max"):
            character.spell_slots_current = getattr(character, "spell_slots_max", 0)

        if self.atomic_state_persistor and self.world_repo:
            world = self.advance_world(ticks=1, persist=False)
            if world is None:
                self.character_repo.save(character)
            else:
                self.atomic_state_persistor(character, world)
        else:
            self.character_repo.save(character)
            world = self.advance_world(ticks=1)
        return character, world

    def rest_intent(self, character_id: int) -> ActionResult:
        self.rest(character_id)
        return ActionResult(messages=["You rest and feel restored."], game_over=False)

    def advance_world(self, ticks: int = 1, persist: bool = True):
        if not self.world_repo:
            return None

        # Prefer the progression pipeline if available.
        if self.progression:
            world = self._require_world()
            self.progression.tick(world, ticks=ticks, persist=persist)
            return world

        world = self.world_repo.load_default()
        if world is None:
            raise ValueError("World not initialized")
        world.advance_turns(ticks)
        if persist:
            self.world_repo.save(world)
        return world

    def explore(self, character_id: int):
        character = self._require_character(character_id)
        world = self._require_world()

        if not self.encounter_service:
            return EncounterPlan(enemies=[], source="disabled"), character, world

        location_id = character.location_id
        location = self.location_repo.get(int(location_id)) if self.location_repo and location_id is not None else None
        faction_bias = None
        if location and getattr(location, "factions", None):
            faction_bias = location.factions[0] if location.factions else None

        effective_level, effective_max_enemies, effective_faction_bias = self._encounter_flashpoint_adjustments(
            world,
            base_player_level=int(character.level),
            base_max_enemies=2,
            base_faction_bias=faction_bias,
        )

        plan = self.encounter_service.generate_plan(
            location_id=character.location_id or 0,
            player_level=effective_level,
            world_turn=world.current_turn,
            faction_bias=effective_faction_bias,
            max_enemies=effective_max_enemies,
            location_biome=str(getattr(location, "biome", "wilderness") or "wilderness"),
            world_flags=self._world_flag_projection(world),
        )

        self.advance_world(ticks=1)
        return plan, character, world

    def explore_intent(self, character_id: int) -> tuple[ExploreView, Character, list[Entity]]:
        plan, character, _ = self.explore(character_id)
        hazard_message = ""
        if plan.hazards:
            hazard_message, skip_encounter = self._resolve_explore_hazard(character, plan)
            if skip_encounter:
                return ExploreView(has_encounter=False, message=hazard_message, enemies=[]), character, []

        if plan.enemies and not self.is_combat_ready():
            message = self._apply_explore_no_combat_fallback(character, plan.enemies)
            if hazard_message:
                message = f"{hazard_message} {message}".strip()
            return ExploreView(has_encounter=False, message=message, enemies=[]), character, []

        view = self.build_explore_view(plan)
        if hazard_message:
            view = ExploreView(has_encounter=view.has_encounter, message=f"{hazard_message} {view.message}".strip(), enemies=view.enemies)
        if not view.has_encounter:
            event_message = self._apply_noncombat_explore_event(character)
            if event_message:
                message = f"{hazard_message} {event_message}".strip() if hazard_message else event_message
                view = ExploreView(has_encounter=False, message=message, enemies=[])
        return view, character, list(plan.enemies)

    def _resolve_explore_hazard(self, character: Character, plan: EncounterPlan) -> tuple[str, bool]:
        world = self._require_world()
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        hazard_names = [str(item) for item in plan.hazards if str(item).strip()]
        if not hazard_names:
            return "", False

        seed = derive_seed(
            namespace="explore.hazard.check",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "world_turn": int(getattr(world, "current_turn", 0)),
                "location_id": int(getattr(character, "location_id", 0) or 0),
                "biome": str(getattr(location, "biome", "wilderness") if location else "wilderness"),
                "hazards": tuple(hazard_names),
                "enemy_count": len(plan.enemies),
            },
        )
        rng = random.Random(seed)

        attrs = getattr(character, "attributes", {}) or {}
        dex = int(attrs.get("dexterity", attrs.get("agility", 10)) or 10)
        wis = int(attrs.get("wisdom", 10) or 10)
        skill_mod = max((dex - 10) // 2, (wis - 10) // 2)
        dc = 12 + min(4, len(hazard_names))
        roll = rng.randint(1, 20)
        total = roll + skill_mod
        lead_hazard = hazard_names[0]

        def _environment_suffix(event_kind: str) -> str:
            if not callable(self.mechanical_flavour_builder):
                return ""
            try:
                line = self.mechanical_flavour_builder(
                    event_kind=str(event_kind),
                    biome=str(getattr(location, "biome", "wilderness") if location else "wilderness"),
                    hazard_name=str(lead_hazard),
                    world_turn=int(getattr(world, "current_turn", 0)),
                )
            except Exception:
                return ""
            return f" {line}" if str(line).strip() else ""

        if total >= dc:
            return f"You navigate {lead_hazard} safely ({total} vs DC {dc}).{_environment_suffix('hazard_success')}".strip(), False

        hp_loss_cap = max(0, int(getattr(character, "hp_current", 1)) - 1)
        hp_loss = min(hp_loss_cap, max(1, int(getattr(character, "hp_max", 1)) // 14))
        if hp_loss > 0:
            character.hp_current = max(1, int(character.hp_current) - int(hp_loss))
        if hasattr(world, "threat_level"):
            world.threat_level = max(0, int(getattr(world, "threat_level", 0)) + 1)

        operations: list[Callable[[object], None]] = []
        if self.location_state_repo is not None and character.location_id is not None:
            operation_builder = getattr(self.location_state_repo, "build_location_flag_change_operation", None)
            if callable(operation_builder):
                operation = operation_builder(
                    location_id=int(character.location_id),
                    changed_turn=int(getattr(world, "current_turn", 0)),
                    flag_key="hazard:last_resolution",
                    old_value=None,
                    new_value=lead_hazard,
                    reason="explore_hazard_failed_check",
                )
                if callable(operation):
                    operations.append(cast(Callable[[object], None], operation))

        persisted = self._persist_character_world_atomic(character, world, operations=operations)
        if not persisted:
            self.character_repo.save(character)
            if self.world_repo:
                self.world_repo.save(world)
            if self.location_state_repo is not None and character.location_id is not None:
                try:
                    self.location_state_repo.record_flag_change(
                        location_id=int(character.location_id),
                        changed_turn=int(getattr(world, "current_turn", 0)),
                        flag_key="hazard:last_resolution",
                        old_value=None,
                        new_value=lead_hazard,
                        reason="explore_hazard_failed_check",
                    )
                except Exception:
                    pass

        forced_retreat = bool(plan.enemies) and rng.randint(1, 100) <= 35
        if forced_retreat:
            return (
                f"{lead_hazard} disrupts your route (-{hp_loss} HP). "
                f"You withdraw before combat.{_environment_suffix('hazard_failed')}"
            ).strip(), True
        return f"{lead_hazard} strains your advance (-{hp_loss} HP).{_environment_suffix('hazard_failed')}".strip(), False

    def get_player_view(self, player_id: int) -> str:
        world = self._require_world()
        character = self._require_character(player_id)
        location = None
        if self.location_repo and character.location_id is not None:
            location = self.location_repo.get(int(character.location_id))

        location_line = (
            f"in {location.name} [{location.biome}]"
            if location
            else "in an unknown place"
        )
        tags = ", ".join(location.tags) if location and location.tags else "quiet"
        factions = ", ".join(location.factions) if location and location.factions else "unclaimed"
        return (
            f"Turn {world.current_turn}\n"
            f"You are {character.name} (HP: {character.hp_current}/{character.hp_max}, Armor {character.armor}) {location_line}.\n"
            f"Local threats: {tags}; influence: {factions}; suggested level {location.recommended_level if location else '?'}\n"
            "Actions: explore, rest, quit"
        )

    def _apply_noncombat_explore_event(self, character: Character) -> str:
        world = self._require_world()
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        seed = derive_seed(
            namespace="explore.noncombat",
            context={
                "character_id": int(character.id or 0),
                "world_turn": int(getattr(world, "current_turn", 0)),
                "location_id": int(character.location_id or 0),
                "location_name": getattr(location, "name", "unknown") if location else "unknown",
            },
        )
        rng = random.Random(seed)
        roll = rng.randint(1, 100)

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags

        if roll <= 40:
            message = "You discover old trail marks that reveal safer routes ahead."
            event_kind = "discovery"
            self._append_consequence(
                world,
                kind="explore_discovery",
                message="Your scouting reveals useful wilderness routes.",
                severity="minor",
                turn=int(getattr(world, "current_turn", 0)),
            )
        elif roll <= 75:
            gold_gain = 2 + rng.randint(1, 5)
            cache_item = self._EXPLORE_CACHE_ITEMS[rng.randrange(len(self._EXPLORE_CACHE_ITEMS))]
            character.money = int(getattr(character, "money", 0)) + gold_gain
            character.inventory.append(cache_item)
            message = f"You uncover a hidden cache: +{gold_gain} gold and {cache_item}."
            event_kind = "cache"
            self._append_consequence(
                world,
                kind="explore_cache",
                message=f"A hidden cache yields {gold_gain} gold and supplies.",
                severity="minor",
                turn=int(getattr(world, "current_turn", 0)),
            )
        else:
            max_safe_loss = max(0, int(getattr(character, "hp_current", 1)) - 1)
            hp_loss = min(max_safe_loss, max(1, int(getattr(character, "hp_max", 1)) // 10))
            if hp_loss > 0:
                character.hp_current = max(1, int(character.hp_current) - int(hp_loss))
            if hasattr(world, "threat_level"):
                world.threat_level = max(0, int(world.threat_level) + 1)
            message = f"A sudden hazard drains {hp_loss} HP as danger rises." if hp_loss > 0 else "A sudden hazard rattles you, but you push through."
            event_kind = "hazard"
            self._append_consequence(
                world,
                kind="explore_hazard",
                message="A wilderness hazard leaves you battered and alerts nearby threats.",
                severity="normal",
                turn=int(getattr(world, "current_turn", 0)),
            )

        flags["last_explore_event"] = {
            "kind": event_kind,
            "turn": int(getattr(world, "current_turn", 0)),
            "seed": int(seed),
        }
        self.character_repo.save(character)
        if self.world_repo:
            self.world_repo.save(world)
        return message

    def _apply_explore_no_combat_fallback(self, character: Character, enemies: list[Entity]) -> str:
        world = self._require_world()
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        seed = derive_seed(
            namespace="explore.no_combat",
            context={
                "character_id": int(character.id or 0),
                "world_turn": int(getattr(world, "current_turn", 0)),
                "location_id": int(character.location_id or 0),
                "location_name": getattr(location, "name", "unknown") if location else "unknown",
                "enemy_ids": [int(getattr(enemy, "id", 0)) for enemy in enemies],
            },
        )
        rng = random.Random(seed)
        roll = rng.randint(1, 100)

        if hasattr(world, "threat_level"):
            world.threat_level = max(0, int(world.threat_level) + 1)

        hp_loss = 0
        if roll <= 60:
            max_safe_loss = max(0, int(getattr(character, "hp_current", 1)) - 1)
            hp_loss = min(max_safe_loss, max(1, int(getattr(character, "hp_max", 1)) // 12))
            if hp_loss > 0:
                character.hp_current = max(1, int(character.hp_current) - int(hp_loss))
            message = (
                f"You spot danger and withdraw before blades are drawn, losing {hp_loss} HP in the scramble."
                if hp_loss > 0
                else "You spot danger and withdraw before blades are drawn."
            )
        else:
            message = "You mark hostile movement and avoid direct combat; local danger rises."

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["last_explore_event"] = {
            "kind": "threat_no_combat",
            "turn": int(getattr(world, "current_turn", 0)),
            "seed": int(seed),
            "enemy_count": len(enemies),
        }

        self._append_consequence(
            world,
            kind="explore_no_combat_threat",
            message="You evade a hostile group before open combat, but threat pressure increases.",
            severity="normal",
            turn=int(getattr(world, "current_turn", 0)),
        )

        self.character_repo.save(character)
        if self.world_repo:
            self.world_repo.save(world)
        return message

    def list_characters(self) -> list[Character]:
        return self.character_repo.list_all()

    def list_character_summaries(self) -> list[CharacterSummaryView]:
        summaries: list[CharacterSummaryView] = []
        for character in self.character_repo.list_all():
            character_id = character.id or 0
            summaries.append(
                CharacterSummaryView(
                    id=character_id,
                    name=character.name,
                    level=character.level,
                    class_name=character.class_name or "Adventurer",
                    alive=character.alive,
                )
            )
        return summaries

    def get_game_loop_view(self, character_id: int) -> GameLoopView:
        character = self._require_character(character_id)
        world_state = self.world_repo.load_default() if self.world_repo else None
        return GameLoopView(
            character_id=character.id or 0,
            name=character.name,
            race=character.race or "",
            class_name=character.class_name or "Adventurer",
            difficulty=character.difficulty or "normal",
            hp_current=character.hp_current,
            hp_max=character.hp_max,
            world_turn=getattr(world_state, "current_turn", None),
            threat_level=getattr(world_state, "threat_level", None),
        )

    def get_character_sheet_intent(self, character_id: int) -> CharacterSheetView:
        character = self._require_character(character_id)
        level = max(1, int(getattr(character, "level", 1) or 1))
        xp = max(0, int(getattr(character, "xp", 0) or 0))
        if level >= LEVEL_CAP:
            next_level_xp = xp_required_for_level(level)
            xp_to_next = 0
        else:
            next_level_xp = xp_required_for_level(level + 1)
            xp_to_next = max(0, int(next_level_xp) - xp)
        return CharacterSheetView(
            character_id=int(character.id or 0),
            name=character.name,
            race=character.race or "",
            class_name=character.class_name or "Adventurer",
            difficulty=character.difficulty or "normal",
            level=level,
            xp=xp,
            next_level_xp=int(next_level_xp),
            xp_to_next_level=int(xp_to_next),
            hp_current=int(character.hp_current),
            hp_max=int(character.hp_max),
        )

    def get_level_up_pending_intent(self, character_id: int) -> LevelUpPendingView | None:
        character = self._require_character(character_id)
        return self.progression_service.preview_pending(character)

    def submit_level_up_choice_intent(
        self,
        character_id: int,
        growth_choice: str,
        option: str | None = None,
    ) -> ActionResult:
        character = self._require_character(character_id)
        flags_before = getattr(character, "flags", None)
        history_before = 0
        if isinstance(flags_before, dict) and isinstance(flags_before.get("progression_history"), list):
            history_before = len(flags_before.get("progression_history", []))

        try:
            level_messages = self.progression_service.apply_level_progression(
                character,
                growth_choice=growth_choice,
            )
        except ValueError as exc:
            return ActionResult(messages=[str(exc)], game_over=False)

        if not level_messages:
            return ActionResult(messages=["No level-up is pending."], game_over=False)

        if option:
            flags = getattr(character, "flags", None)
            if isinstance(flags, dict):
                flags["last_growth_option"] = str(option)

        world = self._require_world() if self.world_repo else None
        operations: list[Callable[[object], None]] = []
        flags_after = getattr(character, "flags", None)
        progression_rows = []
        if isinstance(flags_after, dict):
            history = flags_after.get("progression_history", [])
            if isinstance(history, list):
                progression_rows = [row for row in history[history_before:] if isinstance(row, dict)]

        operation_builder = getattr(self.character_repo, "build_progression_unlock_operation", None)
        for row in progression_rows:
            to_level = int(row.get("to_level", character.level) or character.level)
            row_choice = str(row.get("growth_choice", growth_choice) or growth_choice)
            unlock_key = f"level_{to_level}_{row_choice}"
            if callable(operation_builder):
                operation = operation_builder(
                    character_id=int(character.id or 0),
                    unlock_kind="growth_choice",
                    unlock_key=unlock_key,
                    unlocked_level=to_level,
                    created_turn=int(getattr(world, "current_turn", 0)) if world is not None else 0,
                )
                if callable(operation):
                    operations.append(cast(Callable[[object], None], operation))

        self._set_progression_messages(character, level_messages)

        persisted = False
        if world is not None:
            persisted = self._persist_character_world_atomic(character, world, operations=operations)

        if not persisted:
            self.character_repo.save(character)
            recorder = getattr(self.character_repo, "record_progression_unlock", None)
            if callable(recorder):
                for row in progression_rows:
                    to_level = int(row.get("to_level", character.level) or character.level)
                    row_choice = str(row.get("growth_choice", growth_choice) or growth_choice)
                    unlock_key = f"level_{to_level}_{row_choice}"
                    recorder(
                        character_id=int(character.id or 0),
                        unlock_kind="growth_choice",
                        unlock_key=unlock_key,
                        unlocked_level=to_level,
                        created_turn=int(getattr(world, "current_turn", 0)) if world is not None else 0,
                    )

        return ActionResult(messages=level_messages, game_over=False)

    def get_location_context_intent(self, character_id: int) -> LocationContextView:
        character = self._require_character(character_id)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        world = self.world_repo.load_default() if self.world_repo else None
        location_type = self._current_location_type(character, location)
        location_name = self._settlement_display_name(world, location)
        if location_type == "town":
            return LocationContextView(
                location_type="town",
                title=f"TOWN SQUARE — {location_name or 'Town'}",
                current_location_name=location_name or "Town",
                act_label="Town Activities",
                travel_label="Leave Town",
                rest_label="Rest at Inn",
            )
        return LocationContextView(
            location_type="wilderness",
            title="WILDERNESS",
            current_location_name=location_name or "Frontier",
            act_label="Explore Area",
            travel_label="Return to Town",
            rest_label="Make Camp",
        )

    def get_travel_destinations_intent(self, character_id: int) -> list[TravelDestinationView]:
        character = self._require_character(character_id)
        if not self.location_repo:
            return []
        prep_profile = self._active_travel_prep_profile(character)
        prep_summary = self._travel_prep_summary(prep_profile)
        world = self.world_repo.load_default() if self.world_repo else None
        world_turn = int(getattr(world, "current_turn", 0)) if world is not None else 0
        threat_level = int(getattr(world, "threat_level", 0)) if world is not None else 0

        current_location_id = getattr(character, "location_id", None)
        current_location = self.location_repo.get(current_location_id) if current_location_id is not None else None
        locations = self.location_repo.list_all()
        destinations: list[TravelDestinationView] = []
        for location in locations:
            if current_location_id is not None and location.id == current_location_id:
                continue
            location_type = "town" if self._is_town_location(location) else "wilderness"
            biome = str(getattr(location, "biome", "") or "unknown")
            recommended_level = getattr(location, "recommended_level", "?")
            display_name = self._settlement_display_name(world, location)
            risk_hint = self._travel_risk_hint(
                character_id=character_id,
                world_turn=world_turn,
                threat_level=threat_level,
                location_id=int(getattr(location, "id", 0) or 0),
                location_name=display_name,
                recommended_level=int(recommended_level) if isinstance(recommended_level, int) else 1,
                travel_mode="road",
                prep_profile=prep_profile,
            )
            road_days = self._estimate_travel_days(
                character=character,
                source=current_location,
                destination=location,
                travel_mode="road",
                prep_profile=prep_profile,
            )
            preview = f"{location_type.title()} • {biome} • Lv {recommended_level} • Days {road_days} • Risk {risk_hint}"
            if prep_summary:
                preview = f"{preview} • Prep {prep_summary}"
            destinations.append(
                TravelDestinationView(
                    location_id=int(location.id),
                    name=display_name,
                    location_type=location_type,
                    biome=biome,
                    preview=preview,
                    estimated_days=road_days,
                    route_note=f"Route estimate: {road_days} day(s) by road.",
                    mode_hint="Modes: Road balanced • Stealth safer/slower • Caravan safer/slower",
                    prep_summary=prep_summary,
                )
            )
        return destinations

    def _travel_risk_hint(
        self,
        *,
        character_id: int,
        world_turn: int,
        threat_level: int,
        location_id: int,
        location_name: str,
        recommended_level: int,
        travel_mode: str = "road",
        prep_profile: dict | None = None,
    ) -> str:
        mode = self._normalize_travel_mode(travel_mode)
        prep_id = str((prep_profile or {}).get("id", "none"))
        prep_risk_shift = int((prep_profile or {}).get("risk_shift", 0))
        seed = derive_seed(
            namespace="travel.risk_hint",
            context={
                "character_id": int(character_id),
                "world_turn": int(world_turn),
                "threat_level": int(threat_level),
                "location_id": int(location_id),
                "location_name": str(location_name),
                "recommended_level": max(1, int(recommended_level)),
                "travel_mode": mode,
                "travel_prep": prep_id,
            },
        )
        rng = random.Random(seed)
        roll = rng.randint(1, 100)
        pressure = max(0, int(threat_level)) + max(0, int(recommended_level) - 1)
        mode_shift = {"road": 0, "stealth": -8, "caravan": -12}.get(mode, 0)
        score = roll + pressure + mode_shift + max(-30, min(10, prep_risk_shift))

        if score <= 40:
            return "Low"
        if score <= 85:
            return "Moderate"
        return "High"

    def travel_intent(self, character_id: int, destination_id: int | None = None, travel_mode: str = "road") -> ActionResult:
        character = self._require_character(character_id)
        mode = self._normalize_travel_mode(travel_mode)
        prep_profile = self._active_travel_prep_profile(character)
        target_location = None
        current_location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        if self.location_repo:
            locations = self.location_repo.list_all()
            if destination_id is not None:
                target_location = next((item for item in locations if int(item.id) == int(destination_id)), None)
                if target_location is None:
                    return ActionResult(messages=["That destination is unavailable right now."], game_over=False)
            else:
                location = self.location_repo.get(character.location_id) if character.location_id is not None else None
                current = self._current_location_type(character, location)
                target = "wilderness" if current == "town" else "town"
                if target == "town":
                    target_location = next((item for item in locations if self._is_town_location(item)), None)
                else:
                    target_location = next((item for item in locations if not self._is_town_location(item)), None)

        if target_location is not None:
            target_context = "town" if self._is_town_location(target_location) else "wilderness"
        else:
            location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
            current = self._current_location_type(character, location)
            target_context = "wilderness" if current == "town" else "town"

        world = self.world_repo.load_default() if self.world_repo else None
        destination_name = self._settlement_display_name(world, target_location) if target_location is not None else getattr(target_location, "name", None)
        estimated_days = self._estimate_travel_days(
            character=character,
            source=current_location,
            destination=target_location,
            travel_mode=mode,
            prep_profile=prep_profile,
        )

        event_days = self._plan_travel_event_days(
            character_id=character_id,
            destination_id=int(getattr(target_location, "id", 0) or 0),
            destination_name=str(destination_name or "unknown"),
            travel_mode=mode,
            estimated_days=estimated_days,
            world_turn=int(getattr(world, "current_turn", 0)) if world is not None else 0,
            prep_profile=prep_profile,
        )

        log_messages: list[str] = []
        for day in range(1, estimated_days + 1):
            log_messages.append(f"Day {day} of {estimated_days}.")
            if day in event_days:
                travel_event_message = self._apply_travel_event(
                    character,
                    target_context,
                    destination_name,
                    mode,
                    prep_profile=prep_profile,
                )
                if travel_event_message:
                    log_messages.append(travel_event_message)
            else:
                log_messages.append(self._travel_day_quiet_message(day=day, estimated_days=estimated_days, travel_mode=mode))
            self.character_repo.save(character)
            self.advance_world(ticks=1)

        if target_location is not None:
            character.location_id = target_location.id
            self._set_location_context(character, target_context)
            self.character_repo.save(character)
        else:
            self._set_location_context(character, target_context)
            self.character_repo.save(character)

        consumed_label = self._consume_travel_prep(character)
        if consumed_label:
            self.character_repo.save(character)

        mode_label = {"road": "road", "stealth": "stealth route", "caravan": "caravan route"}.get(mode, "road")
        if target_context == "wilderness":
            message = (
                f"You travel to {destination_name} and head into the wilderness."
                if destination_name
                else "You leave town and head into the wilderness."
            )
        else:
            message = (
                f"You travel to {destination_name} and return to town."
                if destination_name
                else "You return to town."
            )
        message = f"{message} Journey: {estimated_days} day(s) via {mode_label}."
        prep_summary = self._travel_prep_summary(prep_profile)
        if prep_summary:
            message = f"{message} Prep applied: {prep_summary}."
        if consumed_label:
            log_messages.append(f"Travel prep consumed: {consumed_label}.")
        return ActionResult(messages=[message, *log_messages], game_over=False)

    def _apply_travel_event(
        self,
        character: Character,
        target_context: str,
        destination_name: str | None,
        travel_mode: str = "road",
        prep_profile: dict | None = None,
    ) -> str:
        if not self.world_repo:
            return ""
        world = self._require_world()
        mode = self._normalize_travel_mode(travel_mode)
        prep_id = str((prep_profile or {}).get("id", "none"))
        prep_roll_shift = int((prep_profile or {}).get("event_roll_shift", 0))
        seed = derive_seed(
            namespace="travel.event",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "world_turn": int(getattr(world, "current_turn", 0)),
                "target_context": str(target_context or "unknown"),
                "destination_name": str(destination_name or "unknown"),
                "location_id": int(getattr(character, "location_id", 0) or 0),
                "travel_mode": mode,
                "travel_prep": prep_id,
            },
        )
        rng = random.Random(seed)
        roll = rng.randint(1, 100)
        mode_shift = {"road": 0, "stealth": -8, "caravan": -12}.get(mode, 0)
        adjusted_roll = max(1, min(100, roll + mode_shift + max(-20, min(8, prep_roll_shift))))

        if adjusted_roll <= 35:
            message = "The road is clear and you keep good pace."
            event_kind = "travel_clear"
            severity = "minor"
        elif adjusted_roll <= 65:
            if hasattr(world, "threat_level"):
                world.threat_level = max(0, int(getattr(world, "threat_level", 0)) + 1)
            message = "A rough detour slows your route and local danger rises."
            event_kind = "travel_delay"
            severity = "normal"
        elif adjusted_roll <= 85:
            gold_gain = 1 + rng.randint(0, 3)
            character.money = int(getattr(character, "money", 0)) + gold_gain
            message = f"You spot a forgotten cache and gain {gold_gain} gold on the way."
            event_kind = "travel_cache"
            severity = "minor"
        else:
            max_safe_loss = max(0, int(getattr(character, "hp_current", 1)) - 1)
            hp_loss = min(max_safe_loss, max(1, int(getattr(character, "hp_max", 1)) // 12))
            if hp_loss > 0:
                character.hp_current = max(1, int(character.hp_current) - hp_loss)
            if hasattr(world, "threat_level"):
                world.threat_level = max(0, int(getattr(world, "threat_level", 0)) + 1)
            if hp_loss > 0:
                message = f"A roadside skirmish costs you {hp_loss} HP before you break away."
            else:
                message = "You avoid a roadside skirmish, but the route stays tense."
            event_kind = "travel_hazard"
            severity = "normal"

        if mode == "stealth":
            message = f"You keep to quieter paths. {message}"
        elif mode == "caravan":
            message = f"You move with a guarded caravan. {message}"

        self._append_consequence(
            world,
            kind=event_kind,
            message=message,
            severity=severity,
            turn=int(getattr(world, "current_turn", 0)),
        )
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["last_travel_event"] = {
            "kind": event_kind,
            "seed": int(seed),
            "turn": int(getattr(world, "current_turn", 0)),
        }
        self.world_repo.save(world)
        return message

    @staticmethod
    def _normalize_travel_mode(value: str | None) -> str:
        lowered = str(value or "road").strip().lower()
        if lowered in {"road", "stealth", "caravan"}:
            return lowered
        return "road"

    def _estimate_travel_days(
        self,
        *,
        character: Character,
        source: Location | None,
        destination: Location | None,
        travel_mode: str,
        prep_profile: dict | None = None,
    ) -> int:
        if destination is None:
            return 1
        mode = self._normalize_travel_mode(travel_mode)
        prep_day_shift = int((prep_profile or {}).get("day_shift", 0))
        source_id = int(getattr(source, "id", 0) or 0)
        destination_id = int(getattr(destination, "id", 0) or 0)
        id_distance = abs(destination_id - source_id)
        recommended_level = max(1, int(getattr(destination, "recommended_level", 1) or 1))
        biome = str(getattr(destination, "biome", "") or "").lower()

        base_days = 1 + min(3, id_distance)
        challenge_days = 1 if recommended_level >= 3 else 0
        biome_days = 1 if any(token in biome for token in ("mountain", "marsh", "swamp", "wild", "forest")) else 0
        mode_days = {"road": 0, "stealth": 1, "caravan": 1}.get(mode, 0)
        days = base_days + challenge_days + biome_days + mode_days + max(-2, min(2, prep_day_shift))
        return max(1, min(9, days))

    def _plan_travel_event_days(
        self,
        *,
        character_id: int,
        destination_id: int,
        destination_name: str,
        travel_mode: str,
        estimated_days: int,
        world_turn: int,
        prep_profile: dict | None = None,
    ) -> set[int]:
        mode = self._normalize_travel_mode(travel_mode)
        if estimated_days <= 1:
            return set()
        prep_id = str((prep_profile or {}).get("id", "none"))
        prep_event_cap_shift = int((prep_profile or {}).get("event_cap_shift", 0))

        seed = derive_seed(
            namespace="travel.event_windows",
            context={
                "character_id": int(character_id),
                "destination_id": int(destination_id),
                "destination_name": str(destination_name or "unknown"),
                "travel_mode": mode,
                "travel_prep": prep_id,
                "estimated_days": int(estimated_days),
                "world_turn": int(world_turn),
            },
        )
        rng = random.Random(seed)
        max_events = min(3, max(0, int(estimated_days) - 1))
        mode_cap_adjust = {"road": 0, "stealth": -1, "caravan": -1}.get(mode, 0)
        max_events = max(0, max_events + mode_cap_adjust + max(-2, min(1, prep_event_cap_shift)))
        if max_events <= 0:
            return set()

        event_count = rng.randint(0, max_events)
        if event_count <= 0:
            return set()

        days = list(range(1, int(estimated_days) + 1))
        rng.shuffle(days)
        return set(days[:event_count])

    @staticmethod
    def _travel_day_quiet_message(*, day: int, estimated_days: int, travel_mode: str) -> str:
        mode = str(travel_mode or "road")
        if day == estimated_days:
            return "The destination horizon comes into view as you press on."
        if mode == "stealth":
            return "You keep to hedgerows and side trails, avoiding notice."
        if mode == "caravan":
            return "The caravan keeps steady pace, guarded and watchful."
        return "The road is calm; you cover good distance before dusk."

    @staticmethod
    def _location_culture(location: Location | None) -> str:
        if location is None:
            return "human"
        name = str(getattr(location, "name", "") or "").lower()
        biome = str(getattr(location, "biome", "") or "").lower()
        tags = [str(tag).lower() for tag in getattr(location, "tags", []) or []]
        factions = [str(faction).lower() for faction in getattr(location, "factions", []) or []]
        haystack = " ".join([name, biome, *tags, *factions])

        dwarven_tokens = ("dwarf", "khaz", "forge", "anvil", "stone", "mountain", "mine", "peak", "hold")
        elven_tokens = ("elf", "fae", "syl", "grove", "glade", "ancient", "verdant")
        if any(token in haystack for token in dwarven_tokens):
            return "dwarven"
        if any(token in haystack for token in elven_tokens):
            return "elven"
        return "human"

    @staticmethod
    def _settlement_scale(location: Location | None) -> str:
        if location is None:
            return "town"
        name = str(getattr(location, "name", "") or "").lower()
        biome = str(getattr(location, "biome", "") or "").lower()
        tags = [str(tag).lower() for tag in getattr(location, "tags", []) or []]
        haystack = " ".join([name, biome, *tags])
        if any(token in haystack for token in ("city", "capital", "metropolis", "citadel", "port")):
            return "city"
        if any(token in haystack for token in ("village", "hamlet", "camp", "outpost")):
            return "village"
        return "town"

    def _settlement_display_name(self, world: World | None, location: Location | None) -> str:
        if location is None:
            return ""
        original_name = str(getattr(location, "name", "") or "Unknown")
        if world is None:
            return original_name

        cache = self._world_settlement_names(world)
        key = str(int(getattr(location, "id", 0) or 0))
        if key in cache and str(cache.get(key) or "").strip():
            return str(cache[key])

        culture = self._location_culture(location)
        scale = self._settlement_scale(location)
        seed = derive_seed(
            namespace="name.settlement",
            context={
                "world_id": int(getattr(world, "id", 0) or 0),
                "world_seed": int(getattr(world, "rng_seed", 0) or 0),
                "location_id": int(getattr(location, "id", 0) or 0),
                "location_name": original_name,
                "culture": culture,
                "scale": scale,
            },
        )
        generated = generate_settlement_name(culture=culture, seed=seed, scale=scale)
        cache[key] = generated
        return generated

    def rest_with_feedback(self, character_id: int) -> tuple[GameLoopView, str]:
        self.rest(character_id)
        return self.get_game_loop_view(character_id), "You rest and feel restored."

    def is_combat_ready(self) -> bool:
        return self.combat_service is not None

    def get_combat_verbosity(self) -> str:
        return getattr(self.combat_service, "verbosity", "compact")

    def explore_view(self, character_id: int) -> ExploreView:
        plan, _, _ = self.explore(character_id)
        return self.build_explore_view(plan)

    def get_town_view_intent(self, character_id: int) -> TownView:
        character = self._require_character(character_id)
        world = self._require_world()
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        location_name = self._settlement_display_name(world, location)
        district_tag, landmark_tag = self._town_layer_tags(world=world, location=location)
        prep_summary = self._travel_prep_summary(self._active_travel_prep_profile(character))
        npcs = []
        for npc in self._TOWN_NPCS:
            disposition = self._get_npc_disposition(world, npc["id"])
            npcs.append(
                to_town_npc_view(
                    npc_id=npc["id"],
                    name=npc["name"],
                    role=npc["role"],
                    temperament=npc["temperament"],
                    relationship=disposition,
                )
            )
        story_lines = self._active_story_seed_town_lines(world)
        memory_lines = self._recent_story_memory_town_lines(world)
        recent_consequences = self._recent_consequence_messages(world)
        return to_town_view(
            day=getattr(world, "current_turn", None),
            threat_level=getattr(world, "threat_level", None),
            location_name=location_name,
            npcs=npcs,
            consequences=story_lines + memory_lines + recent_consequences,
            district_tag=district_tag,
            landmark_tag=landmark_tag,
            active_prep_summary=prep_summary,
        )

    def get_npc_interaction_intent(self, character_id: int, npc_id: str) -> NpcInteractionView:
        character = self._require_character(character_id)
        world = self._require_world()
        npc = self._find_town_npc(npc_id)
        disposition = self._get_npc_disposition(world, npc["id"])
        greeting = self._npc_greeting(npc_name=npc["name"], temperament=npc["temperament"], disposition=disposition)
        memory_hint = self._story_memory_dialogue_hint(world, npc_id=npc["id"])
        if memory_hint:
            greeting = f"{greeting} {memory_hint}"
        approaches = ["Friendly", "Direct", "Intimidate"]
        if npc["id"] == "broker_silas" and self._has_interaction_unlock(character, "intel_leverage"):
            approaches.append("Leverage Intel")
        if npc["id"] == "captain_ren" and self._has_interaction_unlock(character, "captain_favor"):
            approaches.append("Call In Favor")
        dominant_faction, dominant_score = self._dominant_faction_standing(character_id)
        if dominant_faction and dominant_score >= 10:
            approaches.append("Invoke Faction")
        if int(getattr(character, "money", 0) or 0) >= 8:
            approaches.append("Bribe")
        return NpcInteractionView(
            npc_id=npc["id"],
            npc_name=npc["name"],
            role=npc["role"],
            temperament=npc["temperament"],
            relationship=disposition,
            greeting=greeting,
            approaches=approaches,
        )

    def get_shop_view_intent(self, character_id: int) -> ShopView:
        character = self._require_character(character_id)
        price_modifier = self._town_price_modifier(character_id)
        standing_label = "neutral"
        if price_modifier < 0:
            standing_label = "friendly discount"
        elif price_modifier > 0:
            standing_label = "unfriendly surcharge"

        dynamic_rows: list[dict] = []
        loader = getattr(self.character_repo, "list_shop_items", None)
        if callable(loader):
            try:
                loaded = loader(character_id=character_id, max_items=8)
                if isinstance(loaded, list):
                    dynamic_rows = [row for row in loaded if isinstance(row, dict)]
            except Exception:
                dynamic_rows = []

        items = []
        merged_rows = list(self._SHOP_ITEMS) + dynamic_rows
        emitted: set[str] = set()
        for row in merged_rows:
            item_id = str(row.get("id", "")).strip()
            if not item_id or item_id in emitted:
                continue
            emitted.add(item_id)
            base_price = int(row.get("base_price", 1))
            price = self._bounded_price(base_price, price_modifier)
            availability_note = ""
            can_buy = character.money >= price

            requires_faction = row.get("requires_faction")
            if requires_faction:
                required_reputation = int(row.get("required_reputation", 0))
                standing = self.faction_standings_intent(character_id).get(str(requires_faction), 0)
                if standing < required_reputation:
                    can_buy = False
                    availability_note = f"Requires {requires_faction} reputation {required_reputation}."

            items.append(
                to_shop_item_view(
                    item_id=item_id,
                    name=str(row["name"]),
                    description=str(row.get("description", "")),
                    price=price,
                    can_buy=can_buy,
                    availability_note=availability_note,
                )
            )

        return to_shop_view(gold=character.money, price_modifier_label=standing_label, items=items)

    def buy_shop_item_intent(self, character_id: int, item_id: str) -> ActionResult:
        character = self._require_character(character_id)
        shop = self.get_shop_view_intent(character_id)
        selected = next((item for item in shop.items if item.item_id == item_id), None)
        if selected is None:
            return ActionResult(messages=["That item is not sold here."], game_over=False)
        if not selected.can_buy:
            reason = selected.availability_note or "You cannot buy that right now."
            return ActionResult(messages=[reason], game_over=False)
        if character.money < selected.price:
            return ActionResult(messages=["You do not have enough gold."], game_over=False)

        character.money -= selected.price
        character.inventory.append(selected.name)
        self.character_repo.save(character)
        return ActionResult(
            messages=[
                f"Purchased {selected.name} for {selected.price} gold.",
                f"Gold remaining: {character.money}.",
            ],
            game_over=False,
        )

    def get_sell_inventory_view_intent(self, character_id: int) -> SellInventoryView:
        character = self._require_character(character_id)
        inventory = list(getattr(character, "inventory", []) or [])
        equipped = self._equipment_state(character)

        rows = []
        for item in inventory:
            item_name = str(item)
            price = self._sell_price_for_item(character_id, item_name)
            is_equipped = any(str(equipped.get(slot, "")) == item_name for slot in ("weapon", "armor", "trinket"))
            rows.append(to_sell_item_view(name=item_name, price=price, equipped=is_equipped))

        return to_sell_inventory_view(
            gold=int(getattr(character, "money", 0)),
            items=rows,
            empty_state_hint="No items available to sell. Explore or shop to build inventory first.",
        )

    def sell_inventory_item_intent(self, character_id: int, item_name: str) -> ActionResult:
        character = self._require_character(character_id)
        inventory = list(getattr(character, "inventory", []) or [])
        selected = next((item for item in inventory if str(item) == str(item_name)), None)
        if selected is None:
            return ActionResult(messages=["That item is not in your inventory."], game_over=False)

        sale_price = self._sell_price_for_item(character_id, str(selected))
        before_count = sum(1 for item in inventory if str(item) == str(selected))
        inventory.remove(selected)
        character.inventory = inventory

        equipped = self._equipment_state(character)
        unequipped_slot = None
        for slot in ("weapon", "armor", "trinket"):
            if str(equipped.get(slot, "")) == str(selected) and before_count <= 1:
                equipped.pop(slot, None)
                unequipped_slot = slot

        character.money = int(getattr(character, "money", 0)) + int(sale_price)
        self.character_repo.save(character)

        messages = [
            f"Sold {selected} for {sale_price} gold.",
            f"Gold now: {character.money}.",
        ]
        if unequipped_slot:
            messages.append(f"{selected} was automatically unequipped from {unequipped_slot} slot.")
        return ActionResult(messages=messages, game_over=False)

    def get_equipment_view_intent(self, character_id: int) -> EquipmentView:
        character = self._require_character(character_id)
        equipped = self._equipment_state(character)
        inventory_items = []
        for item in list(getattr(character, "inventory", []) or []):
            slot = self._infer_equipment_slot(item)
            is_equipped = bool(slot and equipped.get(slot) == item)
            inventory_items.append(
                to_equipment_item_view(
                    name=item,
                    slot=slot,
                    equipable=slot is not None,
                    equipped=is_equipped,
                )
            )
        return to_equipment_view(equipped_slots=dict(equipped), inventory_items=inventory_items)

    def equip_inventory_item_intent(self, character_id: int, item_name: str) -> ActionResult:
        character = self._require_character(character_id)
        inventory = list(getattr(character, "inventory", []) or [])
        selected = next((item for item in inventory if str(item) == str(item_name)), None)
        if not selected:
            return ActionResult(messages=["That item is not in your inventory."], game_over=False)

        slot = self._infer_equipment_slot(selected)
        if not slot:
            return ActionResult(messages=["That item cannot be equipped."], game_over=False)

        equipped = self._equipment_state(character)
        prior = equipped.get(slot)
        equipped[slot] = selected
        self.character_repo.save(character)

        if prior and prior != selected:
            messages = [f"Equipped {selected} in {slot} slot.", f"Replaced {prior}."]
        else:
            messages = [f"Equipped {selected} in {slot} slot."]
        return ActionResult(messages=messages, game_over=False)

    def unequip_slot_intent(self, character_id: int, slot_name: str) -> ActionResult:
        character = self._require_character(character_id)
        slot = str(slot_name or "").strip().lower()
        if slot not in {"weapon", "armor", "trinket"}:
            return ActionResult(messages=["That slot cannot be unequipped."], game_over=False)

        equipped = self._equipment_state(character)
        current = equipped.get(slot)
        if not current:
            return ActionResult(messages=[f"{slot.title()} slot is already empty."], game_over=False)

        equipped.pop(slot, None)
        self.character_repo.save(character)
        return ActionResult(messages=[f"Unequipped {current} from {slot} slot."], game_over=False)

    def drop_inventory_item_intent(self, character_id: int, item_name: str) -> ActionResult:
        character = self._require_character(character_id)
        inventory = list(getattr(character, "inventory", []) or [])
        selected = next((item for item in inventory if str(item) == str(item_name)), None)
        if selected is None:
            return ActionResult(messages=["That item is not in your inventory."], game_over=False)

        before_count = sum(1 for item in inventory if str(item) == str(selected))
        inventory.remove(selected)
        character.inventory = inventory

        equipped = self._equipment_state(character)
        unequipped_slot = None
        for slot in ("weapon", "armor", "trinket"):
            if str(equipped.get(slot, "")) == str(selected) and before_count <= 1:
                equipped.pop(slot, None)
                unequipped_slot = slot

        self.character_repo.save(character)

        messages = [f"Dropped {selected}."]
        if unequipped_slot:
            messages.append(f"{selected} was also unequipped from {unequipped_slot} slot.")
        return ActionResult(messages=messages, game_over=False)

    def get_training_view_intent(self, character_id: int) -> TrainingView:
        character = self._require_character(character_id)
        standings = self.faction_standings_intent(character_id)
        options = []
        for row in self._TRAINING_OPTIONS:
            unlock_key = str(row.get("unlock_key", ""))
            unlocked = self._has_interaction_unlock(character, unlock_key)
            cost = int(row.get("cost", 0))
            availability_note = ""

            requires_faction = row.get("requires_faction")
            if requires_faction:
                required_reputation = int(row.get("required_reputation", 0))
                standing = standings.get(str(requires_faction), 0)
                if standing < required_reputation:
                    availability_note = f"Requires {requires_faction} reputation {required_reputation}."

            can_buy = (not unlocked) and character.money >= cost and not availability_note
            options.append(
                to_training_option_view(
                    training_id=str(row["id"]),
                    title=str(row["title"]),
                    cost=cost,
                    unlocked=unlocked,
                    can_buy=can_buy,
                    effect_summary=str(row.get("effect", "")),
                    availability_note=availability_note,
                )
            )
        return to_training_view(gold=character.money, options=options)

    def get_travel_prep_view_intent(self, character_id: int) -> TravelPrepView:
        character = self._require_character(character_id)
        active = self._active_travel_prep_profile(character)
        active_id = str((active or {}).get("id", "")).strip()
        options = []
        for row in self._TRAVEL_PREP_ITEMS:
            prep_id = str(row.get("id", ""))
            price = int(row.get("price", 0))
            is_active = prep_id == active_id and bool(active_id)
            can_buy = int(getattr(character, "money", 0)) >= price
            availability_note = ""
            if is_active:
                can_buy = False
                availability_note = "Already active for your next trip."
            elif active_id:
                availability_note = "Buying this replaces your current prep."
            elif not can_buy:
                availability_note = "Insufficient gold."

            options.append(
                to_travel_prep_option_view(
                    prep_id=prep_id,
                    title=str(row.get("title", prep_id.replace("_", " ").title())),
                    price=price,
                    effect_summary=str(row.get("effect", "")),
                    can_buy=can_buy,
                    active=is_active,
                    availability_note=availability_note,
                )
            )
        return to_travel_prep_view(
            gold=int(getattr(character, "money", 0)),
            active_summary=self._travel_prep_summary(active),
            options=options,
        )

    def purchase_travel_prep_intent(self, character_id: int, prep_id: str) -> ActionResult:
        character = self._require_character(character_id)
        row = self._find_travel_prep_item(prep_id)
        if row is None:
            return ActionResult(messages=["That travel prep is not offered."], game_over=False)

        active = self._active_travel_prep_profile(character)
        selected_id = str(row.get("id", ""))
        if str((active or {}).get("id", "")) == selected_id:
            return ActionResult(messages=["That travel prep is already active for your next journey."], game_over=False)

        price = int(row.get("price", 0))
        if int(getattr(character, "money", 0)) < price:
            return ActionResult(messages=[f"Travel prep costs {price} gold."], game_over=False)

        character.money = int(getattr(character, "money", 0)) - price
        state = self._travel_prep_state(character)
        state["active"] = {
            "id": selected_id,
            "title": str(row.get("title", selected_id.replace("_", " ").title())),
            "risk_shift": int(row.get("risk_shift", 0)),
            "event_roll_shift": int(row.get("event_roll_shift", 0)),
            "event_cap_shift": int(row.get("event_cap_shift", 0)),
            "day_shift": int(row.get("day_shift", 0)),
            "consumes_on_travel": True,
        }
        self.character_repo.save(character)
        summary = self._travel_prep_summary(state.get("active"))
        return ActionResult(
            messages=[
                f"Travel prep secured: {state['active']['title']} ({price} gold).",
                f"Active for next journey: {summary}." if summary else "Active for next journey.",
                f"Gold remaining: {character.money}.",
            ],
            game_over=False,
        )

    def get_rumour_board_intent(self, character_id: int) -> RumourBoardView:
        character = self._require_character(character_id)
        world = self._require_world()
        day = int(getattr(world, "current_turn", 0))
        threat = int(getattr(world, "threat_level", 0))
        broker_disposition = self._get_npc_disposition(world, "broker_silas")
        standings = self.faction_standings_intent(character_id)
        dominant_faction = self._dominant_positive_faction(standings)
        pressure_faction = self._relationship_pressure_faction(world, dominant_faction)
        memory_fingerprint = self._story_memory_fingerprint(world, limit=4)
        flashpoint_fingerprint = self._flashpoint_echo_fingerprint(world, limit=4)
        flashpoint_pressure = self._recent_flashpoint_pressure_score(world, day=day, window=4)
        flashpoint_bias_faction = self._latest_flashpoint_bias_faction(world)

        seed = derive_seed(
            namespace="town.rumour_board",
            context={
                "board_key": "rumour_board",
                "character_id": character_id,
                "day": day,
                "location_id": int(getattr(character, "location_id", 0) or 0),
                "threat": threat,
                "broker_disposition": broker_disposition,
                "intel_unlock": self._has_interaction_unlock(character, "intel_leverage"),
                "dominant_faction": dominant_faction or "none",
                "pressure_faction": pressure_faction or "none",
                "flashpoint_pressure": int(flashpoint_pressure),
                "flashpoint_bias_faction": flashpoint_bias_faction or "none",
                "faction_snapshot": standings,
                "memory_fingerprint": memory_fingerprint,
                "flashpoint_fingerprint": flashpoint_fingerprint,
            },
        )
        rng = random.Random(seed)
        templates = [dict(row) for row in self._RUMOUR_TEMPLATES]
        rng.shuffle(templates)
        if dominant_faction or pressure_faction or flashpoint_bias_faction:
            templates.sort(
                key=lambda row: (
                    0 if flashpoint_bias_faction and row.get("faction_id") == flashpoint_bias_faction else 1,
                    0 if pressure_faction and row.get("faction_id") == pressure_faction else 1,
                    0 if dominant_faction and row.get("faction_id") == dominant_faction else 1,
                )
            )

        base_count = 2
        if threat >= 4:
            base_count += 1
        if flashpoint_pressure >= 6:
            base_count += 1
        if self._has_interaction_unlock(character, "intel_leverage"):
            base_count += 1
        selection = templates[: max(2, min(4, base_count))]

        items: list[RumourItemView] = []
        seed_item = self._active_story_seed_rumour(world)
        if seed_item is not None:
            items.append(seed_item)
        memory_item = self._story_memory_echo_rumour(world, character_id=character_id)
        if memory_item is not None:
            items.append(memory_item)
        flashpoint_item = self._flashpoint_echo_rumour(world, character_id=character_id)
        if flashpoint_item is not None:
            items.append(flashpoint_item)
        for row in selection:
            confidence = str(row.get("confidence", "uncertain"))
            if broker_disposition >= 25 and confidence == "uncertain":
                confidence = "credible"
            if broker_disposition <= -25 and confidence == "credible":
                confidence = "uncertain"
            text = str(row.get("text", ""))
            if confidence in {"uncertain", "speculative"}:
                text = f"[Unverified] {text}"
            items.append(
                to_rumour_item_view(
                    rumour_id=str(row.get("id", "rumour")),
                    text=text,
                    confidence=confidence,
                    source=str(row.get("source", "Townfolk")),
                )
            )

        if len(items) > 4:
            items = items[:4]

        self._record_rumour_history(
            world,
            day=day,
            character_id=character_id,
            dominant_faction=dominant_faction,
            rumour_ids=[item.rumour_id for item in items],
        )
        if self.world_repo:
            self.world_repo.save(world)

        empty_state_hint = (
            "No useful rumours today. Check again after tomorrow's turn; higher town threat and better standing with local informants improve rumour depth."
        )
        return to_rumour_board_view(
            day=getattr(world, "current_turn", None),
            items=items,
            empty_state_hint=empty_state_hint,
        )

    def purchase_training_intent(self, character_id: int, training_id: str) -> ActionResult:
        character = self._require_character(character_id)
        row = next((option for option in self._TRAINING_OPTIONS if option["id"] == training_id), None)
        if row is None:
            return ActionResult(messages=["That training is not offered."], game_over=False)

        cost = int(row.get("cost", 0))
        unlock_key = str(row.get("unlock_key", ""))
        requires_faction = row.get("requires_faction")
        if requires_faction:
            required_reputation = int(row.get("required_reputation", 0))
            standing = self.faction_standings_intent(character_id).get(str(requires_faction), 0)
            if standing < required_reputation:
                return ActionResult(
                    messages=[f"Training requires {requires_faction} reputation {required_reputation}."],
                    game_over=False,
                )
        if self._has_interaction_unlock(character, unlock_key):
            return ActionResult(messages=["You have already completed this training."], game_over=False)
        if character.money < cost:
            return ActionResult(messages=[f"Training costs {cost} gold."], game_over=False)

        character.money -= cost
        self._grant_interaction_unlock(character, unlock_key)
        self.character_repo.save(character)
        return ActionResult(
            messages=[
                f"Training complete: {row['title']}.",
                f"Unlocked: {row.get('effect', 'new interaction options')}.",
            ],
            game_over=False,
        )

    def get_quest_board_intent(self, character_id: int) -> QuestBoardView:
        self._require_character(character_id)
        world = self._require_world()
        world_turn = int(getattr(world, "current_turn", 0))
        quests = self._world_quests(world)
        views: list[QuestStateView] = []
        for quest_id, payload in quests.items():
            if not isinstance(payload, dict):
                continue
            objective_kind = str(payload.get("objective_kind", "kill_any"))
            progress = int(payload.get("progress", 0))
            target = max(1, int(payload.get("target", 1)))
            status = str(payload.get("status", "unknown"))
            views.append(
                to_quest_state_view(
                    quest_id=str(quest_id),
                    title=self._quest_title(str(quest_id)),
                    status=status,
                    progress=progress,
                    target=target,
                    reward_xp=int(payload.get("reward_xp", 0)),
                    reward_money=int(payload.get("reward_money", 0)),
                    objective_summary=self._quest_objective_summary(
                        objective_kind=objective_kind,
                        progress=progress,
                        target=target,
                    ),
                    urgency_label=self._quest_urgency_label(
                        status=status,
                        world_turn=world_turn,
                        expires_turn=payload.get("expires_turn"),
                    ),
                )
            )
        views.sort(key=lambda item: item.quest_id)
        empty_state_hint = (
            "No quest postings yet. Explore nearby zones, advance a day, and check back at the board for new contracts."
        )
        return to_quest_board_view(quests=views, empty_state_hint=empty_state_hint)

    def get_quest_journal_intent(self, character_id: int) -> QuestJournalView:
        board = self.get_quest_board_intent(character_id)
        buckets: dict[str, list[QuestStateView]] = {
            "ready_to_turn_in": [],
            "active": [],
            "completed": [],
            "failed": [],
        }
        for quest in board.quests:
            status = str(getattr(quest, "status", "unknown"))
            if status in buckets:
                buckets[status].append(quest)

        for rows in buckets.values():
            rows.sort(key=lambda item: (item.title.lower(), item.quest_id.lower()))

        sections = [
            QuestJournalSectionView(title="Ready to Turn In", quests=buckets["ready_to_turn_in"]),
            QuestJournalSectionView(title="Active", quests=buckets["active"]),
            QuestJournalSectionView(title="Completed", quests=buckets["completed"]),
            QuestJournalSectionView(title="Failed", quests=buckets["failed"]),
        ]
        sections = [section for section in sections if section.quests]
        empty_state_hint = (
            "No quests tracked yet. Visit the quest board in town, accept a contract, then return here to monitor progress."
        )
        return QuestJournalView(sections=sections, empty_state_hint=empty_state_hint)

    def accept_quest_intent(self, character_id: int, quest_id: str) -> ActionResult:
        character = self._require_character(character_id)
        world = self._require_world()
        quests = self._world_quests(world)
        quest = quests.get(quest_id)
        if not isinstance(quest, dict):
            return ActionResult(messages=["That quest is not available."], game_over=False)
        if quest.get("status") != "available":
            return ActionResult(messages=[f"Quest cannot be accepted right now ({quest.get('status', 'unknown')})."], game_over=False)

        quest["status"] = "active"
        quest["owner_character_id"] = int(character_id)
        current_turn = int(getattr(world, "current_turn", 0))
        quest["accepted_turn"] = current_turn
        quest["expires_turn"] = current_turn + 5

        operations: list[Callable[[object], None]] = []
        if self.quest_state_repo is not None:
            try:
                from rpg.domain.models.quest import QuestState

                seed_key = str(quest.get("seed_key", ""))
                quest_state = QuestState(
                    template_slug=str(quest_id),
                    status="active",
                    progress=int(quest.get("progress", 0) or 0),
                    accepted_turn=current_turn,
                    completed_turn=None,
                    metadata={"seed_key": seed_key},
                )
                operation_builder = getattr(self.quest_state_repo, "build_save_active_with_history_operation", None)
                if callable(operation_builder):
                    operation = operation_builder(
                        character_id=int(character_id),
                        state=quest_state,
                        target_count=max(1, int(quest.get("target", 1) or 1)),
                        seed_key=seed_key,
                        action="accepted",
                        action_turn=current_turn,
                        payload_json=json.dumps({"status": "active", "quest_id": str(quest_id)}),
                    )
                    if callable(operation):
                        operations.append(cast(Callable[[object], None], operation))
                else:
                    save_with_history = getattr(self.quest_state_repo, "save_active_with_history", None)
                    if callable(save_with_history):
                        save_with_history(
                            character_id=int(character_id),
                            state=quest_state,
                            target_count=max(1, int(quest.get("target", 1) or 1)),
                            seed_key=seed_key,
                            action="accepted",
                            action_turn=current_turn,
                            payload_json=json.dumps({"status": "active", "quest_id": str(quest_id)}),
                        )
            except Exception:
                pass

        persisted = self._persist_character_world_atomic(character, world, operations=operations)
        if not persisted and self.world_repo:
            self.world_repo.save(world)
        title = self._QUEST_TITLES.get(quest_id, quest_id)
        return ActionResult(messages=[f"Accepted quest: {title}."], game_over=False)

    def turn_in_quest_intent(self, character_id: int, quest_id: str) -> ActionResult:
        character = self._require_character(character_id)
        world = self._require_world()
        quests = self._world_quests(world)
        quest = quests.get(quest_id)
        if not isinstance(quest, dict):
            return ActionResult(messages=["No such quest found."], game_over=False)

        if quest.get("status") != "ready_to_turn_in":
            return ActionResult(messages=[f"Quest is not ready to turn in ({quest.get('status', 'unknown')})."], game_over=False)

        owner = int(quest.get("owner_character_id", character_id))
        if owner != character_id:
            return ActionResult(messages=["You are not the owner of this quest."], game_over=False)

        reward_xp = int(quest.get("reward_xp", 0))
        reward_money = int(quest.get("reward_money", 0))
        character.xp += reward_xp
        character.money += reward_money
        level_messages = self._apply_level_progression(character)

        quest["status"] = "completed"
        quest["turned_in_turn"] = int(getattr(world, "current_turn", 0))
        turned_in_turn = int(quest["turned_in_turn"])
        quest_flags = world.flags.setdefault("quest_world_flags", {}) if isinstance(world.flags, dict) else {}
        if isinstance(quest_flags, dict):
            quest_flags[f"{quest_id}_turned_in"] = True
        world_flags = world.flags.setdefault("world_flags", {}) if isinstance(world.flags, dict) else {}
        world_flag_key = f"quest:{quest_id}:turned_in"
        if isinstance(world_flags, dict):
            world_flags[world_flag_key] = True
            if character.location_id is not None:
                world_flags[f"location:{int(character.location_id)}:peaceful"] = True

        operations: list[Callable[[object], None]] = []
        world_flag_operation_builder = getattr(self.world_repo, "build_set_world_flag_operation", None)
        if callable(world_flag_operation_builder):
            operation = world_flag_operation_builder(
                world_id=int(getattr(world, "id", 1) or 1),
                flag_key=world_flag_key,
                flag_value="true",
                changed_turn=turned_in_turn,
                reason="quest_completion",
            )
            if callable(operation):
                operations.append(cast(Callable[[object], None], operation))
            if character.location_id is not None:
                operation = world_flag_operation_builder(
                    world_id=int(getattr(world, "id", 1) or 1),
                    flag_key=f"location:{int(character.location_id)}:peaceful",
                    flag_value="true",
                    changed_turn=turned_in_turn,
                    reason="quest_completion_peaceful_window",
                )
                if callable(operation):
                    operations.append(cast(Callable[[object], None], operation))
        if self.quest_state_repo is not None:
            try:
                from rpg.domain.models.quest import QuestState

                seed_key = str(quest.get("seed_key", ""))
                quest_state = QuestState(
                    template_slug=str(quest_id),
                    status="completed",
                    progress=int(quest.get("progress", 0) or 0),
                    accepted_turn=int(quest.get("accepted_turn", turned_in_turn) or turned_in_turn),
                    completed_turn=turned_in_turn,
                    metadata={"seed_key": seed_key},
                )
                operation_builder = getattr(self.quest_state_repo, "build_save_active_with_history_operation", None)
                if callable(operation_builder):
                    operation = operation_builder(
                        character_id=int(character_id),
                        state=quest_state,
                        target_count=max(1, int(quest.get("target", 1) or 1)),
                        seed_key=seed_key,
                        action="completed",
                        action_turn=turned_in_turn,
                        payload_json=json.dumps(
                            {
                                "reward_xp": int(reward_xp),
                                "reward_money": int(reward_money),
                                "quest_id": str(quest_id),
                            }
                        ),
                    )
                    if callable(operation):
                        operations.append(cast(Callable[[object], None], operation))
                else:
                    save_with_history = getattr(self.quest_state_repo, "save_active_with_history", None)
                    if callable(save_with_history):
                        save_with_history(
                            character_id=int(character_id),
                            state=quest_state,
                            target_count=max(1, int(quest.get("target", 1) or 1)),
                            seed_key=seed_key,
                            action="completed",
                            action_turn=turned_in_turn,
                            payload_json=json.dumps(
                                {
                                    "reward_xp": int(reward_xp),
                                    "reward_money": int(reward_money),
                                    "quest_id": str(quest_id),
                                }
                            ),
                        )
            except Exception:
                pass

        self._apply_quest_completion_faction_effect(character_id, operations=operations)
        persisted = self._persist_character_world_atomic(character, world, operations=operations)
        if not persisted:
            self.character_repo.save(character)
            if self.world_repo:
                self.world_repo.save(world)
                world_flag_setter = getattr(self.world_repo, "set_world_flag", None)
                if callable(world_flag_setter):
                    world_flag_setter(
                        world_id=int(getattr(world, "id", 1) or 1),
                        flag_key=world_flag_key,
                        flag_value="true",
                        changed_turn=turned_in_turn,
                        reason="quest_completion",
                    )
                    if character.location_id is not None:
                        world_flag_setter(
                            world_id=int(getattr(world, "id", 1) or 1),
                            flag_key=f"location:{int(character.location_id)}:peaceful",
                            flag_value="true",
                            changed_turn=turned_in_turn,
                            reason="quest_completion_peaceful_window",
                        )

        title = self._QUEST_TITLES.get(quest_id, quest_id)
        messages = [
            f"Turned in quest: {title}.",
            f"Rewards: +{reward_xp} XP, +{reward_money} gold.",
        ]
        messages.extend(level_messages)
        return ActionResult(messages=messages, game_over=False)

    def submit_social_approach_intent(
        self,
        character_id: int,
        npc_id: str,
        approach: str,
    ) -> SocialOutcomeView:
        character = self._require_character(character_id)
        world = self._require_world()
        npc = self._find_town_npc(npc_id)

        normalized_approach = (approach or "").strip().lower()
        if normalized_approach not in {
            "friendly",
            "direct",
            "intimidate",
            "leverage intel",
            "call in favor",
            "invoke faction",
            "bribe",
        }:
            normalized_approach = "direct"
        if normalized_approach == "leverage intel" and not (
            npc["id"] == "broker_silas" and self._has_interaction_unlock(character, "intel_leverage")
        ):
            normalized_approach = "direct"
        if normalized_approach == "call in favor" and not (
            npc["id"] == "captain_ren" and self._has_interaction_unlock(character, "captain_favor")
        ):
            normalized_approach = "direct"
        dominant_faction, dominant_score = self._dominant_faction_standing(character_id)
        if normalized_approach == "invoke faction" and (not dominant_faction or dominant_score < 10):
            normalized_approach = "direct"

        bribe_cost = 8
        did_bribe = normalized_approach == "bribe"
        if did_bribe and int(getattr(character, "money", 0) or 0) < bribe_cost:
            normalized_approach = "direct"
            did_bribe = False
        if did_bribe:
            character.money = max(0, int(getattr(character, "money", 0) or 0) - bribe_cost)
            self.character_repo.save(character)

        disposition_before = self._get_npc_disposition(world, npc["id"])
        skill_attr = {
            "friendly": "charisma",
            "direct": "wisdom",
            "intimidate": "strength",
            "leverage intel": "wisdom",
            "call in favor": "charisma",
            "invoke faction": "charisma",
            "bribe": "charisma",
        }[normalized_approach]
        score = int(getattr(character, "attributes", {}).get(skill_attr, 10))
        modifier = (score - 10) // 2

        dc = 12 + max(0, int(npc["aggression"]) - 4) - max(0, int(npc["openness"]) - 4)
        dc += 2 if disposition_before <= -50 else 0
        dc -= 1 if disposition_before >= 50 else 0
        if normalized_approach == "leverage intel" and npc["id"] == "broker_silas":
            dc -= 2
        if normalized_approach == "call in favor" and npc["id"] == "captain_ren":
            dc -= 3
        if normalized_approach == "invoke faction":
            dc -= 2 + max(0, (dominant_score - 10) // 10)
        if normalized_approach == "bribe":
            dc -= 4
        dc = max(8, min(18, dc))

        world_turn = getattr(world, "current_turn", 0)
        social_state = self._world_social_flags(world)
        nonce_key = f"nonce:{npc['id']}:{normalized_approach}:character:{character_id}"
        prior_nonce = int(social_state.get(nonce_key, 0) or 0)
        next_nonce = prior_nonce + 1
        social_state[nonce_key] = next_nonce
        seed = derive_seed(
            namespace="social.check",
            context={
                "player_id": character_id,
                "npc_id": npc["id"],
                "approach": normalized_approach,
                "world_turn": world_turn,
                "disposition": disposition_before,
                "event_nonce": next_nonce,
            },
        )
        roll = random.Random(seed).randint(1, 20)
        roll_total = roll + modifier
        success = roll_total >= dc

        delta = 8 if success else -6
        if normalized_approach == "intimidate":
            delta = 5 if success else -8
        if normalized_approach == "leverage intel":
            delta = 6 if success else -4
        if normalized_approach == "call in favor":
            delta = 7 if success else -5
        if normalized_approach == "invoke faction":
            delta = 9 if success else -3
        if normalized_approach == "bribe":
            delta = 10 if success else -2
        disposition_after = max(-100, min(100, disposition_before + delta))
        self._set_npc_disposition(world, npc["id"], disposition_after)
        self._append_npc_memory(
            world,
            npc_id=npc["id"],
            event={
                "turn": world_turn,
                "approach": normalized_approach,
                "success": success,
                "delta": delta,
            },
        )

        if not success:
            self._append_consequence(
                world,
                kind="social_rebuff",
                message=f"{npc['name']} rebuffs your approach.",
                severity="minor",
                turn=world_turn,
            )

        if success and npc["id"] == "broker_silas":
            quests = self._world_quests(world)
            progressed = False
            for quest in quests.values():
                if not isinstance(quest, dict):
                    continue
                if quest.get("status") != "active":
                    continue
                if str(quest.get("objective_kind", "kill_any")) != "kill_any":
                    continue
                quest["progress"] = int(quest.get("target", 1))
                quest["status"] = "ready_to_turn_in"
                quest["completed_turn"] = world_turn
                progressed = True
                break

            if progressed:
                self._append_consequence(
                    world,
                    kind="quest_noncombat_progress",
                    message="Silas provides evidence that advances your active quest.",
                    severity="normal",
                    turn=world_turn,
                )
            story_messages = self._resolve_active_story_seed_noncombat(
                world,
                character=character,
                character_id=character_id,
                npc_id=npc["id"],
                approach=normalized_approach,
            )
        else:
            story_messages = []

        if self.world_repo:
            self.world_repo.save(world)

        outcome_message = (
            f"{npc['name']} softens and shares useful details."
            if success
            else f"{npc['name']} remains unconvinced."
        )
        approach_note = ""
        if normalized_approach == "invoke faction" and dominant_faction:
            approach_note = f"You invoke your standing with {dominant_faction}."
        if normalized_approach == "bribe":
            approach_note = f"You spend {bribe_cost} gold to grease the wheels."
        return SocialOutcomeView(
            npc_id=npc["id"],
            npc_name=npc["name"],
            approach=normalized_approach,
            success=success,
            roll_total=roll_total,
            target_dc=dc,
            relationship_before=disposition_before,
            relationship_after=disposition_after,
            messages=[
                outcome_message,
                f"Check: d20 + {modifier} = {roll_total} vs DC {dc}",
                f"Relationship: {disposition_before} → {disposition_after}",
            ]
            + ([approach_note] if approach_note else [])
            + story_messages,
        )

    def apply_retreat_consequence_intent(self, character_id: int) -> ActionResult:
        character = self._require_character(character_id)
        world = self._require_world()

        hp_loss = max(1, character.hp_max // 10)
        character.hp_current = max(1, character.hp_current - hp_loss)
        self.character_repo.save(character)

        if hasattr(world, "threat_level"):
            world.threat_level = max(0, int(world.threat_level) + 1)

        quests = self._world_quests(world)
        for quest in quests.values():
            if not isinstance(quest, dict):
                continue
            if quest.get("status") != "active":
                continue
            progress = int(quest.get("progress", 0))
            if progress > 0:
                quest["progress"] = progress - 1

        self._append_consequence(
            world,
            kind="retreat_penalty",
            message=f"Retreat costs you {hp_loss} HP and emboldens local threats.",
            severity="normal",
            turn=int(getattr(world, "current_turn", 0)),
        )
        if self.world_repo:
            self.world_repo.save(world)

        return ActionResult(
            messages=[
                "Retreat has consequences.",
                f"You lose {hp_loss} HP and threat rises.",
            ],
            game_over=False,
        )

    def apply_defeat_consequence_intent(self, character_id: int) -> ActionResult:
        character = self._require_character(character_id)
        world = self._require_world()

        gold_before = int(getattr(character, "money", 0) or 0)
        gold_loss = min(gold_before, max(5, gold_before // 4)) if gold_before > 0 else 0
        character.money = max(0, gold_before - gold_loss)

        recovery_hp = max(1, int(getattr(character, "hp_max", 1) // 2))
        character.hp_current = max(recovery_hp, 1)
        character.alive = True

        relocation_name = None
        if self.location_repo:
            locations = self.location_repo.list_all()
            town_location = next((item for item in locations if self._is_town_location(item)), None)
            if town_location is not None:
                character.location_id = town_location.id
                self._set_location_context(character, "town")
                relocation_name = getattr(town_location, "name", None)

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["recovery_state"] = {
            "active": True,
            "turn": int(getattr(world, "current_turn", 0)),
            "hp_restored": int(character.hp_current),
            "gold_lost": int(gold_loss),
            "location": str(relocation_name or "safe ground"),
        }

        if hasattr(world, "threat_level"):
            world.threat_level = max(0, int(world.threat_level) + 1)

        self._append_consequence(
            world,
            kind="defeat_setback",
            message=(
                f"After defeat, {character.name} regroups at {relocation_name or 'safe ground'} "
                f"with {character.hp_current} HP and {gold_loss}g lost."
            ),
            severity="normal",
            turn=int(getattr(world, "current_turn", 0)),
        )

        self.character_repo.save(character)
        if self.world_repo:
            self.world_repo.save(world)

        messages = [
            "Defeat has consequences.",
            f"You recover to {character.hp_current} HP.",
            f"You lose {gold_loss} gold." if gold_loss > 0 else "You have no gold to lose.",
        ]
        if relocation_name:
            messages.append(f"You awaken back in {relocation_name}.")
        return ActionResult(messages=messages, game_over=False)

    def get_recovery_status_intent(self, character_id: int) -> str | None:
        character = self._require_character(character_id)
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return None
        recovery = flags.get("recovery_state")
        if not isinstance(recovery, dict) or not recovery.get("active"):
            return None
        location = str(recovery.get("location") or "safe ground")
        hp_restored = int(recovery.get("hp_restored") or getattr(character, "hp_current", 1))
        gold_lost = int(recovery.get("gold_lost") or 0)
        return f"Recovery: regrouped at {location}; HP restored to {hp_restored}; gold lost {gold_lost}."

    def build_explore_view(self, plan: EncounterPlan) -> ExploreView:
        enemies = [
            EnemyView(
                id=enemy.id,
                name=enemy.name,
                armor_class=getattr(enemy, "armour_class", getattr(enemy, "armor", 10)),
                hp_current=getattr(enemy, "hp_current", getattr(enemy, "hp", 1)),
                hp_max=getattr(enemy, "hp_max", getattr(enemy, "hp", 1)),
            )
            for enemy in plan.enemies
        ]
        if not enemies:
            if str(getattr(plan, "source", "")) == "peaceful":
                return ExploreView(has_encounter=False, message="The area is unusually calm today.")
            return ExploreView(has_encounter=False, message="You find nothing of interest today.")
        return ExploreView(has_encounter=True, message="Danger stirs nearby.", enemies=enemies)

    def save_character_state(self, character: Character) -> None:
        self.character_repo.save(character)

    def encounter_intro_intent(self, enemy: Entity) -> str:
        try:
            intro = self.encounter_intro_builder(enemy)
        except Exception:
            intro = random_intro(enemy)
        text = (intro or "").strip()
        return text or random_intro(enemy)

    def combat_player_stats_intent(self, player: Character) -> dict:
        if not self.combat_service:
            return {}
        return self.combat_service.derive_player_stats(player)

    def combat_resolve_intent(
        self,
        player: Character,
        enemy: Entity,
        choose_action: Callable[[list[str], Character, Entity, int, dict], tuple[str, Optional[str]] | str],
        scene: Optional[dict] = None,
    ):
        if not self.combat_service:
            raise RuntimeError("Combat service is unavailable.")
        world_turn = 0
        if self.world_repo:
            world = self.world_repo.load_default()
            world_turn = getattr(world, "current_turn", 0) if world else 0
        scene_ctx = scene or {}
        seed = derive_seed(
            namespace="combat.resolve",
            context={
                "player_id": player.id,
                "enemy_id": enemy.id,
                "world_turn": world_turn,
                "distance": scene_ctx.get("distance", "close"),
                "terrain": scene_ctx.get("terrain", "open"),
                "surprise": scene_ctx.get("surprise", "none"),
            },
        )
        self.combat_service.set_seed(seed)
        return self.combat_service.fight_turn_based(
            player,
            enemy,
            choose_action,
            scene=scene,
        )

    def combat_round_view_intent(
        self,
        options: list[str],
        player: Character,
        enemy: Entity,
        round_no: int,
        scene_ctx: Optional[dict] = None,
    ) -> CombatRoundView:
        stats = self.combat_player_stats_intent(player)
        rage_rounds = getattr(player, "flags", {}).get("rage_rounds", 0)
        rage_label = (
            "Raging"
            if rage_rounds
            else "Ready"
            if (getattr(player, "class_name", "") == "barbarian")
            else "—"
        )
        sneak_ready = "Yes" if getattr(player, "class_name", "") == "rogue" else "—"
        is_dodging = bool(getattr(player, "flags", {}).get("dodging"))
        conditions = "Dodging" if is_dodging else "—"

        scene = scene_ctx or {}
        scene_view = to_combat_scene_view(
            distance=scene.get("distance", "close"),
            terrain=scene.get("terrain", "open"),
            surprise=scene.get("surprise", "none"),
        )
        player_view = to_combat_player_panel_view(
            hp_current=player.hp_current,
            hp_max=player.hp_max,
            armor_class=stats.get("ac", getattr(player, "armour_class", 10)),
            attack_bonus=stats.get("attack_bonus", getattr(player, "attack_bonus", 0)),
            spell_slots_current=getattr(player, "spell_slots_current", 0),
            rage_label=rage_label,
            sneak_ready=sneak_ready,
            conditions=conditions,
        )
        enemy_view = to_combat_enemy_panel_view(
            name=enemy.name,
            hp_current=getattr(enemy, "hp_current", 0),
            hp_max=getattr(enemy, "hp_max", 0),
            armor_class=getattr(enemy, "armour_class", 10),
            intent=getattr(enemy, "intent", None) or "Hostile",
        )
        return to_combat_round_view(
            round_number=round_no,
            scene=scene_view,
            player=player_view,
            enemy=enemy_view,
            options=list(options),
        )

    @staticmethod
    def submit_combat_action_intent(
        options: list[str],
        selected_index: int,
        spell_slug: Optional[str] = None,
        item_name: Optional[str] = None,
    ) -> tuple[str, Optional[str]] | str:
        if selected_index < 0:
            return "Dodge"
        if selected_index >= len(options):
            return "Dodge"
        chosen = options[selected_index]
        if chosen == "Cast Spell":
            return ("Cast Spell", spell_slug)
        if chosen == "Use Item":
            return ("Use Item", item_name)
        return chosen

    def list_spell_options(self, player: Character) -> list[SpellOptionView]:
        known = getattr(player, "known_spells", []) or []
        if not known:
            return []

        options: list[SpellOptionView] = []
        slots_available = getattr(player, "spell_slots_current", 0)
        for name in known:
            slug = "".join(
                ch if ch.isalnum() or ch == " " else "-" for ch in name.lower()
            ).replace(" ", "-")
            spell = self.spell_repo.get_by_slug(slug) if self.spell_repo else None
            level = spell.level_int if spell else 0
            range_text = spell.range_text if spell else ""
            needs_slot = level > 0
            playable = slots_available > 0 if needs_slot else True
            label = f"{name} (Lv {level}{'; ' + range_text if range_text else ''})"
            if needs_slot and not playable:
                label += " [no slots]"
            options.append(SpellOptionView(slug=slug, label=label, playable=playable))
        return options

    def list_combat_item_options(self, player: Character) -> list[str]:
        if not self.combat_service:
            return []
        return self.combat_service.list_usable_items(player)

    def build_character_creation_summary(self, character: Character) -> CharacterCreationSummaryView:
        location_name = "Starting Town"
        location_id = character.location_id
        if self.location_repo and location_id is not None:
            try:
                location = self.location_repo.get(int(location_id))
                if location:
                    world = self.world_repo.load_default() if self.world_repo else None
                    location_name = self._settlement_display_name(world, location) or (location.name or location_name)
            except Exception:
                pass

        return CharacterCreationSummaryView(
            character_id=character.id or 0,
            name=character.name,
            level=character.level,
            class_name=(character.class_name or "adventurer").title(),
            race=character.race or "Unknown",
            speed=getattr(character, "speed", 30),
            background=character.background or "None",
            difficulty=(character.difficulty or "normal").title(),
            hp_current=character.hp_current,
            hp_max=character.hp_max,
            attributes_line=self._format_attr_line(character.attributes),
            race_traits=list(character.race_traits or []),
            background_features=list(character.background_features or []),
            inventory=list(character.inventory or []),
            starting_location_name=location_name,
        )

    def apply_encounter_reward_intent(self, character: Character, monster: Entity) -> RewardOutcomeView:
        xp_gain = monster_kill_xp(monster.level)
        money_gain = monster_kill_gold(monster.level)
        loot_items: list[str] = []

        if monster.loot_tags:
            loot_items.append(monster.loot_tags[0])
        elif monster.faction_id:
            loot_items.append(f"{monster.faction_id} sigil")

        world_turn = 0
        if self.world_repo:
            world = self.world_repo.load_default()
            world_turn = int(getattr(world, "current_turn", 0) or 0)
        utility_seed = derive_seed(
            namespace="loot.utility_consumable",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "monster_id": int(getattr(monster, "id", 0) or 0),
                "monster_level": int(getattr(monster, "level", 1) or 1),
                "world_turn": world_turn,
            },
        )
        if not monster.loot_tags:
            utility_roll = int(utility_seed) % 4
            if utility_roll == 0:
                loot_items.append("Focus Potion")
            elif utility_roll == 1:
                loot_items.append("Whetstone")

        character.xp += xp_gain
        character.money += money_gain
        progression_messages = self._apply_level_progression(character)
        self._set_progression_messages(character, progression_messages)

        if loot_items:
            if character.inventory is None:
                character.inventory = []
            character.inventory.extend(loot_items)

        self.character_repo.save(character)
        if self.world_repo:
            world = self.world_repo.load_default()
            story_messages = self._resolve_active_story_seed_combat(world, character=character, monster=monster)
            if story_messages:
                if world is not None:
                    self.world_repo.save(world)
        return RewardOutcomeView(xp_gain=xp_gain, money_gain=money_gain, loot_items=loot_items)

    @staticmethod
    def _set_progression_messages(character: Character, messages: list[str]) -> None:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        if messages:
            flags["progression_messages"] = list(messages)
        else:
            flags.pop("progression_messages", None)

    @staticmethod
    def _pop_progression_messages(character: Character) -> list[str]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return []
        rows = flags.pop("progression_messages", [])
        if not isinstance(rows, list):
            return []
        return [str(row) for row in rows if str(row).strip()]

    @staticmethod
    def _ability_mod(score: int | None) -> int:
        if score is None:
            return 0
        try:
            return (int(score) - 10) // 2
        except Exception:
            return 0

    def _dominant_faction_standing(self, character_id: int) -> tuple[str | None, int]:
        standings = self.faction_standings_intent(character_id)
        best_id: str | None = None
        best_score = 0
        for faction_id, score in standings.items():
            normalized_score = int(score)
            if normalized_score <= best_score:
                continue
            best_id = str(faction_id)
            best_score = normalized_score
        return best_id, best_score

    def _apply_level_progression(self, character: Character) -> list[str]:
        return self.progression_service.apply_level_progression(character)

    def faction_standings_intent(self, character_id: int) -> dict[str, int]:
        if not self.faction_repo:
            return {}

        target = f"character:{character_id}"
        standings: dict[str, int] = {}
        for faction in self.faction_repo.list_all():
            standings[faction.id] = faction.reputation.get(target, 0)
        return standings

    def get_faction_standings_view_intent(self, character_id: int) -> FactionStandingsView:
        standings = self.faction_standings_intent(character_id)
        empty_state_hint = (
            "No standings tracked yet. Build reputation by resolving encounters and quests tied to local factions, then check back here."
        )
        return FactionStandingsView(standings=standings, empty_state_hint=empty_state_hint)

    def make_choice(self, player_id: int, choice: str) -> ActionResult:
        choice = choice.strip().lower()
        if choice not in {"explore", "rest", "quit"}:
            return ActionResult(messages=["Unknown action. Try: explore, rest, quit."], game_over=False)

        if choice == "quit":
            return ActionResult(messages=["Goodbye."], game_over=True)

        world = self._require_world()
        character = self._require_character(player_id)
        location = None
        if self.location_repo and character.location_id is not None:
            location = self.location_repo.get(int(character.location_id))

        if choice == "rest":
            self.rest(player_id)
            return ActionResult(messages=["You rest and feel a bit better."], game_over=False)

        # explore
        encounter_msg = self._run_encounter(character, world, location)
        self.character_repo.save(character)
        self.advance_world(ticks=1)
        return ActionResult(messages=[encounter_msg], game_over=not character.alive)

    @staticmethod
    def _world_social_flags(world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        social = world.flags.setdefault("npc_social", {})
        if not isinstance(social, dict):
            social = {}
            world.flags["npc_social"] = social
        return social

    @staticmethod
    def _world_quests(world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        quests = world.flags.setdefault("quests", {})
        if not isinstance(quests, dict):
            quests = {}
            world.flags["quests"] = quests
        return quests

    @staticmethod
    def _world_settlement_names(world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        names = world.flags.setdefault("settlement_names", {})
        if not isinstance(names, dict):
            names = {}
            world.flags["settlement_names"] = names
        return names

    @staticmethod
    def _world_town_layers(world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        layers = world.flags.setdefault("town_layers", {})
        if not isinstance(layers, dict):
            layers = {}
            world.flags["town_layers"] = layers
        return layers

    def _quest_title(self, quest_id: str) -> str:
        return self._QUEST_TITLES.get(str(quest_id), str(quest_id).replace("_", " ").title())

    @staticmethod
    def _quest_objective_summary(*, objective_kind: str, progress: int, target: int) -> str:
        kind = str(objective_kind or "kill_any")
        bounded_target = max(1, int(target))
        bounded_progress = max(0, min(int(progress), bounded_target))
        if kind == "travel_count":
            return f"Travel legs: {bounded_progress}/{bounded_target}"
        if kind == "kill_any":
            return f"Defeat hostiles: {bounded_progress}/{bounded_target}"
        return f"Objective progress: {bounded_progress}/{bounded_target}"

    @staticmethod
    def _quest_urgency_label(*, status: str, world_turn: int, expires_turn) -> str:
        normalized_status = str(status or "").lower()
        if normalized_status == "ready_to_turn_in":
            return "Ready to turn in"
        if normalized_status != "active":
            return ""
        if expires_turn is None:
            return ""
        try:
            remaining = int(expires_turn) - int(world_turn)
        except Exception:
            return ""
        if remaining <= 0:
            return "Due now"
        if remaining == 1:
            return "Due in 1 day"
        return f"Due in {remaining} days"

    @staticmethod
    def _world_consequences(world) -> list[dict]:
        if not getattr(world, "flags", None):
            world.flags = {}
        rows = world.flags.setdefault("consequences", [])
        if not isinstance(rows, list):
            rows = []
            world.flags["consequences"] = rows
        return rows

    @staticmethod
    def _world_rumour_history(world) -> list[dict]:
        if not getattr(world, "flags", None):
            world.flags = {}
        rows = world.flags.setdefault("rumour_history", [])
        if not isinstance(rows, list):
            rows = []
            world.flags["rumour_history"] = rows
        return rows

    def _append_consequence(self, world, *, kind: str, message: str, severity: str, turn: int) -> None:
        rows = self._world_consequences(world)
        rows.append(
            {
                "kind": kind,
                "message": message,
                "severity": severity,
                "turn": int(turn),
            }
        )
        if len(rows) > 20:
            del rows[:-20]

    def _recent_consequence_messages(self, world, limit: int = 3) -> list[str]:
        rows = self._world_consequences(world)
        recent = rows[-max(1, int(limit)):]
        rendered: list[str] = []
        for row in reversed(recent):
            if isinstance(row, dict) and row.get("message"):
                rendered.append(str(row["message"]))
        return rendered

    @staticmethod
    def _dominant_positive_faction(standings: dict[str, int]) -> str | None:
        best_id = None
        best_score = 0
        for faction_id, score in standings.items():
            try:
                numeric_score = int(score)
            except Exception:
                continue
            if numeric_score > best_score:
                best_score = numeric_score
                best_id = str(faction_id)
        return best_id if best_score > 0 else None

    def _record_rumour_history(
        self,
        world,
        *,
        day: int,
        character_id: int,
        dominant_faction: str | None,
        rumour_ids: list[str],
    ) -> None:
        rows = self._world_rumour_history(world)
        min_day = int(day) - self._RUMOUR_HISTORY_TURN_WINDOW
        kept = [
            row
            for row in rows
            if isinstance(row, dict) and int(row.get("day", -10_000)) >= min_day
        ]
        if len(kept) != len(rows):
            rows[:] = kept

        fingerprint = tuple(str(item) for item in rumour_ids)
        if rows:
            last = rows[-1]
            if isinstance(last, dict):
                last_fingerprint = tuple(str(item) for item in last.get("rumours", []))
                if int(last.get("day", -1)) == int(day) and last_fingerprint == fingerprint:
                    return

        rows.append(
            {
                "day": int(day),
                "character_id": int(character_id),
                "dominant_faction": dominant_faction,
                "rumours": list(fingerprint),
            }
        )
        if len(rows) > self._RUMOUR_HISTORY_MAX:
            del rows[:-self._RUMOUR_HISTORY_MAX]

    @staticmethod
    def _active_story_seed(world) -> dict | None:
        if not isinstance(getattr(world, "flags", None), dict):
            return None
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return None
        rows = narrative.get("story_seeds", [])
        if not isinstance(rows, list):
            return None
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            if row.get("status") in {"active", "simmering", "escalated"}:
                return row
        return None

    def _active_story_seed_town_lines(self, world) -> list[str]:
        row = self._active_story_seed(world)
        if not row:
            return []
        stage = str(row.get("escalation_stage", "simmering")).replace("_", " ")
        pressure = str(row.get("pressure", ""))
        return [f"Story Seed ({stage}): {pressure}"]

    def _active_story_seed_rumour(self, world) -> RumourItemView | None:
        row = self._active_story_seed(world)
        if not row:
            return None
        seed_id = str(row.get("seed_id", "story_seed"))
        stage = str(row.get("escalation_stage", "simmering")).replace("_", " ")
        text = f"[Story Seed] {row.get('pressure', 'Tension stirs among local powers.')}"
        return to_rumour_item_view(
            rumour_id=f"seed:{seed_id}",
            text=text,
            confidence="credible" if stage in {"escalated", "critical"} else "uncertain",
            source="Story Director",
        )

    def _story_memory_echo_rumour(self, world, *, character_id: int) -> RumourItemView | None:
        row = self._pick_story_memory_event(world, character_id=character_id, npc_id="rumour_board")
        if not row:
            return None
        kind = str(row.get("kind", "story_event")).replace("_", " ")
        turn = int(row.get("turn", 0))
        resolution = str(row.get("resolution", ""))
        text = f"[Echo] Folk still discuss the {kind} from day {turn}."
        if resolution:
            text = f"{text} Outcome: {resolution.replace('_', ' ')}."
        return to_rumour_item_view(
            rumour_id=f"memory:{turn}:{kind.replace(' ', '-')}",
            text=text,
            confidence="credible",
            source="Town Chronicle",
        )

    def _flashpoint_echo_rumour(self, world, *, character_id: int) -> RumourItemView | None:
        row = self._pick_flashpoint_echo(world, character_id=character_id, npc_id="rumour_board")
        if not row:
            return None
        turn = int(row.get("turn", 0))
        resolution = str(row.get("resolution", "")).replace("_", " ")
        channel = str(row.get("channel", "social"))
        bias = str(row.get("bias_faction", "")).strip()
        severity = str(row.get("severity_band", "moderate")).replace("_", " ")
        text = f"[Flashpoint Echo] Day {turn}: {resolution or 'unsettled'} resolution after {channel} intervention. Severity: {severity}."
        if bias:
            text = f"{text} {bias.title()} influence is most discussed."
        return to_rumour_item_view(
            rumour_id=f"flashpoint:{turn}:{channel}",
            text=text,
            confidence="credible" if severity in {"high", "critical"} else "uncertain",
            source="Town Chronicle",
        )

    def _recent_story_memory_town_lines(self, world, limit: int = 2) -> list[str]:
        rows = self._world_major_story_events(world)
        rendered: list[str] = []
        for row in reversed(rows[-max(1, int(limit)) :]):
            if not isinstance(row, dict):
                continue
            kind = str(row.get("kind", "story event")).replace("_", " ")
            resolution = str(row.get("resolution", ""))
            if resolution:
                rendered.append(f"Echo: {kind} resolved as {resolution.replace('_', ' ')}.")
            else:
                rendered.append(f"Echo: {kind} still shapes local talk.")
        return rendered

    def _story_memory_dialogue_hint(self, world, *, npc_id: str) -> str:
        row = self._pick_story_memory_event(world, character_id=0, npc_id=npc_id)
        if not row:
            return self._flashpoint_dialogue_hint(world, npc_id=npc_id)
        kind = str(row.get("kind", "story event")).replace("_", " ")
        resolution = str(row.get("resolution", "")).replace("_", " ")
        if resolution:
            return f"They reference the recent {kind} and its {resolution} ending."
        return f"They reference the recent {kind}."

    def _flashpoint_dialogue_hint(self, world, *, npc_id: str) -> str:
        row = self._pick_flashpoint_echo(world, character_id=0, npc_id=npc_id)
        if not row:
            return ""
        resolution = str(row.get("resolution", "")).replace("_", " ")
        channel = str(row.get("channel", "social"))
        severity = str(row.get("severity_band", "moderate")).replace("_", " ")
        if resolution:
            return f"They keep discussing the flashpoint's {resolution} outcome after {channel} intervention ({severity} severity)."
        return f"They keep discussing the unresolved flashpoint around the frontier ({severity} severity)."

    def _pick_story_memory_event(self, world, *, character_id: int, npc_id: str) -> dict | None:
        rows = self._world_major_story_events(world)
        if not rows:
            return None
        day = int(getattr(world, "current_turn", 0))
        seed = derive_seed(
            namespace="story.memory.pick",
            context={
                "day": day,
                "character_id": int(character_id),
                "npc_id": str(npc_id),
                "size": len(rows),
            },
        )
        rng = random.Random(seed)
        return dict(rows[rng.randrange(len(rows))])

    def _story_memory_fingerprint(self, world, limit: int = 4) -> tuple[str, ...]:
        rows = self._world_major_story_events(world)
        fingerprint: list[str] = []
        for row in rows[-max(1, int(limit)) :]:
            if not isinstance(row, dict):
                continue
            turn = int(row.get("turn", 0))
            kind = str(row.get("kind", "story_event"))
            resolution = str(row.get("resolution", ""))
            fingerprint.append(f"{turn}:{kind}:{resolution}")
        return tuple(fingerprint)

    def _flashpoint_echo_fingerprint(self, world, limit: int = 4) -> tuple[str, ...]:
        rows = self._world_flashpoint_echoes(world)
        fingerprint: list[str] = []
        for row in rows[-max(1, int(limit)) :]:
            if not isinstance(row, dict):
                continue
            turn = int(row.get("turn", 0))
            resolution = str(row.get("resolution", ""))
            channel = str(row.get("channel", ""))
            bias = str(row.get("bias_faction", ""))
            severity = str(row.get("severity_band", ""))
            score = int(row.get("severity_score", 0))
            fingerprint.append(f"{turn}:{resolution}:{channel}:{bias}:{severity}:{score}")
        return tuple(fingerprint)

    def _pick_flashpoint_echo(self, world, *, character_id: int, npc_id: str) -> dict | None:
        rows = self._world_flashpoint_echoes(world)
        if not rows:
            return None
        day = int(getattr(world, "current_turn", 0))
        seed = derive_seed(
            namespace="story.flashpoint.echo.pick",
            context={
                "day": day,
                "character_id": int(character_id),
                "npc_id": str(npc_id),
                "size": len(rows),
            },
        )
        rng = random.Random(seed)
        return dict(rows[rng.randrange(len(rows))])

    def _recent_flashpoint_pressure_score(self, world, *, day: int, window: int) -> int:
        rows = self._world_flashpoint_echoes(world)
        if not rows:
            return 0
        lower_bound = int(day) - int(window)
        score = 0
        for row in rows:
            turn = int(row.get("turn", -10_000)) if isinstance(row, dict) else -10_000
            if turn < lower_bound:
                continue
            if not isinstance(row, dict):
                continue
            score += int(row.get("severity_score", 0))
        return max(0, min(100, int(score)))

    def _encounter_flashpoint_adjustments(
        self,
        world,
        *,
        base_player_level: int,
        base_max_enemies: int,
        base_faction_bias: str | None,
    ) -> tuple[int, int, str | None]:
        day = int(getattr(world, "current_turn", 0))
        pressure = self._recent_flashpoint_pressure_score(world, day=day, window=4)
        flashpoint_bias = self._latest_flashpoint_bias_faction(world)

        effective_level = max(1, int(base_player_level))
        if pressure >= 70:
            effective_level += 1

        effective_max = max(1, int(base_max_enemies))
        if pressure >= 60:
            effective_max += 1
        effective_max = min(3, effective_max)

        effective_bias = flashpoint_bias if pressure >= 45 and flashpoint_bias else base_faction_bias
        return effective_level, effective_max, effective_bias

    def _latest_flashpoint_bias_faction(self, world) -> str | None:
        rows = self._world_flashpoint_echoes(world)
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            faction_id = str(row.get("bias_faction", "")).strip().lower()
            if faction_id:
                return faction_id
        return None

    @staticmethod
    def _world_major_story_events(world) -> list[dict]:
        if not isinstance(getattr(world, "flags", None), dict):
            return []
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return []
        rows = narrative.get("major_events", [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _world_flashpoint_echoes(world) -> list[dict]:
        if not isinstance(getattr(world, "flags", None), dict):
            return []
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return []
        rows = narrative.get("flashpoint_echoes", [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _resolve_active_story_seed_noncombat(
        self,
        world,
        *,
        character: Character,
        character_id: int,
        npc_id: str,
        approach: str,
    ) -> list[str]:
        row = self._active_story_seed(world)
        if not row:
            return []
        kind = str(row.get("kind", ""))
        if kind not in {"merchant_under_pressure", "faction_flashpoint"}:
            return []

        narrative = self._world_narrative_flags(world)
        seed_id = str(row.get("seed_id", "story_seed"))
        variants = row.get("resolution_variants", [])
        if not isinstance(variants, list) or not variants:
            variants = ["prosperity", "debt", "faction_shift"]

        tension = int(narrative.get("tension_level", 0))
        world_turn = int(getattr(world, "current_turn", 0))
        seed = derive_seed(
            namespace="story.seed.resolve",
            context={
                "seed_id": seed_id,
                "character_id": int(character_id),
                "npc_id": str(npc_id),
                "approach": str(approach),
                "world_turn": world_turn,
                "tension": tension,
            },
        )
        rng = random.Random(seed)
        resolution = str(variants[rng.randrange(len(variants))])

        messages: list[str] = []
        if resolution == "prosperity":
            reward = 6 if kind == "merchant_under_pressure" else 4
            character.money += reward
            self.character_repo.save(character)
            faction_delta = 2 if kind == "merchant_under_pressure" else 3
            self._apply_story_seed_faction_effect(character_id=character_id, faction_hint=row.get("faction_bias"), delta=faction_delta)
            if kind == "faction_flashpoint":
                messages.append(f"Story seed resolved (prosperity): border accord holds (+{reward} gold, influence +{faction_delta}).")
            else:
                messages.append(f"Story seed resolved (prosperity): trade routes stabilise (+{reward} gold).")
        elif resolution == "debt":
            loss_cap = 3 if kind == "faction_flashpoint" else 4
            loss = min(character.money, loss_cap)
            character.money = max(0, character.money - loss)
            self.character_repo.save(character)
            threat_shift = 2 if kind == "faction_flashpoint" else 1
            world.threat_level = max(0, int(getattr(world, "threat_level", 0)) + threat_shift)
            if kind == "faction_flashpoint":
                messages.append(f"Story seed resolved (debt): failed talks embolden militias (-{loss} gold, threat +{threat_shift}).")
            else:
                messages.append(f"Story seed resolved (debt): merchants absorb losses (-{loss} gold, threat +1).")
        else:
            faction_delta = 4 if kind == "faction_flashpoint" else 3
            self._apply_story_seed_faction_effect(character_id=character_id, faction_hint=row.get("faction_bias"), delta=faction_delta)
            if kind == "faction_flashpoint":
                messages.append("Story seed resolved (faction shift): command authority transfers after tense mediation.")
            else:
                messages.append("Story seed resolved (faction shift): local influence changes hands.")

        row["status"] = "resolved"
        row["resolution"] = resolution
        row["resolved_turn"] = world_turn
        row["resolved_by"] = "social"

        if kind == "faction_flashpoint":
            aftershock_message = self._apply_flashpoint_downstream_effects(
                world,
                row=row,
                character_id=int(character_id),
                resolution=resolution,
                channel="social",
            )
            if aftershock_message:
                self._append_consequence(
                    world,
                    kind="flashpoint_aftershock",
                    message=aftershock_message,
                    severity="normal",
                    turn=world_turn,
                )

        self._append_story_memory(
            world,
            {
                "turn": world_turn,
                "seed_id": seed_id,
                "kind": str(row.get("kind", "story_seed")),
                "resolution": resolution,
                "actor": int(character_id),
            },
        )
        self._append_consequence(
            world,
            kind="story_seed_resolved",
            message=messages[0],
            severity="normal",
            turn=world_turn,
        )
        return messages

    def _resolve_active_story_seed_combat(
        self,
        world,
        *,
        character: Character,
        monster: Entity,
    ) -> list[str]:
        row = self._active_story_seed(world)
        if not row:
            return []
        kind = str(row.get("kind", ""))
        if kind not in {"merchant_under_pressure", "faction_flashpoint"}:
            return []

        narrative = self._world_narrative_flags(world)
        seed_id = str(row.get("seed_id", "story_seed"))
        variants = row.get("resolution_variants", [])
        if not isinstance(variants, list) or not variants:
            variants = ["prosperity", "debt", "faction_shift"]

        character_id = int(getattr(character, "id", 0) or 0)
        tension = int(narrative.get("tension_level", 0))
        world_turn = int(getattr(world, "current_turn", 0))
        seed = derive_seed(
            namespace="story.seed.resolve.combat",
            context={
                "seed_id": seed_id,
                "character_id": character_id,
                "monster_id": int(getattr(monster, "id", 0) or 0),
                "monster_faction": str(getattr(monster, "faction_id", "") or ""),
                "world_turn": world_turn,
                "tension": tension,
            },
        )
        rng = random.Random(seed)
        resolution = str(variants[rng.randrange(len(variants))])

        messages: list[str] = []
        if resolution == "prosperity":
            threat_drop = 2 if kind == "faction_flashpoint" else 1
            world.threat_level = max(0, int(getattr(world, "threat_level", 0)) - threat_drop)
            faction_delta = 3 if kind == "faction_flashpoint" else 2
            self._apply_story_seed_faction_effect(character_id=character_id, faction_hint=row.get("faction_bias"), delta=faction_delta)
            if kind == "faction_flashpoint":
                messages.append(f"Story seed resolved (prosperity): militia victory secures crossings (threat -{threat_drop}).")
            else:
                messages.append("Story seed resolved (prosperity): caravan routes are secured (threat -1).")
        elif resolution == "debt":
            threat_rise = 1 if kind == "merchant_under_pressure" else 2
            world.threat_level = max(0, int(getattr(world, "threat_level", 0)) + threat_rise)
            if kind == "faction_flashpoint":
                messages.append(f"Story seed resolved (debt): pyrrhic victory deepens faction grudges (threat +{threat_rise}).")
            else:
                messages.append("Story seed resolved (debt): raiders retreat, but losses keep markets unstable (threat +1).")
        else:
            faction_delta = 4 if kind == "faction_flashpoint" else 3
            self._apply_story_seed_faction_effect(character_id=character_id, faction_hint=row.get("faction_bias"), delta=faction_delta)
            if kind == "faction_flashpoint":
                messages.append("Story seed resolved (faction shift): battlefield command reorders the regional balance.")
            else:
                messages.append("Story seed resolved (faction shift): the victory redistributes local influence.")

        row["status"] = "resolved"
        row["resolution"] = resolution
        row["resolved_turn"] = world_turn
        row["resolved_by"] = "combat"
        row["resolved_monster_id"] = int(getattr(monster, "id", 0) or 0)

        if kind == "faction_flashpoint":
            aftershock_message = self._apply_flashpoint_downstream_effects(
                world,
                row=row,
                character_id=character_id,
                resolution=resolution,
                channel="combat",
            )
            if aftershock_message:
                self._append_consequence(
                    world,
                    kind="flashpoint_aftershock",
                    message=aftershock_message,
                    severity="normal",
                    turn=world_turn,
                )

        self._append_story_memory(
            world,
            {
                "turn": world_turn,
                "seed_id": seed_id,
                "kind": str(row.get("kind", "story_seed")),
                "resolution": resolution,
                "actor": character_id,
                "monster_id": int(getattr(monster, "id", 0) or 0),
            },
        )
        self._append_consequence(
            world,
            kind="story_seed_resolved",
            message=messages[0],
            severity="normal",
            turn=world_turn,
        )
        return messages

    @staticmethod
    def _world_narrative_flags(world) -> dict:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        narrative = world.flags.setdefault("narrative", {})
        if not isinstance(narrative, dict):
            narrative = {}
            world.flags["narrative"] = narrative
        return narrative

    def _append_story_memory(self, world, row: dict) -> None:
        narrative = self._world_narrative_flags(world)
        entries = narrative.setdefault("major_events", [])
        if not isinstance(entries, list):
            entries = []
            narrative["major_events"] = entries
        entries.append(dict(row))
        if len(entries) > 20:
            del entries[:-20]

    def _apply_story_seed_faction_effect(self, *, character_id: int, faction_hint, delta: int) -> None:
        if not self.faction_repo:
            return
        target = f"character:{character_id}"
        faction_id = str(faction_hint or "").strip().lower()
        faction = self.faction_repo.get(faction_id) if faction_id else None
        if faction is None:
            factions = self.faction_repo.list_all()
            faction = factions[0] if factions else None
        if faction is None:
            return
        faction.adjust_reputation(target, int(delta))
        self.faction_repo.save(faction)

    def _apply_flashpoint_downstream_effects(
        self,
        world,
        *,
        row: dict,
        character_id: int,
        resolution: str,
        channel: str,
    ) -> str:
        narrative = self._world_narrative_flags(world)
        world_turn = int(getattr(world, "current_turn", 0))
        seed_id = str(row.get("seed_id", "story_seed"))
        faction_bias = str(row.get("faction_bias", "")).strip().lower()

        echo_seed = derive_seed(
            namespace="story.flashpoint.aftershock",
            context={
                "seed_id": seed_id,
                "character_id": int(character_id),
                "resolution": str(resolution),
                "channel": str(channel),
                "turn": world_turn,
                "faction_bias": faction_bias or "none",
            },
        )
        rng = random.Random(echo_seed)

        rival_faction = ""
        affected_count = 0
        if self.faction_repo:
            target = f"character:{character_id}"
            factions = sorted(self.faction_repo.list_all(), key=lambda item: item.id)
            if factions:
                bias_row = self.faction_repo.get(faction_bias) if faction_bias else None
                if bias_row is None:
                    bias_row = factions[0]
                faction_bias = bias_row.id

                rival_pool = [item.id for item in factions if item.id != faction_bias]
                if rival_pool:
                    rival_faction = rival_pool[rng.randrange(len(rival_pool))]

                for faction in factions:
                    has_tracked_standing = target in faction.reputation
                    is_involved_faction = faction.id in {faction_bias, rival_faction}
                    if not has_tracked_standing and not is_involved_faction:
                        continue

                    delta = 0
                    if faction.id == faction_bias:
                        if resolution == "prosperity":
                            delta = 2
                        elif resolution == "debt":
                            delta = -3
                        else:
                            delta = 3
                    elif rival_faction and faction.id == rival_faction:
                        if resolution == "prosperity":
                            delta = -1
                        elif resolution == "debt":
                            delta = 1
                        else:
                            delta = -3
                    else:
                        if resolution == "prosperity":
                            delta = 1
                        elif resolution == "debt":
                            delta = -1
                        else:
                            delta = 0

                    if delta != 0:
                        faction.adjust_reputation(target, int(delta))
                        self.faction_repo.save(faction)
                        affected_count += 1

        echoes = narrative.setdefault("flashpoint_echoes", [])
        if not isinstance(echoes, list):
            echoes = []
            narrative["flashpoint_echoes"] = echoes
        echoes.append(
            {
                "turn": world_turn,
                "seed_id": seed_id,
                "resolution": str(resolution),
                "channel": str(channel),
                "bias_faction": faction_bias or None,
                "rival_faction": rival_faction or None,
                "affected_factions": int(affected_count),
                "severity_score": 0,
                "severity_band": "low",
            }
        )
        latest = echoes[-1]
        severity_score = self._flashpoint_severity_score(
            resolution=str(resolution),
            channel=str(channel),
            affected_factions=int(affected_count),
            threat_level=int(getattr(world, "threat_level", 0)),
        )
        latest["severity_score"] = int(severity_score)
        latest["severity_band"] = self._flashpoint_severity_band(int(severity_score))
        if len(echoes) > 12:
            del echoes[:-12]

        if resolution == "prosperity":
            return "Flashpoint aftershock: patrol terms hold, but rival blocs resent the settlement."
        if resolution == "debt":
            return "Flashpoint aftershock: supply strain widens faction mistrust across the frontier."
        return "Flashpoint aftershock: command realignment ripples through local allegiances."

    @staticmethod
    def _flashpoint_severity_score(*, resolution: str, channel: str, affected_factions: int, threat_level: int) -> int:
        base = 35
        if resolution == "debt":
            base = 60
        elif resolution == "faction_shift":
            base = 72

        channel_weight = 8 if str(channel) == "combat" else 3
        faction_weight = min(18, max(0, int(affected_factions)) * 4)
        threat_weight = min(20, max(0, int(threat_level) - 4) * 3)
        score = base + channel_weight + faction_weight + threat_weight
        return max(0, min(100, int(score)))

    @staticmethod
    def _flashpoint_severity_band(score: int) -> str:
        value = int(score)
        if value >= 80:
            return "critical"
        if value >= 60:
            return "high"
        if value >= 35:
            return "moderate"
        return "low"

    @staticmethod
    def _relationship_pressure_faction(world, dominant_faction: str | None) -> str | None:
        if not dominant_faction or not isinstance(getattr(world, "flags", None), dict):
            return None
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return None
        graph = narrative.get("relationship_graph", {})
        if not isinstance(graph, dict):
            return None
        edges = graph.get("faction_edges", {})
        if not isinstance(edges, dict):
            return None

        worst_partner = None
        worst_score = 0
        for key, raw_score in edges.items():
            if not isinstance(key, str) or "|" not in key:
                continue
            left, right = key.split("|", 1)
            if dominant_faction not in {left, right}:
                continue
            partner = right if left == dominant_faction else left
            try:
                score = int(raw_score)
            except Exception:
                continue
            if score < worst_score:
                worst_score = score
                worst_partner = partner
        return worst_partner

    @staticmethod
    def _bounded_price(base_price: int, modifier: int) -> int:
        floor = 1
        ceiling = max(2, int(base_price) * 2)
        return max(floor, min(ceiling, int(base_price) + int(modifier)))

    def _town_price_modifier(self, character_id: int) -> int:
        standings = self.faction_standings_intent(character_id)
        if not standings:
            return 0
        best = max(int(score) for score in standings.values())
        if 5 <= best < 10:
            return -1
        if -10 < best <= -5:
            return 1
        return calculate_price_modifier(best)

    @staticmethod
    def _interaction_unlocks(character: Character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        unlocks = flags.setdefault("interaction_unlocks", {})
        if not isinstance(unlocks, dict):
            unlocks = {}
            flags["interaction_unlocks"] = unlocks
        return unlocks

    @staticmethod
    def _equipment_state(character: Character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        equipment = flags.setdefault("equipment", {})
        if not isinstance(equipment, dict):
            equipment = {}
            flags["equipment"] = equipment
        return equipment

    def _infer_equipment_slot(self, item_name: str) -> str | None:
        lowered = str(item_name or "").strip().lower()
        if not lowered:
            return None
        for slot, keywords in self._EQUIPMENT_SLOT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return slot
        return None

    def _sell_price_for_item(self, character_id: int, item_name: str) -> int:
        slot = self._infer_equipment_slot(item_name)
        base_by_slot = {
            "weapon": 4,
            "armor": 3,
            "trinket": 2,
        }
        base_price = base_by_slot.get(slot or "", 1)
        modifier = self._town_price_modifier(character_id)
        adjusted = int(base_price) - int(modifier)
        return max(1, adjusted)

    @staticmethod
    def _location_state_flags(character: Character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        state = flags.setdefault("location_state", {})
        if not isinstance(state, dict):
            state = {}
            flags["location_state"] = state
        return state

    @staticmethod
    def _travel_prep_state(character: Character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        state = flags.setdefault("travel_prep", {})
        if not isinstance(state, dict):
            state = {}
            flags["travel_prep"] = state
        return state

    def _active_travel_prep_profile(self, character: Character) -> dict | None:
        state = self._travel_prep_state(character)
        profile = state.get("active")
        if not isinstance(profile, dict):
            return None
        prep_id = str(profile.get("id", "")).strip()
        if not prep_id:
            return None
        return {
            "id": prep_id,
            "title": str(profile.get("title", prep_id.replace("_", " ").title())),
            "risk_shift": int(profile.get("risk_shift", 0)),
            "event_roll_shift": int(profile.get("event_roll_shift", 0)),
            "event_cap_shift": int(profile.get("event_cap_shift", 0)),
            "day_shift": int(profile.get("day_shift", 0)),
            "consumes_on_travel": bool(profile.get("consumes_on_travel", True)),
        }

    @staticmethod
    def _travel_prep_summary(prep_profile: dict | None) -> str:
        if not isinstance(prep_profile, dict):
            return ""
        title = str(prep_profile.get("title", "")).strip()
        if title:
            return title
        prep_id = str(prep_profile.get("id", "")).strip()
        return prep_id.replace("_", " ").title() if prep_id else ""

    def _consume_travel_prep(self, character: Character) -> str:
        state = self._travel_prep_state(character)
        profile = state.get("active")
        if not isinstance(profile, dict):
            return ""
        label = self._travel_prep_summary(profile)
        state.pop("active", None)
        return label

    def _find_travel_prep_item(self, prep_id: str) -> dict | None:
        target = str(prep_id or "").strip().lower()
        if not target:
            return None
        for row in self._TRAVEL_PREP_ITEMS:
            if str(row.get("id", "")).strip().lower() == target:
                return row
        return None

    def _town_layer_tags(self, *, world: World, location: Location | None) -> tuple[str, str]:
        if location is None:
            return "", ""
        cache = self._world_town_layers(world)
        key = str(int(getattr(location, "id", 0) or 0))
        cached = cache.get(key)
        if isinstance(cached, dict):
            district = str(cached.get("district", "")).strip()
            landmark = str(cached.get("landmark", "")).strip()
            if district or landmark:
                return district, landmark

        culture = self._location_culture(location)
        scale = self._settlement_scale(location)
        biome = str(getattr(location, "biome", "") or "")
        seed = derive_seed(
            namespace="town.layers",
            context={
                "world_id": int(getattr(world, "id", 0) or 0),
                "location_id": int(getattr(location, "id", 0) or 0),
                "location_name": str(getattr(location, "name", "") or "Unknown"),
                "culture": culture,
                "scale": scale,
                "biome": biome,
            },
        )
        district, landmark = generate_town_layer_tags(
            culture=culture,
            biome=biome,
            scale=scale,
            seed=seed,
        )
        cache[key] = {"district": district, "landmark": landmark}
        return district, landmark

    @staticmethod
    def _is_town_location(location: Location | None) -> bool:
        if location is None:
            return False
        name = (getattr(location, "name", "") or "").lower()
        biome = (getattr(location, "biome", "") or "").lower()
        tags = [str(tag).lower() for tag in getattr(location, "tags", []) or []]
        haystack = " ".join([name, biome] + tags)
        town_tokens = ("town", "village", "city", "square", "settlement")
        return any(token in haystack for token in town_tokens)

    def _current_location_type(self, character: Character, location: Location | None) -> str:
        state = self._location_state_flags(character)
        explicit = str(state.get("context", "")).strip().lower()
        if explicit in {"town", "wilderness"}:
            return explicit
        return "town" if self._is_town_location(location) else "wilderness"

    def _set_location_context(self, character: Character, context: str) -> None:
        state = self._location_state_flags(character)
        state["context"] = "town" if context == "town" else "wilderness"

    def _has_interaction_unlock(self, character: Character, unlock_key: str) -> bool:
        if not unlock_key:
            return False
        return bool(self._interaction_unlocks(character).get(unlock_key))

    def _grant_interaction_unlock(self, character: Character, unlock_key: str) -> None:
        if not unlock_key:
            return
        unlocks = self._interaction_unlocks(character)
        unlocks[unlock_key] = True

    def _get_npc_disposition(self, world, npc_id: str) -> int:
        social = self._world_social_flags(world)
        row = social.get(npc_id)
        if not isinstance(row, dict):
            return 0
        try:
            return int(row.get("disposition", 0))
        except Exception:
            return 0

    def _set_npc_disposition(self, world, npc_id: str, value: int) -> None:
        social = self._world_social_flags(world)
        row = social.setdefault(npc_id, {})
        if not isinstance(row, dict):
            row = {}
            social[npc_id] = row
        row["disposition"] = int(value)

    def _append_npc_memory(self, world, npc_id: str, event: dict) -> None:
        social = self._world_social_flags(world)
        row = social.setdefault(npc_id, {})
        if not isinstance(row, dict):
            row = {}
            social[npc_id] = row
        memories = row.setdefault("memory", [])
        if not isinstance(memories, list):
            memories = []
            row["memory"] = memories
        memories.append(dict(event))
        if len(memories) > 10:
            del memories[:-10]

    def _apply_quest_completion_faction_effect(
        self,
        character_id: int,
        operations: list[Callable[[object], None]] | None = None,
    ) -> None:
        if not self.faction_repo:
            return

        faction_id = ""
        factions = self.faction_repo.list_all()
        if factions:
            faction_id = str(factions[0].id)
        if not faction_id:
            return

        operation_builder = getattr(self.faction_repo, "build_reputation_delta_operation", None)
        if operations is not None and callable(operation_builder):
            operation = operation_builder(
                faction_id=faction_id,
                character_id=int(character_id),
                delta=3,
                reason="quest_completion",
                changed_turn=int(getattr(self._require_world(), "current_turn", 0)),
            )
            if callable(operation):
                operations.append(cast(Callable[[object], None], operation))
                return

        event_bus = getattr(getattr(self.progression, "event_bus", None), "publish", None)
        if callable(event_bus):
            event_bus(
                FactionReputationChangedEvent(
                    faction_id=faction_id,
                    character_id=int(character_id),
                    delta=3,
                    reason="quest_completion",
                    changed_turn=int(getattr(self._require_world(), "current_turn", 0)),
                )
            )

        target = f"character:{character_id}"
        faction = factions[0]
        faction.adjust_reputation(target, 3)
        faction.influence = max(0, int(faction.influence) + 1)
        self.faction_repo.save(faction)

    def _persist_character_world_atomic(
        self,
        character: Character,
        world: object,
        operations: Sequence[Callable[[object], None]] | None = None,
    ) -> bool:
        if not self.atomic_state_persistor or not self.world_repo:
            for operation in operations or ():
                try:
                    operation(None)
                except Exception:
                    continue
            return False
        try:
            self.atomic_state_persistor(character, world, operations)
            return True
        except TypeError:
            self.atomic_state_persistor(character, world)
            for operation in operations or ():
                try:
                    operation(None)
                except Exception:
                    continue
            return True

    def _find_town_npc(self, npc_id: str) -> dict:
        target = (npc_id or "").strip().lower()
        for npc in self._TOWN_NPCS:
            if str(npc["id"]).lower() == target:
                return npc
        raise ValueError(f"Unknown NPC: {npc_id}")

    @staticmethod
    def _npc_greeting(npc_name: str, temperament: str, disposition: int) -> str:
        if disposition >= 50:
            return f"{npc_name} smiles. 'You're a welcome sight.'"
        if disposition <= -50:
            return f"{npc_name} narrows their eyes. 'Keep this brief.'"
        tone = {
            "warm": "'Good to see you. Need anything?'",
            "stern": "'State your business.'",
            "cynical": "'Information has a price. Speak.'",
        }.get(temperament, "'Yes?'")
        return f"{npc_name} says {tone}"

    def _run_encounter(self, character: Character, world, location: Optional[Location]) -> str:
        rng = random.Random(world.rng_seed + world.current_turn + character.location_id)
        monster = self._pick_monster(character, location, rng)
        if monster is None:
            return "The ruins are silent. Nothing happens."

        evade_roll = rng.random()
        if evade_roll > 0.8:
            return f"You spot signs of {monster.name} and steer clear before it notices you."

        return self._resolve_combat(character, monster, rng, world, location)

    def _pick_monster(
        self, character: Character, location: Optional[Location], rng: random.Random
    ) -> Optional[Entity]:
        if not self.entity_repo:
            return None

        if location and location.encounters:
            candidates = self.entity_repo.get_many([entry.entity_id for entry in location.encounters])
            lookup = {entity.id: entity for entity in candidates}
            weighted: list[tuple[Entity, int]] = []
            for entry in location.encounters:
                entity = lookup.get(entry.entity_id)
                if entity is None:
                    continue
                if not (entry.min_level <= character.level <= entry.max_level):
                    continue
                weighted.append((entity, max(entry.weight, 1)))

            if weighted:
                entities, weights = zip(*weighted)
                return rng.choices(list(entities), weights=list(weights), k=1)[0]

        location_id = character.location_id
        choices = self.entity_repo.list_by_location(int(location_id)) if location_id is not None else []
        if not choices:
            choices = self.entity_repo.list_for_level(target_level=character.level)
        if not choices:
            return None
        return rng.choice(choices)

    def _resolve_combat(
        self,
        character: Character,
        monster: Entity,
        rng: random.Random,
        world,
        location: Optional[Location],
    ) -> str:
        monster_hp = monster.hp

        might = character.attributes.get("might", 0)
        strength = character.attributes.get("strength", 0)
        attribute_bonus = strength if strength else might
        player_strike = rng.randint(character.attack_min, character.attack_max) + attribute_bonus
        modified_strike = int(player_strike * character.outgoing_damage_multiplier)
        effective_player_damage = max(modified_strike - monster.armor, 1)
        monster_hp -= effective_player_damage

        if monster_hp <= 0:
            reward = self.apply_encounter_reward_intent(character, monster)
            faction_note = f" for the {monster.faction_id}" if monster.faction_id else ""
            if self.progression and getattr(self.progression, "event_bus", None):
                self.progression.event_bus.publish(
                    MonsterSlain(
                        monster_id=monster.id,
                        location_id=int(character.location_id or 0),
                        by_character_id=int(character.id or 0),
                        turn=world.current_turn,
                    )
                )
            progression_messages = self._pop_progression_messages(character)
            progression_suffix = f" {' '.join(progression_messages)}" if progression_messages else ""
            return (
                f"You cleave through {monster.name}{faction_note}, dealing {effective_player_damage} damage. "
                f"It falls. (+{reward.xp_gain} XP, +{reward.money_gain} gold){progression_suffix}"
            )

        monster_strike = rng.randint(monster.attack_min, monster.attack_max)
        modified_monster_strike = int(monster_strike * character.incoming_damage_multiplier)
        damage_taken = max(modified_monster_strike - character.armor, 1)
        character.hp_current = max(character.hp_current - damage_taken, 0)

        if character.hp_current <= 0:
            character.alive = False
            threat = f" from the {monster.faction_id}" if monster.faction_id else ""
            return (
                f"{monster.name}{threat} lands a brutal hit for {damage_taken} damage. "
                "You collapse and darkness closes in."
            )

        location_note = f" around {location.name}" if location else "" 
        return (
            f"You and {monster.name} trade blows{location_note}. "
            f"You deal {effective_player_damage} damage but take {damage_taken}. "
            f"{monster.name} still has {monster_hp} HP; you have {character.hp_current}/{character.hp_max}."
        )

    def _require_world(self):
        if self.world_repo is None:
            raise ValueError("World repository not configured")
        world = self.world_repo.load_default()
        if world is None:
            raise ValueError("World not initialized")
        return world

    def _require_character(self, player_id: int) -> Character:
        character: Optional[Character] = self.character_repo.get(player_id)
        if character is None:
            raise ValueError("Character not found")
        return character

    @staticmethod
    def _format_attr_line(attrs: dict[str, int]) -> str:
        ordered = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        aliases = {
            "STR": ("strength", "might"),
            "DEX": ("dexterity", "agility"),
            "CON": ("constitution",),
            "INT": ("intelligence", "wit"),
            "WIS": ("wisdom",),
            "CHA": ("charisma", "spirit"),
        }
        parts: list[str] = []
        for abbr in ordered:
            value = attrs.get(abbr)
            if value is None:
                value = attrs.get(abbr.lower())
            if value is None:
                for key in aliases.get(abbr, ()):
                    if key in attrs:
                        value = attrs[key]
                        break
            if value is not None:
                parts.append(f"{abbr} {value}")
        return " / ".join(parts) if parts else "Balanced stats"

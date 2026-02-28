import copy
import inspect
import json
import math
import random
import time
from pathlib import Path
from collections.abc import Callable, Sequence
from typing import Optional, cast

from rpg.application.dtos import (
    ActionResult,
    CharacterSheetView,
    CombatRoundView,
    DialogueChoiceView,
    DialogueSessionView,
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
from rpg.application.services.dialogue_service import DialogueService
from rpg.application.services.world_progression import WorldProgression
from rpg.application.services.encounter_flavour import random_intro
from rpg.application.services.progression_service import ProgressionService
from rpg.infrastructure.world_import.reference_dataset_loader import load_reference_world_dataset
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
    _REFERENCE_WORLD_DATASET_CACHE: dict[str, object] = {}
    _BIOME_SEVERITY_DEFAULT_CACHE: dict[str, dict[str, int]] = {}
    _RUMOUR_HISTORY_MAX = 12
    _RUMOUR_HISTORY_TURN_WINDOW = 8
    _TRAVEL_MAX_RADIUS = 150.0
    _TRAVEL_SPEED_DIVISOR = 25.0
    _TRAVEL_PREVIEW_RISK_WIDTH = 8
    _MAX_ACTIVE_COMPANIONS = 3
    _MAX_CAMPAIGN_RECRUITED_COMPANIONS = 3
    _COMPANION_LEAD_DISCOVERY_BASE_CHANCE = 4
    _FACTION_HEAT_MAX = 20
    _FACTION_HEAT_LOG_MAX = 32
    _FACTION_HEAT_TRAVEL_DECAY_AMOUNT = 1
    _FACTION_HEAT_TRAVEL_DECAY_INTERVAL = 3
    _FACTION_HEAT_REST_DECAY_AMOUNT = 2
    _FACTION_HEAT_RELIEF_COST = 6
    _FACTION_HEAT_RELIEF_AMOUNT = 3
    _DIPLOMACY_RELATION_MIN = -100
    _DIPLOMACY_RELATION_MAX = 100
    _DIPLOMACY_WAR_THRESHOLD = -45
    _DIPLOMACY_ALLIANCE_THRESHOLD = 45
    _COMPANION_ARC_MAX = 100
    _COMPANION_ARC_HISTORY_MAX = 30
    _NPC_COMPANION_MAP = {
        "broker_silas": "npc_silas",
        "captain_ren": "captain_ren",
    }
    _NPC_FACTION_AFFINITY = {
        "captain_ren": "the_crown",
        "broker_silas": "thieves_guild",
        "innkeeper_mara": "wardens",
    }
    _PROCEDURAL_TOWN_NPC_VERSION = 1
    _PROCEDURAL_TOWN_NPC_TEMPLATES = (
        {
            "template_id": "blacksmith",
            "role": "Blacksmith",
            "temperament": "gruff",
            "openness": 4,
            "aggression": 5,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:commerce",
            "routine": {"day": "Forge", "night": "Anvil Hall", "midnight": "Forge Office", "closed": False},
        },
        {
            "template_id": "armourer",
            "role": "Armourer",
            "temperament": "stern",
            "openness": 4,
            "aggression": 5,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:commerce",
            "routine": {"day": "Armoury", "night": "Armoury Workshop", "midnight": "Armoury Office", "closed": False},
        },
        {
            "template_id": "fletcher",
            "role": "Fletcher",
            "temperament": "focused",
            "openness": 5,
            "aggression": 3,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:commerce",
            "routine": {"day": "Fletcher Stall", "night": "Workshop Loft", "midnight": "Workshop Loft", "closed": False},
        },
        {
            "template_id": "shopkeep",
            "role": "Shopkeep",
            "temperament": "measured",
            "openness": 6,
            "aggression": 3,
            "faction_affinity": "thieves_guild",
            "dialogue_profile": "template:commerce",
            "routine": {"day": "General Store", "night": "Stockroom", "midnight": "Private Quarters", "closed": False},
        },
        {
            "template_id": "travelling_merchant",
            "role": "Travelling Merchant",
            "temperament": "opportunistic",
            "openness": 6,
            "aggression": 3,
            "faction_affinity": "thieves_guild",
            "dialogue_profile": "template:commerce",
            "routine": {"day": "Caravan Pitch", "night": "Caravan Camp", "midnight": "Caravan Camp", "closed": False},
        },
        {
            "template_id": "jeweller",
            "role": "Jeweller",
            "temperament": "careful",
            "openness": 5,
            "aggression": 2,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:commerce",
            "routine": {"day": "Gem House", "night": "Gem House", "midnight": "Vault Office", "closed": True},
        },
        {
            "template_id": "apothecary",
            "role": "Apothecary",
            "temperament": "calm",
            "openness": 6,
            "aggression": 2,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:arcane",
            "routine": {"day": "Apothecary", "night": "Herbal Workshop", "midnight": "Clinic Office", "closed": False},
        },
        {
            "template_id": "guard_captain",
            "role": "Guard Captain",
            "temperament": "disciplined",
            "openness": 4,
            "aggression": 6,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:authority",
            "routine": {"day": "Watch Post", "night": "Barracks Gate", "midnight": "Watch Barracks", "closed": True},
        },
        {
            "template_id": "magistrate",
            "role": "Magistrate",
            "temperament": "formal",
            "openness": 5,
            "aggression": 4,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:authority",
            "routine": {"day": "Town Hall", "night": "Council Chamber", "midnight": "Town Hall Office", "closed": True},
        },
        {
            "template_id": "town_crier",
            "role": "Town Crier",
            "temperament": "booming",
            "openness": 7,
            "aggression": 2,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:authority",
            "routine": {"day": "Market Steps", "night": "Bell Tower Arch", "midnight": "Bell Tower Arch", "closed": False},
        },
        {
            "template_id": "faction_emissary",
            "role": "Faction Emissary",
            "temperament": "calculating",
            "openness": 5,
            "aggression": 4,
            "faction_affinity": "thieves_guild",
            "dialogue_profile": "template:authority",
            "routine": {"day": "Guild Annex", "night": "Guild Annex", "midnight": "Guild Office", "closed": True},
        },
        {
            "template_id": "fence",
            "role": "Fence",
            "temperament": "shifty",
            "openness": 4,
            "aggression": 4,
            "faction_affinity": "thieves_guild",
            "dialogue_profile": "template:underworld",
            "routine": {"day": "Back Alley Stall", "night": "Shadow Courtyard", "midnight": "Shadow Courtyard", "closed": False},
        },
        {
            "template_id": "beggar",
            "role": "Beggar",
            "temperament": "wary",
            "openness": 6,
            "aggression": 1,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:underworld",
            "routine": {"day": "Market Square", "night": "Side Alley", "midnight": "Bridge Arch", "closed": False},
        },
        {
            "template_id": "smuggler",
            "role": "Smuggler",
            "temperament": "hushed",
            "openness": 4,
            "aggression": 4,
            "faction_affinity": "thieves_guild",
            "dialogue_profile": "template:underworld",
            "routine": {"day": "River Steps", "night": "Dockside Crate Yard", "midnight": "Dockside Crate Yard", "closed": False},
        },
        {
            "template_id": "tavern_bouncer",
            "role": "Tavern Bouncer",
            "temperament": "hard",
            "openness": 3,
            "aggression": 6,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:underworld",
            "routine": {"day": "Tavern Door", "night": "Tavern Door", "midnight": "Tavern Door", "closed": False},
        },
        {
            "template_id": "high_priest",
            "role": "High Priest",
            "temperament": "serene",
            "openness": 7,
            "aggression": 1,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:arcane",
            "routine": {"day": "Temple Nave", "night": "Temple Cloister", "midnight": "Temple Office", "closed": False},
        },
        {
            "template_id": "tower_scholar",
            "role": "Tower Scholar",
            "temperament": "distant",
            "openness": 6,
            "aggression": 2,
            "faction_affinity": "tower_obsidian",
            "dialogue_profile": "template:arcane",
            "routine": {"day": "Arcane Archive", "night": "Archive Wing", "midnight": "Scholar Cell", "closed": True},
        },
        {
            "template_id": "oracle",
            "role": "Oracle",
            "temperament": "cryptic",
            "openness": 6,
            "aggression": 1,
            "faction_affinity": "tower_obsidian",
            "dialogue_profile": "template:arcane",
            "routine": {"day": "Seer Shrine", "night": "Seer Shrine", "midnight": "Seer Shrine", "closed": False},
        },
        {
            "template_id": "cultist",
            "role": "Cultist",
            "temperament": "zealous",
            "openness": 3,
            "aggression": 5,
            "faction_affinity": "wild",
            "dialogue_profile": "template:arcane",
            "routine": {"day": "Pilgrim Queue", "night": "Catacomb Entrance", "midnight": "Catacomb Entrance", "closed": False},
        },
        {
            "template_id": "scribe",
            "role": "Scribe",
            "temperament": "curious",
            "openness": 7,
            "aggression": 2,
            "faction_affinity": "the_crown",
            "dialogue_profile": "template:social",
            "routine": {"day": "Registry Desk", "night": "Archive Hall", "midnight": "Records Wing", "closed": True},
        },
        {
            "template_id": "stablemaster",
            "role": "Stablemaster",
            "temperament": "plainspoken",
            "openness": 5,
            "aggression": 4,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:social",
            "routine": {"day": "Town Stables", "night": "Stable Yard", "midnight": "Tack Room", "closed": False},
        },
        {
            "template_id": "barkeep",
            "role": "Barkeep",
            "temperament": "warm",
            "openness": 7,
            "aggression": 2,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:social",
            "routine": {"day": "Common Room", "night": "Taproom", "midnight": "Back Counter", "closed": False},
        },
        {
            "template_id": "minstrel",
            "role": "Minstrel",
            "temperament": "charming",
            "openness": 7,
            "aggression": 1,
            "faction_affinity": "thieves_guild",
            "dialogue_profile": "template:social",
            "routine": {"day": "Tavern Stage", "night": "Tavern Stage", "midnight": "Tavern Stage", "closed": False},
        },
        {
            "template_id": "town_drunk",
            "role": "Town Drunk",
            "temperament": "erratic",
            "openness": 6,
            "aggression": 1,
            "faction_affinity": "wardens",
            "dialogue_profile": "template:social",
            "routine": {"day": "Alley Bench", "night": "Tavern Step", "midnight": "Street Corner", "closed": False},
        },
    )
    _PROCEDURAL_NAME_PREFIXES = (
        "Al",
        "Ber",
        "Cor",
        "Dra",
        "El",
        "Fen",
        "Gar",
        "Hal",
        "Ira",
        "Jor",
        "Kel",
        "Lor",
        "Mar",
        "Nor",
        "Or",
        "Per",
        "Quin",
        "Rin",
        "Sel",
        "Tor",
        "Ul",
        "Val",
        "Wen",
        "Yor",
        "Zel",
    )
    _PROCEDURAL_NAME_SUFFIXES = (
        "an",
        "a",
        "en",
        "ia",
        "or",
        "yn",
        "is",
        "el",
        "eth",
        "in",
        "or",
        "ra",
    )
    _FACTION_ENCOUNTER_PACKAGES = {
        "wardens": {"hazard": "Checkpoint Barricade", "money_bonus": 0, "bonus_item": "Whetstone"},
        "wild": {"hazard": "Predator Trails", "money_bonus": 0, "bonus_item": "Antitoxin"},
        "thieves_guild": {"hazard": "Hidden Snare", "money_bonus": 2, "bonus_item": ""},
        "the_crown": {"hazard": "Patrol Sweep", "money_bonus": 1, "bonus_item": "Torch"},
    }
    _RISK_DESCRIPTORS = {
        1: "Safe",
        2: "Guarded",
        3: "Frontier",
        4: "Perilous",
        5: "Lawless",
    }
    _DEFAULT_BIOME_SEVERITY_INDEX = {
        "temperate_deciduous_forest": 36,
        "grassland": 32,
        "steppe": 42,
        "savanna": 45,
        "taiga": 50,
        "tundra": 64,
        "desert": 78,
        "marsh": 70,
        "swamp": 74,
        "mountain": 68,
        "glacier": 92,
    }
    _DEFAULT_BIOME_SEVERITY_FILE = "data/world/biome_severity_defaults.json"
    _WORLD_WEATHER_BANDS = (
        (30, "Clear"),
        (55, "Overcast"),
        (75, "Rain"),
        (88, "Fog"),
        (97, "Storm"),
        (100, "Blizzard"),
    )
    _TRAVEL_PACE_LABELS = {
        "cautious": "cautious",
        "steady": "steady",
        "hurried": "hurried",
    }
    _CATACLYSM_PHASES = ("whispers", "grip_tightens", "map_shrinks", "ruin")
    _CATACLYSM_KINDS = ("demon_king", "tyrant", "plague")
    _CATACLYSM_PHASE_ENCOUNTER_LEVEL_DELTA = {
        "whispers": 0,
        "grip_tightens": 1,
        "map_shrinks": 1,
        "ruin": 2,
    }
    _CATACLYSM_PHASE_ENCOUNTER_MAX_DELTA = {
        "whispers": 0,
        "grip_tightens": 0,
        "map_shrinks": 1,
        "ruin": 1,
    }
    _CATACLYSM_KIND_ENCOUNTER_BIAS = {
        "demon_king": "tower_obsidian",
        "tyrant": "the_crown",
        "plague": "wild",
    }
    _CATACLYSM_PHASE_REST_CORRUPTION = {
        "whispers": 0,
        "grip_tightens": 1,
        "map_shrinks": 2,
        "ruin": 3,
    }
    _CATACLYSM_PHASE_CAMP_RISK_SHIFT = {
        "whispers": 2,
        "grip_tightens": 5,
        "map_shrinks": 8,
        "ruin": 12,
    }
    _CATACLYSM_PHASE_TOWN_PRICE_SURCHARGE = {
        "whispers": 1,
        "grip_tightens": 2,
        "map_shrinks": 3,
        "ruin": 4,
    }
    _CATACLYSM_PHASE_TRAVEL_DAY_SHIFT = {
        "whispers": 0,
        "grip_tightens": 0,
        "map_shrinks": 1,
        "ruin": 1,
    }
    _CATACLYSM_APEX_PROGRESS_THRESHOLD = 20
    _CAMP_ACTIVITY_DEFS = {
        "forage": {
            "label": "Forage",
            "heal_ratio": 0.9,
            "risk_shift": 8,
            "summary": "You scout nearby brush for useful supplies.",
        },
        "repair": {
            "label": "Repair Gear",
            "heal_ratio": 0.8,
            "risk_shift": 4,
            "summary": "You mend straps and reinforce worn equipment.",
        },
        "watch": {
            "label": "Keep Watch",
            "heal_ratio": 0.55,
            "risk_shift": -12,
            "summary": "You sleep lightly while maintaining a vigilant watch.",
        },
    }
    _SHORT_REST_HEAL_RATIO = 0.45
    _SHORT_REST_MAX_SPELL_RECOVERY = 1
    _INVESTIGATE_BIOME_LORE = {
        "forest": (
            "Fresh bark cuts suggest hurried wardens moved through recently.",
            "Moss-lined stones hide old hunter marks pointing toward safer passes.",
        ),
        "ruins": (
            "Collapsed masonry reveals older sigils beneath the current settlement era.",
            "Scored stone and ash indicate repeated skirmishes around these halls.",
        ),
        "swamp": (
            "Tainted runoff patterns show where hostile camps dump alchemical waste.",
            "Reed bundles tied to roots mark hidden paths locals use after dark.",
        ),
        "wilderness": (
            "Wind-scoured tracks hint at patrol routes rotating every few nights.",
            "Discarded bindings and fire pits imply transient warbands nearby.",
        ),
    }
    _INVESTIGATE_FACTION_LORE = {
        "wardens": "Their watch-signs prioritize chokepoints and civilian routes.",
        "thieves_guild": "Encrypted chalk symbols mark caches and messenger paths.",
        "the_crown": "Military survey stakes map defensible ground for rapid mustering.",
        "wild": "Predator totems and bone markers signal territorial boundaries.",
        "tower_obsidian": "Obsidian etchings imply ritual study of battlefield remains.",
    }
    _NPC_ROUTINES = {
        "innkeeper_mara": {
            "day": "Town Inn",
            "night": "Common Room",
            "midnight": "Back Office",
            "closed": False,
        },
        "captain_ren": {
            "day": "Watch Post",
            "night": "Tavern Patrol",
            "midnight": "Watch Barracks",
            "closed": True,
        },
        "broker_silas": {
            "day": "Market Edge",
            "night": "Tavern Corner",
            "midnight": "Shadowside Booth",
            "closed": False,
        },
    }
    _COMPANION_TEMPLATES = {
        "npc_silas": {
            "name": "Silas",
            "description": "A streetwise scout who trades caution for certainty.",
            "class_name": "rogue",
            "faction_id": "ironcoin_syndicate",
            "hp_max": 16,
            "attributes": {"dexterity": 16, "strength": 10, "constitution": 12, "intelligence": 12, "wisdom": 11, "charisma": 13},
            "known_spells": [],
            "spell_slots_max": 0,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": [],
        },
        "npc_elara": {
            "name": "Elara",
            "description": "An arcane tactician whose calm focus anchors fragile alliances.",
            "class_name": "wizard",
            "faction_id": "shrouded_athenaeum",
            "hp_max": 14,
            "attributes": {"dexterity": 12, "strength": 8, "constitution": 11, "intelligence": 16, "wisdom": 12, "charisma": 10},
            "known_spells": ["Fire Bolt", "Magic Missile", "Cure Wounds"],
            "spell_slots_max": 2,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": [],
        },
        "captain_ren": {
            "name": "Captain Ren",
            "description": "A disciplined veteran who protects the line and never breaks formation.",
            "class_name": "fighter",
            "faction_id": "the_crown",
            "hp_max": 20,
            "attributes": {"dexterity": 12, "strength": 15, "constitution": 14, "intelligence": 10, "wisdom": 12, "charisma": 11},
            "known_spells": [],
            "spell_slots_max": 0,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": [],
        },
        "npc_vael": {
            "name": "Vael",
            "description": "An Obsidian Cabal necromancer forged by forbidden fieldwork.",
            "class_name": "wizard",
            "faction_id": "tower_obsidian",
            "hp_max": 15,
            "attributes": {"dexterity": 11, "strength": 8, "constitution": 12, "intelligence": 17, "wisdom": 12, "charisma": 11},
            "known_spells": ["Ray of Sickness", "Magic Missile", "Shield"],
            "spell_slots_max": 2,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": ["npc_seraphine"],
        },
        "npc_seraphine": {
            "name": "Seraphine",
            "description": "An Alabaster Sanctum battle-cleric sworn to bind dangerous magic.",
            "class_name": "cleric",
            "faction_id": "tower_alabaster",
            "hp_max": 17,
            "attributes": {"dexterity": 10, "strength": 12, "constitution": 13, "intelligence": 11, "wisdom": 17, "charisma": 13},
            "known_spells": ["Cure Wounds", "Shield of Faith", "Sacred Flame"],
            "spell_slots_max": 2,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": ["npc_vael"],
        },
        "npc_kaelen": {
            "name": "Kaelen",
            "description": "A Briarwood ranger who turns wilderness pressure into battlefield advantage.",
            "class_name": "ranger",
            "faction_id": "wardens",
            "hp_max": 18,
            "attributes": {"dexterity": 16, "strength": 11, "constitution": 13, "intelligence": 11, "wisdom": 15, "charisma": 10},
            "known_spells": ["Hunter's Mark", "Cure Wounds"],
            "spell_slots_max": 2,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": ["npc_mirelle"],
        },
        "npc_mirelle": {
            "name": "Mirelle",
            "description": "A Silent Hand infiltrator who thrives on sabotage and precision strikes.",
            "class_name": "rogue",
            "faction_id": "thieves_guild",
            "hp_max": 16,
            "attributes": {"dexterity": 17, "strength": 9, "constitution": 12, "intelligence": 13, "wisdom": 12, "charisma": 14},
            "known_spells": [],
            "spell_slots_max": 0,
            "default_unlocked": False,
            "req_reputation": {},
            "req_completed_quest": "",
            "locked_by_companions": ["npc_kaelen"],
        },
    }
    _TOWER_SPELL_KEYWORDS: dict[str, tuple[str, ...]] = {
        "tower_crimson": (
            "fire",
            "flame",
            "burn",
            "ember",
            "force",
        ),
        "tower_cobalt": (
            "cold",
            "frost",
            "ice",
            "psychic",
            "mind",
            "enchantment",
        ),
        "tower_emerald": (
            "acid",
            "poison",
            "venom",
            "toxic",
            "nature",
            "transmutation",
        ),
        "tower_aurelian": (
            "lightning",
            "thunder",
            "storm",
            "air",
            "light",
            "divination",
            "illusion",
        ),
        "tower_obsidian": (
            "necrotic",
            "shadow",
            "entropy",
            "death",
            "necromancy",
        ),
        "tower_alabaster": (
            "radiant",
            "heal",
            "healing",
            "restores",
            "restore",
            "regains",
            "regain hit points",
            "regains hit points",
            "temporary hit points",
            "abjuration",
            "protection",
            "ward",
            "binding",
        ),
    }
    _QUEST_TITLES = {
        FIRST_HUNT_QUEST_ID: "First Hunt",
        "trail_patrol": "Trail Patrol",
        "supply_drop": "Supply Drop",
        "crown_hunt_order": "Crown Hunt Order",
        "syndicate_route_run": "Syndicate Route Run",
        "forest_path_clearance": "Forest Path Clearance",
        "ruins_wayfinding": "Ruins Wayfinding",
        "cataclysm_scout_front": "Frontline Scout Sweep",
        "cataclysm_supply_lines": "Seal Fractured Supply Lines",
        "cataclysm_alliance_accord": "Alliance Accord Muster",
        "cataclysm_apex_clash": "Apex Clash",
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
            "id": "torch",
            "name": "Torch",
            "description": "Improves visibility in dark ruins and caves.",
            "base_price": 5,
        },
        {
            "id": "rope",
            "name": "Rope",
            "description": "Secures crossings over ledges and unstable paths.",
            "base_price": 7,
        },
        {
            "id": "climbing_kit",
            "name": "Climbing Kit",
            "description": "Pitons and harnesses that reduce vertical traversal risk.",
            "base_price": 12,
        },
        {
            "id": "antitoxin",
            "name": "Antitoxin",
            "description": "Neutralizes poisonous spores, fumes, and swamp toxins.",
            "base_price": 15,
        },
        {
            "id": "iron_longsword",
            "name": "Iron Longsword",
            "description": "Reliable tier-I steel for front-line fighters.",
            "base_price": 28,
        },
        {
            "id": "leather_armor",
            "name": "Leather Armor",
            "description": "Light tier-I armor favored by scouts.",
            "base_price": 24,
        },
        {
            "id": "chain_shirt",
            "name": "Chain Shirt",
            "description": "Mid-tier armor balancing mobility and defense.",
            "base_price": 42,
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
    _TIERED_LOOT_TABLE: dict[int, tuple[str, ...]] = {
        1: (
            "Sturdy Rations",
            "Torch",
            "Rope",
            "Whetstone",
            "Leather Armor",
            "Iron Longsword",
        ),
        2: (
            "Focus Potion",
            "Antitoxin",
            "Climbing Kit",
            "Chain Shirt",
            "Arcane Focus Ring",
            "Rapier",
        ),
        3: (
            "Masterwork Longsword",
            "Scale Mail",
            "Runed Ward Charm",
            "Greater Focus Draught",
            "Duelist Rapier",
        ),
    }

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
        dialogue_service: DialogueService | None = None,
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
        self.dialogue_service = dialogue_service or DialogueService()
        self._snapshot_limit = 24
        self._snapshots: list[dict[str, object]] = []
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

    @classmethod
    def _phase_for_hour(cls, hour: int) -> str:
        normalized = int(hour) % 24
        if normalized < 5:
            return "Midnight"
        if normalized < 11:
            return "Morning"
        if normalized < 17:
            return "Afternoon"
        if normalized < 20:
            return "Dusk"
        return "Night"

    @classmethod
    def _weather_label_for_world(cls, world: World | None, biome_name: str | None = None) -> str:
        if world is None:
            return "Unknown"
        turn = max(0, int(getattr(world, "current_turn", 0) or 0))
        weather_slot = turn // 6
        threat = max(0, int(getattr(world, "threat_level", 0) or 0))
        biome_key = str(biome_name or "").strip().lower()
        severity_centered = cls._biome_severity_score(biome_key) - 50 if biome_key else 0
        severity_shift = max(-12, min(14, int(round(severity_centered / 4.0))))
        phase = cls._phase_for_hour(int(turn % 24))
        time_shift = 3 if phase in {"Night", "Midnight"} else (1 if phase == "Dusk" else 0)
        seed = derive_seed(
            namespace="world.weather",
            context={
                "world_id": int(getattr(world, "id", 0) or 0),
                "world_seed": int(getattr(world, "rng_seed", 0) or 0),
                "weather_slot": int(weather_slot),
                "threat_level": int(threat),
                "biome": biome_key or "global",
            },
        )
        rng = random.Random(seed)
        roll = min(
            100,
            max(
                1,
                int(rng.randint(1, 100)) + min(10, threat * 2) + int(severity_shift) + int(time_shift),
            ),
        )
        for threshold, label in cls._WORLD_WEATHER_BANDS:
            if roll <= int(threshold):
                return str(label)
        return "Clear"

    @classmethod
    def _world_immersion_state(cls, world: World | None, biome_name: str | None = None) -> dict[str, object]:
        if world is None:
            return {
                "day": 1,
                "hour": 0,
                "phase": "Midnight",
                "weather": "Unknown",
                "time_label": "Day 1, Midnight (00:00)",
            }
        turn = max(0, int(getattr(world, "current_turn", 0) or 0))
        day = int(turn // 24) + 1
        hour = int(turn % 24)
        phase = cls._phase_for_hour(hour)
        weather = cls._weather_label_for_world(world, biome_name=biome_name)
        return {
            "day": day,
            "hour": hour,
            "phase": phase,
            "weather": weather,
            "time_label": f"Day {day}, {phase} ({hour:02d}:00)",
        }

    @staticmethod
    def _weather_risk_shift(weather_label: str) -> int:
        weather = str(weather_label or "").strip().lower()
        if weather == "blizzard":
            return 12
        if weather == "storm":
            return 8
        if weather == "rain":
            return 4
        if weather == "fog":
            return 2
        return 0

    @staticmethod
    def _normalize_travel_pace(value: str | None) -> str:
        normalized = str(value or "steady").strip().lower()
        if normalized in {"cautious", "steady", "hurried"}:
            return normalized
        return "steady"

    @staticmethod
    def _survival_state(character: Character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        state = flags.setdefault("survival", {})
        if not isinstance(state, dict):
            state = {}
            flags["survival"] = state
        try:
            state["travel_exhaustion_level"] = max(0, min(6, int(state.get("travel_exhaustion_level", 0) or 0)))
        except Exception:
            state["travel_exhaustion_level"] = 0
        return state

    def _adjust_travel_exhaustion(self, character: Character, *, delta: int, reason: str) -> int:
        state = self._survival_state(character)
        before = int(state.get("travel_exhaustion_level", 0) or 0)
        after = max(0, min(6, before + int(delta)))
        state["travel_exhaustion_level"] = after
        state["last_exhaustion_reason"] = str(reason or "")
        return after

    @classmethod
    def _npc_schedule_snapshot(cls, world: World | None, npc_id: str) -> dict[str, object]:
        immersion = cls._world_immersion_state(world)
        phase = str(immersion.get("phase", "")).strip().lower()
        turn = int(getattr(world, "current_turn", 0) or 0) if world is not None else 0
        profile: dict[str, object] = {}
        if world is not None and isinstance(getattr(world, "flags", None), dict):
            town_state = world.flags.get("town_npcs_v1", {})
            if isinstance(town_state, dict):
                routines = town_state.get("routines", {})
                if isinstance(routines, dict):
                    loaded = routines.get(str(npc_id), {})
                    if isinstance(loaded, dict):
                        profile = dict(loaded)
        if not profile:
            profile = dict(cls._NPC_ROUTINES.get(str(npc_id), {}))
        if phase in {"night", "midnight"} and turn > 0:
            location = str(profile.get(phase, profile.get("night", "Town")) or "Town")
            available = not bool(profile.get("closed", False))
        else:
            location = str(profile.get("day", "Town"))
            available = True
        return {
            "phase": str(immersion.get("phase", "")),
            "time_label": str(immersion.get("time_label", "")),
            "location": location,
            "available": bool(available),
        }

    @staticmethod
    def _codex_state(character: Character) -> dict[str, dict[str, object]]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        raw = flags.setdefault("codex_entries", {})
        if not isinstance(raw, dict):
            raw = {}
            flags["codex_entries"] = raw
        normalized: dict[str, dict[str, object]] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            entry_id = str(key or "").strip().lower()
            if not entry_id:
                continue
            normalized[entry_id] = dict(value)
        flags["codex_entries"] = normalized
        return normalized

    def _record_codex_entry(
        self,
        character: Character,
        *,
        entry_id: str,
        category: str,
        title: str,
        body: str,
        world_turn: int,
        increment_discoveries: bool = False,
    ) -> None:
        state = self._codex_state(character)
        key = str(entry_id or "").strip().lower()
        if not key:
            return
        row = state.get(key, {})
        raw_discoveries = row.get("discoveries", 0)
        if isinstance(raw_discoveries, (int, float, str, bool)):
            try:
                discoveries = int(raw_discoveries)
            except (TypeError, ValueError):
                discoveries = 0
        else:
            discoveries = 0
        if increment_discoveries:
            discoveries += 1
        row.update(
            {
                "category": str(category or "Lore"),
                "title": str(title or key.replace("_", " ").title()),
                "body": str(body or ""),
                "discoveries": max(1, discoveries) if increment_discoveries else max(1, discoveries or 1),
                "updated_turn": int(world_turn),
            }
        )
        state[key] = row

    def get_codex_entries_intent(self, character_id: int) -> list[str]:
        character = self._require_character(character_id)
        entries = self._codex_state(character)
        if not entries:
            return ["No codex entries yet.", "Discover enemies, clues, and relics to expand your field notes."]
        ordered = sorted(entries.items(), key=lambda item: (str(item[1].get("category", "")), str(item[1].get("title", item[0]))))
        lines: list[str] = []
        for _entry_id, row in ordered:
            category = str(row.get("category", "Lore") or "Lore")
            title = str(row.get("title", "Unknown") or "Unknown")
            raw_discoveries = row.get("discoveries", 1)
            if isinstance(raw_discoveries, (int, float, str, bool)):
                try:
                    discoveries = int(raw_discoveries)
                except (TypeError, ValueError):
                    discoveries = 1
            else:
                discoveries = 1
            detail = str(row.get("body", "") or "")
            if category.lower() == "bestiary":
                if discoveries <= 1:
                    tier = "Unknown"
                elif discoveries == 2:
                    tier = "Observed"
                else:
                    tier = "Known"
                lines.append(f"- [{category}] {title} — {tier} (notes {discoveries}): {detail}")
            else:
                lines.append(f"- [{category}] {title} (notes {discoveries}): {detail}")
        return lines

    def rest(self, character_id: int) -> tuple[Character, Optional[World]]:
        character = self._require_character(character_id)
        world_before = self.world_repo.load_default() if self.world_repo else None
        heal_amount = rest_heal_amount(character.hp_max)
        character.hp_current = min(character.hp_current + heal_amount, character.hp_max)
        character.alive = True
        if hasattr(character, "spell_slots_max"):
            character.spell_slots_current = getattr(character, "spell_slots_max", 0)
        self._recover_party_runtime_state(character, context="rest")
        self._apply_cataclysm_rest_corruption(character, world_before=world_before, context="long_rest")

        if self.atomic_state_persistor and self.world_repo:
            world = self.advance_world(ticks=1, persist=False)
            if world is not None:
                self._decay_faction_heat(
                    character,
                    amount=self._FACTION_HEAT_REST_DECAY_AMOUNT,
                    world_turn=int(getattr(world, "current_turn", 0) or 0),
                    reason="rest",
                    interval_turns=0,
                )
            if world is None:
                self.character_repo.save(character)
            else:
                self.atomic_state_persistor(character, world)
        else:
            self.character_repo.save(character)
            world = self.advance_world(ticks=1)
            if world is not None:
                if self._decay_faction_heat(
                    character,
                    amount=self._FACTION_HEAT_REST_DECAY_AMOUNT,
                    world_turn=int(getattr(world, "current_turn", 0) or 0),
                    reason="rest",
                    interval_turns=0,
                ):
                    self.character_repo.save(character)
        return character, world

    def short_rest_intent(self, character_id: int) -> ActionResult:
        character = self._require_character(character_id)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        location_type = self._current_location_type(character, location)
        used_rations = False
        if location_type == "wilderness" and self._consume_inventory_item(character, "Sturdy Rations"):
            used_rations = True
        world_before = self.world_repo.load_default() if self.world_repo else None
        heal_cap = int(rest_heal_amount(int(getattr(character, "hp_max", 1) or 1)))
        heal_amount = max(1, int(round(float(heal_cap) * float(self._SHORT_REST_HEAL_RATIO))))
        if location_type == "wilderness" and not used_rations:
            heal_amount = max(1, int(round(heal_amount * 0.7)))
        character.hp_current = min(int(getattr(character, "hp_max", 1) or 1), int(getattr(character, "hp_current", 1) or 1) + heal_amount)
        if hasattr(character, "spell_slots_max"):
            max_slots = int(getattr(character, "spell_slots_max", 0) or 0)
            current_slots = int(getattr(character, "spell_slots_current", 0) or 0)
            character.spell_slots_current = min(max_slots, current_slots + int(self._SHORT_REST_MAX_SPELL_RECOVERY))
        self._recover_party_runtime_state(character, context="travel")
        corruption_loss = self._apply_cataclysm_rest_corruption(character, world_before=world_before, context="short_rest")

        world_after = self.advance_world(ticks=1) if self.world_repo else None
        if world_after is not None:
            if self._decay_faction_heat(
                character,
                amount=1,
                world_turn=int(getattr(world_after, "current_turn", 0) or 0),
                reason="short_rest",
                interval_turns=0,
            ):
                self.character_repo.save(character)
        else:
            self.character_repo.save(character)
        if world_after is None:
            self.character_repo.save(character)

        messages = [
            f"Short rest: +{heal_amount} HP recovered.",
            "You catch your breath and regain limited focus.",
        ]
        if location_type == "wilderness":
            if used_rations:
                messages.append("You consume Sturdy Rations to steady your recovery.")
            else:
                messages.append("Without Sturdy Rations, recovery is rough and incomplete.")
        exhaustion_recovery = 1 if used_rations or location_type == "town" else 0
        if exhaustion_recovery > 0:
            before = int(self._survival_state(character).get("travel_exhaustion_level", 0) or 0)
            after = self._adjust_travel_exhaustion(character, delta=-exhaustion_recovery, reason="short_rest")
            if after < before:
                messages.append(f"Travel exhaustion eases ({before} -> {after}).")
            self.character_repo.save(character)
        if corruption_loss > 0:
            messages.append(f"Cataclysm corruption seeps into camp: -{corruption_loss} HP.")
        return ActionResult(messages=messages, game_over=False)

    def long_rest_intent(self, character_id: int) -> ActionResult:
        self.rest(character_id)
        character = self._require_character(character_id)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        location_type = self._current_location_type(character, location)
        used_rations = False
        if location_type == "wilderness" and self._consume_inventory_item(character, "Sturdy Rations"):
            used_rations = True
        messages = ["Long rest complete. You rest and feel restored."]
        if location_type == "wilderness":
            if used_rations:
                messages.append("You consume Sturdy Rations and sleep deeply despite the wilds.")
            else:
                messages.append("You lacked Sturdy Rations; the rest is less restorative than an inn stay.")
        exhaustion_recovery = 2 if (location_type == "town" or used_rations) else 1
        before = int(self._survival_state(character).get("travel_exhaustion_level", 0) or 0)
        after = self._adjust_travel_exhaustion(character, delta=-exhaustion_recovery, reason="long_rest")
        if after < before:
            messages.append(f"Travel exhaustion eases ({before} -> {after}).")
        self.character_repo.save(character)
        corruption_note = self._last_rest_corruption_message(self._require_character(character_id))
        if corruption_note:
            messages.append(corruption_note)
        return ActionResult(messages=messages, game_over=False)

    def rest_intent(self, character_id: int) -> ActionResult:
        self.rest(character_id)
        messages = ["You rest and feel restored."]
        corruption_note = self._last_rest_corruption_message(self._require_character(character_id))
        if corruption_note:
            messages.append(corruption_note)
        return ActionResult(messages=messages, game_over=False)

    def get_camp_activity_options_intent(self, character_id: int) -> list[tuple[str, str]]:
        character = self._require_character(character_id)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        if self._current_location_type(character, location) != "wilderness":
            return []
        options: list[tuple[str, str]] = []
        for activity_id in ("forage", "repair", "watch"):
            row = self._CAMP_ACTIVITY_DEFS.get(activity_id, {})
            options.append((activity_id, str(row.get("label", activity_id.title()))))
        return options

    def _campfire_reflection_line(self, character: Character, world: World | None, weather_label: str) -> str:
        consequence_hint = "the road ahead"
        if world is not None:
            recent = [line for line in self._recent_consequence_messages(world) if str(line).strip()]
            if recent:
                consequence_hint = str(recent[-1]).strip().rstrip(".")
        return f"By the campfire, {character.name} reflects on {consequence_hint} under {str(weather_label).lower()} skies."

    def submit_camp_activity_intent(self, character_id: int, activity_id: str) -> ActionResult:
        character = self._require_character(character_id)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        if self._current_location_type(character, location) != "wilderness":
            return ActionResult(messages=["Camp activities can only be performed in the wilderness."], game_over=False)

        key = str(activity_id or "").strip().lower()
        activity = self._CAMP_ACTIVITY_DEFS.get(key)
        if not isinstance(activity, dict):
            return ActionResult(messages=["Unknown camp activity."], game_over=False)
        if not self._consume_inventory_item(character, "Sturdy Rations"):
            return ActionResult(messages=["You need Sturdy Rations to set camp safely."], game_over=False)

        world_before = self.world_repo.load_default() if self.world_repo else None
        world_turn = int(getattr(world_before, "current_turn", 0) or 0) if world_before is not None else 0
        immersion = self._world_immersion_state(world_before, biome_name=str(getattr(location, "biome", "") or ""))
        weather_label = str(immersion.get("weather", "Unknown"))

        heal_cap = int(rest_heal_amount(int(getattr(character, "hp_max", 1) or 1)))
        heal_ratio = float(activity.get("heal_ratio", 1.0) or 1.0)
        heal_amount = max(1, int(round(heal_cap * heal_ratio)))
        before_hp = int(getattr(character, "hp_current", 0) or 0)
        character.hp_current = min(int(getattr(character, "hp_max", 1) or 1), before_hp + heal_amount)
        character.alive = True
        if hasattr(character, "spell_slots_max"):
            max_slots = int(getattr(character, "spell_slots_max", 0) or 0)
            current_slots = int(getattr(character, "spell_slots_current", 0) or 0)
            if key == "watch":
                character.spell_slots_current = min(max_slots, current_slots + 1)
            else:
                character.spell_slots_current = max_slots

        ambush_seed = derive_seed(
            namespace="camp.ambush",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "world_turn": int(world_turn),
                "activity": str(key),
                "location_id": int(getattr(character, "location_id", 0) or 0),
                "weather": weather_label,
            },
        )
        ambush_rng = random.Random(ambush_seed)
        risk = 20 + int(activity.get("risk_shift", 0) or 0) + self._weather_risk_shift(weather_label)
        risk += self._cataclysm_camp_risk_shift(world_before)
        risk = max(4, min(85, int(risk)))
        ambush_roll = int(ambush_rng.randint(1, 100))
        threat_delta = 0

        activity_messages = [str(activity.get("summary", "You make camp."))]
        if key == "forage":
            forage_seed = derive_seed(
                namespace="camp.forage",
                context={
                    "character_id": int(getattr(character, "id", 0) or 0),
                    "world_turn": int(world_turn),
                    "weather": weather_label,
                },
            )
            forage_rng = random.Random(forage_seed)
            if forage_rng.randint(1, 100) <= 60:
                item = ["Healing Herbs", "Antitoxin", "Sturdy Rations"][forage_rng.randint(0, 2)]
                character.inventory.append(item)
                activity_messages.append(f"Foraging yields {item}.")
            else:
                activity_messages.append("Foraging turns up little beyond damp brush.")
        elif key == "repair":
            unlocks = self._interaction_unlocks(character)
            unlocks["camp_repair_ready"] = True
            activity_messages.append("Your kit is tightened and battle-ready for the next engagement.")

        if ambush_roll <= risk:
            max_safe_loss = max(0, int(getattr(character, "hp_current", 1) or 1) - 1)
            hp_loss = min(max_safe_loss, max(1, int(getattr(character, "hp_max", 1) or 1) // 12))
            if hp_loss > 0:
                character.hp_current = max(1, int(getattr(character, "hp_current", 1) or 1) - hp_loss)
            activity_messages.append("Night movement in the dark forces a skirmish at camp's edge.")
            threat_delta = 1
        else:
            activity_messages.append("The night passes without incident.")

        corruption_loss = self._apply_cataclysm_rest_corruption(character, world_before=world_before, context="camp")
        if corruption_loss > 0:
            activity_messages.append(f"Cataclysm corruption gnaws through the camp: -{corruption_loss} HP.")

        world_after = None
        if self.world_repo:
            if self.atomic_state_persistor:
                world_after = self.advance_world(ticks=1, persist=False)
                if world_after is not None:
                    if threat_delta > 0 and hasattr(world_after, "threat_level"):
                        world_after.threat_level = max(0, int(getattr(world_after, "threat_level", 0) or 0) + int(threat_delta))
                    self._decay_faction_heat(
                        character,
                        amount=1,
                        world_turn=int(getattr(world_after, "current_turn", 0) or 0),
                        reason="camp",
                        interval_turns=0,
                    )
                    self.atomic_state_persistor(character, world_after)
                else:
                    self.character_repo.save(character)
            else:
                self.character_repo.save(character)
                world_after = self.advance_world(ticks=1)
                if world_after is not None and threat_delta > 0 and hasattr(world_after, "threat_level"):
                    world_after.threat_level = max(0, int(getattr(world_after, "threat_level", 0) or 0) + int(threat_delta))
                    self.world_repo.save(world_after)
                if world_after is not None and self._decay_faction_heat(
                    character,
                    amount=1,
                    world_turn=int(getattr(world_after, "current_turn", 0) or 0),
                    reason="camp",
                    interval_turns=0,
                ):
                    self.character_repo.save(character)
        else:
            self.character_repo.save(character)

        activity_messages.append(self._campfire_reflection_line(character, world_after or world_before, weather_label))
        return ActionResult(messages=activity_messages, game_over=False)

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
        heated_faction, heat_score = self._dominant_faction_heat(character)
        if heated_faction and heat_score >= 6:
            effective_faction_bias = heated_faction

        plan = self.encounter_service.generate_plan(
            location_id=character.location_id or 0,
            player_level=effective_level,
            world_turn=world.current_turn,
            faction_bias=effective_faction_bias,
            max_enemies=effective_max_enemies,
            location_biome=str(getattr(location, "biome", "wilderness") or "wilderness"),
            world_flags=self._world_flag_projection(world),
        )
        self._apply_faction_encounter_package(
            plan,
            faction_bias=effective_faction_bias,
            character_id=int(getattr(character, "id", 0) or 0),
            world_turn=int(getattr(world, "current_turn", 0) or 0),
            location_id=int(getattr(character, "location_id", 0) or 0),
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
        hazard_text = " ".join(hazard_names).lower()
        biome_text = str(getattr(location, "biome", "wilderness") if location else "wilderness").lower()

        utility_bonus = 0
        utility_note = ""
        if self._inventory_has_item(character, "Climbing Kit") and any(token in hazard_text for token in ("cliff", "rock", "slope", "ruin", "wall", "mountain")):
            self._consume_inventory_item(character, "Climbing Kit")
            utility_bonus += 2
            utility_note = " You deploy a Climbing Kit for safer footing."
        elif self._inventory_has_item(character, "Rope") and any(token in hazard_text for token in ("chasm", "ravine", "bridge", "drop", "cliff")):
            self._consume_inventory_item(character, "Rope")
            utility_bonus += 2
            utility_note = " A rope line stabilizes your crossing."
        elif self._inventory_has_item(character, "Torch") and any(token in hazard_text for token in ("dark", "fog", "crypt", "cave", "tunnel", "night")):
            self._consume_inventory_item(character, "Torch")
            utility_bonus += 2
            utility_note = " Torchlight reveals safer routes through the hazard."
        elif self._inventory_has_item(character, "Antitoxin") and (
            any(token in hazard_text for token in ("poison", "toxic", "spore", "venom", "bog", "swamp"))
            or any(token in biome_text for token in ("swamp", "marsh", "bog"))
        ):
            self._consume_inventory_item(character, "Antitoxin")
            utility_bonus += 2
            utility_note = " Antitoxin blunts the worst of the fumes."
        dc = 12 + min(4, len(hazard_names)) + self._biome_explore_hazard_dc_shift(biome_text)
        dc = max(8, min(20, int(dc)))
        roll = rng.randint(1, 20)
        total = roll + skill_mod + utility_bonus
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
            return f"You navigate {lead_hazard} safely ({total} vs DC {dc}).{utility_note}{_environment_suffix('hazard_success')}".strip(), False

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
                f"You withdraw before combat.{utility_note}{_environment_suffix('hazard_failed')}"
            ).strip(), True
        return f"{lead_hazard} strains your advance (-{hp_loss} HP).{utility_note}{_environment_suffix('hazard_failed')}".strip(), False

    @staticmethod
    def _inventory_has_item(character: Character, item_name: str) -> bool:
        inventory = list(getattr(character, "inventory", []) or [])
        return str(item_name) in [str(row) for row in inventory]

    @staticmethod
    def _consume_inventory_item(character: Character, item_name: str) -> bool:
        inventory = list(getattr(character, "inventory", []) or [])
        target = str(item_name)
        for index, value in enumerate(inventory):
            if str(value) == target:
                del inventory[index]
                character.inventory = inventory
                return True
        return False

    @classmethod
    def _loot_tier_for_level(cls, monster_level: int) -> int:
        level = max(1, int(monster_level or 1))
        if level >= 6:
            return 3
        if level >= 3:
            return 2
        return 1

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
        biome_name = str(getattr(location, "biome", "") if location else "")
        adjusted_roll = max(1, min(100, roll + self._biome_explore_event_roll_shift(biome_name)))

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags

        if adjusted_roll <= 40:
            message = "You discover old trail marks that reveal safer routes ahead."
            event_kind = "discovery"
            self._append_consequence(
                world,
                kind="explore_discovery",
                message="Your scouting reveals useful wilderness routes.",
                severity="minor",
                turn=int(getattr(world, "current_turn", 0)),
            )
        elif adjusted_roll <= 75:
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
        lead_message = self._roll_companion_lead_discovery(
            character,
            world_turn=int(getattr(world, "current_turn", 0)),
            context_key="explore",
            location_name=str(getattr(location, "name", "unknown") if location else "unknown"),
            world_threat=int(getattr(world, "threat_level", 0) or 0),
        )
        arc_message = self._advance_companion_arc(
            character,
            channel="explore",
            world_turn=int(getattr(world, "current_turn", 0) or 0),
            base_delta=1 if event_kind in {"discovery", "cache"} else 0,
        )
        if lead_message:
            message = f"{message} {lead_message}".strip()
        if arc_message:
            message = f"{message} {arc_message}".strip()
        self.character_repo.save(character)
        if self.world_repo:
            self.world_repo.save(world)
        return message

    @classmethod
    def _load_reference_world_dataset_cached(cls):
        project_root = Path(__file__).resolve().parents[4]
        reference_dir = project_root / "data" / "reference_world"
        cache_key = str(reference_dir)
        cached = cls._REFERENCE_WORLD_DATASET_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            dataset = load_reference_world_dataset(reference_dir)
        except Exception:
            dataset = None
        cls._REFERENCE_WORLD_DATASET_CACHE[cache_key] = dataset
        return dataset

    @classmethod
    def _load_default_biome_severity_index(cls) -> dict[str, int]:
        project_root = Path(__file__).resolve().parents[4]
        defaults_path = project_root / cls._DEFAULT_BIOME_SEVERITY_FILE
        cache_key = str(defaults_path)
        cached = cls._BIOME_SEVERITY_DEFAULT_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        merged = dict(cls._DEFAULT_BIOME_SEVERITY_INDEX)
        try:
            with defaults_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                for key, value in payload.items():
                    slug = cls._biome_slug(str(key or ""))
                    if not slug:
                        continue
                    try:
                        merged[slug] = max(0, min(100, int(value)))
                    except (TypeError, ValueError):
                        continue
        except Exception:
            pass

        cls._BIOME_SEVERITY_DEFAULT_CACHE[cache_key] = dict(merged)
        return dict(merged)

    @classmethod
    def get_reference_world_dataset_intent(cls) -> dict[str, object]:
        dataset = cls._load_reference_world_dataset_cached()
        default_index = cls._load_default_biome_severity_index()
        if dataset is None:
            return {
                "available": False,
                "source_files": {},
                "biome_severity_index": default_index,
            }
        dataset_index = dict(getattr(dataset, "biome_severity_index", {}) or {})
        merged_index = dict(default_index)
        merged_index.update(dataset_index)
        return {
            "available": True,
            "source_files": dict(getattr(dataset, "source_files", {}) or {}),
            "biome_severity_index": merged_index,
        }

    @staticmethod
    def _biome_slug(value: str) -> str:
        cleaned = str(value or "").strip().lower().replace("-", " ")
        return "_".join(part for part in cleaned.split() if part)

    @classmethod
    def _biome_severity_score(cls, biome_name: str) -> int:
        dataset = cls._load_reference_world_dataset_cached()
        index = cls._load_default_biome_severity_index()
        if dataset is not None:
            index.update(dict(getattr(dataset, "biome_severity_index", {}) or {}))
        if not index:
            return 50

        slug = cls._biome_slug(biome_name)
        if not slug:
            return 50
        if slug in index:
            return max(0, min(100, int(index[slug] or 0)))

        tokens = [token for token in slug.split("_") if token]
        if not tokens:
            return 50
        scores: list[int] = []
        for key, value in index.items():
            key_text = str(key or "").lower()
            if any(token in key_text for token in tokens):
                try:
                    scores.append(int(value))
                except (TypeError, ValueError):
                    continue
        if not scores:
            return 50
        mean_score = int(round(sum(scores) / float(len(scores))))
        return max(0, min(100, mean_score))

    @classmethod
    def _biome_travel_risk_shift(cls, biome_name: str) -> int:
        centered = cls._biome_severity_score(biome_name) - 50
        return max(-6, min(6, int(round(centered / 8.0))))

    @classmethod
    def _biome_explore_hazard_dc_shift(cls, biome_name: str) -> int:
        centered = cls._biome_severity_score(biome_name) - 50
        return max(-2, min(2, int(round(centered / 20.0))))

    @classmethod
    def _biome_explore_event_roll_shift(cls, biome_name: str) -> int:
        centered = cls._biome_severity_score(biome_name) - 50
        return max(-10, min(10, int(round(centered / 5.0))))

    def wilderness_action_intent(self, character_id: int, action_id: str) -> ActionResult:
        character = self._require_character(character_id)
        world = self._require_world()
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None

        action_key = str(action_id or "").strip().lower()
        action_defs = {
            "scout": {"ability": "wisdom", "skill": "Survival", "dc": 12},
            "investigate": {"ability": "intelligence", "skill": "Investigation", "dc": 13},
            "forage": {"ability": "wisdom", "skill": "Nature", "dc": 11},
            "sneak": {"ability": "dexterity", "skill": "Stealth", "dc": 12},
        }
        payload = action_defs.get(action_key)
        if payload is None:
            return ActionResult(messages=["Unknown wilderness action."], game_over=False)

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        nonce_map = flags.setdefault("wilderness_action_nonce", {})
        if not isinstance(nonce_map, dict):
            nonce_map = {}
            flags["wilderness_action_nonce"] = nonce_map

        nonce_key = f"{action_key}:{int(getattr(world, 'current_turn', 0) or 0)}:{int(getattr(character, 'location_id', 0) or 0)}"
        nonce = int(nonce_map.get(nonce_key, 0) or 0) + 1
        nonce_map[nonce_key] = nonce

        ability_key = str(payload.get("ability", "wisdom"))
        attrs = getattr(character, "attributes", {}) or {}
        score = int(attrs.get(ability_key, 10) or 10)
        modifier = self._ability_mod(score)
        dc = int(payload.get("dc", 12) or 12)

        seed = derive_seed(
            namespace="wilderness.skill_action",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "action": action_key,
                "world_turn": int(getattr(world, "current_turn", 0) or 0),
                "location_id": int(getattr(character, "location_id", 0) or 0),
                "location_name": str(getattr(location, "name", "unknown") if location else "unknown"),
                "nonce": int(nonce),
            },
        )
        rng = random.Random(seed)
        biome_name = str(getattr(location, "biome", "") or "")
        immersion = self._world_immersion_state(world, biome_name=biome_name)
        weather_label = str(immersion.get("weather", "Unknown"))
        severe_visibility = weather_label in {"Rain", "Fog", "Storm", "Blizzard"}
        uses_perception = action_key in {"scout", "investigate"}
        if severe_visibility and uses_perception:
            roll = min(rng.randint(1, 20), rng.randint(1, 20))
            dc += 1 if weather_label in {"Rain", "Fog"} else 2
        else:
            roll = rng.randint(1, 20)
        total = roll + modifier
        success = total >= dc

        skill_name = str(payload.get("skill", "Check"))
        messages = [f"{skill_name} check: d20 ({roll}) + {modifier} = {total} vs DC {dc}."]
        if severe_visibility and uses_perception:
            messages.append(f"{weather_label} imposes disadvantage on field awareness checks.")

        if action_key == "scout":
            if success:
                if hasattr(world, "threat_level"):
                    world.threat_level = max(0, int(getattr(world, "threat_level", 0) or 0) - 1)
                messages.append("You identify safer approach lines and lower local pressure.")
            else:
                messages.append("The trails blur together; you gain no tactical advantage.")

        elif action_key == "investigate":
            if success:
                findings = ["Old Coin Pouch", "Torch", "Rope", "Scout Notes"]
                found = findings[int(seed) % len(findings)]
                character.inventory.append(found)
                biome_key = str(getattr(location, "biome", "wilderness") if location else "wilderness").strip().lower()
                biome_lines = self._INVESTIGATE_BIOME_LORE.get(biome_key) or self._INVESTIGATE_BIOME_LORE.get("wilderness", ())
                location_factions = list(getattr(location, "factions", []) or []) if location is not None else []
                local_faction = str(location_factions[0]).strip().lower() if location_factions else ""
                faction_line = self._INVESTIGATE_FACTION_LORE.get(local_faction, "")
                lore_seed = derive_seed(
                    namespace="wilderness.investigate.lore",
                    context={
                        "character_id": int(getattr(character, "id", 0) or 0),
                        "world_turn": int(getattr(world, "current_turn", 0) or 0),
                        "location_id": int(getattr(character, "location_id", 0) or 0),
                        "biome": biome_key,
                        "faction": local_faction or "none",
                    },
                )
                lore_line = ""
                if biome_lines:
                    lore_line = str(biome_lines[int(lore_seed) % len(biome_lines)])
                if faction_line:
                    lore_line = f"{lore_line} {faction_line}".strip()

                messages.append(f"You uncover {found} while searching the area.")
                if lore_line:
                    messages.append(lore_line)
                self._record_codex_entry(
                    character,
                    entry_id=f"lore:investigate:{int(getattr(character, 'location_id', 0) or 0)}",
                    category="Lore",
                    title="Field Investigation Notes",
                    body=(
                        f"Recovered {found}. "
                        f"Biome: {biome_key or 'unknown'}. "
                        f"Local faction: {(local_faction or 'unaligned').replace('_', ' ')}. "
                        f"{lore_line}".strip()
                    ),
                    world_turn=int(getattr(world, "current_turn", 0) or 0),
                    increment_discoveries=True,
                )
            else:
                messages.append("Your search turns up scraps and false leads.")

        elif action_key == "forage":
            if success:
                heal = max(1, rng.randint(1, 4) + max(0, modifier))
                character.hp_current = min(int(getattr(character, "hp_max", 1) or 1), int(getattr(character, "hp_current", 1) or 1) + heal)
                if rng.randint(1, 100) <= 35:
                    character.inventory.append("Sturdy Rations")
                    messages.append(f"You recover {heal} HP and gather Sturdy Rations.")
                else:
                    messages.append(f"You recover {heal} HP from edible finds and clean water.")
            else:
                messages.append("Foraging fails to yield anything safe to consume.")

        elif action_key == "sneak":
            if success:
                flags["next_explore_surprise"] = "player"
                messages.append("You advance quietly; your next encounter starts with surprise.")
            else:
                messages.append("You snap a branch and lose the element of stealth.")

        self.character_repo.save(character)
        if self.world_repo:
            self.world_repo.save(world)
        return ActionResult(messages=messages, game_over=False)

    def consume_next_explore_surprise_intent(self, character_id: int) -> str | None:
        character = self._require_character(character_id)
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return None
        value = str(flags.pop("next_explore_surprise", "") or "").strip().lower()
        if value not in {"player", "enemy", "none"}:
            value = ""
        self.character_repo.save(character)
        return value or None

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

        encounter_mode = "snare"
        if roll > 66:
            encounter_mode = "poison"
        elif roll > 33:
            encounter_mode = "dark"

        utility_item = ""
        utility_note = ""
        if encounter_mode == "snare" and self._inventory_has_item(character, "Rope"):
            self._consume_inventory_item(character, "Rope")
            utility_item = "Rope"
            utility_note = " You throw a rope line and avoid the worst of the pursuit."
        elif encounter_mode == "dark" and self._inventory_has_item(character, "Torch"):
            self._consume_inventory_item(character, "Torch")
            utility_item = "Torch"
            utility_note = " Torchlight keeps the route visible during the withdrawal."
        elif encounter_mode == "poison" and self._inventory_has_item(character, "Antitoxin"):
            self._consume_inventory_item(character, "Antitoxin")
            utility_item = "Antitoxin"
            utility_note = " Antitoxin blunts tainted cuts and fumes while retreating."

        threat_delta = 1
        if utility_item:
            threat_delta = max(0, threat_delta - 1)
        if hasattr(world, "threat_level"):
            world.threat_level = max(0, int(world.threat_level) + int(threat_delta))

        hp_loss = 0
        if roll <= 60:
            max_safe_loss = max(0, int(getattr(character, "hp_current", 1)) - 1)
            hp_loss = min(max_safe_loss, max(1, int(getattr(character, "hp_max", 1)) // 12))
            if utility_item:
                hp_loss = max(0, int(hp_loss) - 1)
            if hp_loss > 0:
                character.hp_current = max(1, int(character.hp_current) - int(hp_loss))
            message = (
                f"You spot danger and withdraw before blades are drawn, losing {hp_loss} HP in the scramble."
                if hp_loss > 0
                else "You spot danger and withdraw before blades are drawn."
            )
        else:
            message = "You mark hostile movement and avoid direct combat; local danger rises."
        if utility_note:
            message = f"{message}{utility_note}".strip()

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["last_explore_event"] = {
            "kind": "threat_no_combat",
            "turn": int(getattr(world, "current_turn", 0)),
            "seed": int(seed),
            "enemy_count": len(enemies),
            "mode": encounter_mode,
            "utility_item": utility_item,
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
        if world_state is not None:
            self._ensure_persistent_town_npcs(world_state)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        biome_name = str(getattr(location, "biome", "") or "")
        if world_state is not None:
            self._resolve_cataclysm_terminal_state(world_state)
        immersion = self._world_immersion_state(world_state, biome_name=biome_name)
        cataclysm = self._world_cataclysm_state(world_state)
        end_state = self._world_cataclysm_end_state(world_state)
        try:
            raw_progress = cataclysm.get("progress", 0)
            cataclysm_progress = max(0, min(100, int(raw_progress if isinstance(raw_progress, (int, float, str)) else 0)))
        except Exception:
            cataclysm_progress = 0
        summary = str(cataclysm.get("summary", "") or "")
        if bool(end_state.get("game_over", False)):
            summary = str(end_state.get("message", "") or "Game Over — The World Fell")
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
            time_label=str(immersion.get("time_label", "")),
            weather_label=str(immersion.get("weather", "Unknown")),
            cataclysm_active=bool(cataclysm.get("active", False)),
            cataclysm_kind=str(cataclysm.get("kind", "") or ""),
            cataclysm_phase=str(cataclysm.get("phase", "") or ""),
            cataclysm_progress=cataclysm_progress,
            cataclysm_summary=summary,
        )

    def get_cataclysm_terminal_state_intent(self, character_id: int) -> tuple[bool, str] | None:
        self._require_character(character_id)
        if not self.world_repo:
            return None
        world = self._require_world()
        end_state = self._resolve_cataclysm_terminal_state(world)
        message = str(end_state.get("message", "") or "") if isinstance(end_state, dict) else ""
        if not message:
            return None
        return bool(end_state.get("game_over", False)), message

    def get_character_sheet_intent(self, character_id: int) -> CharacterSheetView:
        character = self._require_character(character_id)
        level = max(1, int(getattr(character, "level", 1) or 1))
        xp = max(0, int(getattr(character, "xp", 0) or 0))
        class_levels_line = ""
        class_levels = getattr(character, "class_levels", None)
        if isinstance(class_levels, dict):
            normalized: list[tuple[str, int]] = []
            for raw_slug, raw_level in class_levels.items():
                slug = str(raw_slug or "").strip().lower()
                if not slug:
                    continue
                try:
                    level_value = int(raw_level or 0)
                except Exception:
                    continue
                if level_value <= 0:
                    continue
                normalized.append((slug, level_value))
            if normalized:
                normalized.sort(key=lambda item: (-int(item[1]), item[0]))
                class_levels_line = " / ".join(f"{slug.title()} {int(level_value)}" for slug, level_value in normalized)
        if level >= LEVEL_CAP:
            next_level_xp = xp_required_for_level(level)
            xp_to_next = 0
        else:
            next_level_xp = xp_required_for_level(level + 1)
            xp_to_next = max(0, int(next_level_xp) - xp)
        pressure_summary, pressure_lines = self._faction_pressure_display(character)
        return CharacterSheetView(
            character_id=int(character.id or 0),
            name=character.name,
            race=character.race or "",
            class_name=character.class_name or "Adventurer",
            alignment=str(getattr(character, "alignment", "true_neutral") or "true_neutral").replace("_", " ").title(),
            difficulty=character.difficulty or "normal",
            level=level,
            xp=xp,
            next_level_xp=int(next_level_xp),
            xp_to_next_level=int(xp_to_next),
            hp_current=int(character.hp_current),
            hp_max=int(character.hp_max),
            class_levels_line=class_levels_line,
            pressure_summary=pressure_summary,
            pressure_lines=pressure_lines,
        )

    def get_level_up_pending_intent(self, character_id: int) -> LevelUpPendingView | None:
        character = self._require_character(character_id)
        available_classes: list[str] = []
        if self.class_repo is not None:
            try:
                available_classes = [str(getattr(row, "slug", "") or "").strip().lower() for row in self.class_repo.list_playable()]
            except Exception:
                available_classes = []
        return self.progression_service.preview_pending(character, available_classes=available_classes)

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
                class_choice=option,
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
            unlock_entries = row.get("unlocks", []) if isinstance(row, dict) else []
            normalized_unlocks: list[tuple[str, str, int]] = []
            if isinstance(unlock_entries, list):
                for unlock in unlock_entries:
                    if not isinstance(unlock, dict):
                        continue
                    unlock_kind = str(unlock.get("kind", "") or "").strip() or "growth_choice"
                    unlock_key = str(unlock.get("key", "") or "").strip()
                    unlock_level = int(unlock.get("level", to_level) or to_level)
                    if not unlock_key:
                        continue
                    normalized_unlocks.append((unlock_kind, unlock_key, unlock_level))
            if not normalized_unlocks:
                row_choice = str(row.get("growth_choice", growth_choice) or growth_choice)
                unlock_key = f"level_{to_level}_{row_choice}"
                normalized_unlocks.append(("growth_choice", unlock_key, to_level))

            if callable(operation_builder):
                for unlock_kind, unlock_key, unlock_level in normalized_unlocks:
                    operation = operation_builder(
                        character_id=int(character.id or 0),
                        unlock_kind=unlock_kind,
                        unlock_key=unlock_key,
                        unlocked_level=unlock_level,
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
                    unlock_entries = row.get("unlocks", []) if isinstance(row, dict) else []
                    normalized_unlocks: list[tuple[str, str, int]] = []
                    if isinstance(unlock_entries, list):
                        for unlock in unlock_entries:
                            if not isinstance(unlock, dict):
                                continue
                            unlock_kind = str(unlock.get("kind", "") or "").strip() or "growth_choice"
                            unlock_key = str(unlock.get("key", "") or "").strip()
                            unlock_level = int(unlock.get("level", to_level) or to_level)
                            if not unlock_key:
                                continue
                            normalized_unlocks.append((unlock_kind, unlock_key, unlock_level))
                    if not normalized_unlocks:
                        row_choice = str(row.get("growth_choice", growth_choice) or growth_choice)
                        unlock_key = f"level_{to_level}_{row_choice}"
                        normalized_unlocks.append(("growth_choice", unlock_key, to_level))

                    for unlock_kind, unlock_key, unlock_level in normalized_unlocks:
                        recorder(
                            character_id=int(character.id or 0),
                            unlock_kind=unlock_kind,
                            unlock_key=unlock_key,
                            unlocked_level=unlock_level,
                            created_turn=int(getattr(world, "current_turn", 0)) if world is not None else 0,
                        )

        return ActionResult(messages=level_messages, game_over=False)

    def initialize_skill_training_intent(
        self,
        character_id: int,
        *,
        grant_level_points: bool = False,
    ) -> ActionResult:
        character = self._require_character(character_id)
        snapshot = self.progression_service.initialize_skill_training(
            character,
            grant_level_points=grant_level_points,
        )
        self.character_repo.save(character)
        points = int(snapshot.get("points_available", 0) or 0)
        source_level = int(snapshot.get("points_source_level", 0) or 0)
        if grant_level_points and points > 0:
            return ActionResult(
                messages=[f"Skill training initialized: {points} point(s) ready at level {source_level}."],
                game_over=False,
            )
        return ActionResult(messages=["Skill training profile initialized."], game_over=False)

    def get_skill_training_status_intent(self, character_id: int) -> dict[str, object]:
        character = self._require_character(character_id)
        snapshot = self.progression_service.get_skill_training_snapshot(character)
        return dict(snapshot)

    def list_granular_skills_intent(
        self,
        character_id: int,
        *,
        allow_special: bool = False,
    ) -> list[dict[str, object]]:
        character = self._require_character(character_id)
        return self.progression_service.list_granular_skills(character, allow_special=allow_special)

    def declare_skill_training_intent_intent(self, character_id: int, skill_slugs: list[str]) -> ActionResult:
        character = self._require_character(character_id)
        payload = self.progression_service.declare_skill_training_intent(character, skill_slugs)
        self.character_repo.save(character)
        intent = list(payload.get("intent", [])) if isinstance(payload, dict) else []
        if intent:
            labels = ", ".join(str(row).replace("_", " ").title() for row in intent)
            return ActionResult(messages=[f"Training intent set: {labels}."], game_over=False)
        return ActionResult(messages=["Training intent cleared."], game_over=False)

    def spend_skill_proficiency_points_intent(
        self,
        character_id: int,
        allocations: dict[str, int],
        *,
        allow_special: bool = False,
    ) -> ActionResult:
        character = self._require_character(character_id)
        try:
            messages = self.progression_service.spend_skill_proficiency_points(
                character,
                allocations,
                allow_special=allow_special,
            )
        except ValueError as exc:
            return ActionResult(messages=[str(exc)], game_over=False)
        self.character_repo.save(character)
        return ActionResult(messages=messages, game_over=False)

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
        cataclysm = self._world_cataclysm_state(world)
        world_turn = int(getattr(world, "current_turn", 0)) if world is not None else 0
        threat_level = int(getattr(world, "threat_level", 0)) if world is not None else 0

        current_location_id = getattr(character, "location_id", None)
        current_location = self.location_repo.get(current_location_id) if current_location_id is not None else None
        diplomacy_state: dict[str, object] = {}
        if world is not None:
            diplomacy_state, diplomacy_changed = self._sync_faction_diplomacy(
                world,
                character=character,
                current_location=current_location,
            )
            if diplomacy_changed and self.world_repo:
                self.world_repo.save(world)
        discovered = self._discovered_locations(character, current_location)
        locations = self.location_repo.list_all()
        destinations: list[TravelDestinationView] = []
        for location in locations:
            if current_location_id is not None and location.id == current_location_id:
                continue
            if current_location is not None and not self._is_within_travel_radius(current_location, location):
                continue
            location_type = "town" if self._is_town_location(location) else "wilderness"
            biome = str(getattr(location, "biome", "") or "unknown")
            recommended_level = getattr(location, "recommended_level", "?")
            is_discovered = int(getattr(location, "id", 0) or 0) in discovered
            display_name = self._travel_destination_name(
                world=world,
                source=current_location,
                destination=location,
                discovered=is_discovered,
            )
            risk_hint = self._travel_risk_hint(
                character_id=character_id,
                world_turn=world_turn,
                threat_level=threat_level,
                location_id=int(getattr(location, "id", 0) or 0),
                location_name=display_name,
                recommended_level=int(recommended_level) if isinstance(recommended_level, int) else 1,
                travel_mode="road",
                prep_profile=prep_profile,
                diplomacy_risk_shift=self._diplomacy_travel_risk_shift(diplomacy_state=diplomacy_state, location=location),
            )
            risk_hint = self._apply_cataclysm_travel_risk_hint(risk_hint, cataclysm)
            road_days = self._estimate_travel_days(
                character=character,
                source=current_location,
                destination=location,
                travel_mode="road",
                prep_profile=prep_profile,
            )
            road_days = max(1, min(9, int(road_days) + self._cataclysm_travel_day_shift(cataclysm)))
            risk_descriptor = self._travel_risk_descriptor(location=location, risk_hint=risk_hint)
            risk_width = int(self._TRAVEL_PREVIEW_RISK_WIDTH)
            risk_label = str(risk_descriptor or "")[:risk_width]
            level_label = f"Lv {recommended_level}"
            days_label = f"{road_days}d"
            preview = f"{level_label:<6} • {days_label:<3} • {risk_label:<{risk_width}}"
            diplomacy_route_note = self._diplomacy_route_note(diplomacy_state=diplomacy_state, location=location)
            cataclysm_note = self._cataclysm_route_note(road_days=road_days, cataclysm=cataclysm)
            route_note = " ".join(part for part in [cataclysm_note, diplomacy_route_note] if part).strip()
            destinations.append(
                TravelDestinationView(
                    location_id=int(location.id),
                    name=display_name,
                    location_type=location_type,
                    biome=biome,
                    preview=preview,
                    estimated_days=road_days,
                    route_note=route_note,
                    mode_hint="Modes: Road balanced • Stealth safer/slower • Caravan safer/slower",
                    prep_summary=prep_summary,
                )
            )
        return sorted(destinations, key=lambda row: (int(row.estimated_days), str(row.name).lower()))

    def _travel_destination_name(
        self,
        *,
        world: World | None,
        source: Location | None,
        destination: Location,
        discovered: bool,
    ) -> str:
        if discovered:
            return self._settlement_display_name(world, destination)
        direction = self._get_direction(source, destination)
        direction_label = self._direction_compact_label(direction)
        destination_type = "Town" if self._is_town_location(destination) else "Wilderness"
        return f"{direction_label} {destination_type}"

    @staticmethod
    def _direction_compact_label(direction: str) -> str:
        normalized = str(direction or "").strip().lower().replace("_", "-").replace(" ", "-")
        mapping = {
            "north": "Northern",
            "south": "Southern",
            "east": "Eastern",
            "west": "Western",
            "north-east": "North-East",
            "northeast": "North-East",
            "north-west": "North-West",
            "northwest": "North-West",
            "south-east": "South-East",
            "southeast": "South-East",
            "south-west": "South-West",
            "southwest": "South-West",
        }
        return mapping.get(normalized, str(direction or "Unknown").title())

    @staticmethod
    def _discovered_locations(character: Character, current_location: Location | None) -> set[int]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return {int(getattr(current_location, "id", 0) or 0)} if current_location is not None else set()
        raw = flags.get("discovered_locations", [])
        discovered: set[int] = set()
        if isinstance(raw, list):
            for value in raw:
                try:
                    discovered.add(int(value))
                except (TypeError, ValueError):
                    continue
        if current_location is not None:
            discovered.add(int(getattr(current_location, "id", 0) or 0))
        return {item for item in discovered if item > 0}

    @staticmethod
    def _location_faction_ids(location: Location | None) -> set[str]:
        if location is None:
            return set()

        discovered: set[str] = set()
        factions = getattr(location, "factions", None)
        if isinstance(factions, list):
            for faction_id in factions:
                normalized = str(faction_id or "").strip()
                if normalized:
                    discovered.add(normalized)

        hazard = getattr(location, "hazard_profile", None)
        flags = getattr(hazard, "environmental_flags", None)
        if isinstance(flags, list):
            for item in flags:
                text = str(item or "")
                if text.startswith("faction:") and ":" in text:
                    normalized = text.split(":", 1)[1].strip()
                    if normalized:
                        discovered.add(normalized)

        tags = getattr(location, "tags", None)
        if isinstance(tags, list):
            for item in tags:
                text = str(item or "")
                if text.startswith("faction:") and ":" in text:
                    normalized = text.split(":", 1)[1].strip()
                    if normalized:
                        discovered.add(normalized)

        return discovered

    def _discovered_factions(self, character: Character, current_location: Location | None = None) -> set[str]:
        discovered: set[str] = set()
        flags = getattr(character, "flags", None)
        if isinstance(flags, dict):
            raw = flags.get("discovered_factions", [])
            if isinstance(raw, list):
                for value in raw:
                    normalized = str(value or "").strip()
                    if normalized:
                        discovered.add(normalized)

        discovered.update(self._location_faction_ids(current_location))
        return discovered

    def _record_discovered_factions(self, character: Character, location: Location | None) -> None:
        discovered = self._discovered_factions(character, current_location=location)
        discovered.update(self._location_faction_ids(location))

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["discovered_factions"] = sorted(discovered)

    @classmethod
    def _travel_risk_descriptor(cls, *, location: Location, risk_hint: str) -> str:
        hazard = getattr(location, "hazard_profile", None)
        severity = int(getattr(hazard, "severity", 1) or 1)
        tier = max(1, min(5, severity))
        normalized_hint = str(risk_hint or "").strip().lower()
        if normalized_hint == "high":
            tier = min(5, tier + 1)
        elif normalized_hint == "low":
            tier = max(1, tier - 1)
        return str(cls._RISK_DESCRIPTORS.get(tier, "Unknown"))

    @classmethod
    def _is_within_travel_radius(cls, source: Location, destination: Location) -> bool:
        src_x = float(getattr(source, "x", 0.0) or 0.0)
        src_y = float(getattr(source, "y", 0.0) or 0.0)
        dst_x = float(getattr(destination, "x", 0.0) or 0.0)
        dst_y = float(getattr(destination, "y", 0.0) or 0.0)
        distance = math.sqrt((dst_x - src_x) ** 2 + (dst_y - src_y) ** 2)
        return distance <= float(cls._TRAVEL_MAX_RADIUS)

    @staticmethod
    def _get_direction(source: Location | None, destination: Location) -> str:
        if source is None:
            return "Unknown"
        src_x = float(getattr(source, "x", 0.0) or 0.0)
        src_y = float(getattr(source, "y", 0.0) or 0.0)
        dst_x = float(getattr(destination, "x", 0.0) or 0.0)
        dst_y = float(getattr(destination, "y", 0.0) or 0.0)
        dx = dst_x - src_x
        dy = dst_y - src_y

        if abs(dx) > abs(dy) * 2:
            return "East" if dx > 0 else "West"
        if abs(dy) > abs(dx) * 2:
            return "South" if dy > 0 else "North"
        if dy < 0 and dx > 0:
            return "North-East"
        if dy < 0 and dx < 0:
            return "North-West"
        if dy > 0 and dx > 0:
            return "South-East"
        if dy > 0 and dx < 0:
            return "South-West"
        if dx == 0 and dy == 0:
            return "Here"
        return "Unknown"

    @staticmethod
    def _location_flavour_hint(location: Location) -> str:
        hazard = getattr(location, "hazard_profile", None)
        flags = getattr(hazard, "environmental_flags", None)
        if isinstance(flags, list):
            culture_raw = next(
                (
                    str(item).split(":", 1)[1].strip()
                    for item in flags
                    if str(item).startswith("culture_raw:") and ":" in str(item)
                ),
                "",
            )
            if culture_raw:
                return f"Culture {culture_raw}"

        tags = getattr(location, "tags", None)
        if isinstance(tags, list):
            culture_slug = next(
                (
                    str(item).split(":", 1)[1].strip()
                    for item in tags
                    if str(item).startswith("culture:") and ":" in str(item)
                ),
                "",
            )
            if culture_slug:
                label = culture_slug.replace("_", " ").strip().title()
                return f"Culture {label}"
        return ""

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
        diplomacy_risk_shift: int = 0,
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
        character = self._require_character(character_id)
        pressure += self._faction_heat_pressure(character)
        location = self.location_repo.get(int(location_id)) if self.location_repo else None
        biome_shift = self._biome_travel_risk_shift(str(getattr(location, "biome", "") or ""))
        mode_shift = {"road": 0, "stealth": -8, "caravan": -12}.get(mode, 0)
        score = (
            roll
            + pressure
            + mode_shift
            + max(-30, min(10, prep_risk_shift))
            + biome_shift
            + max(-12, min(18, int(diplomacy_risk_shift)))
        )

        if score <= 40:
            return "Low"
        if score <= 85:
            return "Moderate"
        return "High"

    def travel_intent(
        self,
        character_id: int,
        destination_id: int | None = None,
        travel_mode: str = "road",
        travel_pace: str = "steady",
    ) -> ActionResult:
        character = self._require_character(character_id)
        mode = self._normalize_travel_mode(travel_mode)
        pace = self._normalize_travel_pace(travel_pace)
        prep_profile = self._active_travel_prep_profile(character)
        target_location = None
        current_location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        if self.location_repo:
            locations = self.location_repo.list_all()
            if destination_id is not None:
                reachable_ids = {
                    int(item.location_id)
                    for item in self.get_travel_destinations_intent(character_id)
                }
                target_location = next((item for item in locations if int(item.id) == int(destination_id)), None)
                if target_location is None or int(destination_id) not in reachable_ids:
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
            travel_pace=pace,
            prep_profile=prep_profile,
        )

        event_days = self._plan_travel_event_days(
            character_id=character_id,
            destination_id=int(getattr(target_location, "id", 0) or 0),
            destination_name=str(destination_name or "unknown"),
            travel_mode=mode,
            travel_pace=pace,
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
                    travel_pace=pace,
                    prep_profile=prep_profile,
                    destination_biome=str(getattr(target_location, "biome", "") or ""),
                )
                if travel_event_message:
                    log_messages.append(travel_event_message)
            else:
                log_messages.append(self._travel_day_quiet_message(day=day, estimated_days=estimated_days, travel_mode=mode))

            active_world = self.world_repo.load_default() if self.world_repo else None
            destination_biome = str(getattr(target_location, "biome", "") or "")
            immersion = self._world_immersion_state(active_world, biome_name=destination_biome)
            weather_label = str(immersion.get("weather", "Unknown"))
            if weather_label in {"Rain", "Storm", "Blizzard", "Fog"}:
                log_messages.append(f"Weather: {weather_label} slows the march and complicates scouting.")
            ration_used = self._consume_inventory_item(character, "Sturdy Rations")
            if ration_used:
                log_messages.append("Supplies: You consume Sturdy Rations to keep marching strength.")
            else:
                log_messages.append("Supplies: You have no Sturdy Rations for today.")

            if weather_label == "Blizzard" and not ration_used:
                max_safe_loss = max(0, int(getattr(character, "hp_current", 1)) - 1)
                hp_loss = min(max_safe_loss, 1)
                if hp_loss > 0:
                    character.hp_current = max(1, int(getattr(character, "hp_current", 1)) - hp_loss)
                    log_messages.append("Without winter provisions, the blizzard strips 1 HP from exposure.")

            strain_score = 0
            if pace == "hurried":
                strain_score += 1
            elif pace == "cautious":
                strain_score -= 1
            if weather_label in {"Storm", "Blizzard"}:
                strain_score += 1
            if not ration_used:
                strain_score += 1

            if strain_score >= 2:
                next_level = self._adjust_travel_exhaustion(character, delta=1, reason="travel_strain")
                log_messages.append(f"Travel strain builds exhaustion (level {next_level}/6).")
                if next_level >= 4:
                    max_safe_loss = max(0, int(getattr(character, "hp_current", 1) or 1) - 1)
                    hp_loss = min(max_safe_loss, 1 + max(0, next_level - 4))
                    if hp_loss > 0:
                        character.hp_current = max(1, int(getattr(character, "hp_current", 1) or 1) - hp_loss)
                        log_messages.append(f"Exhaustion wear drains {hp_loss} HP.")

            self.character_repo.save(character)
            world_after_tick = self.advance_world(ticks=1)
            if world_after_tick is not None and self._decay_faction_heat(
                character,
                amount=self._FACTION_HEAT_TRAVEL_DECAY_AMOUNT,
                world_turn=int(getattr(world_after_tick, "current_turn", 0) or 0),
                reason="travel",
                interval_turns=self._FACTION_HEAT_TRAVEL_DECAY_INTERVAL,
            ):
                self.character_repo.save(character)

        if target_location is not None:
            character.location_id = target_location.id
            discovered = self._discovered_locations(character, target_location)
            discovered.add(int(getattr(target_location, "id", 0) or 0))
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            flags["discovered_locations"] = sorted(discovered)
            self._record_discovered_factions(character, target_location)
            self._set_location_context(character, target_context)
            self.character_repo.save(character)
        else:
            self._set_location_context(character, target_context)
            self.character_repo.save(character)

        if target_location is not None and self.world_repo:
            world_after = self._require_world()
            quests = self._world_quests(world_after)
            changed = False
            world_turn = int(getattr(world_after, "current_turn", 0))
            destination_location_id = int(getattr(target_location, "id", 0) or 0)
            for quest in quests.values():
                if not isinstance(quest, dict):
                    continue
                if quest.get("status") != "active":
                    continue
                owner = int(quest.get("owner_character_id", character_id) or character_id)
                if owner != int(character_id):
                    continue
                if str(quest.get("objective_kind", "")).strip().lower() != "travel_to":
                    continue
                try:
                    target_location_id = int(quest.get("objective_target_location_id", 0) or 0)
                except (TypeError, ValueError):
                    target_location_id = 0
                if target_location_id != destination_location_id:
                    continue

                target = max(1, int(quest.get("target", 1) or 1))
                quest["progress"] = target
                quest["status"] = "ready_to_turn_in"
                quest["completed_turn"] = world_turn
                changed = True

            if changed:
                self.world_repo.save(world_after)

        consumed_label = self._consume_travel_prep(character)
        if consumed_label:
            self.character_repo.save(character)

        mode_label = {"road": "road", "stealth": "stealth route", "caravan": "caravan route"}.get(mode, "road")
        pace_label = self._TRAVEL_PACE_LABELS.get(pace, "steady")
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
        message = f"{message} Journey: {estimated_days} day(s) via {mode_label} at a {pace_label} pace."
        exhaustion_level = int(self._survival_state(character).get("travel_exhaustion_level", 0) or 0)
        if exhaustion_level > 0:
            message = f"{message} Exhaustion: {exhaustion_level}/6."
        prep_summary = self._travel_prep_summary(prep_profile)
        if prep_summary:
            message = f"{message} Prep applied: {prep_summary}."
        if consumed_label:
            log_messages.append(f"Travel prep consumed: {consumed_label}.")
        self._recover_party_runtime_state(character, context="travel")
        self.character_repo.save(character)
        return ActionResult(messages=[message, *log_messages], game_over=False)

    def _apply_travel_event(
        self,
        character: Character,
        target_context: str,
        destination_name: str | None,
        travel_mode: str = "road",
        travel_pace: str = "steady",
        prep_profile: dict | None = None,
        destination_biome: str | None = None,
    ) -> str:
        if not self.world_repo:
            return ""
        world = self._require_world()
        mode = self._normalize_travel_mode(travel_mode)
        pace = self._normalize_travel_pace(travel_pace)
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
                "travel_pace": pace,
                "travel_prep": prep_id,
                "destination_biome": str(destination_biome or ""),
            },
        )
        rng = random.Random(seed)
        roll = rng.randint(1, 100)
        mode_shift = {"road": 0, "stealth": -8, "caravan": -12}.get(mode, 0)
        pace_shift = {"cautious": -8, "steady": 0, "hurried": 10}.get(pace, 0)
        heat_pressure = self._faction_heat_pressure(character)
        biome_shift = self._biome_travel_risk_shift(str(destination_biome or ""))
        adjusted_roll = max(
            1,
            min(100, roll + mode_shift + pace_shift + heat_pressure + max(-20, min(8, prep_roll_shift)) + biome_shift),
        )

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

        heated_faction, heat_score = self._dominant_faction_heat(character)
        if heated_faction and heat_score >= 6:
            message = f"{message} Scouts tied to {heated_faction.replace('_', ' ')} shadow your route."

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
        lead_message = self._roll_companion_lead_discovery(
            character,
            world_turn=int(getattr(world, "current_turn", 0)),
            context_key="travel",
            location_name=str(destination_name or "unknown"),
            world_threat=int(getattr(world, "threat_level", 0) or 0),
        )
        if lead_message:
            message = f"{message} {lead_message}".strip()
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
        travel_pace: str = "steady",
        prep_profile: dict | None = None,
    ) -> int:
        if destination is None:
            return 1
        mode = self._normalize_travel_mode(travel_mode)
        pace = self._normalize_travel_pace(travel_pace)
        prep_day_shift = int((prep_profile or {}).get("day_shift", 0))
        source_id = int(getattr(source, "id", 0) or 0)
        destination_id = int(getattr(destination, "id", 0) or 0)
        src_x = float(getattr(source, "x", 0.0) or 0.0)
        src_y = float(getattr(source, "y", 0.0) or 0.0)
        dst_x = float(getattr(destination, "x", 0.0) or 0.0)
        dst_y = float(getattr(destination, "y", 0.0) or 0.0)
        coordinate_distance = math.sqrt((dst_x - src_x) ** 2 + (dst_y - src_y) ** 2)
        id_distance = abs(destination_id - source_id)
        recommended_level = max(1, int(getattr(destination, "recommended_level", 1) or 1))
        biome = str(getattr(destination, "biome", "") or "").lower()

        if coordinate_distance > 0:
            base_days = max(1, int(coordinate_distance / float(self._TRAVEL_SPEED_DIVISOR)))
        else:
            base_days = 1 + min(3, id_distance)
        challenge_days = 1 if recommended_level >= 3 else 0
        biome_days = 1 if any(token in biome for token in ("mountain", "marsh", "swamp", "wild", "forest")) else 0
        mode_days = {"road": 0, "stealth": 1, "caravan": 1}.get(mode, 0)
        pace_days = {"cautious": 1, "steady": 0, "hurried": -1}.get(pace, 0)
        days = base_days + challenge_days + biome_days + mode_days + pace_days + max(-2, min(2, prep_day_shift))
        return max(1, min(9, days))

    def _plan_travel_event_days(
        self,
        *,
        character_id: int,
        destination_id: int,
        destination_name: str,
        travel_mode: str,
        travel_pace: str = "steady",
        estimated_days: int,
        world_turn: int,
        prep_profile: dict | None = None,
    ) -> set[int]:
        mode = self._normalize_travel_mode(travel_mode)
        pace = self._normalize_travel_pace(travel_pace)
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
                "travel_pace": pace,
                "travel_prep": prep_id,
                "estimated_days": int(estimated_days),
                "world_turn": int(world_turn),
            },
        )
        rng = random.Random(seed)
        max_events = min(3, max(0, int(estimated_days) - 1))
        mode_cap_adjust = {"road": 0, "stealth": -1, "caravan": -1}.get(mode, 0)
        pace_cap_adjust = {"cautious": -1, "steady": 0, "hurried": 1}.get(pace, 0)
        max_events = max(0, max_events + mode_cap_adjust + pace_cap_adjust + max(-2, min(1, prep_event_cap_shift)))
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
        self._ensure_persistent_town_npcs(world)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        location_name = self._settlement_display_name(world, location)
        district_tag, landmark_tag = self._town_layer_tags(world=world, location=location)
        immersion = self._world_immersion_state(world, biome_name=str(getattr(location, "biome", "") or ""))
        prep_summary = self._travel_prep_summary(self._active_travel_prep_profile(character))
        npcs = []
        for npc in self._town_npcs_for_world(world):
            disposition = self._get_npc_disposition(world, npc["id"])
            npcs.append(
                to_town_npc_view(
                    npc_id=npc["id"],
                    name=npc["name"],
                    role=str(npc["role"]),
                    temperament=npc["temperament"],
                    relationship=disposition,
                )
            )
        story_lines = self._active_story_seed_town_lines(world)
        memory_lines = self._recent_story_memory_town_lines(world)
        recent_consequences = self._recent_consequence_messages(world)
        phase = str(immersion.get("phase", ""))
        if phase in {"Midnight", "Night"}:
            recent_consequences = [f"Night routine: most merchants close shutters after {phase.lower()}."] + list(recent_consequences)
        elif phase == "Dusk":
            recent_consequences = ["Dusk routine: taverns crowd while traders prepare to close."] + list(recent_consequences)
        if int(getattr(world, "threat_level", 0) or 0) >= 4:
            recent_consequences = ["Tension response: shopkeepers board windows and whisper about flashpoints."] + list(recent_consequences)
        pressure_summary, pressure_lines = self._faction_pressure_display(character)
        cataclysm = self._world_cataclysm_state(world)
        try:
            raw_progress = cataclysm.get("progress", 0)
            cataclysm_progress = max(0, min(100, int(raw_progress if isinstance(raw_progress, (int, float, str)) else 0)))
        except Exception:
            cataclysm_progress = 0
        return to_town_view(
            day=getattr(world, "current_turn", None),
            threat_level=getattr(world, "threat_level", None),
            location_name=location_name,
            npcs=npcs,
            consequences=story_lines + memory_lines + recent_consequences,
            district_tag=district_tag,
            landmark_tag=landmark_tag,
            active_prep_summary=prep_summary,
            pressure_summary=pressure_summary,
            pressure_lines=pressure_lines,
            time_label=str(immersion.get("time_label", "")),
            weather_label=str(immersion.get("weather", "Unknown")),
            cataclysm_active=bool(cataclysm.get("active", False)),
            cataclysm_kind=str(cataclysm.get("kind", "") or ""),
            cataclysm_phase=str(cataclysm.get("phase", "") or ""),
            cataclysm_progress=cataclysm_progress,
            cataclysm_summary=str(cataclysm.get("summary", "") or ""),
        )

    def get_pressure_relief_targets_intent(self, character_id: int) -> list[tuple[str, int]]:
        character = self._require_character(character_id)
        state = self._faction_heat_state(character)
        if not state:
            return []
        ordered = sorted(state.items(), key=lambda item: (-int(item[1]), str(item[0])))
        return [(str(faction_id), int(score)) for faction_id, score in ordered]

    def submit_pressure_relief_intent(self, character_id: int, faction_id: str | None = None) -> ActionResult:
        character = self._require_character(character_id)
        state = self._faction_heat_state(character)
        if not state:
            return ActionResult(messages=["No faction pressure needs attention right now."], game_over=False)

        normalized_faction = str(faction_id or "").strip().lower()
        if normalized_faction and normalized_faction not in state:
            return ActionResult(messages=["That faction is not currently applying pressure."], game_over=False)
        if not normalized_faction:
            normalized_faction, _ = self._dominant_faction_heat(character)
            if not normalized_faction:
                return ActionResult(messages=["No faction pressure needs attention right now."], game_over=False)

        current_heat = int(state.get(normalized_faction, 0) or 0)
        if current_heat <= 0:
            return ActionResult(messages=["That faction's pressure is already calm."], game_over=False)

        relief_cost = int(self._FACTION_HEAT_RELIEF_COST)
        if int(getattr(character, "money", 0) or 0) < relief_cost:
            return ActionResult(messages=[f"You need {relief_cost} gold to lay low and cool tensions."], game_over=False)

        character.money = max(0, int(getattr(character, "money", 0) or 0) - relief_cost)
        self._adjust_faction_heat(character, faction_id=normalized_faction, delta=-int(self._FACTION_HEAT_RELIEF_AMOUNT))
        updated_state = self._faction_heat_state(character)
        next_heat = int(updated_state.get(normalized_faction, 0) or 0)
        heat_delta = int(next_heat - current_heat)

        world_after = None
        if self.world_repo:
            if self.atomic_state_persistor:
                world_after = self.advance_world(ticks=1, persist=False)
            else:
                world_after = self.advance_world(ticks=1)
        world_turn = int(getattr(world_after, "current_turn", 0) or 0)
        if world_turn <= 0 and self.world_repo:
            world_turn = int(getattr(self._require_world(), "current_turn", 0) or 0)

        self._record_faction_heat_event(
            character,
            world_turn=world_turn,
            reason="relief",
            delta_by_faction={normalized_faction: heat_delta},
        )
        arc_message = self._advance_companion_arc(
            character,
            channel="faction",
            world_turn=int(world_turn),
            base_delta=2,
        )

        if self.atomic_state_persistor and self.world_repo and world_after is not None:
            self.atomic_state_persistor(character, world_after)
        else:
            self.character_repo.save(character)

        faction_label = normalized_faction.replace("_", " ").title()
        return ActionResult(
            messages=[
                f"You lay low around {faction_label} contacts.",
                f"Heat: {current_heat} → {next_heat}.",
                f"Spent {relief_cost} gold and one day passes quietly.",
            ] + ([arc_message] if arc_message else []),
            game_over=False,
        )

    def get_npc_interaction_intent(self, character_id: int, npc_id: str) -> NpcInteractionView:
        character = self._require_character(character_id)
        world = self._require_world()
        self._ensure_persistent_town_npcs(world)
        npc = self._find_town_npc(npc_id)
        schedule = self._npc_schedule_snapshot(world, str(npc["id"]))
        disposition = self._get_npc_disposition(world, npc["id"])
        greeting = self._npc_greeting(npc_name=npc["name"], temperament=npc["temperament"], disposition=disposition)
        if not bool(schedule.get("available", True)):
            phase_label = str(schedule.get("phase", "Night") or "Night")
            location_name = str(schedule.get("location", "town") or "town")
            greeting = f"{npc['name']} is off duty during {phase_label.lower()} and can only be found near {location_name}."
            return NpcInteractionView(
                npc_id=npc["id"],
                npc_name=npc["name"],
                role=npc["role"],
                temperament=npc["temperament"],
                relationship=disposition,
                greeting=greeting,
                approaches=[],
            )
        memory_hint = self._story_memory_dialogue_hint(world, npc_id=npc["id"])
        if memory_hint:
            greeting = f"{greeting} {memory_hint}"
        if int(getattr(world, "threat_level", 0) or 0) >= 4:
            greeting = f"{greeting} The unrest has everyone speaking in lower voices."
        if bool(npc.get("is_procedural", False)):
            worksite = str(schedule.get("location", "town") or "town")
            greeting = f"{greeting} {npc['name']} keeps watch over the {str(npc.get('role', 'trade')).lower()} post near {worksite}."
        approaches = ["Friendly", "Direct", "Intimidate"]
        if bool(npc.get("is_procedural", False)):
            approaches.extend(["Persuasion", "Deception", "Intimidation"])
        if npc["id"] == "broker_silas" and self._has_interaction_unlock(character, "intel_leverage"):
            approaches.append("Leverage Intel")
        if npc["id"] == "captain_ren" and self._has_interaction_unlock(character, "captain_favor"):
            approaches.append("Call In Favor")
        dominant_faction, dominant_score = self._dominant_faction_standing(character_id)
        if dominant_faction and dominant_score >= 10:
            approaches.append("Invoke Faction")
        if int(getattr(character, "money", 0) or 0) >= 8:
            approaches.append("Bribe")
        greeting, approaches = self.dialogue_service.contextualize_interaction(
            world=world,
            character=character,
            character_id=int(character_id),
            npc_id=str(npc["id"]),
            greeting=greeting,
            approaches=approaches,
        )
        return NpcInteractionView(
            npc_id=npc["id"],
            npc_name=npc["name"],
            role=npc["role"],
            temperament=npc["temperament"],
            relationship=disposition,
            greeting=greeting,
            approaches=approaches,
        )

    def get_dialogue_session_intent(self, character_id: int, npc_id: str) -> DialogueSessionView:
        interaction = self.get_npc_interaction_intent(character_id, npc_id)
        character = self._require_character(character_id)
        world = self._require_world()
        npc = self._find_town_npc(str(interaction.npc_id))
        session = self.dialogue_service.build_dialogue_session(
            world=world,
            character=character,
            character_id=int(character_id),
            npc_id=str(interaction.npc_id),
            npc_name=str(interaction.npc_name),
            greeting=str(interaction.greeting),
            approaches=list(interaction.approaches or []),
            npc_profile_id=self._npc_dialogue_profile(npc),
        )
        choices = [
            DialogueChoiceView(
                choice_id=str(row.get("choice_id", "")),
                label=str(row.get("label", "")),
                available=bool(row.get("available", False)),
                locked_reason=str(row.get("locked_reason", "")),
            )
            for row in list(session.get("choices", []) or [])
            if isinstance(row, dict)
        ]
        return DialogueSessionView(
            npc_id=str(interaction.npc_id),
            npc_name=str(interaction.npc_name),
            stage_id=str(session.get("stage_id", "opening")),
            greeting=str(session.get("greeting", interaction.greeting)),
            choices=choices,
            challenge_progress=max(0, int(session.get("challenge_progress", 0) or 0)),
            challenge_target=max(1, int(session.get("challenge_target", 3) or 3)),
        )

    def get_shop_view_intent(self, character_id: int) -> ShopView:
        character = self._require_character(character_id)
        price_modifier = self._town_price_modifier(character_id)
        world = self.world_repo.load_default() if self.world_repo else None
        cataclysm = self._world_cataclysm_state(world)
        location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        immersion = self._world_immersion_state(world, biome_name=str(getattr(location, "biome", "") or ""))
        settlement_scale = self._settlement_scale(location)
        scale_price_shift = self._shop_scale_price_shift(settlement_scale)
        local_faction_shift = self._local_faction_trade_shift(character_id, location)
        event_pressure_shift = self._shop_recent_event_pressure_shift(world)
        price_modifier += int(scale_price_shift) + int(local_faction_shift) + int(event_pressure_shift)
        phase = str(immersion.get("phase", ""))
        weather = str(immersion.get("weather", "Unknown"))
        world_turn = int(getattr(world, "current_turn", 0) or 0) if world is not None else 0
        after_hours = phase in {"Midnight", "Night"} and world_turn > 0
        if after_hours:
            price_modifier += 2
        standing_label = "neutral"
        if price_modifier < 0:
            standing_label = "friendly discount"
        elif price_modifier > 0:
            standing_label = "unfriendly surcharge"
        heated_faction, heated_score = self._dominant_faction_heat(character)
        if price_modifier > 0 and heated_faction and heated_score >= 6:
            standing_label = f"{standing_label} ({heated_faction.replace('_', ' ')} pressure)"
        if after_hours:
            standing_label = f"{standing_label}; after-hours premium ({phase.lower()})"
        if weather in {"Storm", "Blizzard"}:
            standing_label = f"{standing_label}; weather scarcity"
        if bool(cataclysm.get("active", False)):
            cataclysm_phase = str(cataclysm.get("phase", "") or "").replace("_", " ")
            standing_label = f"{standing_label}; cataclysm strain ({cataclysm_phase})"
        if settlement_scale == "city":
            standing_label = f"{standing_label}; city trade depth"
        elif settlement_scale == "village":
            standing_label = f"{standing_label}; village scarcity"
        if local_faction_shift < 0:
            standing_label = f"{standing_label}; local faction support"
        elif local_faction_shift > 0:
            standing_label = f"{standing_label}; local faction tolls"
        if event_pressure_shift > 0:
            standing_label = f"{standing_label}; recent unrest"

        dynamic_rows: list[dict] = []
        loader = getattr(self.character_repo, "list_shop_items", None)
        if callable(loader):
            try:
                loaded = loader(character_id=character_id, max_items=self._shop_dynamic_item_limit(settlement_scale, event_pressure_shift))
                if isinstance(loaded, list):
                    dynamic_rows = [row for row in loaded if isinstance(row, dict)]
            except Exception:
                dynamic_rows = []

        items = []
        merged_rows = list(self._SHOP_ITEMS) + dynamic_rows
        after_hours_essentials = {"sturdy_rations", "torch", "rope", "healing_herbs", "antitoxin"}
        cataclysm_essentials = {"sturdy_rations", "torch", "rope", "healing_herbs", "antitoxin", "whetstone"}
        emitted: set[str] = set()
        for row in merged_rows:
            item_id = str(row.get("id", "")).strip()
            if not item_id or item_id in emitted:
                continue
            if settlement_scale == "village" and item_id in {"focus_potion", "iron_longsword"}:
                continue
            if after_hours and item_id not in after_hours_essentials:
                continue
            if bool(cataclysm.get("active", False)) and str(cataclysm.get("phase", "")) in {"map_shrinks", "ruin"}:
                if item_id not in cataclysm_essentials:
                    continue
            if event_pressure_shift >= 2 and item_id not in {"healing_herbs", "sturdy_rations", "torch", "rope", "antitoxin", "whetstone"}:
                continue
            emitted.add(item_id)
            base_price = int(row.get("base_price", 1))
            row_modifier = int(price_modifier)
            if weather in {"Storm", "Blizzard"} and str(item_id) in {"sturdy_rations", "torch", "antitoxin"}:
                row_modifier += 1
            row_modifier += self._cataclysm_item_price_shift(cataclysm=cataclysm, item_id=item_id)
            price = self._bounded_price(base_price, row_modifier)
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

        if after_hours and not items:
            standing_label = f"{standing_label}; shutters closed until morning"
        return to_shop_view(gold=character.money, price_modifier_label=standing_label, items=items)

    @staticmethod
    def _shop_scale_price_shift(settlement_scale: str) -> int:
        normalized = str(settlement_scale or "town").strip().lower()
        if normalized == "city":
            return -1
        if normalized == "village":
            return 1
        return 0

    @staticmethod
    def _shop_dynamic_item_limit(settlement_scale: str, event_pressure_shift: int) -> int:
        normalized = str(settlement_scale or "town").strip().lower()
        if normalized == "city":
            base = 12
        elif normalized == "village":
            base = 5
        else:
            base = 8
        return max(3, int(base) - max(0, int(event_pressure_shift)))

    def _local_faction_trade_shift(self, character_id: int, location: Location | None) -> int:
        if location is None:
            return 0
        local_factions = [
            str(faction_id or "").strip().lower()
            for faction_id in (getattr(location, "factions", []) or [])
            if str(faction_id or "").strip()
        ]
        if not local_factions:
            return 0
        standings = self.faction_standings_intent(character_id)
        if not standings:
            return 0
        local_scores = [int(standings.get(faction_id, 0) or 0) for faction_id in local_factions]
        if not local_scores:
            return 0
        best_local = max(local_scores)
        if best_local >= 10:
            return -1
        if best_local <= -10:
            return 1
        return 0

    @staticmethod
    def _shop_recent_event_pressure_shift(world) -> int:
        if not isinstance(getattr(world, "flags", None), dict):
            return 0
        rows = world.flags.get("consequences", [])
        if not isinstance(rows, list) or not rows:
            return 0
        current_turn = int(getattr(world, "current_turn", 0) or 0)
        severe = 0
        normal = 0
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            row_turn = int(row.get("turn", -10_000) or -10_000)
            if row_turn < current_turn - 8:
                break
            severity = str(row.get("severity", "minor") or "minor").strip().lower()
            if severity in {"high", "critical"}:
                severe += 1
            elif severity == "normal":
                normal += 1
        return min(3, severe + (1 if normal >= 2 else 0))

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
        current_location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        diplomacy_state, diplomacy_changed = self._sync_faction_diplomacy(
            world,
            character=character,
            current_location=current_location,
        )
        if diplomacy_changed and self.world_repo:
            self.world_repo.save(world)
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
        diplomacy_fingerprint = self._diplomacy_fingerprint(diplomacy_state, limit=4)

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
                "diplomacy_fingerprint": diplomacy_fingerprint,
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
        diplomacy_item = self._diplomacy_rumour_item(
            world=world,
            character_id=character_id,
            diplomacy_state=diplomacy_state,
        )
        if diplomacy_item is not None:
            items.append(diplomacy_item)
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
        character = self._require_character(character_id)
        world = self._require_world()
        current_location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        diplomacy_state, diplomacy_changed = self._sync_faction_diplomacy(
            world,
            character=character,
            current_location=current_location,
        )
        world_turn = int(getattr(world, "current_turn", 0))
        changed = self._sync_cataclysm_quest_pressure(world, world_turn=world_turn)
        if (changed or diplomacy_changed) and self.world_repo:
            self.world_repo.save(world)
        quests = self._world_quests(world)
        views: list[QuestStateView] = []
        for quest_id, payload in quests.items():
            if not isinstance(payload, dict):
                continue
            objective_kind = str(payload.get("objective_kind", "kill_any"))
            progress = int(payload.get("progress", 0))
            target = max(1, int(payload.get("target", 1)))
            status = str(payload.get("status", "unknown"))
            urgency_label = self._quest_urgency_label(
                status=status,
                world_turn=world_turn,
                expires_turn=payload.get("expires_turn"),
            )
            diplomacy_suffix = self._diplomacy_quest_urgency_suffix(
                diplomacy_state=diplomacy_state,
                quest_payload=payload,
            )
            if diplomacy_suffix:
                urgency_label = f"{urgency_label} • {diplomacy_suffix}" if urgency_label else diplomacy_suffix
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
                    urgency_label=urgency_label,
                )
            )
        views.sort(key=lambda item: item.quest_id)
        empty_state_hint = (
            "No quest postings yet. Explore nearby zones, advance a day, and check back at the board for new contracts."
        )
        if list(diplomacy_state.get("active_wars", []) or []):
            empty_state_hint = f"{empty_state_hint} Border conflicts may temporarily reduce courier and travel contracts."
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
        self._sync_cataclysm_quest_pressure(world, world_turn=int(getattr(world, "current_turn", 0) or 0))
        quests = self._world_quests(world)
        quest = quests.get(quest_id)
        if not isinstance(quest, dict):
            return ActionResult(messages=["That quest is not available."], game_over=False)
        if quest.get("status") != "available":
            return ActionResult(messages=[f"Quest cannot be accepted right now ({quest.get('status', 'unknown')})."], game_over=False)

        required_rep = max(0, int(quest.get("requires_alliance_reputation", 0) or 0))
        required_count = max(0, int(quest.get("requires_alliance_count", 0) or 0))
        if required_rep > 0 and required_count > 0:
            standings = self.faction_standings_intent(character_id)
            qualified = sum(1 for score in standings.values() if int(score) >= required_rep)
            if qualified < required_count:
                return ActionResult(
                    messages=[
                        f"This bounty requires alliance standing {required_rep}+ with at least {required_count} factions."
                    ],
                    game_over=False,
                )

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
        self._sync_cataclysm_quest_pressure(world, world_turn=int(getattr(world, "current_turn", 0) or 0))
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
        cataclysm_reduction = self._apply_cataclysm_pushback_from_quest(
            world,
            quest_id=str(quest_id),
            quest=quest,
            character_id=int(character_id),
        )
        apex_resolved = self._apply_cataclysm_apex_resolution_from_quest(
            world,
            quest_id=str(quest_id),
            quest=quest,
            character_id=int(character_id),
        )
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
        if cataclysm_reduction > 0:
            messages.append(f"Cataclysm pushback succeeds: doomsday progress -{cataclysm_reduction}%.")
        if apex_resolved:
            messages.append("Apex objective completed: the cataclysm is broken and the world endures.")
        messages.extend(level_messages)
        return ActionResult(messages=messages, game_over=False)

    def submit_social_approach_intent(
        self,
        character_id: int,
        npc_id: str,
        approach: str,
        forced_dc: int | None = None,
        forced_skill: str | None = None,
    ) -> SocialOutcomeView:
        character = self._require_character(character_id)
        world = self._require_world()
        self._ensure_persistent_town_npcs(world)
        npc = self._find_town_npc(npc_id)
        schedule = self._npc_schedule_snapshot(world, str(npc["id"]))
        if not bool(schedule.get("available", True)):
            location_name = str(schedule.get("location", "town") or "town")
            relationship = self._get_npc_disposition(world, npc["id"])
            return SocialOutcomeView(
                npc_id=npc["id"],
                npc_name=npc["name"],
                approach="unavailable",
                success=False,
                roll_total=0,
                target_dc=0,
                relationship_before=relationship,
                relationship_after=relationship,
                messages=[f"{npc['name']} is off duty right now. Try again near {location_name} during daytime."],
            )

        normalized_approach = self.dialogue_service.normalize_approach(approach)
        normalized_forced_skill = self.dialogue_service.normalize_approach(forced_skill or "")
        if normalized_forced_skill in {"persuasion", "intimidation", "deception"}:
            normalized_approach = normalized_forced_skill
        if normalized_approach not in {
            "friendly",
            "direct",
            "intimidate",
            "persuasion",
            "intimidation",
            "deception",
            "leverage intel",
            "call in favor",
            "invoke faction",
            "bribe",
            "urgent appeal",
            "address flashpoint",
            "make amends",
            "leverage rumour",
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
        if normalized_approach == "leverage rumour" and not self.dialogue_service._has_recent_rumour(world, int(character_id)):
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
            "persuasion": "charisma",
            "intimidation": "strength",
            "deception": "charisma",
            "ask about companions": "wisdom",
            "leverage intel": "wisdom",
            "call in favor": "charisma",
            "invoke faction": "charisma",
            "bribe": "charisma",
            "urgent appeal": "charisma",
            "address flashpoint": "wisdom",
            "make amends": "charisma",
            "leverage rumour": "wisdom",
        }[normalized_approach]
        score = int(getattr(character, "attributes", {}).get(skill_attr, 10))
        modifier = (score - 10) // 2
        npc_affinity = self._npc_faction_affinity(world, str(npc["id"]))
        heat_state = self._faction_heat_state(character)
        npc_heat = int(heat_state.get(npc_affinity, 0)) if npc_affinity else 0
        npc_heat_dc_penalty = min(2, max(0, npc_heat // 7))

        dc = 12 + max(0, int(npc["aggression"]) - 4) - max(0, int(npc["openness"]) - 4)
        dc += 2 if disposition_before <= -50 else 0
        dc -= 1 if disposition_before >= 50 else 0
        dc += npc_heat_dc_penalty
        if normalized_approach == "leverage intel" and npc["id"] == "broker_silas":
            dc -= 2
        if normalized_approach == "call in favor" and npc["id"] == "captain_ren":
            dc -= 3
        if normalized_approach == "invoke faction":
            dc -= 2 + max(0, (dominant_score - 10) // 10)
        if normalized_approach == "bribe":
            dc -= 4
        if normalized_approach == "urgent appeal":
            dc -= 1
        if normalized_approach == "address flashpoint":
            if self.dialogue_service._latest_flashpoint(world) is not None:
                dc -= 2
            else:
                dc += 1
        if normalized_approach == "make amends":
            dc += 1
        if normalized_approach == "leverage rumour":
            dc -= 1
        if forced_dc is not None:
            dc = int(forced_dc)
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
        arc_bonus = self._consume_social_momentum_bonus(character)
        roll_total = roll + modifier + int(arc_bonus)
        success = roll_total >= dc

        delta = 8 if success else -6
        if normalized_approach == "intimidate":
            delta = 5 if success else -8
        if normalized_approach == "persuasion":
            delta = 8 if success else -5
        if normalized_approach == "intimidation":
            delta = 5 if success else -8
        if normalized_approach == "deception":
            delta = 6 if success else -6
        if normalized_approach == "leverage intel":
            delta = 6 if success else -4
        if normalized_approach == "call in favor":
            delta = 7 if success else -5
        if normalized_approach == "invoke faction":
            delta = 9 if success else -3
        if normalized_approach == "bribe":
            delta = 10 if success else -2
        if normalized_approach == "urgent appeal":
            delta = 6 if success else -5
        if normalized_approach == "address flashpoint":
            delta = 7 if success else -4
        if normalized_approach == "make amends":
            delta = 9 if success else -3
        if normalized_approach == "leverage rumour":
            delta = 6 if success else -4
        disposition_after = max(-100, min(100, disposition_before + delta))
        self._set_npc_disposition(world, npc["id"], disposition_after)
        if npc_affinity:
            heat_shift = 0
            if not success and normalized_approach in {"intimidate", "intimidation", "invoke faction"}:
                heat_shift = 2
            elif not success:
                heat_shift = 1
            elif success and normalized_approach in {"friendly", "persuasion", "call in favor", "bribe"}:
                heat_shift = -1
            if heat_shift != 0:
                self._adjust_faction_heat(character, faction_id=npc_affinity, delta=heat_shift)
                self.character_repo.save(character)
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

        dialogue_notes = self.dialogue_service.record_outcome(
            world=world,
            character=character,
            character_id=int(character_id),
            npc_id=str(npc["id"]),
            approach=normalized_approach,
            success=bool(success),
            world_turn=int(world_turn),
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
                target_count = max(1, int(quest.get("target", 1) or 1))
                current_progress = max(0, int(quest.get("progress", 0) or 0))
                advanced_progress = min(target_count, current_progress + 1)
                quest["progress"] = advanced_progress
                if advanced_progress >= target_count:
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

        if success:
            mapped_companion_id = str(self._NPC_COMPANION_MAP.get(str(npc.get("id", "")), "")).strip().lower()
            if mapped_companion_id and mapped_companion_id in self._COMPANION_TEMPLATES:
                unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
                if mapped_companion_id not in unlocked_ids:
                    unlocked_ids.add(mapped_companion_id)
                    self._save_unlocked_companion_ids(character, unlocked_ids)
                    self._ensure_companion_arc_rows(character, unlocked_ids)
                    companion_name = str(
                        self._COMPANION_TEMPLATES.get(mapped_companion_id, {}).get(
                            "name", mapped_companion_id.replace("_", " ").title()
                        )
                    )
                    story_messages.append(f"{companion_name} is willing to join your roster.")
                    self.character_repo.save(character)

        arc_message = self._advance_companion_arc(
            character,
            channel="social",
            world_turn=int(world_turn),
            base_delta=1 if success else 0,
        )
        if arc_message:
            story_messages.append(arc_message)

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
                f"Check: d20 + {modifier} + {int(arc_bonus)} = {roll_total} vs DC {dc}",
                f"Relationship: {disposition_before} → {disposition_after}",
            ]
            + (
                [f"Pressure: {npc_affinity.replace('_', ' ')} heat {npc_heat} (+{npc_heat_dc_penalty} DC)."]
                if npc_affinity and npc_heat_dc_penalty > 0
                else []
            )
            + ([approach_note] if approach_note else [])
            + dialogue_notes
            + story_messages,
        )

    def submit_dialogue_choice_intent(self, character_id: int, npc_id: str, choice_id: str) -> SocialOutcomeView:
        interaction = self.get_npc_interaction_intent(character_id, npc_id)
        character = self._require_character(character_id)
        world = self._require_world()
        npc = self._find_town_npc(str(interaction.npc_id))
        resolved = self.dialogue_service.resolve_dialogue_choice(
            world=world,
            character=character,
            character_id=int(character_id),
            npc_id=str(interaction.npc_id),
            npc_name=str(interaction.npc_name),
            greeting=str(interaction.greeting),
            approaches=list(interaction.approaches or []),
            choice_id=str(choice_id),
            npc_profile_id=self._npc_dialogue_profile(npc),
        )
        skill_check = resolved.get("skill_check", {}) if isinstance(resolved.get("skill_check", {}), dict) else {}
        forced_dc = None
        forced_skill = ""
        if skill_check:
            try:
                forced_dc = int(skill_check.get("dc", 12) or 12)
            except Exception:
                forced_dc = None
            forced_skill = str(skill_check.get("skill", "")).strip().lower()

        outcome = self.submit_social_approach_intent(
            character_id=character_id,
            npc_id=npc_id,
            approach=str(resolved.get("approach", "direct")),
            forced_dc=forced_dc,
            forced_skill=forced_skill,
        )
        if not bool(resolved.get("accepted", False)):
            outcome.messages = [str(resolved.get("reason", "Choice unavailable.")), *list(outcome.messages or [])]
        else:
            if skill_check:
                skill_label = str(skill_check.get("skill", "check")).strip().title()
                outcome.messages = [
                    f"Skill check: {skill_label} ({outcome.roll_total} vs DC {outcome.target_dc}).",
                    *list(outcome.messages or []),
                ]
            response = str(resolved.get("response", "")).strip()
            if response:
                outcome.messages = [response, *list(outcome.messages or [])]
            if skill_check:
                world_after_branch = self._require_world()
                character_after_branch = self._require_character(character_id)
                branch = self.dialogue_service.apply_skill_check_branch(
                    world=world_after_branch,
                    character=character_after_branch,
                    npc_id=str(npc_id),
                    success=bool(outcome.success),
                    branch={row_key: row_value for row_key, row_value in skill_check.items()},
                )
                branch_response = str(branch.get("response", "")).strip()
                if branch_response:
                    outcome.messages = [branch_response, *list(outcome.messages or [])]
                branch_note = str(branch.get("note", "")).strip()
                if branch_note:
                    outcome.messages = [*list(outcome.messages or []), branch_note]
                self.character_repo.save(character_after_branch)
                if self.world_repo:
                    self.world_repo.save(world_after_branch)
            effects = resolved.get("effects", [])
            if isinstance(effects, list) and effects:
                world_after = self._require_world()
                character_after = self._require_character(character_id)
                effect_notes = self._apply_dialogue_choice_effects(
                    character=character_after,
                    world=world_after,
                    npc_id=str(npc_id),
                    success=bool(outcome.success),
                    effects=[row for row in effects if isinstance(row, dict)],
                )
                if effect_notes:
                    outcome.messages = [*list(outcome.messages or []), *effect_notes]
                self.character_repo.save(character_after)
                if self.world_repo:
                    self.world_repo.save(world_after)
        return outcome

    def _apply_dialogue_choice_effects(
        self,
        *,
        character: Character,
        world,
        npc_id: str,
        success: bool,
        effects: list[dict],
    ) -> list[str]:
        notes: list[str] = []
        world_turn = int(getattr(world, "current_turn", 0) or 0)
        total_delta: dict[str, int] = {}

        for row in effects:
            kind = str(row.get("kind", "")).strip().lower()
            trigger = str(row.get("on", "success")).strip().lower() or "success"
            should_apply = trigger == "always" or (trigger == "success" and bool(success)) or (trigger == "failure" and not bool(success))
            if not should_apply:
                continue

            if kind == "faction_heat_delta":
                faction_id = str(row.get("faction_id", "")).strip().lower()
                if not faction_id:
                    continue
                try:
                    delta = int(row.get("delta", 0) or 0)
                except Exception:
                    continue
                if delta == 0:
                    continue
                self._adjust_faction_heat(character, faction_id=faction_id, delta=delta)
                total_delta[faction_id] = int(total_delta.get(faction_id, 0) or 0) + int(delta)
                sign = "+" if delta > 0 else ""
                notes.append(f"Pressure shift: {faction_id.replace('_', ' ')} {sign}{delta}.")
                continue

            if kind == "narrative_tension_delta":
                try:
                    delta = int(row.get("delta", 0) or 0)
                except Exception:
                    continue
                if delta == 0:
                    continue
                narrative = self._world_narrative_flags(world)
                current_tension = int(narrative.get("tension_level", 0) or 0)
                next_tension = max(0, min(100, current_tension + delta))
                narrative["tension_level"] = int(next_tension)
                shift = int(next_tension) - int(current_tension)
                if shift != 0:
                    sign = "+" if shift > 0 else ""
                    notes.append(f"Tension shift: {sign}{shift} (now {next_tension}).")
                continue

            if kind == "story_seed_state":
                active_seed = self._active_story_seed(world)
                if not isinstance(active_seed, dict):
                    continue
                target_kind = str(row.get("seed_kind", "")).strip().lower()
                if target_kind and str(active_seed.get("kind", "")).strip().lower() != target_kind:
                    continue

                changed = False
                status = str(row.get("status", "")).strip().lower()
                if status in {"active", "simmering", "escalated", "resolved"}:
                    if str(active_seed.get("status", "")).strip().lower() != status:
                        active_seed["status"] = status
                        changed = True
                    if status == "resolved":
                        active_seed["resolved_by"] = "dialogue_effect"
                        active_seed["resolved_turn"] = world_turn

                escalation_stage = str(row.get("escalation_stage", "")).strip().lower()
                if escalation_stage:
                    if str(active_seed.get("escalation_stage", "")).strip().lower() != escalation_stage:
                        active_seed["escalation_stage"] = escalation_stage
                        changed = True

                if changed:
                    active_seed["last_update_turn"] = world_turn
                    status_label = str(active_seed.get("status", "active")).replace("_", " ")
                    stage_label = str(active_seed.get("escalation_stage", "")).replace("_", " ")
                    summary = f"Story seed state shift: {status_label}"
                    if stage_label:
                        summary = f"{summary} ({stage_label})"
                    notes.append(summary)
                continue

            if kind == "consequence":
                message = str(row.get("message", "")).strip()
                if not message:
                    continue
                severity = str(row.get("severity", "normal") or "normal")
                consequence_kind = str(row.get("consequence_kind", "dialogue_choice") or "dialogue_choice")
                self._append_consequence(
                    world,
                    kind=consequence_kind,
                    message=message,
                    severity=severity,
                    turn=world_turn,
                )
                notes.append(message)

        if total_delta:
            self._record_faction_heat_event(
                character,
                world_turn=world_turn,
                reason=f"dialogue:{str(npc_id or '').strip().lower() or 'npc'}",
                delta_by_faction=total_delta,
            )

        return notes

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

    def _apply_faction_encounter_package(
        self,
        plan: EncounterPlan,
        *,
        faction_bias: str | None,
        character_id: int,
        world_turn: int,
        location_id: int,
    ) -> None:
        faction_id = str(faction_bias or "").strip().lower()
        if not faction_id:
            return
        package = self._FACTION_ENCOUNTER_PACKAGES.get(faction_id)
        if not isinstance(package, dict):
            return
        hazard_name = str(package.get("hazard", "") or "").strip()
        if not hazard_name:
            return

        existing_hazards = [str(item).strip().lower() for item in list(getattr(plan, "hazards", []) or []) if str(item).strip()]
        if hazard_name.lower() in existing_hazards:
            return

        seed = derive_seed(
            namespace="encounter.faction_package",
            context={
                "character_id": int(character_id),
                "world_turn": int(world_turn),
                "location_id": int(location_id),
                "faction": faction_id,
                "enemy_count": len(list(getattr(plan, "enemies", []) or [])),
                "hazard_count": len(existing_hazards),
            },
        )
        roll = int(seed) % 100
        threshold = 85 if not existing_hazards else 65
        if roll >= threshold:
            return

        plan.hazards = [*list(getattr(plan, "hazards", []) or []), hazard_name]

    def save_character_state(self, character: Character) -> None:
        self.character_repo.save(character)

    def create_snapshot_intent(self, label: str | None = None) -> dict[str, object]:
        now_ms = int(time.time() * 1000)
        world_turn = 0
        if self.world_repo:
            world = self.world_repo.load_default()
            world_turn = int(getattr(world, "current_turn", 0) if world is not None else 0)

        snapshot_id = f"snapshot-{now_ms}-{len(self._snapshots) + 1}"
        record = {
            "snapshot_id": snapshot_id,
            "label": str(label or "").strip() or f"Turn {world_turn}",
            "captured_at_epoch_ms": now_ms,
            "world_turn": world_turn,
            "state": self._capture_snapshot_state(),
        }
        self._snapshots.append(record)
        if len(self._snapshots) > self._snapshot_limit:
            del self._snapshots[:-self._snapshot_limit]

        return {
            "snapshot_id": snapshot_id,
            "label": record["label"],
            "captured_at_epoch_ms": now_ms,
            "world_turn": world_turn,
        }

    def list_snapshots_intent(self) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        for row in reversed(self._snapshots):
            captured_at = self._coerce_int(row.get("captured_at_epoch_ms"), default=0)
            world_turn = self._coerce_int(row.get("world_turn"), default=0)
            output.append(
                {
                    "snapshot_id": str(row.get("snapshot_id", "")),
                    "label": str(row.get("label", "")),
                    "captured_at_epoch_ms": captured_at,
                    "world_turn": world_turn,
                }
            )
        return output

    def load_snapshot_intent(self, snapshot_id: str) -> ActionResult:
        target = str(snapshot_id or "").strip()
        record = next((row for row in self._snapshots if str(row.get("snapshot_id", "")) == target), None)
        if record is None:
            return ActionResult(messages=[f"Snapshot not found: {target}"], game_over=False)

        state = record.get("state")
        if not isinstance(state, dict):
            return ActionResult(messages=[f"Snapshot payload is invalid: {target}"], game_over=False)

        try:
            self._restore_snapshot_state(state)
        except Exception as exc:
            return ActionResult(messages=[f"Failed to load snapshot {target}: {exc}"], game_over=False)

        loaded_turn = self._coerce_int(record.get("world_turn"), default=0)

        return ActionResult(
            messages=[
                f"Snapshot loaded: {str(record.get('label', target))} (turn {loaded_turn})."
            ],
            game_over=False,
        )

    def encounter_intro_intent(self, enemy: Entity, character_id: int | None = None) -> str:
        try:
            intro = self.encounter_intro_builder(enemy)
        except Exception:
            intro = random_intro(enemy)
        text = (intro or "").strip()
        message = text or random_intro(enemy)
        if character_id is None:
            return message
        character = self.character_repo.get(int(character_id)) if self.character_repo else None
        if character is None:
            return message
        hint = self._codex_bestiary_hint(character, enemy)
        if not hint:
            return message
        return f"{message} {hint}".strip()

    def _codex_bestiary_hint(self, character: Character, enemy: Entity) -> str:
        codex = self._codex_state(character)
        enemy_name = str(getattr(enemy, "name", "") or "").strip().lower().replace(" ", "_")
        if not enemy_name:
            return ""
        key = f"bestiary:{enemy_name}"
        row = codex.get(key)
        if not isinstance(row, dict):
            return "Codex: Unknown target profile."
        raw_discoveries = row.get("discoveries", 0)
        if isinstance(raw_discoveries, (int, float, str, bool)):
            try:
                discoveries = int(raw_discoveries)
            except (TypeError, ValueError):
                discoveries = 0
        else:
            discoveries = 0
        if discoveries <= 1:
            return "Codex: Unknown profile — collect more encounters."
        if discoveries == 2:
            ac = int(getattr(enemy, "armour_class", 10) or 10)
            return f"Codex: Observed profile — estimated armor around {ac}."
        level = int(getattr(enemy, "level", 1) or 1)
        faction = str(getattr(enemy, "faction_id", "unaffiliated") or "unaffiliated").replace("_", " ")
        return f"Codex: Known profile — level {level}, commonly tied to {faction}."

    def combat_player_stats_intent(self, player: Character) -> dict:
        if not self.combat_service:
            return {}
        return self.combat_service.derive_player_stats(player)

    def _scene_with_world_weather(self, player: Character, scene: Optional[dict]) -> dict:
        scene_ctx = dict(scene or {})
        location = self.location_repo.get(player.location_id) if self.location_repo and player.location_id is not None else None
        biome_name = str(getattr(location, "biome", "") or "")
        world = self.world_repo.load_default() if self.world_repo else None
        immersion = self._world_immersion_state(world, biome_name=biome_name)
        if not str(scene_ctx.get("weather", "") or "").strip():
            scene_ctx["weather"] = str(immersion.get("weather", "Unknown"))
        if not str(scene_ctx.get("terrain", "") or "").strip():
            scene_ctx["terrain"] = str(biome_name or "open")
        return scene_ctx

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
        scene_ctx = self._scene_with_world_weather(player, scene)
        seed = derive_seed(
            namespace="combat.resolve",
            context={
                "player_id": player.id,
                "enemy_id": enemy.id,
                "world_turn": world_turn,
                "distance": scene_ctx.get("distance", "close"),
                "terrain": scene_ctx.get("terrain", "open"),
                "surprise": scene_ctx.get("surprise", "none"),
                "weather": scene_ctx.get("weather", "Unknown"),
            },
        )
        self.combat_service.set_seed(seed)
        return self.combat_service.fight_turn_based(
            player,
            enemy,
            choose_action,
            scene=scene_ctx,
        )

    def combat_resolve_party_intent(
        self,
        player: Character,
        enemies: list[Entity],
        choose_action: Callable[[list[str], Character, Entity, int, dict], tuple[str, Optional[str]] | str],
        choose_target: Optional[Callable] = None,
        evaluate_ai_action: Optional[Callable] = None,
        scene: Optional[dict] = None,
    ):
        if not self.combat_service:
            raise RuntimeError("Combat service is unavailable.")

        world_turn = 0
        if self.world_repo:
            world = self.world_repo.load_default()
            world_turn = getattr(world, "current_turn", 0) if world else 0
        else:
            world = None

        scene_ctx = self._scene_with_world_weather(player, scene)
        party_allies = [player, *self._active_party_companions(player)]
        reinforcement_note = ""
        working_enemies = list(enemies or [])
        if world is not None:
            reinforcement_note, working_enemies = self._apply_mid_combat_reinforcement_hook(
                player=player,
                enemies=working_enemies,
                world=world,
                world_turn=int(world_turn),
                scene_ctx=scene_ctx,
            )
        seed = derive_seed(
            namespace="combat.resolve.party",
            context={
                "player_id": player.id,
                "enemy_ids": [int(getattr(row, "id", 0) or 0) for row in working_enemies],
                "party_ids": [int(getattr(row, "id", 0) or 0) for row in party_allies],
                "world_turn": world_turn,
                "distance": scene_ctx.get("distance", "close"),
                "terrain": scene_ctx.get("terrain", "open"),
                "surprise": scene_ctx.get("surprise", "none"),
                "weather": scene_ctx.get("weather", "Unknown"),
            },
        )
        self.combat_service.set_seed(seed)
        result = self.combat_service.fight_party_turn_based(
            allies=party_allies,
            enemies=working_enemies,
            choose_action=choose_action,
            choose_target=choose_target,
            evaluate_ai_action=evaluate_ai_action,
            scene=scene_ctx,
        )
        if reinforcement_note:
            self._append_party_combat_log(result, reinforcement_note)
        self._persist_party_runtime_state(player, result.allies)
        lead = next(
            (
                ally
                for ally in result.allies
                if int(getattr(ally, "id", 0) or 0) == int(getattr(player, "id", 0) or 0)
            ),
            None,
        )
        if lead is not None and isinstance(getattr(lead, "flags", None), dict):
            lead.flags["party_runtime_state"] = dict((getattr(player, "flags", {}) or {}).get("party_runtime_state", {}))
        if world is not None:
            enemy_factions = [
                str(getattr(row, "faction_id", "") or "").strip().lower()
                for row in list(working_enemies or [])
                if str(getattr(row, "faction_id", "") or "").strip()
            ]
            if self._apply_post_combat_morale_consequence(
                world=world,
                character_id=int(getattr(player, "id", 0) or 0),
                world_turn=int(world_turn),
                allies_won=bool(getattr(result, "allies_won", False)),
                fled=bool(getattr(result, "fled", False)),
                enemy_factions=enemy_factions,
                context_key="party",
            ) and self.world_repo:
                self.world_repo.save(world)
            retreat_bargain_note = self._apply_mid_combat_retreat_bargaining_hook(
                character=player,
                world=world,
                world_turn=int(world_turn),
                enemy_factions=enemy_factions,
                fled=bool(getattr(result, "fled", False)),
                context_key="party",
            )
            if retreat_bargain_note:
                self._append_party_combat_log(result, retreat_bargain_note)
                self.character_repo.save(player)
                if self.world_repo:
                    self.world_repo.save(world)
        return result

    @staticmethod
    def _append_party_combat_log(result, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        try:
            from rpg.application.services.combat_service import CombatLogEntry

            entry = CombatLogEntry(text=text)
        except Exception:
            return
        log_rows = getattr(result, "log", None)
        if isinstance(log_rows, list):
            log_rows.append(entry)

    def _apply_mid_combat_reinforcement_hook(
        self,
        *,
        player: Character,
        enemies: list[Entity],
        world,
        world_turn: int,
        scene_ctx: dict,
    ) -> tuple[str, list[Entity]]:
        if not enemies:
            return "", list(enemies)
        if len(enemies) >= 4:
            return "", list(enemies)

        lead_faction = ""
        for enemy in enemies:
            faction_id = str(getattr(enemy, "faction_id", "") or "").strip().lower()
            if faction_id:
                lead_faction = faction_id
                break
        if not lead_faction:
            return "", list(enemies)

        package = self._FACTION_ENCOUNTER_PACKAGES.get(lead_faction)
        if not isinstance(package, dict):
            return "", list(enemies)

        threat = int(getattr(world, "threat_level", 0) or 0)
        tension = int(self.dialogue_service.tension_level(world))
        if threat < 3 and tension < 60:
            return "", list(enemies)

        seed = derive_seed(
            namespace="combat.mid.reinforcement",
            context={
                "player_id": int(getattr(player, "id", 0) or 0),
                "enemy_ids": [int(getattr(row, "id", 0) or 0) for row in enemies],
                "enemy_faction": lead_faction,
                "world_turn": int(world_turn),
                "threat": int(threat),
                "tension": int(tension),
                "distance": str(scene_ctx.get("distance", "close")),
                "terrain": str(scene_ctx.get("terrain", "open")),
            },
        )
        chance = min(45, 8 + (threat * 3) + max(0, (tension - 50) // 5))
        if int(seed) % 100 >= chance:
            return "", list(enemies)

        anchor = enemies[-1]
        reinforcement_id = -int((int(world_turn) + 1) * 1000 + len(enemies) * 17 + abs(int(getattr(anchor, "id", 0) or 0)))
        reinforcement_attack_min = max(1, int(getattr(anchor, "attack_min", 1) or 1))
        reinforcement_attack_max = max(reinforcement_attack_min, int(getattr(anchor, "attack_max", 2) or 2) - 1)
        reinforcement = Entity(
            id=reinforcement_id,
            name=f"{str(getattr(anchor, 'name', 'Enemy') or 'Enemy')} Reinforcement",
            level=max(1, int(getattr(anchor, "level", 1) or 1)),
            hp=max(4, int(int(getattr(anchor, "hp_max", 6) or 6) * 0.7)),
            hp_current=max(4, int(int(getattr(anchor, "hp_max", 6) or 6) * 0.7)),
            hp_max=max(4, int(int(getattr(anchor, "hp_max", 6) or 6) * 0.7)),
            armour_class=max(8, int(getattr(anchor, "armour_class", 10) or 10) - 1),
            attack_bonus=max(1, int(getattr(anchor, "attack_bonus", 2) or 2) - 1),
            damage_die=str(getattr(anchor, "damage_die", "d4") or "d4"),
            attack_min=reinforcement_attack_min,
            attack_max=reinforcement_attack_max,
            faction_id=lead_faction,
            kind=str(getattr(anchor, "kind", "beast") or "beast"),
            tags=list(getattr(anchor, "tags", []) or []),
        )
        return (
            f"Reinforcements arrive for {lead_faction.replace('_', ' ')} forces.",
            [*list(enemies), reinforcement],
        )

    def _apply_mid_combat_retreat_bargaining_hook(
        self,
        *,
        character: Character,
        world,
        world_turn: int,
        enemy_factions: list[str],
        fled: bool,
        context_key: str,
    ) -> str:
        if not bool(fled):
            return ""
        if int(getattr(character, "money", 0) or 0) < 5:
            return ""

        normalized_factions = sorted({str(item).strip().lower() for item in enemy_factions if str(item).strip()})
        if not normalized_factions:
            return ""

        attributes = getattr(character, "attributes", {}) if isinstance(getattr(character, "attributes", None), dict) else {}
        charisma = int(attributes.get("charisma", 10) or 10)
        charisma_mod = (charisma - 10) // 2
        seed = derive_seed(
            namespace="combat.mid.retreat_bargain",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "world_turn": int(world_turn),
                "enemy_factions": tuple(normalized_factions),
                "charisma": int(charisma),
                "context": str(context_key or "party"),
            },
        )
        roll_total = (int(seed) % 20) + 1 + int(charisma_mod)
        dc = 12 + max(0, min(3, len(normalized_factions) - 1))
        dominant_faction = normalized_factions[0]

        if int(roll_total) >= int(dc):
            character.money = max(0, int(getattr(character, "money", 0) or 0) - 5)
            world.threat_level = max(0, int(getattr(world, "threat_level", 0) or 0) - 1)
            self._adjust_faction_heat(character, faction_id=dominant_faction, delta=-1)
            self._record_faction_heat_event(
                character,
                world_turn=int(world_turn),
                reason="combat_retreat_bargain",
                delta_by_faction={dominant_faction: -1},
            )
            self._append_consequence(
                world,
                kind="combat_retreat_bargain",
                message=f"You bribe local runners and escape cleanly from {dominant_faction.replace('_', ' ')} pursuit.",
                severity="low",
                turn=int(world_turn),
            )
            return f"Retreat bargain succeeds ({roll_total} vs DC {dc}); -5 gold, threat -1."

        world.threat_level = min(20, int(getattr(world, "threat_level", 0) or 0) + 1)
        self._append_consequence(
            world,
            kind="combat_retreat_bargain_failed",
            message="Retreat bargaining fails; your route leaks and local pressure increases.",
            severity="normal",
            turn=int(world_turn),
        )
        return f"Retreat bargain fails ({roll_total} vs DC {dc}); threat +1."

    def _unlocked_companion_ids(self, character: Character, *, persist_defaults: bool = False) -> set[str]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags

        raw_unlocked = flags.get("unlocked_companions")
        if isinstance(raw_unlocked, list):
            return {
                str(value or "").strip().lower()
                for value in raw_unlocked
                if str(value or "").strip().lower() in self._COMPANION_TEMPLATES
            }

        defaults: set[str] = set()
        active_party = flags.get("active_party", [])
        if isinstance(active_party, list):
            defaults.update(
                str(value or "").strip().lower()
                for value in active_party
                if str(value or "").strip().lower() in self._COMPANION_TEMPLATES
            )

        if persist_defaults:
            ordered_defaults = [key for key in self._COMPANION_TEMPLATES if key in defaults]
            flags["unlocked_companions"] = ordered_defaults
        return defaults

    def _save_unlocked_companion_ids(self, character: Character, unlocked_ids: set[str]) -> None:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["unlocked_companions"] = [
            companion_id
            for companion_id in self._COMPANION_TEMPLATES
            if companion_id in unlocked_ids
        ]

    @staticmethod
    def _companion_arc_state(character: Character) -> dict[str, dict[str, int | str]]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        raw = flags.setdefault("companion_arcs", {})
        if not isinstance(raw, dict):
            raw = {}
            flags["companion_arcs"] = raw
        normalized: dict[str, dict[str, int | str]] = {}
        for key, value in raw.items():
            companion_id = str(key or "").strip().lower()
            if not companion_id or not isinstance(value, dict):
                continue
            try:
                progress = int(value.get("progress", 0) or 0)
            except Exception:
                progress = 0
            try:
                trust = int(value.get("trust", 0) or 0)
            except Exception:
                trust = 0
            normalized[companion_id] = {
                "progress": progress,
                "trust": trust,
                "stage": str(value.get("stage", "unknown") or "unknown"),
            }
        flags["companion_arcs"] = normalized
        return normalized

    @staticmethod
    def _companion_arc_history(character: Character) -> list[dict]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        rows = flags.setdefault("companion_arc_history", [])
        if not isinstance(rows, list):
            rows = []
            flags["companion_arc_history"] = rows
        return rows

    @classmethod
    def _companion_arc_stage(cls, progress: int) -> str:
        value = max(0, min(cls._COMPANION_ARC_MAX, int(progress)))
        if value >= 75:
            return "bonded"
        if value >= 45:
            return "tested"
        if value >= 20:
            return "warming"
        return "intro"

    def _ensure_companion_arc_rows(self, character: Character, unlocked_ids: set[str]) -> None:
        arcs = self._companion_arc_state(character)
        for companion_id in unlocked_ids:
            template = self._COMPANION_TEMPLATES.get(companion_id, {})
            if bool(template.get("default_unlocked", False)):
                continue
            if companion_id not in arcs:
                arcs[companion_id] = {
                    "progress": 5,
                    "trust": 5,
                    "stage": "intro",
                }

    def _record_companion_arc_event(
        self,
        character: Character,
        *,
        companion_id: str,
        world_turn: int,
        channel: str,
        delta: int,
    ) -> None:
        rows = self._companion_arc_history(character)
        rows.append(
            {
                "companion_id": str(companion_id),
                "turn": int(world_turn),
                "channel": str(channel),
                "delta": int(delta),
            }
        )
        if len(rows) > self._COMPANION_ARC_HISTORY_MAX:
            del rows[:-self._COMPANION_ARC_HISTORY_MAX]

    def _advance_companion_arc(
        self,
        character: Character,
        *,
        channel: str,
        world_turn: int,
        base_delta: int,
    ) -> str:
        delta_value = int(base_delta)
        if delta_value == 0:
            return ""
        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        self._ensure_companion_arc_rows(character, unlocked_ids)
        arcs = self._companion_arc_state(character)
        candidates = [companion_id for companion_id in sorted(arcs.keys()) if companion_id in unlocked_ids]
        if not candidates:
            return ""

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        nonce_map = flags.setdefault("companion_arc_nonce", {})
        if not isinstance(nonce_map, dict):
            nonce_map = {}
            flags["companion_arc_nonce"] = nonce_map
        nonce_key = f"{str(channel)}:{int(world_turn)}"
        nonce = int(nonce_map.get(nonce_key, 0) or 0) + 1
        nonce_map[nonce_key] = nonce

        seed = derive_seed(
            namespace="companion.arc.progress",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "channel": str(channel),
                "world_turn": int(world_turn),
                "nonce": int(nonce),
                "candidates": tuple(candidates),
            },
        )
        target_id = candidates[int(seed) % len(candidates)]
        row = arcs.get(target_id, {})
        current_progress = int(row.get("progress", 0) or 0)
        current_trust = int(row.get("trust", 0) or 0)
        prior_stage = str(row.get("stage", self._companion_arc_stage(current_progress)) or self._companion_arc_stage(current_progress)).strip().lower()
        next_progress = max(0, min(self._COMPANION_ARC_MAX, current_progress + delta_value))
        trust_shift = 1 if delta_value > 0 else -1
        next_trust = max(0, min(self._COMPANION_ARC_MAX, current_trust + trust_shift))
        stage = self._companion_arc_stage(next_progress)
        arcs[target_id] = {
            "progress": next_progress,
            "trust": next_trust,
            "stage": stage,
        }
        self._record_companion_arc_event(
            character,
            companion_id=target_id,
            world_turn=int(world_turn),
            channel=str(channel),
            delta=int(next_progress - current_progress),
        )

        name = str(self._COMPANION_TEMPLATES.get(target_id, {}).get("name", target_id.replace("_", " ").title()))
        if next_progress == current_progress:
            return ""
        direction = "deepens" if next_progress > current_progress else "frays"
        bonus_notes = self._apply_companion_arc_trigger_effects(
            character,
            companion_id=target_id,
            channel=str(channel),
            prior_stage=prior_stage,
            next_stage=stage,
            delta_value=int(next_progress - current_progress),
        )
        return " ".join(
            [
                f"{name} bond {direction} ({current_progress} -> {next_progress}).",
                *[note for note in bonus_notes if str(note).strip()],
            ]
        ).strip()

    def _apply_companion_arc_trigger_effects(
        self,
        character: Character,
        *,
        companion_id: str,
        channel: str,
        prior_stage: str,
        next_stage: str,
        delta_value: int,
    ) -> list[str]:
        notes: list[str] = []
        unlocks = self._interaction_unlocks(character)
        normalized_companion = str(companion_id or "").strip().lower()
        normalized_channel = str(channel or "").strip().lower()
        previous = str(prior_stage or "intro").strip().lower()
        current = str(next_stage or "intro").strip().lower()

        if previous != current and current in {"warming", "tested", "bonded"}:
            unlock_key = f"companion_arc_stage:{normalized_companion}:{current}"
            if not bool(unlocks.get(unlock_key)):
                unlocks[unlock_key] = True
                notes.append(f"Arc unlock gained: {current.title()} insights.")

        if int(delta_value) <= 0:
            return notes

        if normalized_channel == "explore":
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            current_surprise = str(flags.get("next_explore_surprise", "") or "").strip().lower()
            if current_surprise != "player":
                flags["next_explore_surprise"] = "player"
                notes.append("Companion scouting grants player surprise for the next explore encounter.")
        elif normalized_channel == "social":
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            effects = flags.setdefault("companion_arc_effects", {})
            if not isinstance(effects, dict):
                effects = {}
                flags["companion_arc_effects"] = effects
            charges = max(0, int(effects.get("social_momentum", 0) or 0))
            next_charges = min(3, charges + 1)
            effects["social_momentum"] = next_charges
            if next_charges > charges:
                notes.append("Companion momentum: your next social check gains +1.")
        elif normalized_channel == "faction":
            faction_id, faction_score = self._dominant_faction_heat(character)
            if faction_id and int(faction_score) > 0:
                self._adjust_faction_heat(character, faction_id=faction_id, delta=-1)
                notes.append(f"Companion mediation cools {faction_id.replace('_', ' ')} pressure by 1.")

        return notes

    @staticmethod
    def _consume_social_momentum_bonus(character: Character) -> int:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return 0
        effects = flags.get("companion_arc_effects", {})
        if not isinstance(effects, dict):
            return 0
        charges = max(0, int(effects.get("social_momentum", 0) or 0))
        if charges <= 0:
            return 0
        effects["social_momentum"] = max(0, charges - 1)
        return 1

    def _companion_arc_lines(self, character: Character) -> list[str]:
        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        arcs = self._companion_arc_state(character)
        outcomes = self._companion_arc_outcomes(character)
        rare_ids = [companion_id for companion_id in sorted(arcs.keys()) if companion_id in unlocked_ids]
        lines: list[str] = []
        for companion_id in rare_ids[:4]:
            row = arcs.get(companion_id, {})
            name = str(self._COMPANION_TEMPLATES.get(companion_id, {}).get("name", companion_id.replace("_", " ").title()))
            outcome = str(outcomes.get(companion_id, "") or "").strip().lower()
            if outcome == "oath":
                outcome_label = "Oathbound"
            elif outcome == "distance":
                outcome_label = "Distant"
            elif str(row.get("stage", "")).strip().lower() == "bonded":
                outcome_label = "Choice Available"
            else:
                outcome_label = "Unresolved"
            lines.append(
                f"- {name}: Arc {int(row.get('progress', 0) or 0)}/100, Trust {int(row.get('trust', 0) or 0)}, Stage {str(row.get('stage', 'intro')).title()}, Outcome {outcome_label}"
            )
        return lines

    @staticmethod
    def _companion_arc_outcomes(character: Character) -> dict[str, str]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        raw = flags.setdefault("companion_arc_outcomes", {})
        if not isinstance(raw, dict):
            raw = {}
            flags["companion_arc_outcomes"] = raw
        normalized: dict[str, str] = {}
        for key, value in raw.items():
            companion_id = str(key or "").strip().lower()
            outcome = str(value or "").strip().lower()
            if not companion_id:
                continue
            if outcome in {"oath", "distance"}:
                normalized[companion_id] = outcome
        flags["companion_arc_outcomes"] = normalized
        return normalized

    def get_companion_arc_choices_intent(self, character_id: int) -> list[tuple[str, str]]:
        character = self._require_character(character_id)
        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        self._ensure_companion_arc_rows(character, unlocked_ids)
        arcs = self._companion_arc_state(character)
        outcomes = self._companion_arc_outcomes(character)
        choices: list[tuple[str, str]] = []
        for companion_id in sorted(unlocked_ids):
            row = arcs.get(companion_id)
            if not isinstance(row, dict):
                continue
            if str(row.get("stage", "")).strip().lower() != "bonded":
                continue
            if str(outcomes.get(companion_id, "")).strip().lower() in {"oath", "distance"}:
                continue
            name = str(self._COMPANION_TEMPLATES.get(companion_id, {}).get("name", companion_id.replace("_", " ").title()))
            choices.append((companion_id, name))
        return choices

    def submit_companion_arc_choice_intent(self, character_id: int, companion_id: str, choice: str) -> ActionResult:
        character = self._require_character(character_id)
        normalized_companion = str(companion_id or "").strip().lower()
        normalized_choice = str(choice or "").strip().lower()
        if normalized_choice not in {"oath", "distance"}:
            return ActionResult(messages=["Unknown arc choice."], game_over=False)

        choice_candidates = {key for key, _label in self.get_companion_arc_choices_intent(character_id)}
        if normalized_companion not in choice_candidates:
            return ActionResult(messages=["No unresolved arc choice is available for that companion."], game_over=False)

        arcs = self._companion_arc_state(character)
        outcomes = self._companion_arc_outcomes(character)
        if normalized_companion in outcomes:
            return ActionResult(messages=["This arc choice is already locked in."], game_over=False)

        row = arcs.get(normalized_companion, {})
        current_trust = int(row.get("trust", 0) or 0)
        if normalized_choice == "oath":
            next_trust = min(self._COMPANION_ARC_MAX, current_trust + 5)
            outcome_text = "Oathbound"
            outcome_note = "Their loyalty hardens into a formal oath."
        else:
            next_trust = max(0, current_trust - 4)
            outcome_text = "Distant"
            outcome_note = "They keep their distance, focused on survival over sentiment."

        row["trust"] = int(next_trust)
        row["stage"] = "bonded"
        arcs[normalized_companion] = row
        outcomes[normalized_companion] = normalized_choice

        interaction_unlocks = self._interaction_unlocks(character)
        interaction_unlocks[f"companion_arc:{normalized_companion}:{normalized_choice}"] = True

        world_turn = 0
        if self.world_repo:
            world = self.world_repo.load_default()
            world_turn = int(getattr(world, "current_turn", 0) or 0) if world is not None else 0
        self._record_companion_arc_event(
            character,
            companion_id=normalized_companion,
            world_turn=int(world_turn),
            channel="choice",
            delta=0,
        )

        self.character_repo.save(character)
        name = str(self._COMPANION_TEMPLATES.get(normalized_companion, {}).get("name", normalized_companion.replace("_", " ").title()))
        return ActionResult(
            messages=[
                f"Arc choice locked: {name} becomes {outcome_text}.",
                outcome_note,
            ],
            game_over=False,
        )

    def _companion_lead_ids(self, character: Character) -> set[str]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        raw = flags.get("companion_leads", [])
        if not isinstance(raw, list):
            return set()
        return {
            str(value or "").strip().lower()
            for value in raw
            if str(value or "").strip().lower() in self._COMPANION_TEMPLATES
        }

    def _save_companion_lead_ids(self, character: Character, lead_ids: set[str]) -> None:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["companion_leads"] = [
            companion_id
            for companion_id in self._COMPANION_TEMPLATES
            if companion_id in lead_ids
        ]

    def _record_companion_lead_history(
        self,
        character: Character,
        *,
        companion_id: str,
        world_turn: int,
        context_key: str,
        location_name: str,
    ) -> None:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        history = flags.setdefault("companion_lead_history", [])
        if not isinstance(history, list):
            history = []
            flags["companion_lead_history"] = history
        history.append(
            {
                "companion_id": str(companion_id),
                "turn": int(world_turn),
                "context": str(context_key),
                "location": str(location_name),
            }
        )
        if len(history) > 20:
            del history[:-20]

    def _companion_lead_discovery_chance(
        self,
        *,
        world_turn: int,
        context_key: str,
        location_name: str,
        world_threat: int,
    ) -> int:
        chance = int(self._COMPANION_LEAD_DISCOVERY_BASE_CHANCE)
        chance += min(4, max(0, int(world_threat) - 2))
        chance += min(2, max(0, int(world_turn) // 14))
        lowered_location = str(location_name or "").strip().lower()
        if any(token in lowered_location for token in ("village", "town", "hamlet", "crossing", "inn")):
            chance += 1
        normalized_context = str(context_key or "").strip().lower()
        if normalized_context in {"social", "rumour"}:
            chance += 3
        return max(1, min(20, chance))

    def _roll_companion_lead_discovery(
        self,
        character: Character,
        *,
        world_turn: int,
        context_key: str,
        location_name: str,
        world_threat: int = 0,
    ) -> str:
        return self._roll_companion_lead_discovery_legacy(
            character,
            world_turn=int(world_turn),
            context_key=str(context_key),
            location_name=str(location_name),
            world_threat=int(world_threat),
        )

    def _roll_companion_lead_discovery_legacy(
        self,
        character: Character,
        *,
        world_turn: int,
        context_key: str,
        location_name: str,
        world_threat: int = 0,
    ) -> str:
        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        lead_ids = self._companion_lead_ids(character)
        candidates = [
            companion_id
            for companion_id, template in self._COMPANION_TEMPLATES.items()
            if not bool(template.get("default_unlocked", False))
            and companion_id not in unlocked_ids
            and companion_id not in lead_ids
        ]
        if not candidates:
            return ""

        seed = derive_seed(
            namespace="companion.lead.discovery",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "world_turn": int(world_turn),
                "context": str(context_key or "unknown"),
                "location_name": str(location_name or "unknown"),
                "candidate_count": len(candidates),
            },
        )
        rng = random.Random(seed)
        chance = self._companion_lead_discovery_chance(
            world_turn=int(world_turn),
            context_key=str(context_key),
            location_name=str(location_name),
            world_threat=int(world_threat),
        )
        if rng.randint(1, 100) > chance:
            return ""

        ordered = sorted(candidates)
        discovered_id = ordered[rng.randrange(len(ordered))]
        lead_ids.add(discovered_id)
        self._save_companion_lead_ids(character, lead_ids)
        self._record_companion_lead_history(
            character,
            companion_id=discovered_id,
            world_turn=int(world_turn),
            context_key=str(context_key),
            location_name=str(location_name),
        )

        name = str(self._COMPANION_TEMPLATES.get(discovered_id, {}).get("name", discovered_id.replace("_", " ").title()))
        return f"A rare lead surfaces: you hear {name} was seen nearby."

    def get_companion_leads_intent(self, character_id: int) -> list[str]:
        return self.get_companion_leads_intent_legacy(character_id)

    def get_companion_leads_intent_legacy(self, character_id: int) -> list[str]:
        character = self._require_character(character_id)
        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        self._ensure_companion_arc_rows(character, unlocked_ids)
        lead_ids = self._companion_lead_ids(character)
        flags = getattr(character, "flags", None)
        history = []
        if isinstance(flags, dict) and isinstance(flags.get("companion_lead_history"), list):
            history = [row for row in flags.get("companion_lead_history", []) if isinstance(row, dict)]

        rare_ids = [
            companion_id
            for companion_id, template in self._COMPANION_TEMPLATES.items()
            if not bool(template.get("default_unlocked", False))
        ]
        recruited_rare = [companion_id for companion_id in rare_ids if companion_id in unlocked_ids]

        lines = [
            f"Rare companions recruited: {len(recruited_rare)}/{self._MAX_CAMPAIGN_RECRUITED_COMPANIONS}",
            "",
            "Registry:",
        ]
        for companion_id in rare_ids:
            name = str(self._COMPANION_TEMPLATES.get(companion_id, {}).get("name", companion_id.replace("_", " ").title()))
            if companion_id in unlocked_ids:
                state = "Recruited"
            elif companion_id in lead_ids:
                state = "Lead Acquired"
            else:
                state = "Unknown"
            lines.append(f"- {name}: {state}")

        arc_lines = self._companion_arc_lines(character)
        if arc_lines:
            lines.append("")
            lines.append("Arc Progress:")
            lines.extend(arc_lines)

        if history:
            lines.append("")
            lines.append("Recent Leads:")
            for row in history[-5:]:
                companion_id = str(row.get("companion_id", "") or "").strip().lower()
                if not companion_id:
                    continue
                name = str(self._COMPANION_TEMPLATES.get(companion_id, {}).get("name", companion_id.replace("_", " ").title()))
                turn = int(row.get("turn", 0) or 0)
                location = str(row.get("location", "unknown") or "unknown")
                context = str(row.get("context", "unknown") or "unknown")
                lines.append(f"- Day {turn}: {name} lead via {context} near {location}")
        return lines

    @staticmethod
    def _faction_display_name_from_repo(faction_repo: FactionRepository | None, faction_id: str) -> str:
        if faction_repo:
            row = faction_repo.get(str(faction_id))
            if row is not None and str(getattr(row, "name", "")).strip():
                return str(getattr(row, "name"))
        return str(faction_id).replace("_", " ").title()

    def _companion_lead_rumour_item(self, character: Character) -> RumourItemView | None:
        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        lead_ids = [
            companion_id
            for companion_id in self._companion_lead_ids(character)
            if companion_id not in unlocked_ids
        ]
        if not lead_ids:
            return None
        lead_ids.sort()
        companion_id = lead_ids[0]
        template = self._COMPANION_TEMPLATES.get(companion_id, {})
        name = str(template.get("name", companion_id.replace("_", " ").title()))
        faction_label = self._faction_display_name_from_repo(self.faction_repo, str(template.get("faction_id", "")))
        return to_rumour_item_view(
            rumour_id=f"lead_{companion_id}",
            text=f"[Lead] Tavern whispers point to {name}, a rare ally tied to {faction_label} activity.",
            confidence="credible",
            source="Tavern whispers",
        )

    def _is_quest_completed_for_character(self, character_id: int, quest_id: str) -> bool:
        if not self.world_repo:
            return False
        world = self.world_repo.load_default()
        if world is None:
            return False
        quests = self._world_quests(world)
        payload = quests.get(str(quest_id))
        if not isinstance(payload, dict):
            return False
        status = str(payload.get("status", "")).strip().lower()
        if status != "completed":
            return False
        owner_character_id = payload.get("owner_character_id")
        if owner_character_id is None:
            return True
        try:
            return int(owner_character_id) == int(character_id)
        except Exception:
            return False

    def _companion_recruitment_blockers(
        self,
        *,
        character_id: int,
        companion_id: str,
        character: Character,
        unlocked_ids: set[str],
        standings: dict[str, int],
    ) -> list[str]:
        template = self._COMPANION_TEMPLATES.get(companion_id)
        if not isinstance(template, dict):
            return ["Unknown companion."]

        blockers: list[str] = []

        lead_ids = self._companion_lead_ids(character)
        requires_lead = companion_id in {"npc_vael", "npc_seraphine", "npc_kaelen", "npc_mirelle"}
        if requires_lead and companion_id not in lead_ids:
            blockers.append("No lead yet. Keep exploring and traveling to uncover rare companions.")

        req_reputation = template.get("req_reputation", {})
        if isinstance(req_reputation, dict):
            for faction_id, minimum in req_reputation.items():
                try:
                    required_value = int(minimum)
                except Exception:
                    continue
                current_value = int(standings.get(str(faction_id), 0) or 0)
                if current_value < required_value:
                    blockers.append(f"Requires {faction_id} reputation {required_value} (current {current_value}).")

        req_completed_quest = str(template.get("req_completed_quest", "") or "").strip()
        if req_completed_quest and not self._is_quest_completed_for_character(character_id=character_id, quest_id=req_completed_quest):
            blockers.append(f"Requires completed quest: {req_completed_quest}.")

        raw_active = getattr(character, "flags", {}).get("active_party", [])
        active_ids = {
            str(value or "").strip().lower()
            for value in raw_active
            if isinstance(raw_active, list) and str(value or "").strip().lower() in self._COMPANION_TEMPLATES
        }
        rival_ids = set(unlocked_ids) | set(active_ids)
        locked_by = template.get("locked_by_companions", [])
        if isinstance(locked_by, list):
            for rival_id in locked_by:
                normalized = str(rival_id or "").strip().lower()
                if normalized in rival_ids:
                    rival_name = str(self._COMPANION_TEMPLATES.get(normalized, {}).get("name", normalized.replace("_", " ").title()))
                    blockers.append(f"Refuses to join while {rival_name} travels with you.")

        return blockers

    def recruit_companion_intent(self, character_id: int, companion_id: str) -> ActionResult:
        character = self._require_character(character_id)
        normalized = str(companion_id or "").strip().lower()
        template = self._COMPANION_TEMPLATES.get(normalized)
        if not isinstance(template, dict):
            return ActionResult(messages=["Unknown companion."], game_over=False)

        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        if normalized in unlocked_ids:
            name = str(template.get("name", normalized.replace("_", " ").title()))
            return ActionResult(messages=[f"{name} is already in your roster."], game_over=False)

        rare_recruited_count = sum(
            1
            for companion_id in unlocked_ids
            if not bool(self._COMPANION_TEMPLATES.get(companion_id, {}).get("default_unlocked", False))
        )
        if not bool(template.get("default_unlocked", False)) and rare_recruited_count >= self._MAX_CAMPAIGN_RECRUITED_COMPANIONS:
            return ActionResult(
                messages=[
                    f"Campaign recruit cap reached ({rare_recruited_count}/{self._MAX_CAMPAIGN_RECRUITED_COMPANIONS}).",
                    "No additional rare companions can be recruited this run.",
                ],
                game_over=False,
            )

        standings = self.faction_standings_intent(character_id)
        blockers = self._companion_recruitment_blockers(
            character_id=character_id,
            companion_id=normalized,
            character=character,
            unlocked_ids=unlocked_ids,
            standings=standings,
        )
        if blockers:
            name = str(template.get("name", normalized.replace("_", " ").title()))
            return ActionResult(messages=[f"{name} is not ready to join.", *blockers], game_over=False)

        unlocked_ids.add(normalized)
        self._save_unlocked_companion_ids(character, unlocked_ids)
        self._ensure_companion_arc_rows(character, unlocked_ids)
        self.character_repo.save(character)
        name = str(template.get("name", normalized.replace("_", " ").title()))
        return ActionResult(messages=[f"{name} joins your roster."], game_over=False)

    def _active_party_companions(self, player: Character) -> list[Character]:
        flags = getattr(player, "flags", None)
        if not isinstance(flags, dict):
            return []
        raw = flags.get("active_party", [])
        if not isinstance(raw, list):
            return []

        companions: list[Character] = []
        lane_overrides = self._party_lane_overrides(player)
        for idx, value in enumerate(raw):
            companion_id = str(value or "").strip().lower()
            template = self._COMPANION_TEMPLATES.get(companion_id)
            if not template:
                continue
            companion = Character(
                id=900_000 + idx,
                name=str(template.get("name", companion_id.title())),
                class_name=str(template.get("class_name", "fighter")),
                level=max(1, int(getattr(player, "level", 1) or 1)),
                hp_max=max(1, int(template.get("hp_max", 12) or 12)),
                hp_current=max(1, int(template.get("hp_max", 12) or 12)),
                location_id=getattr(player, "location_id", None),
            )
            attrs = template.get("attributes", {})
            if isinstance(attrs, dict):
                for key, stat in attrs.items():
                    companion.attributes[str(key)] = int(stat)
            companion.known_spells = [str(row) for row in list(template.get("known_spells", []) or [])]
            companion.spell_slots_max = max(0, int(template.get("spell_slots_max", 0) or 0))
            companion.spell_slots_current = companion.spell_slots_max
            self._rehydrate_companion_runtime_state(player, companion_key=companion_id, companion=companion)
            lane = str(lane_overrides.get(companion_id, "") or "").strip().lower()
            if lane in {"vanguard", "rearguard"}:
                companion.flags["combat_lane"] = lane
            companions.append(companion)
        return companions

    @staticmethod
    def _party_lane_overrides(player: Character) -> dict[str, str]:
        flags = getattr(player, "flags", None)
        if not isinstance(flags, dict):
            return {}
        raw = flags.get("party_lane_overrides", {})
        if not isinstance(raw, dict):
            return {}
        result: dict[str, str] = {}
        for key, value in raw.items():
            companion_id = str(key or "").strip().lower()
            lane = str(value or "").strip().lower()
            if companion_id and lane in {"vanguard", "rearguard"}:
                result[companion_id] = lane
        return result

    @staticmethod
    def _party_runtime_state(player: Character) -> dict[str, dict[str, int | bool]]:
        flags = getattr(player, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            player.flags = flags
        state = flags.setdefault("party_runtime_state", {})
        if not isinstance(state, dict):
            state = {}
            flags["party_runtime_state"] = state
        return state

    def _persist_party_runtime_state(self, player: Character, allies: list[Character]) -> None:
        state = self._party_runtime_state(player)
        raw_party = []
        flags = getattr(player, "flags", None)
        if isinstance(flags, dict):
            candidate = flags.get("active_party", [])
            if isinstance(candidate, list):
                raw_party = [str(row or "").strip().lower() for row in candidate if str(row or "").strip()]

        template_by_name = {
            str(template.get("name", "")).strip().lower(): key
            for key, template in self._COMPANION_TEMPLATES.items()
        }
        active_set = set(raw_party)
        for ally in allies:
            ally_name = str(getattr(ally, "name", "") or "").strip().lower()
            companion_key = template_by_name.get(ally_name)
            if not companion_key or companion_key not in active_set:
                continue
            state[companion_key] = {
                "hp_current": int(getattr(ally, "hp_current", 1) or 1),
                "hp_max": int(getattr(ally, "hp_max", 1) or 1),
                "alive": bool(getattr(ally, "alive", int(getattr(ally, "hp_current", 0) or 0) > 0)),
                "spell_slots_current": int(getattr(ally, "spell_slots_current", 0) or 0),
                "spell_slots_max": int(getattr(ally, "spell_slots_max", 0) or 0),
            }

    def _rehydrate_companion_runtime_state(self, player: Character, *, companion_key: str, companion: Character) -> None:
        state = self._party_runtime_state(player)
        payload = state.get(str(companion_key).strip().lower())
        if not isinstance(payload, dict):
            return

        raw_hp_max = payload.get("hp_max", getattr(companion, "hp_max", 1))
        raw_hp_current = payload.get("hp_current", getattr(companion, "hp_current", getattr(companion, "hp_max", 1)))
        try:
            hp_max = max(1, int(raw_hp_max))
        except Exception:
            hp_max = max(1, int(getattr(companion, "hp_max", 1) or 1))
        try:
            hp_current = int(raw_hp_current)
        except Exception:
            hp_current = int(getattr(companion, "hp_current", hp_max) or hp_max)
        companion.hp_max = hp_max
        companion.hp_current = max(0, min(hp_max, hp_current))
        companion.alive = bool(payload.get("alive", companion.hp_current > 0))

        raw_slots_max = payload.get("spell_slots_max", getattr(companion, "spell_slots_max", 0))
        raw_slots_current = payload.get("spell_slots_current", getattr(companion, "spell_slots_current", getattr(companion, "spell_slots_max", 0)))
        try:
            spell_slots_max = max(0, int(raw_slots_max))
        except Exception:
            spell_slots_max = max(0, int(getattr(companion, "spell_slots_max", 0) or 0))
        try:
            spell_slots_current = int(raw_slots_current)
        except Exception:
            spell_slots_current = int(getattr(companion, "spell_slots_current", spell_slots_max) or spell_slots_max)
        companion.spell_slots_max = spell_slots_max
        companion.spell_slots_current = max(0, min(spell_slots_max, spell_slots_current))

    def _recover_party_runtime_state(self, player: Character, *, context: str) -> None:
        state = self._party_runtime_state(player)
        if not state:
            return

        normalized_context = str(context or "").strip().lower()
        for companion_id, payload in state.items():
            if not isinstance(payload, dict):
                continue

            raw_hp_max = payload.get("hp_max", 1)
            raw_hp_current = payload.get("hp_current", raw_hp_max)
            try:
                hp_max = max(1, int(raw_hp_max))
            except Exception:
                hp_max = 1
            try:
                hp_current = int(raw_hp_current)
            except Exception:
                hp_current = hp_max
            hp_current = max(0, min(hp_max, hp_current))
            missing_hp = max(0, hp_max - hp_current)

            if normalized_context == "rest":
                hp_recover = max(1, int(math.ceil(missing_hp * 0.6))) if missing_hp > 0 else 0
                slot_recover = 1
            elif normalized_context == "travel":
                hp_recover = max(0, int(math.ceil(missing_hp * 0.25)))
                slot_recover = 0
            else:
                hp_recover = 0
                slot_recover = 0

            next_hp = min(hp_max, hp_current + hp_recover)
            raw_slots_max = payload.get("spell_slots_max", 0)
            raw_slots_current = payload.get("spell_slots_current", raw_slots_max)
            try:
                slots_max = max(0, int(raw_slots_max))
            except Exception:
                slots_max = 0
            try:
                slots_current = int(raw_slots_current)
            except Exception:
                slots_current = slots_max
            slots_current = max(0, min(slots_max, slots_current))
            next_slots = min(slots_max, slots_current + slot_recover)

            payload["hp_current"] = int(next_hp)
            payload["alive"] = bool(next_hp > 0)
            payload["spell_slots_current"] = int(next_slots)
            state[str(companion_id)] = payload

    def get_party_status_intent(self, character_id: int) -> list[str]:
        character = self._require_character(character_id)
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return []

        raw_party = flags.get("active_party", [])
        if not isinstance(raw_party, list) or not raw_party:
            return []

        runtime_state = self._party_runtime_state(character)
        lines: list[str] = []
        for value in raw_party:
            companion_id = str(value or "").strip().lower()
            if not companion_id:
                continue
            template = self._COMPANION_TEMPLATES.get(companion_id, {})
            display_name = str(template.get("name", companion_id.replace("_", " ").title()))

            payload = runtime_state.get(companion_id, {}) if isinstance(runtime_state, dict) else {}
            hp_max = max(1, int((payload.get("hp_max") if isinstance(payload, dict) else 0) or int(template.get("hp_max", 12) or 12)))
            hp_current = int((payload.get("hp_current") if isinstance(payload, dict) else hp_max) or hp_max)
            hp_current = max(0, min(hp_max, hp_current))

            slots_max = max(0, int((payload.get("spell_slots_max") if isinstance(payload, dict) else 0) or int(template.get("spell_slots_max", 0) or 0)))
            slots_current = int((payload.get("spell_slots_current") if isinstance(payload, dict) else slots_max) or slots_max)
            slots_current = max(0, min(slots_max, slots_current))

            if slots_max > 0:
                lines.append(f"{display_name}: HP {hp_current}/{hp_max}, Slots {slots_current}/{slots_max}")
            else:
                lines.append(f"{display_name}: HP {hp_current}/{hp_max}")
        return lines

    def get_party_capacity_intent(self, character_id: int) -> tuple[int, int]:
        character = self._require_character(character_id)
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return 0, self._MAX_ACTIVE_COMPANIONS

        raw_active = flags.get("active_party", [])
        if not isinstance(raw_active, list):
            return 0, self._MAX_ACTIVE_COMPANIONS

        active_ids = {
            str(value or "").strip().lower()
            for value in raw_active
            if str(value or "").strip() and str(value or "").strip().lower() in self._COMPANION_TEMPLATES
        }
        return len(active_ids), self._MAX_ACTIVE_COMPANIONS

    def get_party_management_intent(self, character_id: int) -> list[dict[str, str | bool]]:
        character = self._require_character(character_id)
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags

        raw_active = flags.get("active_party", [])
        active_ids = {
            str(value or "").strip().lower()
            for value in raw_active
            if isinstance(raw_active, list)
            and str(value or "").strip()
            and str(value or "").strip().lower() in self._COMPANION_TEMPLATES
        }
        unlocked_ids = self._unlocked_companion_ids(character)
        lane_overrides = self._party_lane_overrides(character)
        runtime_state = self._party_runtime_state(character)
        outcomes = self._companion_arc_outcomes(character)

        rows: list[dict[str, str | bool]] = []
        for companion_id in sorted(unlocked_ids):
            template = self._COMPANION_TEMPLATES.get(companion_id, {})
            display_name = str(template.get("name", companion_id.replace("_", " ").title()))
            payload = runtime_state.get(companion_id, {}) if isinstance(runtime_state, dict) else {}
            hp_max = max(1, int((payload.get("hp_max") if isinstance(payload, dict) else 0) or int(template.get("hp_max", 12) or 12)))
            hp_current = int((payload.get("hp_current") if isinstance(payload, dict) else hp_max) or hp_max)
            hp_current = max(0, min(hp_max, hp_current))
            slots_max = max(0, int((payload.get("spell_slots_max") if isinstance(payload, dict) else 0) or int(template.get("spell_slots_max", 0) or 0)))
            slots_current = int((payload.get("spell_slots_current") if isinstance(payload, dict) else slots_max) or slots_max)
            slots_current = max(0, min(slots_max, slots_current))
            lane = lane_overrides.get(companion_id, "auto")
            locked_distance = str(outcomes.get(companion_id, "") or "").strip().lower() == "distance"

            status = f"HP {hp_current}/{hp_max}"
            if slots_max > 0:
                status = f"{status}, Slots {slots_current}/{slots_max}"
            rows.append(
                {
                    "companion_id": companion_id,
                    "name": display_name,
                    "active": companion_id in active_ids,
                    "unlocked": True,
                    "recruitable": not locked_distance,
                    "gate_note": "Arc outcome: Distant (cannot assign active party)." if locked_distance else "",
                    "lane": lane,
                    "status": status,
                }
            )
        return rows

    def set_party_companion_active_intent(self, character_id: int, companion_id: str, active: bool) -> ActionResult:
        character = self._require_character(character_id)
        normalized = str(companion_id or "").strip().lower()
        if normalized not in self._COMPANION_TEMPLATES:
            return ActionResult(messages=["Unknown companion."], game_over=False)

        unlocked_ids = self._unlocked_companion_ids(character, persist_defaults=True)
        if bool(active) and normalized not in unlocked_ids:
            return ActionResult(messages=["Companion is not recruited yet."], game_over=False)

        outcomes = self._companion_arc_outcomes(character)
        if bool(active) and str(outcomes.get(normalized, "") or "").strip().lower() == "distance":
            name = str(self._COMPANION_TEMPLATES[normalized].get("name", normalized.replace("_", " ").title()))
            return ActionResult(
                messages=[f"{name} remains distant and refuses active deployment."],
                game_over=False,
            )

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags

        raw_active = flags.get("active_party", [])
        active_ids = [str(value or "").strip().lower() for value in raw_active] if isinstance(raw_active, list) else []
        active_ids = [value for value in active_ids if value in self._COMPANION_TEMPLATES]
        was_active = normalized in active_ids

        if bool(active):
            if not was_active and len(active_ids) >= self._MAX_ACTIVE_COMPANIONS:
                return ActionResult(
                    messages=[f"Party is full ({len(active_ids)}/{self._MAX_ACTIVE_COMPANIONS}). Deactivate a companion first."],
                    game_over=False,
                )
            if not was_active:
                active_ids.append(normalized)
        else:
            active_ids = [value for value in active_ids if value != normalized]

        flags["active_party"] = active_ids
        self.character_repo.save(character)
        name = str(self._COMPANION_TEMPLATES[normalized].get("name", normalized.replace("_", " ").title()))
        if active:
            message = f"{name} is already in your active party." if was_active else f"{name} joined your active party."
        else:
            message = f"{name} is already in reserve." if not was_active else f"{name} left your active party."
        return ActionResult(messages=[message], game_over=False)

    def set_party_companion_lane_intent(self, character_id: int, companion_id: str, lane: str) -> ActionResult:
        character = self._require_character(character_id)
        normalized = str(companion_id or "").strip().lower()
        if normalized not in self._COMPANION_TEMPLATES:
            return ActionResult(messages=["Unknown companion."], game_over=False)

        lane_key = str(lane or "auto").strip().lower()
        if lane_key not in {"auto", "vanguard", "rearguard"}:
            return ActionResult(messages=["Invalid lane selection."], game_over=False)

        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        overrides = flags.setdefault("party_lane_overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}
            flags["party_lane_overrides"] = overrides

        if lane_key == "auto":
            overrides.pop(normalized, None)
        else:
            overrides[normalized] = lane_key

        self.character_repo.save(character)
        name = str(self._COMPANION_TEMPLATES[normalized].get("name", normalized.replace("_", " ").title()))
        if lane_key == "auto":
            return ActionResult(messages=[f"{name} lane reset to automatic behavior."], game_over=False)
        return ActionResult(messages=[f"{name} assigned to {lane_key} lane."], game_over=False)

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
        conditions_list: list[str] = []
        if is_dodging:
            conditions_list.append("Dodging")
        raw_statuses = getattr(player, "flags", {}).get("combat_statuses", [])
        if isinstance(raw_statuses, list):
            for row in raw_statuses:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("id", "") or "").strip().lower()
                rounds = int(row.get("rounds", 0) or 0)
                if not key or rounds <= 0:
                    continue
                label = key.replace("_", " ").title()
                conditions_list.append(f"{label}({rounds})")
        raw_tactical = getattr(player, "flags", {}).get("combat_tactical_tags", {})
        if isinstance(raw_tactical, dict):
            for key, rounds in raw_tactical.items():
                slug = str(key or "").strip().lower()
                duration = int(rounds or 0)
                if not slug or duration <= 0:
                    continue
                label = slug.replace("_", " ").title()
                conditions_list.append(f"{label}({duration})")
        conditions = " | ".join(conditions_list) if conditions_list else "—"

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
        tower_allegiance = self._tower_allegiance(player)
        for name in known:
            slug = "".join(
                ch if ch.isalnum() or ch == " " else "-" for ch in name.lower()
            ).replace(" ", "-")
            spell = self.spell_repo.get_by_slug(slug) if self.spell_repo else None
            if tower_allegiance and not self._is_spell_allowed_for_tower(tower_allegiance=tower_allegiance, spell=spell, fallback_name=name):
                continue
            level = spell.level_int if spell else 0
            range_text = spell.range_text if spell else ""
            needs_slot = level > 0
            playable = slots_available > 0 if needs_slot else True
            label = f"{name} (Lv {level}{'; ' + range_text if range_text else ''})"
            if needs_slot and not playable:
                label += " [no slots]"
            options.append(SpellOptionView(slug=slug, label=label, playable=playable))
        return options

    @staticmethod
    def _tower_allegiance(player: Character) -> str | None:
        flags = getattr(player, "flags", None)
        if not isinstance(flags, dict):
            return None
        allegiance = str(flags.get("tower_allegiance", "") or "").strip().lower()
        return allegiance or None

    @classmethod
    def _is_spell_allowed_for_tower(cls, *, tower_allegiance: str, spell, fallback_name: str) -> bool:
        allowed_keywords = cls._TOWER_SPELL_KEYWORDS.get(str(tower_allegiance).strip().lower())
        if not allowed_keywords:
            return True

        fields = [str(fallback_name or "")]
        if spell is not None:
            fields.extend(
                [
                    str(getattr(spell, "name", "") or ""),
                    str(getattr(spell, "school", "") or ""),
                    str(getattr(spell, "desc_text", "") or ""),
                    str(getattr(spell, "higher_level", "") or ""),
                ]
            )
        haystack = " ".join(fields).lower()
        return any(keyword in haystack for keyword in allowed_keywords)

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

        flags = getattr(character, "flags", None)
        subclass_name = ""
        if isinstance(flags, dict):
            subclass_name = str(flags.get("subclass_name", "") or "").strip()

        return CharacterCreationSummaryView(
            character_id=character.id or 0,
            name=character.name,
            level=character.level,
            class_name=(character.class_name or "adventurer").title(),
            alignment=str(getattr(character, "alignment", "true_neutral") or "true_neutral").replace("_", " ").title(),
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
            subclass_name=subclass_name,
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

            tier = self._loot_tier_for_level(int(getattr(monster, "level", 1) or 1))
            tier_candidates = list(self._TIERED_LOOT_TABLE.get(tier, ()))
            if tier_candidates:
                tier_seed = derive_seed(
                    namespace="loot.tiered_item",
                    context={
                        "character_id": int(getattr(character, "id", 0) or 0),
                        "monster_id": int(getattr(monster, "id", 0) or 0),
                        "monster_level": int(getattr(monster, "level", 1) or 1),
                        "tier": int(tier),
                        "world_turn": world_turn,
                    },
                )
                tier_roll = int(tier_seed) % 100
                if tier_roll < 38:
                    selected_index = int(tier_seed // 100) % len(tier_candidates)
                    selected_item = str(tier_candidates[selected_index])
                    if selected_item and selected_item not in loot_items:
                        loot_items.append(selected_item)

        money_gain, loot_items = self._apply_faction_reward_tilt(
            character,
            monster,
            money_gain=money_gain,
            loot_items=loot_items,
            world_turn=world_turn,
        )

        monster_name = str(getattr(monster, "name", "Unknown Foe") or "Unknown Foe")
        codex_key = f"bestiary:{monster_name.strip().lower().replace(' ', '_')}"
        codex = self._codex_state(character)
        prior = codex.get(codex_key, {}) if isinstance(codex.get(codex_key, {}), dict) else {}
        raw_previous_notes = prior.get("discoveries", 0)
        if isinstance(raw_previous_notes, (int, float, str, bool)):
            try:
                previous_notes = int(raw_previous_notes)
            except (TypeError, ValueError):
                previous_notes = 0
        else:
            previous_notes = 0
        current_notes = previous_notes + 1
        if current_notes == 1:
            body = "First contact logged. Threat profile still uncertain."
        elif current_notes == 2:
            body = f"Repeated encounter confirms level {int(getattr(monster, 'level', 1) or 1)} combat profile."
        else:
            faction_text = str(getattr(monster, "faction_id", "unknown") or "unknown").replace("_", " ")
            body = f"Field notes expanded. Likely operating alongside {faction_text} elements."
        self._record_codex_entry(
            character,
            entry_id=codex_key,
            category="Bestiary",
            title=monster_name,
            body=body,
            world_turn=int(world_turn),
            increment_discoveries=True,
        )

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

    def _apply_faction_reward_tilt(
        self,
        character: Character,
        monster: Entity,
        *,
        money_gain: int,
        loot_items: list[str],
        world_turn: int,
    ) -> tuple[int, list[str]]:
        faction_id = str(getattr(monster, "faction_id", "") or "").strip().lower()
        if not faction_id:
            return int(money_gain), list(loot_items)
        package = self._FACTION_ENCOUNTER_PACKAGES.get(faction_id)
        if not isinstance(package, dict):
            return int(money_gain), list(loot_items)

        next_money = int(money_gain) + max(0, int(package.get("money_bonus", 0) or 0))
        next_loot = list(loot_items)
        bonus_item = str(package.get("bonus_item", "") or "").strip()
        if not bonus_item:
            return next_money, next_loot

        seed = derive_seed(
            namespace="loot.faction_tilt",
            context={
                "character_id": int(getattr(character, "id", 0) or 0),
                "monster_id": int(getattr(monster, "id", 0) or 0),
                "monster_faction": faction_id,
                "world_turn": int(world_turn),
            },
        )
        if int(seed) % 100 < 35 and bonus_item not in next_loot:
            next_loot.append(bonus_item)
        return next_money, next_loot

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

    @classmethod
    def _faction_heat_state(cls, character: Character) -> dict[str, int]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        raw = flags.setdefault("faction_heat", {})
        if not isinstance(raw, dict):
            raw = {}
            flags["faction_heat"] = raw
        normalized: dict[str, int] = {}
        for key, value in raw.items():
            faction_id = str(key or "").strip().lower()
            if not faction_id:
                continue
            try:
                score = int(value)
            except Exception:
                score = 0
            bounded = max(0, min(cls._FACTION_HEAT_MAX, score))
            if bounded > 0:
                normalized[faction_id] = bounded
        flags["faction_heat"] = dict(normalized)
        return normalized

    @staticmethod
    def _faction_heat_meta_state(character: Character) -> dict[str, object]:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        meta = flags.setdefault("faction_heat_meta", {})
        if not isinstance(meta, dict):
            meta = {}
            flags["faction_heat_meta"] = meta
        return meta

    @classmethod
    def _record_faction_heat_event(
        cls,
        character: Character,
        *,
        world_turn: int,
        reason: str,
        delta_by_faction: dict[str, int],
    ) -> None:
        if not delta_by_faction:
            return
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        history = flags.setdefault("faction_heat_log", [])
        if not isinstance(history, list):
            history = []
            flags["faction_heat_log"] = history
        history.append(
            {
                "turn": int(world_turn),
                "reason": str(reason or "unknown"),
                "delta": {str(key): int(value) for key, value in delta_by_faction.items()},
            }
        )
        if len(history) > cls._FACTION_HEAT_LOG_MAX:
            del history[:-cls._FACTION_HEAT_LOG_MAX]

    @classmethod
    def _adjust_faction_heat(cls, character: Character, faction_id: str | None, delta: int) -> None:
        normalized_faction = str(faction_id or "").strip().lower()
        if not normalized_faction:
            return
        state = cls._faction_heat_state(character)
        current = int(state.get(normalized_faction, 0) or 0)
        next_value = max(0, min(cls._FACTION_HEAT_MAX, current + int(delta)))
        if next_value <= 0:
            state.pop(normalized_faction, None)
        else:
            state[normalized_faction] = next_value
        flags = getattr(character, "flags", None)
        if isinstance(flags, dict):
            flags["faction_heat"] = dict(state)

    @classmethod
    def _decay_faction_heat(
        cls,
        character: Character,
        *,
        amount: int,
        world_turn: int,
        reason: str,
        interval_turns: int = 0,
    ) -> bool:
        decay_amount = max(0, int(amount))
        if decay_amount <= 0:
            return False
        state = cls._faction_heat_state(character)
        if not state:
            return False

        meta = cls._faction_heat_meta_state(character)
        interval = max(0, int(interval_turns))
        if interval > 0:
            raw_prior_turn = meta.get("last_decay_turn", -10_000)
            if isinstance(raw_prior_turn, int):
                prior_turn = int(raw_prior_turn)
            elif isinstance(raw_prior_turn, str):
                try:
                    prior_turn = int(raw_prior_turn)
                except Exception:
                    prior_turn = -10_000
            else:
                prior_turn = -10_000
            if int(world_turn) - prior_turn < interval:
                return False

        deltas: dict[str, int] = {}
        for faction_id, current in list(state.items()):
            next_value = max(0, int(current) - decay_amount)
            change = next_value - int(current)
            if change == 0:
                continue
            deltas[str(faction_id)] = int(change)
            if next_value <= 0:
                state.pop(faction_id, None)
            else:
                state[faction_id] = int(next_value)

        if not deltas:
            return False

        flags = getattr(character, "flags", None)
        if isinstance(flags, dict):
            flags["faction_heat"] = dict(state)
        meta["last_decay_turn"] = int(world_turn)
        cls._record_faction_heat_event(
            character,
            world_turn=int(world_turn),
            reason=str(reason or "decay"),
            delta_by_faction=deltas,
        )
        return True

    @classmethod
    def _faction_heat_pressure(cls, character: Character) -> int:
        state = cls._faction_heat_state(character)
        if not state:
            return 0
        peak = max(int(value) for value in state.values())
        return max(0, min(10, peak // 2))

    @staticmethod
    def _faction_heat_band(score: int) -> str:
        value = int(score)
        if value >= 15:
            return "Severe"
        if value >= 10:
            return "High"
        if value >= 6:
            return "Moderate"
        return "Low"

    @classmethod
    def _faction_pressure_display(cls, character: Character) -> tuple[str, list[str]]:
        state = cls._faction_heat_state(character)
        if not state:
            return "Pressure: Stable", []
        ordered = sorted(state.items(), key=lambda item: (-int(item[1]), str(item[0])))
        top_faction, top_score = ordered[0]
        pressure = cls._faction_heat_pressure(character)
        summary = (
            f"Pressure: {cls._faction_heat_band(int(top_score))} "
            f"({str(top_faction).replace('_', ' ')} heat {int(top_score)}, +{int(pressure)} risk)"
        )
        lines = [
            f"{str(faction_id).replace('_', ' ').title()}: {int(score)} ({cls._faction_heat_band(int(score))})"
            for faction_id, score in ordered[:3]
        ]
        return summary, lines

    @classmethod
    def _dominant_faction_heat(cls, character: Character) -> tuple[str | None, int]:
        state = cls._faction_heat_state(character)
        if not state:
            return None, 0
        faction_id, score = max(state.items(), key=lambda item: (int(item[1]), item[0]))
        return str(faction_id), int(score)

    def _apply_level_progression(self, character: Character, class_choice: str | None = None) -> list[str]:
        return self.progression_service.apply_level_progression(character, class_choice=class_choice)

    def faction_standings_intent(self, character_id: int) -> dict[str, int]:
        if not self.faction_repo:
            return {}

        target = f"character:{character_id}"
        standings: dict[str, int] = {}
        for faction in self.faction_repo.list_all():
            standings[faction.id] = faction.reputation.get(target, 0)
        return standings

    def get_faction_standings_view_intent(self, character_id: int) -> FactionStandingsView:
        character = self._require_character(character_id)
        current_location = self.location_repo.get(character.location_id) if self.location_repo and character.location_id is not None else None
        discovered_factions = self._discovered_factions(character, current_location=current_location)

        standings = {
            faction_id: score
            for faction_id, score in self.faction_standings_intent(character_id).items()
            if faction_id in discovered_factions
        }
        descriptions: dict[str, str] = {}
        if self.faction_repo:
            for faction in self.faction_repo.list_all():
                faction_id = str(getattr(faction, "id", "") or "").strip()
                if not faction_id:
                    continue
                if faction_id not in discovered_factions:
                    continue
                description = str(getattr(faction, "description", "") or "").strip()
                if description:
                    descriptions[faction_id] = description
        empty_state_hint = (
            "No standings tracked yet. Build reputation by resolving encounters and quests tied to local factions, then check back here."
        )
        return FactionStandingsView(standings=standings, descriptions=descriptions, empty_state_hint=empty_state_hint)

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

    @classmethod
    def _world_town_npc_state(cls, world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        row = world.flags.setdefault("town_npcs_v1", {})
        if not isinstance(row, dict):
            row = {}
            world.flags["town_npcs_v1"] = row
        row["version"] = int(cls._PROCEDURAL_TOWN_NPC_VERSION)
        generated = row.setdefault("generated", [])
        if not isinstance(generated, list):
            generated = []
            row["generated"] = generated
        routines = row.setdefault("routines", {})
        if not isinstance(routines, dict):
            routines = {}
            row["routines"] = routines
        affinities = row.setdefault("affinities", {})
        if not isinstance(affinities, dict):
            affinities = {}
            row["affinities"] = affinities
        return row

    @classmethod
    def _procedural_name_for_rng(cls, rng: random.Random) -> str:
        first = cls._PROCEDURAL_NAME_PREFIXES[rng.randrange(len(cls._PROCEDURAL_NAME_PREFIXES))]
        second = cls._PROCEDURAL_NAME_SUFFIXES[rng.randrange(len(cls._PROCEDURAL_NAME_SUFFIXES))]
        return f"{first}{second}"

    def _ensure_persistent_town_npcs(self, world) -> bool:
        state = self._world_town_npc_state(world)
        existing = state.get("generated", [])
        if isinstance(existing, list) and existing:
            return False

        seed = derive_seed(
            namespace="town.npcs.bootstrap",
            context={
                "world_id": int(getattr(world, "id", 0) or 0),
                "world_seed": int(getattr(world, "rng_seed", 0) or 0),
            },
        )
        rng = random.Random(seed)
        generated: list[dict[str, object]] = []
        routines: dict[str, dict[str, object]] = {}
        affinities: dict[str, str] = {}
        seen_ids: set[str] = set()

        for template in self._PROCEDURAL_TOWN_NPC_TEMPLATES:
            template_id = str(template.get("template_id", "npc")).strip().lower()
            npc_name = self._procedural_name_for_rng(rng)
            npc_id = f"generated_{template_id}_{npc_name.lower()}"
            counter = 2
            while npc_id in seen_ids:
                npc_id = f"generated_{template_id}_{npc_name.lower()}_{counter}"
                counter += 1
            seen_ids.add(npc_id)
            generated.append(
                {
                    "id": npc_id,
                    "name": npc_name,
                    "role": str(template.get("role", "Resident")),
                    "temperament": str(template.get("temperament", "neutral")),
                    "openness": int(template.get("openness", 5) or 5),
                    "aggression": int(template.get("aggression", 4) or 4),
                    "is_procedural": True,
                    "template_id": template_id,
                    "dialogue_profile": str(template.get("dialogue_profile", "") or "").strip(),
                }
            )
            routine = template.get("routine", {})
            if isinstance(routine, dict):
                routines[npc_id] = {
                    "day": str(routine.get("day", "Town") or "Town"),
                    "night": str(routine.get("night", "Town") or "Town"),
                    "midnight": str(routine.get("midnight", "Town") or "Town"),
                    "closed": bool(routine.get("closed", False)),
                }
            affinity = str(template.get("faction_affinity", "") or "").strip().lower()
            if affinity:
                affinities[npc_id] = affinity

        state["generated"] = generated
        state["routines"] = routines
        state["affinities"] = affinities
        return True

    def _town_npcs_for_world(self, world) -> list[dict]:
        self._ensure_persistent_town_npcs(world)
        state = self._world_town_npc_state(world)
        generated_raw = state.get("generated", [])
        generated: list[dict] = []
        if isinstance(generated_raw, list):
            generated = [dict(row) for row in generated_raw if isinstance(row, dict)]
        return [*list(self._TOWN_NPCS), *generated]

    def _npc_faction_affinity(self, world, npc_id: str) -> str | None:
        normalized = str(npc_id or "").strip().lower()
        if not normalized:
            return None
        static_affinity = self._NPC_FACTION_AFFINITY.get(normalized)
        if static_affinity:
            return static_affinity
        state = self._world_town_npc_state(world)
        affinities = state.get("affinities", {})
        if not isinstance(affinities, dict):
            return None
        affinity = str(affinities.get(normalized, "") or "").strip().lower()
        return affinity or None

    def _npc_dialogue_profile(self, npc: dict) -> str:
        profile = str(npc.get("dialogue_profile", "") or "").strip()
        if profile:
            return profile
        if bool(npc.get("is_procedural", False)):
            return "template:social"
        return ""

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
        if kind == "travel_to":
            return f"Reach destination: {bounded_progress}/{bounded_target}"
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

    @classmethod
    def _world_cataclysm_state(cls, world) -> dict[str, object]:
        if world is None:
            return {
                "active": False,
                "kind": "",
                "phase": "",
                "progress": 0,
                "seed": 0,
                "started_turn": 0,
                "last_advance_turn": 0,
                "summary": "",
            }

        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        raw = world.flags.setdefault("cataclysm_state", {})
        if not isinstance(raw, dict):
            raw = {}
            world.flags["cataclysm_state"] = raw

        active = bool(raw.get("active", False))
        kind = str(raw.get("kind", "") or "").strip().lower()
        if kind not in cls._CATACLYSM_KINDS:
            kind = ""
        phase = str(raw.get("phase", "") or "").strip().lower()
        if phase not in cls._CATACLYSM_PHASES:
            phase = ""
        progress = max(0, min(100, int(raw.get("progress", 0) or 0)))
        seed = max(0, int(raw.get("seed", 0) or 0))
        started_turn = max(0, int(raw.get("started_turn", 0) or 0))
        last_advance_turn = max(0, int(raw.get("last_advance_turn", 0) or 0))

        if not active:
            kind = ""
            phase = ""
            progress = 0

        phase_label = phase.replace("_", " ").title() if phase else ""
        kind_label = kind.replace("_", " ").title() if kind else ""
        summary = f"{kind_label} — {phase_label} ({progress}%)" if active and kind and phase else ""

        normalized = {
            "active": active,
            "kind": kind,
            "phase": phase,
            "progress": progress,
            "seed": seed,
            "started_turn": started_turn,
            "last_advance_turn": last_advance_turn,
            "summary": summary,
        }
        world.flags["cataclysm_state"] = {
            "active": bool(normalized["active"]),
            "kind": str(normalized["kind"]),
            "phase": str(normalized["phase"]),
            "progress": int(normalized["progress"]),
            "seed": int(normalized["seed"]),
            "started_turn": int(normalized["started_turn"]),
            "last_advance_turn": int(normalized["last_advance_turn"]),
        }
        return normalized

    @staticmethod
    def _world_cataclysm_end_state(world) -> dict[str, object]:
        if world is None:
            return {
                "status": "",
                "game_over": False,
                "message": "",
                "resolved_turn": 0,
            }
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        raw = world.flags.setdefault("cataclysm_end_state", {})
        if not isinstance(raw, dict):
            raw = {}
            world.flags["cataclysm_end_state"] = raw
        status = str(raw.get("status", "") or "").strip().lower()
        if status not in {"", "resolved_victory", "world_fell"}:
            status = ""
        message = str(raw.get("message", "") or "")
        resolved_turn = max(0, int(raw.get("resolved_turn", 0) or 0))
        game_over = bool(raw.get("game_over", False)) or status == "world_fell"
        normalized = {
            "status": status,
            "game_over": bool(game_over),
            "message": message,
            "resolved_turn": int(resolved_turn),
        }
        world.flags["cataclysm_end_state"] = {
            "status": str(normalized["status"]),
            "game_over": bool(normalized["game_over"]),
            "message": str(normalized["message"]),
            "resolved_turn": int(normalized["resolved_turn"]),
        }
        return normalized

    def _resolve_cataclysm_terminal_state(self, world) -> dict[str, object]:
        end_state = self._world_cataclysm_end_state(world)
        if str(end_state.get("status", "") or ""):
            return end_state

        state = self._world_cataclysm_state(world)
        if bool(state.get("active", False)) and str(state.get("phase", "") or "") == "ruin":
            raw_progress = state.get("progress", 0)
            progress = int(raw_progress if isinstance(raw_progress, (int, float, str)) else 0)
            if progress >= 100:
                world_turn = int(getattr(world, "current_turn", 0) or 0)
                raw = world.flags.setdefault("cataclysm_end_state", {}) if isinstance(getattr(world, "flags", None), dict) else {}
                if isinstance(raw, dict):
                    raw["status"] = "world_fell"
                    raw["game_over"] = True
                    raw["message"] = "Game Over — The World Fell"
                    raw["resolved_turn"] = int(world_turn)
                self._append_consequence(
                    world,
                    kind="cataclysm_world_fell",
                    message="Ruin reaches its apex. Game Over — The World Fell.",
                    severity="critical",
                    turn=world_turn,
                )
        return self._world_cataclysm_end_state(world)

    @classmethod
    def _cataclysm_quest_templates(cls, cataclysm: dict[str, object]) -> tuple[dict[str, object], ...]:
        kind = str(cataclysm.get("kind", "") or "")
        phase = str(cataclysm.get("phase", "") or "")
        return (
            {
                "quest_id": "cataclysm_scout_front",
                "status": "available",
                "objective_kind": "kill_any",
                "progress": 0,
                "target": 3,
                "reward_xp": 26,
                "reward_money": 12,
                "cataclysm_pushback": True,
                "pushback_tier": 1,
                "pushback_focus": kind,
                "phase": phase,
            },
            {
                "quest_id": "cataclysm_supply_lines",
                "status": "available",
                "objective_kind": "travel_count",
                "progress": 0,
                "target": 2,
                "reward_xp": 24,
                "reward_money": 14,
                "cataclysm_pushback": True,
                "pushback_tier": 1,
                "pushback_focus": kind,
                "phase": phase,
            },
            {
                "quest_id": "cataclysm_alliance_accord",
                "status": "available",
                "objective_kind": "kill_any",
                "progress": 0,
                "target": 4,
                "reward_xp": 34,
                "reward_money": 18,
                "cataclysm_pushback": True,
                "pushback_tier": 2,
                "pushback_focus": kind,
                "phase": phase,
                "requires_alliance_reputation": 10,
                "requires_alliance_count": 2,
            },
            {
                "quest_id": "cataclysm_apex_clash",
                "status": "available",
                "objective_kind": "kill_any",
                "progress": 0,
                "target": 1,
                "reward_xp": 50,
                "reward_money": 25,
                "cataclysm_pushback": True,
                "pushback_tier": 3,
                "pushback_focus": kind,
                "phase": phase,
                "is_apex_objective": True,
            },
        )

    def _sync_cataclysm_quest_pressure(self, world, *, world_turn: int) -> bool:
        quests = self._world_quests(world)
        cataclysm = self._world_cataclysm_state(world)
        changed = False

        if not bool(cataclysm.get("active", False)):
            removable = [
                quest_id
                for quest_id, payload in quests.items()
                if isinstance(payload, dict)
                and bool(payload.get("cataclysm_pushback", False))
                and str(payload.get("status", "")) == "available"
            ]
            for quest_id in removable:
                quests.pop(quest_id, None)
                changed = True
            return changed

        for quest_id in list(quests.keys()):
            payload = quests.get(quest_id)
            if not isinstance(payload, dict):
                continue
            if bool(payload.get("cataclysm_pushback", False)):
                continue
            if str(payload.get("status", "")) == "available":
                quests.pop(quest_id, None)
                changed = True

        raw_seed = cataclysm.get("seed", 1)
        seed_base = max(1, int(raw_seed if isinstance(raw_seed, (int, float, str)) else 1))
        for row in self._cataclysm_quest_templates(cataclysm):
            quest_id = str(row.get("quest_id", "") or "")
            if not quest_id:
                continue
            if quest_id == "cataclysm_apex_clash":
                raw_progress = cataclysm.get("progress", 0)
                progress = int(raw_progress if isinstance(raw_progress, (int, float, str)) else 0)
                alliance = quests.get("cataclysm_alliance_accord")
                alliance_complete = isinstance(alliance, dict) and str(alliance.get("status", "")) in {
                    "ready_to_turn_in",
                    "completed",
                }
                if progress > int(self._CATACLYSM_APEX_PROGRESS_THRESHOLD) and not alliance_complete:
                    continue
            existing = quests.get(quest_id)
            if isinstance(existing, dict) and str(existing.get("status", "")) in {
                "active",
                "ready_to_turn_in",
                "completed",
                "failed",
            }:
                continue
            seed_value = derive_seed(
                namespace="quest.cataclysm.template",
                context={
                    "cataclysm_seed": int(seed_base),
                    "quest_id": quest_id,
                    "kind": str(cataclysm.get("kind", "") or ""),
                    "phase": str(cataclysm.get("phase", "") or ""),
                },
            )
            payload = dict(row)
            payload["seed_key"] = f"quest:{quest_id}:{int(seed_value)}"
            payload["spawned_turn"] = int(world_turn)
            quests[quest_id] = payload
            changed = True
        return changed

    def _apply_cataclysm_pushback_from_quest(self, world, *, quest_id: str, quest: dict, character_id: int) -> int:
        if not isinstance(quest, dict) or not bool(quest.get("cataclysm_pushback", False)):
            return 0
        state = self._world_cataclysm_state(world)
        if not bool(state.get("active", False)):
            return 0
        tier = max(1, int(quest.get("pushback_tier", 1) or 1))
        raw_state_seed = state.get("seed", 0)
        state_seed = int(raw_state_seed if isinstance(raw_state_seed, (int, float, str)) else 0)
        seed = derive_seed(
            namespace="quest.cataclysm.pushback",
            context={
                "quest_id": str(quest_id or "unknown"),
                "character_id": int(character_id),
                "cataclysm_seed": state_seed,
                "kind": str(state.get("kind", "") or ""),
                "phase": str(state.get("phase", "") or ""),
                "world_turn": int(getattr(world, "current_turn", 0) or 0),
                "tier": int(tier),
            },
        )
        rng = random.Random(seed)
        base = 4 if tier <= 1 else 7
        reduction = max(1, int(base + rng.randint(0, 2)))
        raw_progress = state.get("progress", 0)
        current = max(0, min(100, int(raw_progress if isinstance(raw_progress, (int, float, str)) else 0)))
        updated = max(0, current - reduction)
        state["progress"] = int(updated)
        raw_state = world.flags.setdefault("cataclysm_state", {}) if isinstance(getattr(world, "flags", None), dict) else {}
        if isinstance(raw_state, dict):
            raw_state["progress"] = int(updated)
            raw_state["last_pushback_turn"] = int(getattr(world, "current_turn", 0) or 0)
            raw_state["last_pushback_quest"] = str(quest_id)
        if updated <= 0:
            state["active"] = False
            state["phase"] = ""
            state["kind"] = ""
            if isinstance(raw_state, dict):
                raw_state["active"] = False
                raw_state["phase"] = ""
                raw_state["kind"] = ""
        self._append_consequence(
            world,
            kind="cataclysm_pushback_quest",
            message=f"Quest pressure relief slows the cataclysm by {int(reduction)}%.",
            severity="normal",
            turn=int(getattr(world, "current_turn", 0) or 0),
        )
        return int(reduction)

    def _apply_cataclysm_apex_resolution_from_quest(self, world, *, quest_id: str, quest: dict, character_id: int) -> bool:
        if str(quest_id or "") != "cataclysm_apex_clash":
            return False
        if not isinstance(quest, dict) or not bool(quest.get("is_apex_objective", False)):
            return False
        state = self._world_cataclysm_state(world)
        if not bool(state.get("active", False)):
            return False

        world_turn = int(getattr(world, "current_turn", 0) or 0)
        raw_state = world.flags.setdefault("cataclysm_state", {}) if isinstance(getattr(world, "flags", None), dict) else {}
        if isinstance(raw_state, dict):
            raw_state["active"] = False
            raw_state["kind"] = ""
            raw_state["phase"] = ""
            raw_state["progress"] = 0
            raw_state["last_pushback_quest"] = str(quest_id)
            raw_state["last_pushback_turn"] = int(world_turn)

        raw_end = world.flags.setdefault("cataclysm_end_state", {}) if isinstance(getattr(world, "flags", None), dict) else {}
        if isinstance(raw_end, dict):
            raw_end["status"] = "resolved_victory"
            raw_end["game_over"] = False
            raw_end["message"] = "Cataclysm resolved — The world endures."
            raw_end["resolved_turn"] = int(world_turn)
            raw_end["resolved_by_character_id"] = int(character_id)

        self._append_consequence(
            world,
            kind="cataclysm_apex_resolved",
            message="The apex threat is broken before ruin claims the world.",
            severity="critical",
            turn=world_turn,
        )
        return True

    @classmethod
    def _cataclysm_encounter_modifiers(cls, world) -> tuple[int, int, str | None]:
        state = cls._world_cataclysm_state(world)
        if not bool(state.get("active", False)):
            return 0, 0, None
        phase = str(state.get("phase", "") or "")
        kind = str(state.get("kind", "") or "")
        level_delta = int(cls._CATACLYSM_PHASE_ENCOUNTER_LEVEL_DELTA.get(phase, 0) or 0)
        max_delta = int(cls._CATACLYSM_PHASE_ENCOUNTER_MAX_DELTA.get(phase, 0) or 0)
        bias = cls._CATACLYSM_KIND_ENCOUNTER_BIAS.get(kind)
        return level_delta, max_delta, bias

    @classmethod
    def _cataclysm_rest_corruption_loss(cls, world_before, *, context: str) -> int:
        state = cls._world_cataclysm_state(world_before)
        if not bool(state.get("active", False)):
            return 0
        phase = str(state.get("phase", "") or "")
        base_loss = int(cls._CATACLYSM_PHASE_REST_CORRUPTION.get(phase, 0) or 0)
        if str(context or "").lower() == "short_rest":
            return max(0, base_loss - 1)
        return base_loss

    def _apply_cataclysm_rest_corruption(self, character: Character, *, world_before, context: str) -> int:
        corruption_loss = self._cataclysm_rest_corruption_loss(world_before, context=context)
        applied_loss = min(max(0, int(corruption_loss)), max(0, int(getattr(character, "hp_current", 1) or 1) - 1))
        if applied_loss > 0:
            character.hp_current = max(1, int(getattr(character, "hp_current", 1) or 1) - applied_loss)
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["last_rest_penalty"] = {
            "context": str(context or "rest"),
            "hp_loss": int(applied_loss),
        }
        return int(applied_loss)

    @staticmethod
    def _last_rest_corruption_message(character: Character) -> str:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            return ""
        row = flags.get("last_rest_penalty", {})
        if not isinstance(row, dict):
            return ""
        hp_loss = max(0, int(row.get("hp_loss", 0) or 0))
        if hp_loss <= 0:
            return ""
        return f"Cataclysm corruption lingers after rest: -{hp_loss} HP."

    @classmethod
    def _cataclysm_camp_risk_shift(cls, world_before) -> int:
        state = cls._world_cataclysm_state(world_before)
        if not bool(state.get("active", False)):
            return 0
        phase = str(state.get("phase", "") or "")
        return int(cls._CATACLYSM_PHASE_CAMP_RISK_SHIFT.get(phase, 0) or 0)

    @classmethod
    def _cataclysm_travel_day_shift(cls, cataclysm: dict[str, object]) -> int:
        if not bool(cataclysm.get("active", False)):
            return 0
        phase = str(cataclysm.get("phase", "") or "")
        return int(cls._CATACLYSM_PHASE_TRAVEL_DAY_SHIFT.get(phase, 0) or 0)

    @staticmethod
    def _apply_cataclysm_travel_risk_hint(risk_hint: str, cataclysm: dict[str, object]) -> str:
        if not bool(cataclysm.get("active", False)):
            return str(risk_hint or "")
        order = ["Low", "Moderate", "High"]
        current = str(risk_hint or "Low").title()
        if current not in order:
            current = "Moderate"
        index = min(len(order) - 1, order.index(current) + 1)
        return order[index]

    @staticmethod
    def _cataclysm_route_note(*, road_days: int, cataclysm: dict[str, object]) -> str:
        note = f"Route estimate: {int(road_days)} day(s) by road."
        if not bool(cataclysm.get("active", False)):
            return note
        phase = str(cataclysm.get("phase", "") or "").replace("_", " ")
        kind = str(cataclysm.get("kind", "") or "").replace("_", " ")
        return f"{note} Cataclysm pressure ({kind}, {phase}) destabilizes routes."

    @staticmethod
    def _cataclysm_item_price_shift(*, cataclysm: dict[str, object], item_id: str) -> int:
        if not bool(cataclysm.get("active", False)):
            return 0
        kind = str(cataclysm.get("kind", "") or "")
        normalized_item = str(item_id or "").strip().lower()
        if kind == "plague" and normalized_item in {"antitoxin", "healing_herbs", "sturdy_rations"}:
            return 1
        if kind == "tyrant" and normalized_item in {"whetstone", "rope", "torch"}:
            return 1
        if kind == "demon_king" and normalized_item in {"torch", "antitoxin"}:
            return 1
        return 0

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

    @staticmethod
    def _world_combat_consequence_state(world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        rows = world.flags.setdefault("combat_consequence_state", {})
        if not isinstance(rows, dict):
            rows = {}
            world.flags["combat_consequence_state"] = rows
        return rows

    def _apply_post_combat_morale_consequence(
        self,
        *,
        world,
        character_id: int,
        world_turn: int,
        allies_won: bool,
        fled: bool,
        enemy_factions: list[str],
        context_key: str,
    ) -> bool:
        if not allies_won or fled:
            return False
        normalized_factions = sorted({str(item or "").strip().lower() for item in enemy_factions if str(item or "").strip()})
        if not normalized_factions:
            return False

        state = self._world_combat_consequence_state(world)
        lock_key = f"last_turn:character:{int(character_id)}"
        if int(state.get(lock_key, -10_000) or -10_000) == int(world_turn):
            return False

        dominant_faction = normalized_factions[0]
        seed = derive_seed(
            namespace="combat.morale_consequence",
            context={
                "character_id": int(character_id),
                "world_turn": int(world_turn),
                "enemy_factions": tuple(normalized_factions),
                "context": str(context_key or "unknown"),
            },
        )
        roll = int(seed) % 100
        if roll >= 35:
            return False

        if hasattr(world, "threat_level"):
            world.threat_level = max(0, int(getattr(world, "threat_level", 0) or 0) - 1)
        self._append_consequence(
            world,
            kind="combat_morale_break",
            message=(
                f"{dominant_faction.replace('_', ' ').title()} lines waver after your victory; "
                "local patrol pressure eases."
            ),
            severity="minor",
            turn=int(world_turn),
        )
        state[lock_key] = int(world_turn)
        return True

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
        cat_level_delta, cat_max_delta, cat_bias = self._cataclysm_encounter_modifiers(world)
        effective_level = max(1, int(effective_level) + int(cat_level_delta))
        effective_max = min(3, int(effective_max) + int(cat_max_delta))

        effective_bias = flashpoint_bias if pressure >= 45 and flashpoint_bias else base_faction_bias
        if cat_bias:
            effective_bias = cat_bias
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
    def _faction_pair_key(left: str, right: str) -> str:
        ordered = sorted([str(left or "").strip().lower(), str(right or "").strip().lower()])
        if len(ordered) != 2 or not ordered[0] or not ordered[1] or ordered[0] == ordered[1]:
            return ""
        return f"{ordered[0]}|{ordered[1]}"

    @classmethod
    def _world_faction_diplomacy_state(cls, world) -> dict:
        narrative = cls._world_narrative_flags(world)
        raw = narrative.setdefault("faction_diplomacy", {})
        if not isinstance(raw, dict):
            raw = {}
            narrative["faction_diplomacy"] = raw
        if not isinstance(raw.get("relations"), dict):
            raw["relations"] = {}
        if not isinstance(raw.get("border_pressure"), dict):
            raw["border_pressure"] = {}
        if not isinstance(raw.get("active_wars"), list):
            raw["active_wars"] = []
        if not isinstance(raw.get("active_alliances"), list):
            raw["active_alliances"] = []
        if not isinstance(raw.get("factions"), list):
            raw["factions"] = []
        raw["last_turn"] = int(raw.get("last_turn", -1) or -1)
        return raw

    def _diplomacy_seed_factions(
        self,
        *,
        character: Character | None,
        current_location: Location | None,
        existing: dict,
    ) -> list[str]:
        selected: list[str] = []

        for faction_id in list(existing.get("factions", []) or []):
            normalized = str(faction_id or "").strip().lower()
            if normalized and normalized not in selected:
                selected.append(normalized)

        for faction_id in self._location_faction_ids(current_location):
            normalized = str(faction_id or "").strip().lower()
            if normalized and normalized not in selected:
                selected.append(normalized)

        if character is not None:
            discovered = self._discovered_factions(character, current_location=current_location)
            for faction_id in sorted(discovered):
                normalized = str(faction_id or "").strip().lower()
                if normalized and normalized not in selected:
                    selected.append(normalized)

        defaults = ("wardens", "wild", "undead")
        for faction_id in defaults:
            if faction_id not in selected:
                selected.append(faction_id)

        if self.faction_repo:
            if character is not None:
                target = f"character:{int(getattr(character, 'id', 0) or 0)}"
                standing_factions: list[str] = []
                for faction in self.faction_repo.list_all():
                    faction_id = str(getattr(faction, "id", "") or "").strip().lower()
                    if not faction_id:
                        continue
                    reputation = int(getattr(faction, "reputation", {}).get(target, 0) or 0)
                    if reputation != 0:
                        standing_factions.append(faction_id)
                standing_factions.sort()
                for faction_id in standing_factions:
                    if faction_id not in selected:
                        selected.append(faction_id)

            if len(selected) < 3:
                repo_ids = sorted(
                    str(getattr(faction, "id", "") or "").strip().lower()
                    for faction in self.faction_repo.list_all()
                    if str(getattr(faction, "id", "") or "").strip()
                )
                for faction_id in repo_ids:
                    if faction_id and faction_id not in selected:
                        selected.append(faction_id)
                    if len(selected) >= 3:
                        break

        return sorted(selected)[:12]

    def _sync_faction_diplomacy(
        self,
        world,
        *,
        character: Character | None = None,
        current_location: Location | None = None,
    ) -> tuple[dict[str, object], bool]:
        state = self._world_faction_diplomacy_state(world)
        world_turn = int(getattr(world, "current_turn", 0) or 0)
        world_seed = int(getattr(world, "rng_seed", 0) or 0)
        threat_level = int(getattr(world, "threat_level", 0) or 0)

        factions = self._diplomacy_seed_factions(character=character, current_location=current_location, existing=state)
        if len(factions) < 2:
            changed = int(state.get("last_turn", -1) or -1) != world_turn
            state["factions"] = factions
            state["last_turn"] = world_turn
            return state, changed

        narrative = self._world_narrative_flags(world)
        graph = narrative.setdefault("relationship_graph", {})
        if not isinstance(graph, dict):
            graph = {}
            narrative["relationship_graph"] = graph
        graph_edges = graph.setdefault("faction_edges", {})
        if not isinstance(graph_edges, dict):
            graph_edges = {}
            graph["faction_edges"] = graph_edges

        raw_relations = state.get("relations", {})
        if not isinstance(raw_relations, dict):
            raw_relations = {}
        relations: dict[str, int] = {}
        for left_index in range(len(factions)):
            for right_index in range(left_index + 1, len(factions)):
                pair = self._faction_pair_key(factions[left_index], factions[right_index])
                if not pair:
                    continue
                if pair in raw_relations:
                    value = raw_relations[pair]
                elif pair in graph_edges:
                    value = graph_edges[pair]
                else:
                    seed = derive_seed(
                        namespace="faction.diplomacy.initial",
                        context={
                            "world_seed": world_seed,
                            "pair": pair,
                        },
                    )
                    value = random.Random(seed).randint(-20, 20)
                relations[pair] = max(self._DIPLOMACY_RELATION_MIN, min(self._DIPLOMACY_RELATION_MAX, int(value)))

        previous_relations = dict(relations)
        last_turn = int(state.get("last_turn", -1) or -1)
        if world_turn > last_turn:
            for turn in range(last_turn + 1, world_turn + 1):
                for pair, score in list(relations.items()):
                    seed = derive_seed(
                        namespace="faction.diplomacy.step",
                        context={
                            "world_seed": world_seed,
                            "turn": int(turn),
                            "pair": str(pair),
                            "threat": threat_level,
                        },
                    )
                    roll = random.Random(seed).randint(1, 100)
                    delta = 0
                    if roll <= 8:
                        delta = -6
                    elif roll <= 20:
                        delta = -3
                    elif roll >= 95:
                        delta = 6
                    elif roll >= 82:
                        delta = 3
                    if threat_level >= 6:
                        delta -= 1
                    if score <= -55 and delta < 0:
                        delta = 0
                    if score >= 55 and delta > 0:
                        delta = 0
                    relations[pair] = max(
                        self._DIPLOMACY_RELATION_MIN,
                        min(self._DIPLOMACY_RELATION_MAX, int(score) + int(delta)),
                    )

        active_wars: list[str] = []
        active_alliances: list[str] = []
        border_pressure: dict[str, int] = {faction_id: 0 for faction_id in factions}
        for pair, score in relations.items():
            left, right = str(pair).split("|", 1)
            if int(score) <= int(self._DIPLOMACY_WAR_THRESHOLD):
                active_wars.append(pair)
                border_pressure[left] = int(border_pressure.get(left, 0)) + 3
                border_pressure[right] = int(border_pressure.get(right, 0)) + 3
            elif int(score) >= int(self._DIPLOMACY_ALLIANCE_THRESHOLD):
                active_alliances.append(pair)

        previous_wars = sorted(str(item) for item in list(state.get("active_wars", []) or []))
        previous_alliances = sorted(str(item) for item in list(state.get("active_alliances", []) or []))
        state["factions"] = factions
        state["relations"] = {key: int(value) for key, value in sorted(relations.items())}
        state["active_wars"] = sorted(active_wars)
        state["active_alliances"] = sorted(active_alliances)
        state["border_pressure"] = {key: int(value) for key, value in sorted(border_pressure.items()) if int(value) > 0}
        state["last_turn"] = world_turn

        graph_edges.update({key: int(value) for key, value in relations.items()})
        graph["faction_edges"] = graph_edges

        changed = (
            world_turn != last_turn
            or relations != previous_relations
            or sorted(active_wars) != previous_wars
            or sorted(active_alliances) != previous_alliances
        )
        return state, bool(changed)

    @staticmethod
    def _diplomacy_travel_risk_shift(*, diplomacy_state: dict[str, object], location: Location | None) -> int:
        if location is None:
            return 0
        local_factions = {
            str(faction_id or "").strip().lower()
            for faction_id in getattr(location, "factions", []) or []
            if str(faction_id or "").strip()
        }
        if not local_factions:
            return 0

        pressure_map = diplomacy_state.get("border_pressure", {})
        if not isinstance(pressure_map, dict):
            pressure_map = {}
        wars = diplomacy_state.get("active_wars", [])
        if not isinstance(wars, list):
            wars = []
        alliances = diplomacy_state.get("active_alliances", [])
        if not isinstance(alliances, list):
            alliances = []

        shift = 0
        for faction_id in local_factions:
            shift += int(pressure_map.get(faction_id, 0) or 0)

        for pair in wars:
            left, sep, right = str(pair).partition("|")
            if sep and local_factions.intersection({left, right}):
                shift += 6

        for pair in alliances:
            left, sep, right = str(pair).partition("|")
            if sep and local_factions.intersection({left, right}):
                shift -= 3

        return max(-10, min(18, int(shift)))

    @staticmethod
    def _faction_label(faction_id: str) -> str:
        return str(faction_id or "").replace("_", " ").title()

    @classmethod
    def _diplomacy_route_note(cls, *, diplomacy_state: dict[str, object], location: Location | None) -> str:
        if location is None:
            return ""
        local_factions = {
            str(faction_id or "").strip().lower()
            for faction_id in getattr(location, "factions", []) or []
            if str(faction_id or "").strip()
        }
        if not local_factions:
            return ""

        wars = diplomacy_state.get("active_wars", [])
        if isinstance(wars, list):
            for pair in wars:
                left, sep, right = str(pair).partition("|")
                if not sep:
                    continue
                if local_factions.intersection({left, right}):
                    return f"Border clashes between {cls._faction_label(left)} and {cls._faction_label(right)} increase route danger."

        alliances = diplomacy_state.get("active_alliances", [])
        if isinstance(alliances, list):
            for pair in alliances:
                left, sep, right = str(pair).partition("|")
                if not sep:
                    continue
                if local_factions.intersection({left, right}):
                    return f"Joint patrols from {cls._faction_label(left)} and {cls._faction_label(right)} steady nearby roads."

        return ""

    @staticmethod
    def _diplomacy_fingerprint(diplomacy_state: dict[str, object], limit: int = 4) -> tuple[str, ...]:
        relations = diplomacy_state.get("relations", {})
        if not isinstance(relations, dict):
            return ()
        rows = sorted((str(key), int(value)) for key, value in relations.items())
        trimmed = rows[: max(1, int(limit))]
        return tuple(f"{key}:{value}" for key, value in trimmed)

    def _diplomacy_rumour_item(
        self,
        *,
        world,
        character_id: int,
        diplomacy_state: dict[str, object],
    ) -> RumourItemView | None:
        day = int(getattr(world, "current_turn", 0) or 0)
        wars = [str(item) for item in list(diplomacy_state.get("active_wars", []) or []) if "|" in str(item)]
        alliances = [str(item) for item in list(diplomacy_state.get("active_alliances", []) or []) if "|" in str(item)]
        if not wars and not alliances:
            return None

        seed = derive_seed(
            namespace="town.rumour.diplomacy",
            context={
                "day": day,
                "character_id": int(character_id),
                "wars": tuple(sorted(wars)),
                "alliances": tuple(sorted(alliances)),
            },
        )
        rng = random.Random(seed)

        if wars and (not alliances or rng.randint(1, 100) <= 70):
            pair = wars[rng.randrange(len(wars))]
            left, right = pair.split("|", 1)
            return to_rumour_item_view(
                rumour_id=f"diplomacy:war:{pair}:{day}",
                text=f"[Border War] Scouts report fresh skirmishes between {self._faction_label(left)} and {self._faction_label(right)} along frontier roads.",
                confidence="credible",
                source="Caravan Wardens",
            )

        pair = alliances[rng.randrange(len(alliances))]
        left, right = pair.split("|", 1)
        return to_rumour_item_view(
            rumour_id=f"diplomacy:alliance:{pair}:{day}",
            text=f"[Alliance Watch] {self._faction_label(left)} and {self._faction_label(right)} are coordinating patrol routes, opening safer trade windows.",
            confidence="uncertain",
            source="Guild Couriers",
        )

    def _diplomacy_quest_urgency_suffix(
        self,
        *,
        diplomacy_state: dict[str, object],
        quest_payload: dict,
    ) -> str:
        if not isinstance(quest_payload, dict) or not self.location_repo:
            return ""
        objective_kind = str(quest_payload.get("objective_kind", "")).strip().lower()
        if objective_kind != "travel_to":
            return ""
        try:
            location_id = int(quest_payload.get("objective_target_location_id", 0) or 0)
        except Exception:
            return ""
        if location_id <= 0:
            return ""
        location = self.location_repo.get(location_id)
        if location is None:
            return ""

        local_factions = {
            str(faction_id or "").strip().lower()
            for faction_id in getattr(location, "factions", []) or []
            if str(faction_id or "").strip()
        }
        if not local_factions:
            return ""

        wars = list(diplomacy_state.get("active_wars", []) or [])
        for pair in wars:
            left, sep, right = str(pair).partition("|")
            if sep and local_factions.intersection({left, right}):
                return "Warfront pressure"

        alliances = list(diplomacy_state.get("active_alliances", []) or [])
        for pair in alliances:
            left, sep, right = str(pair).partition("|")
            if sep and local_factions.intersection({left, right}):
                return "Alliance escort window"

        return ""

    @staticmethod
    def _bounded_price(base_price: int, modifier: int) -> int:
        floor = 1
        ceiling = max(2, int(base_price) * 2)
        return max(floor, min(ceiling, int(base_price) + int(modifier)))

    def _town_price_modifier(self, character_id: int) -> int:
        character = self._require_character(character_id)
        standings = self.faction_standings_intent(character_id)
        best = max(int(score) for score in standings.values()) if standings else 0
        heat_penalty = max(0, self._faction_heat_pressure(character))
        world = self.world_repo.load_default() if self.world_repo else None
        cataclysm = self._world_cataclysm_state(world)
        phase = str(cataclysm.get("phase", "") or "")
        cat_surcharge = int(self._CATACLYSM_PHASE_TOWN_PRICE_SURCHARGE.get(phase, 0) or 0) if bool(cataclysm.get("active", False)) else 0
        if 5 <= best < 10:
            return max(-1, -1 + heat_penalty) + cat_surcharge
        if -10 < best <= -5:
            return 1 + heat_penalty + cat_surcharge
        return calculate_price_modifier(best) + heat_penalty + cat_surcharge

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
        operation_rows = list(operations or ())
        if not self.atomic_state_persistor or not self.world_repo:
            return False
        if operation_rows and not self._persistor_supports_operations(self.atomic_state_persistor):
            raise RuntimeError(
                "Configured atomic_state_persistor does not accept operation batches; "
                "cannot guarantee atomic persistence for dependent side-effects."
            )
        if operation_rows:
            self.atomic_state_persistor(character, world, operation_rows)
            return True
        self.atomic_state_persistor(character, world)
        return True

    @staticmethod
    def _persistor_supports_operations(persistor: Callable[..., None]) -> bool:
        try:
            signature = inspect.signature(persistor)
        except Exception:
            return False

        for parameter in signature.parameters.values():
            if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                return True
        return len(signature.parameters) >= 3

    def _find_town_npc(self, npc_id: str) -> dict:
        target = (npc_id or "").strip().lower()
        world = self._require_world()
        for npc in self._town_npcs_for_world(world):
            if str(npc["id"]).lower() == target:
                return npc
        raise ValueError(f"Unknown NPC: {npc_id}")

    def _capture_snapshot_state(self) -> dict[str, object]:
        state: dict[str, object] = {}
        if self.world_repo is not None:
            state["world"] = copy.deepcopy(self.world_repo.load_default())
            for attr in ("_world", "_world_flags", "_world_history"):
                if hasattr(self.world_repo, attr):
                    state[f"world_repo:{attr}"] = copy.deepcopy(getattr(self.world_repo, attr))

        if hasattr(self.character_repo, "_characters"):
            state["character_repo:_characters"] = copy.deepcopy(getattr(self.character_repo, "_characters"))
        else:
            state["characters"] = copy.deepcopy(self.character_repo.list_all())

        if hasattr(self.character_repo, "_progression_unlocks"):
            state["character_repo:_progression_unlocks"] = copy.deepcopy(
                getattr(self.character_repo, "_progression_unlocks")
            )

        if self.entity_repo is not None:
            for attr in ("_entities", "_by_location"):
                if hasattr(self.entity_repo, attr):
                    state[f"entity_repo:{attr}"] = copy.deepcopy(getattr(self.entity_repo, attr))

        if self.faction_repo is not None and hasattr(self.faction_repo, "_factions"):
            state["faction_repo:_factions"] = copy.deepcopy(getattr(self.faction_repo, "_factions"))

        return state

    def _restore_snapshot_state(self, state: dict[str, object]) -> None:
        if self.world_repo is not None:
            for attr in ("_world", "_world_flags", "_world_history"):
                key = f"world_repo:{attr}"
                if key in state and hasattr(self.world_repo, attr):
                    setattr(self.world_repo, attr, copy.deepcopy(state[key]))

            world_obj = state.get("world")
            if isinstance(world_obj, World):
                self.world_repo.save(cast(World, copy.deepcopy(world_obj)))

        if "character_repo:_characters" in state and hasattr(self.character_repo, "_characters"):
            setattr(self.character_repo, "_characters", copy.deepcopy(state["character_repo:_characters"]))
        else:
            characters = state.get("characters")
            if isinstance(characters, list):
                for character in copy.deepcopy(characters):
                    self.character_repo.save(character)

        if "character_repo:_progression_unlocks" in state and hasattr(self.character_repo, "_progression_unlocks"):
            setattr(
                self.character_repo,
                "_progression_unlocks",
                copy.deepcopy(state["character_repo:_progression_unlocks"]),
            )

        if self.entity_repo is not None:
            for attr in ("_entities", "_by_location"):
                key = f"entity_repo:{attr}"
                if key in state and hasattr(self.entity_repo, attr):
                    setattr(self.entity_repo, attr, copy.deepcopy(state[key]))

        if self.faction_repo is not None and "faction_repo:_factions" in state and hasattr(self.faction_repo, "_factions"):
            setattr(self.faction_repo, "_factions", copy.deepcopy(state["faction_repo:_factions"]))

    @staticmethod
    def _npc_greeting(npc_name: str, temperament: str, disposition: int) -> str:
        if disposition >= 50:
            return f"{npc_name} smiles. 'You're a welcome sight.'"
        if disposition <= -50:
            return f"{npc_name} narrows their eyes. 'State your business and move on.'"
        tone = {
            "warm": "'Welcome back. Need anything from the inn?'",
            "stern": "'Report quick. We keep watch rotations tight.'",
            "curious": "'You've seen the old roads too? Tell me what you found.'",
            "cynical": "'Information has a price. Speak.'",
        }.get(temperament, "'Yes?'")
        return f"{npc_name} says {tone}"

    @staticmethod
    def _coerce_int(value: object, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except Exception:
                return int(default)
        return int(default)

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
        combat_service = self.combat_service
        if combat_service:
            world_turn = int(getattr(world, "current_turn", 0) or 0)
            seed = derive_seed(
                namespace="combat.resolve.legacy_explore",
                context={
                    "player_id": int(character.id or 0),
                    "enemy_id": int(monster.id or 0),
                    "world_turn": world_turn,
                    "location_id": int(character.location_id or 0),
                    "terrain": str(getattr(location, "biome", "open") if location else "open"),
                },
            )
            combat_service.set_seed(seed)
            xp_before = int(getattr(character, "xp", 0) or 0)

            def _auto_choose_action(options: list[str], player_state: Character, _enemy: Entity, _round_no: int, _scene: dict):
                if "Use Item" in options and int(getattr(player_state, "hp_current", 0) or 0) <= max(1, int(getattr(player_state, "hp_max", 1) or 1) // 2):
                    usable = combat_service.list_usable_items(player_state)
                    if usable:
                        return "Use Item", usable[0]
                if "Cast Spell" in options and (getattr(player_state, "known_spells", None) or []):
                    known = list(getattr(player_state, "known_spells", []) or [])
                    if known:
                        return "Cast Spell", "".join(ch if ch.isalnum() or ch == " " else "-" for ch in str(known[0]).lower()).replace(" ", "-")
                if "Rage Attack" in options:
                    return "Rage Attack"
                return "Attack"

            combat_result = combat_service.fight_turn_based(
                character,
                monster,
                _auto_choose_action,
                scene={
                    "distance": "close",
                    "terrain": str(getattr(location, "biome", "open") if location else "open"),
                    "surprise": "none",
                    "weather": str(
                        self._world_immersion_state(
                            world,
                            biome_name=str(getattr(location, "biome", "") or ""),
                        ).get("weather", "Unknown")
                    ),
                },
            )

            character.hp_current = int(getattr(combat_result.player, "hp_current", character.hp_current))
            character.alive = bool(getattr(combat_result.player, "alive", character.alive))
            character.inventory = list(getattr(combat_result.player, "inventory", character.inventory) or [])
            character.flags = dict(getattr(combat_result.player, "flags", character.flags) or {})
            character.spell_slots_current = int(getattr(combat_result.player, "spell_slots_current", getattr(character, "spell_slots_current", 0)) or 0)
            character.xp = xp_before

            if combat_result.fled:
                retreat_note = self._apply_mid_combat_retreat_bargaining_hook(
                    character=character,
                    world=world,
                    world_turn=int(world_turn),
                    enemy_factions=[str(getattr(monster, "faction_id", "") or "").strip().lower()],
                    fled=True,
                    context_key="explore",
                )
                if retreat_note:
                    self.character_repo.save(character)
                    if self.world_repo:
                        self.world_repo.save(world)
                    return f"You disengage and escape the encounter. {retreat_note}".strip()
                return "You disengage and escape the encounter."

            if combat_result.player_won or int(getattr(combat_result.enemy, "hp_current", 0) or 0) <= 0:
                reward = self.apply_encounter_reward_intent(character, monster)
                self._apply_post_combat_morale_consequence(
                    world=world,
                    character_id=int(getattr(character, "id", 0) or 0),
                    world_turn=int(getattr(world, "current_turn", 0) or 0),
                    allies_won=True,
                    fled=False,
                    enemy_factions=[str(getattr(monster, "faction_id", "") or "").strip().lower()],
                    context_key="explore",
                )
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
                    f"You defeat {monster.name}{faction_note}. "
                    f"(+{reward.xp_gain} XP, +{reward.money_gain} gold){progression_suffix}"
                )

            if character.hp_current <= 0:
                character.alive = False
                threat = f" from the {monster.faction_id}" if monster.faction_id else ""
                return (
                    f"{monster.name}{threat} overwhelms you in combat. "
                    "You collapse and darkness closes in."
                )

            return (
                f"You skirmish with {monster.name} but neither side is finished. "
                f"You have {character.hp_current}/{character.hp_max} HP remaining."
            )

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

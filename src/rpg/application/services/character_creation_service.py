from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

from rpg.application.dtos import CharacterClassDetailView
from rpg.application.mappers.character_creation_mapper import to_character_class_detail_view
from rpg.application.services.balance_tables import DIFFICULTY_PRESET_PROFILES
from rpg.domain.models.character import CharacterAlignment
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.class_subclass import ClassSubclass
from rpg.domain.models.character_options import Background, DifficultyPreset, Race, Subrace
from rpg.domain.repositories import CharacterRepository, ClassRepository, FeatureRepository, LocationRepository
from rpg.domain.services.character_factory import ABILITY_ALIASES, create_new_character
from rpg.domain.services.subclass_catalog import resolve_subclass, subclasses_for_class
from rpg.domain.services.subclass_progression import subclass_tier_levels_for_class


ABILITY_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

FULL_TO_ABBR = {full: abbr.upper() for abbr, full in ABILITY_ALIASES.items()}


class CharacterCreationService:
    CREATION_REFERENCE_CATEGORIES = (
        ("races", "Races"),
        ("subraces", "Subraces"),
        ("classes", "Classes"),
        ("subclasses", "Subclasses"),
        ("spells", "Spells"),
        ("equipment", "Equipment"),
        ("backgrounds", "Backgrounds"),
        ("skills", "Skills"),
        ("languages", "Languages"),
        ("traits", "Traits"),
    )
    _RACE_FEATURE_SLUGS = {
        "dwarf": "feature.darkvision",
    }
    _ALIGNMENT_ORDER: tuple[str, ...] = (
        CharacterAlignment.LAWFUL_GOOD.value,
        CharacterAlignment.NEUTRAL_GOOD.value,
        CharacterAlignment.CHAOTIC_GOOD.value,
        CharacterAlignment.LAWFUL_NEUTRAL.value,
        CharacterAlignment.TRUE_NEUTRAL.value,
        CharacterAlignment.CHAOTIC_NEUTRAL.value,
        CharacterAlignment.LAWFUL_EVIL.value,
        CharacterAlignment.NEUTRAL_EVIL.value,
        CharacterAlignment.CHAOTIC_EVIL.value,
    )
    _STARTING_GOLD_SPEC_BY_CLASS: dict[str, str] = {
        "artificer": "5d4x10",
        "barbarian": "2d4x10",
        "bard": "5d4x10",
        "cleric": "5d4x10",
        "druid": "2d4x10",
        "fighter": "5d4x10",
        "monk": "5d4",
        "paladin": "5d4x10",
        "ranger": "5d4x10",
        "rogue": "4d4x10",
        "sorcerer": "3d4x10",
        "warlock": "4d4x10",
        "wizard": "4d4x10",
    }
    _EQUIPMENT_PACKAGE_BY_CLASS: dict[str, list[dict[str, object]]] = {
        "fighter": [
            {
                "id": "fighter_chain_mail",
                "label": "(A) Chain Mail + Longsword + Shield",
                "items": ["Chain Mail", "Longsword", "Shield"],
            },
            {
                "id": "fighter_leather_bow",
                "label": "(B) Leather Armor + Longbow + Arrows x20",
                "items": ["Leather Armor", "Longbow", "Arrows x20"],
            },
        ],
        "wizard": [
            {
                "id": "wizard_quarterstaff",
                "label": "(A) Quarterstaff + Spellbook + Component Pouch",
                "items": ["Quarterstaff", "Spellbook", "Component Pouch"],
            },
            {
                "id": "wizard_dagger_focus",
                "label": "(B) Dagger + Spellbook + Arcane Focus",
                "items": ["Dagger", "Spellbook", "Arcane Focus"],
            },
        ],
        "cleric": [
            {
                "id": "cleric_mace_shield",
                "label": "(A) Mace + Shield + Chain Shirt + Holy Symbol",
                "items": ["Mace", "Shield", "Chain Shirt", "Holy Symbol"],
            },
            {
                "id": "cleric_warhammer_scale",
                "label": "(B) Warhammer + Scale Mail + Holy Symbol",
                "items": ["Warhammer", "Scale Mail", "Holy Symbol"],
            },
        ],
    }
    _CLASS_LEVEL1_SPELL_REQUIREMENTS: dict[str, dict[str, int]] = {
        "artificer": {"cantrips": 2, "spells": 2},
        "bard": {"cantrips": 2, "spells": 4},
        "cleric": {"cantrips": 3, "spells": 2},
        "druid": {"cantrips": 2, "spells": 2},
        "paladin": {"cantrips": 0, "spells": 1},
        "ranger": {"cantrips": 0, "spells": 1},
        "sorcerer": {"cantrips": 4, "spells": 2},
        "warlock": {"cantrips": 2, "spells": 2},
        "wizard": {"cantrips": 3, "spells": 6},
    }
    _RACE_SPELLCASTING_GRANTS: dict[str, dict[str, object]] = {
        "high elf": {
            "bonus_cantrip_choices": 1,
            "bonus_cantrip_class": "wizard",
            "granted_cantrips": [],
            "granted_spells": [],
        },
        "tiefling": {
            "bonus_cantrip_choices": 0,
            "bonus_cantrip_class": "",
            "granted_cantrips": ["Thaumaturgy"],
            "granted_spells": [],
        },
    }
    _UNIFIED_SPELLS_CACHE: list[dict[str, object]] | None = None
    _BACKGROUND_EXTRA_CHOICES: dict[str, dict[str, object]] = {
        "temple envoy": {
            "tool_choices": 1,
            "tool_pool": ["Calligrapher's Supplies", "Herbalism Kit", "Musical Instrument"],
            "language_choices": 1,
            "language_pool": ["Celestial", "Draconic", "Elvish", "Sylvan"],
        },
        "lorekeeper": {
            "tool_choices": 1,
            "tool_pool": ["Calligrapher's Supplies", "Cartographer's Tools", "Navigator's Tools"],
            "language_choices": 2,
            "language_pool": ["Draconic", "Elvish", "Dwarvish", "Gnomish", "Infernal"],
        },
        "night runner": {
            "tool_choices": 1,
            "tool_pool": ["Thieves' Tools", "Disguise Kit", "Forgery Kit", "Gaming Set"],
            "language_choices": 1,
            "language_pool": ["Thieves' Cant", "Undercommon", "Goblin", "Elvish"],
        },
        "forgehand": {
            "tool_choices": 1,
            "tool_pool": ["Smith's Tools", "Mason's Tools", "Tinker's Tools", "Alchemist's Supplies"],
            "language_choices": 1,
            "language_pool": ["Dwarvish", "Giant", "Draconic"],
        },
        "frontier tender": {
            "tool_choices": 1,
            "tool_pool": ["Herbalism Kit", "Leatherworker's Tools", "Woodcarver's Tools"],
            "language_choices": 1,
            "language_pool": ["Elvish", "Sylvan", "Giant", "Orc"],
        },
        "watch sentinel": {
            "tool_choices": 1,
            "tool_pool": ["Gaming Set", "Calligrapher's Supplies", "Navigator's Tools"],
            "language_choices": 1,
            "language_pool": ["Dwarvish", "Draconic", "Orc", "Common Sign"],
        },
    }
    _BACKGROUND_PERSONALITY_TABLES: dict[str, dict[str, list[str]]] = {
        "temple envoy": {
            "traits": [
                "I quote old rites for everyday advice.",
                "I treat strangers with patient courtesy.",
                "I keep careful notes about omens and signs.",
                "I speak softly, but with conviction.",
            ],
            "ideals": ["Mercy", "Duty", "Tradition", "Hope"],
            "bonds": [
                "My temple trust must be restored.",
                "I owe my life to a wandering priest.",
                "A sacred relic was stolen and I will recover it.",
            ],
            "flaws": [
                "I am judgmental toward those without faith.",
                "I struggle to forgive old insults.",
                "I avoid hard choices until too late.",
            ],
        },
        "lorekeeper": {
            "traits": [
                "I collect stories as if they were treasure.",
                "I cannot resist correcting bad history.",
                "I always carry ink, quills, and spare paper.",
                "I ask too many questions in dangerous places.",
            ],
            "ideals": ["Knowledge", "Truth", "Discovery", "Legacy"],
            "bonds": [
                "A lost archive map is hidden in my journal.",
                "My mentor vanished while researching forbidden lore.",
                "I swore to preserve stories no one else remembers.",
            ],
            "flaws": [
                "I underestimate practical dangers.",
                "I can be arrogant about my learning.",
                "I hoard secrets even from allies.",
            ],
        },
        "night runner": {
            "traits": [
                "I always know at least one way out.",
                "I grin when plans get risky.",
                "I trust silence more than promises.",
                "I never sit with my back to a door.",
            ],
            "ideals": ["Freedom", "Survival", "Opportunity", "Independence"],
            "bonds": [
                "My old crew still watches from the shadows.",
                "I protect the district that raised me.",
                "A debt to a crime boss hangs over me.",
            ],
            "flaws": [
                "I lie when the truth would be easier.",
                "I assume betrayal before trust.",
                "I overreach when stakes are high.",
            ],
        },
    }
    _FIGHTING_STYLE_OPTIONS: tuple[str, ...] = (
        "Archery",
        "Defence",
        "Dueling",
        "Great Weapon Fighting",
        "Protection",
    )
    _DRACONIC_ANCESTRY_OPTIONS: tuple[str, ...] = (
        "Black (Acid)",
        "Blue (Lightning)",
        "Brass (Fire)",
        "Bronze (Lightning)",
        "Copper (Acid)",
        "Gold (Fire)",
        "Green (Poison)",
        "Red (Fire)",
        "Silver (Cold)",
        "White (Cold)",
    )
    _LEVEL1_FEAT_OPTIONS: tuple[dict[str, str], ...] = (
        {"slug": "alert", "label": "Alert"},
        {"slug": "athlete", "label": "Athlete"},
        {"slug": "durable", "label": "Durable"},
        {"slug": "tough", "label": "Tough"},
        {"slug": "war_caster", "label": "War Caster"},
    )

    def __init__(
        self,
        character_repo: CharacterRepository,
        class_repo: ClassRepository,
        location_repo: LocationRepository,
        open5e_client=None,
        name_generator=None,
        feature_repo: FeatureRepository | None = None,
    ):
        self.character_repo = character_repo
        self.class_repo = class_repo
        self.location_repo = location_repo
        self.name_generator = name_generator
        self._name_generation_sequence = 0
        self.feature_repo = feature_repo
        self.backgrounds: List[Background] = self._default_backgrounds()
        self.difficulties: List[DifficultyPreset] = self._default_difficulties()
        self.starting_equipment: Dict[str, List[str]] = self._default_starting_equipment()
        self.races: List[Race] = []
        self.subraces_by_race: Dict[str, List[Subrace]] = self._default_subraces()
        self.creation_reference: Dict[str, List[str]] = self._default_creation_reference()

        if open5e_client is None:
            self.races = self._default_races()
        else:
            try:
                self.races = self._load_races(open5e_client)
                self.subraces_by_race = self._load_subraces(open5e_client)
                self.creation_reference = self._load_creation_reference(open5e_client, races=self.races)
            finally:
                try:
                    open5e_client.close()
                except Exception:
                    pass

        if not self.races:
            self.races = self._default_races()
        if not self.subraces_by_race:
            self.subraces_by_race = self._default_subraces()
        if not self.creation_reference:
            self.creation_reference = self._default_creation_reference()

    def list_classes(self) -> list[CharacterClass]:
        return self.class_repo.list_playable()

    def list_races(self) -> List[Race]:
        return list(self.races)

    def list_playable_races(self) -> List[Race]:
        return [race for race in self.races if bool(getattr(race, "playable", True))]

    def list_backgrounds(self) -> List[Background]:
        return list(self.backgrounds)

    def list_subraces_for_race(self, race: Race | None = None, race_name: str | None = None) -> List[Subrace]:
        base_name = race_name or (race.name if race else "")
        if not base_name:
            return []
        return list(self.subraces_by_race.get(base_name.strip().lower(), []))

    def list_difficulties(self) -> List[DifficultyPreset]:
        return list(self.difficulties)

    def list_alignments(self) -> List[str]:
        return list(self._ALIGNMENT_ORDER)

    def alignment_option_labels(self) -> List[str]:
        labels: List[str] = []
        for slug in self.list_alignments():
            labels.append(str(slug).replace("_", " ").title())
        return labels

    def list_class_names(self) -> List[str]:
        return [cls.name for cls in self.list_classes()]

    def list_subclasses_for_class(self, class_slug_or_name: str | None) -> List[ClassSubclass]:
        return list(subclasses_for_class(class_slug_or_name))

    def subclass_selection_level_for_class(self, class_slug_or_name: str | None) -> int:
        levels = tuple(subclass_tier_levels_for_class(class_slug_or_name) or ())
        if not levels:
            return 3
        return max(1, int(levels[0]))

    def list_creation_reference_categories(self) -> List[str]:
        return [label for _, label in self.CREATION_REFERENCE_CATEGORIES]

    def list_creation_reference_items(self, category_slug: str, limit: int = 20) -> List[str]:
        key = str(category_slug or "").strip().lower()
        rows = list(self.creation_reference.get(key, []))
        if limit > 0:
            rows = rows[: int(limit)]
        return rows

    def list_background_choice_options(self, background_name: str | None) -> dict[str, object]:
        key = str(background_name or "").strip().lower()
        payload = dict(self._BACKGROUND_EXTRA_CHOICES.get(key, {}))
        return {
            "tool_choices": int(payload.get("tool_choices", 0) or 0),
            "tool_pool": [str(row) for row in list(payload.get("tool_pool", []) or []) if str(row).strip()],
            "language_choices": int(payload.get("language_choices", 0) or 0),
            "language_pool": [str(row) for row in list(payload.get("language_pool", []) or []) if str(row).strip()],
        }

    def list_background_personality_tables(self, background_name: str | None) -> dict[str, list[str]]:
        key = str(background_name or "").strip().lower()
        payload = dict(self._BACKGROUND_PERSONALITY_TABLES.get(key, {}))
        return {
            "traits": [str(row) for row in list(payload.get("traits", []) or []) if str(row).strip()],
            "ideals": [str(row) for row in list(payload.get("ideals", []) or []) if str(row).strip()],
            "bonds": [str(row) for row in list(payload.get("bonds", []) or []) if str(row).strip()],
            "flaws": [str(row) for row in list(payload.get("flaws", []) or []) if str(row).strip()],
        }

    def roll_background_personality(
        self,
        background_name: str | None,
        *,
        rng: random.Random | None = None,
    ) -> dict[str, str]:
        tables = self.list_background_personality_tables(background_name)
        roller = rng or random.Random()

        def _pick(rows: list[str], fallback: str) -> str:
            if not rows:
                return fallback
            return str(rows[roller.randint(0, len(rows) - 1)])

        return {
            "trait": _pick(tables.get("traits", []), "I keep my own counsel."),
            "ideal": _pick(tables.get("ideals", []), "Balance"),
            "bond": _pick(tables.get("bonds", []), "I protect those who depend on me."),
            "flaw": _pick(tables.get("flaws", []), "I take on too much alone."),
        }

    def list_level1_class_feature_choices(self, class_slug: str) -> dict[str, object]:
        class_key = str(class_slug or "").strip().lower()
        if class_key == "fighter":
            return {
                "fighting_style": list(self._FIGHTING_STYLE_OPTIONS),
            }
        if class_key == "rogue":
            skill_rows = list(self.creation_reference.get("skills", []) or [])
            if not skill_rows:
                skill_rows = [
                    "Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception",
                    "History", "Insight", "Intimidation", "Investigation", "Medicine",
                    "Nature", "Perception", "Performance", "Persuasion", "Religion",
                    "Sleight of Hand", "Stealth", "Survival",
                ]
            return {
                "expertise_count": 2,
                "expertise_pool": [str(row) for row in skill_rows if str(row).strip()],
            }
        if class_key == "sorcerer":
            return {
                "draconic_ancestry": list(self._DRACONIC_ANCESTRY_OPTIONS),
            }
        return {}

    @classmethod
    def list_level1_feat_options(cls) -> list[dict[str, str]]:
        return [dict(row) for row in cls._LEVEL1_FEAT_OPTIONS]

    @staticmethod
    def is_feat_selection_eligible(race_name: str | None, subrace_name: str | None = None) -> bool:
        race_key = str(race_name or "").strip().lower()
        subrace_key = str(subrace_name or "").strip().lower()
        if "variant human" in subrace_key:
            return True
        if "custom lineage" in race_key or "custom lineage" in subrace_key:
            return True
        return False

    def race_option_labels(self) -> List[str]:
        labels: List[str] = []
        for race in self.list_playable_races():
            labels.append(
                f"{race.name:<12} | {self._format_bonus_line(race.bonuses):<18} | "
                f"Speed {race.speed:<2} | {self._format_trait_summary(race.traits)}"
            )
        return labels

    def subrace_option_labels(self, race: Race | None) -> List[str]:
        labels: List[str] = []
        for subrace in self.list_subraces_for_race(race=race):
            labels.append(
                f"{subrace.name:<14} | {self._format_bonus_line(subrace.bonuses):<18} | "
                f"Speed +{subrace.speed_bonus:<2} | {self._format_trait_summary(subrace.traits)}"
            )
        return labels

    def background_option_labels(self) -> List[str]:
        labels: List[str] = []
        for background in self.list_backgrounds():
            profs = ", ".join(background.proficiencies) if background.proficiencies else "No profs"
            feature = background.feature or "No feature"
            labels.append(f"{background.name:<10} | {profs:<25} | {feature}")
        return labels

    def difficulty_option_labels(self) -> List[str]:
        return [
            f"{mode.name:<12} | {mode.description}"
            for mode in self.list_difficulties()
        ]

    @staticmethod
    def _normalize_race_spell_key(race_name: str | None, subrace_name: str | None = None) -> list[str]:
        race_key = str(race_name or "").strip().lower()
        subrace_key = str(subrace_name or "").strip().lower()
        keys: list[str] = []
        if subrace_key:
            keys.append(subrace_key)
        if race_key:
            keys.append(race_key)
        if "(" in race_key and ")" in race_key:
            fragment = race_key.split("(", 1)[1].split(")", 1)[0].strip()
            if fragment:
                keys.append(fragment)
        return keys

    def race_spellcasting_grants(self, race_name: str | None, subrace_name: str | None = None) -> dict[str, object]:
        keys = self._normalize_race_spell_key(race_name, subrace_name)
        for key in keys:
            payload = self._RACE_SPELLCASTING_GRANTS.get(key)
            if payload is None:
                continue
            return {
                "bonus_cantrip_choices": int(payload.get("bonus_cantrip_choices", 0) or 0),
                "bonus_cantrip_class": str(payload.get("bonus_cantrip_class", "") or "").strip().lower(),
                "granted_cantrips": [str(row) for row in list(payload.get("granted_cantrips", []) or []) if str(row).strip()],
                "granted_spells": [str(row) for row in list(payload.get("granted_spells", []) or []) if str(row).strip()],
            }
        return {
            "bonus_cantrip_choices": 0,
            "bonus_cantrip_class": "",
            "granted_cantrips": [],
            "granted_spells": [],
        }

    def get_starting_equipment_options(self, class_slug: str) -> list[dict[str, object]]:
        class_key = str(class_slug or "").strip().lower()
        packages = list(self._EQUIPMENT_PACKAGE_BY_CLASS.get(class_key, []))
        if not packages:
            default_items = list(self.starting_equipment.get(class_key, self.starting_equipment.get("_default", [])))
            packages = [
                {
                    "id": f"{class_key}_default",
                    "label": "Use standard class equipment",
                    "items": default_items,
                }
            ]

        gold_spec = str(self._STARTING_GOLD_SPEC_BY_CLASS.get(class_key, "4d4x10") or "4d4x10")
        packages.append(
            {
                "id": "starting_gold",
                "label": f"Use starting gold ({gold_spec}) and buy gear later",
                "items": [],
                "gold_spec": gold_spec,
            }
        )
        return packages

    @staticmethod
    def _roll_gold_from_spec(spec: str, rng: random.Random | None = None) -> int:
        source = str(spec or "").strip().lower().replace(" ", "")
        if "d" not in source:
            try:
                return max(0, int(source))
            except Exception:
                return 0
        parts = source.split("d", 1)
        count = int(parts[0] or 1)
        tail = parts[1]
        multiplier = 1
        if "x" in tail:
            die_raw, mult_raw = tail.split("x", 1)
            die = int(die_raw or 4)
            multiplier = max(1, int(mult_raw or 1))
        else:
            die = int(tail or 4)
        roller = rng or random.Random()
        total = 0
        for _ in range(max(1, count)):
            total += roller.randint(1, max(1, die))
        return max(0, total * multiplier)

    def resolve_starting_equipment_choice(
        self,
        class_slug: str,
        choice_id: str,
        *,
        rng: random.Random | None = None,
    ) -> dict[str, object]:
        class_key = str(class_slug or "").strip().lower()
        choice_key = str(choice_id or "").strip().lower()
        options = self.get_starting_equipment_options(class_key)
        selected = next((row for row in options if str(row.get("id", "")).strip().lower() == choice_key), None)
        if selected is None:
            selected = options[0]

        if str(selected.get("id", "")) == "starting_gold":
            spec = str(selected.get("gold_spec", self._STARTING_GOLD_SPEC_BY_CLASS.get(class_key, "4d4x10")) or "4d4x10")
            return {
                "mode": "starting_gold",
                "items": [],
                "gold_bonus": self._roll_gold_from_spec(spec, rng=rng),
                "label": str(selected.get("label", "Starting gold") or "Starting gold"),
                "gold_spec": spec,
            }

        return {
            "mode": "standard_equipment",
            "items": [str(row) for row in list(selected.get("items", []) or []) if str(row).strip()],
            "gold_bonus": 0,
            "label": str(selected.get("label", "Standard equipment") or "Standard equipment"),
            "gold_spec": "",
        }

    @classmethod
    def _load_unified_spells_rows(cls) -> list[dict[str, object]]:
        if cls._UNIFIED_SPELLS_CACHE is not None:
            return list(cls._UNIFIED_SPELLS_CACHE)
        path = Path(__file__).resolve().parents[4] / "data" / "spells" / "unified_spells.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cls._UNIFIED_SPELLS_CACHE = []
            return []
        spells = payload.get("spells") if isinstance(payload, dict) else []
        if not isinstance(spells, list):
            cls._UNIFIED_SPELLS_CACHE = []
            return []
        rows: list[dict[str, object]] = []
        for row in spells:
            if isinstance(row, dict):
                rows.append(dict(row))
        cls._UNIFIED_SPELLS_CACHE = rows
        return list(rows)

    @staticmethod
    def _row_classes(row: dict[str, object]) -> set[str]:
        raw = str(row.get("classes", "") or "")
        parts = [part.strip().lower() for part in raw.replace(";", ",").split(",") if part.strip()]
        return set(parts)

    def list_starting_spell_options(
        self,
        class_slug: str,
        *,
        race_name: str | None = None,
        subrace_name: str | None = None,
    ) -> dict[str, object]:
        class_key = str(class_slug or "").strip().lower()
        class_profile = dict(self._CLASS_LEVEL1_SPELL_REQUIREMENTS.get(class_key, {"cantrips": 0, "spells": 0}))
        race_profile = self.race_spellcasting_grants(race_name, subrace_name)

        class_name = class_key.replace("_", " ").strip().title()
        rows = self._load_unified_spells_rows()
        cantrip_pool: list[str] = []
        spell_pool: list[str] = []
        seen_cantrips: set[str] = set()
        seen_spells: set[str] = set()
        for row in rows:
            if class_name.lower() not in self._row_classes(row):
                continue
            spell_name = str(row.get("name", "") or "").strip()
            if not spell_name:
                continue
            try:
                level = int(row.get("level_int", 0) or 0)
            except Exception:
                level = 0
            key = spell_name.lower()
            if level <= 0 and key not in seen_cantrips:
                seen_cantrips.add(key)
                cantrip_pool.append(spell_name)
            elif level == 1 and key not in seen_spells:
                seen_spells.add(key)
                spell_pool.append(spell_name)

        bonus_class = str(race_profile.get("bonus_cantrip_class", "") or "").strip().replace("_", " ").title()
        if bonus_class:
            for row in rows:
                if bonus_class.lower() not in self._row_classes(row):
                    continue
                spell_name = str(row.get("name", "") or "").strip()
                if not spell_name:
                    continue
                try:
                    level = int(row.get("level_int", 0) or 0)
                except Exception:
                    level = 0
                key = spell_name.lower()
                if level <= 0 and key not in seen_cantrips:
                    seen_cantrips.add(key)
                    cantrip_pool.append(spell_name)

        cantrip_pool.sort()
        spell_pool.sort()

        required_cantrips = int(class_profile.get("cantrips", 0) or 0) + int(race_profile.get("bonus_cantrip_choices", 0) or 0)
        required_spells = int(class_profile.get("spells", 0) or 0)
        return {
            "class_slug": class_key,
            "required_cantrips": max(0, required_cantrips),
            "required_spells": max(0, required_spells),
            "cantrip_pool": cantrip_pool,
            "spell_pool": spell_pool,
            "granted_cantrips": list(race_profile.get("granted_cantrips", []) or []),
            "granted_spells": list(race_profile.get("granted_spells", []) or []),
            "spellcasting": bool(required_cantrips or required_spells or race_profile.get("granted_cantrips") or race_profile.get("granted_spells")),
        }

    @staticmethod
    def _normalize_unique_spell_names(rows: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for row in list(rows or []):
            text = str(row or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            normalized.append(text)
        return normalized

    def resolve_starting_spell_selection(
        self,
        profile: dict[str, object],
        *,
        selected_cantrips: list[str] | None = None,
        selected_spells: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        granted_cantrips = self._normalize_unique_spell_names(list(profile.get("granted_cantrips", []) or []))
        granted_spells = self._normalize_unique_spell_names(list(profile.get("granted_spells", []) or []))
        pool_cantrips = self._normalize_unique_spell_names(list(profile.get("cantrip_pool", []) or []))
        pool_spells = self._normalize_unique_spell_names(list(profile.get("spell_pool", []) or []))
        required_cantrips = max(0, int(profile.get("required_cantrips", 0) or 0))
        required_spells = max(0, int(profile.get("required_spells", 0) or 0))

        cantrips: list[str] = list(granted_cantrips)
        spells: list[str] = list(granted_spells)

        selected_cantrip_rows = self._normalize_unique_spell_names(list(selected_cantrips or []))
        selected_spell_rows = self._normalize_unique_spell_names(list(selected_spells or []))

        for row in selected_cantrip_rows:
            if row in pool_cantrips and row not in cantrips:
                cantrips.append(row)
            if len(cantrips) >= required_cantrips:
                break
        for row in pool_cantrips:
            if row not in cantrips:
                cantrips.append(row)
            if len(cantrips) >= required_cantrips:
                break

        for row in selected_spell_rows:
            if row in pool_spells and row not in spells:
                spells.append(row)
            if len(spells) >= required_spells:
                break
        for row in pool_spells:
            if row not in spells:
                spells.append(row)
            if len(spells) >= required_spells:
                break

        return cantrips[:required_cantrips] if required_cantrips > 0 else cantrips, spells[:required_spells] if required_spells > 0 else spells

    def requires_starting_spell_selection(
        self,
        class_slug: str,
        *,
        race_name: str | None = None,
        subrace_name: str | None = None,
    ) -> bool:
        profile = self.list_starting_spell_options(class_slug, race_name=race_name, subrace_name=subrace_name)
        return bool(profile.get("spellcasting", False))

    def class_detail_view(self, chosen_class: CharacterClass) -> CharacterClassDetailView:
        recommended = self.format_attribute_line(chosen_class.base_attributes)
        return to_character_class_detail_view(
            class_name=chosen_class.name,
            class_slug=chosen_class.slug,
            primary_ability=chosen_class.primary_ability,
            hit_die=chosen_class.hit_die,
            recommended_line=recommended,
        )

    def format_attribute_line(self, attrs: Dict[str, int]) -> str:
        parts: List[str] = []
        for abbr in ABILITY_ORDER:
            value = attrs.get(abbr, attrs.get(abbr.lower()))
            if value is None:
                full = ABILITY_ALIASES.get(abbr.lower(), abbr.lower())
                value = attrs.get(full)
            if value is not None:
                parts.append(f"{abbr} {value}")
        if not parts and attrs:
            sample_keys = list(attrs.keys())[:3]
            parts = [f"{k.upper()} {attrs[k]}" for k in sample_keys]
        return " / ".join(parts) if parts else "Balanced stats"

    def point_buy_cost(self, scores: Dict[str, int]) -> int:
        return self._point_buy_cost(scores)

    def create_character(
        self,
        name: str,
        class_index: int,
        ability_scores: Dict[str, int] | None = None,
        race: Race | None = None,
        subrace: Subrace | None = None,
        background: Background | None = None,
        difficulty: DifficultyPreset | None = None,
        subclass_slug: str | None = None,
        alignment: str | None = None,
        starting_equipment_override: list[str] | None = None,
        starting_gold_bonus: int = 0,
        selected_cantrips: list[str] | None = None,
        selected_known_spells: list[str] | None = None,
        selected_tool_proficiencies: list[str] | None = None,
        selected_languages: list[str] | None = None,
        personality_profile: dict[str, str] | None = None,
        class_feature_choices: dict[str, object] | None = None,
        selected_feat_slug: str | None = None,
        generated_name_gender: str | None = None,
    ) -> "Character":
        provided_name = (name or "").strip()
        if not provided_name:
            name = self.suggest_generated_name(
                race_name=race.name if race else None,
                class_index=class_index,
                gender=generated_name_gender,
            )
        else:
            name = self.sanitize_name(name)
        classes = self.class_repo.list_playable()
        if class_index < 0 or class_index >= len(classes):
            raise ValueError("Invalid class selection.")
        chosen = classes[class_index]

        if ability_scores is None:
            ability_scores = self.standard_array_for_class(chosen)

        effective_race = self._compose_race_with_subrace(race, subrace)
        if effective_race is not None and not bool(getattr(effective_race, "playable", True)):
            raise ValueError("Selected race is not playable.")

        starting_equipment = self.starting_equipment.get(
            chosen.slug, self.starting_equipment.get("_default", [])
        )
        character = create_new_character(
            name,
            chosen,
            ability_scores=ability_scores,
            race=effective_race,
            background=background,
            difficulty=difficulty,
            starting_equipment=starting_equipment,
            alignment=CharacterAlignment.normalize(alignment),
        )

        if starting_equipment_override is not None:
            character.inventory = [str(item) for item in list(starting_equipment_override or []) if str(item).strip()]

        if int(starting_gold_bonus or 0) > 0:
            character.money = int(getattr(character, "money", 0) or 0) + int(starting_gold_bonus)

        if selected_cantrips is not None or selected_known_spells is not None:
            spell_profile = self.list_starting_spell_options(
                chosen.slug,
                race_name=getattr(effective_race, "name", "") if effective_race is not None else "",
                subrace_name=getattr(subrace, "name", "") if subrace is not None else "",
            )
            resolved_cantrips, resolved_spells = self.resolve_starting_spell_selection(
                spell_profile,
                selected_cantrips=list(selected_cantrips or []),
                selected_spells=list(selected_known_spells or []),
            )
            character.cantrips = list(resolved_cantrips)
            character.known_spells = list(resolved_spells)

        if selected_tool_proficiencies:
            tools = self._normalize_unique_spell_names([str(row) for row in list(selected_tool_proficiencies or [])])
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            flags["tool_proficiencies"] = list(tools)
            existing = list(getattr(character, "proficiencies", []) or [])
            for tool in tools:
                marker = f"Tool: {tool}"
                if marker not in existing:
                    existing.append(marker)
            character.proficiencies = existing

        if selected_languages:
            languages = self._normalize_unique_spell_names([str(row) for row in list(selected_languages or [])])
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            flags["languages"] = list(languages)

        if isinstance(personality_profile, dict) and personality_profile:
            trait = str(personality_profile.get("trait", "") or "").strip()
            ideal = str(personality_profile.get("ideal", "") or "").strip()
            bond = str(personality_profile.get("bond", "") or "").strip()
            flaw = str(personality_profile.get("flaw", "") or "").strip()
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            flags["personality_profile"] = {
                "trait": trait,
                "ideal": ideal,
                "bond": bond,
                "flaw": flaw,
            }

        self._apply_level1_class_feature_choices(
            character,
            class_slug=chosen.slug,
            choices=dict(class_feature_choices or {}),
        )
        self._apply_level1_feat_choice(
            character,
            race_name=getattr(effective_race, "name", "") if effective_race is not None else "",
            subrace_name=getattr(subrace, "name", "") if subrace is not None else "",
            feat_slug=selected_feat_slug,
        )

        selected_subclass = resolve_subclass(chosen.slug, subclass_slug)
        if subclass_slug and selected_subclass is None:
            raise ValueError("Invalid subclass selection.")
        if selected_subclass is not None and int(self.subclass_selection_level_for_class(chosen.slug)) > 1:
            raise ValueError("Subclass cannot be selected at level 1 for this class.")
        if selected_subclass is not None:
            flags = getattr(character, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                character.flags = flags
            flags["subclass_slug"] = selected_subclass.slug
            flags["subclass_name"] = selected_subclass.name
            flags["subclass_class_slug"] = chosen.slug

        starting_location = self.location_repo.get_starting_location()
        character.location_id = starting_location.id if starting_location else None

        self.character_repo.create(character, character.location_id or 0)

        if self.feature_repo is not None and effective_race is not None:
            race_slug = str(getattr(effective_race, "name", "")).strip().lower()
            feature_slug = self._RACE_FEATURE_SLUGS.get(race_slug)
            if feature_slug and character.id is not None:
                try:
                    self.feature_repo.grant_feature_by_slug(character.id, feature_slug)
                except Exception:
                    pass

        return character

    def _apply_level1_class_feature_choices(
        self,
        character,
        *,
        class_slug: str,
        choices: dict[str, object],
    ) -> None:
        if not isinstance(choices, dict) or not choices:
            return
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        class_key = str(class_slug or "").strip().lower()

        if class_key == "fighter":
            style = str(choices.get("fighting_style", "") or "").strip()
            if style and style in self._FIGHTING_STYLE_OPTIONS:
                flags["fighting_style"] = style
                style_key = style.lower()
                if style_key == "defence":
                    character.armour_class = int(getattr(character, "armour_class", 10) or 10) + 1
                elif style_key == "dueling":
                    character.attack_bonus = int(getattr(character, "attack_bonus", 0) or 0) + 1
                elif style_key == "archery":
                    character.attack_bonus = int(getattr(character, "attack_bonus", 0) or 0) + 1
                elif style_key == "great weapon fighting":
                    character.attack_max = int(getattr(character, "attack_max", 4) or 4) + 1
                elif style_key == "protection":
                    character.armour_class = int(getattr(character, "armour_class", 10) or 10) + 1

        if class_key == "rogue":
            expertise_rows = [str(row) for row in list(choices.get("expertise_skills", []) or []) if str(row).strip()]
            if expertise_rows:
                normalized = self._normalize_unique_spell_names(expertise_rows)[:2]
                flags["expertise_skills"] = list(normalized)
                training = flags.get("skill_training")
                if not isinstance(training, dict):
                    training = {}
                    flags["skill_training"] = training
                modifiers = training.get("modifiers")
                if not isinstance(modifiers, dict):
                    modifiers = {}
                    training["modifiers"] = modifiers
                for skill_label in normalized:
                    slug = str(skill_label).strip().lower().replace(" ", "_").replace("-", "_")
                    current = int(modifiers.get(slug, 0) or 0)
                    modifiers[slug] = max(current, 2)

        if class_key == "sorcerer":
            ancestry = str(choices.get("draconic_ancestry", "") or "").strip()
            if ancestry and ancestry in self._DRACONIC_ANCESTRY_OPTIONS:
                flags["draconic_ancestry"] = ancestry

    def _apply_level1_feat_choice(
        self,
        character,
        *,
        race_name: str,
        subrace_name: str,
        feat_slug: str | None,
    ) -> None:
        if not self.is_feat_selection_eligible(race_name, subrace_name):
            return
        slug = str(feat_slug or "").strip().lower()
        if not slug:
            return
        valid = {str(row.get("slug", "") or "").strip().lower() for row in self._LEVEL1_FEAT_OPTIONS}
        if slug not in valid:
            return
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        flags["level1_feat"] = slug

        if slug == "tough":
            character.hp_max = int(getattr(character, "hp_max", 1) or 1) + 2
            character.hp_current = int(getattr(character, "hp_current", 1) or 1) + 2
        elif slug == "durable":
            character.hp_max = int(getattr(character, "hp_max", 1) or 1) + 1
            character.hp_current = int(getattr(character, "hp_current", 1) or 1) + 1
        elif slug == "athlete":
            character.speed = int(getattr(character, "speed", 30) or 30) + 5
        elif slug == "alert":
            flags["initiative_bonus"] = int(flags.get("initiative_bonus", 0) or 0) + 1
        elif slug == "war_caster":
            flags["war_caster"] = True

    def standard_array_for_class(self, cls: CharacterClass) -> Dict[str, int]:
        primary_raw = cls.primary_ability or "STR"
        primary = ABILITY_ALIASES.get(primary_raw.lower(), primary_raw).upper()
        ordered = [primary] + [ability for ability in ABILITY_ORDER if ability != primary]
        allocation: Dict[str, int] = {}
        for ability, score in zip(ordered, STANDARD_ARRAY):
            allocation[ability] = score
        return allocation

    def roll_ability_scores(self, rng: random.Random | None = None) -> List[int]:
        rng = rng or random.Random()
        return [self._roll_4d6_drop_lowest(rng) for _ in range(6)]

    def validate_point_buy(self, scores: Dict[str, int], pool: int = 27) -> Dict[str, int]:
        normalized: Dict[str, int] = {ability: 8 for ability in ABILITY_ORDER}
        for key, raw_value in scores.items():
            canonical = ABILITY_ALIASES.get(key.lower(), key.lower()).upper()
            if canonical not in ABILITY_ORDER:
                continue
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                value = 8
            if value < 8 or value > 15:
                raise ValueError(f"{canonical} must be between 8 and 15.")
            normalized[canonical] = value

        cost = self._point_buy_cost(normalized)
        if cost > pool:
            raise ValueError(f"Point buy exceeds {pool} points (cost {cost}).")
        return normalized

    @staticmethod
    def _point_buy_cost(scores: Dict[str, int]) -> int:
        cost = 0
        for ability, value in scores.items():
            if ability.upper() not in ABILITY_ORDER:
                continue
            cost += POINT_BUY_COSTS.get(value, 0)
        return cost

    @staticmethod
    def _roll_4d6_drop_lowest(rng: random.Random) -> int:
        rolls = sorted([rng.randint(1, 6) for _ in range(4)], reverse=True)
        return sum(rolls[:3])

    def suggest_generated_name(
        self,
        race_name: str | None = None,
        class_index: int = 0,
        gender: str | None = None,
    ) -> str:
        if self.name_generator is None:
            return self.sanitize_name("")

        existing_count = 0
        try:
            existing_count = len(self.character_repo.list_all())
        except Exception:
            existing_count = 0

        safe_class_index = max(0, int(class_index or 0))
        self._name_generation_sequence = int(self._name_generation_sequence) + 1
        generated = self.name_generator.suggest_character_name(
            race_name=race_name,
            gender=gender,
            context={
                "class_index": safe_class_index,
                "existing_count": existing_count,
                "generation_index": int(self._name_generation_sequence),
            },
        )
        return self.sanitize_name(generated)

    @staticmethod
    def sanitize_name(raw: str, max_length: int = 20) -> str:
        trimmed = (raw or "").strip()
        cleaned = "".join(ch for ch in trimmed if ch.isprintable() and ch not in "\t\r\n")
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        return cleaned or "Nameless One"

    @staticmethod
    def _default_races() -> List[Race]:
        playable = [
            Race(name="Human", bonuses={key: 1 for key in ABILITY_ORDER}, speed=30, traits=["Versatile", "Adaptive"], playable=True),
            Race(name="Elf", bonuses={"DEX": 2, "INT": 1}, speed=30, traits=["Keen Senses", "Fey Ancestry"], playable=True),
            Race(name="Half-Elf", bonuses={"CHA": 2, "DEX": 1, "WIS": 1}, speed=30, traits=["Fey Ancestry", "Skill Versatility"], playable=True),
            Race(name="Dwarf", bonuses={"CON": 2, "WIS": 1}, speed=25, traits=["Darkvision", "Stonecunning"], playable=True),
            Race(name="Halfling", bonuses={"DEX": 2, "CHA": 1}, speed=25, traits=["Lucky", "Brave"], playable=True),
            Race(name="Half-Orc", bonuses={"STR": 2, "CON": 1}, speed=30, traits=["Relentless Endurance", "Savage Attacks"], playable=True),
            Race(name="Orc", bonuses={"STR": 2, "CON": 1}, speed=30, traits=["Aggressive", "Powerful Build"], playable=True),
            Race(name="Tiefling", bonuses={"CHA": 2, "INT": 1}, speed=30, traits=["Darkvision", "Hellish Resistance"], playable=True),
            Race(name="Dragonborn", bonuses={"STR": 2, "CHA": 1}, speed=30, traits=["Scaled Resilience", "Ancestral Breath"], playable=True),
        ]

        non_playable = [
            Race(name="Aarakocra", bonuses={"DEX": 2, "WIS": 1}, speed=50, traits=["Flight", "Talons"], playable=False),
            Race(name="Genasi", bonuses={"CON": 2}, speed=30, traits=["Elemental Heritage"], playable=False),
            Race(name="Gnome", bonuses={"INT": 2}, speed=25, traits=["Gnome Cunning"], playable=False),
            Race(name="Goblin", bonuses={"DEX": 2, "CON": 1}, speed=30, traits=["Nimble Escape"], playable=False),
            Race(name="Hobgoblin", bonuses={"CON": 2, "INT": 1}, speed=30, traits=["Martial Training"], playable=False),
            Race(name="Kobold", bonuses={"DEX": 2}, speed=30, traits=["Pack Tactics"], playable=False),
            Race(name="Bugbear", bonuses={"STR": 2, "DEX": 1}, speed=30, traits=["Long-Limbed"], playable=False),
            Race(name="Giant", bonuses={"STR": 3, "CON": 2}, speed=40, traits=["Massive Frame"], playable=False),
            Race(name="Goliath", bonuses={"STR": 2, "CON": 1}, speed=30, traits=["Stone's Endurance"], playable=False),
            Race(name="Dark Elf", bonuses={"DEX": 2, "CHA": 1}, speed=30, traits=["Superior Darkvision", "Sunlight Sensitivity"], playable=False),
        ]

        return [*playable, *non_playable]

    def _load_races(self, open5e_client) -> List[Race]:
        defaults = self._default_races()
        if open5e_client is None:
            return defaults

        remote: List[Race] = []
        try:
            remote = self._fetch_open5e_races(open5e_client)
        except Exception:
            remote = []

        seen = {race.name.lower() for race in defaults}
        merged: List[Race] = list(defaults)
        for race in remote:
            key = race.name.lower()
            if key in seen:
                for idx, existing in enumerate(merged):
                    if existing.name.lower() != key:
                        continue
                    merged[idx] = race
                    break
            else:
                merged.append(race)
                seen.add(key)
        return merged

    def _default_creation_reference(self) -> Dict[str, List[str]]:
        subrace_names: List[str] = []
        for rows in self._default_subraces().values():
            subrace_names.extend([subrace.name for subrace in rows])
        return {
            "races": [race.name for race in self._default_races()],
            "subraces": subrace_names,
            "classes": self._playable_class_names(),
            "subclasses": self._playable_subclass_names(),
            "spells": [],
            "equipment": [],
            "backgrounds": [row.name for row in self._default_backgrounds()],
            "skills": [],
            "languages": [],
            "traits": [],
        }

    def _playable_class_names(self) -> List[str]:
        try:
            rows = self.class_repo.list_playable()
        except Exception:
            return []
        names: List[str] = []
        seen: set[str] = set()
        for row in rows:
            name = str(getattr(row, "name", "")).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
        return names

    def _playable_subclass_names(self) -> List[str]:
        names: List[str] = []
        seen: set[str] = set()
        try:
            class_rows = self.list_classes()
        except Exception:
            class_rows = []
        for class_row in class_rows:
            class_key = getattr(class_row, "slug", None) or getattr(class_row, "name", None)
            for row in self.list_subclasses_for_class(class_key):
                key = str(getattr(row, "name", "")).strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                names.append(str(row.name))
        return names

    def _load_creation_reference(self, client, races: List[Race]) -> Dict[str, List[str]]:
        reference = self._default_creation_reference()
        if races:
            reference["races"] = [race.name for race in races]

        endpoint_map = {
            "classes": "classes",
            "spells": "spells",
            "equipment": "equipment",
            "backgrounds": "backgrounds",
            "skills": "skills",
            "languages": "languages",
            "subraces": "subraces",
            "traits": "traits",
        }

        for category, endpoint in endpoint_map.items():
            names = self._fetch_reference_names(client, endpoint)
            if names:
                reference[category] = names

        # Always preserve playable-class list as minimum fallback visibility.
        if not reference.get("classes"):
            reference["classes"] = self._playable_class_names()
        if not reference.get("subclasses"):
            reference["subclasses"] = self._playable_subclass_names()
        if not reference.get("backgrounds"):
            reference["backgrounds"] = [row.name for row in self.backgrounds]
        if not reference.get("races"):
            reference["races"] = [race.name for race in self.races]
        if not reference.get("subraces"):
            reference["subraces"] = [
                subrace.name
                for rows in self.subraces_by_race.values()
                for subrace in rows
            ]
        return reference

    @staticmethod
    def _merge_bonus_maps(base: Dict[str, int], extra: Dict[str, int]) -> Dict[str, int]:
        merged: Dict[str, int] = dict(base)
        for key, value in extra.items():
            canonical = ABILITY_ALIASES.get(str(key).lower(), str(key).lower())
            abbr = FULL_TO_ABBR.get(canonical, canonical.upper())
            merged[abbr] = merged.get(abbr, 0) + int(value)
        return merged

    @staticmethod
    def _merge_traits(primary: List[str], secondary: List[str]) -> List[str]:
        merged: List[str] = []
        seen: set[str] = set()
        for trait in [*(primary or []), *(secondary or [])]:
            text = str(trait).strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            merged.append(text)
        return merged

    def _compose_race_with_subrace(self, race: Race | None, subrace: Subrace | None) -> Race | None:
        if race is None or subrace is None:
            return race
        if subrace.parent_race.strip().lower() != race.name.strip().lower():
            return race

        merged_bonuses = self._merge_bonus_maps(race.bonuses, subrace.bonuses)
        merged_traits = self._merge_traits(race.traits, subrace.traits)
        return Race(
            name=f"{race.name} ({subrace.name})",
            bonuses=merged_bonuses,
            speed=max(0, int(race.speed) + int(subrace.speed_bonus)),
            traits=merged_traits,
            playable=bool(getattr(race, "playable", True)),
        )

    @staticmethod
    def _extract_reference_name(row: dict) -> str:
        if not isinstance(row, dict):
            return ""
        name = row.get("name") or row.get("full_name") or row.get("index") or row.get("slug")
        return str(name).strip() if name else ""

    def _fetch_reference_names(self, client, endpoint: str, page: int = 1) -> List[str]:
        payload = {}
        if hasattr(client, "list_endpoint"):
            try:
                payload = client.list_endpoint(endpoint, page=page)
            except Exception:
                payload = {}

        if not isinstance(payload, dict) or not payload.get("results"):
            direct_method = f"list_{endpoint.replace('-', '_')}"
            if hasattr(client, direct_method):
                try:
                    payload = getattr(client, direct_method)(page=page)
                except Exception:
                    payload = {}

        results = payload.get("results", []) if isinstance(payload, dict) else []
        names: List[str] = []
        seen: set[str] = set()
        for row in results:
            name = self._extract_reference_name(row)
            key = name.lower()
            if not name or key in seen:
                continue
            names.append(name)
            seen.add(key)
        return names

    def _fetch_open5e_races(self, client) -> List[Race]:
        races: List[Race] = []
        page = 1
        while True:
            payload = client.list_races(page=page)
            results = payload.get("results", [])
            if not results:
                break
            for row in results:
                races.append(self._map_open5e_race(self._hydrate_race_row(client, row)))
            if not payload.get("next"):
                break
            page += 1
        return races

    def _load_subraces(self, client) -> Dict[str, List[Subrace]]:
        defaults = self._default_subraces()
        if client is None:
            return defaults

        remote = self._fetch_open5e_subraces(client)
        if not remote:
            return defaults

        merged = {key: list(rows) for key, rows in defaults.items()}
        seen = {
            key: {subrace.name.lower() for subrace in rows}
            for key, rows in merged.items()
        }
        for subrace in remote:
            parent_key = subrace.parent_race.strip().lower()
            if not parent_key:
                continue
            if parent_key not in merged:
                merged[parent_key] = []
                seen[parent_key] = set()
            if subrace.name.lower() in seen[parent_key]:
                continue
            merged[parent_key].append(subrace)
            seen[parent_key].add(subrace.name.lower())
        return merged

    def _fetch_open5e_subraces(self, client) -> List[Subrace]:
        races_by_key = {race.name.strip().lower(): race.name for race in self.races}
        payload = {}
        if hasattr(client, "list_endpoint"):
            try:
                payload = client.list_endpoint("subraces", page=1)
            except Exception:
                payload = {}

        if not isinstance(payload, dict):
            return []
        results = payload.get("results", [])
        rows: List[Subrace] = []
        for entry in results:
            mapped = self._map_open5e_subrace(entry, races_by_key)
            if mapped is not None:
                rows.append(mapped)
        return rows

    def _map_open5e_subrace(self, row: dict, races_by_key: Dict[str, str]) -> Subrace | None:
        if not isinstance(row, dict):
            return None
        name = str(row.get("name") or row.get("full_name") or "").strip()
        race_ref = row.get("race") or row.get("parent_race") or {}
        if isinstance(race_ref, dict):
            race_name = race_ref.get("name") or race_ref.get("index")
        else:
            race_name = race_ref
        race_name_text = str(race_name or "").strip()
        if not name or not race_name_text:
            return None
        canonical_parent = races_by_key.get(race_name_text.lower(), race_name_text)
        return Subrace(
            name=name,
            parent_race=canonical_parent,
            bonuses=self._parse_ability_bonuses(row.get("ability_bonuses") or row.get("asi") or []),
            speed_bonus=0,
            traits=self._parse_traits(row.get("traits") or []),
        )

    @staticmethod
    def _default_subraces() -> Dict[str, List[Subrace]]:
        return {
            "elf": [
                Subrace(
                    name="High Elf",
                    parent_race="Elf",
                    bonuses={"INT": 1},
                    traits=["Cantrip Aptitude", "Keen Mind"],
                ),
                Subrace(
                    name="Wood Elf",
                    parent_race="Elf",
                    bonuses={"WIS": 1},
                    speed_bonus=5,
                    traits=["Fleet of Foot", "Mask of the Wild"],
                ),
                Subrace(
                    name="Dark Elf",
                    parent_race="Elf",
                    bonuses={"CHA": 1},
                    traits=["Superior Darkvision", "Sunlight Sensitivity"],
                ),
            ],
            "dwarf": [
                Subrace(
                    name="Hill Dwarf",
                    parent_race="Dwarf",
                    bonuses={"WIS": 1},
                    traits=["Dwarven Toughness"],
                ),
                Subrace(
                    name="Mountain Dwarf",
                    parent_race="Dwarf",
                    bonuses={"STR": 2},
                    traits=["Dwarven Armor Training"],
                ),
            ],
            "halfling": [
                Subrace(
                    name="Lightfoot",
                    parent_race="Halfling",
                    bonuses={"CHA": 1},
                    traits=["Naturally Stealthy"],
                ),
                Subrace(
                    name="Stout",
                    parent_race="Halfling",
                    bonuses={"CON": 1},
                    traits=["Stout Resilience"],
                ),
            ],
            "human": [
                Subrace(
                    name="Highland Human",
                    parent_race="Human",
                    bonuses={"CON": 1},
                    traits=["Hardy Traveler"],
                ),
                Subrace(
                    name="Coastal Human",
                    parent_race="Human",
                    bonuses={"CHA": 1},
                    traits=["Silver Tongue"],
                ),
                Subrace(
                    name="Variant Human",
                    parent_race="Human",
                    bonuses={"STR": 1, "DEX": 1},
                    traits=["Bonus Feat", "Bonus Skill"],
                ),
            ],
            "dragonborn": [
                Subrace(
                    name="Black",
                    parent_race="Dragonborn",
                    bonuses={"CON": 1},
                    traits=["Breath: acid line (5x30, DEX save)", "Alignment: Evil"],
                ),
                Subrace(
                    name="Blue",
                    parent_race="Dragonborn",
                    bonuses={"DEX": 1},
                    traits=["Breath: lightning line (5x30, DEX save)", "Alignment: Evil"],
                ),
                Subrace(
                    name="Brass",
                    parent_race="Dragonborn",
                    bonuses={"CHA": 1},
                    traits=["Breath: fire line (5x30, DEX save)", "Alignment: Good"],
                ),
                Subrace(
                    name="Bronze",
                    parent_race="Dragonborn",
                    bonuses={"STR": 1},
                    traits=["Breath: lightning line (5x30, DEX save)", "Alignment: Good"],
                ),
                Subrace(
                    name="Copper",
                    parent_race="Dragonborn",
                    bonuses={"INT": 1},
                    traits=["Breath: acid line (5x30, DEX save)", "Alignment: Good"],
                ),
                Subrace(
                    name="Gold",
                    parent_race="Dragonborn",
                    bonuses={"WIS": 1},
                    traits=["Breath: fire cone (15 ft, DEX save)", "Alignment: Good"],
                ),
                Subrace(
                    name="Green",
                    parent_race="Dragonborn",
                    bonuses={"CON": 1},
                    traits=["Breath: poison cone (15 ft, DEX save)", "Alignment: Evil"],
                ),
                Subrace(
                    name="Red",
                    parent_race="Dragonborn",
                    bonuses={"STR": 1},
                    traits=["Breath: fire cone (15 ft, DEX save)", "Alignment: Evil"],
                ),
                Subrace(
                    name="Silver",
                    parent_race="Dragonborn",
                    bonuses={"WIS": 1},
                    traits=["Breath: cold cone (15 ft, DEX save)", "Alignment: Good"],
                ),
                Subrace(
                    name="White",
                    parent_race="Dragonborn",
                    bonuses={"CON": 1},
                    traits=["Breath: cold cone (15 ft, DEX save)", "Alignment: Evil"],
                ),
            ],
        }

    @staticmethod
    def _hydrate_race_row(client, row: dict) -> dict:
        if not isinstance(row, dict):
            return {}
        slug = row.get("slug") or row.get("index")
        if not slug or not hasattr(client, "get_race"):
            return row
        try:
            detail = client.get_race(str(slug))
        except Exception:
            return row
        if not isinstance(detail, dict):
            return row
        merged = dict(row)
        merged.update(detail)
        return merged

    def _map_open5e_race(self, row: dict) -> Race:
        name = row.get("name", "Unknown")
        speed_raw = row.get("speed") or 30
        try:
            speed = int(speed_raw)
        except Exception:
            speed = 30

        bonuses_raw = row.get("asi") or row.get("ability_bonuses") or row.get("ability_bonuses_json")
        bonuses = self._parse_ability_bonuses(bonuses_raw)

        traits_raw = row.get("traits") or row.get("asi_desc") or ""
        traits = self._parse_traits(traits_raw)

        return Race(name=name, bonuses=bonuses, speed=speed, traits=traits)

    @staticmethod
    def _parse_ability_bonuses(raw) -> Dict[str, int]:
        bonuses: Dict[str, int] = {}

        def _add_bonus(key: str, value) -> None:
            try:
                val_int = int(value)
            except Exception:
                return
            full_key = ABILITY_ALIASES.get(key.lower(), key.lower())
            abbr = FULL_TO_ABBR.get(full_key, full_key.upper())
            bonuses[abbr] = bonuses.get(abbr, 0) + val_int

        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict):
                    ability = entry.get("ability") or entry.get("ability_score") or entry.get("name")
                    if isinstance(ability, dict):
                        ability = (
                            ability.get("index")
                            or ability.get("name")
                            or ability.get("slug")
                        )
                    value = entry.get("value") or entry.get("bonus") or entry.get("score")
                    if ability:
                        _add_bonus(str(ability), value)
                elif isinstance(entry, str):
                    CharacterCreationService._parse_bonus_string(entry, _add_bonus)
        elif isinstance(raw, dict):
            for key, value in raw.items():
                _add_bonus(str(key), value)
        elif isinstance(raw, str):
            CharacterCreationService._parse_bonus_string(raw, _add_bonus)

        return bonuses

    @staticmethod
    def _parse_bonus_string(raw: str, add_bonus) -> None:
        parts = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
        for part in parts:
            tokens = part.replace("+", " +").split()
            if len(tokens) >= 2:
                # formats like "+2 STR" or "STR +2"
                if tokens[0].lstrip("+-").isdigit():
                    add_bonus(tokens[1], tokens[0])
                elif tokens[1].lstrip("+-").isdigit():
                    add_bonus(tokens[0], tokens[1])

    @staticmethod
    def _parse_traits(raw) -> List[str]:
        if isinstance(raw, list):
            parsed: List[str] = []
            for trait in raw:
                if isinstance(trait, dict):
                    name = trait.get("name") or trait.get("index") or trait.get("slug")
                    text = str(name).strip() if name is not None else ""
                else:
                    text = str(trait).strip()
                if text:
                    parsed.append(text)
            return parsed
        if isinstance(raw, str):
            traits = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
            return traits
        return []

    @staticmethod
    def _format_bonus_line(bonuses: Dict[str, int]) -> str:
        if not bonuses:
            return "+0 all"

        unique_values = set(bonuses.values())
        if len(unique_values) == 1 and len(bonuses) >= len(ABILITY_ORDER):
            value = list(unique_values)[0]
            prefix = "+" if value > 0 else ""
            return f"{prefix}{value} to All Stats"

        parts: List[str] = []
        for abbr in ABILITY_ORDER:
            value = bonuses.get(abbr, bonuses.get(abbr.lower()))
            if value:
                prefix = "+" if value > 0 else ""
                parts.append(f"{abbr}{prefix}{value}")
        if not parts:
            parts = [f"{key.upper()}+{value}" for key, value in list(bonuses.items())[:3]]
        return ", ".join(parts)

    @staticmethod
    def _clean_trait_text(raw: str) -> str:
        if not raw:
            return ""
        text = raw.replace("*", "").replace("_", "")
        text = " ".join(text.split())
        if not text:
            return ""
        sentence = text.split(". ")[0].strip()
        sentence = sentence.split(",")[0].strip()
        if sentence.endswith("."):
            sentence = sentence[:-1]
        max_len = 60
        if len(sentence) > max_len:
            sentence = sentence[: max_len - 3].rstrip() + "..."
        return sentence

    def _format_trait_summary(self, traits: List[str], limit: int = 2) -> str:
        cleaned = [self._clean_trait_text(trait) for trait in traits or []]
        cleaned = [trait for trait in cleaned if trait]
        if not cleaned:
            return "No traits"

        def _looks_like_title(value: str) -> bool:
            first = value.split()[0].lower()
            return value[:1].isupper() and first not in {
                "and",
                "or",
                "you",
                "your",
                "the",
                "a",
                "an",
                "in",
                "on",
                "with",
                "while",
                "when",
                "if",
                "as",
                "which",
            }

        primary = [trait for trait in cleaned if _looks_like_title(trait)]
        pool = primary or cleaned
        shown = pool[:limit]
        if len(pool) > limit:
            shown.append(f"+{len(pool) - limit} more")
        return ", ".join(shown)

    @staticmethod
    def _default_backgrounds() -> List[Background]:
        return [
            Background(
                name="Temple Envoy",
                proficiencies=["Insight", "Religion"],
                feature="Sanctuary Network",
                faction="lumen_order",
                starting_money=9,
            ),
            Background(
                name="Lorekeeper",
                proficiencies=["Arcana", "History"],
                feature="Archive Access",
                faction="scribe_circle",
                starting_money=10,
            ),
            Background(
                name="Night Runner",
                proficiencies=["Stealth", "Deception"],
                feature="Hidden Routes",
                faction="underworld",
                starting_money=12,
            ),
            Background(
                name="Forgehand",
                proficiencies=["Athletics", "Investigation"],
                feature="Maker's Eye",
                faction="guild_coalition",
                starting_money=11,
            ),
            Background(
                name="Frontier Tender",
                proficiencies=["Animal Handling", "Nature"],
                feature="Trail Instinct",
                faction="wardens",
                starting_money=10,
            ),
            Background(
                name="Watch Sentinel",
                proficiencies=["Athletics", "Perception"],
                feature="Gate Discipline",
                faction="watch",
                starting_money=10,
            ),
        ]

    @staticmethod
    def _default_difficulties() -> List[DifficultyPreset]:
        ordered = ["story", "normal", "hardcore"]
        return [
            DifficultyPreset(
                slug=slug,
                name=DIFFICULTY_PRESET_PROFILES[slug]["name"],
                description=DIFFICULTY_PRESET_PROFILES[slug]["description"],
                hp_multiplier=DIFFICULTY_PRESET_PROFILES[slug]["hp_multiplier"],
                incoming_damage_multiplier=DIFFICULTY_PRESET_PROFILES[slug]["incoming_damage_multiplier"],
                outgoing_damage_multiplier=DIFFICULTY_PRESET_PROFILES[slug]["outgoing_damage_multiplier"],
            )
            for slug in ordered
        ]

    @staticmethod
    def _default_starting_equipment() -> Dict[str, List[str]]:
        return {
            "barbarian": ["Greataxe", "Explorer's Pack", "Javelin x4"],
            "bard": ["Rapier", "Lute", "Leather Armor", "Dagger"],
            "cleric": ["Mace", "Shield", "Chain Shirt", "Holy Symbol"],
            "druid": ["Scimitar", "Wooden Shield", "Herbalism Kit"],
            "fighter": ["Longsword", "Shield", "Chain Mail"],
            "monk": ["Quarterstaff", "Darts x10"],
            "paladin": ["Longsword", "Shield", "Chain Mail", "Holy Symbol"],
            "ranger": ["Longbow", "Shortsword x2", "Leather Armor"],
            "rogue": ["Shortsword", "Shortbow", "Leather Armor", "Thieves' Tools"],
            "sorcerer": ["Dagger", "Component Pouch", "Wand"],
            "warlock": ["Pact Rod", "Leather Armor", "Dagger x2"],
            "wizard": ["Spellbook", "Quarterstaff", "Component Pouch"],
            "artificer": ["Light Hammer", "Scale Mail", "Tinker Tools"],
            "_default": ["Traveler's Cloak", "Rations (3 days)", "Torch x3"],
        }

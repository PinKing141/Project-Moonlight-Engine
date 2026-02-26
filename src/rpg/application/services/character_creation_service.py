from __future__ import annotations

import random
from typing import Dict, List

from rpg.application.dtos import CharacterClassDetailView
from rpg.application.mappers.character_creation_mapper import to_character_class_detail_view
from rpg.application.services.balance_tables import DIFFICULTY_PRESET_PROFILES
from rpg.domain.models.character_class import CharacterClass
from rpg.domain.models.character_options import Background, DifficultyPreset, Race, Subrace
from rpg.domain.repositories import CharacterRepository, ClassRepository, FeatureRepository, LocationRepository
from rpg.domain.services.character_factory import ABILITY_ALIASES, create_new_character


ABILITY_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

FULL_TO_ABBR = {full: abbr.upper() for abbr, full in ABILITY_ALIASES.items()}


class CharacterCreationService:
    CREATION_REFERENCE_CATEGORIES = (
        ("races", "Races"),
        ("subraces", "Subraces"),
        ("classes", "Classes"),
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

    def list_backgrounds(self) -> List[Background]:
        return list(self.backgrounds)

    def list_subraces_for_race(self, race: Race | None = None, race_name: str | None = None) -> List[Subrace]:
        base_name = race_name or (race.name if race else "")
        if not base_name:
            return []
        return list(self.subraces_by_race.get(base_name.strip().lower(), []))

    def list_difficulties(self) -> List[DifficultyPreset]:
        return list(self.difficulties)

    def list_class_names(self) -> List[str]:
        return [cls.name for cls in self.list_classes()]

    def list_creation_reference_categories(self) -> List[str]:
        return [label for _, label in self.CREATION_REFERENCE_CATEGORIES]

    def list_creation_reference_items(self, category_slug: str, limit: int = 20) -> List[str]:
        key = str(category_slug or "").strip().lower()
        rows = list(self.creation_reference.get(key, []))
        if limit > 0:
            rows = rows[: int(limit)]
        return rows

    def race_option_labels(self) -> List[str]:
        labels: List[str] = []
        for race in self.list_races():
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
    ) -> "Character":
        provided_name = (name or "").strip()
        if not provided_name and self.name_generator is not None:
            existing_count = 0
            try:
                existing_count = len(self.character_repo.list_all())
            except Exception:
                existing_count = 0
            generated = self.name_generator.suggest_character_name(
                race_name=race.name if race else None,
                context={
                    "class_index": class_index,
                    "existing_count": existing_count,
                },
            )
            name = self.sanitize_name(generated)
        else:
            name = self.sanitize_name(name)
        classes = self.class_repo.list_playable()
        if class_index < 0 or class_index >= len(classes):
            raise ValueError("Invalid class selection.")
        chosen = classes[class_index]

        if ability_scores is None:
            ability_scores = self.standard_array_for_class(chosen)

        effective_race = self._compose_race_with_subrace(race, subrace)

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
        )

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

    @staticmethod
    def sanitize_name(raw: str, max_length: int = 20) -> str:
        trimmed = (raw or "").strip()
        cleaned = "".join(ch for ch in trimmed if ch.isprintable() and ch not in "\t\r\n")
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        return cleaned or "Nameless One"

    @staticmethod
    def _default_races() -> List[Race]:
        return [
            Race(name="Human", bonuses={key: 1 for key in ABILITY_ORDER}, speed=30, traits=["Versatile", "Adaptive"]),
            Race(name="Elf", bonuses={"DEX": 2, "INT": 1}, speed=30, traits=["Keen Senses", "Fey Ancestry"]),
            Race(name="Dwarf", bonuses={"CON": 2, "WIS": 1}, speed=25, traits=["Darkvision", "Stonecunning"]),
            Race(name="Halfling", bonuses={"DEX": 2, "CHA": 1}, speed=25, traits=["Lucky", "Brave"]),
            Race(name="Half-Orc", bonuses={"STR": 2, "CON": 1}, speed=30, traits=["Relentless Endurance", "Savage Attacks"]),
            Race(name="Tiefling", bonuses={"CHA": 2, "INT": 1}, speed=30, traits=["Darkvision", "Hellish Resistance"]),
            Race(name="Dragonborn", bonuses={"STR": 2, "CHA": 1}, speed=30, traits=["Scaled Resilience", "Ancestral Breath"]),
        ]

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
            if race.name.lower() not in seen:
                merged.append(race)
                seen.add(race.name.lower())
        return merged

    def _default_creation_reference(self) -> Dict[str, List[str]]:
        subrace_names: List[str] = []
        for rows in self._default_subraces().values():
            subrace_names.extend([subrace.name for subrace in rows])
        return {
            "races": [race.name for race in self._default_races()],
            "subraces": subrace_names,
            "classes": self._playable_class_names(),
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

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from rpg.application.services.seed_policy import derive_seed


@dataclass(frozen=True)
class PhonemeSet:
    vowels: List[str] = field(default_factory=list)
    consonants: List[str] = field(default_factory=list)
    hard_consonants: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class NameComponents:
    prefixes: List[str] = field(default_factory=list)
    suffixes_male: List[str] = field(default_factory=list)
    suffixes_female: List[str] = field(default_factory=list)
    suffixes_neutral: List[str] = field(default_factory=list)
    surname_prefixes: List[str] = field(default_factory=list)
    surname_suffixes: List[str] = field(default_factory=list)
    clan_roots: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class NamingConvention:
    use_surname: bool = False
    surname_probability: float = 0.0
    surname_style: str = "family"


@dataclass(frozen=True)
class LanguageProfile:
    language_name: str
    phonemes: PhonemeSet
    components: NameComponents
    syllable_patterns: List[str] = field(default_factory=list)
    naming_convention: NamingConvention = field(default_factory=NamingConvention)


class DnDCorpusNameGenerator:
    _SUPPORTED_GENDERS = ("male", "female", "nonbinary")
    _RACE_ALIASES = {
        "human": "human",
        "humans": "human",
        "humanoid": "human",
        "humanvariant": "human",
        "person": "human",
        "elf": "elf",
        "elves": "elf",
        "highelf": "elf",
        "woodelf": "elf",
        "halfelf": "halfelf",
        "half-elf": "halfelf",
        "dwarf": "dwarf",
        "dwarves": "dwarf",
        "hilldwarf": "dwarf",
        "mountaindwarf": "dwarf",
        "halfling": "halfling",
        "halforc": "halforc",
        "half-orc": "halforc",
        "orc": "orc",
        "orcs": "orc",
        "tiefling": "tiefling",
        "dragonborn": "dragonborn",
        "darkelf": "darkelf",
        "drow": "darkelf",
        "aarakocra": "aarakocra",
        "genasi": "genasi",
        "gnome": "gnome",
        "gnomes": "gnome",
        "goblin": "goblin",
        "goblins": "goblin",
        "hobgoblin": "hobgoblin",
        "kobold": "kobold",
        "bugbear": "bugbear",
        "giant": "giant",
        "giants": "giant",
        "goliath": "goliath",
    }
    _RACE_TO_LANGUAGE = {
        "human": "human",
        "elf": "elf",
        "halfelf": "halfelf",
        "dwarf": "dwarf",
        "halfling": "halfling",
        "halforc": "halforc",
        "orc": "orc",
        "tiefling": "tiefling",
        "dragonborn": "dragonborn",
    }
    _FALLBACK_NAMES = {
        ("human", "male"): ["Alden", "Borin", "Cedric", "Darian", "Edric", "Fenn"],
        ("human", "female"): ["Aria", "Bryn", "Celia", "Daphne", "Elora", "Faye"],
        ("human", "nonbinary"): ["Ari", "Bren", "Ciel", "Dara", "Ember", "Fable"],
        ("elf", "male"): ["Aelar", "Belanor", "Carric", "Dayereth", "Erevan", "Fivin"],
        ("elf", "female"): ["Ariannis", "Birel", "Caelynn", "Drusilia", "Enna", "Felosial"],
        ("elf", "nonbinary"): ["Aelion", "Calen", "Elaris", "Ilyr", "Sere", "Vaelis"],
        ("dwarf", "male"): ["Baern", "Dain", "Fargrim", "Harbek", "Kildrak", "Thoradin"],
        ("dwarf", "female"): ["Amber", "Diesa", "Gunnloda", "Helja", "Liftrasa", "Riswynn"],
        ("dwarf", "nonbinary"): ["Brennar", "Dori", "Harra", "Karn", "Orin", "Thrain"],
        ("halfling", "male"): ["Alton", "Cade", "Milo", "Perrin", "Roscoe", "Wellby"],
        ("halfling", "female"): ["Andry", "Bree", "Callie", "Kithri", "Lavinia", "Verna"],
        ("halfling", "nonbinary"): ["Ash", "Bram", "Clover", "Pip", "Sage", "Wren"],
        ("halforc", "male"): ["Dench", "Feng", "Gell", "Henk", "Ront", "Shump"],
        ("halforc", "female"): ["Baggi", "Emen", "Kansif", "Myev", "Neega", "Ovak"],
        ("halforc", "nonbinary"): ["Brakka", "Ghor", "Korr", "Murn", "Rag", "Vesh"],
        ("orc", "male"): ["Druuk", "Ghak", "Morg", "Thokk", "Urg", "Varg"],
        ("orc", "female"): ["Bagra", "Dura", "Morga", "Shura", "Ugra", "Vola"],
        ("orc", "nonbinary"): ["Grim", "Krog", "Mazh", "Rusk", "Thrag", "Zurr"],
        ("tiefling", "male"): ["Akmenos", "Amnon", "Barakas", "Damakos", "Ekemon", "Leucis"],
        ("tiefling", "female"): ["Akta", "Bryseis", "Criella", "Kallista", "Nemeia", "Orianna"],
        ("tiefling", "nonbinary"): ["Aster", "Cinder", "Ember", "Nox", "Riven", "Vesper"],
        ("dragonborn", "male"): ["Arjhan", "Balasar", "Ghesh", "Kriv", "Medrash", "Nadarr"],
        ("dragonborn", "female"): ["Akra", "Biri", "Daar", "Harann", "Kava", "Sora"],
        ("dragonborn", "nonbinary"): ["Azar", "Drav", "Kesh", "Rhogar", "Tarak", "Vyrm"],
        ("darkelf", "male"): ["Drizzen", "Velkyn", "Ryld", "Zaknafein", "Pharaun", "Nalfein"],
        ("darkelf", "female"): ["Viconia", "Zesstra", "Vierna", "Quenthel", "Malice", "Sabrae"],
        ("darkelf", "nonbinary"): ["Ilvara", "Jhael", "Nyl", "Ryss", "Sorn", "Veldrin"],
        ("aarakocra", "male"): ["Kleeck", "Tarak", "Skrit", "Aruuk", "Qiri", "Vorr"],
        ("aarakocra", "female"): ["Sree", "Ariik", "Tila", "Qeera", "Veesh", "Karaak"],
        ("aarakocra", "nonbinary"): ["Arii", "Kriit", "Qaar", "Skree", "Tavi", "Virr"],
        ("genasi", "male"): ["Ashar", "Nazer", "Vaylen", "Zahir", "Khem", "Ruvan"],
        ("genasi", "female"): ["Nissa", "Saphra", "Vesha", "Kalyra", "Nym", "Ariya"],
        ("genasi", "nonbinary"): ["Aeris", "Cairn", "Nym", "Pyre", "Rill", "Zeph"],
        ("gnome", "male"): ["Boddynock", "Dimble", "Fonkin", "Frug", "Nackle", "Wrenn"],
        ("gnome", "female"): ["Bimpnottin", "Ellyjobell", "Loopmottin", "Nissa", "Roywyn", "Tana"],
        ("gnome", "nonbinary"): ["Brindle", "Fizz", "Nim", "Pock", "Tink", "Wobble"],
        ("goblin", "male"): ["Snik", "Grub", "Rikkit", "Mog", "Vrak", "Zug"],
        ("goblin", "female"): ["Snika", "Grikka", "Miva", "Rakka", "Zaza", "Vri"],
        ("goblin", "nonbinary"): ["Grit", "Kriz", "Murk", "Rik", "Snag", "Vik"],
        ("hobgoblin", "male"): ["Dargun", "Kragh", "Mokran", "Hruk", "Vharr", "Zorak"],
        ("hobgoblin", "female"): ["Dhara", "Kavra", "Morga", "Vrissa", "Tazra", "Hara"],
        ("hobgoblin", "nonbinary"): ["Drak", "Korr", "Mazh", "Roga", "Vark", "Zhra"],
        ("kobold", "male"): ["Skreek", "Ix", "Tark", "Rik", "Ziz", "Kraz"],
        ("kobold", "female"): ["Siss", "Vixa", "Kiri", "Zarra", "Tis", "Riksa"],
        ("kobold", "nonbinary"): ["Ixx", "Krik", "Rizz", "Szik", "Trix", "Viss"],
        ("bugbear", "male"): ["Brug", "Harg", "Murg", "Thokk", "Vrug", "Krann"],
        ("bugbear", "female"): ["Brakka", "Harra", "Morga", "Thora", "Vrukka", "Karna"],
        ("bugbear", "nonbinary"): ["Bruk", "Garr", "Morg", "Thrag", "Vrakk", "Zurn"],
        ("giant", "male"): ["Hrod", "Skarn", "Bromm", "Targ", "Ulfar", "Drogan"],
        ("giant", "female"): ["Hilda", "Skarra", "Brynja", "Torga", "Ulrika", "Droga"],
        ("giant", "nonbinary"): ["Bryn", "Drokk", "Hroth", "Skarr", "Torr", "Uld"],
        ("goliath", "male"): ["Aukan", "Eglath", "Gae-Al", "Keothi", "Lo-Kag", "Manneo"],
        ("goliath", "female"): ["Gathakanathi", "Kuori", "Lo-Mota", "Maveith", "Nalla", "Orilo"],
        ("goliath", "nonbinary"): ["Aukani", "Gorath", "Lo-Keth", "Mav", "Orin", "Tala"],
    }
    _ENTITY_KIND_TO_RACES = {
        "humanoid": [
            "human",
            "elf",
            "dwarf",
            "halfling",
            "halforc",
            "orc",
            "tiefling",
            "dragonborn",
            "darkelf",
            "gnome",
            "goblin",
            "hobgoblin",
            "kobold",
            "bugbear",
            "goliath",
            "genasi",
            "aarakocra",
        ],
        "person": ["human", "elf", "dwarf", "halfling", "gnome", "tiefling", "genasi"],
        "npc": ["human", "elf", "dwarf", "halfling", "gnome", "tiefling", "genasi"],
        "goblinoid": ["goblin", "hobgoblin", "bugbear"],
        "giant": ["giant", "goliath"],
        "dragon": ["dragonborn"],
        "fiend": ["tiefling"],
    }

    def __init__(self, data_dir: Path | None = None, language_dir: Path | None = None) -> None:
        self.data_dir = data_dir or self._default_data_dir()
        self.language_dir = language_dir or self._default_language_dir()
        self._names_by_race_gender: Dict[Tuple[str, str], List[str]] = {}
        self._language_profiles: Dict[str, LanguageProfile] = {}
        self._load()

    @staticmethod
    def _default_data_dir() -> Path:
        project_root = Path(__file__).resolve().parents[4]
        return project_root / "data" / "name_generation"

    @staticmethod
    def _default_language_dir() -> Path:
        project_root = Path(__file__).resolve().parents[4]
        return project_root / "data" / "languages"

    @staticmethod
    def _normalize_token(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _normalize_race(self, race_name: str | None) -> str:
        token = self._normalize_token(race_name)
        if not token:
            return ""
        return self._RACE_ALIASES.get(token, token)

    def _normalize_gender(self, gender: str | None) -> str:
        token = self._normalize_token(gender)
        if token in self._SUPPORTED_GENDERS:
            return token
        if token in {"nb", "neutral", "enby", "nonbinary", "nongender"}:
            return "nonbinary"
        return ""

    def _extract_subrace_tokens(self, race_name: str | None) -> List[str]:
        text = str(race_name or "").strip()
        if not text:
            return []
        lowered = text.lower()
        tokens: List[str] = []
        if "(" in lowered and ")" in lowered:
            between = lowered.split("(", 1)[1].split(")", 1)[0]
            tokens.append(self._normalize_token(between))
        for chunk in re.split(r"[\s/,-]+", lowered):
            normalized = self._normalize_token(chunk)
            if normalized:
                tokens.append(normalized)
        return tokens

    def _normalize_race_with_subrace(self, race_name: str | None) -> str:
        normalized = self._normalize_race(race_name)
        if normalized:
            return normalized
        for token in self._extract_subrace_tokens(race_name):
            aliased = self._RACE_ALIASES.get(token, "")
            if aliased:
                return aliased
        return ""

    @staticmethod
    def _choose_weighted(rng: random.Random, rows: List[Tuple[str, float]]) -> str:
        if not rows:
            return ""
        total = sum(max(0.0, float(weight)) for _, weight in rows)
        if total <= 0:
            return rows[rng.randrange(len(rows))][0]
        roll = rng.uniform(0.0, total)
        partial = 0.0
        for value, weight in rows:
            partial += max(0.0, float(weight))
            if roll <= partial:
                return value
        return rows[-1][0]

    def _load_language_profiles(self) -> None:
        if not self.language_dir.exists():
            return
        for file_path in sorted(self.language_dir.glob("*.json")):
            try:
                raw = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw, dict):
                continue
            key = self._normalize_token(str(raw.get("language_name") or file_path.stem))
            if not key:
                continue
            phonemes_raw = raw.get("phonemes") if isinstance(raw.get("phonemes"), dict) else {}
            components_raw = raw.get("components") if isinstance(raw.get("components"), dict) else {}
            naming_raw = raw.get("naming_convention") if isinstance(raw.get("naming_convention"), dict) else {}
            profile = LanguageProfile(
                language_name=str(raw.get("language_name") or file_path.stem),
                phonemes=PhonemeSet(
                    vowels=[str(v) for v in (phonemes_raw.get("vowels") or []) if str(v).strip()],
                    consonants=[str(v) for v in (phonemes_raw.get("consonants") or []) if str(v).strip()],
                    hard_consonants=[str(v) for v in (phonemes_raw.get("hard_consonants") or []) if str(v).strip()],
                ),
                components=NameComponents(
                    prefixes=[str(v) for v in (components_raw.get("prefixes") or []) if str(v).strip()],
                    suffixes_male=[str(v) for v in (components_raw.get("suffixes_male") or []) if str(v).strip()],
                    suffixes_female=[str(v) for v in (components_raw.get("suffixes_female") or []) if str(v).strip()],
                    suffixes_neutral=[str(v) for v in (components_raw.get("suffixes_neutral") or []) if str(v).strip()],
                    surname_prefixes=[str(v) for v in (components_raw.get("surname_prefixes") or []) if str(v).strip()],
                    surname_suffixes=[str(v) for v in (components_raw.get("surname_suffixes") or []) if str(v).strip()],
                    clan_roots=[str(v) for v in (components_raw.get("clan_roots") or []) if str(v).strip()],
                ),
                syllable_patterns=[str(v) for v in (raw.get("syllable_patterns") or []) if str(v).strip()],
                naming_convention=NamingConvention(
                    use_surname=bool(naming_raw.get("use_surname", False)),
                    surname_probability=max(0.0, min(1.0, float(naming_raw.get("surname_probability", 0.0) or 0.0))),
                    surname_style=str(naming_raw.get("surname_style") or "family").strip().lower() or "family",
                ),
            )
            self._language_profiles[key] = profile

    def _load(self) -> None:
        self._load_language_profiles()

        if self.data_dir.exists():
            for file_path in sorted(self.data_dir.glob("*.txt")):
                stem = file_path.stem
                if "_" not in stem:
                    continue
                race_part, gender_part = stem.rsplit("_", 1)
                race = self._normalize_race_with_subrace(race_part)
                gender = self._normalize_gender(gender_part)
                if not race or not gender:
                    continue

                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                except Exception:
                    continue

                names = [line.strip() for line in lines if line.strip()]
                if names:
                    self._names_by_race_gender[(race, gender)] = names

        for key, names in self._FALLBACK_NAMES.items():
            if key not in self._names_by_race_gender:
                self._names_by_race_gender[key] = list(names)

    def _choose_gender(self, race: str, context: dict | None = None) -> str:
        context = context or {}
        seed = derive_seed(
            namespace="name.gender",
            context={"race": race or "any", **context},
        )
        rng = random.Random(seed)
        return self._SUPPORTED_GENDERS[rng.randrange(len(self._SUPPORTED_GENDERS))]

    def _pool_for(self, race: str, gender: str) -> List[str]:
        if race and (race, gender) in self._names_by_race_gender:
            return self._names_by_race_gender[(race, gender)]

        same_gender: List[str] = []
        for (candidate_race, candidate_gender), names in self._names_by_race_gender.items():
            if candidate_gender == gender:
                same_gender.extend(names)
        return same_gender

    def _map_race_to_language(self, race: str) -> str:
        mapped = self._RACE_TO_LANGUAGE.get(race, "")
        if mapped and mapped in self._language_profiles:
            return mapped
        normalized = self._normalize_token(race)
        if normalized in self._language_profiles:
            return normalized
        return ""

    def _assemble_components(self, profile: LanguageProfile, gender: str, rng: random.Random) -> str:
        prefix_pool = profile.components.prefixes or profile.phonemes.consonants
        prefix = prefix_pool[rng.randrange(len(prefix_pool))] if prefix_pool else ""
        suffixes = profile.components.suffixes_neutral
        if gender == "male" and profile.components.suffixes_male:
            suffixes = profile.components.suffixes_male
        elif gender == "female" and profile.components.suffixes_female:
            suffixes = profile.components.suffixes_female
        elif not suffixes:
            suffixes = profile.components.suffixes_male or profile.components.suffixes_female
        suffix = suffixes[rng.randrange(len(suffixes))] if suffixes else ""
        built = f"{prefix}{suffix}".strip()
        if not built:
            return ""
        return built[0].upper() + built[1:]

    def _generate_from_phonetics(self, profile: LanguageProfile, rng: random.Random) -> str:
        patterns = profile.syllable_patterns or ["C-V-C"]
        pattern = patterns[rng.randrange(len(patterns))]
        result = ""
        consonants = profile.phonemes.consonants or ["n", "r", "l", "s", "t"]
        vowels = profile.phonemes.vowels or ["a", "e", "i", "o", "u"]
        hard = profile.phonemes.hard_consonants or consonants
        for char in pattern.split("-"):
            token = char.strip().upper()
            if token == "V":
                result += vowels[rng.randrange(len(vowels))]
            elif token == "C":
                result += consonants[rng.randrange(len(consonants))]
            elif token == "H":
                result += hard[rng.randrange(len(hard))]
        built = result.strip()
        if not built:
            return ""
        return built[0].upper() + built[1:]

    def _generate_surname(self, profile: LanguageProfile, rng: random.Random) -> str:
        style = profile.naming_convention.surname_style
        if style == "clan" and profile.components.clan_roots:
            root = profile.components.clan_roots[rng.randrange(len(profile.components.clan_roots))]
            suffixes = profile.components.surname_suffixes or ["forge", "hammer", "stone"]
            suffix = suffixes[rng.randrange(len(suffixes))]
            return f"{root}{suffix}".replace("  ", " ").strip()

        prefix_pool = profile.components.surname_prefixes
        suffix_pool = profile.components.surname_suffixes
        if prefix_pool and suffix_pool:
            return f"{prefix_pool[rng.randrange(len(prefix_pool))]}{suffix_pool[rng.randrange(len(suffix_pool))]}".strip()
        return ""

    def _procedural_name(self, race: str, gender: str, context: dict | None = None) -> str:
        language = self._map_race_to_language(race)
        if not language:
            return ""
        profile = self._language_profiles.get(language)
        if profile is None:
            return ""
        seed = derive_seed(
            namespace="name.procedural",
            context={
                "race": race or "any",
                "gender": gender,
                **(context or {}),
            },
        )
        rng = random.Random(seed)
        first_name = ""
        if profile.components.prefixes and (
            profile.components.suffixes_male or profile.components.suffixes_female or profile.components.suffixes_neutral
        ):
            first_name = self._assemble_components(profile, gender, rng)
        if not first_name:
            first_name = self._generate_from_phonetics(profile, rng)
        if not first_name:
            return ""

        if profile.naming_convention.use_surname and rng.random() <= profile.naming_convention.surname_probability:
            surname = self._generate_surname(profile, rng)
            if surname:
                return f"{first_name} {surname}"
        return first_name

    def suggest_character_name(
        self,
        race_name: str | None,
        gender: str | None = None,
        context: dict | None = None,
    ) -> str:
        race = self._normalize_race_with_subrace(race_name)
        normalized_gender = self._normalize_gender(gender)
        if not normalized_gender:
            normalized_gender = self._choose_gender(race, context)

        generated = self._procedural_name(race=race, gender=normalized_gender, context=context)
        if generated:
            return generated

        pool = self._pool_for(race, normalized_gender)
        if not pool:
            return "Nameless One"

        seed = derive_seed(
            namespace="name.character",
            context={
                "race": race or "any",
                "gender": normalized_gender,
                **(context or {}),
            },
        )
        rng = random.Random(seed)
        return pool[rng.randrange(len(pool))]

    def generate_entity_name(
        self,
        default_name: str,
        kind: str | None = None,
        faction_id: str | None = None,
        entity_id: int | None = None,
        level: int | None = None,
    ) -> str:
        normalized_kind = self._normalize_token(kind)
        default_name_token = self._normalize_token(default_name)
        race = self._normalize_race(default_name) if default_name_token in self._RACE_ALIASES else ""
        if not race:
            races = list(self._ENTITY_KIND_TO_RACES.get(normalized_kind, []))
            if races:
                seed = derive_seed(
                    namespace="name.entity.race",
                    context={
                        "kind": normalized_kind,
                        "faction": self._normalize_token(faction_id),
                        "entity_id": entity_id,
                        "level": level,
                        "default_name": self._normalize_token(default_name),
                    },
                )
                rng = random.Random(seed)
                race = races[rng.randrange(len(races))]
        if not race:
            return default_name

        generated = self.suggest_character_name(
            race_name=race,
            context={
                "kind": normalized_kind,
                "faction": self._normalize_token(faction_id),
                "entity_id": entity_id,
                "level": level,
            },
        )
        return generated or default_name

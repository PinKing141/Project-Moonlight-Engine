from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Dict, List, Tuple

from rpg.application.services.seed_policy import derive_seed


class DnDCorpusNameGenerator:
    _SUPPORTED_GENDERS = ("male", "female")
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
        "halfelf": "elf",
        "half-elf": "elf",
        "dwarf": "dwarf",
        "dwarves": "dwarf",
        "hilldwarf": "dwarf",
        "mountaindwarf": "dwarf",
        "halfling": "halfling",
        "halforc": "halforc",
        "half-orc": "halforc",
        "orc": "halforc",
        "tiefling": "tiefling",
        "dragonborn": "dragonborn",
    }
    _FALLBACK_NAMES = {
        ("human", "male"): ["Alden", "Borin", "Cedric", "Darian", "Edric", "Fenn"],
        ("human", "female"): ["Aria", "Bryn", "Celia", "Daphne", "Elora", "Faye"],
        ("elf", "male"): ["Aelar", "Belanor", "Carric", "Dayereth", "Erevan", "Fivin"],
        ("elf", "female"): ["Ariannis", "Birel", "Caelynn", "Drusilia", "Enna", "Felosial"],
        ("dwarf", "male"): ["Baern", "Dain", "Fargrim", "Harbek", "Kildrak", "Thoradin"],
        ("dwarf", "female"): ["Amber", "Diesa", "Gunnloda", "Helja", "Liftrasa", "Riswynn"],
        ("halfling", "male"): ["Alton", "Cade", "Milo", "Perrin", "Roscoe", "Wellby"],
        ("halfling", "female"): ["Andry", "Bree", "Callie", "Kithri", "Lavinia", "Verna"],
        ("halforc", "male"): ["Dench", "Feng", "Gell", "Henk", "Ront", "Shump"],
        ("halforc", "female"): ["Baggi", "Emen", "Kansif", "Myev", "Neega", "Ovak"],
        ("tiefling", "male"): ["Akmenos", "Amnon", "Barakas", "Damakos", "Ekemon", "Leucis"],
        ("tiefling", "female"): ["Akta", "Bryseis", "Criella", "Kallista", "Nemeia", "Orianna"],
        ("dragonborn", "male"): ["Arjhan", "Balasar", "Ghesh", "Kriv", "Medrash", "Nadarr"],
        ("dragonborn", "female"): ["Akra", "Biri", "Daar", "Harann", "Kava", "Sora"],
    }
    _ENTITY_KIND_TO_RACE = {
        "humanoid": "human",
        "person": "human",
        "npc": "human",
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or self._default_data_dir()
        self._names_by_race_gender: Dict[Tuple[str, str], List[str]] = {}
        self._load()

    @staticmethod
    def _default_data_dir() -> Path:
        project_root = Path(__file__).resolve().parents[4]
        return project_root / "data" / "name_generation"

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
        return ""

    def _load(self) -> None:
        if self.data_dir.exists():
            for file_path in sorted(self.data_dir.glob("*.txt")):
                stem = file_path.stem
                if "_" not in stem:
                    continue
                race_part, gender_part = stem.rsplit("_", 1)
                race = self._normalize_race(race_part)
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

    def suggest_character_name(
        self,
        race_name: str | None,
        gender: str | None = None,
        context: dict | None = None,
    ) -> str:
        race = self._normalize_race(race_name)
        normalized_gender = self._normalize_gender(gender)
        if not normalized_gender:
            normalized_gender = self._choose_gender(race, context)

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
        race = self._ENTITY_KIND_TO_RACE.get(normalized_kind, "")
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

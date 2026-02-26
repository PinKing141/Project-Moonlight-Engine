from typing import Dict, List

from rpg.domain.models.character_class import CharacterClass
from rpg.domain.repositories import ClassRepository


class InMemoryClassRepository(ClassRepository):
    def __init__(self):
        base: Dict[str, Dict[str, int]] = {
            "barbarian": {"STR": 15, "DEX": 12, "CON": 14, "INT": 8, "WIS": 10, "CHA": 10},
            "bard": {"STR": 10, "DEX": 12, "CON": 12, "INT": 12, "WIS": 10, "CHA": 15},
            "cleric": {"STR": 12, "DEX": 10, "CON": 13, "INT": 10, "WIS": 15, "CHA": 11},
            "druid": {"STR": 10, "DEX": 12, "CON": 13, "INT": 12, "WIS": 15, "CHA": 10},
            "fighter": {"STR": 15, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            "monk": {"STR": 12, "DEX": 15, "CON": 12, "INT": 10, "WIS": 14, "CHA": 10},
            "paladin": {"STR": 15, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
            "ranger": {"STR": 13, "DEX": 15, "CON": 13, "INT": 10, "WIS": 12, "CHA": 10},
            "rogue": {"STR": 10, "DEX": 16, "CON": 12, "INT": 12, "WIS": 10, "CHA": 12},
            "sorcerer": {"STR": 8, "DEX": 12, "CON": 12, "INT": 12, "WIS": 10, "CHA": 16},
            "warlock": {"STR": 10, "DEX": 12, "CON": 12, "INT": 12, "WIS": 12, "CHA": 16},
            "wizard": {"STR": 8, "DEX": 12, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
            "artificer": {"STR": 10, "DEX": 12, "CON": 13, "INT": 16, "WIS": 12, "CHA": 10},
        }

        self._classes: List[CharacterClass] = [
            CharacterClass(id=1,  name="Barbarian", slug="barbarian", hit_die="d12", primary_ability="STR", base_attributes=base["barbarian"]),
            CharacterClass(id=2,  name="Bard",      slug="bard",      hit_die="d8",  primary_ability="CHA", base_attributes=base["bard"]),
            CharacterClass(id=3,  name="Cleric",    slug="cleric",    hit_die="d8",  primary_ability="WIS", base_attributes=base["cleric"]),
            CharacterClass(id=4,  name="Druid",     slug="druid",     hit_die="d8",  primary_ability="WIS", base_attributes=base["druid"]),
            CharacterClass(id=5,  name="Fighter",   slug="fighter",   hit_die="d10", primary_ability="STR", base_attributes=base["fighter"]),
            CharacterClass(id=6,  name="Monk",      slug="monk",      hit_die="d8",  primary_ability="DEX", base_attributes=base["monk"]),
            CharacterClass(id=7,  name="Paladin",   slug="paladin",   hit_die="d10", primary_ability="STR", base_attributes=base["paladin"]),
            CharacterClass(id=8,  name="Ranger",    slug="ranger",    hit_die="d10", primary_ability="DEX", base_attributes=base["ranger"]),
            CharacterClass(id=9,  name="Rogue",     slug="rogue",     hit_die="d8",  primary_ability="DEX", base_attributes=base["rogue"]),
            CharacterClass(id=10, name="Sorcerer",  slug="sorcerer",  hit_die="d6",  primary_ability="CHA", base_attributes=base["sorcerer"]),
            CharacterClass(id=11, name="Warlock",   slug="warlock",   hit_die="d8",  primary_ability="CHA", base_attributes=base["warlock"]),
            CharacterClass(id=12, name="Wizard",    slug="wizard",    hit_die="d6",  primary_ability="INT", base_attributes=base["wizard"]),
            CharacterClass(id=13, name="Artificer", slug="artificer", hit_die="d8",  primary_ability="INT", base_attributes=base["artificer"]),
        ]

    def list_playable(self) -> List[CharacterClass]:
        return list(self._classes)

    def get_by_slug(self, slug: str) -> CharacterClass | None:
        slug_key = slug.lower().strip()
        for cls in self._classes:
            if cls.slug.lower() == slug_key:
                return cls
        return None

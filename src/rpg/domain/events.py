from dataclasses import dataclass


@dataclass
class MonsterSlain:
    monster_id: int
    location_id: int
    by_character_id: int
    turn: int


@dataclass
class TickAdvanced:
    turn_after: int

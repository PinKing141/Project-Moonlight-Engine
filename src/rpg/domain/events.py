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


@dataclass
class CombatFeatureTriggered:
    character_id: int
    enemy_id: int
    feature_slug: str
    trigger_key: str
    effect_kind: str
    effect_value: int
    round_number: int


@dataclass
class EntityDamagedEvent:
    entity_id: int
    entity_name: str
    damage_amount: int
    source_entity_id: int | None = None
    source_name: str = ""
    round_number: int = 0


@dataclass
class ConcentrationBrokenEvent:
    entity_id: int
    entity_name: str
    spell_slug: str
    spell_name: str
    targets: list[int]
    reason: str
    round_number: int = 0


@dataclass
class FactionReputationChangedEvent:
    faction_id: str
    character_id: int
    delta: int
    reason: str
    changed_turn: int


@dataclass
class LevelUpPendingEvent:
    character_id: int
    from_level: int
    to_level: int
    xp: int


@dataclass
class LevelUpAppliedEvent:
    character_id: int
    from_level: int
    to_level: int
    hp_gain: int
    growth_choice: str

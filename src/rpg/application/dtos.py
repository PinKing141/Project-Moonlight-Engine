from dataclasses import dataclass, field
from typing import Dict, List
from rpg.domain.models.entity import Entity


@dataclass
class ActionResult:
    messages: List[str] = field(default_factory=list)
    game_over: bool = False


@dataclass
class EncounterPlan:
    enemies: List[Entity] = field(default_factory=list)
    definition_id: str | None = None
    faction_bias: str | None = None
    source: str = "table"
    hazards: List[str] = field(default_factory=list)


@dataclass
class CharacterSummaryView:
    id: int
    name: str
    level: int
    class_name: str
    alive: bool


@dataclass
class GameLoopView:
    character_id: int
    name: str
    race: str
    class_name: str
    difficulty: str
    hp_current: int
    hp_max: int
    world_turn: int | None
    threat_level: int | None
    time_label: str = ""
    weather_label: str = ""
    cataclysm_active: bool = False
    cataclysm_kind: str = ""
    cataclysm_phase: str = ""
    cataclysm_progress: int = 0
    cataclysm_summary: str = ""


@dataclass
class CharacterSheetView:
    character_id: int
    name: str
    race: str
    class_name: str
    difficulty: str
    level: int
    xp: int
    next_level_xp: int
    xp_to_next_level: int
    hp_current: int
    hp_max: int
    pressure_summary: str = ""
    pressure_lines: List[str] = field(default_factory=list)


@dataclass
class LevelUpPendingView:
    character_id: int
    current_level: int
    next_level: int
    xp_current: int
    xp_required: int
    growth_choices: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class EnemyView:
    id: int
    name: str
    armor_class: int
    hp_current: int
    hp_max: int


@dataclass
class ExploreView:
    has_encounter: bool
    message: str
    enemies: List[EnemyView] = field(default_factory=list)


@dataclass
class SpellOptionView:
    slug: str
    label: str
    playable: bool


@dataclass
class CharacterCreationSummaryView:
    character_id: int
    name: str
    level: int
    class_name: str
    race: str
    speed: int
    background: str
    difficulty: str
    hp_current: int
    hp_max: int
    attributes_line: str
    race_traits: List[str] = field(default_factory=list)
    background_features: List[str] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    starting_location_name: str = "Starting Town"
    subclass_name: str = ""


@dataclass
class CombatSceneView:
    distance: str
    terrain: str
    surprise: str


@dataclass
class CombatPlayerPanelView:
    hp_current: int
    hp_max: int
    armor_class: int
    attack_bonus: int
    spell_slots_current: int
    rage_label: str
    sneak_ready: str
    conditions: str


@dataclass
class CombatEnemyPanelView:
    name: str
    hp_current: int
    hp_max: int
    armor_class: int
    intent: str


@dataclass
class CombatRoundView:
    round_number: int
    scene: CombatSceneView
    player: CombatPlayerPanelView
    enemy: CombatEnemyPanelView
    options: List[str] = field(default_factory=list)


@dataclass
class CharacterClassDetailView:
    title: str
    description: str
    primary_ability: str
    hit_die: str
    combat_profile_line: str
    recommended_line: str
    options: List[str] = field(default_factory=lambda: ["Choose this class", "Back"])


@dataclass
class RewardOutcomeView:
    xp_gain: int
    money_gain: int
    loot_items: List[str] = field(default_factory=list)


@dataclass
class TownNpcView:
    id: str
    name: str
    role: str
    temperament: str
    relationship: int

    @property
    def disposition(self) -> int:
        return self.relationship

    @disposition.setter
    def disposition(self, value: int) -> None:
        self.relationship = int(value)


@dataclass
class TownView:
    day: int | None
    threat_level: int | None
    location_name: str = ""
    npcs: List[TownNpcView] = field(default_factory=list)
    consequences: List[str] = field(default_factory=list)
    district_tag: str = ""
    landmark_tag: str = ""
    active_prep_summary: str = ""
    pressure_summary: str = ""
    pressure_lines: List[str] = field(default_factory=list)
    time_label: str = ""
    weather_label: str = ""
    cataclysm_active: bool = False
    cataclysm_kind: str = ""
    cataclysm_phase: str = ""
    cataclysm_progress: int = 0
    cataclysm_summary: str = ""


@dataclass
class NpcInteractionView:
    npc_id: str
    npc_name: str
    role: str
    temperament: str
    relationship: int
    greeting: str
    approaches: List[str] = field(default_factory=list)

    @property
    def disposition(self) -> int:
        return self.relationship

    @disposition.setter
    def disposition(self, value: int) -> None:
        self.relationship = int(value)


@dataclass
class DialogueChoiceView:
    choice_id: str
    label: str
    available: bool
    locked_reason: str = ""


@dataclass
class DialogueSessionView:
    npc_id: str
    npc_name: str
    stage_id: str
    greeting: str
    choices: List[DialogueChoiceView] = field(default_factory=list)
    challenge_progress: int = 0
    challenge_target: int = 3


@dataclass
class SocialOutcomeView:
    npc_id: str
    npc_name: str
    approach: str
    success: bool
    roll_total: int
    target_dc: int
    relationship_before: int
    relationship_after: int
    messages: List[str] = field(default_factory=list)

    @property
    def disposition_before(self) -> int:
        return self.relationship_before

    @disposition_before.setter
    def disposition_before(self, value: int) -> None:
        self.relationship_before = int(value)

    @property
    def disposition_after(self) -> int:
        return self.relationship_after

    @disposition_after.setter
    def disposition_after(self, value: int) -> None:
        self.relationship_after = int(value)


@dataclass
class QuestStateView:
    quest_id: str
    title: str
    status: str
    progress: int
    target: int
    reward_xp: int
    reward_money: int
    objective_summary: str = ""
    urgency_label: str = ""


@dataclass
class QuestBoardView:
    quests: List[QuestStateView] = field(default_factory=list)
    empty_state_hint: str = ""


@dataclass
class QuestJournalSectionView:
    title: str
    quests: List[QuestStateView] = field(default_factory=list)


@dataclass
class QuestJournalView:
    sections: List[QuestJournalSectionView] = field(default_factory=list)
    empty_state_hint: str = ""


@dataclass
class ShopItemView:
    item_id: str
    name: str
    description: str
    price: int
    can_buy: bool
    availability_note: str = ""


@dataclass
class ShopView:
    gold: int
    price_modifier_label: str
    items: List[ShopItemView] = field(default_factory=list)


@dataclass
class SellItemView:
    name: str
    price: int
    equipped: bool


@dataclass
class SellInventoryView:
    gold: int
    items: List[SellItemView] = field(default_factory=list)
    empty_state_hint: str = ""


@dataclass
class EquipmentItemView:
    name: str
    slot: str | None
    equipable: bool
    equipped: bool


@dataclass
class EquipmentView:
    equipped_slots: Dict[str, str] = field(default_factory=dict)
    inventory_items: List[EquipmentItemView] = field(default_factory=list)


@dataclass
class TrainingOptionView:
    training_id: str
    title: str
    cost: int
    unlocked: bool
    can_buy: bool
    effect_summary: str
    availability_note: str = ""


@dataclass
class TrainingView:
    gold: int
    options: List[TrainingOptionView] = field(default_factory=list)


@dataclass
class RumourItemView:
    rumour_id: str
    text: str
    confidence: str
    source: str


@dataclass
class RumourBoardView:
    day: int | None
    items: List[RumourItemView] = field(default_factory=list)
    empty_state_hint: str = ""


@dataclass
class FactionStandingsView:
    standings: Dict[str, int] = field(default_factory=dict)
    descriptions: Dict[str, str] = field(default_factory=dict)
    empty_state_hint: str = ""


@dataclass
class LocationContextView:
    location_type: str
    title: str
    current_location_name: str
    act_label: str
    travel_label: str
    rest_label: str


@dataclass
class TravelDestinationView:
    location_id: int
    name: str
    location_type: str
    biome: str
    preview: str
    estimated_days: int = 1
    route_note: str = ""
    mode_hint: str = ""
    prep_summary: str = ""


@dataclass
class TravelPrepOptionView:
    prep_id: str
    title: str
    price: int
    effect_summary: str
    can_buy: bool
    active: bool
    availability_note: str = ""


@dataclass
class TravelPrepView:
    gold: int
    active_summary: str = ""
    options: List[TravelPrepOptionView] = field(default_factory=list)

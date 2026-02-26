from __future__ import annotations

from typing import Sequence

from rpg.application.dtos import (
    CombatEnemyPanelView,
    CombatPlayerPanelView,
    CombatRoundView,
    CombatSceneView,
    EquipmentItemView,
    EquipmentView,
    QuestBoardView,
    QuestStateView,
    SellInventoryView,
    SellItemView,
    RumourBoardView,
    RumourItemView,
    ShopItemView,
    ShopView,
    TravelPrepOptionView,
    TravelPrepView,
    TrainingOptionView,
    TrainingView,
    TownNpcView,
    TownView,
)


def to_town_npc_view(
    *,
    npc_id: str,
    name: str,
    role: str,
    temperament: str,
    disposition: int,
) -> TownNpcView:
    return TownNpcView(
        id=npc_id,
        name=name,
        role=role,
        temperament=temperament,
        disposition=disposition,
    )


def to_town_view(
    *,
    day: int | None,
    threat_level: int | None,
    location_name: str,
    npcs: Sequence[TownNpcView],
    consequences: Sequence[str],
    district_tag: str,
    landmark_tag: str,
    active_prep_summary: str,
) -> TownView:
    return TownView(
        day=day,
        threat_level=threat_level,
        location_name=location_name,
        npcs=list(npcs),
        consequences=list(consequences),
        district_tag=district_tag,
        landmark_tag=landmark_tag,
        active_prep_summary=active_prep_summary,
    )


def to_quest_state_view(
    *,
    quest_id: str,
    title: str,
    status: str,
    progress: int,
    target: int,
    reward_xp: int,
    reward_money: int,
    objective_summary: str,
    urgency_label: str,
) -> QuestStateView:
    return QuestStateView(
        quest_id=quest_id,
        title=title,
        status=status,
        progress=progress,
        target=target,
        reward_xp=reward_xp,
        reward_money=reward_money,
        objective_summary=objective_summary,
        urgency_label=urgency_label,
    )


def to_quest_board_view(*, quests: Sequence[QuestStateView], empty_state_hint: str) -> QuestBoardView:
    return QuestBoardView(quests=list(quests), empty_state_hint=empty_state_hint)


def to_shop_item_view(
    *,
    item_id: str,
    name: str,
    description: str,
    price: int,
    can_buy: bool,
    availability_note: str = "",
) -> ShopItemView:
    return ShopItemView(
        item_id=item_id,
        name=name,
        description=description,
        price=price,
        can_buy=can_buy,
        availability_note=availability_note,
    )


def to_shop_view(*, gold: int, price_modifier_label: str, items: Sequence[ShopItemView]) -> ShopView:
    return ShopView(gold=gold, price_modifier_label=price_modifier_label, items=list(items))


def to_training_option_view(
    *,
    training_id: str,
    title: str,
    cost: int,
    unlocked: bool,
    can_buy: bool,
    effect_summary: str,
    availability_note: str = "",
) -> TrainingOptionView:
    return TrainingOptionView(
        training_id=training_id,
        title=title,
        cost=cost,
        unlocked=unlocked,
        can_buy=can_buy,
        effect_summary=effect_summary,
        availability_note=availability_note,
    )


def to_training_view(*, gold: int, options: Sequence[TrainingOptionView]) -> TrainingView:
    return TrainingView(gold=gold, options=list(options))


def to_sell_item_view(*, name: str, price: int, equipped: bool) -> SellItemView:
    return SellItemView(name=name, price=price, equipped=equipped)


def to_sell_inventory_view(*, gold: int, items: Sequence[SellItemView], empty_state_hint: str) -> SellInventoryView:
    return SellInventoryView(gold=gold, items=list(items), empty_state_hint=empty_state_hint)


def to_equipment_item_view(*, name: str, slot: str | None, equipable: bool, equipped: bool) -> EquipmentItemView:
    return EquipmentItemView(name=name, slot=slot, equipable=equipable, equipped=equipped)


def to_equipment_view(*, equipped_slots: dict[str, str], inventory_items: Sequence[EquipmentItemView]) -> EquipmentView:
    return EquipmentView(equipped_slots=dict(equipped_slots), inventory_items=list(inventory_items))


def to_travel_prep_option_view(
    *,
    prep_id: str,
    title: str,
    price: int,
    effect_summary: str,
    can_buy: bool,
    active: bool,
    availability_note: str = "",
) -> TravelPrepOptionView:
    return TravelPrepOptionView(
        prep_id=prep_id,
        title=title,
        price=price,
        effect_summary=effect_summary,
        can_buy=can_buy,
        active=active,
        availability_note=availability_note,
    )


def to_travel_prep_view(*, gold: int, active_summary: str, options: Sequence[TravelPrepOptionView]) -> TravelPrepView:
    return TravelPrepView(gold=gold, active_summary=active_summary, options=list(options))


def to_rumour_item_view(*, rumour_id: str, text: str, confidence: str, source: str) -> RumourItemView:
    return RumourItemView(rumour_id=rumour_id, text=text, confidence=confidence, source=source)


def to_rumour_board_view(*, day: int | None, items: Sequence[RumourItemView], empty_state_hint: str) -> RumourBoardView:
    return RumourBoardView(day=day, items=list(items), empty_state_hint=empty_state_hint)


def to_combat_scene_view(*, distance: str, terrain: str, surprise: str) -> CombatSceneView:
    return CombatSceneView(distance=distance, terrain=terrain, surprise=surprise)


def to_combat_player_panel_view(
    *,
    hp_current: int,
    hp_max: int,
    armor_class: int,
    attack_bonus: int,
    spell_slots_current: int,
    rage_label: str,
    sneak_ready: str,
    conditions: str,
) -> CombatPlayerPanelView:
    return CombatPlayerPanelView(
        hp_current=hp_current,
        hp_max=hp_max,
        armor_class=armor_class,
        attack_bonus=attack_bonus,
        spell_slots_current=spell_slots_current,
        rage_label=rage_label,
        sneak_ready=sneak_ready,
        conditions=conditions,
    )


def to_combat_enemy_panel_view(
    *,
    name: str,
    hp_current: int,
    hp_max: int,
    armor_class: int,
    intent: str,
) -> CombatEnemyPanelView:
    return CombatEnemyPanelView(
        name=name,
        hp_current=hp_current,
        hp_max=hp_max,
        armor_class=armor_class,
        intent=intent,
    )


def to_combat_round_view(
    *,
    round_number: int,
    scene: CombatSceneView,
    player: CombatPlayerPanelView,
    enemy: CombatEnemyPanelView,
    options: Sequence[str],
) -> CombatRoundView:
    return CombatRoundView(
        round_number=round_number,
        scene=scene,
        player=player,
        enemy=enemy,
        options=list(options),
    )

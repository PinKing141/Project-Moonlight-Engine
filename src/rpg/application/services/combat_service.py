import random
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Tuple

from rpg.application.services.feature_effect_registry import (
    FeatureEffectContext,
    default_feature_effect_registry,
)
from rpg.domain.events import CombatFeatureTriggered
from rpg.domain.models.character import Character
from rpg.domain.models.entity import Entity
from rpg.domain.models.feature import Feature
from rpg.domain.models.stats import ability_modifier, ability_scores_from_mapping
from rpg.domain.repositories import FeatureRepository, SpellRepository
from rpg.application.spells.spell_definitions import SPELL_DEFINITIONS


@dataclass
class CombatLogEntry:
    text: str


@dataclass
class CombatResult:
    player: Character
    enemy: Entity
    log: List[CombatLogEntry]
    player_won: bool
    fled: bool = False


def ability_mod(score: int | None) -> int:
    return ability_modifier(score)


def proficiency_bonus(level: int) -> int:
    if level >= 17:
        return 6
    if level >= 13:
        return 5
    if level >= 9:
        return 4
    if level >= 5:
        return 3
    return 2


def roll_die(spec: str, rng: random.Random | None = None) -> int:
    rng = rng or random
    if not spec or not isinstance(spec, str):
        return 1
    if spec.startswith("d"):
        try:
            sides = int(spec[1:])
            return rng.randint(1, max(2, sides))
        except ValueError:
            return 1
    try:
        sides = int(spec)
        return rng.randint(1, max(2, sides))
    except ValueError:
        return 1


def _roll_dice_expr(expr: str, ability_mod: int = 0, rng: random.Random | None = None) -> int:
    rng = rng or random
    """Simple dice expression roller supporting NdX+M."""
    if not expr:
        return 0
    expr = expr.lower().replace(" ", "")
    total = 0
    parts = expr.split("+")
    for part in parts:
        if "d" in part:
            try:
                num_str, die_str = part.split("d", 1)
                num = int(num_str) if num_str else 1
                sides = int(die_str) if die_str else 6
                for _ in range(max(num, 1)):
                    total += rng.randint(1, max(2, sides))
            except Exception:
                continue
        elif part == "mod":
            total += max(ability_mod, 0)
        else:
            try:
                total += int(part)
            except Exception:
                continue
    return max(total, 0)


def _slugify_spell_name(name: str) -> str:
    return (
        "".join(ch if ch.isalnum() or ch == " " else "-" for ch in name.lower())
        .replace(" ", "-")
        .replace("--", "-")
    )


class CombatService:
    def __init__(
        self,
        spell_repo: Optional[SpellRepository] = None,
        verbosity: str = "compact",
        feature_repo: Optional[FeatureRepository] = None,
        event_publisher: Optional[Callable[[object], None]] = None,
        feature_effect_registry=None,
        mechanical_flavour_builder: Optional[Callable[..., str]] = None,
    ) -> None:
        self.spell_repo = spell_repo
        self.verbosity = verbosity  # compact | normal | debug
        self.feature_repo = feature_repo
        self.event_publisher = event_publisher
        self.feature_effect_registry = feature_effect_registry or default_feature_effect_registry()
        self.mechanical_flavour_builder = mechanical_flavour_builder
        self.rng = random.Random()

    def set_seed(self, seed: int) -> None:
        self.rng.seed(seed)

    _COMBAT_ITEM_ORDER: Tuple[str, ...] = (
        "Healing Potion",
        "Healing Herbs",
        "Sturdy Rations",
    )

    _WEAPON_BY_CLASS: Dict[str, Tuple[str, str]] = {
        "barbarian": ("d12", "strength"),
        "fighter": ("d10", "strength"),
        "paladin": ("d8", "strength"),
        "ranger": ("d8", "dexterity"),
        "rogue": ("d6", "dexterity"),
        "monk": ("d6", "dexterity"),
        "bard": ("d6", "dexterity"),
        "cleric": ("d8", "strength"),
        "druid": ("d8", "dexterity"),
        "sorcerer": ("d6", "charisma"),
        "wizard": ("d6", "intelligence"),
        "warlock": ("d8", "charisma"),
        "artificer": ("d8", "intelligence"),
    }

    _SPELL_ABILITY: Dict[str, str] = {
        "wizard": "intelligence",
        "artificer": "intelligence",
        "sorcerer": "charisma",
        "bard": "charisma",
        "warlock": "charisma",
        "cleric": "wisdom",
        "druid": "wisdom",
        "ranger": "wisdom",
        "paladin": "charisma",
    }

    _WEAPON_DIE_KEYWORDS: Dict[str, str] = {
        "greataxe": "d12",
        "greatsword": "d12",
        "longsword": "d8",
        "rapier": "d8",
        "scimitar": "d6",
        "shortsword": "d6",
        "mace": "d6",
        "hammer": "d6",
        "quarterstaff": "d6",
        "staff": "d6",
        "spear": "d6",
        "dagger": "d4",
        "javelin": "d6",
        "longbow": "d8",
        "shortbow": "d6",
        "crossbow": "d8",
        "wand": "d6",
        "rod": "d6",
    }

    _DEX_WEAPON_KEYWORDS = (
        "bow",
        "crossbow",
        "rapier",
        "dagger",
        "dart",
        "finesse",
    )

    @staticmethod
    def _ability_scores(player: Character):
        attrs: Dict[str, int] = getattr(player, "attributes", {}) or {}
        return ability_scores_from_mapping(attrs)

    def _primary_attack_mod(self, player: Character) -> int:
        scores = self._ability_scores(player)
        return max(scores.strength_mod, scores.dexterity_mod)

    def _mental_mod(self, player: Character) -> int:
        scores = self._ability_scores(player)
        return max(scores.intelligence_mod, scores.wisdom_mod, scores.charisma_mod)

    def _derive_weapon_profile(self, player: Character) -> tuple[str, int]:
        equipped = self._equipment_state(player)
        equipped_weapon = str(equipped.get("weapon", "") or "").strip().lower()
        if equipped_weapon:
            die = self._weapon_die_from_name(equipped_weapon)
            scores = self._ability_scores(player)
            if any(keyword in equipped_weapon for keyword in self._DEX_WEAPON_KEYWORDS):
                mod = scores.dexterity_mod
            else:
                mod = scores.strength_mod
            return die, mod

        slug = (player.class_name or "").lower()
        die, ability_key = self._WEAPON_BY_CLASS.get(slug, ("d6", "strength"))
        scores = self._ability_scores(player)
        mod_by_key = {
            "strength": scores.strength_mod,
            "dexterity": scores.dexterity_mod,
            "constitution": scores.constitution_mod,
            "intelligence": scores.intelligence_mod,
            "wisdom": scores.wisdom_mod,
            "charisma": scores.charisma_mod,
        }
        mod = mod_by_key.get(ability_key, scores.strength_mod)
        return die, mod

    def _derive_spell_mod(self, player: Character) -> int:
        slug = (player.class_name or "").lower()
        ability_key = self._SPELL_ABILITY.get(slug)
        scores = self._ability_scores(player)
        mod_by_key = {
            "strength": scores.strength_mod,
            "dexterity": scores.dexterity_mod,
            "constitution": scores.constitution_mod,
            "intelligence": scores.intelligence_mod,
            "wisdom": scores.wisdom_mod,
            "charisma": scores.charisma_mod,
        }
        if ability_key:
            return mod_by_key.get(ability_key, 0)
        return max(scores.intelligence_mod, scores.wisdom_mod, scores.charisma_mod)

    def _derive_ac(self, player: Character) -> int:
        scores = self._ability_scores(player)
        dex_mod = scores.dexterity_mod
        equipped = self._equipment_state(player)
        has_equipment_state = any(bool(str(equipped.get(slot, "") or "").strip()) for slot in ("weapon", "armor", "trinket"))

        if has_equipment_state:
            armor_item = str(equipped.get("armor", "") or "").strip().lower()
            shield_bonus = 2 if "shield" in armor_item else 0
            temp_bonus = getattr(player, "flags", {}).get("temp_ac_bonus", 0)

            base_ac = 10
            dex_cap: Optional[int] = None
            if "chain mail" in armor_item:
                base_ac, dex_cap = 16, 0
            elif "scale mail" in armor_item:
                base_ac, dex_cap = 14, 2
            elif "chain shirt" in armor_item:
                base_ac, dex_cap = 13, 2
            elif "leather" in armor_item:
                base_ac, dex_cap = 11, None

            dex_contrib = min(dex_mod, dex_cap) if dex_cap is not None else dex_mod
            return max(base_ac + dex_contrib + shield_bonus + temp_bonus, 10)

        inv = [item.lower() for item in getattr(player, "inventory", [])]
        shield_bonus = 2 if any("shield" in item for item in inv) else 0
        temp_bonus = getattr(player, "flags", {}).get("temp_ac_bonus", 0)

        base_ac = 10
        dex_cap: Optional[int] = None
        if any("chain mail" in item for item in inv):
            base_ac, dex_cap = 16, 0
        elif any("scale mail" in item for item in inv):
            base_ac, dex_cap = 14, 2
        elif any("chain shirt" in item for item in inv):
            base_ac, dex_cap = 13, 2
        elif any("leather armor" in item for item in inv):
            base_ac, dex_cap = 11, None

        dex_contrib = min(dex_mod, dex_cap) if dex_cap is not None else dex_mod
        return max(base_ac + dex_contrib + shield_bonus + temp_bonus, 10)

    @staticmethod
    def _equipment_state(player: Character) -> dict:
        flags = getattr(player, "flags", None)
        if not isinstance(flags, dict):
            return {}
        equipment = flags.get("equipment")
        return equipment if isinstance(equipment, dict) else {}

    def _weapon_die_from_name(self, item_name: str) -> str:
        lowered = str(item_name or "").lower()
        for key, die in self._WEAPON_DIE_KEYWORDS.items():
            if key in lowered:
                return die
        return "d6"

    def _character_features(self, player: Character) -> list[Feature]:
        if self.feature_repo is None or player.id is None:
            return []
        try:
            return list(self.feature_repo.list_for_character(player.id))
        except Exception:
            return []

    def _resolve_feature_trigger(
        self,
        *,
        features: list[Feature],
        trigger_key: str,
        player: Character,
        enemy: Entity,
        round_number: int,
        is_crit: bool = False,
    ) -> tuple[int, int, int]:
        initiative_bonus = 0
        attack_bonus = 0
        bonus_damage = 0

        context = FeatureEffectContext(
            trigger_key=trigger_key,
            round_number=round_number,
            is_crit=is_crit,
        )

        for feature in features:
            if str(feature.trigger_key) != str(trigger_key):
                continue
            outcome = self.feature_effect_registry.apply(feature, context)
            added_initiative = int(outcome.initiative_bonus)
            added_attack = int(outcome.attack_bonus)
            added_damage = int(outcome.bonus_damage)
            if added_initiative or added_attack or added_damage:
                self._publish_feature_trigger(
                    player=player,
                    enemy=enemy,
                    feature=feature,
                    round_number=round_number,
                )
            initiative_bonus += added_initiative
            attack_bonus += added_attack
            bonus_damage += added_damage

        return initiative_bonus, attack_bonus, bonus_damage

    def _publish_feature_trigger(
        self,
        *,
        player: Character,
        enemy: Entity,
        feature: Feature,
        round_number: int,
    ) -> None:
        if self.event_publisher is None:
            return
        if player.id is None:
            return
        try:
            self.event_publisher(
                CombatFeatureTriggered(
                    character_id=int(player.id),
                    enemy_id=int(getattr(enemy, "id", 0) or 0),
                    feature_slug=feature.slug,
                    trigger_key=feature.trigger_key,
                    effect_kind=feature.effect_kind,
                    effect_value=int(feature.effect_value),
                    round_number=int(round_number),
                )
            )
        except Exception:
            return

    def derive_player_stats(self, player: Character) -> dict:
        """Derive combat stats from attributes, gear, and class; avoids drift."""
        weapon_die, weapon_mod = self._derive_weapon_profile(player)
        prof = proficiency_bonus(getattr(player, "level", 1))
        ac = self._derive_ac(player)
        spell_mod = self._derive_spell_mod(player)
        return {
            "weapon_die": weapon_die,
            "weapon_mod": weapon_mod,
            "proficiency": prof,
            "attack_bonus": prof + weapon_mod,
            "damage_die": weapon_die,
            "damage_mod": weapon_mod,
            "ac": ac,
            "spell_mod": spell_mod,
            "spell_attack_bonus": prof + spell_mod,
        }

    def _intent_for_enemy(self, enemy: Entity) -> str:
        kind = (getattr(enemy, "kind", "") or "").lower()
        mapping = {
            "beast": "aggressive",
            "undead": "brute",
            "humanoid": "cautious",
            "fiend": "ambusher",
            "construct": "brute",
            "dragon": "aggressive",
        }
        return mapping.get(kind, "aggressive")

    def _intent_flavour(self, intent: str) -> str:
        flavour = {
            "aggressive": "The foe lunges without hesitation.",
            "cautious": "The foe eyes an escape route.",
            "ambusher": "The foe strikes from the shadows.",
            "brute": "The foe marches forward, uncaring of pain.",
            "skirmisher": "The foe darts in and out of reach.",
        }
        return flavour.get(intent, "The foe sizes you up.")

    def _log(self, log: List[CombatLogEntry], text: str, level: str = "compact") -> None:
        order = {"compact": 0, "normal": 1, "debug": 2}
        current = order.get(self.verbosity, 0)
        needed = order.get(level, 0)
        if current >= needed:
            log.append(CombatLogEntry(text))

    def _add_flavour(self, log: List[CombatLogEntry], tracker: dict, key: str, text: str, level: str = "normal") -> None:
        """Append a flavour line once per key to avoid text spam."""
        if tracker.get(key):
            return
        self._log(log, text, level=level)
        tracker[key] = True

    def _add_mechanical_flavour(
        self,
        log: List[CombatLogEntry],
        *,
        actor: str,
        action: str,
        enemy: Entity,
        terrain: str,
        round_no: int,
    ) -> None:
        if self.mechanical_flavour_builder is None:
            return
        try:
            line = self.mechanical_flavour_builder(
                actor=str(actor),
                action=str(action),
                enemy_kind=str(getattr(enemy, "kind", "creature") or "creature"),
                terrain=str(terrain or "open"),
                round_no=int(round_no),
            )
        except Exception:
            return
        if line:
            self._log(log, str(line), level="normal")

    def _select_enemy_action(self, intent: str, foe: Entity, round_no: int, terrain: str = "open") -> tuple[str, Optional[str]]:
        """Return (action, advantage_for_attack)."""
        hp_max = getattr(foe, "hp_max", getattr(foe, "hp", 1)) or 1
        hp_pct = (foe.hp_current or hp_max) / hp_max

        terrain_bias = 0
        if terrain == "cramped" and intent == "brute":
            terrain_bias += 0.1
        if terrain == "open" and intent in {"skirmisher", "ambusher"}:
            terrain_bias += 0.1
        if terrain == "difficult" and intent == "cautious":
            terrain_bias += 0.1

        if hp_pct <= 0.25:
            if intent in {"cautious", "skirmisher"}:
                return "flee", None
            if intent == "aggressive":
                return "reckless", "advantage"
        if hp_pct <= 0.5 and intent == "cautious":
            return "attack", "disadvantage"  # more defensive strikes

        if intent == "ambusher":
            return "attack", "advantage" if round_no == 1 else None
        if intent == "brute":
            return "attack", None
        if intent == "skirmisher":
            if hp_pct < 0.5 - terrain_bias:
                return "flee", None
            return "attack", None
        # aggressive default
        return "attack", None

    def _roll_d20(self, advantage: Optional[str] = None) -> tuple[int, int, int]:
        """Return (roll, alt_roll, chosen) where alt_roll is 0 when unused."""
        first = self.rng.randint(1, 20)
        if advantage not in {"advantage", "disadvantage"}:
            return first, 0, first

        second = self.rng.randint(1, 20)
        chosen = max(first, second) if advantage == "advantage" else min(first, second)
        return first, second, chosen

    def _attack_roll(
        self,
        attack_bonus: int,
        proficiency: int,
        ability_bonus: int,
        target_ac: int,
        advantage: Optional[str],
        log: List[CombatLogEntry],
        attacker_name: str,
        target_name: str,
    ) -> tuple[bool, bool, int, int]:
        raw, alt, chosen = self._roll_d20(advantage)
        total = chosen + attack_bonus + proficiency + ability_bonus
        if advantage == "advantage":
            self._log(log, f"{attacker_name} rolls {raw} and {alt} (advantage).", level="debug")
        elif advantage == "disadvantage":
            self._log(log, f"{attacker_name} rolls {raw} and {alt} (disadvantage).", level="debug")
        else:
            self._log(log, f"{attacker_name} rolls {raw}.", level="debug")

        is_crit = chosen == 20
        hit = is_crit or total >= target_ac
        self._log(log, f"Attack total: {chosen} + {attack_bonus} (atk) + {proficiency} (prof) + {ability_bonus} (ability) = {total} vs AC {target_ac}.", level="debug")
        if not hit:
            self._log(log, f"{attacker_name} misses {target_name}.", level="compact")
        return hit, is_crit, chosen, total

    def _deal_damage(
        self,
        damage_die: str,
        ability_bonus: int,
        is_crit: bool,
        sneak_die: Optional[str],
        rage_bonus: int,
    ) -> int:
        dmg_roll = roll_die(damage_die, rng=self.rng)
        if is_crit:
            dmg_roll += roll_die(damage_die, rng=self.rng)
        if sneak_die:
            dmg_roll += roll_die(sneak_die, rng=self.rng)
        total = dmg_roll + max(ability_bonus, 0) + rage_bonus
        return max(total, 1)

    def fight_turn_based(
        self,
        player: Character,
        enemy: Entity,
        choose_action: Callable[[List[str], Character, Entity, int, dict], tuple[str, Optional[str]] | str],
        scene: Optional[dict] = None,
    ) -> CombatResult:
        """Multi-round, DnD-lite combat. choose_action receives (options, player, enemy, round)."""
        log: List[CombatLogEntry] = []
        foe = replace(enemy)
        foe.hp_max = getattr(foe, "hp_max", foe.hp)
        foe.hp_current = getattr(foe, "hp_current", foe.hp_max)

        player = replace(player)
        player.flags = dict(getattr(player, "flags", {}) or {})
        player_hp = player.hp_current
        player.hp_max = getattr(player, "hp_max", player.hp_current)

        derived = self.derive_player_stats(player)
        attack_mod = derived["weapon_mod"]
        mental_mod = derived["spell_mod"]
        prof = derived["proficiency"]
        player.armour_class = derived["ac"]
        features = self._character_features(player)
        sneak_available = player.class_name == "rogue"
        rage_available = player.class_name == "barbarian"
        rage_rounds = 0
        player_dodge = False
        scores = self._ability_scores(player)
        surprise = (scene or {}).get("surprise")
        def _roll_initiative(with_adv: bool, base_bonus: int) -> int:
            if not with_adv:
                return self.rng.randint(1, 20) + base_bonus
            r1 = self.rng.randint(1, 20)
            r2 = self.rng.randint(1, 20)
            return max(r1, r2) + base_bonus

        initiative_bonus, _, _ = self._resolve_feature_trigger(
            features=features,
            trigger_key="on_initiative",
            player=player,
            enemy=foe,
            round_number=1,
        )
        initiative_player = _roll_initiative(surprise == "player", scores.initiative + initiative_bonus)
        initiative_enemy = _roll_initiative(surprise == "enemy", getattr(foe, "attack_bonus", 0))
        player_has_opening = initiative_player >= initiative_enemy
        self._log(log, f"Initiative: You {initiative_player} vs {foe.name} {initiative_enemy}.", level="normal")
        turn_order = ["player", "enemy"] if initiative_player >= initiative_enemy else ["enemy", "player"]

        round_no = 1
        fled = False
        distance = (scene or {}).get("distance", "close")
        terrain = (scene or {}).get("terrain", "open")
        flavour_tracker: dict[str, bool] = {}
        while player_hp > 0 and foe.hp_current > 0:
            if player.class_name == "rogue":
                sneak_available = True
            self._log(log, f"-- Round {round_no} --", level="debug")
            intent = self._intent_for_enemy(foe)
            round_flavour_used = False
            for actor in turn_order:
                if actor == "player":
                    advantage_state = "advantage" if player_has_opening and round_no == 1 else None
                    options = ["Attack", "Dash", "Dodge", "Use Item", "Flee"]
                    has_magic = (getattr(player, "spell_slots_current", 0) > 0) or bool(getattr(player, "cantrips", []))
                    if has_magic:
                        options.insert(1, "Cast Spell")
                    if rage_available and rage_rounds <= 0:
                        options.insert(1, "Rage Attack")
                    choice = choose_action(options, player, foe, round_no, {"distance": distance, "terrain": terrain, "surprise": surprise})
                    action_payload = None
                    action = choice
                    if isinstance(choice, tuple):
                        action, action_payload = choice

                    if action == "Rage Attack" and rage_available and rage_rounds <= 0:
                        rage_rounds = 3
                        player.flags["rage_rounds"] = rage_rounds
                        self._log(log, "You fly into a rage!", level="normal")
                        action = "Attack"

                    if action == "Attack":
                        sneak_die = "d6" if sneak_available else None
                        _, roll_attack_bonus, _ = self._resolve_feature_trigger(
                            features=features,
                            trigger_key="on_attack_roll",
                            player=player,
                            enemy=foe,
                            round_number=round_no,
                        )
                        hit, is_crit, _, _ = self._attack_roll(
                            roll_attack_bonus,
                            prof,
                            attack_mod,
                            foe.armour_class,
                            advantage_state,
                            log,
                            player.name,
                            foe.name,
                        )
                        if hit:
                            dmg = self._deal_damage(
                                derived["damage_die"],
                                derived["damage_mod"],
                                is_crit,
                                sneak_die if sneak_available else None,
                                rage_rounds > 0 and 2 or 0,
                            )
                            _, _, hit_bonus_damage = self._resolve_feature_trigger(
                                features=features,
                                trigger_key="on_attack_hit",
                                player=player,
                                enemy=foe,
                                round_number=round_no,
                                is_crit=is_crit,
                            )
                            dmg += hit_bonus_damage
                            foe.hp_current = max(0, foe.hp_current - dmg)
                            self._log(log, f"You deal {dmg} damage to {foe.name} ({foe.hp_current}/{foe.hp_max}).", level="compact")
                            sneak_available = False
                        else:
                            self._log(log, "Your strike fails to connect.", level="compact")
                        self._add_mechanical_flavour(
                            log,
                            actor="player",
                            action="attack",
                            enemy=foe,
                            terrain=terrain,
                            round_no=round_no,
                        )

                    elif action == "Cast Spell":
                        self._resolve_spell_cast(player, foe, action_payload, spell_mod, prof, log)
                        self._add_mechanical_flavour(
                            log,
                            actor="player",
                            action="cast_spell",
                            enemy=foe,
                            terrain=terrain,
                            round_no=round_no,
                        )

                    elif action == "Dodge":
                        player_dodge = True
                        player.flags["dodging"] = 1
                        self._log(log, "You focus on defense; incoming attacks have disadvantage.", level="compact")

                    elif action == "Use Item":
                        player_hp = self._resolve_use_item(player, player_hp, log, preferred_item=action_payload)

                    elif action == "Flee":
                        flee_roll = self.rng.randint(1, 20) + attack_mod
                        if flee_roll >= 12:
                            self._log(log, "You slip away from the fight!", level="compact")
                            fled = True
                            return CombatResult(player, foe, log, player_won=False, fled=True)
                        else:
                            self._log(log, "You fail to escape.", level="compact")

                    elif action == "Dash":
                        if distance == "far":
                            distance = "mid"
                        elif distance == "mid":
                            distance = "close"
                        self._log(log, f"You dash forward. Distance is now {distance}.", level="compact")

                else:  # enemy turn
                    if not round_flavour_used:
                        self._add_flavour(log, flavour_tracker, f"intent_{round_no}", self._intent_flavour(intent))
                        round_flavour_used = True
                    enemy_action, enemy_advantage = self._select_enemy_action(intent, foe, round_no, terrain)
                    if enemy_action == "flee":
                        self._log(log, f"{foe.name} tries to flee the battle!", level="compact")
                        foe.hp_current = 0
                        break

                    if distance == "far":
                        self._log(log, f"{foe.name} closes in.", level="compact")
                        distance = "mid"
                        continue
                    elif distance == "mid" and enemy_action == "attack":
                        # ranged not modeled; treat as disadvantaged strike
                        enemy_advantage = "disadvantage"

                    target_ac = player.armour_class
                    if enemy_action == "reckless":
                        enemy_advantage = "advantage"
                        foe_armour_class = getattr(foe, "armour_class", 10) - 2
                        foe.armour_class = max(8, foe_armour_class)
                        self._log(log, f"{foe.name} fights recklessly, leaving openings.", level="compact")

                    advantage_state = "disadvantage" if player_dodge else enemy_advantage
                    hit, is_crit, _, _ = self._attack_roll(
                        foe.attack_bonus,
                        0,
                        0,
                        target_ac,
                        advantage_state,
                        log,
                        foe.name,
                        player.name,
                    )
                    if hit:
                        dmg = self._deal_damage(
                            foe.damage_die,
                            0,
                            is_crit,
                            None,
                            0,
                        )
                        player_hp = max(0, player_hp - dmg)
                        self._log(log, f"{foe.name} hits you for {dmg} damage ({player_hp}/{player.hp_max}).", level="compact")
                    else:
                        self._log(log, f"{foe.name} misses you.", level="compact")
                    self._add_mechanical_flavour(
                        log,
                        actor="enemy",
                        action=enemy_action,
                        enemy=foe,
                        terrain=terrain,
                        round_no=round_no,
                    )

            player_dodge = False
        player.flags.pop("dodging", None)
        if rage_rounds > 0:
            rage_rounds -= 1
            player.flags["rage_rounds"] = rage_rounds
        if player.flags.get("shield_rounds"):
            player.flags["shield_rounds"] = max(player.flags.get("shield_rounds", 0) - 1, 0)
            if player.flags["shield_rounds"] <= 0:
                player.flags.pop("temp_ac_bonus", None)
            round_no += 1
            if round_no > 50:
                player.hp_current = player_hp
                player.alive = player_hp > 0
                return CombatResult(
                    player,
                    foe,
                    log,
                    player_won=player_hp > 0 and foe.hp_current <= 0,
                )

        player.hp_current = player_hp
        player.alive = player_hp > 0

        if foe.hp_current <= 0:
            xp_gain = max(getattr(foe, "level", 1) * 5, 1)
            player.xp += xp_gain
            self._log(log, f"{foe.name} falls. +{xp_gain} XP.", level="compact")

        return CombatResult(player, foe, log, player_won=player_hp > 0 and foe.hp_current <= 0)

    def list_usable_items(self, player: Character) -> List[str]:
        inventory = list(getattr(player, "inventory", []) or [])
        available: List[str] = []
        for item_name in self._COMBAT_ITEM_ORDER:
            if item_name in inventory:
                available.append(item_name)
        return available

    def _resolve_use_item(
        self,
        player: Character,
        player_hp: int,
        log: List[CombatLogEntry],
        preferred_item: Optional[str] = None,
    ) -> int:
        inventory = list(getattr(player, "inventory", []) or [])

        usable_items = self.list_usable_items(player)
        selected_item = None
        if preferred_item and str(preferred_item) in usable_items:
            selected_item = str(preferred_item)
        elif usable_items:
            selected_item = usable_items[0]

        if selected_item == "Healing Potion":
            player.inventory.remove("Healing Potion")
            heal = roll_die("d4", rng=self.rng) + roll_die("d4", rng=self.rng) + 2
            player_hp = min(player.hp_max, player_hp + heal)
            self._log(log, f"You drink a potion and heal {heal} HP ({player_hp}/{player.hp_max}).", level="compact")
            return player_hp

        if selected_item == "Healing Herbs":
            player.inventory.remove("Healing Herbs")
            heal = roll_die("d4", rng=self.rng) + 1
            player_hp = min(player.hp_max, player_hp + heal)
            self._log(log, f"You apply healing herbs and recover {heal} HP ({player_hp}/{player.hp_max}).", level="compact")
            return player_hp

        if selected_item == "Sturdy Rations":
            player.inventory.remove("Sturdy Rations")
            heal = 2
            player_hp = min(player.hp_max, player_hp + heal)
            self._log(log, f"You take a quick ration break and recover {heal} HP ({player_hp}/{player.hp_max}).", level="compact")
            return player_hp

        self._log(log, "No usable items found.", level="compact")
        return player_hp

    def _resolve_spell_cast(
        self,
        player: Character,
        foe: Entity,
        spell_slug: Optional[str],
        spell_mod: int,
        prof: int,
        log: List[CombatLogEntry],
    ) -> None:
        # Fallback to first known spell if none provided
        known = getattr(player, "known_spells", []) or []
        target_slug = spell_slug or (_slugify_spell_name(known[0]) if known else None)
        if not target_slug:
            self._log(log, "You have no spells to cast.", level="compact")
            return

        definition = SPELL_DEFINITIONS.get(target_slug)
        if not definition:
            self._log(log, f"{target_slug} is not implemented in combat yet.", level="compact")
            return

        spell = self.spell_repo.get_by_slug(target_slug) if self.spell_repo else None
        level_int = spell.level_int if spell else 0
        if level_int > 0:
            slots = getattr(player, "spell_slots_current", 0)
            if slots <= 0:
                self._log(log, "No spell slots remaining.", level="compact")
                return
            player.spell_slots_current = max(slots - 1, 0)
            self._log(log, "You expend a spell slot.", level="compact")

        spell_attack_bonus = prof + spell_mod
        spell_dc = 8 + prof + spell_mod
        foe_ac = getattr(foe, "armour_class", 10)

        def _foe_save_mod(ability: Optional[str]) -> int:
            # Simple approximation; entities currently do not have saves
            return 0

        def _apply_damage(amount: int, damage_type: str | None) -> None:
            if damage_type == "healing":
                player.hp_current = min(player.hp_max, player.hp_current + amount)
                self._log(log, f"You restore {amount} HP ({player.hp_current}/{player.hp_max}).", level="compact")
            else:
                foe.hp_current = max(0, foe.hp_current - amount)
                self._log(log, f"The spell hits {foe.name} for {amount} {damage_type or 'damage'} ({foe.hp_current}/{foe.hp_max}).", level="compact")

        if definition.resolution == "spell_attack":
            hit, is_crit, _, _ = self._attack_roll(
                0,
                prof,
                spell_mod,
                foe_ac,
                None,
                log,
                player.name,
                foe.name,
            )
            if hit:
                dice_expr = definition.damage_dice or "1d6"
                dmg = _roll_dice_expr(dice_expr, ability_mod=spell_mod, rng=self.rng)
                if is_crit:
                    dmg += _roll_dice_expr(dice_expr, ability_mod=0, rng=self.rng)
                _apply_damage(dmg, definition.damage_type)
            else:
                self._log(log, "Your spell fizzles past the enemy.", level="compact")
        elif definition.resolution == "save":
            save_mod = _foe_save_mod(definition.save_ability)
            save_roll = self.rng.randint(1, 20) + save_mod
            self._log(log, f"{foe.name} attempts a save: {save_roll} vs DC {spell_dc}.", level="debug")
            if save_roll >= spell_dc:
                self._log(log, f"{foe.name} resists the spell.", level="compact")
                return
            dmg = _roll_dice_expr(definition.damage_dice or "1d6", ability_mod=spell_mod, rng=self.rng)
            _apply_damage(dmg, definition.damage_type)
        else:  # auto
            dmg = _roll_dice_expr(definition.damage_dice or "1d4", ability_mod=spell_mod, rng=self.rng)
            if definition.damage_type == "healing":
                _apply_damage(dmg, "healing")
            elif definition.slug == "shield":
                bonus = 5
                player.flags["temp_ac_bonus"] = bonus
                player.flags["shield_rounds"] = 1
                self._log(log, f"A shimmering barrier grants +{bonus} AC until your next turn.", level="compact")
            else:
                _apply_damage(dmg, definition.damage_type)

    def _player_attack(self, player: Character, foe: Entity, log: List[CombatLogEntry]) -> None:
        roll = self.rng.randint(1, 20)
        total = roll + player.attack_bonus
        if roll == 20:
            dmg = roll_die(player.damage_die, rng=self.rng) + roll_die(player.damage_die, rng=self.rng)
            dmg = max(int(dmg * getattr(player, "outgoing_damage_multiplier", 1.0)), 1)
            foe.hp_current = max(0, foe.hp_current - dmg)
            self._log(log, f"Critical hit! You roll a natural 20 and deal {dmg} damage ({foe.hp_current}/{foe.hp_max} HP left).", level="normal")
        elif total >= foe.armour_class:
            dmg = roll_die(player.damage_die, rng=self.rng)
            dmg = max(int(dmg * getattr(player, "outgoing_damage_multiplier", 1.0)), 1)
            foe.hp_current = max(0, foe.hp_current - dmg)
            self._log(log, f"You roll {roll} + {player.attack_bonus} = {total} and hit for {dmg} damage ({foe.hp_current}/{foe.hp_max} HP left).", level="compact")
        else:
            self._log(log, f"You roll {roll} + {player.attack_bonus} = {total} and miss.", level="compact")

    def _enemy_attack(self, player: Character, foe: Entity, log: List[CombatLogEntry]) -> None:
        roll = self.rng.randint(1, 20)
        total = roll + foe.attack_bonus
        if roll == 20:
            dmg = roll_die(foe.damage_die, rng=self.rng) + roll_die(foe.damage_die, rng=self.rng)
            dmg = max(int(dmg * getattr(player, "incoming_damage_multiplier", 1.0)), 1)
            player.hp_current = max(0, player.hp_current - dmg)
            self._log(log, f"Critical! The {foe.name} lands a brutal blow for {dmg} damage ({player.hp_current}/{player.hp_max} HP left).", level="normal")
        elif total >= player.armour_class:
            dmg = roll_die(foe.damage_die, rng=self.rng)
            dmg = max(int(dmg * getattr(player, "incoming_damage_multiplier", 1.0)), 1)
            player.hp_current = max(0, player.hp_current - dmg)
            self._log(log, f"The {foe.name} rolls {roll} + {foe.attack_bonus} = {total} and hits for {dmg} damage ({player.hp_current}/{player.hp_max} HP left).", level="compact")
        else:
            self._log(log, f"The {foe.name} rolls {roll} + {foe.attack_bonus} = {total} and misses you.", level="compact")

    def fight_simple(self, player: Character, enemy: Entity) -> CombatResult:
        log: List[CombatLogEntry] = []

        foe = replace(enemy)
        foe.hp_max = getattr(foe, "hp_max", foe.hp)
        foe.hp_current = getattr(foe, "hp_current", foe.hp_max)

        self._player_attack(player, foe, log)

        if foe.hp_current <= 0:
            xp_gain = max(getattr(foe, "level", 1) * 5, 1)
            player.xp += xp_gain
            self._log(log, f"The {foe.name} collapses. (+{xp_gain} XP)", level="compact")
            return CombatResult(player, foe, log, player_won=True)

        self._enemy_attack(player, foe, log)

        player_won = player.hp_current > 0
        if not player_won:
            self._log(log, "You drop to the ground, consciousness fading...", level="compact")

        return CombatResult(player, foe, log, player_won=player_won)

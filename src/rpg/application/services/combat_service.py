import random
import copy
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Tuple

from rpg.application.services.feature_effect_registry import (
    ConditionEffect,
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


@dataclass
class PartyCombatResult:
    allies: List[Character]
    enemies: List[Entity]
    log: List[CombatLogEntry]
    allies_won: bool
    fled: bool = False


PartyTargetSelection = int | tuple[str, int] | None
LegacyPartyTargetSelector = Callable[[Character, List[Entity], int, dict], Optional[int]]
ExtendedPartyTargetSelector = Callable[[Character, List[Character], List[Entity], int, dict, str], PartyTargetSelection]
PartyTargetSelector = LegacyPartyTargetSelector | ExtendedPartyTargetSelector


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
    _RANGE_ALIAS: Dict[str, str] = {
        "engaged": "engaged",
        "close": "engaged",
        "near": "near",
        "mid": "near",
        "far": "far",
    }

    _BACKLINE_CLASSES: Tuple[str, ...] = ("wizard", "sorcerer", "warlock", "bard")
    _BACKLINE_NAME_KEYWORDS: Tuple[str, ...] = (
        "archer",
        "shaman",
        "mage",
        "warlock",
        "witch",
        "priest",
        "acolyte",
    )
    _BOSS_NAME_KEYWORDS: Tuple[str, ...] = (
        "dragon",
        "tyrant",
        "lord",
        "queen",
        "king",
        "ancient",
        "demon",
        "lich",
        "boss",
    )

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
        "Focus Potion",
        "Whetstone",
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
    _STATUS_LABELS: Dict[str, str] = {
        "poisoned": "Poisoned",
        "burning": "Burning",
        "blessed": "Blessed",
        "stunned": "Stunned",
        "blinded": "Blinded",
        "charmed": "Charmed",
        "deafened": "Deafened",
        "paralysed": "Paralysed",
        "frightened": "Frightened",
        "grappled": "Grappled",
        "incapacitated": "Incapacitated",
        "invisible": "Invisible",
        "petrified": "Petrified",
        "prone": "Prone",
        "restrained": "Restrained",
        "exhaustion": "Exhaustion",
        "unconscious": "Unconscious",
    }
    _STATUS_ATTACK_ROLL_SHIFT: Dict[str, int] = {
        "poisoned": -2,
        "blessed": 2,
    }
    _TACTICAL_LABELS: Dict[str, str] = {
        "concealed": "Concealed",
        "cover": "Cover",
        "high_ground": "High Ground",
        "hidden_strike": "Hidden Strike",
        "helped": "Helped",
        "exposed": "Exposed",
        "dodging": "Dodging",
        "disengaged": "Disengaged",
    }

    @staticmethod
    def _ability_scores(player: Character):
        attrs: Dict[str, int] = getattr(player, "attributes", {}) or {}
        return ability_scores_from_mapping(attrs)

    def _actor_statuses(self, actor) -> List[Dict[str, int | str]]:
        if isinstance(actor, Character):
            flags = getattr(actor, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                actor.flags = flags
            raw = flags.setdefault("combat_statuses", [])
            if not isinstance(raw, list):
                raw = []
                flags["combat_statuses"] = raw
            return [row for row in raw if isinstance(row, dict) and str(row.get("id", "")).strip()]

        raw = getattr(actor, "_combat_statuses", None)
        if not isinstance(raw, list):
            raw = []
            setattr(actor, "_combat_statuses", raw)
        return [row for row in raw if isinstance(row, dict) and str(row.get("id", "")).strip()]

    def _set_actor_statuses(self, actor, statuses: List[Dict[str, int | str]]) -> None:
        normalized = [
            {
                "id": str(row.get("id", "")).strip().lower(),
                "rounds": max(0, int(row.get("rounds", 0) or 0)),
                "potency": max(1, int(row.get("potency", 1) or 1)),
                "source_id": int(row.get("source_id", 0) or 0),
                "source_name": str(row.get("source_name", "") or "").strip(),
            }
            for row in statuses
            if str(row.get("id", "")).strip()
        ]
        if isinstance(actor, Character):
            flags = getattr(actor, "flags", None)
            if not isinstance(flags, dict):
                flags = {}
                actor.flags = flags
            flags["combat_statuses"] = normalized
            return
        setattr(actor, "_combat_statuses", normalized)

    def _has_status(self, actor, status_id: str) -> bool:
        key = str(status_id or "").strip().lower()
        return any(str(row.get("id", "")).strip().lower() == key and int(row.get("rounds", 0) or 0) > 0 for row in self._actor_statuses(actor))

    def _has_status_from_source(self, actor, status_id: str, source_actor) -> bool:
        key = str(status_id or "").strip().lower()
        source_id = int(getattr(source_actor, "id", 0) or 0)
        source_name = str(getattr(source_actor, "name", "") or "").strip().lower()
        for row in self._actor_statuses(actor):
            row_key = str(row.get("id", "")).strip().lower()
            rounds = int(row.get("rounds", 0) or 0)
            if row_key != key or rounds <= 0:
                continue
            row_source_id = int(row.get("source_id", 0) or 0)
            row_source_name = str(row.get("source_name", "") or "").strip().lower()
            if source_id and row_source_id == source_id:
                return True
            if source_name and row_source_name and row_source_name == source_name:
                return True
        return False

    def _status_potency(self, actor, status_id: str) -> int:
        key = str(status_id or "").strip().lower()
        best = 0
        for row in self._actor_statuses(actor):
            row_key = str(row.get("id", "")).strip().lower()
            rounds = int(row.get("rounds", 0) or 0)
            if row_key != key or rounds <= 0:
                continue
            best = max(best, int(row.get("potency", 1) or 1))
        return int(best)

    def _exhaustion_level(self, actor) -> int:
        return int(self._status_potency(actor, "exhaustion") or 0)

    def _movement_blocked(self, actor) -> bool:
        if (
            self._has_status(actor, "stunned")
            or self._has_status(actor, "paralysed")
            or self._has_status(actor, "restrained")
            or self._has_status(actor, "grappled")
            or self._has_status(actor, "incapacitated")
            or self._has_status(actor, "petrified")
            or self._has_status(actor, "unconscious")
        ):
            return True
        return self._exhaustion_level(actor) >= 5

    def _turn_blocked(self, actor) -> bool:
        if (
            self._has_status(actor, "stunned")
            or self._has_status(actor, "paralysed")
            or self._has_status(actor, "incapacitated")
            or self._has_status(actor, "petrified")
            or self._has_status(actor, "unconscious")
        ):
            return True
        return self._exhaustion_level(actor) >= 6

    def _ability_check_disadvantage(self, actor, *, requires_sight: bool = False, requires_hearing: bool = False) -> bool:
        if requires_sight and self._has_status(actor, "blinded"):
            return True
        if requires_hearing and self._has_status(actor, "deafened"):
            return True
        if self._has_status(actor, "poisoned") or self._has_status(actor, "frightened"):
            return True
        return self._exhaustion_level(actor) >= 1

    def _ability_check_roll(self, actor, modifier: int, *, requires_sight: bool = False, requires_hearing: bool = False) -> int:
        if self._ability_check_disadvantage(actor, requires_sight=requires_sight, requires_hearing=requires_hearing):
            roll = min(self.rng.randint(1, 20), self.rng.randint(1, 20))
        else:
            roll = self.rng.randint(1, 20)
        return int(roll + int(modifier))

    @staticmethod
    def _combine_advantage(base: Optional[str], delta: int) -> Optional[str]:
        score = 0
        if base == "advantage":
            score += 1
        elif base == "disadvantage":
            score -= 1
        score += int(delta)
        if score > 0:
            return "advantage"
        if score < 0:
            return "disadvantage"
        return None

    def _condition_advantage_delta(self, attacker, defender, *, distance: str = "close") -> int:
        delta = 0
        if self._has_status(attacker, "blinded"):
            delta -= 1
        if self._has_status(attacker, "restrained"):
            delta -= 1
        if self._has_status(attacker, "paralysed"):
            delta -= 1
        if self._has_status(attacker, "stunned"):
            delta -= 1
        if self._has_status(attacker, "prone"):
            delta -= 1
        if self._has_status(attacker, "poisoned"):
            delta -= 1
        if self._has_status(attacker, "frightened"):
            delta -= 1
        if self._exhaustion_level(attacker) >= 3:
            delta -= 1
        if self._has_status(attacker, "invisible"):
            delta += 1

        if self._has_status(defender, "blinded"):
            delta += 1
        if self._has_status(defender, "restrained"):
            delta += 1
        if self._has_status(defender, "paralysed"):
            delta += 1
        if self._has_status(defender, "stunned"):
            delta += 1
        if self._has_status(defender, "incapacitated"):
            delta += 1
        if self._has_status(defender, "unconscious"):
            delta += 1
        if self._has_status(defender, "petrified"):
            delta += 1
        if self._has_status(defender, "invisible"):
            delta -= 1
        if self._has_status(defender, "prone"):
            if self._is_melee_range(distance):
                delta += 1
            else:
                delta -= 1
        return int(delta)

    @staticmethod
    def _is_melee_range(distance: str | None) -> bool:
        normalized = str(distance or "engaged").strip().lower()
        return CombatService._RANGE_ALIAS.get(normalized, "engaged") == "engaged"

    @classmethod
    def _normalize_range_band(cls, distance: str | None) -> str:
        normalized = str(distance or "engaged").strip().lower()
        return cls._RANGE_ALIAS.get(normalized, "engaged")

    @classmethod
    def _range_label(cls, distance: str | None) -> str:
        band = cls._normalize_range_band(distance)
        labels = {"engaged": "Engaged", "near": "Near", "far": "Far"}
        return labels.get(band, "Engaged")

    @classmethod
    def _step_toward_engagement(cls, distance: str | None) -> str:
        band = cls._normalize_range_band(distance)
        if band == "far":
            return "near"
        if band == "near":
            return "engaged"
        return "engaged"

    @classmethod
    def _is_attack_viable_for_range(cls, *, is_melee_attack: bool, distance: str | None) -> bool:
        band = cls._normalize_range_band(distance)
        if is_melee_attack:
            return band == "engaged"
        return band in {"engaged", "near", "far"}

    def _modify_incoming_damage(self, target, damage: int) -> int:
        total = max(0, int(damage))
        if self._has_status(target, "petrified"):
            total = max(1, total // 2)
        return max(total, 0)

    def _apply_status(
        self,
        *,
        actor,
        status_id: str,
        rounds: int,
        log: List[CombatLogEntry],
        potency: int = 1,
        source_name: str = "Effect",
        source_actor=None,
    ) -> None:
        key = str(status_id or "").strip().lower()
        if key not in self._STATUS_LABELS:
            return
        next_rounds = max(1, int(rounds or 1))
        next_potency = max(1, int(potency or 1))
        statuses = self._actor_statuses(actor)
        existing = next((row for row in statuses if str(row.get("id", "")).strip().lower() == key), None)
        source_id = int(getattr(source_actor, "id", 0) or 0)
        source_label = str(getattr(source_actor, "name", "") or "").strip() or str(source_name or "")
        if existing is not None:
            existing["rounds"] = max(int(existing.get("rounds", 0) or 0), next_rounds)
            existing["potency"] = max(int(existing.get("potency", 1) or 1), next_potency)
            if source_id:
                existing["source_id"] = source_id
            if source_label:
                existing["source_name"] = source_label
        else:
            statuses.append(
                {
                    "id": key,
                    "rounds": next_rounds,
                    "potency": next_potency,
                    "source_id": source_id,
                    "source_name": source_label,
                }
            )
            self._log(log, f"{source_name}: {getattr(actor, 'name', 'Target')} is now {self._STATUS_LABELS[key]} ({next_rounds} rounds).", level="compact")
            if key == "unconscious" and not self._has_status(actor, "prone"):
                statuses.append(
                    {
                        "id": "prone",
                        "rounds": max(next_rounds, 1),
                        "potency": 1,
                        "source_id": source_id,
                        "source_name": source_label,
                    }
                )
        self._set_actor_statuses(actor, statuses)

    def _status_attack_roll_shift(self, actor) -> int:
        shift = 0
        for row in self._actor_statuses(actor):
            key = str(row.get("id", "")).strip().lower()
            rounds = int(row.get("rounds", 0) or 0)
            potency = max(1, int(row.get("potency", 1) or 1))
            if rounds <= 0:
                continue
            shift += int(self._STATUS_ATTACK_ROLL_SHIFT.get(key, 0)) * potency
        return int(shift)

    def _apply_start_turn_statuses(self, actor, log: List[CombatLogEntry]) -> None:
        statuses = self._actor_statuses(actor)
        hp_now = int(getattr(actor, "hp_current", 0) or 0)
        hp_max = int(getattr(actor, "hp_max", hp_now) or hp_now)
        for row in statuses:
            if hp_now <= 0:
                break
            key = str(row.get("id", "")).strip().lower()
            rounds = int(row.get("rounds", 0) or 0)
            potency = max(1, int(row.get("potency", 1) or 1))
            if rounds <= 0:
                continue
            if key == "burning":
                damage = sum(roll_die("d4", rng=self.rng) for _ in range(potency))
                damage = self._modify_incoming_damage(actor, damage)
                hp_now = max(0, hp_now - damage)
                self._log(log, f"{getattr(actor, 'name', 'Target')} burns for {damage} damage ({hp_now}/{hp_max}).", level="compact")
            elif key == "poisoned":
                if self._has_status(actor, "petrified"):
                    continue
                damage = max(1, potency)
                damage = self._modify_incoming_damage(actor, damage)
                hp_now = max(0, hp_now - damage)
                self._log(log, f"{getattr(actor, 'name', 'Target')} suffers {damage} poison damage ({hp_now}/{hp_max}).", level="compact")
            elif key == "exhaustion":
                if potency >= 6:
                    hp_now = 0
                    self._log(log, f"{getattr(actor, 'name', 'Target')} collapses from exhaustion.", level="compact")
                    break
                if potency >= 4:
                    cap = max(1, hp_max // 2)
                    if hp_now > cap:
                        hp_now = cap
                        self._log(log, f"{getattr(actor, 'name', 'Target')} is drained by exhaustion ({hp_now}/{hp_max}).", level="compact")
        actor.hp_current = hp_now

    def _tick_actor_statuses_end_turn(self, actor, log: List[CombatLogEntry]) -> None:
        statuses = self._actor_statuses(actor)
        remaining: List[Dict[str, int | str]] = []
        for row in statuses:
            key = str(row.get("id", "")).strip().lower()
            rounds = int(row.get("rounds", 0) or 0)
            potency = max(1, int(row.get("potency", 1) or 1))
            if rounds <= 0:
                continue
            rounds -= 1
            if rounds <= 0:
                label = self._STATUS_LABELS.get(key, key.title())
                self._log(log, f"{getattr(actor, 'name', 'Target')} is no longer {label}.", level="normal")
                continue
            remaining.append(
                {
                    "id": key,
                    "rounds": rounds,
                    "potency": potency,
                    "source_id": int(row.get("source_id", 0) or 0),
                    "source_name": str(row.get("source_name", "") or "").strip(),
                }
            )
        self._set_actor_statuses(actor, remaining)

    def _actor_tactical_tags(self, actor) -> Dict[str, int]:
        if isinstance(actor, Character):
            flags = getattr(actor, "flags", None)
            if not isinstance(flags, dict):
                return {}
            payload = flags.get("combat_tactical_tags")
        else:
            payload = getattr(actor, "_combat_tactical_tags", None)
        if not isinstance(payload, dict):
            return {}

        normalized: Dict[str, int] = {}
        for key, value in payload.items():
            slug = str(key or "").strip().lower()
            rounds = int(value or 0)
            if slug and rounds > 0:
                normalized[slug] = rounds
        return normalized

    def _set_actor_tactical_tags(self, actor, tags: Dict[str, int]) -> None:
        normalized: Dict[str, int] = {}
        for key, value in tags.items():
            slug = str(key or "").strip().lower()
            rounds = int(value or 0)
            if slug and rounds > 0:
                normalized[slug] = rounds
        if isinstance(actor, Character):
            flags = getattr(actor, "flags", None)
            if not isinstance(flags, dict):
                return
            if normalized:
                flags["combat_tactical_tags"] = normalized
            else:
                flags.pop("combat_tactical_tags", None)
            return
        setattr(actor, "_combat_tactical_tags", normalized)

    def _add_tactical_tag(self, actor, *, tag: str, rounds: int) -> None:
        key = str(tag or "").strip().lower()
        if not key:
            return
        next_rounds = max(1, int(rounds or 1))
        tags = self._actor_tactical_tags(actor)
        tags[key] = max(int(tags.get(key, 0) or 0), next_rounds)
        self._set_actor_tactical_tags(actor, tags)

    def _has_tactical_tag(self, actor, tag: str) -> bool:
        key = str(tag or "").strip().lower()
        return key in self._actor_tactical_tags(actor)

    def _consume_tactical_tag(self, actor, tag: str) -> bool:
        key = str(tag or "").strip().lower()
        tags = self._actor_tactical_tags(actor)
        if key not in tags:
            return False
        tags.pop(key, None)
        self._set_actor_tactical_tags(actor, tags)
        return True

    def _tick_actor_tactical_tags_end_turn(self, actor) -> None:
        tags = self._actor_tactical_tags(actor)
        remaining: Dict[str, int] = {}
        for key, rounds in tags.items():
            next_rounds = int(rounds) - 1
            if next_rounds > 0:
                remaining[key] = next_rounds
        self._set_actor_tactical_tags(actor, remaining)

    def _clear_actor_tactical_tags(self, actor) -> None:
        self._set_actor_tactical_tags(actor, {})

    def _terrain_supports_hiding(self, *, terrain: str, distance: str) -> bool:
        terrain_key = str(terrain or "").strip().lower()
        if terrain_key in {"forest", "jungle", "woodland", "swamp", "wetland", "marsh", "bog", "cramped"}:
            return True
        return self._normalize_range_band(distance) != "engaged"

    def _tactical_advantage_delta(self, *, attacker, defender) -> int:
        delta = 0
        if self._has_tactical_tag(attacker, "high_ground"):
            delta += 1
        if self._has_tactical_tag(attacker, "hidden_strike"):
            delta += 1
        if self._has_tactical_tag(attacker, "helped"):
            delta += 1

        if self._has_tactical_tag(defender, "cover"):
            delta -= 1
        if self._has_tactical_tag(defender, "concealed"):
            delta -= 1
        if self._has_tactical_tag(defender, "dodging"):
            delta -= 1
        if self._has_tactical_tag(defender, "disengaged"):
            delta -= 1
        if self._has_tactical_tag(defender, "exposed"):
            delta += 1
        return int(delta)

    def _entity_grapple_mod(self, actor) -> int:
        if isinstance(actor, Character):
            scores = self._ability_scores(actor)
            return max(scores.strength_mod, scores.dexterity_mod)
        return max(0, int(int(getattr(actor, "attack_bonus", 0) or 0) // 2))

    def _resolve_contested_grapple(self, *, attacker, defender) -> bool:
        attacker_mod = self._entity_grapple_mod(attacker)
        defender_mod = self._entity_grapple_mod(defender)
        attacker_total = self._ability_check_roll(attacker, attacker_mod, requires_sight=False)
        defender_total = self._ability_check_roll(defender, defender_mod, requires_sight=False)
        return int(attacker_total) >= int(defender_total)

    def _apply_spell_status_effects(self, *, caster: Character, target, definition, log: List[CombatLogEntry]) -> None:
        damage_type = str(getattr(definition, "damage_type", "") or "").strip().lower()
        if int(getattr(target, "hp_current", 0) or 0) <= 0:
            return
        if damage_type == "fire" and self.rng.randint(1, 100) <= 35:
            self._apply_status(actor=target, status_id="burning", rounds=2, potency=1, log=log, source_name=getattr(caster, "name", "Spell"), source_actor=caster)
        elif damage_type == "healing":
            self._apply_status(actor=target, status_id="blessed", rounds=2, potency=1, log=log, source_name=getattr(caster, "name", "Spell"), source_actor=caster)
        elif damage_type == "psychic" and self.rng.randint(1, 100) <= 20:
            self._apply_status(actor=target, status_id="stunned", rounds=1, potency=1, log=log, source_name=getattr(caster, "name", "Spell"), source_actor=caster)
        elif damage_type in {"poison", "acid", "necrotic"} and self.rng.randint(1, 100) <= 30:
            self._apply_status(actor=target, status_id="poisoned", rounds=2, potency=1, log=log, source_name=getattr(caster, "name", "Spell"), source_actor=caster)

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
        target_actor=None,
        log: Optional[List[CombatLogEntry]] = None,
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

            for effect in tuple(outcome.condition_effects or ()):
                if not isinstance(effect, ConditionEffect):
                    continue
                target_key = str(getattr(effect, "target", "target") or "target").strip().lower()
                actor = player if target_key == "self" else target_actor
                if actor is None:
                    continue
                self._apply_status(
                    actor=actor,
                    status_id=str(getattr(effect, "status_id", "") or ""),
                    rounds=max(1, int(getattr(effect, "rounds", 1) or 1)),
                    potency=max(1, int(getattr(effect, "potency", 1) or 1)),
                    log=log if log is not None else [],
                    source_name=str(feature.name or feature.slug or "Feature"),
                    source_actor=player,
                )

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

    def _select_enemy_tactical_action(
        self,
        *,
        intent: str,
        actor,
        target,
        terrain: str,
        distance: str,
        default_action: str,
    ) -> str:
        base = str(default_action or "attack").strip().lower()
        if base not in {"attack", "reckless"}:
            return base

        intent_key = str(intent or "").strip().lower()
        roll = self.rng.randint(1, 100)
        is_melee_actor = self._is_melee_actor(actor)
        engaged = self._is_melee_range(distance)
        can_hide = self._terrain_supports_hiding(terrain=str(terrain), distance=str(distance))
        hp_max = max(1, int(getattr(actor, "hp_max", getattr(actor, "hp", 1)) or 1))
        hp_now = int(getattr(actor, "hp_current", hp_max) or hp_max)
        hp_ratio = float(hp_now) / float(hp_max)
        threatened = engaged and not self._movement_blocked(actor)

        if threatened and not is_melee_actor:
            return "disengage"

        if threatened and hp_ratio <= 0.45 and intent_key in {"cautious", "skirmisher", "ambusher"} and roll <= 50:
            return "disengage"

        if intent_key == "ambusher" and can_hide and not self._has_tactical_tag(actor, "hidden_strike") and roll <= 45:
            return "hide"

        if is_melee_actor and engaged:
            if intent_key in {"brute", "aggressive"} and not self._has_status(target, "grappled") and roll <= 35:
                return "grapple"
            if intent_key in {"cautious", "skirmisher"} and not self._has_status(target, "prone") and roll <= 30:
                return "shove"

        if intent_key in {"cautious", "skirmisher"} and can_hide and not engaged and roll <= 30:
            return "hide"

        return base

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
        player.flags = copy.deepcopy(getattr(player, "flags", {}) or {})
        player.inventory = list(getattr(player, "inventory", []) or [])
        player.attributes = dict(getattr(player, "attributes", {}) or {})
        player.race_traits = list(getattr(player, "race_traits", []) or [])
        player.background_features = list(getattr(player, "background_features", []) or [])
        player.proficiencies = list(getattr(player, "proficiencies", []) or [])
        player.cantrips = list(getattr(player, "cantrips", []) or [])
        player.known_spells = list(getattr(player, "known_spells", []) or [])
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
        whetstone_bonus = 0
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
            target_actor=foe,
            log=log,
        )
        initiative_player = _roll_initiative(surprise == "player", scores.initiative + initiative_bonus)
        initiative_enemy = _roll_initiative(surprise == "enemy", getattr(foe, "attack_bonus", 0))
        player_has_opening = initiative_player >= initiative_enemy
        self._log(log, f"Initiative: You {initiative_player} vs {foe.name} {initiative_enemy}.", level="normal")
        turn_order = ["player", "enemy"] if initiative_player >= initiative_enemy else ["enemy", "player"]

        round_no = 1
        fled = False
        distance = self._normalize_range_band((scene or {}).get("distance", "engaged"))
        terrain = (scene or {}).get("terrain", "open")
        weather = str((scene or {}).get("weather", "") or "")
        flavour_tracker: dict[str, bool] = {}
        while player_hp > 0 and foe.hp_current > 0:
            if player.class_name == "rogue":
                sneak_available = True
            self._log(log, f"-- Round {round_no} --", level="debug")
            self._apply_round_lair_action(
                log=log,
                round_no=round_no,
                terrain=str(terrain),
                allies=[player],
                enemies=[foe],
                scene=scene if isinstance(scene, dict) else None,
            )
            player_hp = int(getattr(player, "hp_current", player_hp) or player_hp)
            if int(getattr(foe, "hp_current", 0) or 0) <= 0:
                break
            if player_hp <= 0:
                break
            intent = self._intent_for_enemy(foe)
            round_flavour_used = False
            for actor in turn_order:
                if actor == "player":
                    player.hp_current = int(player_hp)
                    self._apply_start_turn_statuses(player, log)
                    player_hp = int(getattr(player, "hp_current", player_hp) or player_hp)
                    if player_hp <= 0:
                        break
                    if self._has_status(player, "stunned"):
                        self._log(log, f"{player.name} is stunned and loses the turn.", level="compact")
                        self._tick_actor_statuses_end_turn(player, log)
                        self._tick_actor_tactical_tags_end_turn(player)
                        continue
                    if self._turn_blocked(player):
                        self._log(log, f"{player.name} is incapacitated and loses the turn.", level="compact")
                        self._tick_actor_statuses_end_turn(player, log)
                        self._tick_actor_tactical_tags_end_turn(player)
                        continue
                    advantage_state = "advantage" if player_has_opening and round_no == 1 else None
                    advantage_state = self._combine_advantage(
                        advantage_state,
                        self._condition_advantage_delta(player, foe, distance=str(distance)),
                    )
                    options = [
                        "Attack",
                        "Dash",
                        "Disengage",
                        "Dodge",
                        "Hide",
                        "Help",
                        "Grapple",
                        "Shove",
                        "Use Item",
                        "Flee",
                    ]
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
                        if not self._is_attack_viable_for_range(is_melee_attack=self._is_melee_actor(player), distance=distance):
                            self._log(log, f"Target is out of melee range ({self._range_label(distance)}). Dash to close distance.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        if self._has_status_from_source(player, "charmed", foe):
                            self._log(log, f"{player.name} cannot attack {foe.name} while charmed.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        sneak_die = "d6" if sneak_available else None
                        _, roll_attack_bonus, _ = self._resolve_feature_trigger(
                            features=features,
                            trigger_key="on_attack_roll",
                            player=player,
                            enemy=foe,
                            round_number=round_no,
                            target_actor=foe,
                            log=log,
                        )
                        weather_shift = self._weather_attack_shift(weather=weather, attacker=player, action="attack")
                        weather_advantage = self._weather_attack_advantage(weather=weather, attacker=player, action="attack")
                        if weather_shift:
                            self._log(log, f"Weather pressure ({weather}) applies {weather_shift} to your strike.", level="compact")
                        if weather_advantage == "disadvantage":
                            self._log(log, f"Weather pressure ({weather}) imposes disadvantage on your ranged attack.", level="compact")
                        attack_advantage_state = self._combine_advantage(
                            advantage_state,
                            -1 if weather_advantage == "disadvantage" else 0,
                        )
                        attack_advantage_state = self._combine_advantage(
                            attack_advantage_state,
                            self._tactical_advantage_delta(attacker=player, defender=foe),
                        )
                        hit, is_crit, _, _ = self._attack_roll(
                            roll_attack_bonus + self._status_attack_roll_shift(player) + int(weather_shift),
                            prof,
                            attack_mod,
                            foe.armour_class,
                            attack_advantage_state,
                            log,
                            player.name,
                            foe.name,
                        )
                        if hit:
                            if self._has_status(foe, "paralysed") and self._is_melee_range(distance):
                                is_crit = True
                            if self._has_status(foe, "unconscious") and self._is_melee_range(distance):
                                is_crit = True
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
                                target_actor=foe,
                                log=log,
                            )
                            dmg += hit_bonus_damage
                            dmg += whetstone_bonus
                            dmg = self._modify_incoming_damage(foe, dmg)
                            foe.hp_current = max(0, foe.hp_current - dmg)
                            self._log(log, f"You deal {dmg} damage to {foe.name} ({foe.hp_current}/{foe.hp_max}).", level="compact")
                            sneak_available = False
                            self._consume_tactical_tag(player, "hidden_strike")
                            self._consume_tactical_tag(player, "helped")
                            self._consume_tactical_tag(foe, "exposed")
                            if foe.hp_current <= 0:
                                break
                        else:
                            self._log(log, "Your strike fails to connect.", level="compact")
                            self._consume_tactical_tag(player, "hidden_strike")
                            self._consume_tactical_tag(player, "helped")
                            self._consume_tactical_tag(foe, "exposed")
                        self._add_mechanical_flavour(
                            log,
                            actor="player",
                            action="attack",
                            enemy=foe,
                            terrain=terrain,
                            round_no=round_no,
                        )

                    elif action == "Cast Spell":
                        if not self._is_attack_viable_for_range(is_melee_attack=False, distance=distance):
                            self._log(log, f"Target is out of spell range ({self._range_label(distance)}).", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        if self._has_status_from_source(player, "charmed", foe):
                            self._log(log, f"{player.name} cannot target {foe.name} with harmful magic while charmed.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        weather_shift = self._weather_attack_shift(weather=weather, attacker=player, action="cast_spell")
                        weather_advantage = self._weather_attack_advantage(weather=weather, attacker=player, action="cast_spell")
                        if weather_shift:
                            self._log(log, f"Weather pressure ({weather}) disrupts casting aim ({weather_shift} to hit).", level="compact")
                        if weather_advantage == "disadvantage":
                            self._log(log, f"Weather pressure ({weather}) imposes disadvantage on ranged spell attacks.", level="compact")
                        player.flags["combat_weather_shift"] = int(weather_shift)
                        player.flags["combat_weather_advantage"] = str(weather_advantage or "")
                        self._resolve_spell_cast(player, foe, action_payload, mental_mod, prof, log)
                        player.flags.pop("combat_weather_shift", None)
                        player.flags.pop("combat_weather_advantage", None)
                        player_hp = int(getattr(player, "hp_current", player_hp) or player_hp)
                        self._add_mechanical_flavour(
                            log,
                            actor="player",
                            action="cast_spell",
                            enemy=foe,
                            terrain=terrain,
                            round_no=round_no,
                        )
                        if foe.hp_current <= 0:
                            break

                    elif action == "Dodge":
                        player_dodge = True
                        player.flags["dodging"] = 1
                        self._add_tactical_tag(player, tag="dodging", rounds=2)
                        self._log(log, "You focus on defense; incoming attacks have disadvantage.", level="compact")

                    elif action == "Disengage":
                        if self._movement_blocked(player):
                            self._log(log, "You cannot disengage while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        self._add_tactical_tag(player, tag="disengaged", rounds=2)
                        if self._is_dense_cover_terrain(str(terrain)):
                            self._add_tactical_tag(player, tag="cover", rounds=2)
                            self._log(log, "You disengage into cover.", level="compact")
                        else:
                            self._log(log, "You disengage and deny a clean strike.", level="compact")

                    elif action == "Hide":
                        if self._movement_blocked(player):
                            self._log(log, "You cannot hide while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        if not self._terrain_supports_hiding(terrain=str(terrain), distance=str(distance)):
                            self._log(log, "There is nowhere to hide here.", level="compact")
                        else:
                            stealth_total = self._ability_check_roll(player, scores.dexterity_mod, requires_sight=False)
                            if stealth_total >= 12:
                                self._add_tactical_tag(player, tag="concealed", rounds=2)
                                self._add_tactical_tag(player, tag="hidden_strike", rounds=2)
                                self._log(log, "You slip from sight and line up a hidden strike.", level="compact")
                            else:
                                self._add_tactical_tag(player, tag="exposed", rounds=1)
                                self._log(log, "You fail to hide and reveal your position.", level="compact")

                    elif action == "Help":
                        self._add_tactical_tag(player, tag="helped", rounds=2)
                        self._log(log, "You feint and read the foe, preparing your next strike.", level="compact")

                    elif action == "Grapple":
                        if not self._is_melee_range(distance):
                            self._log(log, f"You must be engaged to grapple ({self._range_label(distance)}).", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        if self._resolve_contested_grapple(attacker=player, defender=foe):
                            self._apply_status(
                                actor=foe,
                                status_id="grappled",
                                rounds=2,
                                potency=1,
                                log=log,
                                source_name=player.name,
                                source_actor=player,
                            )
                            self._add_tactical_tag(foe, tag="exposed", rounds=2)
                            self._log(log, f"You grapple {foe.name} and control their movement.", level="compact")
                        else:
                            self._log(log, f"{foe.name} slips free of your grapple attempt.", level="compact")

                    elif action == "Shove":
                        if not self._is_melee_range(distance):
                            self._log(log, f"You must be engaged to shove ({self._range_label(distance)}).", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        if self._resolve_contested_grapple(attacker=player, defender=foe):
                            if not self._has_status(foe, "prone"):
                                self._apply_status(
                                    actor=foe,
                                    status_id="prone",
                                    rounds=1,
                                    potency=1,
                                    log=log,
                                    source_name=player.name,
                                    source_actor=player,
                                )
                                self._log(log, f"You shove {foe.name} to the ground.", level="compact")
                            else:
                                distance = "near" if self._normalize_range_band(distance) == "engaged" else "far"
                                self._log(log, f"You drive {foe.name} back to {self._range_label(distance)}.", level="compact")
                        else:
                            self._log(log, f"{foe.name} resists your shove.", level="compact")

                    elif action == "Use Item":
                        player_hp, whetstone_bonus = self._resolve_use_item(
                            player,
                            player_hp,
                            log,
                            preferred_item=action_payload,
                            whetstone_bonus=whetstone_bonus,
                        )
                        player.hp_current = int(player_hp)

                    elif action == "Dash":
                        if self._has_status_from_source(player, "frightened", foe):
                            self._log(log, "Fear holds you in place; you cannot move closer to the source.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        if self._movement_blocked(player):
                            self._log(log, "You cannot dash while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        distance = self._step_toward_engagement(distance)
                        self._log(log, f"You dash forward. Distance is now {self._range_label(distance)}.", level="compact")

                    elif action == "Flee":
                        if self._movement_blocked(player):
                            self._log(log, "You cannot flee while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(player, log)
                            self._tick_actor_tactical_tags_end_turn(player)
                            continue
                        flee_roll = self._ability_check_roll(player, attack_mod, requires_sight=False)
                        if flee_roll >= 12:
                            self._log(log, "You slip away from the fight!", level="compact")
                            fled = True
                            player.flags.pop("dodging", None)
                            player.flags.pop("temp_ac_bonus", None)
                            player.flags.pop("shield_rounds", None)
                            player.flags.pop("combat_statuses", None)
                            player.flags.pop("combat_tactical_tags", None)
                            if "rage_rounds" in player.flags:
                                player.flags["rage_rounds"] = 0
                            self._clear_actor_tactical_tags(foe)
                            player.hp_current = player_hp
                            player.alive = player_hp > 0
                            return CombatResult(player, foe, log, player_won=False, fled=True)
                        else:
                            self._log(log, "You fail to escape.", level="compact")

                    self._tick_actor_statuses_end_turn(player, log)
                    self._tick_actor_tactical_tags_end_turn(player)

                else:  # enemy turn
                    self._apply_start_turn_statuses(foe, log)
                    if int(getattr(foe, "hp_current", 0) or 0) <= 0:
                        break
                    if self._has_status(foe, "stunned"):
                        self._log(log, f"{foe.name} is stunned and loses the turn.", level="compact")
                        self._tick_actor_statuses_end_turn(foe, log)
                        self._tick_actor_tactical_tags_end_turn(foe)
                        continue
                    if self._turn_blocked(foe):
                        self._log(log, f"{foe.name} is incapacitated and loses the turn.", level="compact")
                        self._tick_actor_statuses_end_turn(foe, log)
                        self._tick_actor_tactical_tags_end_turn(foe)
                        continue
                    if not round_flavour_used:
                        self._add_flavour(log, flavour_tracker, f"intent_{round_no}", self._intent_flavour(intent))
                        round_flavour_used = True
                    enemy_action, enemy_advantage = self._select_enemy_action(intent, foe, round_no, terrain)
                    enemy_action = self._select_enemy_tactical_action(
                        intent=intent,
                        actor=foe,
                        target=player,
                        terrain=str(terrain),
                        distance=str(distance),
                        default_action=str(enemy_action),
                    )
                    if enemy_action == "flee":
                        self._log(log, f"{foe.name} tries to flee the battle!", level="compact")
                        foe.hp_current = 0
                        break

                    enemy_is_melee = self._is_melee_actor(foe)
                    if enemy_is_melee and not self._is_attack_viable_for_range(is_melee_attack=True, distance=distance):
                        next_band = self._step_toward_engagement(distance)
                        if next_band != distance:
                            distance = next_band
                            self._log(log, f"{foe.name} closes in. Distance is now {self._range_label(distance)}.", level="compact")
                        continue
                    if (not enemy_is_melee) and self._normalize_range_band(distance) == "engaged" and enemy_action == "attack":
                        enemy_advantage = "disadvantage"

                    if enemy_action == "disengage":
                        if not self._movement_blocked(foe):
                            if self._normalize_range_band(distance) == "engaged":
                                distance = "near"
                            elif self._normalize_range_band(distance) == "near":
                                distance = "far"
                            self._add_tactical_tag(foe, tag="disengaged", rounds=2)
                            if self._is_dense_cover_terrain(str(terrain)):
                                self._add_tactical_tag(foe, tag="cover", rounds=2)
                            self._log(log, f"{foe.name} disengages to {self._range_label(distance)} and resets footing.", level="compact")
                        else:
                            self._log(log, f"{foe.name} tries to disengage but cannot move.", level="compact")
                        self._tick_actor_statuses_end_turn(foe, log)
                        self._tick_actor_tactical_tags_end_turn(foe)
                        continue

                    if enemy_action == "hide":
                        if self._terrain_supports_hiding(terrain=str(terrain), distance=str(distance)):
                            self._add_tactical_tag(foe, tag="concealed", rounds=2)
                            self._add_tactical_tag(foe, tag="hidden_strike", rounds=2)
                            self._log(log, f"{foe.name} slips into concealment.", level="compact")
                        else:
                            self._log(log, f"{foe.name} searches for cover but stays exposed.", level="compact")
                        self._tick_actor_statuses_end_turn(foe, log)
                        self._tick_actor_tactical_tags_end_turn(foe)
                        continue

                    if enemy_action == "grapple":
                        if self._resolve_contested_grapple(attacker=foe, defender=player):
                            self._apply_status(
                                actor=player,
                                status_id="grappled",
                                rounds=2,
                                potency=1,
                                log=log,
                                source_name=foe.name,
                                source_actor=foe,
                            )
                            self._add_tactical_tag(player, tag="exposed", rounds=2)
                            self._log(log, f"{foe.name} grapples you and locks your movement.", level="compact")
                        else:
                            self._log(log, f"{foe.name} lunges to grapple, but you slip free.", level="compact")
                        self._tick_actor_statuses_end_turn(foe, log)
                        self._tick_actor_tactical_tags_end_turn(foe)
                        continue

                    if enemy_action == "shove":
                        if self._resolve_contested_grapple(attacker=foe, defender=player):
                            if not self._has_status(player, "prone"):
                                self._apply_status(
                                    actor=player,
                                    status_id="prone",
                                    rounds=1,
                                    potency=1,
                                    log=log,
                                    source_name=foe.name,
                                    source_actor=foe,
                                )
                                self._log(log, f"{foe.name} shoves you to the ground.", level="compact")
                            else:
                                distance = "near" if self._normalize_range_band(distance) == "engaged" else "far"
                                self._log(log, f"{foe.name} drives you back to {self._range_label(distance)}.", level="compact")
                        else:
                            self._log(log, f"{foe.name} tries to shove you, but you hold your footing.", level="compact")
                        self._tick_actor_statuses_end_turn(foe, log)
                        self._tick_actor_tactical_tags_end_turn(foe)
                        continue

                    target_ac = player.armour_class
                    if enemy_action == "reckless":
                        enemy_advantage = "advantage"
                        foe_armour_class = getattr(foe, "armour_class", 10) - 2
                        foe.armour_class = max(8, foe_armour_class)
                        self._log(log, f"{foe.name} fights recklessly, leaving openings.", level="compact")

                    advantage_state = "disadvantage" if player_dodge else enemy_advantage
                    advantage_state = self._combine_advantage(
                        advantage_state,
                        self._condition_advantage_delta(foe, player, distance=str(distance)),
                    )
                    advantage_state = self._combine_advantage(
                        advantage_state,
                        self._tactical_advantage_delta(attacker=foe, defender=player),
                    )
                    weather_shift = self._weather_attack_shift(weather=weather, attacker=foe, action=enemy_action)
                    weather_advantage = self._weather_attack_advantage(weather=weather, attacker=foe, action=enemy_action)
                    attack_advantage_state = self._combine_advantage(
                        advantage_state,
                        -1 if weather_advantage == "disadvantage" else 0,
                    )
                    hit, is_crit, _, _ = self._attack_roll(
                        int(getattr(foe, "attack_bonus", 0) or 0) + self._status_attack_roll_shift(foe) + int(weather_shift),
                        0,
                        0,
                        target_ac,
                        attack_advantage_state,
                        log,
                        foe.name,
                        player.name,
                    )
                    if hit:
                        if self._has_status(player, "paralysed") and self._is_melee_range(distance):
                            is_crit = True
                        if self._has_status(player, "unconscious") and self._is_melee_range(distance):
                            is_crit = True
                        dmg = self._deal_damage(
                            foe.damage_die,
                            0,
                            is_crit,
                            None,
                            0,
                        )
                        dmg = self._modify_incoming_damage(player, dmg)
                        player_hp = max(0, player_hp - dmg)
                        self._log(log, f"{foe.name} hits you for {dmg} damage ({player_hp}/{player.hp_max}).", level="compact")
                        self._consume_tactical_tag(foe, "hidden_strike")
                        self._consume_tactical_tag(foe, "helped")
                        self._consume_tactical_tag(player, "exposed")
                    else:
                        self._log(log, f"{foe.name} misses you.", level="compact")
                        self._consume_tactical_tag(foe, "hidden_strike")
                        self._consume_tactical_tag(foe, "helped")
                        self._consume_tactical_tag(player, "exposed")
                    self._add_mechanical_flavour(
                        log,
                        actor="enemy",
                        action=enemy_action,
                        enemy=foe,
                        terrain=terrain,
                        round_no=round_no,
                    )
                    self._tick_actor_statuses_end_turn(foe, log)
                    self._tick_actor_tactical_tags_end_turn(foe)

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
                player.flags.pop("dodging", None)
                player.flags.pop("temp_ac_bonus", None)
                player.flags.pop("shield_rounds", None)
                player.flags.pop("combat_statuses", None)
                player.flags.pop("combat_tactical_tags", None)
                if "rage_rounds" in player.flags:
                    player.flags["rage_rounds"] = 0
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
        player.flags.pop("dodging", None)
        player.flags.pop("temp_ac_bonus", None)
        player.flags.pop("shield_rounds", None)
        player.flags.pop("combat_statuses", None)
        player.flags.pop("combat_tactical_tags", None)
        if "rage_rounds" in player.flags:
            player.flags["rage_rounds"] = 0
        self._clear_actor_tactical_tags(foe)

        if foe.hp_current <= 0:
            xp_gain = max(getattr(foe, "level", 1) * 5, 1)
            player.xp += xp_gain
            self._log(log, f"{foe.name} falls. +{xp_gain} XP.", level="compact")

        return CombatResult(player, foe, log, player_won=player_hp > 0 and foe.hp_current <= 0)

    def fight_party_turn_based(
        self,
        allies: List[Character],
        enemies: List[Entity],
        choose_action: Callable[[List[str], Character, Entity, int, dict], tuple[str, Optional[str]] | str],
        scene: Optional[dict] = None,
        choose_target: Optional[PartyTargetSelector] = None,
        evaluate_ai_action: Optional[Callable[[object, List[object], List[object], int, dict], tuple[str, Optional[str]] | str]] = None,
    ) -> PartyCombatResult:
        log: List[CombatLogEntry] = []
        active_allies: list[Character] = []
        active_enemies: list[Entity] = []

        for ally in allies:
            row = replace(ally)
            row.flags = copy.deepcopy(getattr(ally, "flags", {}) or {})
            row.inventory = list(getattr(ally, "inventory", []) or [])
            row.attributes = dict(getattr(ally, "attributes", {}) or {})
            row.race_traits = list(getattr(ally, "race_traits", []) or [])
            row.background_features = list(getattr(ally, "background_features", []) or [])
            row.proficiencies = list(getattr(ally, "proficiencies", []) or [])
            row.cantrips = list(getattr(ally, "cantrips", []) or [])
            row.known_spells = list(getattr(ally, "known_spells", []) or [])
            row.hp_max = int(getattr(row, "hp_max", getattr(row, "hp_current", 1)) or 1)
            row.hp_current = int(getattr(row, "hp_current", row.hp_max) or row.hp_max)
            active_allies.append(row)

        for enemy in enemies:
            row = replace(enemy)
            row.hp_max = int(getattr(row, "hp_max", getattr(row, "hp", 1)) or 1)
            row.hp_current = int(getattr(row, "hp_current", row.hp_max) or row.hp_max)
            active_enemies.append(row)

        if not active_allies or not active_enemies:
            return PartyCombatResult(
                allies=active_allies,
                enemies=active_enemies,
                log=log,
                allies_won=bool(active_allies) and not bool(active_enemies),
                fled=False,
            )

        terrain = str((scene or {}).get("terrain", "open"))
        distance = self._normalize_range_band(str((scene or {}).get("distance", "engaged")))
        weather = str((scene or {}).get("weather", "") or "")
        surprise = (scene or {}).get("surprise")
        player_actor_id = int(getattr(active_allies[0], "id", 0) or 0)

        def _initiative_for_ally(actor: Character) -> int:
            scores = self._ability_scores(actor)
            roll = self.rng.randint(1, 20)
            if surprise == "player":
                roll = max(roll, self.rng.randint(1, 20))
            total = int(roll + scores.initiative)
            if self._is_swamp_terrain(terrain) and self._is_heavy_armor_user(actor):
                total -= 100
            return total

        def _initiative_for_enemy(actor: Entity) -> int:
            roll = self.rng.randint(1, 20)
            if surprise == "enemy":
                roll = max(roll, self.rng.randint(1, 20))
            return int(roll + int(getattr(actor, "attack_bonus", 0) or 0))

        initiative_rows: list[dict] = []
        for ally in active_allies:
            initiative_rows.append({"side": "ally", "actor": ally, "initiative": _initiative_for_ally(ally)})
        for enemy in active_enemies:
            initiative_rows.append({"side": "enemy", "actor": enemy, "initiative": _initiative_for_enemy(enemy)})

        initiative_rows.sort(
            key=lambda row: (
                int(row["initiative"]),
                1 if str(row["side"]) == "ally" else 0,
                str(getattr(row["actor"], "name", "")).lower(),
            ),
            reverse=True,
        )
        ordered = [f"{getattr(row['actor'], 'name', '?')}:{int(row['initiative'])}" for row in initiative_rows]
        self._log(log, f"Initiative queue: {', '.join(ordered)}.", level="normal")

        round_no = 1
        fled = False
        while any(a.hp_current > 0 for a in active_allies) and any(e.hp_current > 0 for e in active_enemies):
            if round_no > 50:
                break
            self._log(log, f"-- Round {round_no} --", level="debug")
            self._apply_round_lair_action(
                log=log,
                round_no=round_no,
                terrain=terrain,
                allies=active_allies,
                enemies=active_enemies,
                scene=scene if isinstance(scene, dict) else None,
            )
            round_engagements: dict[int, set[int]] = {}

            for row in initiative_rows:
                side = str(row["side"])
                actor = row["actor"]
                if int(getattr(actor, "hp_current", 0) or 0) <= 0:
                    continue

                living_allies = [a for a in active_allies if int(getattr(a, "hp_current", 0) or 0) > 0]
                living_enemies = [e for e in active_enemies if int(getattr(e, "hp_current", 0) or 0) > 0]
                if not living_allies or not living_enemies:
                    break

                if side == "ally":
                    actor_character = actor
                    self._apply_start_turn_statuses(actor_character, log)
                    if int(getattr(actor_character, "hp_current", 0) or 0) <= 0:
                        continue
                    if self._has_status(actor_character, "stunned"):
                        self._log(log, f"{actor_character.name} is stunned and loses the turn.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue
                    if self._turn_blocked(actor_character):
                        self._log(log, f"{actor_character.name} is incapacitated and loses the turn.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue
                    is_player_actor = int(getattr(actor_character, "id", 0) or 0) == player_actor_id
                    if is_player_actor:
                        preview_targets = self._combat_target_pool(attacker=actor_character, opponents=living_enemies, action="Attack")
                        target = preview_targets[0] if preview_targets else living_enemies[0]
                        options = [
                            "Attack",
                            "Dash",
                            "Disengage",
                            "Dodge",
                            "Hide",
                            "Help",
                            "Grapple",
                            "Shove",
                            "Use Item",
                            "Flee",
                        ]
                        has_magic = (getattr(actor_character, "spell_slots_current", 0) > 0) or bool(getattr(actor_character, "cantrips", []))
                        if has_magic:
                            options.insert(1, "Cast Spell")
                        choice = choose_action(options, actor_character, target, round_no, {"distance": distance, "terrain": terrain, "surprise": surprise})
                    else:
                        if callable(evaluate_ai_action):
                            choice = evaluate_ai_action(actor_character, living_allies, living_enemies, round_no, {"distance": distance, "terrain": terrain, "surprise": surprise})
                        else:
                            choice = self._evaluate_ai_action(actor_character, living_allies, living_enemies, round_no, {"distance": distance, "terrain": terrain, "surprise": surprise})
                        target = living_enemies[0]

                    action_payload = None
                    action = choice
                    if isinstance(choice, tuple):
                        action, action_payload = choice

                    spell_slug = str(action_payload or "").strip().lower() if str(action) == "Cast Spell" else ""
                    should_target_allies = bool(spell_slug and self._is_healing_spell(spell_slug))
                    if should_target_allies:
                        target_candidates = list(living_allies)
                    else:
                        target_candidates = self._combat_target_pool(
                            attacker=actor_character,
                            opponents=living_enemies,
                            action=str(action),
                        )
                    if not target_candidates:
                        target_candidates = living_allies if should_target_allies else living_enemies
                    target_index = self._select_party_target_index(
                        actor=actor_character,
                        target_candidates=target_candidates,
                        allies=living_allies,
                        enemies=living_enemies,
                        round_no=round_no,
                        scene_ctx={"distance": distance, "terrain": terrain, "surprise": surprise},
                        action=str(action),
                        choose_target=choose_target,
                        should_target_allies=should_target_allies,
                        is_player_actor=is_player_actor,
                    )
                    target = target_candidates[target_index]

                    if str(action) == "Flee":
                        if self._movement_blocked(actor_character):
                            self._log(log, f"{actor_character.name} cannot flee while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        flee_scores = self._ability_scores(actor_character)
                        flee_roll = self._ability_check_roll(actor_character, int(flee_scores.initiative), requires_sight=False)
                        if flee_roll >= 12:
                            fled = True
                            self._log(log, f"{actor_character.name} orders a retreat and escapes.", level="compact")
                            break
                        self._log(log, f"{actor_character.name} fails to disengage.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Cast Spell":
                        if not self._is_attack_viable_for_range(is_melee_attack=False, distance=distance):
                            self._log(log, f"{actor_character.name} cannot cast at {self._range_label(distance)} range.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        derived = self.derive_player_stats(actor_character)
                        weather_spell_advantage = self._weather_attack_advantage(
                            weather=weather,
                            attacker=actor_character,
                            action="cast_spell",
                        )
                        self._resolve_spell_cast_party(
                            caster=actor_character,
                            target=target,
                            spell_slug=action_payload,
                            spell_mod=int(derived.get("spell_mod", 0)),
                            prof=int(derived.get("proficiency", 2)),
                            attack_roll_shift=self._terrain_ranged_attack_shift(
                                terrain=terrain,
                                attacker=actor_character,
                                action="cast_spell",
                            ) + self._weather_attack_shift(weather=weather, attacker=actor_character, action="cast_spell"),
                            attack_advantage=weather_spell_advantage,
                            log=log,
                        )
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Use Item":
                        hp_after, _ = self._resolve_use_item(actor_character, int(getattr(actor_character, "hp_current", 1) or 1), log, preferred_item=action_payload, whetstone_bonus=0)
                        actor_character.hp_current = hp_after
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Dash":
                        if self._has_status_from_source(actor_character, "frightened", target):
                            self._log(log, f"{actor_character.name} cannot move closer while frightened.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        if self._movement_blocked(actor_character):
                            self._log(log, f"{actor_character.name} cannot reposition while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        if self._is_treacherous_ground(terrain):
                            dex_mod = self._ability_scores(actor_character).dexterity_mod
                            check_total = self._ability_check_roll(actor_character, dex_mod, requires_sight=True)
                            if check_total < 12:
                                self._log(log, f"{actor_character.name} slips on treacherous ground and loses momentum.", level="compact")
                                self._tick_actor_statuses_end_turn(actor_character, log)
                                self._tick_actor_tactical_tags_end_turn(actor_character)
                                continue
                        distance = self._step_toward_engagement(distance)
                        if self._is_treacherous_ground(terrain):
                            self._add_tactical_tag(actor_character, tag="high_ground", rounds=2)
                            self._log(log, f"{actor_character.name} secures high ground.", level="compact")
                        self._log(log, f"{actor_character.name} repositions to {self._range_label(distance)}.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Disengage":
                        if self._movement_blocked(actor_character):
                            self._log(log, f"{actor_character.name} cannot disengage while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        self._add_tactical_tag(actor_character, tag="disengaged", rounds=2)
                        if self._is_dense_cover_terrain(terrain):
                            self._add_tactical_tag(actor_character, tag="cover", rounds=2)
                            self._log(log, f"{actor_character.name} disengages into cover.", level="compact")
                        else:
                            self._log(log, f"{actor_character.name} disengages safely.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Hide":
                        if self._movement_blocked(actor_character):
                            self._log(log, f"{actor_character.name} cannot hide while restrained or incapacitated.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        if not self._terrain_supports_hiding(terrain=terrain, distance=distance):
                            self._log(log, f"{actor_character.name} has nowhere to hide.", level="compact")
                        else:
                            dex_mod = self._ability_scores(actor_character).dexterity_mod
                            stealth_total = self._ability_check_roll(actor_character, dex_mod, requires_sight=False)
                            if stealth_total >= 12:
                                self._add_tactical_tag(actor_character, tag="concealed", rounds=2)
                                self._add_tactical_tag(actor_character, tag="hidden_strike", rounds=2)
                                self._log(log, f"{actor_character.name} vanishes into concealment.", level="compact")
                            else:
                                self._add_tactical_tag(actor_character, tag="exposed", rounds=1)
                                self._log(log, f"{actor_character.name} fails to hide and is exposed.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Help":
                        self._add_tactical_tag(target, tag="exposed", rounds=2)
                        self._log(log, f"{actor_character.name} distracts {target.name}, opening their guard.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Grapple":
                        if not self._is_melee_range(distance):
                            self._log(log, f"{actor_character.name} must be engaged to grapple.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        if self._resolve_contested_grapple(attacker=actor_character, defender=target):
                            self._apply_status(
                                actor=target,
                                status_id="grappled",
                                rounds=2,
                                potency=1,
                                log=log,
                                source_name=actor_character.name,
                                source_actor=actor_character,
                            )
                            self._add_tactical_tag(target, tag="exposed", rounds=2)
                            self._log(log, f"{actor_character.name} grapples {target.name}.", level="compact")
                        else:
                            self._log(log, f"{target.name} slips free of {actor_character.name}'s grapple.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Shove":
                        if not self._is_melee_range(distance):
                            self._log(log, f"{actor_character.name} must be engaged to shove.", level="compact")
                            self._tick_actor_statuses_end_turn(actor_character, log)
                            self._tick_actor_tactical_tags_end_turn(actor_character)
                            continue
                        if self._resolve_contested_grapple(attacker=actor_character, defender=target):
                            if not self._has_status(target, "prone"):
                                self._apply_status(
                                    actor=target,
                                    status_id="prone",
                                    rounds=1,
                                    potency=1,
                                    log=log,
                                    source_name=actor_character.name,
                                    source_actor=actor_character,
                                )
                                self._log(log, f"{actor_character.name} shoves {target.name} prone.", level="compact")
                            else:
                                distance = "near" if self._normalize_range_band(distance) == "engaged" else "far"
                                self._log(log, f"{actor_character.name} forces {target.name} back to {self._range_label(distance)}.", level="compact")
                        else:
                            self._log(log, f"{target.name} holds position against the shove.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    if str(action) == "Dodge":
                        if self._is_treacherous_ground(terrain):
                            dex_mod = self._ability_scores(actor_character).dexterity_mod
                            check_total = self._ability_check_roll(actor_character, dex_mod, requires_sight=True)
                            if check_total < 12:
                                self._log(log, f"{actor_character.name} stumbles while dodging and loses the turn.", level="compact")
                                self._tick_actor_statuses_end_turn(actor_character, log)
                                self._tick_actor_tactical_tags_end_turn(actor_character)
                                continue
                        self._add_tactical_tag(actor_character, tag="dodging", rounds=2)
                        self._log(log, f"{actor_character.name} braces defensively.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue

                    derived = self.derive_player_stats(actor_character)
                    if not self._is_attack_viable_for_range(
                        is_melee_attack=self._is_melee_actor(actor_character),
                        distance=distance,
                    ):
                        self._log(log, f"{actor_character.name} cannot make a melee attack at {self._range_label(distance)} range.", level="compact")
                        self._tick_actor_statuses_end_turn(actor_character, log)
                        self._tick_actor_tactical_tags_end_turn(actor_character)
                        continue
                    terrain_attack_shift = self._terrain_ranged_attack_shift(
                        terrain=terrain,
                        attacker=actor_character,
                        action="attack",
                    )
                    weather_attack_shift = self._weather_attack_shift(weather=weather, attacker=actor_character, action="attack")
                    weather_attack_advantage = self._weather_attack_advantage(weather=weather, attacker=actor_character, action="attack")
                    target_key = self._combat_actor_key(target)
                    actor_key = self._combat_actor_key(actor_character)
                    engaged = round_engagements.setdefault(target_key, set())
                    flank_active = any(existing != actor_key for existing in engaged)
                    engaged.add(actor_key)
                    if flank_active:
                        self._log(log, f"{actor_character.name} flanks {target.name}.", level="compact")
                    if terrain_attack_shift:
                        self._log(log, f"Dense cover disrupts line of sight ({terrain_attack_shift} to hit).", level="compact")
                    if weather_attack_shift:
                        self._log(log, f"Weather pressure ({weather}) applies {weather_attack_shift} to hit.", level="compact")
                    if weather_attack_advantage == "disadvantage":
                        self._log(log, f"Weather pressure ({weather}) imposes disadvantage on ranged attacks.", level="compact")
                    hit_advantage_state = self._combine_advantage(
                        self._combine_advantage(
                            self._combine_advantage(
                                "advantage" if flank_active else None,
                                self._condition_advantage_delta(actor_character, target, distance=str(distance)),
                            ),
                            -1 if weather_attack_advantage == "disadvantage" else 0,
                        ),
                        self._tactical_advantage_delta(attacker=actor_character, defender=target),
                    )
                    hit, is_crit, _, _ = self._attack_roll(
                        int(terrain_attack_shift) + int(weather_attack_shift) + self._status_attack_roll_shift(actor_character),
                        int(derived.get("proficiency", 2)),
                        int(derived.get("weapon_mod", 0)),
                        int(getattr(target, "armour_class", 10) or 10),
                        hit_advantage_state,
                        log,
                        str(getattr(actor_character, "name", "Ally")),
                        str(getattr(target, "name", "Enemy")),
                    )
                    if hit:
                        if self._has_status(target, "paralysed") and self._is_melee_range(distance):
                            is_crit = True
                        if self._has_status(target, "unconscious") and self._is_melee_range(distance):
                            is_crit = True
                        sneak_die = "d6" if flank_active and str(getattr(actor_character, "class_name", "")).lower() == "rogue" else None
                        dmg = self._deal_damage(
                            str(derived.get("damage_die", "d6")),
                            int(derived.get("damage_mod", 0)),
                            is_crit,
                            sneak_die,
                            0,
                        )
                        if flank_active:
                            dmg += 2
                        dmg = self._modify_incoming_damage(target, dmg)
                        target.hp_current = max(0, int(getattr(target, "hp_current", 0) or 0) - dmg)
                        self._log(log, f"{actor_character.name} hits {target.name} for {dmg} damage ({target.hp_current}/{target.hp_max}).", level="compact")
                    self._consume_tactical_tag(actor_character, "hidden_strike")
                    self._consume_tactical_tag(actor_character, "helped")
                    self._consume_tactical_tag(target, "exposed")
                    self._tick_actor_statuses_end_turn(actor_character, log)
                    self._tick_actor_tactical_tags_end_turn(actor_character)
                    continue

                enemy_actor = actor
                self._apply_start_turn_statuses(enemy_actor, log)
                if int(getattr(enemy_actor, "hp_current", 0) or 0) <= 0:
                    continue
                if self._has_status(enemy_actor, "stunned"):
                    self._log(log, f"{enemy_actor.name} is stunned and loses the turn.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue
                if self._turn_blocked(enemy_actor):
                    self._log(log, f"{enemy_actor.name} is incapacitated and loses the turn.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue
                targets = [a for a in active_allies if int(getattr(a, "hp_current", 0) or 0) > 0]
                if not targets:
                    break
                if callable(evaluate_ai_action):
                    enemy_choice = evaluate_ai_action(enemy_actor, living_enemies, living_allies, round_no, {"distance": distance, "terrain": terrain, "surprise": surprise})
                    enemy_action = enemy_choice[0] if isinstance(enemy_choice, tuple) else str(enemy_choice)
                else:
                    enemy_action = str(self._evaluate_ai_action(enemy_actor, living_enemies, living_allies, round_no, {"distance": distance, "terrain": terrain, "surprise": surprise}))
                target_pool = self._combat_target_pool(attacker=enemy_actor, opponents=targets, action=enemy_action)
                if not target_pool:
                    target_pool = targets
                target = self._lowest_hp_target(target_pool)
                enemy_action = self._select_enemy_tactical_action(
                    intent=self._intent_for_enemy(enemy_actor),
                    actor=enemy_actor,
                    target=target,
                    terrain=str(terrain),
                    distance=str(distance),
                    default_action=str(enemy_action),
                )
                if str(enemy_action).lower() == "flee":
                    enemy_actor.hp_current = 0
                    self._log(log, f"{enemy_actor.name} flees.", level="compact")
                    continue

                enemy_is_melee = self._is_melee_actor(enemy_actor)
                if enemy_is_melee and not self._is_attack_viable_for_range(is_melee_attack=True, distance=distance):
                    next_band = self._step_toward_engagement(distance)
                    if next_band != distance:
                        distance = next_band
                        self._log(log, f"{enemy_actor.name} advances to {self._range_label(distance)} range.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue

                if str(enemy_action).lower() == "disengage":
                    if not self._movement_blocked(enemy_actor):
                        if self._normalize_range_band(distance) == "engaged":
                            distance = "near"
                        elif self._normalize_range_band(distance) == "near":
                            distance = "far"
                        self._add_tactical_tag(enemy_actor, tag="disengaged", rounds=2)
                        if self._is_dense_cover_terrain(str(terrain)):
                            self._add_tactical_tag(enemy_actor, tag="cover", rounds=2)
                        self._log(log, f"{enemy_actor.name} disengages to {self._range_label(distance)} range.", level="compact")
                    else:
                        self._log(log, f"{enemy_actor.name} tries to disengage but cannot move.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue

                if str(enemy_action).lower() == "hide":
                    if self._terrain_supports_hiding(terrain=str(terrain), distance=str(distance)):
                        self._add_tactical_tag(enemy_actor, tag="concealed", rounds=2)
                        self._add_tactical_tag(enemy_actor, tag="hidden_strike", rounds=2)
                        self._log(log, f"{enemy_actor.name} melts into concealment.", level="compact")
                    else:
                        self._log(log, f"{enemy_actor.name} cannot find enough cover to hide.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue

                if str(enemy_action).lower() == "grapple":
                    if self._resolve_contested_grapple(attacker=enemy_actor, defender=target):
                        self._apply_status(
                            actor=target,
                            status_id="grappled",
                            rounds=2,
                            potency=1,
                            log=log,
                            source_name=str(getattr(enemy_actor, "name", "Enemy")),
                            source_actor=enemy_actor,
                        )
                        self._add_tactical_tag(target, tag="exposed", rounds=2)
                        self._log(log, f"{enemy_actor.name} grapples {target.name}.", level="compact")
                    else:
                        self._log(log, f"{enemy_actor.name} fails to secure a grapple on {target.name}.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue

                if str(enemy_action).lower() == "shove":
                    if self._resolve_contested_grapple(attacker=enemy_actor, defender=target):
                        if not self._has_status(target, "prone"):
                            self._apply_status(
                                actor=target,
                                status_id="prone",
                                rounds=1,
                                potency=1,
                                log=log,
                                source_name=str(getattr(enemy_actor, "name", "Enemy")),
                                source_actor=enemy_actor,
                            )
                            self._log(log, f"{enemy_actor.name} shoves {target.name} prone.", level="compact")
                        else:
                            distance = "near" if self._normalize_range_band(distance) == "engaged" else "far"
                            self._log(log, f"{enemy_actor.name} forces {target.name} back to {self._range_label(distance)}.", level="compact")
                    else:
                        self._log(log, f"{target.name} resists {enemy_actor.name}'s shove.", level="compact")
                    self._tick_actor_statuses_end_turn(enemy_actor, log)
                    self._tick_actor_tactical_tags_end_turn(enemy_actor)
                    continue

                target_ac = self._derive_ac(target)
                enemy_attack_shift = self._terrain_ranged_attack_shift(
                    terrain=terrain,
                    attacker=enemy_actor,
                    action=enemy_action,
                )
                weather_enemy_shift = self._weather_attack_shift(weather=weather, attacker=enemy_actor, action=enemy_action)
                weather_enemy_advantage = self._weather_attack_advantage(weather=weather, attacker=enemy_actor, action=enemy_action)
                hit, is_crit, _, _ = self._attack_roll(
                    int(getattr(enemy_actor, "attack_bonus", 0) or 0)
                    + int(enemy_attack_shift)
                    + int(weather_enemy_shift)
                    + self._status_attack_roll_shift(enemy_actor),
                    0,
                    0,
                    int(target_ac),
                    self._combine_advantage(
                        self._combine_advantage(
                            self._combine_advantage(
                                None,
                                self._condition_advantage_delta(enemy_actor, target, distance=str(distance)),
                            ),
                            -1 if weather_enemy_advantage == "disadvantage" else 0,
                        ),
                        self._tactical_advantage_delta(attacker=enemy_actor, defender=target),
                    ),
                    log,
                    str(getattr(enemy_actor, "name", "Enemy")),
                    str(getattr(target, "name", "Ally")),
                )
                if hit:
                    if self._has_status(target, "paralysed") and self._is_melee_range(distance):
                        is_crit = True
                    if self._has_status(target, "unconscious") and self._is_melee_range(distance):
                        is_crit = True
                    dmg = self._deal_damage(
                        str(getattr(enemy_actor, "damage_die", "d4") or "d4"),
                        0,
                        is_crit,
                        None,
                        0,
                    )
                    dmg = self._modify_incoming_damage(target, dmg)
                    target.hp_current = max(0, int(getattr(target, "hp_current", 0) or 0) - dmg)
                    self._log(log, f"{enemy_actor.name} hits {target.name} for {dmg} damage ({target.hp_current}/{target.hp_max}).", level="compact")
                else:
                    self._log(log, f"{enemy_actor.name} misses {target.name}.", level="compact")
                self._consume_tactical_tag(enemy_actor, "hidden_strike")
                self._consume_tactical_tag(enemy_actor, "helped")
                self._consume_tactical_tag(target, "exposed")
                self._tick_actor_statuses_end_turn(enemy_actor, log)
                self._tick_actor_tactical_tags_end_turn(enemy_actor)

            if fled:
                break
            round_no += 1

        allies_won = any(a.hp_current > 0 for a in active_allies) and not any(e.hp_current > 0 for e in active_enemies)
        if allies_won and active_allies:
            lead = active_allies[0]
            xp_gain = sum(max(1, int(getattr(enemy, "level", 1) or 1) * 5) for enemy in active_enemies if int(getattr(enemy, "hp_current", 0) or 0) <= 0)
            if xp_gain > 0:
                lead.xp = int(getattr(lead, "xp", 0) or 0) + int(xp_gain)
                self._log(log, f"Party victory. {lead.name} gains +{xp_gain} XP.", level="compact")
        for ally in active_allies:
            if isinstance(getattr(ally, "flags", None), dict):
                ally.flags.pop("combat_statuses", None)
                ally.flags.pop("combat_tactical_tags", None)
        for enemy in active_enemies:
            try:
                if hasattr(enemy, "_combat_statuses"):
                    delattr(enemy, "_combat_statuses")
                if hasattr(enemy, "_combat_tactical_tags"):
                    delattr(enemy, "_combat_tactical_tags")
            except Exception:
                pass
        return PartyCombatResult(
            allies=active_allies,
            enemies=active_enemies,
            log=log,
            allies_won=allies_won,
            fled=fled,
        )

    def _select_party_target_index(
        self,
        *,
        actor: Character,
        target_candidates: list,
        allies: list[Character],
        enemies: list[Entity],
        round_no: int,
        scene_ctx: dict,
        action: str,
        choose_target,
        should_target_allies: bool,
        is_player_actor: bool,
    ) -> int:
        if not target_candidates:
            return 0

        if callable(choose_target):
            if is_player_actor:
                try:
                    selected = choose_target(actor, allies, enemies, round_no, scene_ctx, action)
                except TypeError:
                    selected = choose_target(actor, target_candidates, round_no, scene_ctx)
            else:
                selected = None

            if isinstance(selected, tuple) and len(selected) == 2:
                side_key = str(selected[0] or "").strip().lower()
                idx = int(selected[1]) if isinstance(selected[1], int) else -1
                if side_key in {"ally", "allies"} and should_target_allies and 0 <= idx < len(allies):
                    chosen = allies[idx]
                    return target_candidates.index(chosen) if chosen in target_candidates else 0
                if side_key in {"enemy", "enemies"} and (not should_target_allies) and 0 <= idx < len(enemies):
                    chosen = enemies[idx]
                    return target_candidates.index(chosen) if chosen in target_candidates else 0

            if isinstance(selected, int) and 0 <= int(selected) < len(target_candidates):
                return int(selected)

        if should_target_allies:
            return int(target_candidates.index(self._lowest_hp_target(target_candidates)))
        if is_player_actor:
            return 0
        return int(target_candidates.index(self._lowest_hp_target(target_candidates)))

    def _combat_target_pool(self, *, attacker, opponents: list, action: str) -> list:
        if not opponents:
            return []
        normalized_action = str(action or "").strip().lower()
        if normalized_action != "attack":
            return list(opponents)
        if not self._is_melee_actor(attacker):
            return list(opponents)

        vanguard = [row for row in opponents if self._combat_lane(row) == "vanguard"]
        if vanguard:
            return vanguard
        return list(opponents)

    @staticmethod
    def _is_swamp_terrain(terrain: str) -> bool:
        normalized = str(terrain or "").strip().lower()
        return normalized in {"swamp", "wetland", "marsh", "bog"}

    @staticmethod
    def _is_treacherous_ground(terrain: str) -> bool:
        normalized = str(terrain or "").strip().lower()
        return normalized in {"mountain", "mountains", "volcano", "volcanic"}

    @staticmethod
    def _is_dense_cover_terrain(terrain: str) -> bool:
        normalized = str(terrain or "").strip().lower()
        return normalized in {"forest", "jungle", "woodland"}

    def _terrain_ranged_attack_shift(self, *, terrain: str, attacker, action: str) -> int:
        if not self._is_dense_cover_terrain(terrain):
            return 0
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"attack", "cast_spell"}:
            return 0
        if self._is_melee_actor(attacker):
            return 0
        return -2

    def _weather_attack_shift(self, *, weather: str, attacker, action: str) -> int:
        normalized_weather = str(weather or "").strip().lower()
        if not normalized_weather:
            return 0

        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"attack", "cast_spell", "reckless"}:
            return 0

        is_melee = self._is_melee_actor(attacker)
        if normalized_weather == "rain":
            return -1 if not is_melee else 0
        if normalized_weather in {"fog", "storm"}:
            return -2 if not is_melee else -1
        if normalized_weather == "blizzard":
            return -3 if not is_melee else -2
        return 0

    def _weather_attack_advantage(self, *, weather: str, attacker, action: str) -> Optional[str]:
        normalized_weather = str(weather or "").strip().lower()
        if normalized_weather not in {"rain", "storm", "blizzard"}:
            return None

        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"attack", "cast_spell", "reckless"}:
            return None

        if self._is_melee_actor(attacker):
            return None
        return "disadvantage"

    def _is_heavy_armor_user(self, actor: Character) -> bool:
        equipment = self._equipment_state(actor)
        armor = str(equipment.get("armor", "") or "").strip().lower()
        if not armor:
            inventory = [str(item or "").strip().lower() for item in list(getattr(actor, "inventory", []) or [])]
            armor = " ".join(inventory)
        return any(keyword in armor for keyword in ("chain mail", "plate", "splint", "heavy"))

    def _combat_lane(self, actor) -> str:
        if isinstance(actor, Character):
            flags = getattr(actor, "flags", None)
            if isinstance(flags, dict):
                forced = str(flags.get("combat_lane", "") or "").strip().lower()
                if forced in {"vanguard", "rearguard"}:
                    return forced
            class_slug = str(getattr(actor, "class_name", "") or "").strip().lower()
            if class_slug in self._BACKLINE_CLASSES:
                return "rearguard"
            return "vanguard"

        flags = getattr(actor, "tags", None)
        if isinstance(flags, list):
            normalized = {str(item or "").strip().lower() for item in flags}
            if "lane:rearguard" in normalized:
                return "rearguard"
            if "lane:vanguard" in normalized:
                return "vanguard"

        name_key = str(getattr(actor, "name", "") or "").strip().lower()
        if any(keyword in name_key for keyword in self._BACKLINE_NAME_KEYWORDS):
            return "rearguard"
        return "vanguard"

    def _is_melee_actor(self, actor) -> bool:
        if isinstance(actor, Character):
            return self._combat_lane(actor) == "vanguard"
        return self._combat_lane(actor) == "vanguard"

    @staticmethod
    def _lowest_hp_target(targets: list):
        return min(
            targets,
            key=lambda row: (
                int(getattr(row, "hp_current", 0) or 0),
                int(getattr(row, "hp_max", 0) or 0),
                str(getattr(row, "name", "")).lower(),
            ),
        )

    @staticmethod
    def _is_healing_spell(spell_slug: str) -> bool:
        definition = SPELL_DEFINITIONS.get(str(spell_slug or "").strip().lower())
        return bool(definition and str(getattr(definition, "damage_type", "")).lower() == "healing")

    def _evaluate_ai_action(self, actor, allies: list, enemies: list, round_no: int, scene_ctx: dict):
        _ = round_no
        _ = scene_ctx
        living_allies = [row for row in allies if int(getattr(row, "hp_current", 0) or 0) > 0]
        living_enemies = [row for row in enemies if int(getattr(row, "hp_current", 0) or 0) > 0]
        if not living_allies or not living_enemies:
            return "Attack"

        if not isinstance(actor, Character):
            hp_max = max(1, int(getattr(actor, "hp_max", getattr(actor, "hp_current", 1)) or 1))
            hp_now = int(getattr(actor, "hp_current", hp_max) or hp_max)
            if hp_now <= max(1, hp_max // 4) and len(living_enemies) < len(living_allies):
                return "flee"
            return "attack"

        is_character = isinstance(actor, Character)
        if is_character:
            known_spells = [str(name or "") for name in list(getattr(actor, "known_spells", []) or [])]
            healing_slug = next(
                (
                    _slugify_spell_name(name)
                    for name in known_spells
                    if self._is_healing_spell(_slugify_spell_name(name))
                ),
                None,
            )
            if healing_slug and int(getattr(actor, "spell_slots_current", 0) or 0) > 0:
                critical_ally = next(
                    (
                        row
                        for row in sorted(living_allies, key=lambda unit: int(getattr(unit, "hp_current", 0) or 0))
                        if int(getattr(row, "hp_current", 0) or 0) <= max(1, int(getattr(row, "hp_max", 1) or 1) // 4)
                    ),
                    None,
                )
                if critical_ally is not None:
                    return ("Cast Spell", healing_slug)

        return "Attack"

    @staticmethod
    def _combat_actor_key(actor) -> int:
        raw_id = getattr(actor, "id", None)
        if raw_id is None:
            return abs(hash((str(getattr(actor, "name", "?")), str(getattr(actor, "class_name", "?")))))
        try:
            return int(raw_id)
        except Exception:
            return abs(hash(str(raw_id)))

    def _apply_round_lair_action(
        self,
        *,
        log: List[CombatLogEntry],
        round_no: int,
        terrain: str,
        allies: list[Character],
        enemies: list[Entity],
        scene: Optional[dict] = None,
    ) -> None:
        scene_payload = scene if isinstance(scene, dict) else {}
        hazard_state = scene_payload.setdefault("_hazard_state", {}) if isinstance(scene_payload, dict) else {}
        if not isinstance(hazard_state, dict):
            hazard_state = {}
            if isinstance(scene_payload, dict):
                scene_payload["_hazard_state"] = hazard_state

        provided_hazards = [
            str(item).strip().lower().replace(" ", "_")
            for item in list(scene_payload.get("hazards", []) or [])
            if str(item).strip()
        ]
        hazard_flags = set(provided_hazards)
        normalized = str(terrain or "").strip().lower()
        if normalized in {"volcano", "volcanic"}:
            hazard_flags.add("spreading_fire")
        if normalized in {"cramped", "difficult", "mountain", "mountains"}:
            hazard_flags.add("trapline")

        if any(self._is_boss_enemy(enemy) for enemy in enemies):
            hazard_flags.add("boss_lair")

        if not hazard_flags:
            return

        if "spreading_fire" in hazard_flags:
            current_intensity = int(hazard_state.get("fire_intensity", 0) or 0)
            hazard_state["fire_intensity"] = max(1, current_intensity + 1)

        if "trapline" in hazard_flags:
            cooldown = int(hazard_state.get("trap_cooldown", 0) or 0)
            hazard_state["trap_cooldown"] = max(0, cooldown - 1)

        is_boss_lair_round = "boss_lair" in hazard_flags
        is_terrain_surge_round = normalized in {"volcano", "volcanic", "mountain", "mountains"} and round_no % 3 == 0
        if not is_boss_lair_round and not is_terrain_surge_round:
            if "spreading_fire" not in hazard_flags and "trapline" not in hazard_flags:
                return

        if is_boss_lair_round:
            self._log(log, "Initiative 20 — Lair Action: The boss warps the battlefield!", level="compact")
            impacted_allies = [row for row in list(allies) if int(getattr(row, "hp_current", 0) or 0) > 0]
            for actor in impacted_allies:
                save_mod = self._ability_scores(actor).dexterity_mod
                save_roll = self._ability_check_roll(actor, save_mod, requires_sight=True)
                if save_roll >= 13:
                    self._log(log, f"{actor.name} evades the lair pulse.", level="compact")
                    continue
                damage = roll_die("d6", rng=self.rng) + roll_die("d6", rng=self.rng)
                damage = self._modify_incoming_damage(actor, damage)
                hp_now = int(getattr(actor, "hp_current", 0) or 0)
                actor.hp_current = max(0, hp_now - damage)
                self._log(log, f"{actor.name} takes {damage} lair damage ({actor.hp_current}/{getattr(actor, 'hp_max', hp_now)}).", level="compact")

        if is_terrain_surge_round:
            self._log(log, "Initiative 20 — Lair Action: A violent terrain surge erupts across the vanguard!", level="compact")
            impacted = [
                row
                for row in list(allies) + list(enemies)
                if int(getattr(row, "hp_current", 0) or 0) > 0 and self._combat_lane(row) == "vanguard"
            ]
            for actor in impacted:
                save_mod = self._ability_scores(actor).dexterity_mod if isinstance(actor, Character) else 0
                save_roll = self._ability_check_roll(actor, int(save_mod), requires_sight=True)
                if save_roll >= 12:
                    self._log(log, f"{actor.name} weathers the surge.", level="compact")
                    continue
                damage = roll_die("d6", rng=self.rng) + roll_die("d6", rng=self.rng)
                damage = self._modify_incoming_damage(actor, damage)
                hp_now = int(getattr(actor, "hp_current", 0) or 0)
                actor.hp_current = max(0, hp_now - damage)
                self._log(log, f"{actor.name} takes {damage} lair damage ({actor.hp_current}/{getattr(actor, 'hp_max', hp_now)}).", level="compact")

        if "spreading_fire" in hazard_flags:
            intensity = max(1, int(hazard_state.get("fire_intensity", 1) or 1))
            self._log(log, f"Hazard: Spreading fire intensifies (tier {intensity}).", level="compact")
            for actor in [row for row in list(allies) + list(enemies) if int(getattr(row, "hp_current", 0) or 0) > 0]:
                save_mod = self._ability_scores(actor).dexterity_mod if isinstance(actor, Character) else 0
                save_roll = self._ability_check_roll(actor, int(save_mod), requires_sight=True)
                if save_roll >= 11 + min(4, intensity):
                    continue
                damage = sum(roll_die("d4", rng=self.rng) for _ in range(min(4, intensity)))
                damage = self._modify_incoming_damage(actor, damage)
                hp_now = int(getattr(actor, "hp_current", 0) or 0)
                actor.hp_current = max(0, hp_now - damage)
                self._apply_status(
                    actor=actor,
                    status_id="burning",
                    rounds=1,
                    potency=1,
                    log=log,
                    source_name="Spreading Fire",
                )
                self._log(log, f"{actor.name} is scorched for {damage} ({actor.hp_current}/{getattr(actor, 'hp_max', hp_now)}).", level="compact")

        if "trapline" in hazard_flags and int(hazard_state.get("trap_cooldown", 0) or 0) <= 0:
            self._log(log, "Hazard: Hidden traps spring from the battlefield!", level="compact")
            hazard_state["trap_cooldown"] = 2
            candidates = [row for row in list(allies) + list(enemies) if int(getattr(row, "hp_current", 0) or 0) > 0]
            self.rng.shuffle(candidates)
            for actor in candidates[:2]:
                save_mod = self._ability_scores(actor).dexterity_mod if isinstance(actor, Character) else 0
                save_roll = self._ability_check_roll(actor, int(save_mod), requires_sight=True)
                if save_roll >= 12:
                    self._log(log, f"{actor.name} avoids the trap trigger.", level="compact")
                    continue
                damage = roll_die("d6", rng=self.rng)
                damage = self._modify_incoming_damage(actor, damage)
                hp_now = int(getattr(actor, "hp_current", 0) or 0)
                actor.hp_current = max(0, hp_now - damage)
                self._apply_status(
                    actor=actor,
                    status_id="restrained",
                    rounds=1,
                    potency=1,
                    log=log,
                    source_name="Trapline",
                )
                self._log(log, f"{actor.name} is hit by a trap for {damage} ({actor.hp_current}/{getattr(actor, 'hp_max', hp_now)}).", level="compact")

    def _is_boss_enemy(self, enemy: Entity) -> bool:
        level = int(getattr(enemy, "level", 1) or 1)
        hp_max = int(getattr(enemy, "hp_max", getattr(enemy, "hp", 1)) or 1)
        name_key = str(getattr(enemy, "name", "") or "").strip().lower()
        if level >= 10 or hp_max >= 80:
            return True
        return any(keyword in name_key for keyword in self._BOSS_NAME_KEYWORDS)

    def _resolve_spell_cast_party(
        self,
        *,
        caster: Character,
        target,
        spell_slug: Optional[str],
        spell_mod: int,
        prof: int,
        attack_roll_shift: int,
        attack_advantage: Optional[str] = None,
        log: List[CombatLogEntry],
    ) -> None:
        known = getattr(caster, "known_spells", []) or []
        target_slug = spell_slug or (_slugify_spell_name(known[0]) if known else None)
        if not target_slug:
            self._log(log, f"{caster.name} has no spells to cast.", level="compact")
            return

        definition = SPELL_DEFINITIONS.get(str(target_slug).strip().lower())
        if not definition:
            self._log(log, f"{target_slug} is not implemented in combat yet.", level="compact")
            return

        spell = self.spell_repo.get_by_slug(target_slug) if self.spell_repo else None
        level_int = spell.level_int if spell else 0
        if level_int > 0:
            slots = int(getattr(caster, "spell_slots_current", 0) or 0)
            if slots <= 0:
                self._log(log, f"{caster.name} has no spell slots remaining.", level="compact")
                return
            caster.spell_slots_current = max(slots - 1, 0)
            self._log(log, f"{caster.name} expends a spell slot.", level="compact")

        target_name = str(getattr(target, "name", "target"))
        target_ac = int(getattr(target, "armour_class", 10) or 10)
        spell_dc = 8 + int(prof) + int(spell_mod)

        def _apply_damage(amount: int, damage_type: str | None) -> None:
            if str(damage_type or "").lower() == "healing":
                hp_max = int(getattr(target, "hp_max", getattr(target, "hp_current", 1)) or 1)
                hp_now = int(getattr(target, "hp_current", hp_max) or hp_max)
                healed = min(hp_max, hp_now + amount)
                target.hp_current = healed
                self._log(log, f"{caster.name} restores {amount} HP to {target_name} ({target.hp_current}/{hp_max}).", level="compact")
            else:
                hp_now = int(getattr(target, "hp_current", 0) or 0)
                hp_max = int(getattr(target, "hp_max", hp_now) or hp_now)
                target.hp_current = max(0, hp_now - amount)
                self._log(log, f"{caster.name}'s spell hits {target_name} for {amount} {damage_type or 'damage'} ({target.hp_current}/{hp_max}).", level="compact")

        if definition.resolution == "spell_attack":
            if attack_roll_shift:
                self._log(log, f"Dense cover disrupts spell trajectory ({attack_roll_shift} to hit).", level="compact")
            hit, is_crit, _, _ = self._attack_roll(
                int(attack_roll_shift),
                int(prof),
                int(spell_mod),
                target_ac,
                attack_advantage if attack_advantage in {"advantage", "disadvantage"} else None,
                log,
                caster.name,
                target_name,
            )
            if not hit:
                self._log(log, f"{caster.name}'s spell misses.", level="compact")
                return
            dice_expr = definition.damage_dice or "1d6"
            dmg = _roll_dice_expr(dice_expr, ability_mod=int(spell_mod), rng=self.rng)
            if is_crit:
                dmg += _roll_dice_expr(dice_expr, ability_mod=0, rng=self.rng)
            _apply_damage(dmg, definition.damage_type)
            self._apply_spell_status_effects(caster=caster, target=target, definition=definition, log=log)
            return

        if definition.resolution == "save":
            save_roll = self.rng.randint(1, 20)
            self._log(log, f"{target_name} attempts a save: {save_roll} vs DC {spell_dc}.", level="debug")
            if save_roll >= spell_dc:
                self._log(log, f"{target_name} resists the spell.", level="compact")
                return
            dmg = _roll_dice_expr(definition.damage_dice or "1d6", ability_mod=int(spell_mod), rng=self.rng)
            _apply_damage(dmg, definition.damage_type)
            self._apply_spell_status_effects(caster=caster, target=target, definition=definition, log=log)
            return

        dmg = _roll_dice_expr(definition.damage_dice or "1d4", ability_mod=int(spell_mod), rng=self.rng)
        if definition.slug == "shield":
            bonus = 5
            caster.flags["temp_ac_bonus"] = bonus
            caster.flags["shield_rounds"] = 1
            self._log(log, f"A shimmering barrier grants {caster.name} +{bonus} AC until next turn.", level="compact")
            return
        _apply_damage(dmg, definition.damage_type)
        self._apply_spell_status_effects(caster=caster, target=target, definition=definition, log=log)

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
        whetstone_bonus: int = 0,
    ) -> tuple[int, int]:
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
            return player_hp, whetstone_bonus

        if selected_item == "Healing Herbs":
            player.inventory.remove("Healing Herbs")
            heal = roll_die("d4", rng=self.rng) + 1
            player_hp = min(player.hp_max, player_hp + heal)
            self._log(log, f"You apply healing herbs and recover {heal} HP ({player_hp}/{player.hp_max}).", level="compact")
            return player_hp, whetstone_bonus

        if selected_item == "Sturdy Rations":
            player.inventory.remove("Sturdy Rations")
            heal = 2
            player_hp = min(player.hp_max, player_hp + heal)
            self._log(log, f"You take a quick ration break and recover {heal} HP ({player_hp}/{player.hp_max}).", level="compact")
            return player_hp, whetstone_bonus

        if selected_item == "Focus Potion":
            player.inventory.remove("Focus Potion")
            slot_max = int(getattr(player, "spell_slots_max", 0) or 0)
            slots_now = int(getattr(player, "spell_slots_current", 0) or 0)
            if slot_max > 0:
                restored = 1 if slots_now < slot_max else 0
                player.spell_slots_current = min(slot_max, slots_now + 1)
                if restored:
                    self._log(
                        log,
                        f"You drink a Focus Potion and restore 1 spell slot ({player.spell_slots_current}/{slot_max}).",
                        level="compact",
                    )
                else:
                    self._log(log, "Your spell slots are already full.", level="compact")
            else:
                self._log(log, "The potion has no effect without magical training.", level="compact")
            return player_hp, whetstone_bonus

        if selected_item == "Whetstone":
            player.inventory.remove("Whetstone")
            whetstone_bonus = 1
            self._log(log, "You sharpen your weapon. Attacks deal +1 damage this encounter.", level="compact")
            return player_hp, whetstone_bonus

        self._log(log, "No usable items found.", level="compact")
        return player_hp, whetstone_bonus

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
        weather_shift = int(getattr(player, "flags", {}).get("combat_weather_shift", 0) or 0)
        weather_advantage = str(getattr(player, "flags", {}).get("combat_weather_advantage", "") or "").strip().lower()
        if weather_advantage not in {"advantage", "disadvantage"}:
            weather_advantage = ""

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
            if weather_shift:
                self._log(log, f"Weather pressure applies {weather_shift} to spell accuracy.", level="compact")
            hit, is_crit, _, _ = self._attack_roll(
                weather_shift,
                prof,
                spell_mod,
                foe_ac,
                weather_advantage or None,
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
                self._apply_spell_status_effects(caster=player, target=foe, definition=definition, log=log)
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
            self._apply_spell_status_effects(caster=player, target=foe, definition=definition, log=log)
        else:  # auto
            dmg = _roll_dice_expr(definition.damage_dice or "1d4", ability_mod=spell_mod, rng=self.rng)
            if definition.damage_type == "healing":
                _apply_damage(dmg, "healing")
                self._apply_spell_status_effects(caster=player, target=player, definition=definition, log=log)
            elif definition.slug == "shield":
                bonus = 5
                player.flags["temp_ac_bonus"] = bonus
                player.flags["shield_rounds"] = 1
                self._log(log, f"A shimmering barrier grants +{bonus} AC until your next turn.", level="compact")
            else:
                _apply_damage(dmg, definition.damage_type)
                self._apply_spell_status_effects(caster=player, target=foe, definition=definition, log=log)

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

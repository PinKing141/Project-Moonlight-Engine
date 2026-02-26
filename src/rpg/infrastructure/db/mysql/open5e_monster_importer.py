import re
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from rpg.domain.models.entity import Entity


class MonsterListingClient(Protocol):
    def list_monsters(self, page: int = 1) -> dict:
        ...

    def close(self) -> None:
        ...


@dataclass
class UpsertResult:
    created: int = 0
    updated: int = 0
    attached: int = 0


class EntityImportRepository(Protocol):
    def upsert_entities(self, entities: Sequence[Entity], location_id: Optional[int] = None) -> UpsertResult:
        ...

    def get_default_location_id(self) -> Optional[int]:
        ...


_TO_HIT_RE = re.compile(r"([+-]\d+)\s*to hit", re.IGNORECASE)
_DICE_RE = re.compile(r"\((\d+d\d+(?:\s*[+-]\s*\d+)?)\)")


def _cr_to_level(raw) -> int:
    if raw is None:
        return 1
    try:
        if isinstance(raw, str) and "/" in raw:
            num, den = raw.split("/", 1)
            return max(1, int(round(float(num) / float(den))))
        return max(1, int(round(float(raw))))
    except Exception:
        return 1


def _parse_action_block(actions) -> tuple[Optional[int], Optional[str]]:
    if isinstance(actions, dict):
        actions = actions.get("results", []) or actions.get("items", [])
    if not actions:
        return None, None
    if not isinstance(actions, list):
        if isinstance(actions, str):
            actions = [{"name": "attack", "desc": actions}]
        else:
            return None, None

    normalized_actions = []
    for action in actions:
        if isinstance(action, dict):
            normalized_actions.append(action)
            continue
        normalized_actions.append({"name": "attack", "desc": str(action)})

    actions = normalized_actions

    if not actions:
        return None, None

    preferred = {
        "bite",
        "claw",
        "slam",
        "longsword",
        "shortsword",
        "dagger",
        "mace",
        "spear",
        "club",
        "maul",
        "morningstar",
        "scimitar",
        "halberd",
        "battleaxe",
        "greatsword",
        "longbow",
        "shortbow",
        "javelin",
    }
    chosen = None
    for action in actions:
        name = str(action.get("name", "")).lower()
        if name == "multiattack":
            continue
        if name in preferred:
            chosen = action
            break
        if chosen is None:
            chosen = action  # fallback first non-multiattack

    if not chosen:
        return None, None

    desc = chosen.get("desc", "") or ""
    to_hit_match = _TO_HIT_RE.search(desc)
    dice_match = _DICE_RE.search(desc)
    to_hit = int(to_hit_match.group(1)) if to_hit_match else None
    dice = dice_match.group(1).replace(" ", "") if dice_match else None
    return to_hit, dice


def _estimate_from_level(level: int) -> tuple[int, str]:
    if level <= 1:
        return 3, "1d6+1"
    if level <= 4:
        return 5, "1d8+2"
    if level <= 8:
        return 6, "2d6+3"
    if level <= 12:
        return 7, "2d8+4"
    if level <= 16:
        return 8, "3d8+5"
    return 9, "4d8+6"


def _default_stats_for_level(level: int) -> tuple[int, int, int, int]:
    scaled_level = max(level, 1)
    hp = 6 + scaled_level * 3
    attack_min = 1 + scaled_level // 2
    attack_max = 2 + scaled_level
    armor = max(scaled_level // 3, 0)
    return hp, attack_min, attack_max, armor


def _parse_csvish(raw_value) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip().lower() for item in raw_value if str(item).strip()]
    text_value = str(raw_value).strip().lower()
    if not text_value:
        return []
    return [segment.strip() for segment in text_value.split(",") if segment.strip()]


def _first_present(monster: dict, *keys: str):
    for key in keys:
        if key in monster and monster.get(key) is not None:
            return monster.get(key)
    return None


class Open5eMonsterImporter:
    """Fetch Open5e monsters and persist them through a repository."""

    def __init__(self, repository: EntityImportRepository, client: MonsterListingClient) -> None:
        self.repository = repository
        self.client = client

    def import_monsters(self, pages: int, start_page: int = 1, location_id: Optional[int] = None) -> UpsertResult:
        summary = UpsertResult()
        if pages <= 0:
            return summary

        target_location = location_id if location_id is not None else self.repository.get_default_location_id()

        for page in range(start_page, start_page + pages):
            payload = self.client.list_monsters(page=page)
            monsters = payload.get("results", [])
            if not monsters:
                continue
            entities = [self._map_monster(monster) for monster in monsters]
            result = self.repository.upsert_entities(entities, location_id=target_location)
            summary.created += result.created
            summary.updated += result.updated
            summary.attached += result.attached

        return summary

    def _map_monster(self, monster: dict) -> Entity:
        level = _cr_to_level(_first_present(monster, "challenge_rating", "cr", "challenge"))
        name = _first_present(monster, "name", "monster_name", "title") or "Unknown Monster"
        hp_guess, attack_min, attack_max, armor = _default_stats_for_level(level)

        armour_class_raw = _first_present(monster, "armor_class", "ac")
        hit_points_raw = _first_present(monster, "hit_points", "hp", "hp_max")
        to_hit_raw, dice_raw = _parse_action_block(_first_present(monster, "actions", "attacks", "action_list"))
        est_hit, est_dice = _estimate_from_level(level)

        armour_class = armour_class_raw if armour_class_raw is not None else max(10, 10 + level // 2 + armor)
        attack_bonus = to_hit_raw if to_hit_raw is not None else est_hit
        damage_dice = dice_raw or est_dice
        hit_points = hit_points_raw if hit_points_raw is not None else hp_guess
        kind = str(_first_present(monster, "type", "monster_type") or "beast").lower()
        subtype = str(_first_present(monster, "subtype", "sub_type") or "").strip().lower()
        tags = [kind]
        if subtype:
            tags.append(subtype)
        resistances = _parse_csvish(_first_present(monster, "damage_resistances", "resistances", "damageResistance"))

        return Entity(
            id=0,
            name=name,
            level=level,
            hp=hit_points,
            hp_current=hit_points,
            hp_max=hit_points,
            armour_class=armour_class,
            attack_bonus=attack_bonus,
            damage_die=damage_dice,
            attack_min=attack_min,
            attack_max=attack_max,
            armor=armor,
            kind=kind,
            tags=tags,
            resistances=resistances,
        )

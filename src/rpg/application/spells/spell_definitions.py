from dataclasses import dataclass
from typing import Literal, Optional

Resolution = Literal["spell_attack", "save", "auto"]


@dataclass(frozen=True)
class SpellDefinition:
    slug: str
    resolution: Resolution
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    save_ability: Optional[str] = None
    concentration: bool = False
    notes: Optional[str] = None


SPELL_DEFINITIONS: dict[str, SpellDefinition] = {
    "fire-bolt": SpellDefinition("fire-bolt", "spell_attack", damage_dice="1d10", damage_type="fire"),
    "ray-of-frost": SpellDefinition("ray-of-frost", "spell_attack", damage_dice="1d8", damage_type="cold"),
    "sacred-flame": SpellDefinition("sacred-flame", "save", damage_dice="1d8", damage_type="radiant", save_ability="DEX"),
    "eldritch-blast": SpellDefinition("eldritch-blast", "spell_attack", damage_dice="1d10", damage_type="force"),
    "vicious-mockery": SpellDefinition("vicious-mockery", "save", damage_dice="1d4", damage_type="psychic", save_ability="WIS"),
    "magic-missile": SpellDefinition("magic-missile", "auto", damage_dice="3d4+3", damage_type="force"),
    "burning-hands": SpellDefinition("burning-hands", "save", damage_dice="3d6", damage_type="fire", save_ability="DEX"),
    "cure-wounds": SpellDefinition("cure-wounds", "auto", damage_dice="1d8+MOD", damage_type="healing"),
    "shield": SpellDefinition("shield", "auto", notes="+5 AC until your next turn"),
    "hex": SpellDefinition("hex", "auto", damage_type="necrotic", notes="Mark target; your hits deal +1d6 (not yet implemented fully)."),
}

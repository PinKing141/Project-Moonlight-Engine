from __future__ import annotations

from collections.abc import Mapping, Sequence

from rpg.domain.models.class_subclass import ClassSubclass


CLASS_SUBCLASS_CATALOG: Mapping[str, Sequence[ClassSubclass]] = {
    "artificer": (
        ClassSubclass("apothecary", "The Apothecary", "Brews volatile elixirs, restorative draughts, and toxic concoctions."),
        ClassSubclass("iron_vanguard", "The Iron Vanguard", "Armoured inventor fighting beside a mechanical companion."),
    ),
    "barbarian": (
        ClassSubclass("frenzy", "Path of the Frenzy", "Unbridled rage grants extra offense at a personal stamina cost."),
        ClassSubclass("ancestral_spirit", "Path of the Ancestral Spirit", "Animal-spirit rites grant supernatural resilience or mobility while raging."),
    ),
    "bard": (
        ClassSubclass("antiquity", "College of Antiquity", "A scholar-performer using cutting insight, lore, and magical secrets."),
        ClassSubclass("valour", "College of Valour", "A martial inspirer who thrives in melee with armour and battlefield support."),
    ),
    "cleric": (
        ClassSubclass("vitality", "Domain of Vitality", "Master restorative cleric with strong defensive and healing focus."),
        ClassSubclass("conflict", "Domain of Conflict", "Battle priest with martial training and divine frontline pressure."),
    ),
    "druid": (
        ClassSubclass("terrain", "Circle of the Terrain", "Biome-attuned spellcaster with accelerated magical recovery."),
        ClassSubclass("lunar_form", "Circle of the Lunar Form", "Shapeshifting specialist focused on dangerous frontline beast forms."),
    ),
    "fighter": (
        ClassSubclass("paragon", "The Paragon", "Relies on raw physical excellence, improved critical pressure, and endurance."),
        ClassSubclass("combat_tactician", "The Combat Tactician", "Uses tactical stamina to execute maneuvers and direct allies."),
    ),
    "monk": (
        ClassSubclass("striking_hand", "Way of the Striking Hand", "Channels internal force to topple foes, displace them, and shut reactions down."),
        ClassSubclass("shrouded_fist", "Way of the Shrouded Fist", "Shadow-stepping infiltrator with darkness and silence techniques."),
    ),
    "paladin": (
        ClassSubclass("righteousness", "Oath of Righteousness", "A principled protector devoted to truth, defense, and sanctified duty."),
        ClassSubclass("retribution", "Oath of Retribution", "A relentless hunter who singles out and pursues priority threats."),
    ),
    "ranger": (
        ClassSubclass("wilderness_stalker", "The Wilderness Stalker", "Deadly hunter skilled at controlling multi-target skirmishes and large prey."),
        ClassSubclass("beast_warden", "The Beast Warden", "Fights in coordinated tandem with a bonded beast companion."),
    ),
    "rogue": (
        ClassSubclass("scoundrel", "The Scoundrel", "Elite infiltrator with rapid hands, movement utility, and item mastery."),
        ClassSubclass("nightblade", "The Nightblade", "Assault specialist of disguise and toxins who excels at opening strikes."),
    ),
    "warlock": (
        ClassSubclass("infernal", "Pact of the Infernal", "Harnesses hellfire-style power and thrives when enemies fall."),
        ClassSubclass("sylvan_lord", "Pact of the Sylvan Lord", "Uses feylike charms, misdirection, and displacement magic."),
    ),
    "wizard": (
        ClassSubclass("crimson_spire", "School of the Crimson Spire", "Artillery casters shaping explosive fire and force."),
        ClassSubclass("alabaster_sanctum", "School of the Alabaster Sanctum", "Defensive ward scholars specializing in protective abjuration."),
        ClassSubclass("obsidian_cabal", "School of the Obsidian Cabal", "Forbidden arcanists of shadow, death, and life-draining arts."),
        ClassSubclass("cobalt_ward", "School of the Cobalt Ward", "Arcane suppressors focused on containment and anti-magic control."),
        ClassSubclass("emerald_circle", "School of the Emerald Circle", "Transmuters and conjurers of acid, poison, and nature-warping effects."),
        ClassSubclass("aurelian_order", "School of the Aurelian Order", "Fate seers manipulating timing, probability, and foresight."),
    ),
    "sorcerer": (
        ClassSubclass("crimson_pyreborn", "Crimson Pyreborn", "Innate volatile fire/force prodigy trained for destructive control."),
        ClassSubclass("alabaster_seraph", "Alabaster Seraph", "Rare lawful-celestial bloodline adept at sanctioned restorative combat magic."),
        ClassSubclass("obsidian_umbralist", "Obsidian Umbralist", "Natural channeler of gloom, deathly resonance, and umbral force."),
        ClassSubclass("cobalt_anomaly", "Cobalt Anomaly", "Unstable conduit of chaotic surges studied for containment."),
        ClassSubclass("emerald_beguiler", "Emerald Beguiler", "Fae-tinged manipulator blending beguilement with toxic power."),
        ClassSubclass("aurelian_fate_weaver", "Aurelian Fate-Weaver", "Innately linked to cosmic order, luck, and temporal drift."),
    ),
}


def subclasses_for_class(class_slug_or_name: str | None) -> list[ClassSubclass]:
    class_key = str(class_slug_or_name or "").strip().lower()
    return list(CLASS_SUBCLASS_CATALOG.get(class_key, ()))


def resolve_subclass(class_slug_or_name: str | None, subclass_slug: str | None) -> ClassSubclass | None:
    target_slug = str(subclass_slug or "").strip().lower()
    if not target_slug:
        return None
    for option in subclasses_for_class(class_slug_or_name):
        if option.slug == target_slug:
            return option
    return None

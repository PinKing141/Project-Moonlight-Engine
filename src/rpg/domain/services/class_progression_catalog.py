from __future__ import annotations

from dataclasses import dataclass, field


CLASS_PROGRESSION_SCHEMA_VERSION = "class_progression_v1"
UNMAPPED_FUTURE_FEATURE_TEXT = "Future feature pending content update."
KNOWN_FEATURE_FLAGS = {
    "asi",
    "spell_access",
    "subclass_feature",
    "resource_refresh",
    "extra_attack",
    "capstone",
}


@dataclass(frozen=True)
class ClassProgressionRow:
    level: int
    gains: tuple[str, ...]
    resource_tags: tuple[str, ...] = field(default_factory=tuple)
    feature_flags: tuple[str, ...] = field(default_factory=tuple)


def _rows(*entries: tuple[int, str]) -> tuple[ClassProgressionRow, ...]:
    rows: list[ClassProgressionRow] = []
    for level, gains_text in entries:
        gains = tuple(part.strip() for part in str(gains_text).split(",") if part.strip())
        rows.append(ClassProgressionRow(level=int(level), gains=gains))
    return tuple(rows)


def gains_with_fallback(row: ClassProgressionRow) -> tuple[str, ...]:
    gains = tuple(str(part).strip() for part in tuple(getattr(row, "gains", ()) or ()) if str(part).strip())
    if gains:
        return gains
    return (UNMAPPED_FUTURE_FEATURE_TEXT,)


def gains_text_for_row(row: ClassProgressionRow) -> str:
    return ", ".join(gains_with_fallback(row))


def progression_contract_for_class(class_slug_or_name: str | None) -> dict[str, object]:
    class_slug = normalize_class_progression_key(class_slug_or_name)
    rows = progression_rows_for_class(class_slug_or_name)
    payload_rows: list[dict[str, object]] = []
    for row in rows:
        payload_rows.append(
            {
                "class_slug": class_slug,
                "level": int(row.level),
                "gains": [str(value) for value in gains_with_fallback(row)],
                "resource_tags": [str(value) for value in tuple(getattr(row, "resource_tags", ()) or ()) if str(value).strip()],
                "feature_flags": [str(value) for value in tuple(getattr(row, "feature_flags", ()) or ()) if str(value).strip()],
            }
        )
    return {
        "version": CLASS_PROGRESSION_SCHEMA_VERSION,
        "class_slug": class_slug,
        "rows": payload_rows,
    }


def normalize_progression_contract(payload: dict[str, object] | None) -> tuple[str, tuple[ClassProgressionRow, ...], tuple[str, ...]]:
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}
    version = str(raw.get("version", "") or "").strip()
    if version != CLASS_PROGRESSION_SCHEMA_VERSION:
        warnings.append(
            f"Unknown progression contract version '{version or 'missing'}'; defaulting to {CLASS_PROGRESSION_SCHEMA_VERSION}."
        )
        version = CLASS_PROGRESSION_SCHEMA_VERSION

    rows_raw = raw.get("rows", [])
    if not isinstance(rows_raw, list):
        warnings.append("Progression contract rows must be a list; defaulting to empty rows.")
        rows_raw = []

    normalized_rows: list[ClassProgressionRow] = []
    for index, row_raw in enumerate(rows_raw):
        if not isinstance(row_raw, dict):
            warnings.append(f"Skipping non-object row at index {index}.")
            continue

        unknown_fields = sorted(
            set(row_raw.keys())
            - {"class_slug", "level", "gains", "resource_tags", "feature_flags"}
        )
        if unknown_fields:
            warnings.append(
                f"Row {index} has unsupported fields {', '.join(unknown_fields)}; unsupported fields were ignored."
            )

        try:
            level = int(row_raw.get("level", 0) or 0)
        except Exception:
            level = 0
        if level <= 0:
            warnings.append(f"Skipping row {index} with invalid level '{row_raw.get('level')}'.")
            continue

        gains_raw = row_raw.get("gains", [])
        if isinstance(gains_raw, str):
            gains = tuple(part.strip() for part in gains_raw.split(",") if part.strip())
        elif isinstance(gains_raw, list):
            gains = tuple(str(part).strip() for part in gains_raw if str(part).strip())
        else:
            gains = ()

        resource_tags_raw = row_raw.get("resource_tags", [])
        if isinstance(resource_tags_raw, list):
            resource_tags = tuple(str(part).strip() for part in resource_tags_raw if str(part).strip())
        elif isinstance(resource_tags_raw, str):
            resource_tags = tuple(part.strip() for part in resource_tags_raw.split(",") if part.strip())
        else:
            resource_tags = ()

        feature_flags_raw = row_raw.get("feature_flags", [])
        if isinstance(feature_flags_raw, str):
            feature_candidates = [part.strip() for part in feature_flags_raw.split(",") if part.strip()]
        elif isinstance(feature_flags_raw, list):
            feature_candidates = [str(part).strip() for part in feature_flags_raw if str(part).strip()]
        else:
            feature_candidates = []

        feature_flags: list[str] = []
        for feature_value in feature_candidates:
            key = str(feature_value).lower()
            if key not in KNOWN_FEATURE_FLAGS:
                warnings.append(
                    f"Row {index} has unknown feature flag '{feature_value}'; flag ignored."
                )
                continue
            feature_flags.append(key)

        normalized_rows.append(
            ClassProgressionRow(
                level=int(level),
                gains=tuple(gains),
                resource_tags=tuple(resource_tags),
                feature_flags=tuple(feature_flags),
            )
        )

    return version, tuple(normalized_rows), tuple(warnings)


CLASS_PROGRESSION_TABLES: dict[str, tuple[ClassProgressionRow, ...]] = {
    "barbarian": _rows(
        (1, "Rage, Unarmored Defense"),
        (2, "Reckless Attack, Danger Sense"),
        (3, "Primal Path feature"),
        (4, "ASI"),
        (5, "Extra Attack, Fast Movement"),
        (6, "Path feature"),
        (7, "Feral Instinct"),
        (8, "ASI"),
        (9, "Brutal Critical (1 die)"),
        (10, "Path feature"),
        (11, "Relentless Rage"),
        (12, "ASI"),
        (13, "Brutal Critical (2 dice)"),
        (14, "Path feature"),
        (15, "Persistent Rage"),
        (16, "ASI"),
        (17, "Brutal Critical (3 dice)"),
        (18, "Indomitable Might"),
        (19, "ASI"),
        (20, "Primal Champion"),
    ),
    "bard": _rows(
        (1, "Bardic Inspiration (d6), Spellcasting"),
        (2, "Jack of All Trades, Song of Rest"),
        (3, "Bard College, Expertise"),
        (4, "ASI"),
        (5, "Inspiration refresh on SR, Inspiration d8"),
        (6, "Countercharm, College feature"),
        (7, "4th-level spell access"),
        (8, "ASI"),
        (9, "Song of Rest upgrade"),
        (10, "Expertise, Magical Secrets, Inspiration d10"),
        (11, "6th-level spell access"),
        (12, "ASI"),
        (13, "Song of Rest upgrade"),
        (14, "College feature, Magical Secrets"),
        (15, "Inspiration d12"),
        (16, "ASI"),
        (17, "9th-level spell access"),
        (18, "Magical Secrets"),
        (19, "ASI"),
        (20, "Superior Inspiration"),
    ),
    "cleric": _rows(
        (1, "Spellcasting, Divine Domain"),
        (2, "Channel Divinity"),
        (3, "2nd-level spell access"),
        (4, "ASI"),
        (5, "Destroy Undead (CR 1/2), 3rd-level spells"),
        (6, "Domain feature, Channel Divinity use+"),
        (7, "4th-level spells"),
        (8, "ASI, Divine Strike/Potent Cantrip"),
        (9, "5th-level spells"),
        (10, "Divine Intervention"),
        (11, "Destroy Undead (CR 2), 6th-level spells"),
        (12, "ASI"),
        (13, "7th-level spells"),
        (14, "Destroy Undead (CR 3)"),
        (15, "8th-level spells"),
        (16, "ASI"),
        (17, "Domain capstone, 9th-level spells"),
        (18, "Channel Divinity use+"),
        (19, "ASI"),
        (20, "Divine Intervention auto-success"),
    ),
    "druid": _rows(
        (1, "Druidic, Spellcasting"),
        (2, "Wild Shape, Druid Circle"),
        (3, "2nd-level spells"),
        (4, "ASI, Wild Shape improvement"),
        (5, "3rd-level spells"),
        (6, "Circle feature"),
        (7, "4th-level spells"),
        (8, "ASI, Wild Shape flight/swim unlocks"),
        (9, "5th-level spells"),
        (10, "Circle feature"),
        (11, "6th-level spells"),
        (12, "ASI"),
        (13, "7th-level spells"),
        (14, "Circle feature"),
        (15, "8th-level spells"),
        (16, "ASI"),
        (17, "9th-level spells"),
        (18, "Timeless Body, Beast Spells"),
        (19, "ASI"),
        (20, "Archdruid"),
    ),
    "fighter": _rows(
        (1, "Fighting Style, Second Wind"),
        (2, "Action Surge"),
        (3, "Martial Archetype"),
        (4, "ASI"),
        (5, "Extra Attack"),
        (6, "ASI"),
        (7, "Archetype feature"),
        (8, "ASI"),
        (9, "Indomitable"),
        (10, "Archetype feature"),
        (11, "Extra Attack (2)"),
        (12, "ASI"),
        (13, "Indomitable (2)"),
        (14, "ASI"),
        (15, "Archetype feature"),
        (16, "ASI"),
        (17, "Action Surge (2), Indomitable (3)"),
        (18, "Archetype feature"),
        (19, "ASI"),
        (20, "Extra Attack (3)"),
    ),
    "monk": _rows(
        (1, "Martial Arts, Unarmored Defense"),
        (2, "Ki, Unarmored Movement"),
        (3, "Monastic Tradition, Deflect Missiles"),
        (4, "ASI, Slow Fall"),
        (5, "Extra Attack, Stunning Strike"),
        (6, "Ki-Empowered Strikes, Tradition feature"),
        (7, "Evasion, Stillness of Mind"),
        (8, "ASI"),
        (9, "Unarmored Movement improvement"),
        (10, "Purity of Body"),
        (11, "Tradition feature"),
        (12, "ASI"),
        (13, "Tongue of the Sun and Moon"),
        (14, "Diamond Soul"),
        (15, "Timeless Body"),
        (16, "ASI"),
        (17, "Tradition feature"),
        (18, "Empty Body"),
        (19, "ASI"),
        (20, "Perfect Self"),
    ),
    "paladin": _rows(
        (1, "Divine Sense, Lay on Hands"),
        (2, "Fighting Style, Spellcasting, Divine Smite"),
        (3, "Sacred Oath, Divine Health"),
        (4, "ASI"),
        (5, "Extra Attack"),
        (6, "Aura of Protection"),
        (7, "Oath feature"),
        (8, "ASI"),
        (9, "3rd-level spells"),
        (10, "Aura of Courage"),
        (11, "Improved Divine Smite"),
        (12, "ASI"),
        (13, "4th-level spells"),
        (14, "Cleansing Touch"),
        (15, "Oath feature"),
        (16, "ASI"),
        (17, "5th-level spells"),
        (18, "Aura range improvement"),
        (19, "ASI"),
        (20, "Oath capstone"),
    ),
    "ranger": _rows(
        (1, "Favored Enemy, Natural Explorer"),
        (2, "Fighting Style, Spellcasting"),
        (3, "Ranger Archetype, Primeval Awareness"),
        (4, "ASI"),
        (5, "Extra Attack"),
        (6, "Favored Enemy/Natural Explorer improvement"),
        (7, "Archetype feature"),
        (8, "ASI, Land's Stride"),
        (9, "3rd-level spells"),
        (10, "Hide in Plain Sight"),
        (11, "Archetype feature"),
        (12, "ASI"),
        (13, "4th-level spells"),
        (14, "Vanish"),
        (15, "Archetype feature"),
        (16, "ASI"),
        (17, "5th-level spells"),
        (18, "Feral Senses"),
        (19, "ASI"),
        (20, "Foe Slayer"),
    ),
    "rogue": _rows(
        (1, "Expertise, Sneak Attack, Thieves' Cant"),
        (2, "Cunning Action"),
        (3, "Roguish Archetype"),
        (4, "ASI"),
        (5, "Uncanny Dodge"),
        (6, "Expertise"),
        (7, "Evasion"),
        (8, "ASI"),
        (9, "Archetype feature"),
        (10, "ASI"),
        (11, "Reliable Talent"),
        (12, "ASI"),
        (13, "Archetype feature"),
        (14, "Blindsense"),
        (15, "Slippery Mind"),
        (16, "ASI"),
        (17, "Archetype feature"),
        (18, "Elusive"),
        (19, "ASI"),
        (20, "Stroke of Luck"),
    ),
    "sorcerer": _rows(
        (1, "Spellcasting, Sorcerous Origin"),
        (2, "Font of Magic"),
        (3, "Metamagic"),
        (4, "ASI"),
        (5, "3rd-level spells"),
        (6, "Origin feature"),
        (7, "4th-level spells"),
        (8, "ASI"),
        (9, "5th-level spells"),
        (10, "Metamagic option"),
        (11, "6th-level spells"),
        (12, "ASI"),
        (13, "7th-level spells"),
        (14, "Origin feature"),
        (15, "8th-level spells"),
        (16, "ASI"),
        (17, "9th-level spells, Metamagic option"),
        (18, "Origin feature"),
        (19, "ASI"),
        (20, "Sorcerous Restoration"),
    ),
    "warlock": _rows(
        (1, "Otherworldly Patron, Pact Magic"),
        (2, "Eldritch Invocations"),
        (3, "Pact Boon"),
        (4, "ASI"),
        (5, "Invocation upgrade"),
        (6, "Patron feature"),
        (7, "4th-level pact slots"),
        (8, "ASI"),
        (9, "5th-level pact slots"),
        (10, "Patron feature"),
        (11, "Mystic Arcanum (6th)"),
        (12, "ASI, Invocation upgrade"),
        (13, "Mystic Arcanum (7th)"),
        (14, "Patron feature"),
        (15, "Mystic Arcanum (8th), Invocation upgrade"),
        (16, "ASI"),
        (17, "Mystic Arcanum (9th)"),
        (18, "Invocation upgrade"),
        (19, "ASI"),
        (20, "Eldritch Master"),
    ),
    "wizard": _rows(
        (1, "Spellcasting, Arcane Recovery"),
        (2, "Arcane Tradition"),
        (3, "2nd-level spells"),
        (4, "ASI"),
        (5, "3rd-level spells"),
        (6, "Tradition feature"),
        (7, "4th-level spells"),
        (8, "ASI"),
        (9, "5th-level spells"),
        (10, "Tradition feature"),
        (11, "6th-level spells"),
        (12, "ASI"),
        (13, "7th-level spells"),
        (14, "Tradition feature"),
        (15, "8th-level spells"),
        (16, "ASI"),
        (17, "9th-level spells"),
        (18, "Spell Mastery"),
        (19, "ASI"),
        (20, "Signature Spells"),
    ),
    "artificer": _rows(
        (1, "Magical Tinkering, Spellcasting"),
        (2, "Infuse Item"),
        (3, "Artificer Specialist, tool feature"),
        (4, "ASI"),
        (5, "Specialist feature"),
        (6, "Tool Expertise"),
        (7, "Flash of Genius"),
        (8, "ASI"),
        (9, "Specialist feature"),
        (10, "Magic Item Adept"),
        (11, "Spell-Storing Item"),
        (12, "ASI"),
        (13, "4th-level spells"),
        (14, "Magic Item Savant"),
        (15, "Specialist feature"),
        (16, "ASI"),
        (17, "5th-level spells"),
        (18, "Magic Item Master"),
        (19, "ASI"),
        (20, "Soul of Artifice"),
    ),
}


def normalize_class_progression_key(class_slug_or_name: str | None) -> str:
    return str(class_slug_or_name or "").strip().lower().replace("-", " ").replace("_", " ").strip().replace(" ", "_")


def progression_rows_for_class(class_slug_or_name: str | None) -> tuple[ClassProgressionRow, ...]:
    key = normalize_class_progression_key(class_slug_or_name)
    if not key:
        return ()
    lookup = key.replace("_", "")
    for slug, rows in CLASS_PROGRESSION_TABLES.items():
        slug_lookup = str(slug).replace("_", "")
        if key == slug or lookup == slug_lookup:
            return rows
    return ()

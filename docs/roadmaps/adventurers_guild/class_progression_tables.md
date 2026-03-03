# Class Progression Tables (1–20)

This table set is a **design contract** for progression content planning. It is intentionally implementation-oriented and can be translated into data tables for repositories.

## Baseline Alignment
- Engine level cap is already 20; this table remains the canonical progression target for that cap.
- Integrate through existing progression service/contracts incrementally; avoid one-pass full rewrite.
- Keep compatibility with current level-up flow and additive data-contract evolution.

## Use This As a Checklist, Not a Big-Bang Rewrite

### CP-1: Data Contract Definition
- [x] Define machine-readable schema for class progression rows (`class_slug`, `level`, `gains`, `resource_tags`, `feature_flags`).
- [x] Add version key (e.g., `class_progression_v1`) and normalization defaults.
- [x] Keep unknown features non-fatal (warn + skip strategy).

### CP-2: Repository Parity
- [x] Add in-memory source of truth for progression rows.
- [x] Add SQL parity path with migration-safe loading.
- [x] Add parity tests (in-memory vs SQL) for representative classes/levels.

### CP-3: Service Integration (bounded)
- [x] Resolve level gains via data contract before applying state mutations.
- [x] Keep existing level-up/public intent signatures stable.
- [x] Emit deterministic unlock records for replay/debug.

### CP-4: Test Coverage
- [x] Unit tests for every class milestone breakpoints (1, 3, 5, 11, 17, 20).
- [x] Integration tests for level-up flow with unlock persistence.
- [x] Regression tests for multiclass interaction and resource refresh behavior.

### CP-5: Player Visibility
- [x] Expose upcoming milestone preview in existing UI surfaces.
- [x] Ensure unlock text maps 1:1 to data rows (no hardcoded duplicate lists).
- [x] Add fallback text for unmapped future features.

## Non-Goals (prevent overbuild)
- No redesign of core combat math in this slice.
- No speculative class rebalancing beyond represented table entries.
- No new progression UI navigation tree; use current views.

## Legend
- `ASI` = ability score improvement / feat pick
- `SR` = short-rest resource
- `LR` = long-rest resource

---

## Barbarian
| Level | Gains |
|---|---|
| 1 | Rage, Unarmored Defense |
| 2 | Reckless Attack, Danger Sense |
| 3 | Primal Path feature |
| 4 | ASI |
| 5 | Extra Attack, Fast Movement |
| 6 | Path feature |
| 7 | Feral Instinct |
| 8 | ASI |
| 9 | Brutal Critical (1 die) |
| 10 | Path feature |
| 11 | Relentless Rage |
| 12 | ASI |
| 13 | Brutal Critical (2 dice) |
| 14 | Path feature |
| 15 | Persistent Rage |
| 16 | ASI |
| 17 | Brutal Critical (3 dice) |
| 18 | Indomitable Might |
| 19 | ASI |
| 20 | Primal Champion |

## Bard
| Level | Gains |
|---|---|
| 1 | Bardic Inspiration (d6), Spellcasting |
| 2 | Jack of All Trades, Song of Rest |
| 3 | Bard College, Expertise |
| 4 | ASI |
| 5 | Inspiration refresh on SR, Inspiration d8 |
| 6 | Countercharm, College feature |
| 7 | 4th-level spell access |
| 8 | ASI |
| 9 | Song of Rest upgrade |
| 10 | Expertise, Magical Secrets, Inspiration d10 |
| 11 | 6th-level spell access |
| 12 | ASI |
| 13 | Song of Rest upgrade |
| 14 | College feature, Magical Secrets |
| 15 | Inspiration d12 |
| 16 | ASI |
| 17 | 9th-level spell access |
| 18 | Magical Secrets |
| 19 | ASI |
| 20 | Superior Inspiration |

## Cleric
| Level | Gains |
|---|---|
| 1 | Spellcasting, Divine Domain |
| 2 | Channel Divinity |
| 3 | 2nd-level spell access |
| 4 | ASI |
| 5 | Destroy Undead (CR 1/2), 3rd-level spells |
| 6 | Domain feature, Channel Divinity use+ |
| 7 | 4th-level spells |
| 8 | ASI, Divine Strike/Potent Cantrip |
| 9 | 5th-level spells |
| 10 | Divine Intervention |
| 11 | Destroy Undead (CR 2), 6th-level spells |
| 12 | ASI |
| 13 | 7th-level spells |
| 14 | Destroy Undead (CR 3) |
| 15 | 8th-level spells |
| 16 | ASI |
| 17 | Domain capstone, 9th-level spells |
| 18 | Channel Divinity use+ |
| 19 | ASI |
| 20 | Divine Intervention auto-success |

## Druid
| Level | Gains |
|---|---|
| 1 | Druidic, Spellcasting |
| 2 | Wild Shape, Druid Circle |
| 3 | 2nd-level spells |
| 4 | ASI, Wild Shape improvement |
| 5 | 3rd-level spells |
| 6 | Circle feature |
| 7 | 4th-level spells |
| 8 | ASI, Wild Shape flight/swim unlocks |
| 9 | 5th-level spells |
| 10 | Circle feature |
| 11 | 6th-level spells |
| 12 | ASI |
| 13 | 7th-level spells |
| 14 | Circle feature |
| 15 | 8th-level spells |
| 16 | ASI |
| 17 | 9th-level spells |
| 18 | Timeless Body, Beast Spells |
| 19 | ASI |
| 20 | Archdruid |

## Fighter
| Level | Gains |
|---|---|
| 1 | Fighting Style, Second Wind |
| 2 | Action Surge |
| 3 | Martial Archetype |
| 4 | ASI |
| 5 | Extra Attack |
| 6 | ASI |
| 7 | Archetype feature |
| 8 | ASI |
| 9 | Indomitable |
| 10 | Archetype feature |
| 11 | Extra Attack (2) |
| 12 | ASI |
| 13 | Indomitable (2) |
| 14 | ASI |
| 15 | Archetype feature |
| 16 | ASI |
| 17 | Action Surge (2), Indomitable (3) |
| 18 | Archetype feature |
| 19 | ASI |
| 20 | Extra Attack (3) |

## Monk
| Level | Gains |
|---|---|
| 1 | Martial Arts, Unarmored Defense |
| 2 | Ki, Unarmored Movement |
| 3 | Monastic Tradition, Deflect Missiles |
| 4 | ASI, Slow Fall |
| 5 | Extra Attack, Stunning Strike |
| 6 | Ki-Empowered Strikes, Tradition feature |
| 7 | Evasion, Stillness of Mind |
| 8 | ASI |
| 9 | Unarmored Movement improvement |
| 10 | Purity of Body |
| 11 | Tradition feature |
| 12 | ASI |
| 13 | Tongue of the Sun and Moon |
| 14 | Diamond Soul |
| 15 | Timeless Body |
| 16 | ASI |
| 17 | Tradition feature |
| 18 | Empty Body |
| 19 | ASI |
| 20 | Perfect Self |

## Paladin
| Level | Gains |
|---|---|
| 1 | Divine Sense, Lay on Hands |
| 2 | Fighting Style, Spellcasting, Divine Smite |
| 3 | Sacred Oath, Divine Health |
| 4 | ASI |
| 5 | Extra Attack |
| 6 | Aura of Protection |
| 7 | Oath feature |
| 8 | ASI |
| 9 | 3rd-level spells |
| 10 | Aura of Courage |
| 11 | Improved Divine Smite |
| 12 | ASI |
| 13 | 4th-level spells |
| 14 | Cleansing Touch |
| 15 | Oath feature |
| 16 | ASI |
| 17 | 5th-level spells |
| 18 | Aura range improvement |
| 19 | ASI |
| 20 | Oath capstone |

## Ranger
| Level | Gains |
|---|---|
| 1 | Favored Enemy, Natural Explorer |
| 2 | Fighting Style, Spellcasting |
| 3 | Ranger Archetype, Primeval Awareness |
| 4 | ASI |
| 5 | Extra Attack |
| 6 | Favored Enemy/Natural Explorer improvement |
| 7 | Archetype feature |
| 8 | ASI, Land's Stride |
| 9 | 3rd-level spells |
| 10 | Hide in Plain Sight |
| 11 | Archetype feature |
| 12 | ASI |
| 13 | 4th-level spells |
| 14 | Vanish |
| 15 | Archetype feature |
| 16 | ASI |
| 17 | 5th-level spells |
| 18 | Feral Senses |
| 19 | ASI |
| 20 | Foe Slayer |

## Rogue
| Level | Gains |
|---|---|
| 1 | Expertise, Sneak Attack, Thieves' Cant |
| 2 | Cunning Action |
| 3 | Roguish Archetype |
| 4 | ASI |
| 5 | Uncanny Dodge |
| 6 | Expertise |
| 7 | Evasion |
| 8 | ASI |
| 9 | Archetype feature |
| 10 | ASI |
| 11 | Reliable Talent |
| 12 | ASI |
| 13 | Archetype feature |
| 14 | Blindsense |
| 15 | Slippery Mind |
| 16 | ASI |
| 17 | Archetype feature |
| 18 | Elusive |
| 19 | ASI |
| 20 | Stroke of Luck |

## Sorcerer
| Level | Gains |
|---|---|
| 1 | Spellcasting, Sorcerous Origin |
| 2 | Font of Magic |
| 3 | Metamagic |
| 4 | ASI |
| 5 | 3rd-level spells |
| 6 | Origin feature |
| 7 | 4th-level spells |
| 8 | ASI |
| 9 | 5th-level spells |
| 10 | Metamagic option |
| 11 | 6th-level spells |
| 12 | ASI |
| 13 | 7th-level spells |
| 14 | Origin feature |
| 15 | 8th-level spells |
| 16 | ASI |
| 17 | 9th-level spells, Metamagic option |
| 18 | Origin feature |
| 19 | ASI |
| 20 | Sorcerous Restoration |

## Warlock
| Level | Gains |
|---|---|
| 1 | Otherworldly Patron, Pact Magic |
| 2 | Eldritch Invocations |
| 3 | Pact Boon |
| 4 | ASI |
| 5 | Invocation upgrade |
| 6 | Patron feature |
| 7 | 4th-level pact slots |
| 8 | ASI |
| 9 | 5th-level pact slots |
| 10 | Patron feature |
| 11 | Mystic Arcanum (6th) |
| 12 | ASI, Invocation upgrade |
| 13 | Mystic Arcanum (7th) |
| 14 | Patron feature |
| 15 | Mystic Arcanum (8th), Invocation upgrade |
| 16 | ASI |
| 17 | Mystic Arcanum (9th) |
| 18 | Invocation upgrade |
| 19 | ASI |
| 20 | Eldritch Master |

## Wizard
| Level | Gains |
|---|---|
| 1 | Spellcasting, Arcane Recovery |
| 2 | Arcane Tradition |
| 3 | 2nd-level spells |
| 4 | ASI |
| 5 | 3rd-level spells |
| 6 | Tradition feature |
| 7 | 4th-level spells |
| 8 | ASI |
| 9 | 5th-level spells |
| 10 | Tradition feature |
| 11 | 6th-level spells |
| 12 | ASI |
| 13 | 7th-level spells |
| 14 | Tradition feature |
| 15 | 8th-level spells |
| 16 | ASI |
| 17 | 9th-level spells |
| 18 | Spell Mastery |
| 19 | ASI |
| 20 | Signature Spells |

## Artificer
| Level | Gains |
|---|---|
| 1 | Magical Tinkering, Spellcasting |
| 2 | Infuse Item |
| 3 | Artificer Specialist, tool feature |
| 4 | ASI |
| 5 | Specialist feature |
| 6 | Tool Expertise |
| 7 | Flash of Genius |
| 8 | ASI |
| 9 | Specialist feature |
| 10 | Magic Item Adept |
| 11 | Spell-Storing Item |
| 12 | ASI |
| 13 | 4th-level spells |
| 14 | Magic Item Savant |
| 15 | Specialist feature |
| 16 | ASI |
| 17 | 5th-level spells |
| 18 | Magic Item Master |
| 19 | ASI |
| 20 | Soul of Artifice |

---

## Implementation Notes
- Convert this file into machine-readable progression data before wiring level-up logic.
- Validate each level gain with automated tests (`progression_service` + class profile tests).
- Tie unlock visibility to UI intents so players can preview upcoming milestones.

## Definition of Done
- [x] All listed class/level gains are represented in machine-readable data.
- [x] Progression integration passes deterministic regression tests.
- [x] No application contract drift for level-up related intents.
- [x] Documentation is updated alongside any data-contract/schema changes.

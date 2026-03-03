# Difficulty Tiers + Hardcore House Rules

## Current System Baseline
- Character creation currently exposes five presets: `easy`, `normal`, `hard`, `deadly`, `nightmare`.
- This roadmap defines the target five-tier policy and hardcore toggles without breaking existing save/profile behavior.

## 1) Difficulty Tiers (5)

| Tier | Design Intent | Resource Pressure | Casualty Risk | AI/Encounter Behavior |
|---|---|---|---|---|
| Easy | Minimal resource tax, learning-friendly pacing | Low | Very low | Forgiving target selection, shorter fights |
| Normal | Tense but stable runs | Moderate | Low | Standard tactics, occasional focus fire |
| Hard | Mistakes punished; weaker builds can drop | High | Moderate | Coordinated enemy turns, stronger hazard usage |
| Deadly | Tactical play required every encounter | Very high | High | Aggressive target focus, multi-layer hazards |
| Nightmare | Near-hardcore even without house rules | Extreme | Very high | Optimized enemy synergies, high attrition cadence |

## 2) Mapping to User-Specified Meanings
- Easy = minimal resource tax.
- Normal = scary moments, usually no casualties.
- Hard = weaker characters may be knocked out; slight chance of death.
- Deadly = high lethal risk; requires smart tactical play.
- Added 5th tier (`Nightmare`) to satisfy five-tier requirement while preserving your named four.

## 2.1) Compatibility Mapping (migration-safe)

| Existing Preset | Interim Target Tier | Notes |
|---|---|---|
| `easy` | Easy | Direct canonical mapping |
| `normal` | Normal | Default baseline path |
| `hard` | Hard | High-pressure baseline |
| `medium` (legacy alias) | Normal | Normalized to canonical `normal` |

Deadly/Nightmare are now first-class presets in current implementation.

## 3) Hardcore House Rules (toggle set)

### A) Maximum Monster HP
- Monsters roll no HP dice; always use maximum HP profile.
- Elite/leader monsters gain additional resistance windows at high tiers.

### B) Deadlier Death Saves
- Base death save DC starts at 10.
- DC increases with overkill damage bands.
- Failed death save applies a wound state that requires post-combat skill checks to clear.
- Unresolved wound states reduce rest efficiency and can stack penalties.

### C) Rest Restrictions
- Short/Long rest disabled while failed death saves remain unresolved.
- Recovery actions available through medical kits, healer services, or camp events.
- Guild medical support can clear one failed-save mark at merit cost.

### Hardcore Toggle Rules
- Toggles are opt-in and can be bundled as presets (`Hardcore Lite`, `Hardcore Full`) plus custom.
- Enabling toggles must show explicit warning text for lethality and rest lockouts.
- Toggle state must be persisted with deterministic run context for replay/debug parity.

## 4) Scaling Knobs
- Enemy HP multiplier
- Enemy damage variance and crit pressure
- Reinforcement chance
- Environmental hazard density
- Resource scarcity (consumables, safe rests, healing windows)

## 4.1) Knob Constraints (anti-overbuild)
- Cap each knob with min/max ranges documented in one table.
- One phase may change at most two knob families unless telemetry indicates severe imbalance.
- Avoid adding new knob types unless an acceptance criterion requires them.

## 5) Guardrails
- No "unwinnable" mandatory contracts on Easy/Medium.
- Hardcore toggles are opt-in preset or custom profile.
- Reward multipliers must track risk tier to prevent degenerate farming.

## 6) Implementation Checklist (phased)

### DR-1: Policy Contract
- [x] Define canonical tier enum + compatibility aliases.
- [x] Define hardcore toggle schema + default values.
- [x] Add normalization tests for legacy/unknown difficulty payloads.

### DR-2: Runtime Wiring
- [x] Apply tier/toggle modifiers through existing deterministic progression/combat pathways.
- [x] Ensure encounter/reward/rest systems read same resolved difficulty profile.
- [x] Add regression tests for deterministic outcomes across preset/toggle combinations.

### DR-3: UX + Safety
- [x] Surface concise risk labels and expected casualty pressure.
- [x] Show guardrail warning if configuration risks unwinnable mandatory path.
- [x] Keep legacy preset labels visible until migration complete.

## 7) Definition of Done
- [x] Difficulty selection remains backward-compatible for existing saves/profiles.
- [x] Five-tier semantics are test-covered and measurable.
- [x] Hardcore toggles are opt-in, persisted, and replay-stable.
- [x] Reward/risk linkage passes anti-farming checks.

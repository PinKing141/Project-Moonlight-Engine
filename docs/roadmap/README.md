# Project Moonlight Engine Roadmap (Comprehensive)

This roadmap packages long-horizon planning into phase-specific documents with strict scope controls to prevent both over-coding and under-coding.

## Roadmap Index

- [Roadmap Governance and Scope Controls](./roadmap_governance.md)
- [V17 — Architecture Stabilization](./V17_architecture_stabilization.md)
- [V18 — D&D Feel Layer 1 (Checks, Stealth, Consequences)](./V18_checks_stealth_consequences.md)
- [V19 — D&D Feel Layer 2 (Resource Attrition & Rest Pressure)](./V19_resource_attrition_rest_pressure.md)
- [V20 — Combat Depth (Reactions, Positioning, Roles)](./V20_combat_depth_reactions_positioning_roles.md)
- [V21 — Class Identity & Non-Combat Magic Expansion](./V21_class_identity_noncombat_magic.md)
- [V22 — Campaign Systems (Faction War, Crafting, Endgame)](./V22_campaign_systems_faction_crafting_endgame.md)
- [V22a — Faction Simulation & Quest Arc Foundation (Implemented)](./V22a_faction_quest_foundation.md)
- [V22b — Crafting & Endgame Foundation (Implemented)](./V22b_crafting_endgame_foundation.md)
- [Merged Roadmap (V19–V22a)](./V19_V22a_merged_roadmap.md)
- [Master Roadmap (Governance + V17–V22a)](./V17_V22a_master_roadmap.md)

## Current Phase

- V21 stabilization is complete.
- V22a closeout is complete.
- V22b closeout is complete.

## How To Use

1. Start with `roadmap_governance.md`.
2. Run one phase at a time unless dependencies are explicitly marked as parallel-safe.
3. Treat each phase's **Out of Scope** list as hard constraints.
4. Do not open coding work until the phase's **Definition of Ready** is complete.

## Suggested Sequencing

- Required sequence: `V17 -> V18 -> V19`.
- Optional parallelization after V19: V20 and V21 can overlap if staffing supports it.
- V22 should start only after V20/V21 stabilization gates pass.

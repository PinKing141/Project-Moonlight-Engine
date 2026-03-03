# System Linkage Gap Audit (Implementation Completeness)

Date: 2026-03-03

Scope: Identify *integration/completeness* gaps (not net-new feature ideas), focused on where existing systems are present but still only partially linked end-to-end.

## 1) World progression still declares unlinked future hooks

`WorldProgression.tick()` currently advances turn, crafting state normalization, cataclysm clock, and faction conflict clock, then leaves an explicit future-hooks marker for NPC schedules, faction AI, and story triggers. This indicates the progression backbone exists, but several intended cross-system links are still not wired into the per-turn pipeline.

## 2) Crafting is wired as a narrow bridge path, not a broad systemic loop

Downtime routing applies deterministic crafting outcomes only when the selected activity ID starts with `craft_`. This is a thin coupling seam and implies that broader crafting interactions are not generalized across other systems.

Separately, the dedicated downtime catalog currently includes only two craft entries (`craft_healing_herbs`, `craft_whetstone`) alongside non-crafting activities, reinforcing that crafting is integrated as a constrained slice rather than a fully connected progression/economy loop.

## 3) Faction conflict progression requires pre-activated state

Faction conflict ticking exits early unless `faction_conflict_v1.active` is true and relation data already exists. In practice, this means faction conflict progression does not self-bootstrap from global faction state; another subsystem must seed and activate that envelope first.

## 4) Cataclysm/campaign pressure is foundation-level by design

Roadmap closeout text for V22b explicitly positions this as a foundation pass (deterministic baseline, compact summary surfacing, no major UI expansion), with larger loops intentionally out of scope. This explains why some campaign systems may feel present but not deeply connected in day-to-day play surfaces.

## 5) Documentation signal drift can obscure what is actually complete

The V22 campaign roadmap file declares implementation complete while also saying “Active next roadmap phase”, and repeats V22a as both active and implemented. This inconsistency can make it hard to tell which integrations are fully closed versus still transitional.

## Practical interpretation

If your question is “what is still missing to *link systems together*?”, the primary answer is:

- per-turn orchestration hooks beyond current clocks,
- generalized crafting integration (beyond `craft_` downtime IDs),
- automatic faction-conflict bootstrapping from faction/world context,
- deeper campaign-surface integration beyond compact summaries,
- and roadmap status cleanup so implementation reality is clearer.

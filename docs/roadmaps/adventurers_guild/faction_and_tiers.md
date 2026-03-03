# Adventurers Guild: Faction/Occupation Spec

## Implementation Status Anchor
- Treat Guild as an extension over current faction/conflict systems already in play (`faction_conflict_v1` + quest arc branch metadata v2).
- Reuse existing town/faction surfacing patterns before introducing new presentation flows.
- Keep application contract changes additive only.

## 1) Core Concept
The Adventurers Guild is an **occupation layer**, not a sovereign allegiance. A character may belong to:
- one or more world factions (politics/religion/culture), and
- the Adventurers Guild at the same time.

## 2) Membership Model
- `guild_membership_status`: `none | provisional | active | suspended | expelled`
- `guild_rank_tier`: `bronze | silver | gold | diamond | platinum`
- `guild_role_mode`: `solo | party_member | party_leader`
- `guild_reputation`: integer score (global + regional split)
- `guild_merits`: spendable currency for licenses, waivers, and support boons

### Data Contract Constraints
- Version all new payloads (e.g., `guild_v1`) and normalize legacy/empty states.
- Keep unknown enum values fail-safe (default to `none` / `bronze` behavior, never crash).
- Do not duplicate faction standing fields; Guild values augment, not replace.

## 3) Coexistence Rules (Cross-Faction)
1. Guild does not override base faction standing.
2. Faction conflicts can modify Guild contract availability, but never fully block low-tier livelihood quests.
3. Guild reputation is partially portable between regions (e.g., 70% carry-over baseline).
4. Criminal behavior can cause rank suspension independently of faction relations.

### Coexistence Test Checklist
- [ ] Low-tier livelihood contract remains available under hostile faction conditions.
- [ ] Reputation carry-over applies deterministically by configured percentage.
- [ ] Suspension can trigger independently of faction standing.
- [ ] Existing faction view outputs remain backward-compatible.

## 4) Tier System (Bronze → Silver → Gold → Diamond → Platinum)

| Tier | Access | Party Rights | Contract Scope | Failure Penalty |
|---|---|---|---|---|
| Bronze | Entry board + training contracts | Solo + duo (licensed) | Local fetch/explore/escort | Minimal; warning-heavy |
| Silver | Regional board unlocked | Up to 4 party members | Multi-step contracts | Moderate rep loss |
| Gold | High-value board + special commissions | Up to 6 with specialist slots | Crisis chains + elite hunts | Meaningful rep + merit loss |
| Diamond | Command contracts + strategic ops | Multi-party coordination | Region-shaping arcs | Severe rep damage, suspension risk |
| Platinum | Grand charter + high authority calls | Lead mixed guild cells | World-impact campaigns | Potential demotion + expulsion review |

## 5) Promotion Requirements
Promotion checks use all of:
- Completed contracts threshold
- Success ratio over recent N contracts
- Reputation floor (global and regional)
- Conduct score (civilian safety, collateral control)
- Role competency (solo/personal and party leadership milestones)

### Promotion Gate Checklist
- [ ] Promotion policy evaluates all five requirement categories.
- [ ] Failure response returns explicit unmet criteria (no opaque deny).
- [ ] Recent-N window is deterministic and persisted.
- [ ] Promotion/demotion transitions are recorded in rank history.

## 6) Party + Solo Identity
- A player can register as a **solo adventurer** and still temporarily attach to a party contract.
- Party leader certification is unlocked at Silver and strengthened at Gold.
- Diamond/Platinum contracts can enforce mandatory party composition tags (healer, scout, vanguard, arcane).

### Party License Rules (bounded)
- Keep composition tags declarative (data-driven tags, no role AI subsystem).
- Validate composition at accept-time and launch-time only.
- Do not introduce matchmaking or real-time party networking.

## 7) Data/Service Roadmap
- Domain: add Guild membership aggregate and rank progression policy.
- Application: add Guild board/query/accept/turn-in intents.
- Infrastructure: persistence tables for rank history, conduct incidents, and contract licensing.
- Presentation: show rank card, active charter constraints, and promotion checklist.

## Execution Order (anti-clutter)
1. Data contract + normalization (`guild_v1`) with tests.
2. Promotion policy evaluator + deterministic history records.
3. Additive application intents (query/accept/turn-in/check-promotion).
4. Minimal presentation surfacing in existing town/quest views.

## Definition of Ready (slice)
- [ ] Scope statement and player-facing behavior are explicit.
- [ ] Data impact and rollback/fallback are documented.
- [ ] Determinism and contract compatibility risks are identified.
- [ ] Unit + integration test list is defined before coding.

## Definition of Done (slice)
- [ ] Acceptance checks pass for membership, promotion, and suspension paths.
- [ ] In-memory and SQL behavior are parity-tested for Guild fields.
- [ ] Contract docs and references are updated.
- [ ] No unrelated service refactors included.

## 8) Non-Goals (prevent overbuild)
- No real-time multiplayer assumptions.
- No economy overhaul in same phase.
- No rewrite of existing faction engine; only extension points.
- No new standalone UI navigation mode for Guild management.

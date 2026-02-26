from __future__ import annotations

import random

from rpg.application.services.event_bus import EventBus
from rpg.application.services.seed_policy import derive_seed
from rpg.domain.events import TickAdvanced
from rpg.domain.repositories import WorldRepository


class StoryDirector:
    _REL_HISTORY_MAX = 30
    _DEFAULT_FACTIONS = ("wardens", "wild", "undead")
    _STORY_SEED_MAX = 12
    _INJECTION_REPEAT_WINDOW = 6
    _INJECTION_KINDS = ("story_seed", "faction_flashpoint")

    def __init__(
        self,
        world_repo: WorldRepository,
        event_bus: EventBus,
        cadence_turns: int = 3,
    ) -> None:
        self.world_repo = world_repo
        self.event_bus = event_bus
        self.cadence_turns = max(1, int(cadence_turns))

    def register_handlers(self) -> None:
        self.event_bus.subscribe(TickAdvanced, self.on_tick_advanced, priority=60)

    def on_tick_advanced(self, event: TickAdvanced) -> None:
        world = self.world_repo.load_default()
        if world is None:
            return

        narrative = self._world_narrative_state(world)
        tension_before = int(narrative.get("tension_level", 0))
        tension_after = self._calculate_tension(world, tension_before)
        narrative["tension_level"] = tension_after
        self._update_relationship_graph(world, narrative=narrative, turn_after=int(event.turn_after), tension=tension_after)

        should_inject, cadence_seed = self._should_inject(world, event.turn_after, narrative)
        narrative["last_cadence_seed"] = cadence_seed
        narrative["last_checked_turn"] = int(event.turn_after)

        if should_inject:
            kind = self._select_injection_kind(world, narrative=narrative, turn_after=int(event.turn_after), tension=tension_after)
            narrative["last_injection_turn"] = int(event.turn_after)
            self._append_injection_marker(
                narrative,
                turn=int(event.turn_after),
                seed=int(cadence_seed),
                kind=kind,
            )
            if kind == "faction_flashpoint":
                self._inject_faction_flashpoint(world, narrative=narrative, turn_after=int(event.turn_after), seed=int(cadence_seed), tension=tension_after)
            else:
                self._inject_story_seed(world, narrative=narrative, turn_after=int(event.turn_after), seed=int(cadence_seed), tension=tension_after)

        self.world_repo.save(world)

    @staticmethod
    def _world_narrative_state(world) -> dict:
        if not getattr(world, "flags", None):
            world.flags = {}
        state = world.flags.setdefault("narrative", {})
        if not isinstance(state, dict):
            state = {}
            world.flags["narrative"] = state
        return state

    @staticmethod
    def _recent_consequence_count(world, turn_after: int, window: int = 3) -> int:
        rows = world.flags.get("consequences", []) if isinstance(getattr(world, "flags", None), dict) else []
        if not isinstance(rows, list):
            return 0
        lower_bound = int(turn_after) - int(window)
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_turn = int(row.get("turn", -10_000))
            if row_turn >= lower_bound:
                count += 1
        return count

    @staticmethod
    def _recent_flashpoint_pressure(world, turn_after: int, window: int = 4) -> int:
        if not isinstance(getattr(world, "flags", None), dict):
            return 0
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return 0
        rows = narrative.get("flashpoint_echoes", [])
        if not isinstance(rows, list):
            return 0

        lower_bound = int(turn_after) - int(window)
        score = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_turn = int(row.get("turn", -10_000))
            if row_turn < lower_bound:
                continue
            band = str(row.get("severity_band", "moderate"))
            if band == "critical":
                score += 4
            elif band == "high":
                score += 3
            elif band == "moderate":
                score += 2
            else:
                score += 1
        return min(12, int(score))

    def _calculate_tension(self, world, tension_before: int) -> int:
        turn_after = int(getattr(world, "current_turn", 0))
        threat = max(0, int(getattr(world, "threat_level", 0)))
        consequence_pressure = self._recent_consequence_count(world, turn_after=turn_after, window=3)
        flashpoint_pressure = self._recent_flashpoint_pressure(world, turn_after=turn_after, window=4)
        target = max(0, min(100, (threat * 8) + (consequence_pressure * 5) + (flashpoint_pressure * 2)))

        if tension_before < target:
            return min(100, tension_before + min(6, target - tension_before))
        if tension_before > target:
            return max(0, tension_before - min(4, tension_before - target))
        return max(0, min(100, tension_before))

    def _should_inject(self, world, turn_after: int, narrative: dict) -> tuple[bool, int]:
        last_injection_turn = int(narrative.get("last_injection_turn", -10_000))
        if int(turn_after) - last_injection_turn < self.cadence_turns:
            return False, 0

        tension = int(narrative.get("tension_level", 0))
        seed = derive_seed(
            namespace="story.cadence",
            context={
                "world_turn": int(turn_after),
                "world_seed": int(getattr(world, "rng_seed", 0)),
                "threat": int(getattr(world, "threat_level", 0)),
                "tension": tension,
            },
        )
        roll = random.Random(seed).randint(1, 100)
        threshold = 35 + min(40, tension // 2)
        return roll <= threshold, seed

    @staticmethod
    def _append_injection_marker(narrative: dict, *, turn: int, seed: int, kind: str) -> None:
        markers = narrative.setdefault("injections", [])
        if not isinstance(markers, list):
            markers = []
            narrative["injections"] = markers
        markers.append(
            {
                "turn": int(turn),
                "seed": int(seed),
                "kind": str(kind),
            }
        )
        if len(markers) > 20:
            del markers[:-20]

    def _inject_story_seed(self, world, *, narrative: dict, turn_after: int, seed: int, tension: int) -> None:
        seeds = self._world_story_seeds(narrative)
        active = [row for row in seeds if isinstance(row, dict) and row.get("status") in {"active", "simmering", "escalated"}]
        if active:
            for row in active:
                current_stage = str(row.get("escalation_stage", "simmering"))
                next_stage = self._next_stage(current_stage=current_stage, tension=tension)
                row["escalation_stage"] = next_stage
                row["last_update_turn"] = int(turn_after)
            return

        faction_bias = self._pick_faction_for_seed(world, seed=seed)
        seed_id = f"seed_{turn_after}_{seed % 10000:04d}"
        seeds.append(
            {
                "seed_id": seed_id,
                "kind": "merchant_under_pressure",
                "status": "active",
                "created_turn": int(turn_after),
                "last_update_turn": int(turn_after),
                "initiator": "broker_silas",
                "motivation": "Protect caravan profits",
                "pressure": "Faction raids on trade routes",
                "opportunity": "Hire local help to secure shipments",
                "escalation_stage": "simmering",
                "escalation_path": [
                    "caravan_delayed",
                    "route_sabotage",
                    "open_trade_conflict",
                ],
                "resolution_variants": [
                    "prosperity",
                    "debt",
                    "faction_shift",
                ],
                "faction_bias": faction_bias,
                "narrative_tags": ["scarcity", "ambition"],
            }
        )
        if len(seeds) > self._STORY_SEED_MAX:
            del seeds[:-self._STORY_SEED_MAX]

    def _inject_faction_flashpoint(self, world, *, narrative: dict, turn_after: int, seed: int, tension: int) -> None:
        seeds = self._world_story_seeds(narrative)
        active = [row for row in seeds if isinstance(row, dict) and row.get("status") in {"active", "simmering", "escalated"}]
        if active:
            for row in active:
                current_stage = str(row.get("escalation_stage", "simmering"))
                next_stage = self._next_stage(current_stage=current_stage, tension=tension)
                row["escalation_stage"] = next_stage
                row["last_update_turn"] = int(turn_after)
            return

        faction_bias = self._pick_faction_for_seed(world, seed=seed)
        seed_id = f"seed_{turn_after}_{seed % 10000:04d}"
        seeds.append(
            {
                "seed_id": seed_id,
                "kind": "faction_flashpoint",
                "status": "active",
                "created_turn": int(turn_after),
                "last_update_turn": int(turn_after),
                "initiator": "captain_ren",
                "motivation": "Stabilize borders",
                "pressure": "Border skirmishes threaten fragile truces",
                "opportunity": "Broker terms before militia escalation",
                "escalation_stage": "simmering",
                "escalation_path": [
                    "patrol_incident",
                    "reprisal_raid",
                    "open_faction_conflict",
                ],
                "resolution_variants": [
                    "prosperity",
                    "debt",
                    "faction_shift",
                ],
                "faction_bias": faction_bias,
                "narrative_tags": ["rivalry", "power"],
            }
        )
        if len(seeds) > self._STORY_SEED_MAX:
            del seeds[:-self._STORY_SEED_MAX]

    def _select_injection_kind(self, world, *, narrative: dict, turn_after: int, tension: int) -> str:
        imbalance = self._faction_imbalance(narrative)
        recent_tags = self._recent_story_tags(narrative, limit=4)

        story_weight = 55
        flashpoint_weight = 45

        if tension >= 45:
            flashpoint_weight += 15
        if imbalance >= 12:
            flashpoint_weight += 15
        if "scarcity" in recent_tags:
            story_weight -= 10
            flashpoint_weight += 10
        if "rivalry" in recent_tags:
            flashpoint_weight -= 10
            story_weight += 10

        story_weight = max(10, int(story_weight))
        flashpoint_weight = max(10, int(flashpoint_weight))

        kind_seed = derive_seed(
            namespace="story.injection.kind",
            context={
                "world_turn": int(turn_after),
                "world_seed": int(getattr(world, "rng_seed", 0)),
                "threat": int(getattr(world, "threat_level", 0)),
                "tension": int(tension),
                "imbalance": int(imbalance),
                "tag_count": len(recent_tags),
            },
        )
        roll = random.Random(kind_seed).randrange(story_weight + flashpoint_weight)
        preferred = "story_seed" if roll < story_weight else "faction_flashpoint"
        return self._guard_repetition(narrative, turn_after=int(turn_after), preferred=preferred, guard_seed=int(kind_seed))

    @classmethod
    def _guard_repetition(cls, narrative: dict, *, turn_after: int, preferred: str, guard_seed: int) -> str:
        markers = narrative.get("injections", []) if isinstance(narrative, dict) else []
        if not isinstance(markers, list) or not markers:
            return preferred

        last = markers[-1] if isinstance(markers[-1], dict) else {}
        last_kind = str(last.get("kind", ""))
        last_turn = int(last.get("turn", -10_000))
        if last_kind != preferred:
            return preferred
        if int(turn_after) - last_turn > cls._INJECTION_REPEAT_WINDOW:
            return preferred

        alternatives = [kind for kind in cls._INJECTION_KINDS if kind != preferred]
        if not alternatives:
            return preferred
        rng = random.Random(int(guard_seed) + 17)
        return alternatives[rng.randrange(len(alternatives))]

    @staticmethod
    def _faction_imbalance(narrative: dict) -> int:
        graph = narrative.get("relationship_graph", {}) if isinstance(narrative, dict) else {}
        if not isinstance(graph, dict):
            return 0
        edges = graph.get("faction_edges", {})
        if not isinstance(edges, dict) or not edges:
            return 0
        negative_scores: list[int] = []
        for raw_score in edges.values():
            try:
                score = int(raw_score)
            except Exception:
                continue
            if score < 0:
                negative_scores.append(abs(score))
        return max(negative_scores) if negative_scores else 0

    @staticmethod
    def _recent_story_tags(narrative: dict, *, limit: int) -> list[str]:
        rows = narrative.get("story_seeds", []) if isinstance(narrative, dict) else []
        if not isinstance(rows, list):
            return []
        tags: list[str] = []
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            row_tags = row.get("narrative_tags", [])
            if not isinstance(row_tags, list):
                continue
            for tag in row_tags:
                value = str(tag).strip().lower()
                if value:
                    tags.append(value)
                    if len(tags) >= int(limit):
                        return tags
        return tags

    @staticmethod
    def _world_story_seeds(narrative: dict) -> list[dict]:
        rows = narrative.setdefault("story_seeds", [])
        if not isinstance(rows, list):
            rows = []
            narrative["story_seeds"] = rows
        return rows

    @staticmethod
    def _next_stage(current_stage: str, tension: int) -> str:
        if current_stage == "critical":
            return "critical"
        if tension >= 60:
            return "critical"
        if tension >= 30:
            return "escalated"
        return "simmering"

    def _pick_faction_for_seed(self, world, *, seed: int) -> str:
        narrative = self._world_narrative_state(world)
        graph = self._world_relationship_graph(narrative)
        edges = graph.get("faction_edges", {}) if isinstance(graph, dict) else {}
        if isinstance(edges, dict) and edges:
            most_negative = None
            most_negative_score = 0
            for key, raw_score in edges.items():
                if not isinstance(key, str) or "|" not in key:
                    continue
                try:
                    score = int(raw_score)
                except Exception:
                    continue
                if score < most_negative_score:
                    most_negative_score = score
                    left, right = key.split("|", 1)
                    most_negative = (left, right)
            if most_negative:
                return sorted(list(most_negative))[0]

        factions = sorted(self._DEFAULT_FACTIONS)
        rng = random.Random(seed)
        return factions[rng.randrange(len(factions))]

    def _update_relationship_graph(self, world, *, narrative: dict, turn_after: int, tension: int) -> None:
        graph = self._world_relationship_graph(narrative)
        edges = graph.setdefault("faction_edges", {})
        if not isinstance(edges, dict):
            edges = {}
            graph["faction_edges"] = edges

        for left, right in self._default_faction_pairs():
            key = self._edge_key(left, right)
            edges.setdefault(key, 0)

        affinity = graph.setdefault("npc_faction_affinity", {})
        if not isinstance(affinity, dict):
            affinity = {}
            graph["npc_faction_affinity"] = affinity
        affinity.setdefault("broker_silas", {"wardens": 2, "wild": -1, "undead": -2})
        affinity.setdefault("captain_ren", {"wardens": 5, "wild": -3, "undead": -4})
        affinity.setdefault("innkeeper_mara", {"wardens": 1, "wild": 1, "undead": -1})

        if turn_after % 2 != 0:
            return

        edge_keys = sorted(str(key) for key in edges.keys())
        if not edge_keys:
            return

        seed = derive_seed(
            namespace="story.relationship.tick",
            context={
                "world_turn": int(turn_after),
                "world_seed": int(getattr(world, "rng_seed", 0)),
                "threat": int(getattr(world, "threat_level", 0)),
                "tension": int(tension),
                "edge_count": len(edge_keys),
            },
        )
        rng = random.Random(seed)
        edge_key = edge_keys[rng.randrange(len(edge_keys))]
        delta_pool = [-2, -1, 1, 2]
        if tension < 20:
            delta_pool = [-1, 1]
        delta = delta_pool[rng.randrange(len(delta_pool))]

        previous = int(edges.get(edge_key, 0))
        updated = max(-100, min(100, previous + delta))
        edges[edge_key] = updated

        history = graph.setdefault("history", [])
        if not isinstance(history, list):
            history = []
            graph["history"] = history
        history.append(
            {
                "turn": int(turn_after),
                "edge": edge_key,
                "delta": int(delta),
                "value": int(updated),
                "seed": int(seed),
            }
        )
        if len(history) > self._REL_HISTORY_MAX:
            del history[:-self._REL_HISTORY_MAX]

    @staticmethod
    def _world_relationship_graph(narrative: dict) -> dict:
        graph = narrative.setdefault("relationship_graph", {})
        if not isinstance(graph, dict):
            graph = {}
            narrative["relationship_graph"] = graph
        return graph

    @classmethod
    def _default_faction_pairs(cls) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        factions = sorted(cls._DEFAULT_FACTIONS)
        for left_index, left in enumerate(factions):
            for right in factions[left_index + 1 :]:
                pairs.append((left, right))
        return pairs

    @staticmethod
    def _edge_key(left: str, right: str) -> str:
        ordered = sorted([str(left), str(right)])
        return f"{ordered[0]}|{ordered[1]}"


def register_story_director_handlers(
    event_bus: EventBus,
    world_repo: WorldRepository,
    cadence_turns: int = 3,
) -> StoryDirector:
    director = StoryDirector(world_repo=world_repo, event_bus=event_bus, cadence_turns=cadence_turns)
    director.register_handlers()
    return director

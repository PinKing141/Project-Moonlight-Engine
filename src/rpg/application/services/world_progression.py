from pathlib import Path

from rpg.domain.events import TickAdvanced
from rpg.domain.models.world import World
from rpg.domain.repositories import EntityRepository, WorldRepository
from rpg.application.services.seed_policy import derive_seed
from rpg.infrastructure.world_import.reference_dataset_loader import load_reference_world_dataset
from .event_bus import EventBus


class WorldProgression:
    _REFERENCE_WORLD_DATASET_CACHE: dict[str, object] = {}
    _CATACLYSM_PHASES = ("whispers", "grip_tightens", "map_shrinks", "ruin")
    _CATACLYSM_PHASE_BY_PROGRESS = (
        (24, "whispers"),
        (59, "grip_tightens"),
        (99, "map_shrinks"),
        (100, "ruin"),
    )
    _FACTION_CONFLICT_VERSION = 1
    _CRAFTING_VERSION = 1
    _CRAFTING_PROFESSIONS = ("gathering", "refining", "fieldcraft")

    def __init__(self, world_repo: WorldRepository, entity_repo: EntityRepository, event_bus: EventBus) -> None:
        self.world_repo = world_repo
        self.entity_repo = entity_repo
        self.event_bus = event_bus

    def tick(self, world: World, ticks: int = 1, persist: bool = True) -> None:
        for _ in range(ticks):
            world.advance_turns()
            self._ensure_crafting_state(world)
            self._advance_cataclysm_clock(world)
            self._advance_faction_conflict_clock(world)
            # Future hooks: NPC schedules, faction AI, story triggers
        if persist:
            self.world_repo.save(world)
        self.event_bus.publish(TickAdvanced(turn_after=world.current_turn))

    @staticmethod
    def _faction_stance_for_score(score: int) -> str:
        value = int(score)
        if value >= 4:
            return "allied"
        if value <= -4:
            return "hostile"
        return "neutral"


    @staticmethod
    def _pair_key(left: str, right: str) -> str:
        a = str(left or "").strip().lower()
        b = str(right or "").strip().lower()
        if not a or not b or a == b:
            return ""
        ordered = sorted((a, b))
        return f"{ordered[0]}|{ordered[1]}"

    @classmethod
    def _seed_faction_conflict_relations_from_diplomacy(cls, world: World, existing: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
        if not isinstance(getattr(world, "flags", None), dict):
            return existing
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return existing
        diplomacy = narrative.get("faction_diplomacy", {})
        if not isinstance(diplomacy, dict):
            return existing
        relations = diplomacy.get("relations", {})
        if not isinstance(relations, dict):
            return existing

        seeded = dict(existing)
        world_turn = int(getattr(world, "current_turn", 0) or 0)
        for raw_pair, raw_score in relations.items():
            pair_text = str(raw_pair or "").strip().lower()
            if not pair_text:
                continue
            left, sep, right = pair_text.partition("|")
            pair = cls._pair_key(left, right) if sep else ""
            if not pair:
                continue
            try:
                score = int(raw_score)
            except Exception:
                continue
            score = max(-10, min(10, int(round(score / 10.0))))
            seeded[pair] = {
                "score": int(score),
                "stance": str(cls._faction_stance_for_score(score)),
                "last_updated_turn": int(world_turn),
            }
        return seeded
    @classmethod
    def _ensure_faction_conflict_state(cls, world: World) -> dict:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        row = world.flags.setdefault("faction_conflict_v1", {})
        if not isinstance(row, dict):
            row = {}
            world.flags["faction_conflict_v1"] = row

        row["version"] = int(cls._FACTION_CONFLICT_VERSION)
        row["active"] = bool(row.get("active", False))

        relations = row.get("relations", {})
        if not isinstance(relations, dict):
            relations = {}
        normalized_relations: dict[str, dict[str, object]] = {}
        for raw_pair, raw_payload in relations.items():
            pair = str(raw_pair or "").strip().lower().replace(" ", "")
            if not pair:
                continue
            payload = raw_payload if isinstance(raw_payload, dict) else {}
            try:
                score = int(payload.get("score", 0) or 0)
            except Exception:
                score = 0
            score = max(-10, min(10, int(score)))
            normalized_relations[pair] = {
                "score": int(score),
                "stance": str(cls._faction_stance_for_score(score)),
                "last_updated_turn": int(payload.get("last_updated_turn", 0) or 0),
            }
        normalized_relations = cls._seed_faction_conflict_relations_from_diplomacy(world, normalized_relations)
        row["relations"] = normalized_relations
        if normalized_relations and "active" not in row:
            row["active"] = True
        elif normalized_relations and not bool(row.get("active", False)):
            row["active"] = True
        row["last_tick_turn"] = int(row.get("last_tick_turn", 0) or 0)
        return row

    def _advance_faction_conflict_clock(self, world: World) -> None:
        state = self._ensure_faction_conflict_state(world)
        world_turn = int(getattr(world, "current_turn", 0) or 0)
        if not bool(state.get("active", False)):
            state["last_tick_turn"] = int(world_turn)
            return

        relations = state.get("relations", {})
        if not isinstance(relations, dict) or not relations:
            state["last_tick_turn"] = int(world_turn)
            return

        world_seed = int(getattr(world, "rng_seed", 0) or 0)
        for pair in sorted(relations.keys()):
            payload = relations.get(pair)
            if not isinstance(payload, dict):
                continue
            score_before = max(-10, min(10, int(payload.get("score", 0) or 0)))
            drift_seed = derive_seed(
                namespace="world.faction_conflict.v1.tick",
                context={
                    "world_turn": int(world_turn),
                    "world_seed": int(world_seed),
                    "pair": str(pair),
                    "score_before": int(score_before),
                },
            )
            drift = int(int(drift_seed) % 3) - 1
            score_after = max(-10, min(10, int(score_before) + int(drift)))
            payload["score"] = int(score_after)
            payload["stance"] = str(self._faction_stance_for_score(score_after))
            payload["last_updated_turn"] = int(world_turn)

        state["last_tick_turn"] = int(world_turn)

    @classmethod
    def _ensure_crafting_state(cls, world: World) -> dict:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        row = world.flags.setdefault("crafting_v1", {})
        if not isinstance(row, dict):
            row = {}
            world.flags["crafting_v1"] = row

        row["version"] = int(cls._CRAFTING_VERSION)
        row["active"] = bool(row.get("active", False))

        raw_professions = row.get("professions", {})
        if not isinstance(raw_professions, dict):
            raw_professions = {}
        normalized_professions: dict[str, int] = {}
        for profession in cls._CRAFTING_PROFESSIONS:
            try:
                value = int(raw_professions.get(profession, 0) or 0)
            except Exception:
                value = 0
            normalized_professions[str(profession)] = max(0, min(100, int(value)))
        row["professions"] = normalized_professions

        raw_known = row.get("known_recipes", [])
        known_recipes: list[str] = []
        if isinstance(raw_known, list):
            for value in raw_known:
                recipe_id = str(value or "").strip().lower().replace(" ", "_")
                if recipe_id and recipe_id not in known_recipes:
                    known_recipes.append(recipe_id)
        row["known_recipes"] = known_recipes

        raw_stockpile = row.get("stockpile", {})
        if not isinstance(raw_stockpile, dict):
            raw_stockpile = {}
        normalized_stockpile: dict[str, int] = {}
        for raw_key, raw_qty in raw_stockpile.items():
            item_id = str(raw_key or "").strip().lower().replace(" ", "_")
            if not item_id:
                continue
            try:
                qty = int(raw_qty)
            except Exception:
                qty = 0
            bounded_qty = max(0, min(999, int(qty)))
            if bounded_qty > 0:
                normalized_stockpile[item_id] = int(bounded_qty)
        row["stockpile"] = normalized_stockpile

        row["last_tick_turn"] = int(row.get("last_tick_turn", 0) or 0)
        row["last_craft_turn"] = int(row.get("last_craft_turn", 0) or 0)
        return row

    @classmethod
    def _cataclysm_phase_from_progress(cls, progress: int) -> str:
        bounded = max(0, min(100, int(progress)))
        for threshold, phase in cls._CATACLYSM_PHASE_BY_PROGRESS:
            if bounded <= int(threshold):
                return str(phase)
        return "ruin"

    @classmethod
    def _ensure_cataclysm_state(cls, world: World) -> dict:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        row = world.flags.setdefault("cataclysm_state", {})
        if not isinstance(row, dict):
            row = {}
            world.flags["cataclysm_state"] = row
        return row

    @classmethod
    def _load_reference_world_dataset_cached(cls):
        project_root = Path(__file__).resolve().parents[4]
        reference_dir = project_root / "data" / "reference_world"
        cache_key = str(reference_dir)
        cached = cls._REFERENCE_WORLD_DATASET_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            dataset = load_reference_world_dataset(reference_dir)
        except Exception:
            dataset = None
        cls._REFERENCE_WORLD_DATASET_CACHE[cache_key] = dataset
        return dataset

    @staticmethod
    def _world_cataclysm_focus_biome_slug(world: World) -> str:
        if not isinstance(getattr(world, "flags", None), dict):
            return ""
        root_flags = world.flags
        state = root_flags.get("cataclysm_state", {})
        if isinstance(state, dict):
            focus = str(state.get("focus_biome", "") or "").strip().lower().replace("-", " ")
            if focus:
                return "_".join(part for part in focus.split() if part)
        focus = str(root_flags.get("cataclysm_focus_biome", "") or "").strip().lower().replace("-", " ")
        if not focus:
            return ""
        return "_".join(part for part in focus.split() if part)

    @classmethod
    def _cataclysm_biome_pressure(cls, world: World) -> int:
        dataset = cls._load_reference_world_dataset_cached()
        index = dict(getattr(dataset, "biome_severity_index", {}) or {}) if dataset is not None else {}
        if not index:
            return 50

        focus_slug = cls._world_cataclysm_focus_biome_slug(world)
        if focus_slug and focus_slug in index:
            try:
                return max(0, min(100, int(index[focus_slug])))
            except Exception:
                pass

        values: list[int] = []
        for value in index.values():
            try:
                values.append(max(0, min(100, int(value))))
            except Exception:
                continue
        if not values:
            return 50
        return max(0, min(100, int(round(sum(values) / float(len(values))))))

    def _advance_cataclysm_clock(self, world: World) -> None:
        state = self._ensure_cataclysm_state(world)
        if not bool(state.get("active", False)):
            return

        progress_before = max(0, min(100, int(state.get("progress", 0) or 0)))
        if progress_before >= 100:
            state["phase"] = "ruin"
            state["progress"] = 100
            state["last_advance_turn"] = int(getattr(world, "current_turn", 0) or 0)
            return

        world_turn = int(getattr(world, "current_turn", 0) or 0)
        phase_before = str(state.get("phase", self._cataclysm_phase_from_progress(progress_before)) or "whispers").strip().lower()
        if phase_before not in self._CATACLYSM_PHASES:
            phase_before = self._cataclysm_phase_from_progress(progress_before)

        slowdown_ticks = max(0, int(state.get("slowdown_ticks", 0) or 0))
        rollback_buffer = max(0, int(state.get("rollback_buffer", 0) or 0))

        cadence = {"whispers": 4, "grip_tightens": 3, "map_shrinks": 2, "ruin": 999}.get(phase_before, 3)
        biome_pressure = self._cataclysm_biome_pressure(world)
        if biome_pressure >= 70:
            cadence = max(1, int(cadence) - 1)
        elif biome_pressure <= 30:
            cadence = int(cadence) + 1
        if slowdown_ticks > 0:
            cadence += 2
            slowdown_ticks = max(0, slowdown_ticks - 1)

        started_turn = max(0, int(state.get("started_turn", world_turn) or world_turn))
        elapsed = max(0, int(world_turn) - int(started_turn))
        if int(cadence) <= 0:
            cadence = 1
        should_advance = (elapsed % int(cadence)) == 0

        progress_after = int(progress_before)
        if should_advance:
            step_seed = derive_seed(
                namespace="world.cataclysm.clock",
                context={
                    "world_turn": int(world_turn),
                    "world_seed": int(getattr(world, "rng_seed", 0) or 0),
                    "kind": str(state.get("kind", "") or ""),
                    "phase": str(phase_before),
                    "progress": int(progress_before),
                },
            )
            step = 4 + (int(step_seed) % 5)
            if biome_pressure >= 70:
                step += 1
            elif biome_pressure <= 30:
                step -= 1
            step = max(2, min(10, int(step)))
            progress_after = min(100, int(progress_after) + int(step))

        if rollback_buffer > 0:
            rollback_amount = min(int(rollback_buffer), 12)
            progress_after = max(0, int(progress_after) - int(rollback_amount))
            rollback_buffer = max(0, int(rollback_buffer) - int(rollback_amount))

        phase_after = self._cataclysm_phase_from_progress(progress_after)
        state["progress"] = int(progress_after)
        state["phase"] = str(phase_after)
        state["last_advance_turn"] = int(world_turn)
        state["slowdown_ticks"] = int(slowdown_ticks)
        state["rollback_buffer"] = int(rollback_buffer)

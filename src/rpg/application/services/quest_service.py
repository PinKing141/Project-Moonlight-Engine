from __future__ import annotations

from rpg.application.services.event_bus import EventBus
from rpg.application.services.seed_policy import derive_seed
from rpg.domain.events import MonsterSlain, TickAdvanced
from rpg.domain.models.quest import (
    cataclysm_quest_templates,
    quest_payload_from_template,
    quest_template_objective_kind,
    standard_quest_templates,
)
from rpg.domain.repositories import CharacterRepository, QuestTemplateRepository, WorldRepository


class QuestService:
    QUEST_ID = "first_hunt"
    _QUEST_STATE_VERSION = "quest_state_v2"
    _NOVELTY_HISTORY_KEY = "quest_generation_signature_history"
    _NOVELTY_HISTORY_MAX = 40
    _NOVELTY_RECENT_WINDOW = 12
    _NOVELTY_MIN_SCORE = 0.50
    _NOVELTY_MAX_RETRIES = 3
    _TIER_ORDER = ("bronze", "silver", "gold", "diamond", "platinum")
    _RANK_MAX_TEMPLATE_TIER = {
        "none": "bronze",
        "provisional": "bronze",
        "active": "silver",
        "suspended": "bronze",
        "expelled": "bronze",
        "bronze": "bronze",
        "silver": "silver",
        "gold": "gold",
        "diamond": "diamond",
        "platinum": "platinum",
    }
    _DIFFICULTY_PROFILE = {
        "story": {"reward_multiplier": 0.90, "target_cap": 2},
        "normal": {"reward_multiplier": 1.00, "target_cap": 3},
        "hard": {"reward_multiplier": 1.12, "target_cap": 4},
        "nightmare": {"reward_multiplier": 1.25, "target_cap": 5},
    }
    _REWARD_MULTIPLIER_MIN = 0.80
    _REWARD_MULTIPLIER_MAX = 1.35
    _FAILURE_MODES = (
        "timeout",
        "casualties",
        "item_loss",
        "faction_fallout",
    )
    _TELEMETRY_KEY = "quest_generation_telemetry_v1"
    _TELEMETRY_ALERT_MAX = 24
    _TELEMETRY_RECENT_WINDOW = 20
    _TELEMETRY_REPEAT_ALERT_THRESHOLD = 4
    _NARRATIVE_PATTERNS = (
        "Local scouts report {title} near the {biome} frontier.",
        "A sealed dispatch flags {title} as the next priority contract.",
        "Rumors spread that {title} could shift control of the nearby routes.",
    )
    _ENCOUNTER_AI_PROFILES = {
        "hunt": "aggressive_pursuit",
        "travel": "ambush_and_harass",
        "gather": "zone_denial",
        "deliver": "intercept_routes",
    }

    def __init__(
        self,
        world_repo: WorldRepository,
        character_repo: CharacterRepository,
        event_bus: EventBus,
        quest_template_repo: QuestTemplateRepository | None = None,
    ) -> None:
        self.world_repo = world_repo
        self.character_repo = character_repo
        self.event_bus = event_bus
        self.quest_template_repo = quest_template_repo

    def _standard_templates(self):
        if self.quest_template_repo is None:
            return tuple(standard_quest_templates())
        try:
            rows = self.quest_template_repo.list_templates(include_cataclysm=False)
        except Exception:
            rows = []
        return tuple(rows) if rows else tuple(standard_quest_templates())

    def _cataclysm_templates(self):
        if self.quest_template_repo is None:
            return tuple(cataclysm_quest_templates())
        try:
            rows = self.quest_template_repo.list_templates(include_cataclysm=True)
        except Exception:
            rows = []
        return tuple(rows) if rows else tuple(cataclysm_quest_templates())

    @staticmethod
    def _safe_int(value: object, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)

    @classmethod
    def _tier_index(cls, tier: str) -> int:
        normalized = str(tier or "bronze").strip().lower()
        try:
            return cls._TIER_ORDER.index(normalized)
        except Exception:
            return 0

    @classmethod
    def _template_tier(cls, template) -> str:
        tags = tuple(getattr(template, "tags", ()) or ())
        for tag in tags:
            value = str(tag or "").strip().lower()
            if value.startswith("tier:"):
                candidate = value.split(":", 1)[1].strip().lower()
                if candidate in cls._TIER_ORDER:
                    return candidate

        pushback_tier = cls._safe_int(getattr(template, "pushback_tier", 0), 0)
        if pushback_tier <= 0:
            return "bronze"
        if pushback_tier == 1:
            return "silver"
        if pushback_tier == 2:
            return "gold"
        if pushback_tier == 3:
            return "diamond"
        return "platinum"

    def _resolve_generation_context(self) -> tuple[str, str]:
        try:
            characters = list(self.character_repo.list_all())
        except Exception:
            characters = []
        if not characters:
            return "bronze", "normal"

        primary = sorted(characters, key=lambda item: int(getattr(item, "id", 0) or 0))[0]
        difficulty = str(getattr(primary, "difficulty", "normal") or "normal").strip().lower() or "normal"
        if difficulty not in self._DIFFICULTY_PROFILE:
            difficulty = "normal"

        rank_tier = "bronze"
        flags = getattr(primary, "flags", {})
        if isinstance(flags, dict):
            guild = flags.get("guild", {})
            if isinstance(guild, dict):
                rank_tier = str(guild.get("rank_tier", "bronze") or "bronze").strip().lower() or "bronze"
        if rank_tier not in self._TIER_ORDER:
            rank_tier = "bronze"
        return rank_tier, difficulty

    def _is_template_allowed_for_rank(self, template, *, rank_tier: str) -> bool:
        max_tier = str(self._RANK_MAX_TEMPLATE_TIER.get(rank_tier, rank_tier) or "bronze").strip().lower()
        return self._tier_index(self._template_tier(template)) <= self._tier_index(max_tier)

    def _condition_template_pool(self, templates: tuple, *, rank_tier: str) -> tuple:
        allowed = [template for template in templates if self._is_template_allowed_for_rank(template, rank_tier=rank_tier)]
        if allowed:
            return tuple(allowed)
        if not templates:
            return tuple()

        floor = sorted(templates, key=lambda item: self._tier_index(self._template_tier(item)))[0]
        return (floor,)

    def _condition_rewards_and_target(self, payload: dict[str, object], *, difficulty: str) -> None:
        profile = self._DIFFICULTY_PROFILE.get(difficulty, self._DIFFICULTY_PROFILE["normal"])
        multiplier = float(profile.get("reward_multiplier", 1.0) or 1.0)
        multiplier = max(self._REWARD_MULTIPLIER_MIN, min(self._REWARD_MULTIPLIER_MAX, multiplier))

        base_xp = self._safe_int(payload.get("reward_xp", 0), 0)
        base_money = self._safe_int(payload.get("reward_money", 0), 0)
        scaled_xp = max(1, int(round(float(base_xp) * multiplier)))
        scaled_money = max(0, int(round(float(base_money) * multiplier)))

        min_xp = max(1, int(base_xp * self._REWARD_MULTIPLIER_MIN))
        max_xp = max(min_xp, int(base_xp * self._REWARD_MULTIPLIER_MAX) + 1)
        payload["reward_xp"] = max(min_xp, min(max_xp, scaled_xp))

        min_money = max(0, int(base_money * self._REWARD_MULTIPLIER_MIN))
        max_money = max(min_money, int(base_money * self._REWARD_MULTIPLIER_MAX) + 1)
        payload["reward_money"] = max(min_money, min(max_money, scaled_money))

        target_cap = max(1, self._safe_int(profile.get("target_cap", 3), 3))
        target = max(1, self._safe_int(payload.get("target", 1), 1))
        payload["target"] = min(target, target_cap)

    def _failure_mode_for_template(self, template, *, difficulty: str, retry_count: int) -> str:
        signature = f"{str(getattr(template, 'slug', ''))}|{difficulty}|{int(retry_count)}"
        mode_index = int(derive_seed(namespace="quest.failure_mode", context={"signature": signature})) % len(
            self._FAILURE_MODES
        )
        return self._FAILURE_MODES[mode_index]

    def _diversified_failure_mode(
        self,
        template,
        *,
        difficulty: str,
        retry_count: int,
        used_modes: set[str],
    ) -> str:
        mode = self._failure_mode_for_template(template, difficulty=difficulty, retry_count=retry_count)
        if mode not in used_modes:
            return mode

        try:
            base_index = self._FAILURE_MODES.index(mode)
        except Exception:
            base_index = 0
        for offset in range(1, len(self._FAILURE_MODES)):
            candidate = self._FAILURE_MODES[(base_index + offset) % len(self._FAILURE_MODES)]
            if candidate not in used_modes:
                return candidate
        return mode

    @classmethod
    def _telemetry_structure(cls) -> dict[str, object]:
        return {
            "version": "quest_generation_telemetry_v1",
            "counters": {
                "family": {},
                "biome": {},
                "antagonist": {},
            },
            "recent": {
                "family": [],
                "biome": [],
                "antagonist": [],
            },
            "alerts": [],
            "tuning": {
                "recent_window": int(cls._TELEMETRY_RECENT_WINDOW),
                "repeat_alert_threshold": int(cls._TELEMETRY_REPEAT_ALERT_THRESHOLD),
                "novelty_recent_window": int(cls._NOVELTY_RECENT_WINDOW),
                "novelty_min_score": float(cls._NOVELTY_MIN_SCORE),
                "novelty_max_retries": int(cls._NOVELTY_MAX_RETRIES),
            },
        }

    @classmethod
    def _ensure_generation_telemetry(cls, world) -> dict[str, object]:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        raw = world.flags.get(cls._TELEMETRY_KEY)
        if not isinstance(raw, dict):
            raw = cls._telemetry_structure()
            world.flags[cls._TELEMETRY_KEY] = raw

        counters = raw.get("counters")
        if not isinstance(counters, dict):
            counters = {}
        for key in ("family", "biome", "antagonist"):
            if not isinstance(counters.get(key), dict):
                counters[key] = {}
        raw["counters"] = counters

        recent = raw.get("recent")
        if not isinstance(recent, dict):
            recent = {}
        for key in ("family", "biome", "antagonist"):
            if not isinstance(recent.get(key), list):
                recent[key] = []
            if len(recent[key]) > cls._TELEMETRY_RECENT_WINDOW:
                recent[key] = recent[key][-cls._TELEMETRY_RECENT_WINDOW :]
        raw["recent"] = recent

        alerts = raw.get("alerts")
        if not isinstance(alerts, list):
            alerts = []
        if len(alerts) > cls._TELEMETRY_ALERT_MAX:
            alerts = alerts[-cls._TELEMETRY_ALERT_MAX :]
        raw["alerts"] = alerts

        tuning = raw.get("tuning")
        if not isinstance(tuning, dict):
            tuning = {}
        tuning.setdefault("recent_window", int(cls._TELEMETRY_RECENT_WINDOW))
        tuning.setdefault("repeat_alert_threshold", int(cls._TELEMETRY_REPEAT_ALERT_THRESHOLD))
        tuning.setdefault("novelty_recent_window", int(cls._NOVELTY_RECENT_WINDOW))
        tuning.setdefault("novelty_min_score", float(cls._NOVELTY_MIN_SCORE))
        tuning.setdefault("novelty_max_retries", int(cls._NOVELTY_MAX_RETRIES))
        raw["tuning"] = tuning

        world.flags[cls._TELEMETRY_KEY] = raw
        return raw

    @staticmethod
    def _template_biome_tag(template) -> str:
        for tag in tuple(getattr(template, "tags", ()) or ()):
            normalized = str(tag or "").strip().lower()
            if normalized.startswith("biome:"):
                return normalized.split(":", 1)[1].strip() or "unknown"
        return "unknown"

    @staticmethod
    def _template_family(template) -> str:
        kind = getattr(getattr(template, "objective", None), "kind", "hunt")
        value = getattr(kind, "value", kind)
        normalized = str(value or "hunt").strip().lower()
        return normalized or "hunt"

    @staticmethod
    def _template_antagonist(template) -> str:
        target = str(getattr(getattr(template, "objective", None), "target_key", "any_hostile") or "any_hostile")
        return target.strip().lower() or "any_hostile"

    @classmethod
    def _append_recent_dimension(cls, telemetry: dict[str, object], *, dimension: str, value: str) -> int:
        recent = telemetry.get("recent", {})
        if not isinstance(recent, dict):
            recent = {}
            telemetry["recent"] = recent
        rows = recent.get(dimension, [])
        if not isinstance(rows, list):
            rows = []
        rows.append(str(value))
        if len(rows) > cls._TELEMETRY_RECENT_WINDOW:
            rows = rows[-cls._TELEMETRY_RECENT_WINDOW :]
        recent[dimension] = rows
        return sum(1 for item in rows if str(item) == str(value))

    @classmethod
    def _increment_counter_dimension(cls, telemetry: dict[str, object], *, dimension: str, value: str) -> int:
        counters = telemetry.get("counters", {})
        if not isinstance(counters, dict):
            counters = {}
            telemetry["counters"] = counters
        bucket = counters.get(dimension, {})
        if not isinstance(bucket, dict):
            bucket = {}
        key = str(value)
        current = int(bucket.get(key, 0) or 0) + 1
        bucket[key] = current
        counters[dimension] = bucket
        return current

    @classmethod
    def _append_telemetry_alert(
        cls,
        telemetry: dict[str, object],
        *,
        dimension: str,
        value: str,
        count: int,
        world_turn: int,
    ) -> None:
        alerts = telemetry.get("alerts", [])
        if not isinstance(alerts, list):
            alerts = []
        existing = next(
            (
                row
                for row in reversed(alerts)
                if isinstance(row, dict)
                and str(row.get("dimension", "")) == str(dimension)
                and str(row.get("value", "")) == str(value)
                and int(row.get("turn", -1) or -1) == int(world_turn)
            ),
            None,
        )
        if existing is not None:
            return
        alerts.append(
            {
                "kind": "repetition_threshold",
                "dimension": str(dimension),
                "value": str(value),
                "count": int(count),
                "turn": int(world_turn),
                "message": f"{str(dimension).title()} '{value}' repeated {int(count)} times in recent window.",
            }
        )
        if len(alerts) > cls._TELEMETRY_ALERT_MAX:
            alerts = alerts[-cls._TELEMETRY_ALERT_MAX :]
        telemetry["alerts"] = alerts

    def _record_generation_telemetry(self, world, *, template, world_turn: int, payload: dict[str, object]) -> None:
        telemetry = self._ensure_generation_telemetry(world)
        family = self._template_family(template)
        biome = self._template_biome_tag(template)
        antagonist = self._template_antagonist(template)

        for dimension, value in (("family", family), ("biome", biome), ("antagonist", antagonist)):
            self._increment_counter_dimension(telemetry, dimension=dimension, value=value)
            repeat_count = self._append_recent_dimension(telemetry, dimension=dimension, value=value)
            if repeat_count >= self._TELEMETRY_REPEAT_ALERT_THRESHOLD:
                self._append_telemetry_alert(
                    telemetry,
                    dimension=dimension,
                    value=value,
                    count=repeat_count,
                    world_turn=world_turn,
                )

        payload["telemetry_family"] = str(family)
        payload["telemetry_biome"] = str(biome)
        payload["telemetry_antagonist"] = str(antagonist)

    @classmethod
    def _ensure_quest_state_schema(cls, world) -> dict[str, object]:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}

        legacy = world.flags.get("quests", {})
        if not isinstance(legacy, dict):
            legacy = {}

        envelope = world.flags.get("quests_v2", {})
        if not isinstance(envelope, dict):
            envelope = {}
        envelope["version"] = cls._QUEST_STATE_VERSION

        contracts = envelope.get("contracts", {})
        if not isinstance(contracts, dict):
            contracts = {}

        if not contracts and legacy:
            for quest_id, payload in legacy.items():
                if isinstance(payload, dict):
                    contracts[str(quest_id)] = payload

        envelope["contracts"] = contracts
        if not isinstance(envelope.get("journal", {}), dict):
            envelope["journal"] = {}
        if not isinstance(envelope.get("history", []), list):
            envelope["history"] = []

        world.flags["quests_v2"] = envelope
        world.flags["quests"] = contracts
        return envelope

    @staticmethod
    def _compose_narrative_payload(
        template,
        *,
        biome: str,
        failure_mode: str,
        world_turn: int,
        difficulty: str,
        seed_value: int,
    ) -> dict[str, str]:
        title = str(getattr(template, "title", getattr(template, "slug", "Contract")) or "Contract").strip()
        patterns = QuestService._NARRATIVE_PATTERNS
        index = int(seed_value) % len(patterns)
        brief = patterns[index].format(title=title, biome=str(biome or "unknown"))
        rumor = f"Town whispers suggest failure may cause {str(failure_mode).replace('_', ' ')}."
        twist = f"Twist at turn {int(world_turn)}: resistance scales for {str(difficulty).title()} crews."
        consequence = f"If unresolved, expect {str(failure_mode).replace('_', ' ')} repercussions in surrounding districts."
        return {
            "narrative_brief": brief,
            "rumor_hook": rumor,
            "twist_hint": twist,
            "consequence_preview": consequence,
        }

    def _encounter_strategy_hint(self, template, *, difficulty: str, failure_mode: str) -> tuple[str, str]:
        family = self._template_family(template)
        profile = self._ENCOUNTER_AI_PROFILES.get(family, "adaptive_skirmish")
        strategy = f"{profile}|{str(difficulty)}|counter:{str(failure_mode)}"
        return profile, strategy

    @staticmethod
    def _update_analytics_snapshot(world, *, world_turn: int) -> None:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        telemetry = world.flags.get("quest_generation_telemetry_v1", {})
        if not isinstance(telemetry, dict):
            return

        counters = telemetry.get("counters", {}) if isinstance(telemetry.get("counters", {}), dict) else {}
        top_family = ""
        top_count = 0
        family_counts = counters.get("family", {}) if isinstance(counters.get("family", {}), dict) else {}
        for key, value in family_counts.items():
            current = int(value or 0)
            if current > top_count:
                top_family = str(key)
                top_count = current

        snapshot = {
            "turn": int(world_turn),
            "top_family": str(top_family),
            "top_family_count": int(top_count),
            "alerts_count": len(telemetry.get("alerts", [])) if isinstance(telemetry.get("alerts", []), list) else 0,
            "generated_total": sum(int(v or 0) for v in family_counts.values()) if isinstance(family_counts, dict) else 0,
        }
        trends = telemetry.get("trends", [])
        if not isinstance(trends, list):
            trends = []
        trends.append(snapshot)
        if len(trends) > 30:
            trends = trends[-30:]
        telemetry["trends"] = trends
        telemetry["analytics_export"] = {
            "schema_version": "quest_generation_analytics_v1",
            "latest_turn": int(world_turn),
            "latest_snapshot": snapshot,
        }
        world.flags["quest_generation_telemetry_v1"] = telemetry

    def register_handlers(self) -> None:
        self.event_bus.subscribe(TickAdvanced, self.on_tick_advanced, priority=20)
        self.event_bus.subscribe(MonsterSlain, self.on_monster_slain, priority=20)

    def on_tick_advanced(self, event: TickAdvanced) -> None:
        world = self.world_repo.load_default()
        if world is None:
            return

        if not isinstance(world.flags, dict):
            world.flags = {}

        self._ensure_quest_state_schema(world)

        quests = world.flags.setdefault("quests", {})
        for quest_id, quest in quests.items():
            if not isinstance(quest, dict) or quest.get("status") != "active":
                continue
            expires_turn = int(quest.get("expires_turn", event.turn_after + 1))
            if event.turn_after <= expires_turn:
                continue
            quest["status"] = "failed"
            quest["failed_turn"] = event.turn_after
            quest["failed_reason"] = "expired"
            self._append_consequence(
                world,
                message=f"You failed to finish {str(quest_id).replace('_', ' ').title()} in time.",
                kind="quest_expired",
                turn=event.turn_after,
            )

        if event.turn_after < 1:
            self.world_repo.save(world)
            return

        if self._is_cataclysm_active(world):
            self._sync_cataclysm_templates(world=world, quests=quests, world_turn=int(event.turn_after))
        else:
            self._sync_standard_templates(quests=quests, world_turn=int(event.turn_after))

        for quest in quests.values():
            if not isinstance(quest, dict):
                continue
            if quest.get("status") != "active":
                continue
            if str(quest.get("objective_kind", "")) != "travel_count":
                continue
            progress = int(quest.get("progress", 0))
            target = max(1, int(quest.get("target", 1)))
            progress += 1
            quest["progress"] = min(progress, target)
            if progress >= target:
                quest["status"] = "ready_to_turn_in"
                quest["completed_turn"] = event.turn_after

        self._update_analytics_snapshot(world, world_turn=int(event.turn_after))

        self.world_repo.save(world)

    @staticmethod
    def _is_cataclysm_active(world) -> bool:
        if not isinstance(getattr(world, "flags", None), dict):
            return False
        state = world.flags.get("cataclysm_state", {})
        if not isinstance(state, dict):
            return False
        return bool(state.get("active", False))

    @classmethod
    def _read_signature_history(cls, world) -> list[dict[str, object]]:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        raw = world.flags.setdefault(cls._NOVELTY_HISTORY_KEY, [])
        if not isinstance(raw, list):
            raw = []
            world.flags[cls._NOVELTY_HISTORY_KEY] = raw

        normalized: list[dict[str, object]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            signature = str(item.get("signature", "") or "").strip().lower()
            if not signature:
                continue
            try:
                turn = int(item.get("turn", 0) or 0)
            except Exception:
                turn = 0
            normalized.append({"signature": signature, "turn": turn})

        if len(normalized) > cls._NOVELTY_HISTORY_MAX:
            normalized = normalized[-cls._NOVELTY_HISTORY_MAX :]
        world.flags[cls._NOVELTY_HISTORY_KEY] = list(normalized)
        return normalized

    @classmethod
    def _append_signature_history(cls, world, *, signature: str, world_turn: int) -> None:
        history = cls._read_signature_history(world)
        history.append({"signature": str(signature).strip().lower(), "turn": int(world_turn)})
        if len(history) > cls._NOVELTY_HISTORY_MAX:
            history = history[-cls._NOVELTY_HISTORY_MAX :]
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        world.flags[cls._NOVELTY_HISTORY_KEY] = list(history)

    @classmethod
    def _recent_signatures(cls, world) -> list[str]:
        history = cls._read_signature_history(world)
        recent = history[-cls._NOVELTY_RECENT_WINDOW :]
        return [str(item.get("signature", "") or "").strip().lower() for item in recent if str(item.get("signature", "") or "").strip()]

    @staticmethod
    def _base_signature_for_template(template, *, cataclysm_kind: str = "", cataclysm_phase: str = "") -> str:
        slug = str(getattr(template, "slug", "") or "").strip().lower()
        objective_kind = str(getattr(getattr(template, "objective", None), "kind", "hunt") or "hunt").strip().lower()
        target_key = str(getattr(getattr(template, "objective", None), "target_key", "any_hostile") or "any_hostile").strip().lower()
        tier = int(getattr(template, "pushback_tier", 0) or 0)
        cat_kind = str(cataclysm_kind or "").strip().lower()
        cat_phase = str(cataclysm_phase or "").strip().lower()
        return f"{slug}|{objective_kind}|{target_key}|tier:{tier}|kind:{cat_kind}|phase:{cat_phase}"

    @staticmethod
    def _novelty_score_for_signature(signature: str, *, recent_signatures: list[str]) -> float:
        key = str(signature or "").strip().lower()
        if not key:
            return 0.0
        repeat_count = sum(1 for item in recent_signatures if str(item or "").strip().lower() == key)
        return 1.0 / float(1 + repeat_count)

    def _derive_seed_with_novelty_retries(
        self,
        *,
        namespace: str,
        context: dict[str, object],
        base_signature: str,
        recent_signatures: list[str],
    ) -> tuple[int, str, float, int]:
        best_seed = 0
        best_signature = ""
        best_score = -1.0
        best_retry = 0

        for retry_attempt in range(self._NOVELTY_MAX_RETRIES + 1):
            retry_context = dict(context)
            retry_context["retry_attempt"] = int(retry_attempt)
            seed_value = derive_seed(namespace=f"{namespace}.retry", context=retry_context)
            signature_variant = f"{base_signature}|variant:{int(seed_value) % 4}"
            novelty_score = self._novelty_score_for_signature(signature_variant, recent_signatures=recent_signatures)

            if novelty_score > best_score:
                best_seed = int(seed_value)
                best_signature = signature_variant
                best_score = float(novelty_score)
                best_retry = int(retry_attempt)

            if novelty_score >= self._NOVELTY_MIN_SCORE:
                return int(seed_value), signature_variant, float(novelty_score), int(retry_attempt)

        return int(best_seed), best_signature, max(0.0, float(best_score)), int(best_retry)

    def _sync_standard_templates(self, *, quests: dict, world_turn: int) -> None:
        world = self.world_repo.load_default()
        if world is None:
            return
        recent_signatures = self._recent_signatures(world)
        rank_tier, difficulty = self._resolve_generation_context()
        self._ensure_quest_state_schema(world)

        removable = [
            quest_id
            for quest_id, payload in quests.items()
            if isinstance(payload, dict)
            and bool(payload.get("cataclysm_pushback", False))
            and str(payload.get("status", "")) == "available"
        ]
        for quest_id in removable:
            quests.pop(quest_id, None)

        templates = self._condition_template_pool(self._standard_templates(), rank_tier=rank_tier)
        used_failure_modes: set[str] = set()
        for template in templates:
            quest_id = str(template.slug)
            if not quest_id or quest_id in quests:
                continue
            base_context = {
                "world_turn": int(world_turn),
                "quest_id": quest_id,
                "objective_kind": quest_template_objective_kind(template),
            }
            seed_value, signature, novelty_score, retry_count = self._derive_seed_with_novelty_retries(
                namespace="quest.template",
                context=base_context,
                base_signature=self._base_signature_for_template(template),
                recent_signatures=recent_signatures,
            )
            payload = quest_payload_from_template(template)
            self._condition_rewards_and_target(payload, difficulty=difficulty)
            payload["seed_key"] = f"quest:{quest_id}:{int(seed_value)}"
            payload["signature"] = str(signature)
            payload["novelty_score"] = round(float(novelty_score), 4)
            payload["novelty_retry_count"] = int(retry_count)
            failure_mode = self._diversified_failure_mode(
                template,
                difficulty=difficulty,
                retry_count=retry_count,
                used_modes=used_failure_modes,
            )
            payload["failure_mode"] = failure_mode
            payload["rank_gate"] = str(rank_tier)
            payload["difficulty_profile"] = str(difficulty)
            profile, strategy = self._encounter_strategy_hint(template, difficulty=difficulty, failure_mode=failure_mode)
            payload["encounter_ai_profile_v2"] = profile
            payload["encounter_ai_strategy"] = strategy
            narrative = self._compose_narrative_payload(
                template,
                biome=str(self._template_biome_tag(template)),
                failure_mode=failure_mode,
                world_turn=int(world_turn),
                difficulty=str(difficulty),
                seed_value=int(seed_value),
            )
            payload.update(narrative)
            note = str(payload.get("objective_note", "") or "").strip()
            if narrative.get("narrative_brief"):
                payload["objective_note"] = f"{note} {narrative['narrative_brief']}".strip()
            self._record_generation_telemetry(world, template=template, world_turn=int(world_turn), payload=payload)
            quests[quest_id] = payload
            used_failure_modes.add(str(failure_mode))
            self._append_signature_history(world, signature=signature, world_turn=int(world_turn))
            recent_signatures.append(str(signature))

    def _sync_cataclysm_templates(self, *, world, quests: dict, world_turn: int) -> None:
        recent_signatures = self._recent_signatures(world)
        rank_tier, difficulty = self._resolve_generation_context()
        self._ensure_quest_state_schema(world)
        state = world.flags.get("cataclysm_state", {}) if isinstance(world.flags, dict) else {}
        cat_seed = int(state.get("seed", 0) or 0) if isinstance(state, dict) else 0
        kind = str(state.get("kind", "") or "") if isinstance(state, dict) else ""
        phase = str(state.get("phase", "") or "") if isinstance(state, dict) else ""

        removable = [
            quest_id
            for quest_id, payload in quests.items()
            if isinstance(payload, dict)
            and not bool(payload.get("cataclysm_pushback", False))
            and str(payload.get("status", "")) == "available"
        ]
        for quest_id in removable:
            quests.pop(quest_id, None)

        templates = self._condition_template_pool(self._cataclysm_templates(), rank_tier=rank_tier)
        used_failure_modes: set[str] = set()
        for template in templates:
            quest_id = str(template.slug)
            if not quest_id:
                continue
            existing = quests.get(quest_id)
            if isinstance(existing, dict) and str(existing.get("status", "")) in {
                "active",
                "ready_to_turn_in",
                "completed",
                "failed",
            }:
                continue
            base_context = {
                "cataclysm_seed": int(cat_seed),
                "quest_id": quest_id,
                "kind": kind,
                "phase": phase,
            }
            seed_value, signature, novelty_score, retry_count = self._derive_seed_with_novelty_retries(
                namespace="quest.cataclysm.template",
                context=base_context,
                base_signature=self._base_signature_for_template(template, cataclysm_kind=kind, cataclysm_phase=phase),
                recent_signatures=recent_signatures,
            )
            payload = quest_payload_from_template(template, cataclysm_kind=kind, cataclysm_phase=phase)
            self._condition_rewards_and_target(payload, difficulty=difficulty)
            payload["seed_key"] = f"quest:{quest_id}:{int(seed_value)}"
            payload["spawned_turn"] = int(world_turn)
            payload["signature"] = str(signature)
            payload["novelty_score"] = round(float(novelty_score), 4)
            payload["novelty_retry_count"] = int(retry_count)
            failure_mode = self._diversified_failure_mode(
                template,
                difficulty=difficulty,
                retry_count=retry_count,
                used_modes=used_failure_modes,
            )
            payload["failure_mode"] = failure_mode
            payload["rank_gate"] = str(rank_tier)
            payload["difficulty_profile"] = str(difficulty)
            profile, strategy = self._encounter_strategy_hint(template, difficulty=difficulty, failure_mode=failure_mode)
            payload["encounter_ai_profile_v2"] = profile
            payload["encounter_ai_strategy"] = strategy
            narrative = self._compose_narrative_payload(
                template,
                biome=str(self._template_biome_tag(template)),
                failure_mode=failure_mode,
                world_turn=int(world_turn),
                difficulty=str(difficulty),
                seed_value=int(seed_value),
            )
            payload.update(narrative)
            note = str(payload.get("objective_note", "") or "").strip()
            if narrative.get("narrative_brief"):
                payload["objective_note"] = f"{note} {narrative['narrative_brief']}".strip()
            self._record_generation_telemetry(world, template=template, world_turn=int(world_turn), payload=payload)
            quests[quest_id] = payload
            used_failure_modes.add(str(failure_mode))
            self._append_signature_history(world, signature=signature, world_turn=int(world_turn))
            recent_signatures.append(str(signature))

    def on_monster_slain(self, event: MonsterSlain) -> None:
        world = self.world_repo.load_default()
        if world is None or not isinstance(world.flags, dict):
            return

        self._ensure_quest_state_schema(world)

        quests = world.flags.setdefault("quests", {})
        touched = False
        for quest in quests.values():
            if not isinstance(quest, dict):
                continue
            if quest.get("status") != "active":
                continue
            if str(quest.get("objective_kind", "kill_any")) != "kill_any":
                continue

            progress = int(quest.get("progress", 0)) + 1
            target = max(1, int(quest.get("target", 1)))
            quest["progress"] = min(progress, target)
            quest["owner_character_id"] = event.by_character_id
            touched = True

            if progress < target:
                continue

            quest["status"] = "ready_to_turn_in"
            quest["completed_turn"] = event.turn

        if touched:
            self.world_repo.save(world)

    @staticmethod
    def _append_consequence(world, *, message: str, kind: str, turn: int) -> None:
        if not isinstance(world.flags, dict):
            world.flags = {}
        rows = world.flags.setdefault("consequences", [])
        if not isinstance(rows, list):
            rows = []
            world.flags["consequences"] = rows
        rows.append({"message": message, "kind": kind, "turn": int(turn), "severity": "normal"})
        if len(rows) > 20:
            del rows[:-20]


def register_quest_handlers(
    event_bus: EventBus,
    world_repo: WorldRepository | None,
    character_repo: CharacterRepository | None,
    quest_template_repo: QuestTemplateRepository | None = None,
) -> None:
    if world_repo is None or character_repo is None:
        return

    service = QuestService(
        world_repo=world_repo,
        character_repo=character_repo,
        event_bus=event_bus,
        quest_template_repo=quest_template_repo,
    )
    service.register_handlers()

from __future__ import annotations

import json
import random
import os
from pathlib import Path
from typing import Sequence

from rpg.application.services.seed_policy import derive_seed


class DialogueService:
    _DIALOGUE_CONTENT_CACHE: dict[str, dict] = {}
    _DIALOGUE_CONTENT_FILE = "data/world/dialogue_trees.json"
    _MANEUVERS = ("friendly", "direct", "intimidate")
    _STAGES = ("opening", "probe", "resolve")

    @classmethod
    def _dialogue_content_path(cls) -> Path:
        project_root = Path(__file__).resolve().parents[4]
        return project_root / cls._DIALOGUE_CONTENT_FILE

    @classmethod
    def validate_dialogue_content(cls, payload: object) -> list[str]:
        def _validate_variants(*, owner: str, value: object) -> None:
            if value is None:
                return
            if not isinstance(value, list):
                errors.append(f"{owner} must be a list")
                return
            for variant_index, variant in enumerate(value):
                variant_prefix = f"{owner}[{variant_index}]"
                if not isinstance(variant, dict):
                    errors.append(f"{variant_prefix} must be an object")
                    continue
                variant_line = str(variant.get("line", "")).strip()
                if not variant_line:
                    errors.append(f"{variant_prefix}.line is required")
                variant_requires = variant.get("requires", [])
                if not isinstance(variant_requires, list):
                    errors.append(f"{variant_prefix}.requires must be a list")

        errors: list[str] = []
        if not isinstance(payload, dict):
            return ["payload must be an object"]

        npcs = payload.get("npcs")
        if not isinstance(npcs, dict):
            return ["payload.npcs must be an object"]

        allowed_stages = set(cls._STAGES)
        for npc_id, npc_tree in npcs.items():
            npc_key = str(npc_id or "").strip()
            if not npc_key:
                errors.append("npc id cannot be empty")
                continue
            if not isinstance(npc_tree, dict):
                errors.append(f"npcs.{npc_key} must be an object")
                continue
            for stage_id, stage_row in npc_tree.items():
                stage_key = str(stage_id or "").strip().lower()
                if stage_key not in allowed_stages:
                    errors.append(f"npcs.{npc_key}.{stage_id} is not a supported stage")
                    continue
                if not isinstance(stage_row, dict):
                    errors.append(f"npcs.{npc_key}.{stage_key} must be an object")
                    continue
                line = stage_row.get("line", "")
                if not str(line).strip():
                    errors.append(f"npcs.{npc_key}.{stage_key}.line is required")
                _validate_variants(owner=f"npcs.{npc_key}.{stage_key}.variants", value=stage_row.get("variants"))
                choices = stage_row.get("choices", [])
                if not isinstance(choices, list):
                    errors.append(f"npcs.{npc_key}.{stage_key}.choices must be a list")
                    continue
                for idx, choice in enumerate(choices):
                    prefix = f"npcs.{npc_key}.{stage_key}.choices[{idx}]"
                    if not isinstance(choice, dict):
                        errors.append(f"{prefix} must be an object")
                        continue
                    choice_id = str(choice.get("id", "")).strip().lower()
                    label = str(choice.get("label", "")).strip()
                    if not choice_id:
                        errors.append(f"{prefix}.id is required")
                    if not label:
                        errors.append(f"{prefix}.label is required")
                    requires = choice.get("requires", [])
                    if not isinstance(requires, list):
                        errors.append(f"{prefix}.requires must be a list")
                    response = choice.get("response")
                    if response is not None and not str(response).strip():
                        errors.append(f"{prefix}.response must be a non-empty string when provided")
                    _validate_variants(owner=f"{prefix}.response_variants", value=choice.get("response_variants"))
                    effects = choice.get("effects", [])
                    if effects is not None:
                        if not isinstance(effects, list):
                            errors.append(f"{prefix}.effects must be a list")
                        else:
                            for effect_index, effect in enumerate(effects):
                                effect_prefix = f"{prefix}.effects[{effect_index}]"
                                if not isinstance(effect, dict):
                                    errors.append(f"{effect_prefix} must be an object")
                                    continue
                                effect_kind = str(effect.get("kind", "")).strip().lower()
                                if not effect_kind:
                                    errors.append(f"{effect_prefix}.kind is required")
                                    continue
                                trigger = str(effect.get("on", "success")).strip().lower()
                                if trigger not in {"success", "failure", "always"}:
                                    errors.append(f"{effect_prefix}.on must be one of success|failure|always")
                                if effect_kind == "faction_heat_delta":
                                    faction_id = str(effect.get("faction_id", "")).strip().lower()
                                    if not faction_id:
                                        errors.append(f"{effect_prefix}.faction_id is required")
                                    delta = effect.get("delta", None)
                                    try:
                                        int(delta)
                                    except Exception:
                                        errors.append(f"{effect_prefix}.delta must be an integer")
                                elif effect_kind == "narrative_tension_delta":
                                    delta = effect.get("delta", None)
                                    try:
                                        int(delta)
                                    except Exception:
                                        errors.append(f"{effect_prefix}.delta must be an integer")
                                elif effect_kind == "story_seed_state":
                                    status = str(effect.get("status", "")).strip().lower()
                                    escalation_stage = str(effect.get("escalation_stage", "")).strip().lower()
                                    if not status and not escalation_stage:
                                        errors.append(f"{effect_prefix} must include status and/or escalation_stage")
                                    if status and status not in {"active", "simmering", "escalated", "resolved"}:
                                        errors.append(f"{effect_prefix}.status must be one of active|simmering|escalated|resolved")
                                elif effect_kind == "consequence":
                                    message = str(effect.get("message", "")).strip()
                                    if not message:
                                        errors.append(f"{effect_prefix}.message is required")
        return errors

    @classmethod
    def load_dialogue_content_cached(cls) -> dict:
        path = cls._dialogue_content_path()
        cache_key = str(path)
        cached = cls._DIALOGUE_CONTENT_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        payload: dict = {"version": 1, "npcs": {}}
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not cls.validate_dialogue_content(loaded):
                payload = dict(loaded)
        except Exception:
            payload = {"version": 1, "npcs": {}}

        cls._DIALOGUE_CONTENT_CACHE[cache_key] = dict(payload)
        return dict(payload)

    @staticmethod
    def _dialogue_tree_enabled() -> bool:
        return os.getenv("RPG_DIALOGUE_TREE_ENABLED", "0").strip().lower() in {"1", "true", "yes"}

    @staticmethod
    def _contextual_options_enabled() -> bool:
        return os.getenv("RPG_DIALOGUE_CONTEXTUAL_OPTIONS", "0").strip().lower() in {"1", "true", "yes"}

    @staticmethod
    def _character_dialogue_state(character) -> dict:
        flags = getattr(character, "flags", None)
        if not isinstance(flags, dict):
            flags = {}
            character.flags = flags
        row = flags.setdefault("dialogue_state_v1", {})
        if not isinstance(row, dict):
            row = {}
            flags["dialogue_state_v1"] = row
        row.setdefault("version", 1)
        sessions = row.setdefault("npc_sessions", {})
        if not isinstance(sessions, dict):
            sessions = {}
            row["npc_sessions"] = sessions
        return row

    @staticmethod
    def _world_dialogue_state(world) -> dict:
        if not isinstance(getattr(world, "flags", None), dict):
            world.flags = {}
        row = world.flags.setdefault("dialogue_state_v1", {})
        if not isinstance(row, dict):
            row = {}
            world.flags["dialogue_state_v1"] = row
        row.setdefault("version", 1)
        row.setdefault("npc_global", {})
        if not isinstance(row.get("npc_global"), dict):
            row["npc_global"] = {}
        return row

    @staticmethod
    def tension_level(world) -> int:
        if not isinstance(getattr(world, "flags", None), dict):
            return 0
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return 0
        return max(0, min(100, int(narrative.get("tension_level", 0) or 0)))

    @staticmethod
    def _latest_flashpoint(world) -> dict | None:
        if not isinstance(getattr(world, "flags", None), dict):
            return None
        narrative = world.flags.get("narrative", {})
        if not isinstance(narrative, dict):
            return None
        rows = narrative.get("flashpoint_echoes", [])
        if not isinstance(rows, list):
            return None
        for row in reversed(rows):
            if isinstance(row, dict):
                return row
        return None

    @staticmethod
    def has_recent_social_rebuff(world, npc_id: str, current_turn: int, window: int = 6) -> bool:
        if not isinstance(getattr(world, "flags", None), dict):
            return False
        social = world.flags.get("npc_social", {})
        if not isinstance(social, dict):
            return False
        npc_row = social.get(str(npc_id), {})
        if not isinstance(npc_row, dict):
            return False
        memory = npc_row.get("memory", [])
        if not isinstance(memory, list):
            return False
        lower = int(current_turn) - int(window)
        for event in reversed(memory):
            if not isinstance(event, dict):
                continue
            turn = int(event.get("turn", -10_000) or -10_000)
            if turn < lower:
                break
            if bool(event.get("success", True)):
                continue
            return True
        return False

    @staticmethod
    def _has_recent_rumour(world, character_id: int) -> bool:
        if not isinstance(getattr(world, "flags", None), dict):
            return False
        rows = world.flags.get("rumour_history", [])
        if not isinstance(rows, list) or not rows:
            return False
        target = int(character_id)
        for row in reversed(rows[-6:]):
            if not isinstance(row, dict):
                continue
            if int(row.get("character_id", -1) or -1) == target:
                return True
        return False

    def contextualize_interaction(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        greeting: str,
        approaches: Sequence[str],
    ) -> tuple[str, list[str]]:
        normalized = [str(item) for item in approaches if str(item).strip()]
        turn = int(getattr(world, "current_turn", 0) or 0)
        tension = self.tension_level(world)
        latest_flashpoint = self._latest_flashpoint(world)
        contextual_options_enabled = self._contextual_options_enabled()

        if contextual_options_enabled and tension >= 60:
            greeting = f"{greeting} Tension is critical across town." if greeting else "Tension is critical across town."
            normalized.append("Urgent Appeal")

        if contextual_options_enabled and latest_flashpoint is not None:
            normalized.append("Address Flashpoint")

        if contextual_options_enabled and self.has_recent_social_rebuff(world, npc_id=npc_id, current_turn=turn):
            normalized.append("Make Amends")

        unlocks = getattr(character, "flags", {}) if isinstance(getattr(character, "flags", None), dict) else {}
        interaction_unlocks = unlocks.get("interaction_unlocks", {}) if isinstance(unlocks, dict) else {}
        has_intel_unlock = isinstance(interaction_unlocks, dict) and bool(interaction_unlocks.get("intel_leverage"))
        if contextual_options_enabled and has_intel_unlock and self._has_recent_rumour(world, character_id=int(character_id)):
            normalized.append("Leverage Rumour")

        deduped: list[str] = []
        seen: set[str] = set()
        for option in normalized:
            key = option.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(option)
        return greeting, deduped

    @staticmethod
    def _normalize_choice_id(choice_id: str) -> str:
        return str(choice_id or "").strip().lower().replace("_", " ")

    @staticmethod
    def _normalize_label(value: str) -> str:
        token = str(value or "").strip()
        return token if token else "Direct"

    def _session_row(self, *, character, npc_id: str) -> dict:
        state = self._character_dialogue_state(character)
        sessions = state.setdefault("npc_sessions", {})
        if not isinstance(sessions, dict):
            sessions = {}
            state["npc_sessions"] = sessions
        row = sessions.setdefault(str(npc_id), {})
        if not isinstance(row, dict):
            row = {}
            sessions[str(npc_id)] = row
        stage = str(row.get("stage_id", "opening") or "opening").strip().lower()
        if stage not in self._STAGES:
            stage = "opening"
        row["stage_id"] = stage
        return row

    def build_dialogue_session(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        npc_name: str,
        greeting: str,
        approaches: Sequence[str],
    ) -> dict:
        stage_row = self._session_row(character=character, npc_id=str(npc_id))
        stage_id = str(stage_row.get("stage_id", "opening"))

        available_labels = [self._normalize_label(item) for item in approaches if self._normalize_label(item)]
        available_ids = {self._normalize_choice_id(label) for label in available_labels}

        content = self.load_dialogue_content_cached()
        npc_trees = content.get("npcs", {}) if isinstance(content, dict) else {}
        npc_tree = npc_trees.get(str(npc_id), {}) if isinstance(npc_trees, dict) else {}
        content_stage = npc_tree.get(stage_id, {}) if isinstance(npc_tree, dict) else {}
        content_line = str(content_stage.get("line", "")).strip() if isinstance(content_stage, dict) else ""
        content_line_variants = content_stage.get("variants", []) if isinstance(content_stage, dict) else []
        content_choices = content_stage.get("choices", []) if isinstance(content_stage, dict) else []
        selected_line = self._pick_variant_line(
            world=world,
            character=character,
            character_id=int(character_id),
            npc_id=str(npc_id),
            base_line=content_line,
            variants=content_line_variants,
        )

        if isinstance(content_choices, list) and content_choices:
            preferred = [self._normalize_label(str(row.get("label", ""))) for row in content_choices if isinstance(row, dict)]
            preferred = [row for row in preferred if row]
        elif stage_id == "opening":
            preferred = ["Friendly", "Direct", "Intimidate"]
        elif stage_id == "probe":
            preferred = ["Direct", "Friendly", "Intimidate", "Leverage Intel", "Leverage Rumour", "Invoke Faction"]
        else:
            preferred = ["Make Amends", "Address Flashpoint", "Friendly", "Direct", "Intimidate"]

        merged_labels: list[str] = []
        seen: set[str] = set()
        for label in [*preferred, *available_labels]:
            key = self._normalize_choice_id(label)
            if not key or key in seen:
                continue
            seen.add(key)
            merged_labels.append(label)

        choices = []
        for label in merged_labels:
            key = self._normalize_choice_id(label)
            is_available = key in available_ids
            locked_reason = "" if is_available else "Unavailable in current world or relationship state."
            rule = None
            if isinstance(content_choices, list):
                for row in content_choices:
                    if not isinstance(row, dict):
                        continue
                    row_id = self._normalize_choice_id(str(row.get("id", "")))
                    if row_id and row_id == key:
                        rule = row
                        break
            if isinstance(rule, dict):
                requires = rule.get("requires", [])
                req_list = [str(item).strip().lower() for item in requires] if isinstance(requires, list) else []
                req_fail = self._failed_requirements(
                    world=world,
                    character=character,
                    character_id=int(character_id),
                    npc_id=str(npc_id),
                    required=req_list,
                )
                if req_fail:
                    is_available = False
                    locked_reason = self._requirement_reason(req_fail[0])
            choices.append(
                {
                    "choice_id": key,
                    "label": label,
                    "available": bool(is_available),
                    "locked_reason": locked_reason,
                }
            )

        if self._dialogue_tree_enabled():
            stage_prefix = {
                "opening": "[Opening]",
                "probe": "[Probe]",
                "resolve": "[Resolve]",
            }.get(stage_id, "[Opening]")
            line = selected_line if selected_line else greeting
            rendered_greeting = f"{stage_prefix} {line}".strip()
        else:
            rendered_greeting = greeting

        return {
            "npc_id": str(npc_id),
            "npc_name": str(npc_name),
            "stage_id": stage_id,
            "greeting": rendered_greeting,
            "choices": choices,
            "challenge_progress": int(stage_row.get("challenge_progress", 0) or 0),
            "challenge_target": 3,
        }

    def _failed_requirements(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        required: list[str],
    ) -> list[str]:
        if not required:
            return []
        failed: list[str] = []
        for key in required:
            if not self._requirement_satisfied(
                world=world,
                character=character,
                character_id=character_id,
                npc_id=npc_id,
                requirement=str(key).strip().lower(),
            ):
                failed.append(str(key).strip().lower())
        return failed

    def _requirement_satisfied(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        requirement: str,
    ) -> bool:
        if not requirement:
            return True
        turn = int(getattr(world, "current_turn", 0) or 0)
        latest_flashpoint = self._latest_flashpoint(world)
        has_rebuff = self.has_recent_social_rebuff(world, npc_id=npc_id, current_turn=turn)
        has_rumour = self._has_recent_rumour(world, int(character_id))
        unlocks = {}
        if isinstance(getattr(character, "flags", None), dict):
            unlocks = character.flags.get("interaction_unlocks", {})
        has_intel = isinstance(unlocks, dict) and bool(unlocks.get("intel_leverage"))
        has_gold = int(getattr(character, "money", 0) or 0) >= 8
        tension = self.tension_level(world)
        faction_heat = {}
        if isinstance(getattr(character, "flags", None), dict):
            loaded_heat = character.flags.get("faction_heat", {})
            faction_heat = loaded_heat if isinstance(loaded_heat, dict) else {}

        checks = {
            "flashpoint_present": bool(latest_flashpoint is not None),
            "recent_rebuff": bool(has_rebuff),
            "recent_rumour": bool(has_rumour),
            "intel_unlock": bool(has_intel),
            "has_gold_8": bool(has_gold),
            "tension_high": bool(tension >= 60),
            "tension_critical": bool(tension >= 80),
            "tension_low": bool(tension <= 25),
        }

        if requirement in checks:
            return bool(checks[requirement])

        if requirement.startswith("faction_heat_") and requirement.endswith("_high"):
            faction_id = requirement[len("faction_heat_") : -len("_high")]
            if not faction_id:
                return False
            score = int(faction_heat.get(faction_id, 0) or 0)
            return score >= 10

        if requirement.startswith("dominant_faction_"):
            faction_id = requirement[len("dominant_faction_") :]
            if not faction_id:
                return False
            ranked = sorted(
                ((str(key), int(value or 0)) for key, value in faction_heat.items() if str(key).strip()),
                key=lambda row: row[1],
                reverse=True,
            )
            if not ranked:
                return False
            top_name, top_score = ranked[0]
            return top_name == faction_id and top_score > 0

        return True

    @staticmethod
    def _requirement_reason(requirement: str) -> str:
        mapping = {
            "flashpoint_present": "No active flashpoint context right now.",
            "recent_rebuff": "Requires a recent social rebuff with this NPC.",
            "recent_rumour": "Requires recent rumour intelligence.",
            "intel_unlock": "Requires intel leverage training.",
            "has_gold_8": "Requires at least 8 gold.",
            "tension_high": "Requires high civic tension.",
            "tension_critical": "Requires critical civic tension.",
            "tension_low": "Only available when civic tension is low.",
        }
        token = str(requirement).strip().lower()
        if token.startswith("faction_heat_") and token.endswith("_high"):
            faction = token[len("faction_heat_") : -len("_high")].replace("_", " ").strip()
            if faction:
                return f"Requires high heat with {faction}."
        if token.startswith("dominant_faction_"):
            faction = token[len("dominant_faction_") :].replace("_", " ").strip()
            if faction:
                return f"Requires {faction} as your dominant faction pressure."
        return mapping.get(str(requirement), "Unavailable due to unmet requirement.")

    def _pick_variant_line(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        base_line: str,
        variants: object,
    ) -> str:
        selected = str(base_line or "").strip()
        if not isinstance(variants, list):
            return selected
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            requires_raw = variant.get("requires", [])
            requires = [str(item).strip().lower() for item in requires_raw] if isinstance(requires_raw, list) else []
            failed = self._failed_requirements(
                world=world,
                character=character,
                character_id=int(character_id),
                npc_id=str(npc_id),
                required=requires,
            )
            if failed:
                continue
            line = str(variant.get("line", "")).strip()
            if line:
                return line
        return selected

    def resolve_dialogue_choice(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        npc_name: str,
        greeting: str,
        approaches: Sequence[str],
        choice_id: str,
    ) -> dict:
        session = self.build_dialogue_session(
            world=world,
            character=character,
            character_id=int(character_id),
            npc_id=str(npc_id),
            npc_name=str(npc_name),
            greeting=str(greeting),
            approaches=approaches,
        )
        choice_key = self._normalize_choice_id(choice_id)
        selected = None
        for row in session.get("choices", []):
            if not isinstance(row, dict):
                continue
            if self._normalize_choice_id(str(row.get("choice_id", ""))) == choice_key:
                selected = row
                break

        if not isinstance(selected, dict):
            return {"approach": "direct", "accepted": False, "reason": "Unknown dialogue choice."}
        if not bool(selected.get("available", False)):
            return {"approach": "direct", "accepted": False, "reason": str(selected.get("locked_reason", "Choice is locked."))}

        stage_id = str(session.get("stage_id", "opening") or "opening").strip().lower()
        content = self.load_dialogue_content_cached()
        npc_trees = content.get("npcs", {}) if isinstance(content, dict) else {}
        npc_tree = npc_trees.get(str(npc_id), {}) if isinstance(npc_trees, dict) else {}
        content_stage = npc_tree.get(stage_id, {}) if isinstance(npc_tree, dict) else {}
        content_choices = content_stage.get("choices", []) if isinstance(content_stage, dict) else []

        choice_response = ""
        choice_effects: list[dict] = []
        if isinstance(content_choices, list):
            for row in content_choices:
                if not isinstance(row, dict):
                    continue
                row_id = self._normalize_choice_id(str(row.get("id", "")))
                if row_id != choice_key:
                    continue
                base_response = str(row.get("response", "")).strip()
                response_variants = row.get("response_variants", [])
                choice_response = self._pick_variant_line(
                    world=world,
                    character=character,
                    character_id=int(character_id),
                    npc_id=str(npc_id),
                    base_line=base_response,
                    variants=response_variants,
                )
                loaded_effects = row.get("effects", [])
                if isinstance(loaded_effects, list):
                    choice_effects = [item for item in loaded_effects if isinstance(item, dict)]
                break

        return {
            "approach": self.normalize_approach(str(selected.get("label", "direct"))),
            "accepted": True,
            "reason": "",
            "response": choice_response,
            "effects": choice_effects,
        }

    @staticmethod
    def normalize_approach(approach: str) -> str:
        token = str(approach or "").strip().lower()
        if token in {"urgent appeal"}:
            return "urgent appeal"
        if token in {"address flashpoint", "flashpoint"}:
            return "address flashpoint"
        if token in {"make amends", "apologize", "apologise"}:
            return "make amends"
        if token in {"leverage rumour", "leverage rumor"}:
            return "leverage rumour"
        return token

    def record_outcome(
        self,
        *,
        world,
        character,
        character_id: int,
        npc_id: str,
        approach: str,
        success: bool,
        world_turn: int,
    ) -> list[str]:
        dialogue_tree_enabled = self._dialogue_tree_enabled()
        if not dialogue_tree_enabled:
            return []

        char_state = self._character_dialogue_state(character)
        world_state = self._world_dialogue_state(world)

        sessions = char_state.setdefault("npc_sessions", {})
        if not isinstance(sessions, dict):
            sessions = {}
            char_state["npc_sessions"] = sessions
        npc_key = str(npc_id)
        session = sessions.setdefault(npc_key, {})
        if not isinstance(session, dict):
            session = {}
            sessions[npc_key] = session

        normalized = self.normalize_approach(approach)
        session["last_turn"] = int(world_turn)
        session["last_approach"] = normalized
        session["last_success"] = bool(success)

        stage = str(session.get("stage_id", "opening") or "opening").strip().lower()
        if stage not in self._STAGES:
            stage = "opening"
        if bool(success):
            if stage == "opening":
                session["stage_id"] = "probe"
            elif stage == "probe":
                session["stage_id"] = "resolve"
            else:
                session["stage_id"] = "opening"
                session["last_resolved_turn"] = int(world_turn)
        else:
            session["stage_id"] = "opening"

        npc_global = world_state.setdefault("npc_global", {})
        if not isinstance(npc_global, dict):
            npc_global = {}
            world_state["npc_global"] = npc_global
        global_row = npc_global.setdefault(npc_key, {})
        if not isinstance(global_row, dict):
            global_row = {}
            npc_global[npc_key] = global_row
        global_row["last_turn"] = int(world_turn)
        global_row["last_approach"] = normalized
        global_row["last_success"] = bool(success)

        notes: list[str] = []
        challenges_enabled = os.getenv("RPG_DIALOGUE_CHALLENGES", "0").strip().lower() in {"1", "true", "yes"}
        progress = int(session.get("challenge_progress", 0) or 0)
        triad_approach = normalized in self._MANEUVERS
        if challenges_enabled and triad_approach:
            seed = derive_seed(
                namespace="dialogue.challenge.sequence",
                context={
                    "character_id": int(character_id),
                    "npc_id": str(npc_id),
                    "world_seed": int(getattr(world, "rng_seed", 0) or 0),
                },
            )
            rng = random.Random(seed)
            sequence = [self._MANEUVERS[rng.randrange(len(self._MANEUVERS))] for _ in range(3)]
            expected = sequence[min(progress, 2)]
            if bool(success) and normalized == expected:
                progress += 1
                session["challenge_progress"] = progress
                notes.append(f"Dialogue challenge progress: {progress}/3.")
                if progress >= 3:
                    session["challenge_progress"] = 0
                    session["challenge_completed_turn"] = int(world_turn)
                    notes.append("Dialogue challenge completed: the NPC recognizes your tactical consistency.")
            else:
                session["challenge_progress"] = 0
                if not success:
                    notes.append("Dialogue challenge reset after a failed maneuver.")
                elif normalized != expected:
                    notes.append("Dialogue challenge reset: wrong maneuver order.")

        return notes

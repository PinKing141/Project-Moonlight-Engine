from __future__ import annotations

from rpg.application.services.seed_policy import derive_seed


class MechanicalFlavourEnricher:
    def __init__(self, lexical_client=None, enabled: bool = False, max_words: int = 8) -> None:
        self.lexical_client = lexical_client
        self.enabled = enabled
        self.max_words = max(1, int(max_words))
        self._cache: dict[str, tuple[str, ...]] = {}

    def _adjectives_for(self, noun: str) -> tuple[str, ...]:
        key = str(noun or "").strip().lower() or "combat"
        if key in self._cache:
            return self._cache[key]
        if not self.enabled or self.lexical_client is None:
            fallback = ("grim", "tense", "volatile", "sudden")
            self._cache[key] = fallback
            return fallback
        try:
            rows = self.lexical_client.related_adjectives(key, max_words=self.max_words)
        except Exception:
            rows = []
        cleaned = tuple(str(item).strip().lower() for item in rows if str(item).strip())
        if not cleaned:
            cleaned = ("grim", "tense", "volatile", "sudden")
        self._cache[key] = cleaned
        return cleaned

    @staticmethod
    def _pick(pool: tuple[str, ...], *, namespace: str, context: dict) -> str:
        if not pool:
            return "tense"
        seed = derive_seed(namespace=namespace, context=context)
        return pool[int(seed) % len(pool)]

    def build_combat_line(
        self,
        *,
        actor: str,
        action: str,
        enemy_kind: str,
        terrain: str,
        round_no: int,
    ) -> str:
        adjectives = self._adjectives_for(enemy_kind)
        picked = self._pick(
            adjectives,
            namespace="flavour.mechanical.combat",
            context={
                "actor": str(actor),
                "action": str(action),
                "enemy_kind": str(enemy_kind),
                "terrain": str(terrain),
                "round_no": int(round_no),
                "pool": adjectives,
            },
        )
        return f"The exchange turns {picked}."

    def build_environment_line(
        self,
        *,
        event_kind: str,
        biome: str,
        hazard_name: str,
        world_turn: int,
    ) -> str:
        adjectives = self._adjectives_for(biome)
        picked = self._pick(
            adjectives,
            namespace="flavour.mechanical.environment",
            context={
                "event_kind": str(event_kind),
                "biome": str(biome),
                "hazard_name": str(hazard_name),
                "world_turn": int(world_turn),
                "pool": adjectives,
            },
        )
        return f"The {hazard_name.lower()} feels {picked}."

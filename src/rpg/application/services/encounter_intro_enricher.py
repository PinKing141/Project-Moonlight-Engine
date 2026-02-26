from rpg.application.services.encounter_flavour import random_intro
from rpg.domain.models.entity import Entity


class EncounterIntroEnricher:
    def __init__(self, lexical_client=None, enabled: bool = False, max_extra_lines: int = 1) -> None:
        self.lexical_client = lexical_client
        self.enabled = enabled
        self.max_extra_lines = max_extra_lines

    def build_intro(self, enemy: Entity) -> str:
        base = random_intro(enemy)
        if not self.enabled or self.max_extra_lines <= 0 or self.lexical_client is None:
            return base

        enemy_kind = str(getattr(enemy, "kind", "creature") or "creature").lower()
        enemy_name = str(getattr(enemy, "name", "foe") or "foe")

        try:
            words = self.lexical_client.related_adjectives(enemy_kind, max_words=8)
        except Exception:
            return base
        if not words:
            return base

        idx = hash(f"{enemy_name}|{enemy_kind}") % len(words)
        adjective = words[idx].strip()
        if not adjective:
            return base

        sentence = f" The moment feels {adjective}."
        return f"{base}{sentence}"

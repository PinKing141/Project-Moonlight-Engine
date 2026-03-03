from __future__ import annotations

from collections.abc import Mapping

from rpg.domain.models.quest import QuestTemplate, cataclysm_quest_templates, standard_quest_templates
from rpg.domain.repositories import QuestTemplateRepository
from rpg.domain.services.quest_template_catalog import build_template_from_payload


class InMemoryQuestTemplateRepository(QuestTemplateRepository):
    def __init__(self, payload_rows: list[Mapping[str, object]] | None = None) -> None:
        self._templates: dict[str, QuestTemplate] = {}
        self.last_warnings: list[str] = []

        if isinstance(payload_rows, list):
            self._load_from_payload_rows(payload_rows)
        else:
            self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        for template in tuple(standard_quest_templates()) + tuple(cataclysm_quest_templates()):
            self._templates[str(template.slug)] = template

    def _load_from_payload_rows(self, payload_rows: list[Mapping[str, object]]) -> None:
        for index, payload in enumerate(payload_rows):
            template, warnings = build_template_from_payload(payload)
            for warning in warnings:
                self.last_warnings.append(f"row:{index} {warning}")
            if template is None:
                continue
            self._templates[str(template.slug)] = template

        if not self._templates:
            self._bootstrap_defaults()

    def get_template(self, template_slug: str) -> QuestTemplate | None:
        key = str(template_slug or "").strip().lower()
        if not key:
            return None
        return self._templates.get(key)

    def list_templates(
        self,
        *,
        include_cataclysm: bool | None = None,
        required_tags: list[str] | None = None,
        forbidden_tags: list[str] | None = None,
    ) -> list[QuestTemplate]:
        required = {str(tag or "").strip().lower() for tag in (required_tags or []) if str(tag or "").strip()}
        forbidden = {str(tag or "").strip().lower() for tag in (forbidden_tags or []) if str(tag or "").strip()}

        rows = sorted(self._templates.values(), key=lambda item: str(item.slug))
        filtered: list[QuestTemplate] = []
        for template in rows:
            if include_cataclysm is not None and bool(template.cataclysm_pushback) != bool(include_cataclysm):
                continue
            template_tags = {str(tag).strip().lower() for tag in tuple(template.tags or ()) if str(tag).strip()}
            if required and not required.issubset(template_tags):
                continue
            if forbidden and template_tags.intersection(forbidden):
                continue
            filtered.append(template)
        return filtered

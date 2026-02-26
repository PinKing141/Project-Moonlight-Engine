from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from rpg.domain.models.feature import Feature
from rpg.domain.repositories import FeatureRepository


class InMemoryFeatureRepository(FeatureRepository):
    def __init__(self, features: Dict[str, Feature] | None = None) -> None:
        self._features_by_slug: Dict[str, Feature] = dict(features or {})
        self._by_character: Dict[int, List[str]] = defaultdict(list)

    def list_for_character(self, character_id: int) -> List[Feature]:
        slugs = self._by_character.get(int(character_id), [])
        items: list[Feature] = []
        for slug in slugs:
            row = self._features_by_slug.get(slug)
            if row is not None:
                items.append(row)
        return items

    def grant_feature_by_slug(self, character_id: int, feature_slug: str) -> bool:
        slug = str(feature_slug or "").strip().lower()
        if not slug or slug not in self._features_by_slug:
            return False
        bucket = self._by_character[int(character_id)]
        if slug in bucket:
            return False
        bucket.append(slug)
        return True

import httpx

from rpg.infrastructure.resilient_http import get_json_with_retry


class DnD5eClient:
    BASE_URL = "https://www.dnd5eapi.co"
    API_PREFIX = "/api/2014"
    SUPPORTED_ENDPOINTS = {
        "ability-scores",
        "alignments",
        "backgrounds",
        "classes",
        "conditions",
        "damage-types",
        "equipment",
        "equipment-categories",
        "feats",
        "features",
        "languages",
        "magic-items",
        "magic-schools",
        "monsters",
        "proficiencies",
        "races",
        "rule-sections",
        "rules",
        "skills",
        "spells",
        "subclasses",
        "subraces",
        "traits",
        "weapon-properties",
    }

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 10.0,
        retries: int = 2,
        backoff_seconds: float = 0.2,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._retries = retries
        self._backoff_seconds = backoff_seconds
        self.client = http_client or httpx.Client(base_url=base_url, timeout=timeout)

    @classmethod
    def _normalize_endpoint(cls, endpoint: str) -> str:
        value = str(endpoint or "").strip().lower().lstrip("/")
        if value not in cls.SUPPORTED_ENDPOINTS:
            allowed = ", ".join(sorted(cls.SUPPORTED_ENDPOINTS))
            raise ValueError(f"Unsupported dnd5e endpoint '{endpoint}'. Allowed values: {allowed}")
        return value

    def get_api_index(self) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}",
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_endpoint(self, endpoint: str, page: int = 1) -> dict:
        normalized = self._normalize_endpoint(endpoint)
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/{normalized}",
            params={"page": page},
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def get_endpoint_resource(self, endpoint: str, resource_slug: str) -> dict:
        normalized = self._normalize_endpoint(endpoint)
        slug = str(resource_slug or "").strip().strip("/")
        if not slug:
            raise ValueError("resource_slug is required")
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/{normalized}/{slug}",
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_monsters(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/monsters",
            params={"page": page},
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def get_monster(self, slug: str) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/monsters/{slug}",
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_spells(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/spells",
            params={"page": page},
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_classes(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/classes",
            params={"page": page},
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_races(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/races",
            params={"page": page},
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def get_race(self, slug: str) -> dict:
        return get_json_with_retry(
            self.client,
            f"{self.API_PREFIX}/races/{slug}",
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def close(self) -> None:
        self.client.close()

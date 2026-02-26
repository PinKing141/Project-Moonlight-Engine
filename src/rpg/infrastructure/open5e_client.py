import httpx

from rpg.infrastructure.resilient_http import get_json_with_retry


class Open5eClient:
    """Lightweight Open5e HTTP client (synchronous, small surface)."""

    BASE_URL = "https://api.open5e.com"

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

    def list_monsters(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            "/monsters/",
            params={"page": page},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def get_monster(self, slug: str) -> dict:
        return get_json_with_retry(
            self.client,
            f"/monsters/{slug}/",
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_spells(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            "/spells/",
            params={"page": page},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_classes(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            "/classes/",
            params={"page": page},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def list_races(self, page: int = 1) -> dict:
        return get_json_with_retry(
            self.client,
            "/races/",
            params={"page": page},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def get_race(self, slug: str) -> dict:
        return get_json_with_retry(
            self.client,
            f"/races/{slug}/",
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )

    def close(self) -> None:
        self.client.close()

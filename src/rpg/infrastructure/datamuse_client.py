import re

import httpx

from rpg.infrastructure.resilient_http import get_json_with_retry


_WORD_RE = re.compile(r"^[a-zA-Z][a-zA-Z\- ]{1,24}$")


class DatamuseClient:
    BASE_URL = "https://api.datamuse.com"

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 2.0,
        retries: int = 1,
        backoff_seconds: float = 0.1,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._retries = retries
        self._backoff_seconds = backoff_seconds
        self.client = http_client or httpx.Client(base_url=base_url, timeout=timeout)

    def related_adjectives(self, noun: str, max_words: int = 8) -> list[str]:
        payload = get_json_with_retry(
            self.client,
            "/words",
            params={"rel_jjb": noun, "max": max_words},
            headers={"Accept": "application/json"},
            retries=self._retries,
            backoff_seconds=self._backoff_seconds,
        )
        rows = payload.get("results", [])
        words: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            word = str(row.get("word", "")).strip()
            if not word:
                continue
            lowered = word.lower()
            if not _WORD_RE.match(lowered):
                continue
            words.append(lowered)
        return words

    def close(self) -> None:
        self.client.close()

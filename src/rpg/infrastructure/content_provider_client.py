from typing import Any, Callable


class FallbackContentClient:
    def __init__(
        self,
        cache,
        primary_client=None,
        fallback_client=None,
        cache_ttl_seconds: int = 86400,
        providers: list[object] | None = None,
    ) -> None:
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds
        if providers is not None:
            self.providers = list(providers)
        else:
            ordered: list[object] = []
            if primary_client is not None:
                ordered.append(primary_client)
            if fallback_client is not None:
                ordered.append(fallback_client)
            self.providers = ordered

        if not self.providers:
            raise ValueError("FallbackContentClient requires at least one provider")

    def _cache_key(self, method_name: str, **kwargs: Any) -> str:
        bits = [method_name]
        for key in sorted(kwargs.keys()):
            bits.append(f"{key}={kwargs[key]}")
        return "content:" + "|".join(bits)

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        return self.cache.get(cache_key, ttl_seconds=self.cache_ttl_seconds)

    def _read_stale_cache(self, cache_key: str) -> dict[str, Any] | None:
        return self.cache.get(cache_key, ttl_seconds=self.cache_ttl_seconds, allow_stale=True)

    def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        try:
            self.cache.set(cache_key, payload)
        except Exception:
            pass

    def _get_with_fallback(
        self,
        method_name: str,
        *,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        cache_key = self._cache_key(method_name, **kwargs)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        fetchers: list[Callable[[], dict[str, Any]]] = []
        for provider in self.providers:
            fetchers.append(lambda provider=provider: getattr(provider, method_name)(**kwargs))

        last_error: Exception | None = None
        for fetch in fetchers:
            try:
                payload = fetch()
                if isinstance(payload, dict):
                    self._write_cache(cache_key, payload)
                    return payload
            except Exception as exc:
                last_error = exc

        stale_payload = self._read_stale_cache(cache_key)
        if stale_payload is not None:
            return stale_payload

        if last_error:
            raise last_error
        return {}

    def list_monsters(self, page: int = 1) -> dict:
        return self._get_with_fallback("list_monsters", kwargs={"page": page})

    def get_monster(self, slug: str) -> dict:
        return self._get_with_fallback("get_monster", kwargs={"slug": slug})

    def list_spells(self, page: int = 1) -> dict:
        return self._get_with_fallback("list_spells", kwargs={"page": page})

    def list_classes(self, page: int = 1) -> dict:
        return self._get_with_fallback("list_classes", kwargs={"page": page})

    def list_magicitems(self, page: int = 1) -> dict:
        return self._get_with_fallback("list_magicitems", kwargs={"page": page})

    def list_races(self, page: int = 1) -> dict:
        return self._get_with_fallback("list_races", kwargs={"page": page})

    def get_race(self, slug: str) -> dict:
        return self._get_with_fallback("get_race", kwargs={"slug": slug})

    def get_api_index(self) -> dict:
        return self._get_with_fallback("get_api_index", kwargs={})

    def list_endpoint(self, endpoint: str, page: int = 1) -> dict:
        return self._get_with_fallback("list_endpoint", kwargs={"endpoint": endpoint, "page": page})

    def get_endpoint_resource(self, endpoint: str, resource_slug: str) -> dict:
        return self._get_with_fallback(
            "get_endpoint_resource",
            kwargs={"endpoint": endpoint, "resource_slug": resource_slug},
        )

    def close(self) -> None:
        for client in self.providers:
            try:
                client.close()
            except Exception:
                pass

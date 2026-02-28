import os

from rpg.infrastructure.content_cache import FileContentCache
from rpg.infrastructure.content_provider_client import FallbackContentClient
from rpg.infrastructure.dnd5e_client import DnD5eClient
from rpg.infrastructure.local_srd_provider import LocalSrdProvider
from rpg.infrastructure.open5e_client import Open5eClient


def _is_truthy(value: str | None, *, default: str = "0") -> bool:
    normalized = str(value if value is not None else default).strip().lower()
    return normalized in {"1", "true", "yes"}


def _base_clients() -> tuple[LocalSrdProvider, DnD5eClient, Open5eClient, FileContentCache, int]:
    timeout = float(os.getenv("RPG_CONTENT_TIMEOUT_S", "10"))
    retries = int(os.getenv("RPG_CONTENT_RETRIES", "2"))
    backoff_seconds = float(os.getenv("RPG_CONTENT_BACKOFF_S", "0.2"))
    cache_ttl_seconds = int(os.getenv("RPG_CONTENT_CACHE_TTL_S", "86400"))
    cache_dir = os.getenv("RPG_CONTENT_CACHE_DIR", ".rpg_cache/content")
    local_dir = os.getenv("RPG_LOCAL_SRD_DIR", "data/srd/2014")
    local_page_size = int(os.getenv("RPG_LOCAL_SRD_PAGE_SIZE", "50"))

    cache = FileContentCache(cache_dir)
    local = LocalSrdProvider(root_dir=local_dir, page_size=local_page_size)
    dnd5e = DnD5eClient(timeout=timeout, retries=retries, backoff_seconds=backoff_seconds)
    open5e = Open5eClient(timeout=timeout, retries=retries, backoff_seconds=backoff_seconds)
    return local, dnd5e, open5e, cache, cache_ttl_seconds


def create_runtime_content_client() -> FallbackContentClient:
    local, dnd5e, open5e, cache, cache_ttl_seconds = _base_clients()
    local_enabled = _is_truthy(os.getenv("RPG_LOCAL_SRD_ENABLED"), default="1")
    runtime_remote_enabled = _is_truthy(os.getenv("RPG_CONTENT_RUNTIME_REMOTE_ENABLED"), default="0")

    providers: list[object] = []
    if local_enabled:
        providers.append(local)
    if runtime_remote_enabled:
        providers.extend([dnd5e, open5e])
    if not providers:
        providers = [local]

    return FallbackContentClient(
        providers=providers,
        cache=cache,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def create_import_content_client() -> FallbackContentClient:
    local, dnd5e, open5e, cache, cache_ttl_seconds = _base_clients()
    include_local = _is_truthy(os.getenv("RPG_IMPORT_INCLUDE_LOCAL_SRD"), default="1")
    providers = [dnd5e, open5e]
    if include_local:
        providers.append(local)

    return FallbackContentClient(
        providers=providers,
        cache=cache,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def create_content_client() -> FallbackContentClient:
    return create_runtime_content_client()


def create_content_client_factory():
    return create_runtime_content_client

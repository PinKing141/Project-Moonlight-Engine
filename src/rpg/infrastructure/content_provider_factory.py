import os

from rpg.infrastructure.content_cache import FileContentCache
from rpg.infrastructure.content_provider_client import FallbackContentClient
from rpg.infrastructure.dnd5e_client import DnD5eClient
from rpg.infrastructure.local_srd_provider import LocalSrdProvider
from rpg.infrastructure.open5e_client import Open5eClient


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
    local_enabled = os.getenv("RPG_LOCAL_SRD_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
    providers = [dnd5e, open5e]
    if local_enabled:
        providers = [local, dnd5e, open5e]

    return FallbackContentClient(
        providers=providers,
        cache=cache,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def create_import_content_client() -> FallbackContentClient:
    local, dnd5e, open5e, cache, cache_ttl_seconds = _base_clients()
    include_local = os.getenv("RPG_IMPORT_INCLUDE_LOCAL_SRD", "1").strip().lower() in {"1", "true", "yes"}
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

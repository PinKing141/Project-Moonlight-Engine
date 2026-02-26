from __future__ import annotations

from typing import Any, Mapping

from rpg.application.services.seed_canonicalizer import hash_seed_payload, serialize_seed_payload

def derive_seed(namespace: str, context: Mapping[str, Any]) -> int:
    serialized = serialize_seed_payload(namespace=namespace, context=context)
    return hash_seed_payload(serialized)

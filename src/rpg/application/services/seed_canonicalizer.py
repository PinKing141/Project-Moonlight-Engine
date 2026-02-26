from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping


def _normalize_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Seed context contains non-finite float value.")
        return float(value)
    if isinstance(value, str):
        return str(value)
    return str(value)


def canonicalize_seed_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): canonicalize_seed_value(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize_seed_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [canonicalize_seed_value(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return _normalize_scalar(value)


def serialize_seed_payload(namespace: str, context: Mapping[str, Any]) -> str:
    payload = {
        "namespace": str(namespace),
        "context": canonicalize_seed_value(context),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def hash_seed_payload(serialized_payload: str) -> int:
    digest = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()
    return int(digest, 16) % (2**32)

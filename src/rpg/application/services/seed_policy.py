from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        normalized = [_normalize(item) for item in value]
        if isinstance(value, set):
            return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return normalized
    return value


def derive_seed(namespace: str, context: Mapping[str, Any]) -> int:
    normalized = _normalize(context)
    payload = {"namespace": namespace, "context": normalized}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return int(digest, 16) % (2**32)

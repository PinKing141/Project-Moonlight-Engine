import json
import os
import time
from hashlib import sha1
from pathlib import Path
from typing import Any


class FileContentCache:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, cache_key: str) -> Path:
        key_hash = sha1(cache_key.encode("utf-8")).hexdigest()
        return self.root_dir / f"{key_hash}.json"

    def set(self, cache_key: str, payload: dict[str, Any]) -> None:
        path = self._path_for_key(cache_key)
        envelope = {
            "stored_at": int(time.time()),
            "payload": payload,
        }
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, path)

    def get(
        self,
        cache_key: str,
        *,
        ttl_seconds: int | None,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        path = self._path_for_key(cache_key)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(envelope, dict):
            return None
        stored_at = envelope.get("stored_at")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            return None
        if allow_stale:
            return payload
        if ttl_seconds is None:
            return payload
        try:
            age_seconds = int(time.time()) - int(stored_at)
        except Exception:
            return None
        if age_seconds <= max(0, int(ttl_seconds)):
            return payload
        return None

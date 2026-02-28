import json
import os
import shutil
import time
from hashlib import sha1
from pathlib import Path
from typing import Any


DEFAULT_CONTENT_DATA_VERSION = "0.1.0"
_MANIFEST_FILENAME = "manifest.json"


class FileContentCache:
    def __init__(self, root_dir: str | Path, *, data_version: str | None = None) -> None:
        self.root_dir = Path(root_dir)
        configured_version = str(data_version or os.getenv("RPG_CONTENT_DATA_VERSION", DEFAULT_CONTENT_DATA_VERSION)).strip()
        self.data_version = configured_version or DEFAULT_CONTENT_DATA_VERSION
        self._manifest_path = self.root_dir / _MANIFEST_FILENAME
        self._ensure_cache_version()

    def _ensure_cache_version(self) -> None:
        manifest_version = self._read_manifest_version()
        if manifest_version == self.data_version and self.root_dir.exists():
            return

        if self.root_dir.exists():
            shutil.rmtree(self.root_dir, ignore_errors=True)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._write_manifest()

    def _read_manifest_version(self) -> str | None:
        if not self._manifest_path.exists():
            return None
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        value = str(payload.get("data_version", "")).strip()
        return value or None

    def _write_manifest(self) -> None:
        envelope = {
            "data_version": self.data_version,
            "updated_at": int(time.time()),
        }
        tmp_path = self._manifest_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_path, self._manifest_path)

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

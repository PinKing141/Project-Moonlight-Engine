import json
from pathlib import Path


class LocalSrdProvider:
    def __init__(self, root_dir: str | Path, page_size: int = 50) -> None:
        self.root_dir = Path(root_dir)
        self.page_size = max(1, int(page_size))
        self._dataset_cache: dict[str, list[dict]] = {}

    def _dataset_path(self, kind: str) -> Path:
        return self.root_dir / f"{kind}.json"

    def _load_rows(self, kind: str) -> list[dict]:
        if kind in self._dataset_cache:
            return self._dataset_cache[kind]

        path = self._dataset_path(kind)
        if not path.exists():
            raise FileNotFoundError(f"Local SRD dataset not found: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            rows = raw.get("results") or raw.get("items") or []
        elif isinstance(raw, list):
            rows = raw
        else:
            rows = []

        normalized = [row for row in rows if isinstance(row, dict)]
        self._dataset_cache[kind] = normalized
        return normalized

    def _paginate(self, rows: list[dict], page: int = 1) -> dict:
        page_num = max(1, int(page))
        start = (page_num - 1) * self.page_size
        end = start + self.page_size
        sliced = rows[start:end]
        has_next = end < len(rows)
        return {
            "count": len(rows),
            "next": f"local://{page_num + 1}" if has_next else None,
            "previous": f"local://{page_num - 1}" if page_num > 1 else None,
            "results": sliced,
        }

    @staticmethod
    def _slugify(value: str) -> str:
        return "-".join(value.strip().lower().split())

    def _get_by_slug(self, kind: str, slug: str) -> dict:
        normalized_slug = self._slugify(slug)
        rows = self._load_rows(kind)
        for row in rows:
            row_slug = row.get("slug") or row.get("index") or self._slugify(str(row.get("name", "")))
            if str(row_slug).strip().lower() == normalized_slug:
                return row
        raise KeyError(f"No {kind} entry for slug={slug}")

    def list_monsters(self, page: int = 1) -> dict:
        return self._paginate(self._load_rows("monsters"), page=page)

    def get_monster(self, slug: str) -> dict:
        return self._get_by_slug("monsters", slug)

    def list_spells(self, page: int = 1) -> dict:
        return self._paginate(self._load_rows("spells"), page=page)

    def list_classes(self, page: int = 1) -> dict:
        return self._paginate(self._load_rows("classes"), page=page)

    def list_magicitems(self, page: int = 1) -> dict:
        try:
            rows = self._load_rows("magicitems")
        except FileNotFoundError:
            rows = self._load_rows("equipment")
        return self._paginate(rows, page=page)

    def list_races(self, page: int = 1) -> dict:
        return self._paginate(self._load_rows("races"), page=page)

    def get_race(self, slug: str) -> dict:
        return self._get_by_slug("races", slug)

    def close(self) -> None:
        return None

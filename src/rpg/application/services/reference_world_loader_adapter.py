from __future__ import annotations

from importlib import import_module
from pathlib import Path


def load_reference_world_dataset_via_adapter(reference_dir: Path):
    module = import_module("rpg.infrastructure.world_import.reference_dataset_loader")
    loader = getattr(module, "load_reference_world_dataset", None)
    if not callable(loader):
        return None
    return loader(reference_dir)

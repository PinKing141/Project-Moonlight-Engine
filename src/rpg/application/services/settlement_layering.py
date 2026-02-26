from __future__ import annotations

import random


_HUMAN_DISTRICTS = (
    "Market Quarter",
    "River Ward",
    "Smiths Row",
    "Lantern Ward",
    "Old Gate",
)
_ELVEN_DISTRICTS = (
    "Canopy Ring",
    "Mooncourt",
    "Whisper Walk",
    "Dawn Terrace",
    "Grove Ward",
)
_DWARVEN_DISTRICTS = (
    "Anvil Tier",
    "Stone Ward",
    "Forge Quarter",
    "Deep Arcade",
    "Ember Walk",
)

_HUMAN_LANDMARKS = (
    "Bell Keep",
    "Pilgrim Arch",
    "Granary Hall",
    "Founders Well",
    "Watch Bastion",
)
_ELVEN_LANDMARKS = (
    "Star Mirror",
    "Song Spire",
    "Glimmer Pool",
    "Wayleaf Court",
    "Silver Bower",
)
_DWARVEN_LANDMARKS = (
    "Hall of Chains",
    "Runic Lift",
    "Oath Forge",
    "Basalt Vault",
    "Hammer Gate",
)


def _culture_key(culture: str | None) -> str:
    value = str(culture or "human").strip().lower()
    if value in {"human", "elven", "dwarven"}:
        return value
    return "human"


def generate_town_layer_tags(*, culture: str, biome: str, scale: str, seed: int) -> tuple[str, str]:
    rng = random.Random(int(seed))
    culture_key = _culture_key(culture)

    districts_by_culture = {
        "human": list(_HUMAN_DISTRICTS),
        "elven": list(_ELVEN_DISTRICTS),
        "dwarven": list(_DWARVEN_DISTRICTS),
    }
    landmarks_by_culture = {
        "human": list(_HUMAN_LANDMARKS),
        "elven": list(_ELVEN_LANDMARKS),
        "dwarven": list(_DWARVEN_LANDMARKS),
    }

    district_pool = districts_by_culture.get(culture_key, list(_HUMAN_DISTRICTS))
    landmark_pool = landmarks_by_culture.get(culture_key, list(_HUMAN_LANDMARKS))

    biome_key = str(biome or "").strip().lower()
    scale_key = str(scale or "town").strip().lower()
    if "mountain" in biome_key and "Stone Ward" in district_pool:
        district_pool = ["Stone Ward", *[item for item in district_pool if item != "Stone Ward"]]
    if "forest" in biome_key and "Grove Ward" in district_pool:
        district_pool = ["Grove Ward", *[item for item in district_pool if item != "Grove Ward"]]
    if scale_key == "city" and "Market Quarter" in district_pool:
        district_pool = ["Market Quarter", *[item for item in district_pool if item != "Market Quarter"]]

    district = district_pool[rng.randrange(len(district_pool))]
    landmark = landmark_pool[rng.randrange(len(landmark_pool))]
    return district, landmark

from __future__ import annotations

import random

AWKWARD_STEAD_CORES = {
    "pass",
    "crossing",
    "mouth",
    "watch",
    "point",
}

OLD_ENGLISH_SUFFIXES = {
    "ton",
    "ham",
    "ford",
    "vale",
    "keep",
    "hold",
    "haven",
    "gate",
    "watch",
    "port",
    "crest",
    "reach",
    "mouth",
    "stead",
    "wick",
    "borough",
    "shire",
    "wall",
    "court",
    "landing",
}

HUMAN_PREFIXES = (
    "Ash", "Black", "White", "Red", "Green", "Grey", "High", "Low", "East", "West",
    "North", "South", "Stone", "Iron", "Silver", "Gold", "Oak", "Thorn", "Raven", "Wolf",
)
HUMAN_CORES = (
    "wood", "field", "brook", "ford", "vale", "ridge", "hill", "marsh", "hollow", "bridge",
    "creek", "cliff", "meadow", "shore", "watch", "point", "crossing", "grove", "barrow", "pass",
)
HUMAN_SUFFIXES = (
    "ton", "ham", "ford", "vale", "keep", "hold", "haven", "gate", "watch", "port",
    "crest", "reach", "mouth", "stead", "wick", "borough", "shire", "wall", "court", "landing",
)

BLENDED_FANTASY_PREFIXES = ("Ael", "Vael", "Myr", "Syl", "Thal", "Kael")
BLENDED_FANTASY_CORES = ("thir", "vael", "myr", "lyth", "dorn", "grim")
BLENDED_FANTASY_SUFFIXES = ("wyn", "heim", "thiel", "delve", "spire", "guard")

ELVEN_PREFIXES = (
    "Ael", "Elar", "Lyth", "Syl", "Fael", "Vaer", "Thael", "Myr", "Cael", "Aer",
    "Ilae", "Nyra", "Elun", "Saer", "Vael", "Thal", "Aerin", "Lorae", "Maer", "Yll",
)
ELVEN_CORES = (
    "thir", "lora", "neth", "sylva", "rael", "veth", "myr", "lyth", "vael", "thalas",
    "elen", "shael", "nor", "aria", "ithil", "nael", "sira", "yll", "riel", "faen",
)
ELVEN_SUFFIXES = (
    "wyn", "riel", "thalas", "lith", "dell", "myr", "vael", "ion", "ara", "thea",
    "sha", "nor", "wynne", "syl", "thir", "arael", "eth", "lora", "aeth", "thiel",
)

DWARVEN_PREFIXES = (
    "Kar", "Dur", "Bar", "Thor", "Grim", "Khaz", "Mor", "Drak", "Bal", "Gor",
    "Thar", "Brom", "Dorn", "Kaz", "Rug", "Harn", "Brak", "Vorg", "Keld", "Storn",
)
DWARVEN_CORES = (
    "grom", "dorn", "khar", "grim", "barak", "thrum", "keld", "vard", "guld", "drak",
    "gran", "morg", "zang", "hold", "mith", "krag", "thuld", "varg", "bron", "rak",
)
DWARVEN_SUFFIXES = (
    "hold", "heim", "forge", "deep", "peak", "vault", "stone", "delve", "hammer", "anvil",
    "guard", "barr", "reach", "cliff", "thane", "shield", "hall", "crest", "mine", "keep",
)


def generate_settlement_name(*, culture: str, seed: int, scale: str = "town") -> str:
    normalized_culture = str(culture or "human").strip().lower()
    normalized_scale = str(scale or "town").strip().lower()
    rng = random.Random(int(seed))

    if normalized_culture == "elven":
        return _build_elven_name(rng=rng, scale=normalized_scale)

    if normalized_culture == "dwarven":
        return _build_dwarven_name(rng=rng, scale=normalized_scale)

    return _build_human_blended_name(
        rng=rng,
        scale=normalized_scale,
    )


def _build_human_blended_name(*, rng: random.Random, scale: str) -> str:
    suffix_probability = {"village": 0.20, "town": 0.42, "city": 0.70}.get(scale, 0.42)

    style_roll = rng.random()
    if style_roll < 0.65:
        prefixes = HUMAN_PREFIXES
        cores = HUMAN_CORES
        suffixes = HUMAN_SUFFIXES
    elif style_roll < 0.83:
        prefixes = HUMAN_PREFIXES + BLENDED_FANTASY_PREFIXES
        cores = HUMAN_CORES
        suffixes = HUMAN_SUFFIXES
    elif style_roll < 0.93:
        prefixes = HUMAN_PREFIXES
        cores = HUMAN_CORES + BLENDED_FANTASY_CORES
        suffixes = HUMAN_SUFFIXES
    else:
        prefixes = HUMAN_PREFIXES
        cores = HUMAN_CORES
        suffixes = HUMAN_SUFFIXES + BLENDED_FANTASY_SUFFIXES

    return _build_name(
        rng=rng,
        culture="human",
        prefixes=prefixes,
        cores=cores,
        suffixes=suffixes,
        suffix_probability=suffix_probability,
    )


def _build_elven_name(*, rng: random.Random, scale: str) -> str:
    return _build_name(
        rng=rng,
        culture="elven",
        prefixes=ELVEN_PREFIXES,
        cores=ELVEN_CORES,
        suffixes=ELVEN_SUFFIXES,
        suffix_probability={"village": 0.35, "town": 0.45, "city": 0.60}.get(scale, 0.45),
    )


def _build_dwarven_name(*, rng: random.Random, scale: str) -> str:
    return _build_name(
        rng=rng,
        culture="dwarven",
        prefixes=DWARVEN_PREFIXES,
        cores=DWARVEN_CORES,
        suffixes=DWARVEN_SUFFIXES,
        suffix_probability={"village": 0.55, "town": 0.70, "city": 0.82}.get(scale, 0.70),
    )


def _build_name(*, rng: random.Random, culture: str, prefixes: tuple[str, ...], cores: tuple[str, ...], suffixes: tuple[str, ...], suffix_probability: float) -> str:
    prefix = rng.choice(prefixes)
    core = rng.choice(cores)
    name = _join_parts(prefix, core)

    if rng.random() <= float(suffix_probability):
        candidate_suffixes = list(suffixes)
        rng.shuffle(candidate_suffixes)
        for suffix in candidate_suffixes:
            if _suffix_is_compatible(culture=culture, stem=name, core=core, suffix=suffix):
                name = _join_parts(name, suffix)
                break

    return _title_case(name)


def _suffix_is_compatible(*, culture: str, stem: str, core: str, suffix: str) -> bool:
    normalized_culture = str(culture or "human").lower()
    normalized_stem = str(stem or "").lower()
    normalized_core = str(core or "").lower()
    normalized_suffix = str(suffix or "").lower()

    if not normalized_suffix:
        return False
    if normalized_suffix == normalized_core:
        return False
    if normalized_suffix == "stead" and (normalized_core in AWKWARD_STEAD_CORES or normalized_stem.endswith("ss")):
        return False
    if normalized_culture == "elven" and normalized_suffix in OLD_ENGLISH_SUFFIXES:
        return False
    return True


def _join_parts(left: str, right: str) -> str:
    a = str(left or "")
    b = str(right or "")
    if not a:
        return b
    if not b:
        return a
    if a[-1].lower() == b[0].lower():
        b = b[1:]
    return f"{a}{b}"


def _title_case(value: str) -> str:
    cleaned = "".join(ch for ch in str(value or "") if ch.isalpha())
    if not cleaned:
        return "Haven"
    return cleaned[0].upper() + cleaned[1:]

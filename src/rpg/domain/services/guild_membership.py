from __future__ import annotations

from dataclasses import dataclass


GUILD_SCHEMA_VERSION = "guild_v1"
GUILD_PROMOTION_POLICY_VERSION = "guild_promotion_v1"
GUILD_REPUTATION_CARRYOVER_BASELINE = 0.70

GUILD_MEMBERSHIP_STATUSES = ("none", "provisional", "active", "suspended", "expelled")
GUILD_RANK_TIERS = ("bronze", "silver", "gold", "diamond", "platinum")
GUILD_ROLE_MODES = ("solo", "party_member", "party_leader")

_STATUS_DEFAULT = "none"
_TIER_DEFAULT = "bronze"
_ROLE_DEFAULT = "solo"

PROMOTION_POLICY_BY_TARGET_TIER: dict[str, dict[str, float | int]] = {
    "silver": {
        "completed_contracts": 6,
        "recent_window": 10,
        "success_ratio": 0.60,
        "global_reputation_floor": 10,
        "regional_reputation_floor": 5,
        "conduct_floor": 45,
        "role_competency_floor": 25,
    },
    "gold": {
        "completed_contracts": 16,
        "recent_window": 12,
        "success_ratio": 0.68,
        "global_reputation_floor": 30,
        "regional_reputation_floor": 15,
        "conduct_floor": 55,
        "role_competency_floor": 45,
    },
    "diamond": {
        "completed_contracts": 30,
        "recent_window": 15,
        "success_ratio": 0.75,
        "global_reputation_floor": 55,
        "regional_reputation_floor": 28,
        "conduct_floor": 65,
        "role_competency_floor": 62,
    },
    "platinum": {
        "completed_contracts": 48,
        "recent_window": 18,
        "success_ratio": 0.82,
        "global_reputation_floor": 85,
        "regional_reputation_floor": 42,
        "conduct_floor": 78,
        "role_competency_floor": 75,
    },
}


@dataclass(frozen=True)
class GuildMembershipState:
    version: str
    membership_status: str
    rank_tier: str
    role_mode: str
    reputation_global: int
    reputation_by_region: dict[str, int]
    merits: int


def _normalize_enum(value: object, allowed: tuple[str, ...], default: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else default


def _normalize_reputation_by_region(value: object) -> tuple[dict[str, int], tuple[str, ...]]:
    warnings: list[str] = []
    if not isinstance(value, dict):
        return {}, tuple(warnings)

    normalized: dict[str, int] = {}
    for raw_region, raw_score in value.items():
        region = str(raw_region or "").strip().lower()
        if not region:
            warnings.append("Ignored empty region key in guild reputation map.")
            continue
        try:
            normalized[region] = int(raw_score)
        except Exception:
            warnings.append(f"Ignored guild regional reputation for '{region}' because value was not an integer.")
    return normalized, tuple(warnings)


def default_guild_membership_state() -> GuildMembershipState:
    return GuildMembershipState(
        version=GUILD_SCHEMA_VERSION,
        membership_status=_STATUS_DEFAULT,
        rank_tier=_TIER_DEFAULT,
        role_mode=_ROLE_DEFAULT,
        reputation_global=0,
        reputation_by_region={},
        merits=0,
    )


def default_guild_membership_payload() -> dict[str, object]:
    default = default_guild_membership_state()
    return {
        "version": default.version,
        "membership_status": default.membership_status,
        "rank_tier": default.rank_tier,
        "role_mode": default.role_mode,
        "reputation_global": default.reputation_global,
        "reputation_by_region": dict(default.reputation_by_region),
        "merits": default.merits,
    }


def normalize_guild_membership_payload(payload: dict[str, object] | None) -> tuple[GuildMembershipState, tuple[str, ...]]:
    warnings: list[str] = []
    raw = payload if isinstance(payload, dict) else {}

    version = str(raw.get("version", "") or "").strip()
    if version != GUILD_SCHEMA_VERSION:
        warnings.append(f"Unknown guild payload version '{version or 'missing'}'; defaulting to {GUILD_SCHEMA_VERSION}.")
        version = GUILD_SCHEMA_VERSION

    membership_status_raw = str(raw.get("membership_status", "") or "").strip().lower()
    membership_status = _normalize_enum(membership_status_raw, GUILD_MEMBERSHIP_STATUSES, _STATUS_DEFAULT)
    if membership_status != membership_status_raw and membership_status_raw:
        warnings.append(
            f"Unknown guild membership status '{membership_status_raw}'; defaulted to '{membership_status}'."
        )

    rank_tier_raw = str(raw.get("rank_tier", "") or "").strip().lower()
    rank_tier = _normalize_enum(rank_tier_raw, GUILD_RANK_TIERS, _TIER_DEFAULT)
    if rank_tier != rank_tier_raw and rank_tier_raw:
        warnings.append(f"Unknown guild rank tier '{rank_tier_raw}'; defaulted to '{rank_tier}'.")

    role_mode_raw = str(raw.get("role_mode", "") or "").strip().lower()
    role_mode = _normalize_enum(role_mode_raw, GUILD_ROLE_MODES, _ROLE_DEFAULT)
    if role_mode != role_mode_raw and role_mode_raw:
        warnings.append(f"Unknown guild role mode '{role_mode_raw}'; defaulted to '{role_mode}'.")

    try:
        reputation_global = int(raw.get("reputation_global", 0) or 0)
    except Exception:
        warnings.append("Guild global reputation was invalid; defaulted to 0.")
        reputation_global = 0

    reputation_by_region, region_warnings = _normalize_reputation_by_region(raw.get("reputation_by_region", {}))
    warnings.extend(region_warnings)

    try:
        merits = int(raw.get("merits", 0) or 0)
    except Exception:
        warnings.append("Guild merits value was invalid; defaulted to 0.")
        merits = 0
    merits = max(0, merits)

    state = GuildMembershipState(
        version=version,
        membership_status=membership_status,
        rank_tier=rank_tier,
        role_mode=role_mode,
        reputation_global=reputation_global,
        reputation_by_region=reputation_by_region,
        merits=merits,
    )
    return state, tuple(warnings)


def normalize_recent_contract_results(results: list[object] | tuple[object, ...] | None, window: int) -> list[bool]:
    if window <= 0:
        return []

    raw_values: list[object] = []
    if isinstance(results, (list, tuple)):
        raw_values = list(results)

    normalized: list[bool] = []
    for value in raw_values:
        if isinstance(value, bool):
            normalized.append(value)
            continue
        text = str(value or "").strip().lower()
        if text in {"1", "true", "success", "pass", "completed"}:
            normalized.append(True)
        elif text in {"0", "false", "fail", "failed", "abandoned"}:
            normalized.append(False)
    if len(normalized) <= window:
        return normalized
    return normalized[-window:]


def next_guild_tier(current_tier: str | None) -> str | None:
    tier = _normalize_enum(current_tier, GUILD_RANK_TIERS, _TIER_DEFAULT)
    index = GUILD_RANK_TIERS.index(tier)
    if index >= len(GUILD_RANK_TIERS) - 1:
        return None
    return GUILD_RANK_TIERS[index + 1]


def portable_reputation_score(score: int, carry_ratio: float = GUILD_REPUTATION_CARRYOVER_BASELINE) -> int:
    ratio = max(0.0, min(1.0, float(carry_ratio)))
    return int(int(score) * ratio)


def evaluate_tier_promotion(
    *,
    current_tier: str | None,
    completed_contracts: int,
    recent_contract_results: list[object] | tuple[object, ...] | None,
    reputation_global: int,
    reputation_by_region: dict[str, int] | None,
    conduct_score: int,
    role_competency_score: int,
) -> dict[str, object]:
    normalized_tier = _normalize_enum(current_tier, GUILD_RANK_TIERS, _TIER_DEFAULT)
    target_tier = next_guild_tier(normalized_tier)
    if target_tier is None:
        return {
            "policy_version": GUILD_PROMOTION_POLICY_VERSION,
            "current_tier": normalized_tier,
            "target_tier": None,
            "eligible": False,
            "unmet_criteria": ("Already at highest tier.",),
            "recent_window_size": 0,
            "recent_sample_size": 0,
            "recent_success_ratio": 1.0,
        }

    policy = PROMOTION_POLICY_BY_TARGET_TIER[target_tier]
    recent_window = int(policy["recent_window"])
    normalized_results = normalize_recent_contract_results(recent_contract_results, recent_window)
    sample_size = len(normalized_results)
    success_ratio = (sum(1 for value in normalized_results if value) / sample_size) if sample_size > 0 else 0.0

    regional_best = 0
    if isinstance(reputation_by_region, dict) and reputation_by_region:
        regional_best = max(int(value) for value in reputation_by_region.values())

    unmet: list[str] = []

    contracts_needed = int(policy["completed_contracts"])
    if int(completed_contracts) < contracts_needed:
        unmet.append(f"Completed contracts {int(completed_contracts)}/{contracts_needed}.")

    ratio_needed = float(policy["success_ratio"])
    if success_ratio < ratio_needed:
        unmet.append(f"Recent success ratio {success_ratio:.2f}/{ratio_needed:.2f} over last {recent_window}.")

    global_needed = int(policy["global_reputation_floor"])
    if int(reputation_global) < global_needed:
        unmet.append(f"Global reputation {int(reputation_global)}/{global_needed}.")

    regional_needed = int(policy["regional_reputation_floor"])
    if int(regional_best) < regional_needed:
        unmet.append(f"Regional reputation peak {int(regional_best)}/{regional_needed}.")

    conduct_needed = int(policy["conduct_floor"])
    if int(conduct_score) < conduct_needed:
        unmet.append(f"Conduct score {int(conduct_score)}/{conduct_needed}.")

    role_needed = int(policy["role_competency_floor"])
    if int(role_competency_score) < role_needed:
        unmet.append(f"Role competency {int(role_competency_score)}/{role_needed}.")

    return {
        "policy_version": GUILD_PROMOTION_POLICY_VERSION,
        "current_tier": normalized_tier,
        "target_tier": target_tier,
        "eligible": len(unmet) == 0,
        "unmet_criteria": tuple(unmet),
        "recent_window_size": recent_window,
        "recent_sample_size": sample_size,
        "recent_success_ratio": success_ratio,
    }
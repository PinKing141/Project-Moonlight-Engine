"""Prewarm content cache via configured providers.

Usage examples:
    python -m rpg.infrastructure.prewarm_content_cache --mode dry-run
    python -m rpg.infrastructure.prewarm_content_cache --mode execute --targets races classes --pages 2
    python -m rpg.infrastructure.prewarm_content_cache --mode execute --strategy import --targets all --pages 1
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from rpg.infrastructure.content_provider_factory import (
    create_import_content_client,
    create_runtime_content_client,
)


TARGET_METHODS = {
    "races": "list_races",
    "classes": "list_classes",
    "spells": "list_spells",
    "monsters": "list_monsters",
}


@dataclass(frozen=True)
class PrewarmCall:
    target: str
    page: int
    method_name: str


@dataclass(frozen=True)
class PrewarmSummary:
    planned: int
    executed: int
    succeeded: int
    failed: int


def normalize_targets(targets: list[str]) -> list[str]:
    lowered = [target.strip().lower() for target in targets if target.strip()]
    if not lowered:
        lowered = ["races", "classes", "spells", "monsters"]
    if "all" in lowered:
        return ["races", "classes", "spells", "monsters"]

    deduped: list[str] = []
    for target in lowered:
        if target not in TARGET_METHODS:
            raise ValueError(f"Unsupported target '{target}'. Choose from: {', '.join(TARGET_METHODS.keys())}, all")
        if target not in deduped:
            deduped.append(target)
    return deduped


def build_prewarm_plan(targets: list[str], pages: int, start_page: int = 1) -> list[PrewarmCall]:
    resolved_targets = normalize_targets(targets)
    page_count = max(1, int(pages))
    first_page = max(1, int(start_page))

    plan: list[PrewarmCall] = []
    for target in resolved_targets:
        method_name = TARGET_METHODS[target]
        for page in range(first_page, first_page + page_count):
            plan.append(PrewarmCall(target=target, page=page, method_name=method_name))
    return plan


def execute_prewarm_plan(client, plan: list[PrewarmCall], dry_run: bool) -> PrewarmSummary:
    if dry_run:
        return PrewarmSummary(planned=len(plan), executed=0, succeeded=0, failed=0)

    executed = 0
    succeeded = 0
    failed = 0
    for call in plan:
        executed += 1
        try:
            method = getattr(client, call.method_name)
            payload = method(page=call.page)
            if isinstance(payload, dict):
                succeeded += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return PrewarmSummary(planned=len(plan), executed=executed, succeeded=succeeded, failed=failed)


def _build_client(strategy: str):
    if strategy == "import":
        return create_import_content_client()
    return create_runtime_content_client()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prewarm content cache through configured providers")
    parser.add_argument("--mode", choices=["dry-run", "execute"], default="dry-run")
    parser.add_argument("--strategy", choices=["runtime", "import"], default="runtime")
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["races", "classes", "spells", "monsters"],
        help="Targets to prewarm: races classes spells monsters all",
    )
    parser.add_argument("--pages", type=int, default=1, help="Number of pages per target to prewarm")
    parser.add_argument("--start-page", type=int, default=1, help="First page index to prewarm")
    args = parser.parse_args()

    plan = build_prewarm_plan(args.targets, pages=args.pages, start_page=args.start_page)

    print(f"Prewarm mode: {args.mode}")
    print(f"Strategy: {args.strategy}")
    print(f"Planned calls: {len(plan)}")
    for call in plan:
        print(f"  - {call.target}: page {call.page} ({call.method_name})")

    if args.mode == "dry-run":
        print("Dry run complete. No provider calls executed.")
        return

    client = _build_client(args.strategy)
    try:
        summary = execute_prewarm_plan(client, plan, dry_run=False)
    finally:
        try:
            client.close()
        except Exception:
            pass

    print(
        f"Prewarm complete: executed={summary.executed}, "
        f"succeeded={summary.succeeded}, failed={summary.failed}."
    )


if __name__ == "__main__":
    main()

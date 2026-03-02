from __future__ import annotations

from collections import Counter

from rpg.domain.models.character import Character
from rpg.domain.models.downtime import DowntimeActivity, DowntimeOutcome


class DowntimeService:
    _ACTIVITIES: tuple[DowntimeActivity, ...] = (
        DowntimeActivity(
            id="craft_healing_herbs",
            title="Craft: Healing Herbs",
            description="Spend a day brewing practical field remedies.",
            days=1,
            gold_cost=4,
            inventory_rewards=("Healing Herbs",),
            reputation_deltas={"wardens": 1},
        ),
        DowntimeActivity(
            id="craft_whetstone",
            title="Craft: Whetstone",
            description="Refine salvaged stone and metal into a weapon whetstone.",
            days=1,
            gold_cost=3,
            inventory_rewards=("Whetstone",),
        ),
        DowntimeActivity(
            id="carouse_contacts",
            title="Carouse Contacts",
            description="Buy rounds, gather rumors, and build low-profile guild ties.",
            days=1,
            gold_cost=6,
            reputation_deltas={"thieves_guild": 2, "the_crown": -1},
        ),
        DowntimeActivity(
            id="research_rituals",
            title="Research Rituals",
            description="Spend quiet library hours researching arcane developments.",
            days=2,
            gold_cost=8,
            inventory_rewards=("Scout Notes",),
            reputation_deltas={"tower_aurelian": 1},
        ),
        DowntimeActivity(
            id="contract_work",
            title="Contract Work",
            description="Take practical guild work to earn coin and local trust.",
            days=1,
            gold_reward=10,
            reputation_deltas={"the_crown": 1},
        ),
    )

    def list_activities(self) -> list[DowntimeActivity]:
        return list(self._ACTIVITIES)

    def get_activity(self, activity_id: str) -> DowntimeActivity | None:
        key = str(activity_id or "").strip().lower()
        return next((row for row in self._ACTIVITIES if row.id == key), None)

    def can_perform(self, *, activity: DowntimeActivity, character: Character) -> tuple[bool, str]:
        cost = int(activity.gold_cost)
        money = int(getattr(character, "money", 0) or 0)
        if money < cost:
            return False, f"Requires {cost} gold."

        if activity.inventory_costs:
            inventory = Counter(str(item) for item in list(getattr(character, "inventory", []) or []))
            for item in activity.inventory_costs:
                if inventory.get(str(item), 0) <= 0:
                    return False, f"Missing required material: {item}."
                inventory[str(item)] -= 1
        return True, ""

    def perform(self, *, activity: DowntimeActivity, character: Character) -> DowntimeOutcome:
        inventory = list(getattr(character, "inventory", []) or [])

        for item in activity.inventory_costs:
            for index, current in enumerate(inventory):
                if str(current) == str(item):
                    inventory.pop(index)
                    break

        for reward in activity.inventory_rewards:
            inventory.append(str(reward))

        gold_delta = int(activity.gold_reward) - int(activity.gold_cost)
        character.money = int(getattr(character, "money", 0) or 0) + gold_delta
        character.inventory = inventory

        lines = [
            f"Downtime complete: {activity.title}.",
            f"Spent {max(0, int(activity.days))} day(s) in settlement.",
        ]
        if gold_delta < 0:
            lines.append(f"Gold spent: {abs(gold_delta)}.")
        elif gold_delta > 0:
            lines.append(f"Gold earned: {gold_delta}.")
        if activity.inventory_rewards:
            lines.append("Gained: " + ", ".join(activity.inventory_rewards) + ".")
        if activity.inventory_costs:
            lines.append("Consumed: " + ", ".join(activity.inventory_costs) + ".")

        return DowntimeOutcome(
            activity_id=activity.id,
            days_spent=max(0, int(activity.days)),
            gold_delta=int(gold_delta),
            inventory_added=tuple(str(item) for item in activity.inventory_rewards),
            inventory_removed=tuple(str(item) for item in activity.inventory_costs),
            reputation_deltas={str(key): int(value) for key, value in activity.reputation_deltas.items()},
            messages=tuple(lines),
        )

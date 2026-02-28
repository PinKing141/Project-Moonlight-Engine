from __future__ import annotations

from typing import Dict, List, Optional

from rpg.domain.models.faction import Faction
from rpg.domain.repositories import FactionRepository

try:
    from rpg.infrastructure.inmemory.generated_taklamakan_faction_flavour import FACTION_DESCRIPTION_OVERRIDES
except Exception:
    FACTION_DESCRIPTION_OVERRIDES = {}


class InMemoryFactionRepository(FactionRepository):
    def __init__(self) -> None:
        self._factions: Dict[str, Faction] = {
            "wild": Faction(id="wild", name="Wild Tribes", influence=2, alignment="chaotic"),
            "undead": Faction(id="undead", name="Restless Dead", influence=3, alignment="evil"),
            "wardens": Faction(id="wardens", name="Emerald Wardens", influence=1, alignment="neutral"),
            "the_crown": Faction(id="the_crown", name="The Crown", influence=4, alignment="lawful"),
            "thieves_guild": Faction(id="thieves_guild", name="The Thieves Guild", influence=3, alignment="chaotic"),
            "arcane_syndicate": Faction(id="arcane_syndicate", name="The Arcane Syndicate", influence=3, alignment="neutral"),
            "tozan_empire": Faction(id="tozan_empire", name="Tozan Empire", influence=5, alignment="lawful"),
            "sarprakelian_khaganate": Faction(
                id="sarprakelian_khaganate",
                name="Sarprakelian Khaganate",
                influence=5,
                alignment="lawful",
            ),
            "kingdom_of_onimydrait": Faction(
                id="kingdom_of_onimydrait",
                name="Kingdom of Onimydrait",
                influence=4,
                alignment="neutral",
            ),
            "kingdom_of_staglenia": Faction(
                id="kingdom_of_staglenia",
                name="Kingdom of Staglenia",
                influence=4,
                alignment="lawful",
            ),
            "vuyurt_khaganate": Faction(
                id="vuyurt_khaganate",
                name="Vuyurt Khaganate",
                influence=4,
                alignment="chaotic",
            ),
            "republic_of_pudrock": Faction(
                id="republic_of_pudrock",
                name="Republic of Pudrock",
                influence=3,
                alignment="neutral",
            ),
            "witnesses_of_elloragh": Faction(
                id="witnesses_of_elloragh",
                name="Witnesses of Elloragh",
                influence=5,
                alignment="lawful",
            ),
            "neverchist_synod": Faction(
                id="neverchist_synod",
                name="Neverchist Synod",
                influence=5,
                alignment="lawful",
            ),
            "ironcoin_syndicate": Faction(
                id="ironcoin_syndicate",
                name="Ironcoin Syndicate",
                influence=4,
                alignment="neutral",
            ),
            "shrouded_athenaeum": Faction(
                id="shrouded_athenaeum",
                name="Shrouded Athenaeum",
                influence=4,
                alignment="neutral",
            ),
            "golden_banner_company": Faction(
                id="golden_banner_company",
                name="Golden Banner Company",
                influence=3,
                alignment="neutral",
            ),
            "blond_spirit_cult": Faction(
                id="blond_spirit_cult",
                name="Blond Spirit Cult",
                influence=2,
                alignment="evil",
            ),
            "crimson_corsairs": Faction(
                id="crimson_corsairs",
                name="Crimson Corsairs",
                influence=3,
                alignment="chaotic",
            ),
            "conclave_council": Faction(
                id="conclave_council",
                name="Arcane Council",
                influence=5,
                alignment="lawful",
                description="The governing body of the arcane towers. They enforce the laws of magic and mediate disputes to prevent arcane war.",
            ),
            "tower_crimson": Faction(
                id="tower_crimson",
                name="Tower of Evocation",
                influence=4,
                alignment="neutral",
                description="Militant evokers specializing in fire, force, and battlefield pressure. They believe magic is a weapon to enforce order.",
            ),
            "tower_cobalt": Faction(
                id="tower_cobalt",
                name="Tower of Enchantment",
                influence=4,
                alignment="neutral",
                description="Mind-focused arcanists dedicated to influence, memory, and disciplined control. They act as key record-keepers for the Council.",
            ),
            "tower_emerald": Faction(
                id="tower_emerald",
                name="Tower of Transmutation",
                influence=4,
                alignment="neutral",
                description="Transmuters and biomancers who reshape matter and living systems. They are secretive and isolationist.",
            ),
            "tower_aurelian": Faction(
                id="tower_aurelian",
                name="Tower of Divination",
                influence=4,
                alignment="neutral",
                description="Diviners dealing in prophecy, foresight, and predictive strategy. They act as diplomats and treasurers of the Council.",
            ),
            "tower_obsidian": Faction(
                id="tower_obsidian",
                name="Tower of Necromancy",
                influence=4,
                alignment="neutral",
                description="Controversial practitioners of shadow, entropy, and necromancy. Barely tolerated by the Council, they do the necessary dark work.",
            ),
            "tower_alabaster": Faction(
                id="tower_alabaster",
                name="Tower of Abjuration",
                influence=5,
                alignment="lawful",
                description="Practitioners of protective, healing, and binding magics, trying desperately to keep the other towers from destroying each other.",
            ),
        }
        for faction_id, description in FACTION_DESCRIPTION_OVERRIDES.items():
            faction = self._factions.get(str(faction_id))
            if faction is None:
                continue
            faction.description = str(description)

    def get(self, faction_id: str) -> Optional[Faction]:
        return self._factions.get(faction_id)

    def list_all(self) -> List[Faction]:
        return list(self._factions.values())

    def save(self, faction: Faction) -> None:
        self._factions[faction.id] = faction

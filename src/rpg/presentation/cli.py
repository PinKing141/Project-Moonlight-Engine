from rpg.bootstrap import _build_inmemory_game_service, create_game_service
from rpg.presentation.main_menu import main_menu as _main_menu


def _bootstrap():
    game = create_game_service()
    creation_service = getattr(game, "character_creation_service", None)
    if creation_service is None:
        raise RuntimeError("Character creation service unavailable for current bootstrap mode.")
    return game, creation_service


def _bootstrap_inmemory():
    game = _build_inmemory_game_service()
    creation_service = getattr(game, "character_creation_service", None)
    if creation_service is None:
        raise RuntimeError("Character creation service unavailable for in-memory bootstrap.")
    return game, creation_service


def run_character_creator(creation_service) -> int:
    """Minimal compatibility character creator used by e2e/scripted CLI tests."""
    print("=== Character Creation ===")
    name = input("Enter your character's name: ").strip()

    available = creation_service.list_classes()
    for idx, cls in enumerate(available, start=1):
        ability = f" ({cls.primary_ability})" if getattr(cls, "primary_ability", None) else ""
        print(f"{idx}) {cls.name}{ability}")

    choice = input("> ").strip()
    selected_idx = int(choice) - 1 if choice.isdigit() else 0
    selected_idx = max(0, min(selected_idx, len(available) - 1))
    chosen = available[selected_idx]

    character = creation_service.create_character(name, selected_idx)

    print(f"\nCreated {character.name}, a level {character.level} {chosen.name}")
    print(f"HP: {character.hp_current}/{character.hp_max}")
    print(f"Starting at location ID {character.location_id}")
    return character.id or 0


def _run_game_loop(game, player_id: int) -> None:
    """Legacy-compatible text-input loop used by existing scripted e2e tests."""
    game_over = False
    while not game_over:
        view = game.get_player_view(player_id)
        print(view)
        choice = input(">>> ")
        result = game.make_choice(player_id, choice)
        for msg in result.messages:
            print(msg)
        game_over = bool(result.game_over)


def main() -> None:
    print("Legacy CLI entry is deprecated. Launching canonical arrow-key menu...")
    from rpg.__main__ import main as runtime_main

    runtime_main()


if __name__ == "__main__":
    main()

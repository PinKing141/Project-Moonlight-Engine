from rpg.infrastructure.legacy_cli_compat import (
    bootstrap as _bootstrap,
    bootstrap_inmemory as _bootstrap_inmemory,
    main_menu_loop as _main_menu,
    run_character_creator,
    run_game_loop as _run_game_loop,
)


def main() -> None:
    print("Legacy CLI entry is deprecated. Launching canonical arrow-key menu...")
    from rpg.__main__ import main as runtime_main

    runtime_main()


if __name__ == "__main__":
    main()

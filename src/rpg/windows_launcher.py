"""Windows launcher entrypoint for no-console executable builds."""

import traceback


def _show_error_dialog(title: str, message: str) -> None:
    try:
        import ctypes  # type: ignore

        mb_icon_error = 0x00000010
        mb_ok = 0x00000000
        ctypes.windll.user32.MessageBoxW(0, str(message), str(title), mb_ok | mb_icon_error)
        return
    except Exception:
        pass
    print(f"{title}: {message}")


def main() -> None:
    try:
        from rpg.__main__ import main as runtime_main

        runtime_main()
    except Exception as exc:
        details = traceback.format_exc(limit=8)
        _show_error_dialog(
            "Project Moonlight Engine",
            f"The game closed due to an unexpected error:\n\n{exc}\n\n{details}",
        )


if __name__ == "__main__":
    main()

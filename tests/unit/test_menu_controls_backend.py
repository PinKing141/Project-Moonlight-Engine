from rpg.presentation import menu_controls


class _Backend:
    def __init__(self):
        self.cleared = False
        self.read_values = ["UP", "ENTER"]
        self.arrow_calls = []
        self.prompt_calls = []

    def clear_screen(self) -> None:
        self.cleared = True

    def read_key(self):
        if self.read_values:
            return self.read_values.pop(0)
        return None

    def arrow_menu(self, title, options, footer_hint=None, initial_enter_guard_seconds=None) -> int:
        self.arrow_calls.append((title, list(options), footer_hint, initial_enter_guard_seconds))
        return 1

    def prompt_input(self, prompt: str = "") -> str:
        self.prompt_calls.append(prompt)
        return ""


def test_menu_backend_delegates_clear_and_read_key():
    backend = _Backend()
    menu_controls.set_menu_transport_backend(backend)
    try:
        menu_controls.clear_screen()
        assert backend.cleared is True
        assert menu_controls.read_key() == "UP"
        assert menu_controls.prompt_input("Press ENTER") == ""
        assert backend.prompt_calls == ["Press ENTER"]
    finally:
        menu_controls.reset_menu_transport_backend()


def test_menu_backend_delegates_arrow_menu_call():
    backend = _Backend()
    menu_controls.set_menu_transport_backend(backend)
    try:
        result = menu_controls.arrow_menu("Test", ["A", "B"], footer_hint="x", initial_enter_guard_seconds=0.5)
        assert result == 1
        assert backend.arrow_calls == [("Test", ["A", "B"], "x", 0.5)]
    finally:
        menu_controls.reset_menu_transport_backend()

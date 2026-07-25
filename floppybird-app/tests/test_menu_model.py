import unittest

from floppybird.menu.input import ENCODER_CLICK, ENCODER_ROTATE_CCW, ENCODER_ROTATE_CW, BTN4
from floppybird.menu.model import MenuModel, ScreenKind


class BootTransitionTests(unittest.TestCase):
    def test_starts_in_boot(self) -> None:
        model = MenuModel()
        self.assertIs(model.current_screen().kind, ScreenKind.BOOT)

    def test_boot_advances_to_main_after_two_seconds(self) -> None:
        model = MenuModel()
        model.tick(1.9)
        self.assertIs(model.current_screen().kind, ScreenKind.BOOT)
        model.tick(0.1)
        self.assertIs(model.current_screen().kind, ScreenKind.MAIN_MENU)

    def test_input_ignored_during_boot(self) -> None:
        model = MenuModel()
        model.handle_input(ENCODER_CLICK)
        self.assertIs(model.current_screen().kind, ScreenKind.BOOT)


class MainMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = MenuModel()
        self.model.tick(2.0)  # BOOT → MAIN

    def test_starts_at_index_zero(self) -> None:
        self.assertEqual(self.model.current_screen().index, 0)

    def test_encoder_cw_increments_index(self) -> None:
        self.model.handle_input(ENCODER_ROTATE_CW)
        self.assertEqual(self.model.current_screen().index, 1)

    def test_encoder_ccw_decrements_index(self) -> None:
        self.model.handle_input(ENCODER_ROTATE_CW)
        self.model.handle_input(ENCODER_ROTATE_CCW)
        self.assertEqual(self.model.current_screen().index, 0)

    def test_encoder_wraps_around_at_end(self) -> None:
        for _ in range(3):  # 3개 항목 → 끝까지 감
            self.model.handle_input(ENCODER_ROTATE_CW)
        self.assertEqual(self.model.current_screen().index, 0)  # 랩어라운드

    def test_encoder_wraps_around_at_start(self) -> None:
        self.model.handle_input(ENCODER_ROTATE_CCW)  # 0 → 마지막
        self.assertEqual(self.model.current_screen().index, 2)

    def test_click_enters_music_at_index_0(self) -> None:
        self.model.handle_input(ENCODER_CLICK)
        self.assertIs(self.model.current_screen().kind, ScreenKind.MUSIC)

    def test_click_enters_game_at_index_1(self) -> None:
        self.model.handle_input(ENCODER_ROTATE_CW)
        self.model.handle_input(ENCODER_CLICK)
        self.assertIs(self.model.current_screen().kind, ScreenKind.GAME)

    def test_click_enters_settings_at_index_2(self) -> None:
        self.model.handle_input(ENCODER_ROTATE_CW)
        self.model.handle_input(ENCODER_ROTATE_CW)
        self.model.handle_input(ENCODER_CLICK)
        self.assertIs(self.model.current_screen().kind, ScreenKind.SETTINGS)


class BackFromSubScreenTests(unittest.TestCase):
    def _enter(self, model: MenuModel, index: int) -> None:
        model.tick(2.0)
        for _ in range(index):
            model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_CLICK)

    def test_btn4_returns_from_music(self) -> None:
        model = MenuModel()
        self._enter(model, 0)
        model.handle_input(BTN4)
        self.assertIs(model.current_screen().kind, ScreenKind.MAIN_MENU)

    def test_btn4_returns_from_game(self) -> None:
        model = MenuModel()
        self._enter(model, 1)
        model.handle_input(BTN4)
        self.assertIs(model.current_screen().kind, ScreenKind.MAIN_MENU)

    def test_btn4_returns_from_settings(self) -> None:
        model = MenuModel()
        self._enter(model, 2)
        model.handle_input(BTN4)
        self.assertIs(model.current_screen().kind, ScreenKind.MAIN_MENU)

    def test_index_preserved_on_return(self) -> None:
        model = MenuModel()
        self._enter(model, 1)
        model.handle_input(BTN4)
        self.assertEqual(model.current_screen().index, 1)


def _make_clock(h: int, m: int):
    """주어진 시/분을 항상 반환하는 가짜 clock 소스 (struct_time 호환)."""
    import time as _time
    return lambda: _time.struct_time(
        (2026, 1, 1, h, m, 0, 0, 1, -1)
    )


class ClockStatusTests(unittest.TestCase):
    """Screen.now_hhmm — 벽시계 주입/표시 검증."""

    def test_main_menu_carries_clock_when_provided(self) -> None:
        model = MenuModel(clock=_make_clock(12, 34))
        model.tick(2.0)  # BOOT → MAIN_MENU
        self.assertEqual(model.current_screen().now_hhmm, "12:34")

    def test_clock_zero_pads_minute(self) -> None:
        # 9시 5분 → "09:05" (두 자리 zero-pad)
        model = MenuModel(clock=_make_clock(9, 5))
        model.tick(2.0)
        self.assertEqual(model.current_screen().now_hhmm, "09:05")

    def test_clock_zero_pads_hour(self) -> None:
        model = MenuModel(clock=_make_clock(7, 30))
        model.tick(2.0)
        self.assertEqual(model.current_screen().now_hhmm, "07:30")

    def test_boot_carries_clock_too(self) -> None:
        # BOOT도 부팅 진입 시각을 now_hhmm로 들고 있음 (렌더링에선 안 쓰지만).
        model = MenuModel(clock=_make_clock(23, 59))
        self.assertEqual(model.current_screen().now_hhmm, "23:59")

    def test_clock_reflects_source_change_between_calls(self) -> None:
        # clock이 매 호출마다 다른 값을 주면 current_screen이 그 값을 반영.
        import time as _time
        times = iter([
            _time.struct_time((2026, 1, 1, 8, 0, 0, 0, 1, -1)),
            _time.struct_time((2026, 1, 1, 8, 1, 0, 0, 1, -1)),
        ])
        model = MenuModel(clock=lambda: next(times))
        model.tick(2.0)
        # 첫 current_screen은 08:01 (boot 시각은 첫 값 08:00, MAIN에서는 두 번째 값).
        self.assertEqual(model.current_screen().now_hhmm, "08:01")

    def test_default_clock_uses_system_localtime(self) -> None:
        # clock 인자 생략 시 time.localtime 사용 → 정상 동작.
        model = MenuModel()
        model.tick(2.0)
        import time as _time
        now = _time.localtime()
        expected = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        self.assertEqual(model.current_screen().now_hhmm, expected)

    def test_clock_source_propagates_to_subscreens(self) -> None:
        # 서브화면은 시계를 그리진 않지만 Screen.now_hhmm는 여전히 채워짐.
        from floppybird.menu.input import ENCODER_CLICK
        model = MenuModel(clock=_make_clock(15, 45))
        model.tick(2.0)
        model.handle_input(ENCODER_CLICK)  # MAIN → MUSIC
        screen = model.current_screen()
        self.assertIs(screen.kind, ScreenKind.MUSIC)
        self.assertEqual(screen.now_hhmm, "15:45")


if __name__ == "__main__":
    unittest.main()

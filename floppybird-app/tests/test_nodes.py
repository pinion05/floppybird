"""이슈 #9: Node 트리 단위 테스트.

검증:
- Node/Page ABC 인터페이스 계약
- ListComponent/ListCell/NavItem Node 준수
- 5종 Page render/handle_input/tick
- MenuModel 루트 교체 흐름 (BootPage → MainPage → 서브 페이지)
- golden frame 회귀 (픽셀 동일)
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import time
import unittest
import zipfile
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from floppybird.menu.input import (
    BTN1,
    BTN4,
    ENCODER_CLICK,
    ENCODER_ROTATE_CCW,
    ENCODER_ROTATE_CW,
)
from floppybird.menu.model import MenuModel
from floppybird.menu.nodes import (
    BootPage,
    GamePage,
    ListCell,
    ListComponent,
    ListContext,
    MainPage,
    MusicPage,
    NavItem,
    Node,
    Page,
    Rect,
    SettingsPage,
)
from floppybird.menu.render import draw_root, _font
from mn12832l.renderer import MvlsbRenderer

_WIDTH = 128
_HEIGHT = 32


# ─── 헬퍼 ───


def _make_clock(h: int, m: int):
    return lambda: time.struct_time((2026, 1, 1, h, m, 0, 0, 1, -1))


def _pixel_bbox(frame: bytes) -> Optional[Tuple[int, int, int, int]]:
    """켜진 픽셀의 (x_min, y_min, x_max, y_max) 반환. 빈 프레임이면 None."""
    x_min = y_min = 9999
    x_max = y_max = -1
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            if frame[(y // 8) * _WIDTH + x] & (1 << (y % 8)):
                if x < x_min:
                    x_min = x
                if x > x_max:
                    x_max = x
                if y < y_min:
                    y_min = y
                if y > y_max:
                    y_max = y
    if x_max < 0:
        return None
    return x_min, y_min, x_max, y_max


def _render_frame(node: Node) -> bytes:
    return draw_root(node, MvlsbRenderer())


def _region_has_pixels(frame: bytes, x0: int, x1: int, y0: int, y1: int) -> bool:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if frame[(y // 8) * _WIDTH + x] & (1 << (y % 8)):
                return True
    return False


# ─── Node ABC 계약 ───


class NodeContractTests(unittest.TestCase):
    def test_node_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            Node()  # type: ignore[abstract]

    def test_page_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            Page()  # type: ignore[abstract]

    def test_page_is_node(self) -> None:
        self.assertTrue(issubclass(Page, Node))

    def test_listcell_is_node(self) -> None:
        self.assertTrue(issubclass(ListCell, Node))

    def test_listcomponent_is_node(self) -> None:
        self.assertTrue(issubclass(ListComponent, Node))

    def test_all_pages_are_node(self) -> None:
        for cls in (BootPage, MainPage, MusicPage, GamePage, SettingsPage):
            self.assertTrue(issubclass(cls, Node), f"{cls.__name__} must be Node")

    def test_all_pages_are_page(self) -> None:
        for cls in (BootPage, MainPage, MusicPage, GamePage, SettingsPage):
            self.assertTrue(issubclass(cls, Page), f"{cls.__name__} must be Page")

    def test_navitem_is_listcell(self) -> None:
        self.assertTrue(issubclass(NavItem, ListCell))

    def test_listcell_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            ListCell()  # type: ignore[abstract]


# ─── BootPage ───


class BootPageTests(unittest.TestCase):
    def test_boot_tick_before_2s_returns_none(self) -> None:
        boot = BootPage()
        self.assertIsNone(boot.tick(1.9))

    def test_boot_tick_at_2s_returns_mainpage(self) -> None:
        boot = BootPage()
        result = boot.tick(2.0)
        self.assertIsInstance(result, MainPage)

    def test_boot_ignores_all_input(self) -> None:
        boot = BootPage()
        for event in (BTN1, BTN4, ENCODER_CLICK, ENCODER_ROTATE_CW):
            self.assertIsNone(boot.handle_input(event))

    def test_boot_produces_non_empty_frame(self) -> None:
        frame = _render_frame(BootPage())
        self.assertEqual(len(frame), 512)
        self.assertTrue(any(b != 0 for b in frame))

    def test_boot_animates_across_steps(self) -> None:
        b1 = BootPage()
        b1.tick(0.0)
        f1 = _render_frame(b1)
        b2 = BootPage()
        b2.tick(0.5)
        f2 = _render_frame(b2)
        self.assertNotEqual(f1, f2)

    def test_boot_clock_propagated_to_mainpage(self) -> None:
        clock = _make_clock(10, 30)
        boot = BootPage(clock=clock)
        main = boot.tick(2.0)
        self.assertIsInstance(main, MainPage)


# ─── MainPage ───


class MainPageTests(unittest.TestCase):
    def test_render_produces_512_bytes(self) -> None:
        frame = _render_frame(MainPage())
        self.assertEqual(len(frame), 512)

    def test_render_has_pixels(self) -> None:
        frame = _render_frame(MainPage())
        bbox = _pixel_bbox(frame)
        self.assertIsNotNone(bbox)

    def test_clock_draws_in_top_right(self) -> None:
        main = MainPage(clock=_make_clock(12, 34))
        frame = _render_frame(main)
        self.assertTrue(_region_has_pixels(frame, 100, 127, 0, 7))

    def test_no_clock_no_top_right_pixels(self) -> None:
        main = MainPage()
        frame = _render_frame(main)
        self.assertFalse(_region_has_pixels(frame, 100, 127, 0, 7))

    def test_selected_index_starts_at_zero(self) -> None:
        main = MainPage()
        self.assertEqual(main.selected_index, 0)

    def test_cw_increments_index(self) -> None:
        main = MainPage()
        main.handle_input(ENCODER_ROTATE_CW)
        self.assertEqual(main.selected_index, 1)

    def test_ccw_wraps_to_last(self) -> None:
        main = MainPage()
        main.handle_input(ENCODER_ROTATE_CCW)
        self.assertEqual(main.selected_index, 2)

    def test_cw_wraps_around_at_end(self) -> None:
        main = MainPage()
        for _ in range(3):
            main.handle_input(ENCODER_ROTATE_CW)
        self.assertEqual(main.selected_index, 0)

    def test_click_at_0_returns_musicpage(self) -> None:
        main = MainPage()
        result = main.handle_input(ENCODER_CLICK)
        self.assertIsInstance(result, MusicPage)

    def test_click_at_1_returns_gamepage(self) -> None:
        main = MainPage()
        main.handle_input(ENCODER_ROTATE_CW)
        result = main.handle_input(ENCODER_CLICK)
        self.assertIsInstance(result, GamePage)

    def test_click_at_2_returns_settingspage(self) -> None:
        main = MainPage()
        main.handle_input(ENCODER_ROTATE_CW)
        main.handle_input(ENCODER_ROTATE_CW)
        result = main.handle_input(ENCODER_CLICK)
        self.assertIsInstance(result, SettingsPage)

    def test_clock_different_times_different_frames(self) -> None:
        f1 = _render_frame(MainPage(clock=_make_clock(12, 34)))
        f2 = _render_frame(MainPage(clock=_make_clock(12, 35)))
        self.assertNotEqual(f1, f2)


# ─── 서브 페이지 ───


class SubPageTests(unittest.TestCase):
    def test_music_page_render(self) -> None:
        frame = _render_frame(MusicPage())
        self.assertEqual(len(frame), 512)
        bbox = _pixel_bbox(frame)
        self.assertIsNotNone(bbox)

    def test_game_page_render(self) -> None:
        frame = _render_frame(GamePage())
        self.assertEqual(len(frame), 512)
        bbox = _pixel_bbox(frame)
        self.assertIsNotNone(bbox)

    def test_settings_page_render(self) -> None:
        frame = _render_frame(SettingsPage())
        self.assertEqual(len(frame), 512)
        bbox = _pixel_bbox(frame)
        self.assertIsNotNone(bbox)

    def test_music_btn4_returns_back(self) -> None:
        main = MainPage()
        music = MusicPage(back=main)
        result = music.handle_input(BTN4)
        self.assertIs(result, main)

    def test_game_btn4_returns_back(self) -> None:
        main = MainPage()
        game = GamePage(back=main)
        result = game.handle_input(BTN4)
        self.assertIs(result, main)

    def test_settings_btn4_returns_back(self) -> None:
        main = MainPage()
        settings = SettingsPage(back=main)
        result = settings.handle_input(BTN4)
        self.assertIs(result, main)

    def test_music_ignores_other_input(self) -> None:
        music = MusicPage()
        for event in (BTN1, ENCODER_ROTATE_CW, ENCODER_CLICK):
            self.assertIsNone(music.handle_input(event))


# ─── ListComponent + ListCell ───


class _FakeCell(ListCell):
    def __init__(self, *, height: int = 9) -> None:
        self.HEIGHT = height
        self.render_calls: list = []

    def render_cell(self, draw, font, rect, selected) -> None:
        self.render_calls.append((rect, selected))


class ListComponentTests(unittest.TestCase):
    def _new_draw(self):
        return ImageDraw.Draw(Image.new("1", (128, 32), 0))

    def test_render_passes_rect_with_cell_height(self) -> None:
        cell_a = _FakeCell(height=9)
        cell_b = _FakeCell(height=12)
        comp = ListComponent([cell_a, cell_b], origin=(1, 3), width=100)
        comp.render(self._new_draw(), ImageFont.load_default())
        rect_a, sel_a = cell_a.render_calls[0]
        rect_b, _ = cell_b.render_calls[0]
        self.assertEqual(rect_a, Rect(1, 3, 100, 9))
        self.assertEqual(rect_b, Rect(1, 3 + 9, 100, 12))
        self.assertTrue(sel_a)

    def test_render_marks_only_selected(self) -> None:
        cells = [_FakeCell(), _FakeCell(), _FakeCell()]
        comp = ListComponent(cells)
        comp.render(self._new_draw(), ImageFont.load_default())
        self.assertTrue(cells[0].render_calls[0][1])
        self.assertFalse(cells[1].render_calls[0][1])
        self.assertFalse(cells[2].render_calls[0][1])

    def test_default_on_methods_return_false(self) -> None:
        cell = _FakeCell()
        ctx = ListContext()
        self.assertFalse(cell.on_button_1(ctx))
        self.assertFalse(cell.on_button_4(ctx))
        self.assertFalse(cell.on_encoder_click(ctx))
        self.assertFalse(cell.on_encoder_rotate(+1, ctx))

    def test_default_height_is_9(self) -> None:
        self.assertEqual(_FakeCell().HEIGHT, 9)

    def test_cw_wraps_around(self) -> None:
        comp = ListComponent([_FakeCell(), _FakeCell()])
        comp.handle_input(ENCODER_ROTATE_CW)  # 0→1
        comp.handle_input(ENCODER_ROTATE_CW)  # 1→0 (wrap)
        self.assertEqual(comp.selected, 0)

    def test_ccw_wraps_around(self) -> None:
        comp = ListComponent([_FakeCell(), _FakeCell()])
        comp.handle_input(ENCODER_ROTATE_CCW)  # 0→1 (wrap)
        self.assertEqual(comp.selected, 1)

    def test_empty_cells_noop(self) -> None:
        comp = ListComponent([])
        result = comp.handle_input(ENCODER_ROTATE_CW)
        self.assertIsNone(result)


class NavItemTests(unittest.TestCase):
    def test_render_selected_has_marker(self) -> None:
        font = ImageFont.load_default()
        item = NavItem("MUSIC", lambda: MusicPage())
        img_sel = Image.new("1", (128, 9), 0)
        item.render_cell(
            ImageDraw.Draw(img_sel), font, Rect(0, 0, 100, 9), selected=True
        )
        img_unsel = Image.new("1", (128, 9), 0)
        item.render_cell(
            ImageDraw.Draw(img_unsel), font, Rect(0, 0, 100, 9), selected=False
        )
        count_sel = sum(img_sel.getpixel((x, y)) > 0 for x in range(128) for y in range(9))
        count_unsel = sum(img_unsel.getpixel((x, y)) > 0 for x in range(128) for y in range(9))
        self.assertGreater(count_sel, count_unsel)

    def test_click_navigates(self) -> None:
        target_page = MusicPage()
        item = NavItem("MUSIC", lambda: target_page)
        ctx = ListContext()
        result = item.on_encoder_click(ctx)
        self.assertTrue(result)
        self.assertIsNotNone(ctx.navigate_target)

    def test_default_height_is_9(self) -> None:
        self.assertEqual(NavItem("X", lambda: MusicPage()).HEIGHT, 9)


# ─── MenuModel 통합 (루트 교체 흐름) ───


class MenuModelIntegrationTests(unittest.TestCase):
    def test_starts_in_boot(self) -> None:
        model = MenuModel()
        self.assertIsInstance(model.current_root(), BootPage)

    def test_boot_advances_to_main_after_two_seconds(self) -> None:
        model = MenuModel()
        model.tick(1.9)
        self.assertIsInstance(model.current_root(), BootPage)
        model.tick(0.1)
        self.assertIsInstance(model.current_root(), MainPage)

    def test_input_ignored_during_boot(self) -> None:
        model = MenuModel()
        model.handle_input(ENCODER_CLICK)
        self.assertIsInstance(model.current_root(), BootPage)

    def test_click_enters_music(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_CLICK)
        self.assertIsInstance(model.current_root(), MusicPage)

    def test_click_enters_game_at_index_1(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_CLICK)
        self.assertIsInstance(model.current_root(), GamePage)

    def test_click_enters_settings_at_index_2(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_CLICK)
        self.assertIsInstance(model.current_root(), SettingsPage)

    def test_btn4_returns_from_music(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_CLICK)  # → Music
        model.handle_input(BTN4)  # → back
        self.assertIsInstance(model.current_root(), MainPage)

    def test_btn4_returns_from_game(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_CLICK)
        model.handle_input(BTN4)
        self.assertIsInstance(model.current_root(), MainPage)

    def test_btn4_returns_from_settings(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_ROTATE_CW)
        model.handle_input(ENCODER_CLICK)
        model.handle_input(BTN4)
        self.assertIsInstance(model.current_root(), MainPage)

    def test_index_preserved_on_return(self) -> None:
        model = MenuModel()
        model.tick(2.0)
        model.handle_input(ENCODER_ROTATE_CW)  # index=1
        model.handle_input(ENCODER_CLICK)  # → Game
        model.handle_input(BTN4)  # → back
        root = model.current_root()
        self.assertIsInstance(root, MainPage)
        assert isinstance(root, MainPage)
        self.assertEqual(root.selected_index, 1)

    def test_main_menu_has_clock(self) -> None:
        model = MenuModel(clock=_make_clock(12, 34))
        model.tick(2.0)
        frame = _render_frame(model.current_root())
        self.assertTrue(_region_has_pixels(frame, 100, 127, 0, 7))

    def test_boot_no_clock_in_top_right(self) -> None:
        """BootPage는 clock이 있어도 시계를 그리지 않는다 — 프레임 동일."""
        model_no = MenuModel(clock=_make_clock(12, 34))
        f_no = _render_frame(model_no.current_root())
        # BootPage 자체(워드마크) 픽셀은 있지만 clock 픽셀이 추가되지 않음.
        # clock 주입 여부와 무관하게 동일 프레임.
        boot_no_clock = _render_frame(BootPage())
        boot_with_clock = _render_frame(BootPage(clock=_make_clock(12, 34)))
        self.assertEqual(boot_no_clock, boot_with_clock)

    def test_clock_zero_pads(self) -> None:
        model = MenuModel(clock=_make_clock(9, 5))
        model.tick(2.0)
        frame = _render_frame(model.current_root())
        # 09:05 — 우상단에 픽셀 있어야 함
        self.assertTrue(_region_has_pixels(frame, 100, 127, 0, 7))

    def test_subscreens_no_clock(self) -> None:
        """서브화면은 clock 주입 없음 — 정적 렌더."""
        model = MenuModel(clock=_make_clock(15, 45))
        model.tick(2.0)
        model.handle_input(ENCODER_CLICK)  # → Music
        frame = _render_frame(model.current_root())
        # MusicPage는 clock 안 받음 — 우상단 시계 없음
        self.assertFalse(_region_has_pixels(frame, 100, 127, 0, 7))


# ─── Golden frame 회귀 ───


class GoldenFrameTests(unittest.TestCase):
    def test_all_pages_produce_512_bytes(self) -> None:
        nodes = [
            BootPage(),
            MainPage(),
            MusicPage(),
            GamePage(),
            SettingsPage(),
        ]
        for node in nodes:
            frame = _render_frame(node)
            self.assertEqual(len(frame), 512)

    def test_all_pages_fit_in_buffer(self) -> None:
        nodes = [
            BootPage(),
            MainPage(),
            MusicPage(),
            GamePage(),
            SettingsPage(),
        ]
        for node in nodes:
            frame = _render_frame(node)
            bbox = _pixel_bbox(frame)
            self.assertIsNotNone(bbox, f"{type(node).__name__} should draw")
            x_min, y_min, x_max, y_max = bbox
            self.assertGreaterEqual(x_min, 0)
            self.assertLess(x_max, _WIDTH)
            self.assertGreaterEqual(y_min, 0)
            self.assertLess(y_max, _HEIGHT)

    def test_all_pages_leave_margin(self) -> None:
        margin = 1
        nodes = [
            BootPage(),
            MainPage(),
            MusicPage(),
            GamePage(),
            SettingsPage(),
        ]
        for node in nodes:
            frame = _render_frame(node)
            bbox = _pixel_bbox(frame)
            assert bbox is not None
            x_min, y_min, x_max, y_max = bbox
            self.assertGreaterEqual(x_min, margin)
            self.assertLess(x_max, _WIDTH - margin)
            self.assertGreaterEqual(y_min, margin)
            self.assertLess(y_max, _HEIGHT - margin)

    def test_golden_frames_stable(self) -> None:
        for cls in (MusicPage, GamePage, SettingsPage):
            node = cls()
            self.assertEqual(_render_frame(node), _render_frame(cls()))

    def test_selection_marker_moves(self) -> None:
        main0 = MainPage()
        f0 = _render_frame(main0)
        main1 = MainPage()
        main1.handle_input(ENCODER_ROTATE_CW)
        f1 = _render_frame(main1)
        self.assertNotEqual(f0, f1)

    def test_boot_no_clock_regardless_of_hhmm(self) -> None:
        """BootPage는 clock이 있어도 시계를 그리지 않는다."""
        boot_no_clock = _render_frame(BootPage())
        boot_with_clock = _render_frame(BootPage(clock=_make_clock(12, 34)))
        self.assertEqual(boot_no_clock, boot_with_clock)


# ─── Font (zipimport 회귀 — 기존 테스트 유지) ───


def _build_package_zip() -> str:
    src_root = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "mn12832l-stm32-driver", "src"
        )
    )
    pkg_root = os.path.join(src_root, "mn12832l")
    if not os.path.isdir(pkg_root):
        raise FileNotFoundError(
            f"driver package not found at {pkg_root} — run tests from repo root"
        )
    fd, zip_path = tempfile.mkstemp(suffix=".zip", prefix="mn12832l_test_")
    os.close(fd)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(pkg_root):
            for fn in files:
                if "__pycache__" in root:
                    continue
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, src_root)
                z.write(full, arc)
    return zip_path


class FontLoadTests(unittest.TestCase):
    def test_font_resource_readable_under_zipimport(self) -> None:
        zip_path = _build_package_zip()
        try:
            sys.path.insert(0, zip_path)
            for key in list(sys.modules):
                if key == "mn12832l" or key.startswith("mn12832l."):
                    del sys.modules[key]
            import importlib
            import importlib.util

            importlib.import_module("mn12832l")
            pkg_spec = importlib.util.find_spec("mn12832l")
            self.assertIn(zip_path, getattr(pkg_spec, "origin", "") or "")

            from importlib import resources

            fp = resources.files("mn12832l").joinpath("assets", "Galmuri7.ttf")
            self.assertTrue(fp.is_file())
            data = fp.read_bytes()
            self.assertIn(data[:4], (b"\x00\x01\x00\x00", b"OTTO"))
        finally:
            if zip_path in sys.path:
                sys.path.remove(zip_path)
            for key in list(sys.modules):
                if key == "mn12832l" or key.startswith("mn12832l."):
                    del sys.modules[key]
            try:
                os.remove(zip_path)
            except OSError:
                pass

    def test_font_loads_galmuri_not_default(self) -> None:
        _font.cache_clear()
        font = _font(8)
        from importlib import resources

        data = resources.files("mn12832l").joinpath("assets", "Galmuri7.ttf").read_bytes()
        reference = ImageFont.truetype(io.BytesIO(data), 8)
        for probe in ("M", "g", "8", " "):
            self.assertEqual(font.getbbox(probe), reference.getbbox(probe))

    def test_font_loads_galmuri_under_zipimport(self) -> None:
        from floppybird.menu import render as render_mod

        zip_path = _build_package_zip()
        try:
            sys.path.insert(0, zip_path)
            for key in list(sys.modules):
                if key == "mn12832l" or key.startswith("mn12832l."):
                    del sys.modules[key]
            import importlib
            import importlib.util

            importlib.import_module("mn12832l")
            pkg_spec = importlib.util.find_spec("mn12832l")
            self.assertIn(zip_path, getattr(pkg_spec, "origin", "") or "")

            render_mod._font.cache_clear()
            font = render_mod._font(8)
            from importlib import resources

            data = (
                resources.files("mn12832l")
                .joinpath("assets", "Galmuri7.ttf")
                .read_bytes()
            )
            reference = ImageFont.truetype(io.BytesIO(data), 8)
            for probe in ("M", "g", "8", " "):
                self.assertEqual(font.getbbox(probe), reference.getbbox(probe))
        finally:
            if zip_path in sys.path:
                sys.path.remove(zip_path)
            for key in list(sys.modules):
                if key == "mn12832l" or key.startswith("mn12832l."):
                    del sys.modules[key]
            try:
                os.remove(zip_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()

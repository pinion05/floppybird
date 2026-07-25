"""이슈 #7: ListComponent + ListCell 프레임워크 단위 테스트.

검증:
- Cell이 HEIGHT/render/on_xxx 결정
- 모든 입력: Cell 우선 (True 반환 = 가로챔), False면 컨테이너 기본 동작
- BTN4도 일반화 (예외 없음)
- NavItem 구체 Cell 동작
"""

from __future__ import annotations

import unittest

from PIL import Image, ImageDraw, ImageFont

from floppybird.menu.input import (
    BTN1,
    BTN2,
    BTN3,
    BTN4,
    ENCODER_CLICK,
    ENCODER_ROTATE_CCW,
    ENCODER_ROTATE_CW,
)
from floppybird.menu.list_component import (
    ListCell,
    ListComponent,
    ListContext,
    NavItem,
    Rect,
)
from floppybird.menu.model import ScreenKind


# --- 테스트용 FakeCell들 ---


class _FakeCell(ListCell):
    """테스트 더미. render는 아무것도 안 그림. 플래그로 on_xxx 동작 제어."""

    def __init__(
        self,
        *,
        rotate: bool = False,
        button4: bool = False,
        click: bool = False,
        height: int = 9,
    ) -> None:
        self.HEIGHT = height
        self._rotate = rotate
        self._button4 = button4
        self._click = click
        self.render_calls: list = []  # (rect, selected) 기록
        self.rotate_calls: list = []
        self.button4_calls: list = []
        self.click_calls: list = []

    def render(self, draw, font, rect, selected) -> None:
        self.render_calls.append((rect, selected))


class _RotateCapturingCell(_FakeCell):
    """on_encoder_rotate에서 회전 기록 + 플래그 반환."""

    def on_encoder_rotate(self, delta, ctx) -> bool:
        self.rotate_calls.append(delta)
        return self._rotate


class _Button4CapturingCell(_FakeCell):
    def on_button_4(self, ctx) -> bool:
        self.button4_calls.append(True)
        return self._button4


class _ClickCapturingCell(_FakeCell):
    def on_encoder_click(self, ctx) -> bool:
        self.click_calls.append(True)
        return self._click


# === ListCell 인터페이스 ===


class ListCellInterfaceTests(unittest.TestCase):
    def test_listcell_is_abstract_cannot_instantiate(self) -> None:
        """ListCell은 ABC — render 추상 메서드 미구현 시 인스턴스 불가."""
        with self.assertRaises(TypeError):
            ListCell()  # type: ignore[abstract]

    def test_default_on_methods_return_false(self) -> None:
        """모든 on_xxx 기본 False — 아무것도 안 하면 자동 컨테이너 위임."""

        class _Minimal(ListCell):
            def render(self, draw, font, rect, selected) -> None:
                pass

        cell = _Minimal()
        ctx = ListContext()
        self.assertFalse(cell.on_button_1(ctx))
        self.assertFalse(cell.on_button_2(ctx))
        self.assertFalse(cell.on_button_3(ctx))
        self.assertFalse(cell.on_button_4(ctx))
        self.assertFalse(cell.on_encoder_click(ctx))
        self.assertFalse(cell.on_encoder_rotate(+1, ctx))
        self.assertFalse(cell.on_encoder_rotate(-1, ctx))

    def test_default_height_is_9(self) -> None:
        """HEIGHT 기본 9."""

        class _Minimal(ListCell):
            def render(self, draw, font, rect, selected) -> None:
                pass

        self.assertEqual(_Minimal().HEIGHT, 9)


# === ListComponent.render (레이아웃) ===


class ListComponentRenderTests(unittest.TestCase):
    def _new_draw(self):
        return ImageDraw.Draw(Image.new("1", (128, 32), 0))

    def test_render_passes_rect_with_cell_height(self) -> None:
        """cell.HEIGHT로 rect.height 세팅, 다음 cell은 y+HEIGHT에 배치."""
        cell_a = _FakeCell(height=9)
        cell_b = _FakeCell(height=12)
        comp = ListComponent([cell_a, cell_b], origin=(1, 3), width=100)

        comp.render(self._new_draw(), None, selected=0)

        rect_a, sel_a = cell_a.render_calls[0]
        rect_b, sel_b = cell_b.render_calls[0]
        self.assertEqual(rect_a, Rect(1, 3, 100, 9))
        self.assertEqual(rect_b, Rect(1, 3 + 9, 100, 12))
        self.assertTrue(sel_a)
        self.assertFalse(sel_b)

    def test_render_marks_only_selected(self) -> None:
        cells = [_FakeCell() for _ in range(3)]
        comp = ListComponent(cells)

        comp.render(self._new_draw(), None, selected=2)

        self.assertFalse(cells[0].render_calls[0][1])
        self.assertFalse(cells[1].render_calls[0][1])
        self.assertTrue(cells[2].render_calls[0][1])


# === ListComponent.handle_input (Cell 우선 원칙) ===


class ListComponentInputTests(unittest.TestCase):
    def test_cw_rotate_when_cell_false_advances_selected(self) -> None:
        """Cell이 회전 안 쓰면(False) 컨테이너가 selected +1."""
        cells = [_RotateCapturingCell(), _RotateCapturingCell()]
        comp = ListComponent(cells)
        ctx = ListContext()

        new_sel, go_up = comp.handle_input(ENCODER_ROTATE_CW, 0, ctx)

        self.assertEqual(new_sel, 1)
        self.assertFalse(go_up)
        self.assertEqual(cells[0].rotate_calls, [+1])

    def test_cw_rotate_when_cell_true_does_not_advance(self) -> None:
        """Cell이 회전 가로채면(True) selected 유지 — 슬라이더 값 조정 등."""
        cells = [_RotateCapturingCell(rotate=True), _RotateCapturingCell()]
        comp = ListComponent(cells)
        ctx = ListContext()

        new_sel, _ = comp.handle_input(ENCODER_ROTATE_CW, 0, ctx)

        self.assertEqual(new_sel, 0)  # 안 움직임

    def test_ccw_rotate_when_cell_false_decrements_selected(self) -> None:
        cells = [_RotateCapturingCell(), _RotateCapturingCell()]
        comp = ListComponent(cells)

        new_sel, _ = comp.handle_input(ENCODER_ROTATE_CCW, 1, ListContext())

        self.assertEqual(new_sel, 0)
        self.assertEqual(cells[1].rotate_calls, [-1])

    def test_cw_at_end_returns_overflow(self) -> None:
        """마지막 항목에서 CW → 범위 초과값 (wrap/clamp은 호출자 책임).

        ListComponent는 정책 모름. MenuModel은 %n wrap, 다른 화면은 min/max 클램프.
        """
        cells = [_FakeCell(), _FakeCell()]
        comp = ListComponent(cells)

        new_sel, _ = comp.handle_input(ENCODER_ROTATE_CW, 1, ListContext())

        self.assertEqual(new_sel, 2)  # 범위 밖. 호출자가 wrap/clamp.

    def test_ccw_at_start_returns_negative(self) -> None:
        """첫 항목에서 CCW → 음수 (호출자가 wrap/clamp)."""
        cells = [_FakeCell(), _FakeCell()]
        comp = ListComponent(cells)

        new_sel, _ = comp.handle_input(ENCODER_ROTATE_CCW, 0, ListContext())

        self.assertEqual(new_sel, -1)

    def test_btn4_when_cell_false_returns_go_up(self) -> None:
        """Cell이 BTN4 안 쓰면(False) 컨테이너가 '위로' 신호."""
        cells = [_Button4CapturingCell()]
        comp = ListComponent(cells)

        new_sel, go_up = comp.handle_input(BTN4, 0, ListContext())

        self.assertEqual(new_sel, 0)
        self.assertTrue(go_up)

    def test_btn4_when_cell_true_no_go_up(self) -> None:
        """Cell이 BTN4 가로채면(True) 위로 안 감 — 슬라이더 편집 취소 등."""
        cells = [_Button4CapturingCell(button4=True)]
        comp = ListComponent(cells)

        _, go_up = comp.handle_input(BTN4, 0, ListContext())

        self.assertFalse(go_up)

    def test_btn1_routes_to_cell(self) -> None:
        """BTN1/2/3/CLICK은 Cell에게만 — 컨테이너 기본 동작 없음."""

        class _B1(ListCell):
            called = False
            def render(self, draw, font, rect, selected) -> None: pass
            def on_button_1(self, ctx) -> bool:
                _B1.called = True
                return False

        comp = ListComponent([_B1()])
        new_sel, go_up = comp.handle_input(BTN1, 0, ListContext())

        self.assertTrue(_B1.called)
        self.assertEqual(new_sel, 0)
        self.assertFalse(go_up)

    def test_encoder_click_routes_to_cell(self) -> None:
        cells = [_ClickCapturingCell()]
        comp = ListComponent(cells)

        new_sel, go_up = comp.handle_input(ENCODER_CLICK, 0, ListContext())

        self.assertEqual(cells[0].click_calls, [True])
        self.assertEqual(new_sel, 0)
        self.assertFalse(go_up)

    def test_empty_cells_returns_unchanged(self) -> None:
        comp = ListComponent([])
        new_sel, go_up = comp.handle_input(ENCODER_ROTATE_CW, 0, ListContext())
        self.assertEqual(new_sel, 0)
        self.assertFalse(go_up)


# === NavItem ===


class NavItemTests(unittest.TestCase):
    def test_render_draws_marker_and_label(self) -> None:
        """NavItem render: 선택/비선택 시 픽셀 차이 (마커 '>' vs ' ')."""
        font = ImageFont.load_default()
        item = NavItem("MUSIC PLAYER", ScreenKind.MUSIC)

        def _count_pixels(image):
            return sum(
                image.getpixel((x, y)) > 0
                for x in range(image.width)
                for y in range(image.height)
            )

        image_sel = Image.new("1", (128, 9), 0)
        item.render(ImageDraw.Draw(image_sel), font, Rect(0, 0, 100, 9), selected=True)

        image_unsel = Image.new("1", (128, 9), 0)
        item.render(ImageDraw.Draw(image_unsel), font, Rect(0, 0, 100, 9), selected=False)

        # 선택 시 '>' 마커로 비선택보다 픽셀 수 많아야
        self.assertGreater(
            _count_pixels(image_sel), _count_pixels(image_unsel),
            "선택 시 '>' 마커로 비선택보다 픽셀 수가 많아야",
        )

    def test_render_unselected_no_marker(self) -> None:
        """비선택 시 라벨 자체는 여전히 그려짐 — 마커만 ' '."""
        font = ImageFont.load_default()
        item = NavItem("X", ScreenKind.MUSIC)
        image = Image.new("1", (128, 9), 0)
        item.render(ImageDraw.Draw(image), font, Rect(0, 0, 100, 9), selected=False)

        total = sum(
            image.getpixel((x, y)) > 0
            for x in range(image.width)
            for y in range(image.height)
        )
        self.assertGreater(total, 0, "비선택이어도 라벨은 그려져야")

    def test_click_navigates_to_target(self) -> None:
        item = NavItem("MUSIC", ScreenKind.MUSIC)
        ctx = ListContext()

        result = item.on_encoder_click(ctx)

        self.assertTrue(result)
        self.assertEqual(ctx.navigate_target, ScreenKind.MUSIC)

    def test_default_height_is_9(self) -> None:
        self.assertEqual(NavItem("X", ScreenKind.MUSIC).HEIGHT, 9)


if __name__ == "__main__":
    unittest.main()

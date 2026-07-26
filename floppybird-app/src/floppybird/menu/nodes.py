"""Node 트리 — Page/Cell/Container를 단일 Node 인터페이스로 통합 (이슈 #9).

Composite 패턴 + 재귀적 자식 보유. Page/Cell/Container가 같은 인터페이스 따름.
역할(Page/Cell/Container)은 유지, Node는 인터페이스 통합만 (Godot 경고 수용).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from PIL import ImageDraw, ImageFont

from mn12832l import FRAME_WIDTH, FRAME_HEIGHT, load_ascii_art_asset

from .input import (
    BTN1,
    BTN2,
    BTN3,
    BTN4,
    ENCODER_CLICK,
    ENCODER_ROTATE_CCW,
    ENCODER_ROTATE_CW,
    InputEvent,
)

_BOOT_DURATION = 2.0

# 벽시계 소스 — struct_time(또는 같은 필드를 가진 객체)를 반환하는 호출 가능 객체.
ClockSource = Callable[[], "time.struct_time"]


def _hhmm(t: "time.struct_time") -> str:
    """struct_time → "HH:MM" 문자열 (예: 9시 5분 → "09:05")."""
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


# ─── Drawing helpers ───


def _draw_wordmark(draw: ImageDraw.ImageDraw) -> None:
    """패키지에 든 FLOPPYBIRD 워드마크(ASCII 아트)를 상단 중앙에 그린다 (41×7, scale=2)."""
    rows = load_ascii_art_asset()
    scale = 2
    width = len(rows[0]) * scale
    origin_x = (FRAME_WIDTH - width) // 2
    origin_y = 2
    for row_index, row in enumerate(rows):
        for column_index, pixel in enumerate(row):
            if pixel != "#":
                continue
            left = origin_x + column_index * scale
            top = origin_y + row_index * scale
            draw.rectangle(
                (left, top, left + scale - 1, top + scale - 1),
                fill=1,
            )


def _draw_loading_bar(draw: ImageDraw.ImageDraw, step: int) -> None:
    """워드마크 아래에 움직이는 스캔바를 그린다 (y=20~24)."""
    bar_left = 20
    bar_right = FRAME_WIDTH - 21
    bar_top = 20
    bar_bottom = 24
    draw.rectangle((bar_left, bar_top, bar_right, bar_bottom), outline=1)
    inner_left = bar_left + 1
    inner_width = bar_right - bar_left - 1
    for offset in range(18):
        x = inner_left + (step + offset) % inner_width
        draw.line((x, bar_top + 2, x, bar_bottom - 2), fill=1)


def _draw_clock(
    draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, hhmm: str
) -> None:
    """우상단에 "HH:MM" 시계를 그린다 (Galmuri7 size 8, 우측 1px 여백)."""
    bbox = font.getbbox(hhmm)
    text_width = bbox[2] - bbox[0]
    x = FRAME_WIDTH - text_width - 1
    draw.text((x, 0), hhmm, font=font, fill=1)


# ─── Node ABC ───


class Node(ABC):
    """모든 화면 요소의 기본. 자식 노드를 가질 수 있다 (재귀 허용, 강제 아님)."""

    @abstractmethod
    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """자기를 image buffer에 그린다."""

    @abstractmethod
    def handle_input(self, event: InputEvent) -> Optional["Node"]:
        """입력 처리. None = 현재 노드 유지, 다른 Node = 루트 교체."""

    def tick(self, dt: float) -> Optional["Node"]:
        """시간 기반 갱신. 기본 None 반환."""
        return None


class Page(Node):
    """루트 가능, 전체 512픽셀 책임. 자식 보유 가능."""
    pass


# ─── List components ───


@dataclass(frozen=True)
class Rect:
    """Cell이 그려질 영역. 화면 좌상단 origin, 픽셀 단위."""

    x: int
    y: int
    width: int
    height: int


class ListContext:
    """Cell이 상위에 화면 전환을 요청하는 통로. target = Page 팩토리."""

    def __init__(self) -> None:
        self.navigate_target: Optional[Callable[[], Page]] = None

    def navigate(self, target: Callable[[], Page]) -> None:
        self.navigate_target = target

    def consume_navigate(self) -> Optional[Callable[[], Page]]:
        target = self.navigate_target
        self.navigate_target = None
        return target


class ListCell(Node, ABC):
    """목록의 한 항목. 자기 렌더링·높이·인터랙션을 스스로 결정.

    ListComponent가 레이아웃 컨텍스트(rect, selected)를 전달하며 render_cell 호출.
    on_xxx는 bool 반환: True = 가로챔, False = 컨테이너 기본 동작.
    """

    HEIGHT: int = 9

    @abstractmethod
    def render_cell(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.ImageFont,
        rect: Rect,
        selected: bool,
    ) -> None:
        """rect 영역에 자기를 그린다. selected면 선택 마커 등 표시."""

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Node.render — Cell은 ListComponent가 호출하므로 독립 렌더 no-op."""
        pass  # ListComponent.render_cell 경유

    def on_button_1(self, ctx: ListContext) -> bool:
        return False

    def on_button_2(self, ctx: ListContext) -> bool:
        return False

    def on_button_3(self, ctx: ListContext) -> bool:
        return False

    def on_button_4(self, ctx: ListContext) -> bool:
        return False

    def on_encoder_click(self, ctx: ListContext) -> bool:
        return False

    def on_encoder_rotate(self, delta: int, ctx: ListContext) -> bool:
        """delta: +1=CW(아래로), -1=CCW(위로)."""
        return False

    # Node 인터페이스 — ListCell은 ListComponent가 입력을 라우팅하므로
    # 독립 handle_input은 no-op.
    def handle_input(self, event: InputEvent) -> Optional[Node]:
        return None


class NavItem(ListCell):
    """페이지 이동 항목. 클릭 시 target 팩토리로 새 Page 생성."""

    def __init__(self, label: str, target: Callable[[], Page]) -> None:
        self.label = label
        self.target = target

    def render_cell(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.ImageFont,
        rect: Rect,
        selected: bool,
    ) -> None:
        marker = ">" if selected else " "
        draw.text((rect.x, rect.y), f"{marker} {self.label}", font=font, fill=1)

    def on_encoder_click(self, ctx: ListContext) -> bool:
        ctx.navigate(self.target)
        return True


class ListComponent(Node):
    """항목을 세로로 배치 + 입력 라우팅. selected 상태를 자체 보유.

    Cell 우선 입력 원칙: 선택된 Cell이 먼저. True 반환 = 가로챔.
    False면 컨테이너 기본 동작 (회전=selected ±1 wrap-around).
    """

    def __init__(
        self,
        cells: list,
        *,
        origin: Tuple[int, int] = (1, 3),
        width: int = 126,
    ) -> None:
        self.cells = list(cells)
        self.origin = origin
        self.width = width
        self._selected = 0
        self._ctx = ListContext()

    @property
    def selected(self) -> int:
        return self._selected

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """cells를 세로로 배치. cell.HEIGHT로 y 누적."""
        y = self.origin[1]
        for i, cell in enumerate(self.cells):
            rect = Rect(self.origin[0], y, self.width, cell.HEIGHT)
            cell.render_cell(draw, font, rect, i == self._selected)
            y += cell.HEIGHT

    def handle_input(self, event: InputEvent) -> Optional[Node]:
        if not self.cells:
            return None
        cell = self.cells[self._selected]
        n = len(self.cells)

        if event is ENCODER_ROTATE_CW:
            if not cell.on_encoder_rotate(+1, self._ctx):
                self._selected = (self._selected + 1) % n
        elif event is ENCODER_ROTATE_CCW:
            if not cell.on_encoder_rotate(-1, self._ctx):
                self._selected = (self._selected - 1) % n
        elif event is BTN4:
            cell.on_button_4(self._ctx)
        elif event is BTN1:
            cell.on_button_1(self._ctx)
        elif event is BTN2:
            cell.on_button_2(self._ctx)
        elif event is BTN3:
            cell.on_button_3(self._ctx)
        elif event is ENCODER_CLICK:
            cell.on_encoder_click(self._ctx)

        # 모든 이벤트 처리 후 navigate 소비 — Cell이 ctx.navigate() 요청했으면 팩토리 호출
        target = self._ctx.consume_navigate()
        if target is not None:
            return target()
        return None


# ─── Pages ───


class BootPage(Page):
    """워드마크 + 로딩바. tick() 2초 후 MainPage 반환."""

    def __init__(self, clock: Optional[ClockSource] = None) -> None:
        self._clock = clock
        self._elapsed = 0.0

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        step = int(self._elapsed * 100)
        _draw_wordmark(draw)
        _draw_loading_bar(draw, step)

    def handle_input(self, event: InputEvent) -> Optional[Node]:
        return None  # 부팅 중 입력 무시 (스펙 4.2.2)

    def tick(self, dt: float) -> Optional[Node]:
        self._elapsed += dt
        if self._elapsed >= _BOOT_DURATION:
            return MainPage(clock=self._clock)
        return None


class MainPage(Page):
    """메인 메뉴. ListComponent 자식 + 우상단 시계."""

    def __init__(self, clock: Optional[ClockSource] = None) -> None:
        self._clock = clock
        self._list = ListComponent(
            [
                NavItem("MUSIC PLAYER", lambda: MusicPage(self)),
                NavItem("MINI GAME", lambda: GamePage(self)),
                NavItem("SETTINGS", lambda: SettingsPage(self)),
            ]
        )

    @property
    def selected_index(self) -> int:
        return self._list.selected

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        self._list.render(draw, font)
        if self._clock is not None:
            _draw_clock(draw, font, _hhmm(self._clock()))

    def handle_input(self, event: InputEvent) -> Optional[Node]:
        return self._list.handle_input(event)


class MusicPage(Page):
    """NOW PLAYING — 정적."""

    def __init__(self, back: Optional[Page] = None) -> None:
        self._back = back

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        draw.text((1, 2), "NOW PLAYING", font=font, fill=1)
        draw.text((1, 12), "TRACK 01", font=font, fill=1)
        # 재생바 50% — 양끝 1px 여백 (스펙 4.3 — y=24)
        draw.rectangle([1, 24, 126, 28], outline=1, fill=0)
        draw.rectangle([1, 24, 63, 28], outline=1, fill=1)

    def handle_input(self, event: InputEvent) -> Optional[Node]:
        if event is BTN4:
            return self._back
        return None


class GamePage(Page):
    """COMING SOON — 정적."""

    def __init__(self, back: Optional[Page] = None) -> None:
        self._back = back

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        draw.text((1, 12), "COMING SOON", font=font, fill=1)

    def handle_input(self, event: InputEvent) -> Optional[Node]:
        if event is BTN4:
            return self._back
        return None


class SettingsPage(Page):
    """BRIGHTNESS / CONTRAST — 정적."""

    def __init__(self, back: Optional[Page] = None) -> None:
        self._back = back

    def render(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        draw.text((1, 2), "BRIGHTNESS 50%", font=font, fill=1)
        draw.text((1, 12), "CONTRAST 50%", font=font, fill=1)

    def handle_input(self, event: InputEvent) -> Optional[Node]:
        if event is BTN4:
            return self._back
        return None

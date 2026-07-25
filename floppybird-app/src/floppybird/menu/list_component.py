"""ListComponent + ListCell — 재사용 목록 프레임워크 (이슈 #7).

설계 원칙:
- 모든 입력은 선택된 Cell이 먼저 본다. Cell이 False 반환하면 컨테이너가 기본 동작.
- Cell이 자기 높이(HEIGHT), 렌더링, 인터랙션을 결정.
- ListComponent는 레이아웃(세로 배치) + 입력 라우팅만.
- 버퍼(512바이트)는 이 모듈 밖(draw_screen/Renderer.snapshot)에서. Cell은 ImageDraw에만.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from PIL import ImageDraw, ImageFont

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

if TYPE_CHECKING:
    # 순환 import 회피 — list_component ← model ← list_component.
    # runtime엔 필요 없고 타입 힌트용만.
    from .model import ScreenKind


@dataclass(frozen=True)
class Rect:
    """Cell이 그려질 영역. 화면 좌상단 origin, 픽셀 단위."""

    x: int
    y: int
    width: int
    height: int


class ListContext:
    """Cell이 상위(MenuModel)에 화면 전환을 요청하는 통로.

    Cell은 이 객체를 통해 navigate를 호출만 하고, 실제 전환은 상위가 담당.
    Cell이 모델을 직접 조작하지 않게(결합도 낮춤).
    """

    def __init__(self) -> None:
        self.navigate_target: Optional[ScreenKind] = None

    def navigate(self, kind: ScreenKind) -> None:
        self.navigate_target = kind

    def consume_navigate(self) -> Optional[ScreenKind]:
        target = self.navigate_target
        self.navigate_target = None
        return target


class ListCell(ABC):
    """목록의 한 항목. 자기 렌더링·높이·인터랙션을 스스로 결정.

    모든 on_xxx는 bool 반환:
      True  = 이 입력을 가로챘다 (컨테이너는 기본 동작 안 함)
      False = 안 쓴다 (컨테이너가 기본 동작 — 회전이면 selected 이동, BTN4면 위로)

    예외 없음 — BTN4도 같은 패턴.
    """

    HEIGHT: int = 9  # 클래스 상수. 서브클래스가 오버라이드 (슬라이더 12 등).

    @abstractmethod
    def render(
        self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont,
        rect: Rect, selected: bool,
    ) -> None:
        """rect 영역에 자기를 그린다. selected면 선택 마커 등 표시."""

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
        """delta: +1=CW(아래로), -1=CCW(위로). 슬라이더/볼륨용."""
        return False


class NavItem(ListCell):
    """페이지 이동 항목. 클릭 시 target 화면으로 전환.

    기존 MAIN_MENU 항목("> MUSIC PLAYER")의 동작을 그대로 제공.
    """

    def __init__(self, label: str, target: ScreenKind) -> None:
        self.label = label
        self.target = target

    def render(
        self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont,
        rect: Rect, selected: bool,
    ) -> None:
        marker = ">" if selected else " "
        draw.text((rect.x, rect.y), f"{marker} {self.label}", font=font, fill=1)

    def on_encoder_click(self, ctx: ListContext) -> bool:
        ctx.navigate(self.target)
        return True


class ListComponent:
    """항목을 세로로 배치 + 입력 라우팅. 상태 없음 (서비스).

    상태(selected)는 호출자(MenuModel)가 들고, 매 호출마다 인자로 전달.
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

    def render(
        self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont,
        selected: int,
    ) -> None:
        """cells를 세로로 배치. cell.HEIGHT로 y 누적. selected에 마커는 Cell 책임."""
        y = self.origin[1]
        for i, cell in enumerate(self.cells):
            rect = Rect(self.origin[0], y, self.width, cell.HEIGHT)
            cell.render(draw, font, rect, i == selected)
            y += cell.HEIGHT

    def handle_input(
        self, event: InputEvent, selected: int, ctx: ListContext,
    ) -> Tuple[int, bool]:
        """입력 처리. 반환 (new_selected, go_up).

        원칙: 선택된 Cell이 먼저. Cell이 True 반환하면 가로챔.
        False면 컨테이너 기본 동작 (회전=selected ±1, BTN4=위로 신호).

        **범위 정책 없음** — selected가 음수/초과가 될 수 있음. wrap-around나
        클램프는 호출자가 선택 (MAIN_MENU는 %n wrap, WiFi는 스크롤+클램프).
        ListComponent는 라우팅만, 정책은 호출자.
        """
        if not self.cells:
            return selected, False
        cell = self.cells[selected]

        if event is ENCODER_ROTATE_CW:
            if cell.on_encoder_rotate(+1, ctx):
                return selected, False
            return selected + 1, False
        if event is ENCODER_ROTATE_CCW:
            if cell.on_encoder_rotate(-1, ctx):
                return selected, False
            return selected - 1, False
        if event is BTN4:
            if cell.on_button_4(ctx):
                return selected, False
            return selected, True  # "위로" 신호
        if event is BTN1:
            cell.on_button_1(ctx)
            return selected, False
        if event is BTN2:
            cell.on_button_2(ctx)
            return selected, False
        if event is BTN3:
            cell.on_button_3(ctx)
            return selected, False
        if event is ENCODER_CLICK:
            cell.on_encoder_click(ctx)
            return selected, False
        return selected, False

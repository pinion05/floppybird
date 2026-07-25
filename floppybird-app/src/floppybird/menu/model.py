"""VFD 메뉴 상태 기계 — VFD/렌더링에 독립적인 순수 Python 모델."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from .input import ENCODER_CLICK, ENCODER_ROTATE_CCW, ENCODER_ROTATE_CW, BTN4, InputEvent
from .list_component import ListComponent, ListContext, NavItem

_BOOT_DURATION = 2.0

# 벽시계 소스 — struct_time(또는 같은 필드를 가진 객체)를 반환하는 호출 가능 객체.
ClockSource = Callable[[], "time.struct_time"]


def _hhmm(t: "time.struct_time") -> str:
    """struct_time → "HH:MM" 문자열 (예: 9시 5분 → "09:05")."""
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


class ScreenKind(Enum):
    BOOT = auto()
    MAIN_MENU = auto()
    MUSIC = auto()
    GAME = auto()
    SETTINGS = auto()


# MAIN_MENU 항목 — NavItem으로 구성. (이슈 #7 이전엔 _MAIN_ITEMS 개수 + _MAIN_TARGETS
# 리스트가 분리되어 있었음. ListComponent 도입으로 항목 정의가 한 곳에 모임.)
# 항목 추가/순서 변경은 이 리스트만 고치면 됨.
_MAIN_ITEMS: list = [
    NavItem("MUSIC PLAYER", ScreenKind.MUSIC),
    NavItem("MINI GAME", ScreenKind.GAME),
    NavItem("SETTINGS", ScreenKind.SETTINGS),
]


@dataclass(frozen=True)
class Screen:
    kind: ScreenKind
    index: int = 0
    boot_elapsed: float = 0.0
    # "HH:MM" 벽시계 — 상태바 렌더링용. BOOT 직후에만 설정되고,
    # BOOT 중에는 아직 시계를 그리지 않는 단계라 None.
    now_hhmm: Optional[str] = None


class MenuModel:
    """메뉴 상태. 입력 부품(InputSource)을 모름 — 이벤트만 받는다.

    MAIN_MENU 입력 처리는 ListComponent에 위임. 상태(_index)는 모델이 소유,
    ListComponent는 상태 없는 서비스 — 호출 시 selected를 인자로 전달.
    """

    def __init__(self, clock: ClockSource = time.localtime) -> None:
        self._clock = clock
        self._kind = ScreenKind.BOOT
        self._index = 0
        self._boot_elapsed = 0.0
        # 부팅 진입 시각을 "고정" 시계로 씀 (부팅은 2초라 매 프레임 갱신할 필요 없음).
        self._boot_hhmm: Optional[str] = _hhmm(self._clock())
        # MAIN_MENU용 ListComponent — 상태 없는 서비스. 항목 리스트 고정.
        self._main_list = ListComponent(_MAIN_ITEMS)
        self._main_ctx = ListContext()

    def handle_input(self, event: InputEvent) -> None:
        if self._kind is ScreenKind.BOOT:
            return  # 부팅 중 입력 무시 (스펙 4.2.2)
        if self._kind is ScreenKind.MAIN_MENU:
            self._handle_main(event)
        else:
            self._handle_sub(event)

    def _handle_main(self, event: InputEvent) -> None:
        # ListComponent에 위임. Cell 우선 입력 라우팅.
        new_selected, _go_up = self._main_list.handle_input(
            event, self._index, self._main_ctx
        )
        n = len(_MAIN_ITEMS)
        # wrap-around는 모델 책임 (ListComponent는 min/max 클램프만).
        self._index = new_selected % n if n else 0
        # Cell이 navigate 요청했으면 화면 전환 (NavItem 클릭 → MUSIC/GAME/SETTINGS).
        target = self._main_ctx.consume_navigate()
        if target is not None:
            self._kind = target
        # go_up 신호는 MAIN_MENU 자체가 최상위라 의미 없음 — 서브에서만.

    def _handle_sub(self, event: InputEvent) -> None:
        if event is BTN4:  # 뒤로 (스펙 4.2.2)
            self._kind = ScreenKind.MAIN_MENU

    def tick(self, dt: float) -> None:
        if self._kind is ScreenKind.BOOT:
            self._boot_elapsed += dt
            if self._boot_elapsed >= _BOOT_DURATION:
                self._kind = ScreenKind.MAIN_MENU
        # 시계는 tick에서 갱신하지 않고 current_screen()에서 그때그때 읽어온다.
        # (BOOT는 고정값 _boot_hhmm 사용.)

    def current_screen(self) -> Screen:
        # BOOT: 부팅 진입 시각 고정. 그 외: 현재 시각 실시간.
        hhmm = self._boot_hhmm if self._kind is ScreenKind.BOOT else _hhmm(self._clock())
        return Screen(
            kind=self._kind,
            index=self._index,
            boot_elapsed=self._boot_elapsed,
            now_hhmm=hhmm,
        )

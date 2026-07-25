"""VFD 메뉴 상태 기계 — VFD/렌더링에 독립적인 순수 Python 모델."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from .input import ENCODER_CLICK, ENCODER_ROTATE_CCW, ENCODER_ROTATE_CW, BTN4, InputEvent

_BOOT_DURATION = 2.0
_MAIN_ITEMS = 3  # MUSIC, GAME, SETTINGS

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


# MAIN_MENU 인덱스 → 하위 화면 매핑 (스펙 4.2.1)
_MAIN_TARGETS = [ScreenKind.MUSIC, ScreenKind.GAME, ScreenKind.SETTINGS]


@dataclass(frozen=True)
class Screen:
    kind: ScreenKind
    index: int = 0
    boot_elapsed: float = 0.0
    # "HH:MM" 벽시계 — 상태바 렌더링용. BOOT 직후에만 설정되고,
    # BOOT 중에는 아직 시계를 그리지 않는 단계라 None.
    now_hhmm: Optional[str] = None


class MenuModel:
    """메뉴 상태. 입력 부품(InputSource)을 모름 — 이벤트만 받는다."""

    def __init__(self, clock: ClockSource = time.localtime) -> None:
        self._clock = clock
        self._kind = ScreenKind.BOOT
        self._index = 0
        self._boot_elapsed = 0.0
        # 부팅 진입 시각을 "고정" 시계로 씀 (부팅은 2초라 매 프레임 갱신할 필요 없음).
        self._boot_hhmm: Optional[str] = _hhmm(self._clock())

    def handle_input(self, event: InputEvent) -> None:
        if self._kind is ScreenKind.BOOT:
            return  # 부팅 중 입력 무시 (스펙 4.2.2)
        if self._kind is ScreenKind.MAIN_MENU:
            self._handle_main(event)
        else:
            self._handle_sub(event)

    def _handle_main(self, event: InputEvent) -> None:
        if event is ENCODER_ROTATE_CW:
            self._index = (self._index + 1) % _MAIN_ITEMS
        elif event is ENCODER_ROTATE_CCW:
            self._index = (self._index - 1) % _MAIN_ITEMS
        elif event is ENCODER_CLICK:
            self._kind = _MAIN_TARGETS[self._index]

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

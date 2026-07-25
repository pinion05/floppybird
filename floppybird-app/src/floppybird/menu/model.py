"""VFD 메뉴 상태 기계 — thin MenuModel. root Node만 보유 (이슈 #9).

모든 페이지 상태는 각 Page 인스턴스 안에. MenuModel은 루트만 들고,
handle_input/tick 결과로 새 Node가 반환되면 루트 교체.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from .input import InputEvent
from .nodes import BootPage, ClockSource, Node, Page

ClockSource = Callable[[], "time.struct_time"]


class MenuModel:
    """메뉴 상태. root Node만 보유. 입력/시간 → Node에 위임."""

    def __init__(self, clock: ClockSource = time.localtime) -> None:
        self._clock = clock
        self._root: Node = BootPage(clock=clock)

    @property
    def root(self) -> Node:
        return self._root

    def handle_input(self, event: InputEvent) -> None:
        nxt = self._root.handle_input(event)
        if nxt is not None:
            self._root = nxt

    def tick(self, dt: float) -> None:
        nxt = self._root.tick(dt)
        if nxt is not None:
            self._root = nxt

    def current_root(self) -> Node:
        """렌더링용 root 반환. 시계는 Page가 clock 소스에서 직접 읽어 그림."""
        return self._root

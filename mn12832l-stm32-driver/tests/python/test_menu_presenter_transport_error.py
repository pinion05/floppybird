"""P4 회귀: present()는 TransportError를 전파하지 않고 PresentedFrame로 반환해야 한다.

배경: DigitalTwinTransport._read_response(twin.py)와 SubprocessTransport._read_exact
(transport.py)는 C twin 프로세스가 타임아웃/크래시/비정상 종료할 때 TransportError
계열을 raise한다. MenuApp.tick(app.py)은 present() 반환값만 소비하므로, 예외가
새어나가면 self._root.after() 재스케줄이 안 돼 미리보기 창이 에러 UI도 없이 멈춘다.
"""

from __future__ import annotations

import unittest

from mn12832l.menu.model import Screen, ScreenKind
from mn12832l.menu.presenter import MenuPresenter
from mn12832l.transport import TransportError


class _FailingTransport:
    """FrameTransport 호환 stub: request()가 항상 TransportError를 뱉는다."""

    last_result = None

    def open(self) -> None:
        pass

    def request(self, packet: bytes) -> bytes:
        raise TransportError("simulated twin process crash")

    def close(self) -> None:
        pass


def _make_presenter_with_failing_transport() -> MenuPresenter:
    presenter = MenuPresenter(engine="/nonexistent/never-spawned")
    failing = _FailingTransport()
    presenter._transport = failing
    presenter._display._transport = failing
    return presenter


class PresenterTransportErrorTests(unittest.TestCase):
    def test_present_returns_failure_frame_on_transport_error(self) -> None:
        """TransportError를 잡아 twin_passed=False PresentedFrame로 반환해야 한다."""
        presenter = _make_presenter_with_failing_transport()
        presenter.open()
        try:
            result = presenter.present(Screen(ScreenKind.BOOT))
        except TransportError as exc:
            self.fail(
                f"present() must not propagate TransportError "
                f"(would freeze MenuApp.tick): {exc}"
            )
        self.assertFalse(result.twin_passed, "transport error must read as twin failure")
        self.assertIsNotNone(result.error, "error string must surface to UI")
        self.assertIn("simulated", result.error)


if __name__ == "__main__":
    unittest.main()

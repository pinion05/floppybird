"""P4 회귀: present()는 TransportError를 전파하지 않고 PresentedFrame로 반환해야 한다."""

from __future__ import annotations

import unittest

from floppybird.menu.nodes import BootPage
from floppybird.menu.presenter import MenuPresenter
from mn12832l.transport import TransportError


class _FailingTransport:
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
        presenter = _make_presenter_with_failing_transport()
        presenter.open()
        try:
            result = presenter.present(BootPage())
        except TransportError as exc:
            self.fail(
                f"present() must not propagate TransportError "
                f"(would freeze MenuApp.tick): {exc}"
            )
        self.assertFalse(result.twin_passed)
        self.assertIsNotNone(result.error)
        self.assertIn("simulated", result.error)


if __name__ == "__main__":
    unittest.main()

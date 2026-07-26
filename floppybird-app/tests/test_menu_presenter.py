"""presenter 테스트 — Node 트리 기반 (이슈 #9)."""

import os
import unittest

from floppybird.menu.nodes import BootPage, GamePage, MainPage, MusicPage, SettingsPage
from floppybird.menu.presenter import MenuPresenter


@unittest.skipUnless(
    os.environ.get("MN12832L_SYSTEM_TWIN"),
    "MN12832L_SYSTEM_TWIN is not configured",
)
class PresenterWithSystemTwinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = os.environ["MN12832L_SYSTEM_TWIN"]

    def test_boot_frame_passes_twin_verification(self) -> None:
        presenter = MenuPresenter(engine=self.engine)
        presenter.open()
        try:
            result = presenter.present(BootPage())
        finally:
            presenter.close()
        self.assertTrue(result.twin_passed, f"twin failed: {result.error}")
        self.assertEqual(len(result.verified_frame), 512)
        self.assertIsNotNone(result.stats)

    def test_all_pages_pass_twin(self) -> None:
        nodes = [
            BootPage(),
            MainPage(),
            MusicPage(),
            GamePage(),
            SettingsPage(),
        ]
        presenter = MenuPresenter(engine=self.engine)
        presenter.open()
        try:
            for node in nodes:
                result = presenter.present(node)
                self.assertTrue(
                    result.twin_passed, f"{type(node).__name__}: {result.error}"
                )
        finally:
            presenter.close()

    def test_identical_node_produces_identical_verified_frame(self) -> None:
        presenter = MenuPresenter(engine=self.engine)
        presenter.open()
        try:
            first = presenter.present(GamePage())
            second = presenter.present(GamePage())
            self.assertTrue(first.twin_passed)
            self.assertTrue(second.twin_passed)
            self.assertEqual(first.verified_frame, second.verified_frame)
        finally:
            presenter.close()


class PresenterErrorHandlingTests(unittest.TestCase):
    def test_missing_engine_raises_on_open(self) -> None:
        with self.assertRaises(Exception):
            presenter = MenuPresenter(engine="/nonexistent/twin")
            presenter.open()


if __name__ == "__main__":
    unittest.main()

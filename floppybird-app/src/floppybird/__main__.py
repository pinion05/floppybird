"""`python -m floppybird` 진입점 — 메뉴 미리보기 창 실행."""

from __future__ import annotations

import os
import sys
import tkinter as tk

from .menu.app import MenuApp


def main() -> int:
    engine = os.environ.get("MN12832L_SYSTEM_TWIN")
    if not engine:
        print("MN12832L_SYSTEM_TWIN 환경변수가 필요합니다.", file=sys.stderr)
        print("예: 루트 ./run 스크립트 사용, 또는", file=sys.stderr)
        print(
            "    MN12832L_SYSTEM_TWIN=/path/to/vfd_system_twin python -m floppybird",
            file=sys.stderr,
        )
        return 2

    root = tk.Tk()
    app = MenuApp(root, engine=engine)
    app.setup()
    app.start()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

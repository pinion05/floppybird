"""Node → 512바이트 MVLSB 프레임. Galmuri7 폰트 사용 (스펙 2.1, 4.3)."""

from __future__ import annotations

import io
from functools import lru_cache
from importlib import resources

from PIL import Image, ImageDraw, ImageFont

from mn12832l import FRAME_HEIGHT, FRAME_WIDTH, MvlsbRenderer

from .nodes import Node


@lru_cache(maxsize=4)
def _font(size: int = 8) -> ImageFont.ImageFont:
    """패키지에 든 Galmuri7.ttf를 importlib.resources로 로드 (wheel/zipapp 호환).

    assets는 mn12832l 패키지 루트에 있으므로 상위 디렉토리 순회(joinpath('..')) 없이
    'mn12832l'에서 직접 참조한다 — joinpath('..')는 zipapp/zipimport 안에서
    정규화되지 않아 실패한다.

    리소스를 read_bytes()로 읽어 io.BytesIO에 담아 Pillow에 전달한다. 이 방식은
    (1) str(Traversable)이 실제 파일 경로가 아니라 zip 안 경로라 ImageFont.truetype
    이 못 여는 문제를 피하고, (2) as_file() 컨텍스트 매니저의 임시 파일 수명 문제를
    회피하면서 @lru_cache를 유지할 수 있게 한다 (BytesIO는 seek(0) 후 재사용 가능).
    """
    try:
        data = (
            resources.files("mn12832l")
            .joinpath("assets")
            .joinpath("Galmuri7.ttf")
            .read_bytes()
        )
        return ImageFont.truetype(io.BytesIO(data), size)
    except OSError:
        return ImageFont.load_default()


def draw_root(root: Node, renderer: MvlsbRenderer) -> bytes:
    """root Node를 framebuffer에 그리고 512바이트 snapshot 반환."""
    image = Image.new("1", (FRAME_WIDTH, FRAME_HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    font = _font(8)

    root.render(draw, font)

    renderer.load_image(image)
    return renderer.snapshot()

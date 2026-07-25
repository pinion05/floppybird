# floppybird-app

Floppybird VFD 메뉴 애플리케이션. Fallout 컨셉의 메뉴 시스템 + Tkinter 미리보기.

`mn12832l-vfd` 드라이버(디스플레이 하드웨어 추상화 + 디지털 트윈) 위에 올라가는
애플리케이션 계층이다. 드라이버의 공개 API(`display`, `transport`, `twin`,
`renderer`, `protocol`)만 import한다.

## 실행

루트 `floppybird/` 디렉토리에서 `./run`. 자세한 건 루트 `README.md` 참고.

## 패키지 구조

```
floppybird-app/
├── pyproject.toml
└── src/floppybird/
    ├── __init__.py
    ├── __main__.py          ← python -m floppybird
    └── menu/
        ├── app.py           ← Tkinter 미리보기 창
        ├── presenter.py     ← Screen → 검증된 프레임
        ├── model.py         ← 메뉴 상태 기계
        ├── render.py        ← Screen → 512바이트 MVLSB
        ├── input.py         ← InputSource 추상화
        └── tk_source.py     ← TkinterSource 구현
```

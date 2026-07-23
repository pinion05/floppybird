# Floppybird

이 디렉토리는 **Floppybird** 프로젝트 루트입니다.
Floppybird는 노션 워크스페이스 **명떨이와 재민이의 우당탕탕 으라샤 작업실** 아래에서 진행 중인 프로젝트이며, 이 디렉토리에는 해당 프로젝트에서 사용할 라이브러리 코드가 포함됩니다.

## Notion 구조

```
🐙 명떨이와 재민이의 우당탕탕 으라샤 작업실  (workspace root)
│   id: 39eefc9d-ad50-8...
└── 💾 Floppybird
    │   id: 3daefc9d-ad50-8276-9f32-01edf052db75
    │   https://www.notion.so/Floppybird-3daefc9dad5082769f32f01edf052db75
    ├── 📊 개발현황
    ├── 📚 레퍼런스
    └── ⚙️ Hardware
```

## 하위 프로젝트

- **`mn12832l-stm32-driver/`** — MN12832L 128×32 VFD 디스플레이용 STM32 드라이버 라이브러리.
  Python 호스트 스택(프레임 프로토콜, 디지털 트윈), STM32F0 펌웨어(스캔 드라이버, 호스트 링크 수신기), 핀 레벨 디지털 트윈을 포함.
  세부 내용은 해당 디렉토리의 `README.md`와 `docs/` 참고.

## Notion CLI

`notion` CLI로 위 페이지에 접근 가능 (이미 인증됨).

```sh
notion page view 3daefc9d-ad50-8276-9f32-01edf052db75   # Floppybird
notion search "Floppybird"
```

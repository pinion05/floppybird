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

---

## 에이전트 규칙

### PR 전 cua 테스트 (절대 규칙)

**PR을 올리기 전에 반드시 cua-driver로 실제 동작을 검증한다.** 예외 없음.

적용 범위: Tkinter 미리보기 창의 레이아웃·입력·상태 전환 등 **눈에 보이는 동작**을 바꾸는 변경. 단위 테스트만으로는 "코드가 돈다"는 것만 증명할 뿐, "사용자가 보는 화면이 맞다"를 증명하지 못한다.

절차:
1. cua-driver 데몬 시작 (`cua-driver serve`)
2. 미리보기 앱 실행 후 `list_windows` / `get_window_state`로 창 캡처
3. 변경된 부분이 스크린샷에 정상 반영되었는지 확인 (필요시 `analyze_image`로 교차 검증)
4. 입력 인터랙션이 필요한 변경이면, 실제 클릭/타이핑 후 before/after diff로 효과 확인
5. cua-driver pixel click이 안 닿는 위젯(tkinter Button 등 synthetic event를 무시하는 경우)은 프로그래밍적 이벤트 주입으로 우회하되, 그 사실을 PR 본문에 명시
6. 스크린샷을 저장소에 커밋해 PR 본문에 포함 (raw URL로 참조)

"샌드박스라서 cua를 못 돌렸다" 같은 핑계 금지. 환경 문제면 먼저 해결하거나 사용자에게 보고한다. cua 검증 없이 PR을 올린 경우, 머지 전 반드시 보충한다.

### 앱/드라이버 패키지 분리 유지

- **드라이버**(`mn12832l-stm32-driver/`) — 디스플레이 하드웨어 추상화 + 호스트 스택 + 디지털 트윈
- **앱**(`floppybird-app/`) — Fallout 컨셉 메뉴 + Tkinter 미리보기, 드라이버에 의존

앱은 드라이버 공개 API만 import한다 (`from mn12832l import ...`). 드라이버 내부 모듈을 `mn12832l.display`, `mn12832l.twin` 형태로 직접 import하지 않는다. 역방향(드라이버→앱) 의존은 금지.

### Node 트리 아키텍처 (이슈 #9, PR #10)

메뉴 화면은 **Composite 패턴 Node 트리**로 구성. `ScreenKind` enum은 폐지됨.

```text
Node (ABC) — render / handle_input → Optional[Node] / tick → Optional[Node]
├── Page (ABC) — 루트 가능, 전체 512px 책임
│   ├── BootPage      — tick 2초 후 MainPage 반환
│   ├── MainPage      — ListComponent 자식 + 시계
│   ├── MusicPage     — BTN4 → back Page 반환
│   ├── GamePage      — BTN4 → back Page 반환
│   └── SettingsPage  — BTN4 → back Page 반환
├── ListComponent     — selected 자체 보유, Cell 우선 입력 라우팅
└── ListCell (ABC)    — render_cell(rect, selected), on_xxx bool 반환
    └── NavItem       — on_encoder_click → ctx.navigate(팩토리)
```

규칙:
- 화면 식별은 `isinstance(node, PageClass)`. enum 금지.
- 페이지 이동은 `Callable[[], Page]` 팩토리. `ScreenKind` 값 전달 금지.
- `MenuModel`은 root Node만 보유. `handle_input`/`tick` 반환값으로 root 교체.
- 새 Page 추가 시: `nodes.py`에 Page 클래스 추가, `NavItem`에 팩토리 등록.
- `ListComponent`는 selected 상태를 자체 보유. 외부에서 인자로 전달하지 않는다.

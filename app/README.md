# SimTrust 화면 초안 (Streamlit)

창업자가 자기 서비스를 가상 사용자에게 평가받는 서비스.

스토리보드(UI 설계서)와 중간발표 캡처용 초안. 데이터는 전부 `mock.py`의 목업이고 숫자는 예시.

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 구조
```
app.py            # 사이드바(서비스 선택) + 메뉴 3그룹 네비게이션
ui.py             # 공통: 경로 표시, 단계 진행 바, 칩
mock.py           # 목업 데이터, 판정 규칙(TRUST_RULES), verdict()·f1()
views/
  service_list.py   ST-SV-101  서비스 목록
  snapshot.py       ST-SV-102  스냅샷 등록
  personas.py       ST-PS-201  페르소나 세트
  run_setup.py      ST-SM-301  실행 설정
  issue_cards.py    ST-SM-302  이슈 카드
  report.py         ST-RP-500  서비스 리포트 (문제점·막힌 화면·개선 제안)
  dashboard.py      ST-RP-501  지표 대시보드
  trust_map.py      ST-RP-502  신뢰도 지도
```

## 레포에 넣는 위치
레포 루트에 `app/` 폴더로 넣는다. 그러면 페르소나를 복사하지 않고 실험 폴더를 바로 읽는다.
```
Simtrust/
├── app/                                  ← 이 폴더
├── experiments/
│   ├── personas_nemotron_korea/personas/ ← 여기 JSON을 그대로 읽음
│   └── smoke_ko/
└── scripts/
```
경로가 다르면 `SIMTRUST_PERSONA_DIR=경로 streamlit run app/app.py` 로 덮어쓴다.
파일이 없으면 자동으로 목업을 쓰고, 화면에 어느 쪽인지 표시된다.

## 실제 데이터 붙이기
- 페르소나: TinyTroupe 저장 형식(`{"type": "TinyPerson", "persona": {...}}`)과 평평한 dict 둘 다 읽음
- 판정 기준: `mock.TRUST_RULES` 값만 바꾸면 신뢰도 지도 판정이 따라 바뀜
- 이슈 카드: `experiments/smoke_ko/results` 형식 확인 후 연결 예정

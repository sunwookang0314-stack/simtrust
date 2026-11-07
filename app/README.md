# SimTrust 조회 전용 데모 (Streamlit)

7주차 스토리보드(UI 설계서) 캡처와 8주차 중간발표 시연용 화면. TRD v0.1 구조를 따른다.
CLI 명령(IF-03~IF-13)이 만든 JSON·CSV를 Streamlit이 **읽어서 보여주기만** 한다는 가정이라,
화면에는 입력 폼·실행 버튼·계산·저장이 없다. 숫자는 전부 예시값이다.

## 실행
레포 루트에서:
```bash
pip install -r app/requirements.txt
streamlit run app/main.py --server.address localhost
```
테마·툴바 설정은 레포 루트 `.streamlit/config.toml`에서 읽는다.

## 구조
```
app/
  main.py        # 사이드바(서비스·조건·메뉴·데모 상태·캡처 모드) + 페이지 등록
  ui.py          # SCREENS(화면 번호·ID·출처·상태 목록), 헤더, 단계 바, 다음 버튼, 칩, 공통 CSS
  demo_data.py   # 모든 화면이 쓰는 고정 숫자 (유일한 출처) + 페르소나 로더
  views/         # 화면 11개 (p1_1_snapshot.py … p5_1_mvp_check.py)
```
- 숫자는 `demo_data.py`에만 있다. import 할 때 `_check()`가 합계가 맞는지 확인한다 (예: 조건별 일치+유효 추가+허위+판단 불가 = 가상 이슈).
- 페르소나만 실제 파일을 읽는다: `experiments/personas_nemotron_korea/personas/` 의 JSON 30명에서 서비스별 재학생 5 + 취준생 5를 시드 42로 고정 추출. 파일이 없으면 고정 목업 10명. 경로는 `SIMTRUST_PERSONA_DIR`로 바꿀 수 있다.

## 데모 상태 · 캡처 모드
- 상태가 있는 화면은 사이드바 "데모 상태"에서 고르거나 URL `?state=코드`로 바로 연다.
- 사이드바 맨 아래 **캡처 모드**를 켜면 "데모 화면 · 숫자는 예시" 문구와 상태 선택기가 숨는다.
- 모든 상태는 1440×900 창에서 스크롤 없이 들어오게 맞췄다.
- 하단 오른쪽 "다음" 버튼으로 1-1 → … → 5-1 → 1-1 순서로 넘어간다.

## 스토리보드 캡처 체크리스트 (23개)
1-1은 기본 페이지라 주소가 `/`이다.

| 화면 번호 | 화면 | 상태 | URL | 캡처 |
|---|---|---|---|---|
| 1-1 | 서비스·스냅샷 | 기본 | http://localhost:8501/ | ☐ |
| 1-1 | 서비스·스냅샷 | E1 · 화면 변경 감지 | http://localhost:8501/?state=E1 | ☐ |
| 1-2 | 정답지 | 기본 | http://localhost:8501/groundtruth | ☐ |
| 1-2 | 정답지 | E2 · 녹취 없는 세션 | http://localhost:8501/groundtruth?state=E2 | ☐ |
| 1-3 | 페르소나 세트 | 기본 | http://localhost:8501/personas | ☐ |
| 1-3 | 페르소나 세트 | E3 · 후보 부족 중단 | http://localhost:8501/personas?state=E3 | ☐ |
| 2-1 | 실행 기록 | 기본 | http://localhost:8501/runs | ☐ |
| 2-1 | 실행 기록 | E4 · 비용 상한 도달 | http://localhost:8501/runs?state=E4 | ☐ |
| 2-2 | 이슈 카드 | 목록 | http://localhost:8501/issue-cards | ☐ |
| 2-2 | 이슈 카드 | 상세 | http://localhost:8501/issue-cards?state=detail | ☐ |
| 2-2 | 이슈 카드 | E5 · 지적 없음·파싱 실패 | http://localhost:8501/issue-cards?state=E5 | ☐ |
| 3-1 | 가상 이슈 묶기 | 기본 | http://localhost:8501/grouping | ☐ |
| 3-2 | 이슈 매칭 판정 | 기본 | http://localhost:8501/matching | ☐ |
| 3-2 | 이슈 매칭 판정 | E6 · CSV 검증 실패 | http://localhost:8501/matching?state=E6 | ☐ |
| 3-2 | 이슈 매칭 판정 | E7 · 일치도 미달 | http://localhost:8501/matching?state=E7 | ☐ |
| 4-1 | 지표 대시보드 | 기본 | http://localhost:8501/dashboard | ☐ |
| 4-1 | 지표 대시보드 | E8 · 계산 불가 칸 | http://localhost:8501/dashboard?state=E8 | ☐ |
| 4-2 | 신뢰도 지도 (창업자) | 기본 | http://localhost:8501/trust-map | ☐ |
| 4-2 | 신뢰도 지도 (창업자) | 조건 0과 비교 | http://localhost:8501/trust-map?state=c0 | ☐ |
| 4-3 | 시장성 비교 | 기본 | http://localhost:8501/market | ☐ |
| 4-3 | 시장성 비교 | E10 · 표본 적음 | http://localhost:8501/market?state=E10 | ☐ |
| 5-1 | 점검 결과 (창업자) | 기본 | http://localhost:8501/mvp-check | ☐ |
| 5-1 | 점검 결과 (창업자) | E11 · 유형 다름 | http://localhost:8501/mvp-check?state=E11 | ☐ |

# SimTrust 기말 화면 (React + Vite)

담당: 김승하. 계획은 `docs/work-orders/kim-seungha/할일.md` 3-1.

## 실행
```
cd web
npm install
npm run dev      # http://localhost:5173/
npm run build    # dist/ (상대 경로라 GitHub Pages 하위 폴더에서도 열림)
```

## 화면
1~6은 벤치마크 검증(이번 학기 본편), 7은 새 MVP 점검(학기 범위 밖, 미리보기)이다.

| 주소 | 화면 | 상태 |
|---|---|---|
| `#/` | 0 메인 | 디자인 |
| `#/service?service=&platform=` | 1 서비스 고르기 (링커리어·캠퍼스픽, 앱·웹, 기능 4개 화면) | 그린 화면. `public/captures/`에 실제 캡처를 넣으면 그걸 띄움 (비공개, 커밋 안 됨) |
| `#/ask?service=&platform=` | 2 AI에게 묻기 (GPT·Claude·Gemini + AI+페르소나) | 장면 동작, 답은 지어낸 예시 |
| `#/extract` | 3 이유 뽑기 (화면 2 답 → 이유 줄) | 동작, 예시 답 |
| `#/coding` | 4 코드 붙이기 (판정자 2명, kappa, 가림 보기) | 동작, 코드북 v0.1 실제 코드 |
| `#/reasons?service=&feature=&kind=&ai=` | 5 거름망 (① 사람 설문, ② 다수결) | 가짜 견본으로 동작 |
| `#/map?service=&kind=` | 6 신뢰도 지도 | 가짜 견본으로 동작 |
| `#/mvp` | 7 새 MVP 점검 | 미리보기 틀 (#32 대기) |

## 데이터
- `src/lib/examples.js`: 화면 2~4가 같이 쓰는 예시 답·이유 줄·판정자 코드 (지어낸 것)
- `public/data/codebook_v0.1.csv`: 코드북 v0.1 (화면 4의 코드 이름·정의)
- `public/data/sample/`: 판정 계산기(`scripts/score_reasons.py`) 출력 형식의 가짜 견본 (`experiments/demo_sample/out/`, 김민우)
- 실제 결과가 나오면 같은 이름의 `cells_*.csv`, `reasons_*.csv`로 바꾸면 된다. 읽는 코드는 `src/lib/data.js`
- 응답 원문은 넣지 않는다. 계산기 결과(코드와 숫자)만 쓴다

## 구조
- `src/lib/` 데이터 읽기, 판정 색, 화면 순서, 주소 파라미터
- `src/components/` 판정 배지, 통과율·재현율 막대, 이유 칩, 칸 고르기 (개념 애니메이션 부품)
- `src/pages/` 화면 0~6

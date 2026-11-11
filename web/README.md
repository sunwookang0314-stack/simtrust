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
| 주소 | 화면 | 상태 |
|---|---|---|
| `#/` | 0 메인 | 디자인 |
| `#/input` | 1 검사할 화면 넣기 | 틀 (#32 입력 방식 대기) |
| `#/ask` | 2 AI 셋에게 묻기 | 틀 |
| `#/extract` | 3 답 → 이유 추출 | 틀 |
| `#/coding` | 4 코드 붙이기 | 틀 (데모 방식 대기) |
| `#/reasons?service=&feature=&kind=` | 5 이유별 판정 (AI 셋 나란히) | 가짜 견본으로 동작 |
| `#/map?service=&kind=` | 6 신뢰도 지도 | 가짜 견본으로 동작 |

## 데이터
- `public/data/sample/`: 판정 계산기(`scripts/score_reasons.py`) 출력 형식의 가짜 견본 (`experiments/demo_sample/out/`, 김민우)
- 실제 결과가 나오면 같은 이름의 `cells_*.csv`, `reasons_*.csv`로 바꾸면 된다. 읽는 코드는 `src/lib/data.js`
- 응답 원문은 넣지 않는다. 계산기 결과(코드와 숫자)만 쓴다

## 구조
- `src/lib/` 데이터 읽기, 판정 색, 화면 순서, 주소 파라미터
- `src/components/` 판정 배지, 통과율·재현율 막대, 이유 칩, 칸 고르기 (개념 애니메이션 부품)
- `src/pages/` 화면 0~6

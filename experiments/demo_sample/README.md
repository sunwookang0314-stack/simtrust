# 기말 데모 견본 표 (가짜 데이터)

- 작성: 김민우, 2026-11-06
- 전부 가짜다. 실제 응답도, 실제 AI 답도 아니다. 기말 데모(#35) 화면 틀을 먼저 잡을 수 있게 만들었다
- 같이 확인한 것: 폼 응답 CSV부터 정리 시트, 사람 코드, 판정 계산기까지 사람 쪽 흐름이 끝까지 이어진다
- 표의 칸 이름은 실제 결과에서도 같다. 숫자만 바뀐다

```
python experiments/demo_sample/make_demo_sample.py
```

10초쯤 걸리고 `out/`을 다시 만든다.

## 가짜 설정

- 서비스 2곳(linkareer, campuspick) x 응답자 40명, 기능 4개 (폼 B v2 4-3 행)
- 사람 이유 분포는 사람 수 시뮬레이션과 같은 가정(공통 이유 60%)이다 (`experiments/sample_size_sim/`)
- AI는 조건 0(페르소나 없음)이고 모델 셋을 흉내 냈다. 실제 데모에서는 GPT, Claude, Gemini 자리다

| 파일 이름 | 흉내 낸 모델 |
|---|---|
| `model_a` | 사람과 같은 분포로 이유를 대는 모델 |
| `model_b` | 절반은 사람이 안 말하는 이유를 대는 모델 |
| `model_c` | "필요 없어서" 같은 공통 이유만 대는 모델 |

## 파일

| 파일 | 내용 |
|---|---|
| `out/reasons_model_*.csv` | 이유 한 줄씩. #35 화면의 이유 목록 |
| `out/cells_model_*.csv` | 칸(서비스 x 기능 x 쓸/안 쓸)마다 숫자와 판정 |
| `out/codebook_fake.csv` | 가짜 코드북 (code, scope, name) |
| `out/summary.json` | 모델별 안 쓸 이유 칸 판정 수 |

## reasons 표 칸

| 칸 | 뜻 |
|---|---|
| scope | `main`이면 본 칸, `platform_ref`면 플랫폼별 참고 칸. 화면에는 `main`만 써도 된다 |
| service, feature_id | 서비스, 기능(F1~F4) |
| platform | `*`면 앱·웹을 합친 칸 |
| kind | `use` 쓸 이유, `nouse` 안 써본 사람의 안 쓸 이유, `nouse_quit` 그만둔 사람의 안 쓸 이유(참고) |
| type | `ai_reason`은 AI가 말한 이유, `missed`는 사람은 말했는데 AI가 안 말한 이유 |
| code, name | 코드북 코드와 이름 |
| common | Y면 어느 기능에나 나오는 공통 이유 |
| ai_episodes_with_code / ai_episodes | AI를 몇 번 돌려서 몇 번 이 이유를 말했나 |
| human_count / n_humans | 응답자 몇 명 중 몇 명이 같은 이유를 말했나 |
| passed | Y면 응답자 중 같은 이유를 말한 사람이 있다 (초안 기준 1명 이상) |
| basis | 화면에 그대로 쓸 근거 문장. "응답자 14명 중 6명이 같은 이유를 말함" |

## cells 표에서 쓸 칸

| 칸 | 뜻 |
|---|---|
| n_humans | 그 칸에 답한 응답자 수 |
| precision, recall | 통과율, 재현율 |
| precision_nocommon, recall_nocommon | 공통 이유를 빼고 잰 통과율, 재현율. 판정에는 안 쓴다 |
| verdict | 믿고 써도 됨 / 참고용 / 사람에게 물어볼 것 / 자료 부족 / 계산 불가 |
| human_precision_low, human_precision_high | 사람끼리 범위 |
| floor_precision_low, floor_precision_high | 아무 기능에나 할 말 범위 |

## #35 화면으로 옮기는 법 [제안]

1. 이유 목록: reasons에서 `scope=main`, `type=ai_reason`인 줄의 `name`과 `basis`. `passed`가 Y면 "믿을 만함", N이면 "믿기 어려움"
2. AI가 놓친 이유: `type=missed`인 줄
3. 기능마다 판정: cells의 `verdict`
4. AI끼리 비교: 세 파일에서 같은 service, feature_id, kind, code를 맞춰 보면 셋 다 말한 이유와 하나만 말한 이유가 나온다

## 읽을 때 주의

- model_a의 linkareer F2 안 쓸 이유는 통과율이 1.0인데 판정은 "사람에게 물어볼 것"이다. 공통 이유가 많아서 다른 기능 답(아무 기능에나 할 말)과 구별이 안 되기 때문이다. 이 규칙이 사람이 적을 때 너무 엄격하다는 것은 사람 수 시뮬레이션에도 나왔다
- 판정 규칙은 아직 동결 전이라 판정 결과가 바뀔 수 있다. 표 모양은 그대로다
- 서술 답은 "공고 저장: F2-1 에 해당하는 가짜 답입니다." 같은 가짜 문장이라 정리 시트는 견본에 넣지 않았다

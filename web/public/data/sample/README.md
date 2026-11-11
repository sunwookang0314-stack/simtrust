# 가짜 견본 데이터 (화면 틀용)

- 출처: `experiments/demo_sample/out/` (김민우, 브랜치 `feat/reason-scoring` 커밋 `dd0754e`, 11/11 복사)
- 전부 가짜다. 실제 응답도 실제 AI 답도 아니다. 칸 이름은 판정 계산기(`scripts/score_reasons.py`) 실제 출력과 같아서, 실제 결과가 나오면 이 폴더 파일만 바꾸면 된다
- `model_a/b/c`는 기말 데모(#35)에서 GPT·Claude·Gemini 자리다
- `../codebook_v0.1.csv`: 코드북 v0.1 (`docs/codebook/코드북_초안.csv`, 브랜치 `feat/reason-scoring` 커밋 `dd0754e`). 화면 4가 코드 이름·정의를 읽는다. 코드북이 v1.0으로 고정되면 바꾼다
- `cells_persona.csv`, `reasons_persona.csv`: **페르소나 AI 자리표시 (11/11 김승하)**. 김민우 견본에 페르소나 AI(조건 2) 결과가 없어서 `model_a`를 복사하고 condition을 2로, AI 답 수를 30개(10명 × 3번)로 맞춘 것. 판정·통과율·재현율은 model_a와 같다. 김민우 견본이 나오면 바꾼다
- 화면의 GPT·Claude·Gemini는 `model_a/b/c` 자리다 (어느 모델이 어느 파일인지는 의미 없음)

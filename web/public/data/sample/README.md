# 가짜 견본 데이터 (화면 틀용)

- 출처: `experiments/demo_sample/out/` (김민우, 브랜치 `feat/reason-scoring` 커밋 `9f1f604`, 11/21 복사)
- 전부 가짜다. 실제 응답도 실제 AI 답도 아니다. 칸 이름은 판정 계산기(`scripts/score_reasons.py`) 실제 출력과 같아서, 실제 결과가 나오면 이 폴더 파일만 바꾸면 된다
- 사람은 8개 서비스를 합쳐 판정한다 (사전등록 v1 11/16). 표의 `service` 칸은 `*`
- `model_a/b/c`는 GPT·Claude·Gemini 자리(조건 0), `persona`는 바탕 모델 + 페르소나 10명(P01~P10) 자리(조건 2). 어느 파일이 어느 모델인지는 의미 없다
- `reasons_*.csv`의 `ai_persona_ids`는 그 이유를 말한 페르소나(플랫폼:번호). 화면 5 거름망에서 페르소나 원을 켤 때 쓴다
- `verdict`는 규칙 초안의 `main`으로 낸 것이다. 본 규칙은 v2에서 `fixed_70`으로 정해졌고, 규칙 동결(11/22) 뒤 다시 받는다
- 화면 4가 읽는 `../codebook.csv`는 코드북 v1.0 작업본(브랜치 `docs/codebook-v1` 커밋 `a25518a`, 33개 확정). 고정되면 `docs/codebook/코드북.csv`로 바꾼다

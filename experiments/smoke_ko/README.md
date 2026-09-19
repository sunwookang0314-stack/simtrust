# TinyTroupe 한국어 스모크 테스트

TinyTroupe(0.7.0)를 한국어 페르소나와 한국어 기획안에 그대로 써도 되는지 확인한 실험.
리포 루트의 `scripts/smoke_tinytroupe.py`가 "호출이 되는지"를 보는 최소 확인이라면,
이쪽은 "결과를 믿을 수 있는지"를 재는 쪽이다. 페르소나 3명에게 같은 기획안을 3번씩 묻고 답이 얼마나 흔들리는지 측정한다.

## 확인하려는 것

| 질문 | 어떻게 재는가 |
|---|---|
| Q1. 한국어로 답하는가 | 응답 글자 중 한글 비율 |
| Q2. 정해진 스키마로 이슈가 뽑히는가 | ResultsExtractor 성공률, 필드/값 범위 준수율 |
| Q3. 같은 걸 3번 돌리면 얼마나 달라지는가 | 반복 간 이슈 수, (문제유형, 단계) 집합의 Jaccard, 발화 텍스트 유사도 |
| 추가. 따로 물었을 때 vs 서로 대화시켰을 때 | `--mode independent` / `--mode world` |

## 결과 요약

- Q1: 18건 중 17건이 한글 비율 0.97 이상. 나머지 1건은 아래 Q3 참고.
- Q2: independent 9건 전부 스키마 준수. 실패는 전부 API 오류(429/503)였고 모델이 형식을 틀린 적은 없다.
- Q3: 이슈 개수는 안정적인데(±0.5~0.8) 무엇을 지적하는지는 반복마다 바뀐다(Jaccard 0.37~0.78). 쓸지 말지 결론은 3번 다 같았다.
- world 모드에서는 지적 종류가 5개에서 4개로 줄고 가입·신뢰 쪽으로 몰렸다. 비용은 2배. 자세한 건 `results/compare_independent_vs_world.md`.

자세한 표와 발화 원문은 `results/report.html`을 브라우저로 열면 된다. `results/summary.md`는 같은 내용의 텍스트판.

## 파일

- `config.smoke.ini` : 이 실험용 설정. 실행할 때 `config.ini`로 복사된다(리포 .gitignore가 config.ini를 제외하므로).
- `personas/` : 대학생 페르소나 3명 (컴공 2학년, 경영 4학년 취준생, 디자인 1학년 신입생)
- `proposal_01_campusbook.md` : 중고 교재 거래 앱 기획안. 6단계 가입, 학생증 24시간 승인, 마케팅 동의 필수, 계좌이체만 가능, 야간 푸시 기본 켜짐, 판매 수수료 같은 문제를 일부러 넣었다.
- `run_smoke.py` : 실행 + 집계
- `make_report.py` : `results/report.html` 생성
- `cache/` : 모델·반복별 API 캐시. 이게 있으면 API 키 없이 같은 결과를 다시 만들 수 있다.
- `results/` : 반복별 원본 JSON, `summary.md`, `compare_independent_vs_world.md`, `report.html`
- `FINDINGS.md` : 실험하면서 본 TinyTroupe 문제점

## 실행

키가 없어도 `cache/`가 있으면 그대로 재현된다. 키를 새로 쓰려면 `.env`가 아니라 환경변수로 준다.

Windows PowerShell:
```powershell
.\.venv\Scripts\python.exe experiments\smoke_ko\run_smoke.py --mode independent --reps 3
.\.venv\Scripts\python.exe experiments\smoke_ko\run_smoke.py --mode world --reps 3
.\.venv\Scripts\python.exe experiments\smoke_ko\make_report.py
```

WSL/Linux:
```bash
.venv/bin/python experiments/smoke_ko/run_smoke.py --mode independent --reps 3
.venv/bin/python experiments/smoke_ko/make_report.py
```

`--analyze-only`를 주면 호출 없이 집계만 다시 한다.

무료 제공자로 돌릴 때는 환경변수 두 개가 필요하다.
```
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_API_KEY=<https://aistudio.google.com/apikey>
```

## 캐시를 반복마다 따로 두는 이유

TinyTroupe의 API 캐시는 같은 입력이면 같은 출력을 돌려준다. 3번 반복이 캐시 하나를 같이 쓰면 결과가 항상 똑같아져서 Q3를 잴 수 없다.
그래서 `cache/{모델}__{모드}_rep{n}.api_cache.json`으로 나눴다. 처음 한 번만 API를 부르고 그 뒤로는 캐시로 재현된다.

루트 README의 방침대로라면 실행 산출물은 `runs/`에 두고 git에서 빼는 게 맞다.
여기서는 "키 없이 재현"을 보여주려고 캐시를 같이 커밋했다(요구사항 R-06). 방침을 맞춰야 하면 옮기면 된다.

## 모델

- 이 결과는 전부 무료 `gemini-3.5-flash-lite`로 돌렸다. 보고서에 넣을 수치가 아니다.
- `gemini-3.6-flash`는 무료 한도가 하루 20회라 중간에 막혔다. 그때 나온 rep0 하나는 비교용으로 `results/`에 남겨뒀다.
- 최종 수치는 루트 README 방침대로 `config.openai.ini`(gpt-5-mini) 하나로 다시 돌려야 한다. 결과 파일명에 모델명이 붙어서 섞이지 않는다.

## 비용

호출 1건에 입력이 1만 토큰을 넘는다. TinyTroupe 페르소나 시스템 프롬프트가 39KB라서 그렇다.
independent 3명×3회는 18회 호출에 약 15만 토큰, world는 27회에 약 31만 토큰이었다.
`TinyPerson.MAX_ACTIONS_BEFORE_DONE`을 기본값 15 그대로 두고 돌렸다. 루트 `scripts/smoke_tinytroupe.py`처럼 3으로 낮추면 더 줄어든다.

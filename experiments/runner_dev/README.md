# AI 실행기 1단계 (scripts/run_simulation.py)

AI실행기.md의 1단계 뼈대다. 가짜 화면, 임시 페르소나, 무료 Gemini로 명령 한 줄을 치면
원시 응답, 실행 기록, 숫자 요약이 나온다.

질문 흐름은 아직 v4 과제형(화면을 넘기며 과제 수행)이다. AI 제시 프로토콜이 폼 B 기준(기능별로 쓸 것 같다/안 쓸 것 같다와 이유)으로 바뀌어서 2단계에서 이 부분을 다시 짠다. 비용 가드, 캐시, 실행 기록, 종료 코드는 그대로 쓴다.

## 실행

```powershell
.\.venv\Scripts\python.exe scripts\use_provider.py gemini
.\.venv\Scripts\python.exe scripts\run_simulation.py --service fake --condition 2 --repeat 1 --seed 1 `
    --config configs\simulation.dev.json --limit-personas 1
```

- `--config`를 안 주면 `configs/simulation.json`을 읽는다. 본실험용 값(화면 입력 방식, 비용 상한 등)이 아직 안 정해져서 이 파일은 만들지 않았다.
- `--limit-personas`는 시범 실행용이다. 페르소나 폴더에서 앞에서부터 N명만 쓴다.

출력 위치는 실행 설정에서 정한다. 개발 설정은 전부 `runs/dev/` 아래로 보내서 공개 폴더(`data/virtual/`)를 더럽히지 않는다.

| 파일 | 내용 |
|---|---|
| `runs/dev/raw_responses.jsonl` | 원시 응답. 한 줄 = 한 에피소드(서비스 x 페르소나 x 회차) |
| `runs/dev/meta/{run_id}.json` | 실행 기록. TRD 7장 13칸 + protocol_version, snapshot_version + 호출 수 등 |
| `runs/dev/meta/{batch_id}.summary.json` | 숫자 요약. 화면에도 같은 숫자만 찍는다 |
| `runs/dev/cache/...` | 페르소나(조건 0은 슬롯) x 회차별 API 캐시 |

종료 코드는 TRD 6장 표를 따른다. 0 정상, 1 사용법 오류·입력 파일 없음, 2 설정 불일치·인증, 3 비용 상한, 4 입력 검증 실패, 5 API 실패·빈 응답.

## 오프라인 테스트

API 키 없이 돈다. TinyTroupe의 실제 호출 함수만 가짜로 바꾸고 나머지는 그대로 쓴다.

```
python -m unittest tests.test_run_simulation -v
```

확인하는 것: 같은 캐시로 다시 돌리면 API를 안 부르고 같은 결과, 회차별 캐시 분리, 조건 0 슬롯, 조건 1에서 이름·거주지가 빠지는지, 기능 설명이 AI 입력에 안 들어가는지, 비용 상한(3), 인증 오류 재시도 없이 중단(2), 키 비었을 때(2), 제공자 불일치(2), 빈 응답 재시도 뒤 실패(5), 입력 오류(1, 4).

이 테스트로는 실제 Gemini 응답으로 도는지 알 수 없다. 그건 키를 넣고 직접 돌려야 한다.

## 1단계에서 임시로 정한 것

역할(2026-11-01): 실행기와 추출(IF-06)은 김민우, 김승하는 2차 검토. AI실행기.md에는 추출이 김승하로 적혀 있지만 이렇게 바꿨다.

- run_id는 에피소드(페르소나 x 회차)마다 하나다. 명령 한 번은 batch_id로 묶는다. TRD의 가상 응답 요약 표가 run_id를 PK로 쓰고 페르소나·회차 칸을 같이 두고 있어서 이렇게 읽었다. IF-06 `--run`이 무엇을 받을지는 추출 단계를 짤 때 정한다.
- 원시 응답 칸 이름(steps의 step_no, screen_shown, actions, think, talk, screen_mapped, mark)은 출발점이다. 2단계에서 프로토콜 10번에 맞춰 확정한다.

팀 합의가 필요한 것 둘.

- 조건 1은 나이와 occupation.title만 남기고, 이름은 성별 단서가 될 수 있어서 페르소나 ID로 바꿨다.
- 에피소드 하나가 실패하면 그 자리에서 전체를 멈춘다. 같은 원인으로 나머지가 줄줄이 실패하며 비용을 쓰는 걸 막으려고 이렇게 했다.

구현하면서 정한 것.

- 조건 0은 이름 자리에 슬롯 ID만 둔 빈 TinyPerson이다. TinyTroupe 기본 시스템 프롬프트는 그대로 들어간다.
- 비용 상한은 다음 실제 호출 직전에 확인한다. 그래서 마지막 호출 하나만큼은 상한을 넘을 수 있다. 캐시 응답은 세지 않는다.
- seed는 기록만 한다. TinyTroupe가 API에 seed를 넘기지 않는다.
- TinyTroupe 안에서 예상 못 한 오류가 나면 실행 기록에 traceback을 남기고 종료 코드 5로 끝낸다. TRD 표에 맞는 칸이 없어서 5로 골랐다.
- 과제 지시 문구(`task_prompt_template`)는 개발 설정 파일에 넣은 임시 문구다. 프로토콜 v0.1의 고정 문구가 나오면 바꾼다.

## 실제 Gemini로 돌려 본 결과 (2026-11-01)

- 가짜 화면, 조건 2, 페르소나 1명, 1회, 과제 2개로 돌렸다. 종료 코드 0
- 토큰: 입력 14,657 + 출력 660. 한글 비율 100%
- 과제 1회 평균 44.1초. 60회로 환산하면 0.73시간(NFR-05 기준 8시간)
- 같은 캐시로 다시 돌리면 실제 호출 0회, 결과가 같았다
- gemini-2.5-flash는 새로 발급한 키에서 404("no longer available to new users")가 난다. models.list로 확인한 gemini-3.8-flash로 바꿨다(config.gemini.ini는 PR #2). 모델이 없으면 종료 코드 2로 끝나게 했다
- gemini-3.8-flash는 503(high demand)이 자주 난다. TinyTroupe 재시도로 넘어갔다

## 아직 확인 못 한 것

- 비용 상한(3)과 인증 오류(2)는 오프라인 테스트로만 확인했다.
- TinyTroupe가 실행한 폴더에 `tinytroupe.*.log`를 남기고, 여기에 프롬프트 전문이 들어간다. `*.log`라 커밋은 안 되지만 실제 캡처로 시범 실행하기 전에 로그 위치를 옮겨야 한다.
- Gemini 호환 주소가 틀린 키에 어떤 오류를 주는지. 401이 아니라 400으로 올 경우에 대비해 문구로도 가려내게 했지만 실제 응답으로 확인하지 않았다.
- 이미지 입력(`input_mode: image`). 코드 경로만 있고 돌려 보지 않았다. AI실행기.md 시범 실행 2번(gpt-5-mini) 몫이다.

## 테스트하다 본 것

TinyTroupe는 한글을 `\uXXXX` 형태로 바꿔서 모델에 보낸다. 페르소나는 `agent/tiny_person.py:319`의 `json.dumps(..., indent=4)`, 메시지(화면 설명, 과제 문구 포함)는 `agent/action_generator.py:125`의 `json.dumps(msg["content"])`가 `ensure_ascii` 기본값으로 직렬화하기 때문이다. 토큰 수와 응답 품질에 얼마나 영향이 있는지는 아직 재지 않았다. 고치면 캐시 키가 바뀌므로 본실험 전에 정해야 한다.

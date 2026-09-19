# 실험 중 본 TinyTroupe 문제점

버전 0.7.0, 커밋 a6244b3 기준. 1번과 6번은 리포 루트 README에도 이미 적혀 있는 내용이고, 여기서는 이 실험에서 실제로 걸린 상황을 덧붙인다.

## 1. config.ini의 BASE_URL이 OpenAI 클라이언트에 적용되지 않음

- `tinytroupe/__init__.py` 86행에서 `BASE_URL`을 읽어 `base_url`에 저장하지만,
- `tinytroupe/clients/openai_client.py` 173행의 `OpenAI(api_key=..., max_retries=0, http_client=...)`에 `base_url`을 넘기지 않는다.
- `base_url`을 실제로 쓰는 곳은 `clients/ollama_client.py`뿐이다.
- 그래서 `API_TYPE=openai`에 `BASE_URL`을 넣어도 요청이 `api.openai.com`으로 간다. (401로 확인)
- 우회: 환경변수 `OPENAI_BASE_URL`을 설정하면 openai SDK가 알아서 읽는다.
- 고치려면 `OpenAI(...)` 호출에 `base_url=config_manager.get("base_url")` 한 줄 추가.

## 2. OpenAI 모델이 아니면 매 호출마다 ERROR 로그

- `_count_tokens()`가 모르는 모델명이면 `NotImplementedError`를 던지고, 이게 ERROR 레벨로 찍힌다.
- 동작에는 영향 없음. 로그가 시끄러울 뿐.

## 3. ResultsExtractor가 frequency_penalty / presence_penalty를 0.0으로 고정해서 보냄

- `extraction/results_extractor.py`: `client().send_message(messages, frequency_penalty=0.0, presence_penalty=0.0)`
- Gemini의 OpenAI 호환 엔드포인트는 이 필드를 400으로 거부한다. 발화는 되는데 추출만 실패한다.
- 우회: `run_smoke.py`에서 `OpenAIClient._raw_model_call`을 감싸 두 키를 빼고 보낸다.
- 고치려면 None이면 보내지 않게 하거나 config에서 읽게 바꾸면 된다.

## 4. TinyWorld 이름은 프로세스 안에서 유일해야 함

- 같은 이름으로 `TinyWorld`를 두 번 만들면 `ValueError: Environment names must be unique`.
- 반복 실험할 때 이름에 rep 번호를 붙여서 해결했다.

## 5. (관측) world 모드 2스텝째에서 출력이 깨진 사례 1건

- 모델: gemini-3.5-flash-lite, world rep1, 김지호.
- 1스텝은 정상 한국어. 2스텝에서 다른 사람 발화를 들은 뒤 THINK/TALK/DONE 전부가 `u0061u006E...` 식의 유니코드 이스케이프로 깨진 영어가 나왔다. 풀면 "anion, gain, gain. anyway, 6step, is too much overhead..." 정도.
- 한글 비율 0.45로 걸러졌다. world 9건 중 1건, independent 9건 중 0건.
- lite 모델 문제인지, TinyTroupe의 영어 프롬프트(39KB)와 한국어 대화가 섞여서 생긴 건지 아직 모른다. gpt-5-mini에서 다시 확인해야 한다.
- 주제정리 문서에 적어둔 "언어 설정이 없어서 출력 언어가 섞일 수 있다"가 실제로 한 번 일어난 것.

## 6. REASONING_EFFORT 는 효과가 없고, MAX_ACTIONS_BEFORE_DONE 기본값이 15다

루트 README에 적힌 내용을 코드로 다시 확인했다. 둘 다 맞다.

- `clients/openai_client.py`의 `_is_reasoning_model()`이 `"o1" in model or "o3" in model`이라서, `gpt-5-mini`나 `gemini-*`에는 `reasoning_effort`가 전달되지 않는다.
  이 실험의 `config.smoke.ini`에도 `REASONING_EFFORT=low`가 들어 있지만 실제로는 아무 효과가 없다. 처음에는 이걸 실험 조건인 줄 알고 리포트에 적었다가 지웠다.
- `agent/tiny_person.py:34`의 `MAX_ACTIONS_BEFORE_DONE = 15`. 이 실험은 기본값으로 돌려서 `listen_and_act` 한 번이 평균 2회 호출로 이어졌다(반복당 6호출, 5만 토큰).
  루트 `scripts/smoke_tinytroupe.py`처럼 3으로 낮추면 줄일 수 있다.

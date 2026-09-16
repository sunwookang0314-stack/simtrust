# SimTrust 개발 환경 메모

설정 파일(`config.*.ini`)에는 한글을 못 넣는다. TinyTroupe가 `configparser`로 읽을 때
인코딩을 지정하지 않아서, 한글 Windows(cp949)에서는 한글 주석 한 글자만 있어도
`import tinytroupe` 단계에서 `UnicodeDecodeError`가 난다. 그래서 한국어 설명은 여기 모아둔다.

## 폴더 구조

```
simtrust/
├─ .env                  API 키 (git 제외)
├─ config.openai.ini     유료 프로필
├─ config.gemini.ini     무료 프로필
├─ config.ini            현재 적용된 설정 (스크립트가 생성, git 제외)
├─ scripts/
│   ├─ use_provider.py   제공자 전환
│   └─ smoke_tinytroupe.py
├─ runs/                 실행 결과·메타데이터·API 캐시 (git 제외)
└─ external/
    ├─ TinyTroupe/       0.7.0
    └─ genagents/
```

가상환경이 둘이다. TinyTroupe는 `openai>=1.65`를 요구하고 genagents는 `openai==1.6.0`으로
고정돼 있어서 한 환경에 같이 못 넣는다.

- `.venv` : TinyTroupe용
- `.venv-ga` : genagents용 (설치 미완료)

## 무료와 유료를 나누는 기준

| 상황 | 쓸 것 |
|---|---|
| 사람(실제 참여자) 데이터가 프롬프트에 들어감 | **유료** 또는 사람이 직접 처리 |
| 발표·보고서에 들어갈 수치를 만듦 | **유료 하나로 고정** |
| 파이프라인 개발, 프롬프트 다듬기, 화면 작업 | 무료 |

무료 티어는 입력이 모델 개선에 쓰일 수 있어서 참여자 데이터를 보내면 안 된다.
그리고 조건별 수치를 서로 다른 모델로 뽑으면 비교 자체가 무효가 되므로,
최종 실험은 `config.openai.ini` 하나로 통일한다.

## 실행 순서

```powershell
# 1) 무료 프로필로 전환 (.env 검사를 통과해야 config.ini 가 바뀐다)
.\.venv\Scripts\python.exe scripts\use_provider.py gemini

# 2) 스모크 테스트
.\.venv\Scripts\python.exe scripts\smoke_tinytroupe.py
```

`.env`는 제공자에 따라 이렇게 쓴다.

```
# 무료
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_API_KEY=<https://aistudio.google.com/apikey>

# 유료 (OPENAI_BASE_URL 줄은 반드시 지운다)
OPENAI_API_KEY=<https://platform.openai.com/api-keys>
```

## 비용 관련해서 알아둘 것

원본 기본값이 위험해서 프로필에서 바꿔뒀다.

| 항목 | 원본 | 우리 설정 |
|---|---|---|
| `MAX_COMPLETION_TOKENS` | 128,000 | 2,048 (무료 프로필은 8,192) |
| `CACHE_API_CALLS` | False | True |
| `MAX_CONCURRENT_MODEL_CALLS` | 4 | 2 (무료 1) |
| `TinyPerson.MAX_ACTIONS_BEFORE_DONE` | 15 | 3 (스크립트에서 지정) |

주의할 점 두 가지다.

- `REASONING_EFFORT`는 이 버전에서 **효과가 없다**. `clients/openai_client.py`가 모델명에
  `o1`이나 `o3`가 들어갈 때만 이 값을 보낸다. `gpt-5-mini`에는 안 걸린다.
  결국 비용을 막는 건 `MAX_COMPLETION_TOKENS` 하나뿐이다.
- `MAX_ACTIONS_BEFORE_DONE`이 기본 15라서, `listen_and_act` 한 번이 최대 15회 호출로
  번질 수 있다. 스크립트에서 3으로 낮춰뒀다.

임베딩(semantic memory)은 두 프로필 모두 꺼뒀다. llama-index가 `OPENAI_BASE_URL`이 아니라
`OPENAI_API_BASE`를 보기 때문에, 무료 프로필에서도 임베딩만 OpenAI로 나가서 인증 오류가 난다.
켤 일이 생기면 `[Cognition]` 섹션을 손봐야 한다.

## 무료 프로필에서 응답이 비어 있을 때

`gemini-2.5-flash`는 내부 사고 토큰이 출력 한도에 같이 잡힌다. 한도가 낮으면 사고에 다 쓰고
빈 내용이 돌아온다. 그래서 무료 프로필의 상한을 8,192로 잡아뒀다. 그래도 비면 더 올려라.

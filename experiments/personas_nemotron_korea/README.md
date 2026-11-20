# Nemotron-Personas-Korea → 재학·취준·직장 페르소나

[nvidia/Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea)
(CC BY 4.0)에서 "재학생", "취준생", "직장인" 그룹을 근사해서 걸러내고(1단계), 4칸에서
칸마다 10명씩 뽑아 TinyTroupe `TinyPerson` 형식으로 변환한다(2단계).

**지금 쓰는 패널은 `personas_v2/panel/` 40명이다 (11/17).** 아래 "4칸 패널" 참고.
`personas/`의 30명(재학 15, 취준 15)은 이전 판이라 기존 설정·문서가 가리키는 것 때문에 남겨 둔다. 결과물은 팀 공유를 위해
git에 포함한다 (`WORK_LOG.md`만 로컬 전용 작업 일지라 제외).

## 왜 두 그룹으로 나눴나

데이터셋에 '대학생'이나 '재학 중'을 직접 나타내는 필드가 없다.

- `occupation`: 직업명 또는 `무직`만 있고 학생이라는 값이 없다.
- `education_level`: **졸업까지 끝낸 최종 학력**이다. 재학 중이어도 완료 전이면
  그 아래 학력(고등학교 등)으로 잡힌다.
- 자유서술 텍스트(`persona` 등)에 "대학생"이 직접 나오는 경우는 샤드당 32건 수준으로
  너무 적고, "전직 대학생" 같은 과거형도 섞여 있어 신뢰할 수 없다.

처음에는 "무직 + (고졸 또는 전문대졸) + 19~26세" 하나로 뭉뚱그렸는데 두 가지 문제를
실제로 확인했다:

1. 전문대를 이미 졸업한 사람(= 재학생이 아니라 그냥 무직 졸업자)이 섞여 들어왔다.
   샘플 점검 중 "배우자·자녀와 거주, 육아휴직 중"인 2~3년제 전문대 졸업자가
   "대학생"으로 라벨링된 걸 발견함.
2. "고졸 + 무직" 인구를 나이별로 쪼개보니 **20세부터 27세까지 숫자가 거의 평평했다**
   (19세에서만 압도적으로 많음). 재학생이라면 나이가 들수록 졸업해서 줄어드는 모양이
   나와야 하는데 그렇지 않다는 건, 이 구간에 "애초에 대학에 안 간 사람"이 나이와
   무관하게 섞여 있다는 뜻이다. 즉 이 데이터셋은 '재학 중'이라는 생애주기 상태를
   아예 모델링하지 않는다 — 나이를 어떻게 좁혀도 "더 순수한 재학생"이 되지 않는다.

그래서 **식별이 비교적 명확한 "취준생"과, 불가피하게 근사치인 "재학생"을 분리**했다:

```sql
-- 재학생 (아직 학위를 안 끝낸, 재학생이 가장 많이 몰려있는 나이대)
occupation = '무직'
AND education_level = '고등학교'          -- 전문대 졸업자 제외
AND age BETWEEN 19 AND 25
AND marital_status = '미혼'

-- 취준생 (4년제 졸업 후 아직 취업 전)
occupation = '무직'
AND education_level = '4년제 대학교'       -- 4년제 완료는 22세부터만 나타남 → 확정적
AND age BETWEEN 23 AND 27
AND marital_status = '미혼'
```

"재학생" 쪽은 여전히 근사치다 (고졸 상태로 계속 머무를 비진학자와 구분 불가, 군필
지연 등도 반영 못함). "취준생" 쪽은 `education_level`이 "졸업 완료"를 명확히
가리키므로 상대적으로 깨끗한 정의다. 미혼 조건은 두 그룹 모두에 넣었다 (기혼·有자녀는
이 나이대라도 재학생/취준생일 가능성이 매우 낮다고 판단).

## 4칸 패널 (11/17)

폼 B 응답이 나온 뒤 사람 쪽 상태 묶음(2-1: 재학 / 졸업 후 취업 준비 / 직장)에 맞춰 칸을
나눠 다시 뽑았다. 칸마다 수를 똑같이(10명) 맞추고, 사람 쪽 구성 비율은 분석할 때 가중으로 맞춘다.

| 칸 (ID 접두사) | 묶음 | 조건 | 풀 | 뽑는 방식 |
|---|---|---|---|---|
| `S1-` | 재학 | 무직 · 고등학교 · 미혼 · 19~22세 | 10,292 | 나이마다 2~3명, 각 나이 안 성비는 풀 비율 |
| `S2-` | 재학 | 무직 · 고등학교 · 미혼 · 23~25세 | 2,282 | 성별×나이 비례층화 |
| `J-` | 취준 | 무직 · 4년제 · 미혼 · 23~27세 | 12,567 | 성별×나이 비례층화 |
| `W-` | 직장 | 직업 있음(전직·구직중 제외) · 4년제 또는 전문대 · 미혼 · 23~27세 | 27,702 | 성별×나이 비례층화 |

- S1을 비례로 뽑으면 19세가 풀의 78%라 10명 중 8명이 19세가 된다. 그래서 나이마다 고르게 뽑는다.
  10명을 4개 나이에 나누고 남는 2명은 시드로 고른 나이에 한 명씩 더한다.
- J·W는 성별×나이 층이 10개라 비례로 뽑아도 반올림 때문에 층마다 1명(남녀 5:5)이 된다.
  풀의 성비(J 여 58%, W 남 60%)와는 다르다.
- W 풀에서 "전직 OO, 현재 구직중" 2,226명은 지금 직장이 없으니 뺐다.

### 페르소나 글

변환 메모("근사함", "추정")는 모델이 그대로 읽으니 페르소나 글에서 뺐다 (`docs/work-orders/kim-minwoo/AI실행기.md`).

| 칸 | `occupation.title` | `education` |
|---|---|---|
| 재학 | 대학생 | 대학교 재학 중 |
| 취준 | 취업준비생 | `education_level` 졸업 (전공 계열) |
| 직장 | 원본 `occupation` 그대로 (예: 치과기공사, 그 외 법률 관련 사무원) | `education_level` 졸업 (전공 계열) |

나머지 필드 매핑은 아래 "필드 매핑"과 같다.

### 한계

- 재학은 근사치다. 무직·고졸·미혼을 재학생으로 쳤으니 대학에 안 간 사람이 섞여 있다.
  원본 글에 "고교 졸업 후 잠시 숨을 고르는" 같은 문장이 남아 있으면 "대학교 재학 중"과 어긋날 수 있다.
- 휴학과 졸업유예는 데이터로 구분할 수 없어서 재학에 묶었다.
- 직장은 직업이 있다는 것만 알 수 있고 몇 년차인지는 데이터에 없다. 23~27세로 사회초년생을 근사했다.

## 파일

- `fetch_university_personas.py` (1단계) : HuggingFace 원본 parquet(9개 조각, 총 100만 건)을
  네트워크로 직접 쿼리(duckdb httpfs)해서 그룹 조건에 맞는 행만 로컬에 저장한다.
  전체를 디스크에 받지 않고 원격에서 걸러서 가져온다. `--groups`로 일부 그룹만 받을 수 있다.
- `data/students_in_progress.parquet` (재학생 풀, 19~25세) : 12,574행, ~22MB.
- `data/job_seekers.parquet` (취준생 풀) : 12,567행, ~22MB.
- `data/workers.parquet` (직장인 풀) : 27,702행, ~26MB (zstd).
  (모두 **팀 공유를 위해 git에 포함**한다. 저장소 용량에 민감하면 Git LFS로 옮기는 것도 고려.)
- `sample_and_convert.py` (2단계) : 4칸에서 칸마다 N명을 뽑아 TinyTroupe `TinyPerson` JSON으로 변환한다.
- `personas_v2/panel/*.agent.json` : 변환된 40명. 실행기(`scripts/run_simulation.py`)의 `personas_dir`로
  바로 쓴다. 실행기는 파일 이름에서 `_` 앞(`S1-01` 등)을 페르소나 ID로 쓴다.
- `personas_v2/manifest.json` : 페르소나마다 칸, 묶음(재학/취준/직장), 원본 uuid, 나이, 성별, 원본 직업, 학력.
  실행기가 읽는 폴더 밖에 둔다.
- `personas/` : 이전 판 30명 (재학 15, 취준 15). 메모가 글에 들어가 있는 판이다.

### 필드 매핑 (2단계)

Nemotron에 실제로 있는 값만 쓰고, 근거 없는 성격 수치(Big Five 등)는 만들어내지 않았다.

| TinyPerson 필드 | Nemotron 출처 |
|---|---|
| `name` | `persona` 텍스트 맨 앞 "OOO 씨는" 패턴에서 정규식으로 추출 (전수 매치 확인함) |
| `age`, `gender` | `age`, `sex` (남자→Male, 여자→Female) |
| `residence` | `province` + `district` + `family_type` + `housing_type` 조합 |
| `education`, `occupation.title` | 위 "페르소나 글" 표 |
| `occupation.description`, `long_term_goals` | `career_goals_and_ambitions` |
| `preferences.likes` | `hobbies_and_interests_list` |
| `other_facts` | `persona` 요약문 + 6종 세부 페르소나(`professional_persona`, `sports_persona`, `arts_persona`, `travel_persona`, `culinary_persona`, `family_persona`) + `cultural_background` + `skills_and_expertise` + 혼인/병역 상태 |

`style`, `personality.big_five`, `behaviors` 등 Nemotron에 대응 데이터가 없는 필드는
비워뒀다 (지어내지 않음).

## 실행

```bash
python3 -m venv .venv-data   # 최초 1회, 루트 .venv와 별개 (TinyTroupe 의존성과 무관)
.venv-data/bin/pip install duckdb pandas pyarrow

# 1단계: 원본에서 그룹 조건으로 필터링 (전체 약 5분, 이미 있으면 --groups로 일부만)
.venv-data/bin/python experiments/personas_nemotron_korea/fetch_university_personas.py
.venv-data/bin/python experiments/personas_nemotron_korea/fetch_university_personas.py --groups workers

# 2단계: 4칸 x 10명 샘플링 + TinyPerson 변환 (같은 시드면 결과가 같다)
.venv-data/bin/python experiments/personas_nemotron_korea/sample_and_convert.py --n-per-cell 10 --seed 42
```

# Nemotron-Personas-Korea → 대학생/취준생 페르소나

[nvidia/Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea)
(CC BY 4.0)에서 "재학생"과 "취준생" 두 그룹을 근사해서 걸러내고(1단계), 각각 N명을
샘플링해 TinyTroupe `TinyPerson` 형식으로 변환한다(2단계). 결과물은 팀 공유를 위해
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

## 파일

- `fetch_university_personas.py` (1단계) : HuggingFace 원본 parquet(9개 조각, 총 100만 건)을
  네트워크로 직접 쿼리(duckdb httpfs)해서 두 그룹 조건에 맞는 행만 로컬에 저장한다.
  전체를 디스크에 받지 않고 원격에서 걸러서 가져온다.
- `data/students_in_progress.parquet` (1단계 결과, 재학생 풀) : 12,574행, ~22MB.
- `data/job_seekers.parquet` (1단계 결과, 취준생 풀) : 12,567행, ~22MB.
  (두 파일 모두 **팀 공유를 위해 git에 포함**한다. 저장소 용량에 민감하면 Git LFS로
  옮기는 것도 고려.)
- `sample_and_convert.py` (2단계) : 두 parquet에서 각각 성별×나이 비례층화로 N명을 뽑고,
  TinyTroupe `TinyPerson` JSON(`experiments/smoke_ko/personas/*.agent.json`과 같은 형식)으로
  변환한다.
- `personas/students_in_progress/*.agent.json`, `personas/job_seekers/*.agent.json`
  (2단계 결과) : 변환된 페르소나 파일들. 파일명 접두사 `S`=재학생, `J`=취준생.
- `personas/manifest.json` : 어떤 원본 uuid가 어떤 그룹·파일이 됐는지 추적용 목록.

### 필드 매핑 (2단계)

Nemotron에 실제로 있는 값만 쓰고, 근거 없는 성격 수치(Big Five 등)는 만들어내지 않았다.

| TinyPerson 필드 | Nemotron 출처 |
|---|---|
| `name` | `persona` 텍스트 맨 앞 "OOO 씨는" 패턴에서 정규식으로 추출 (전수 매치 확인함) |
| `age`, `gender` | `age`, `sex` (남자→Male, 여자→Female) |
| `residence` | `province` + `district` + `family_type` + `housing_type` 조합 |
| `education` | 그룹별로 다르게 서술. 재학생은 "재학 여부 확인 불가, 근사함"을 명시, 취준생은 "졸업 완료(확정)"로 서술 |
| `occupation.title` | 재학생="대학생 (재학 중으로 추정)", 취준생="취업준비생 (4년제 대학교 졸업)" |
| `occupation.description`, `long_term_goals` | `career_goals_and_ambitions` |
| `preferences.likes` | `hobbies_and_interests_list` |
| `other_facts` | `persona` 요약문 + 6종 세부 페르소나(`professional_persona`, `sports_persona`, `arts_persona`, `travel_persona`, `culinary_persona`, `family_persona`) + `cultural_background` + `skills_and_expertise` + 혼인/병역 상태 |

`style`, `personality.big_five`, `behaviors` 등 Nemotron에 대응 데이터가 없는 필드는
비워뒀다 (지어내지 않음).

## 실행

```bash
python3 -m venv .venv-data   # 최초 1회, 루트 .venv와 별개 (TinyTroupe 의존성과 무관)
.venv-data/bin/pip install duckdb pandas pyarrow

# 1단계: 원본에서 재학생/취준생 두 그룹 조건으로 필터링
.venv-data/bin/python experiments/personas_nemotron_korea/fetch_university_personas.py

# 2단계: 그룹별 N명 샘플링 + TinyPerson 변환 (기본 15+15=30명)
.venv-data/bin/python experiments/personas_nemotron_korea/sample_and_convert.py \
    --n-students 15 --n-job-seekers 15
```

## 다음 단계

- 변환된 페르소나를 `experiments/smoke_ko/run_smoke.py` 같은 파이프라인에 투입해서
  실제로 TinyTroupe가 문제없이 로드/대화하는지 확인
- 필요하면 `--n-students`, `--n-job-seekers`, `--seed`를 바꿔 다른 규모/비율의 샘플을
  추가로 생성

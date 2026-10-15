"""화면 초안용 목업 데이터.

실제 파이프라인이 붙기 전까지 화면을 채우는 용도. 숫자는 전부 예시.
나중에 실제 결과 파일(data/*.json, data/*.csv)이 생기면 load_* 함수만 바꾸면 된다.
"""
import json
import random
from pathlib import Path

import pandas as pd

import os

DATA_DIR = Path(__file__).parent / "data"
REPO_ROOT = Path(__file__).resolve().parents[1]

# 페르소나는 복사하지 않고 실험 폴더를 직접 읽는다 (원본은 한 곳에만).
# 경로가 다르면 환경변수 SIMTRUST_PERSONA_DIR 로 덮어쓰기.
PERSONA_DIR = Path(os.environ.get(
    "SIMTRUST_PERSONA_DIR",
    REPO_ROOT / "experiments" / "personas_nemotron_korea" / "personas",
))

# ---------------------------------------------------------------- 공통 상수
CONDITIONS = {
    "C0": {"name": "기준선", "sub": "페르소나 없음",
           "desc": '같은 모델에 "이 서비스의 문제점을 지적해봐" 단일 지시'},
    "C1": {"name": "토론형", "sub": "MiroFish 방식",
           "desc": "페르소나끼리 토론한 뒤 지적을 모음"},
    "C2": {"name": "SimTrust", "sub": "개별 페르소나",
           "desc": "페르소나별로 각자 화면을 보고 독립적으로 지적"},
}

# 문제 유형 분류표 확정 전 임시값
ISSUE_TYPES = ["기능을 못 찾음", "흐름 중간에 막힘", "용어를 이해 못 함", "취향·감성"]
SEVERITY = ["높음", "중간", "낮음"]

# TinyTroupe 생성 프롬프트가 요구하는 17개 항목
PERSONA_FIELDS = [
    "name", "age", "gender", "nationality", "residence", "education",
    "long_term_goals", "occupation", "style", "personality", "preferences",
    "beliefs", "skills", "behaviors", "health", "relationships", "other_facts",
]

# 신뢰도 지도 판정 기준 (예시 · 팀 확정 필요)
TRUST_RULES = {"trust": 0.7, "reference": 0.4, "min_count": 10}

# ---------------------------------------------------------------- 서비스
SERVICES = [
    {"id": "svc-a", "name": "테스트 서비스 A", "desc": "대외활동 탐색·지원",
     "url": "https://example-a.vercel.app", "commit": "a6f3c21", "frozen": "2026/09/30",
     "flow": "가입 → 공고 검색 → 지원 1회 완주",
     "screens": ["S1 로그인", "S2 메인", "S3 공고 검색", "S4 공고 상세", "S5 지원서 작성"],
     "status": "리포트 완료", "step": 4},
    {"id": "svc-b", "name": "테스트 서비스 B", "desc": "대외활동 후기 공유",
     "url": "https://example-b.vercel.app", "commit": "3d91b0e", "frozen": "2026/10/06",
     "flow": "가입 → 후기 작성",
     "screens": ["S1 로그인", "S2 메인", "S3 후기 목록", "S4 후기 작성"],
     "status": "스냅샷 등록됨", "step": 1},
]

STATUS_ORDER = ["스냅샷 등록됨", "실행 완료", "리포트 완료"]

RUNS = pd.DataFrame([
    ["R-0012", "테스트 서비스 A", "C2 SimTrust", 3, "2026/10/12 14:20", 96],
    ["R-0011", "테스트 서비스 A", "C1 토론형", 3, "2026/10/12 13:05", 71],
    ["R-0010", "테스트 서비스 A", "C0 기준선", 3, "2026/10/12 11:40", 64],
], columns=["실행 ID", "서비스", "조건", "반복", "실행 일시", "이슈 카드 수"])


# ---------------------------------------------------------------- 페르소나
def _unwrap(raw: dict) -> dict:
    """TinyTroupe 저장 형식({"type": "TinyPerson", "persona": {...}})과 평평한 dict 둘 다 받는다."""
    return raw.get("persona", raw) if isinstance(raw, dict) else {}


def as_text(v) -> str:
    """표에 넣을 짧은 문자열. occupation 처럼 dict 인 항목은 title 우선."""
    if isinstance(v, dict):
        return str(v.get("title") or v.get("name") or next(iter(v.values()), ""))
    if isinstance(v, list):
        return ", ".join(map(str, v[:2]))
    return "" if v is None else str(v)


def _age(p: dict) -> int | None:
    try:
        return int(p.get("age"))
    except (TypeError, ValueError):
        return None


def real_persona_files() -> list[Path]:
    if not PERSONA_DIR.is_dir():
        return []
    return sorted(f for f in PERSONA_DIR.rglob("*.json") if f.name != "manifest.json")


def load_personas(n: int = 20, seed: int = 42, age=(19, 26)) -> tuple[list[dict], str]:
    """(페르소나 목록, 출처 설명). 실험 폴더에 파일이 있으면 그걸, 없으면 목업."""
    files = real_persona_files()
    if files:
        people = []
        for f in files:
            try:
                p = _unwrap(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            p.setdefault("name", f.stem)
            p["__id__"] = f.name.split(".")[0]  # 이름이 겹칠 수 있어 파일명을 ID로 쓴다
            people.append(p)
        pool = [p for p in people if _age(p) is None or age[0] <= _age(p) <= age[1]]
        picked = random.Random(seed).sample(pool, min(n, len(pool)))
        try:
            where = PERSONA_DIR.relative_to(REPO_ROOT)
        except ValueError:
            where = PERSONA_DIR
        return picked, f"실제 데이터 · {where} ({len(people)}명 중 조건 일치 {len(pool)}명)"

    rnd = random.Random(seed)
    regions = ["서울", "경기", "인천", "부산", "대구", "대전", "광주"]
    majors = ["경영학", "컴퓨터공학", "미디어커뮤니케이션", "시각디자인", "사회복지학", "기계공학"]
    people = []
    for i in range(n):
        pid = f"P-{rnd.randint(10, 1999):04d}"
        p = {
            "__id__": pid,
            "name": pid,
            "age": rnd.randint(*age),
            "gender": rnd.choice(["여", "남"]),
            "nationality": "대한민국",
            "residence": rnd.choice(regions),
            "education": f"{rnd.choice(majors)} 전공 {rnd.randint(1, 4)}학년",
            "occupation": "대학생",
        }
        rest = [k for k in PERSONA_FIELDS if k not in p]
        # 일부 페르소나는 일부러 빈 항목을 남겨 경고 화면을 보여준다
        drop = rnd.choice([0, 0, 0, 0, 0, 1, 5])
        for k in rest[: len(rest) - drop]:
            p[k] = "…"
        people.append(p)
    return people, f"목업 데이터 · {PERSONA_DIR} 에 파일이 없음"


def field_fill(p: dict) -> int:
    return sum(1 for k in PERSONA_FIELDS if p.get(k) not in (None, "", [], {}))


# ---------------------------------------------------------------- 이슈 카드
VIRTUAL_ISSUES = pd.DataFrame([
    ["VI-0231", "C2", "P-0412", "S3 공고 검색", "기능을 못 찾음", "높음", "마감일 필터가 어디 있는지 찾지 못함", "정상"],
    ["VI-0232", "C2", "P-1033", "S5 지원서 작성", "흐름 중간에 막힘", "높음", "중간 저장이 안 보여 이탈이 불안함", "정상"],
    ["VI-0233", "C2", "P-0877", "S4 공고 상세", "용어를 이해 못 함", "중간", "'서포터즈'와 '기자단' 구분이 모호함", "정상"],
    ["VI-0234", "C1", "(토론)", "S2 메인", "취향·감성", "낮음", "메인 색감이 딱딱해 보임", "정상"],
    ["VI-0235", "C2", "P-1520", "S1 로그인", "", "", "(지적 없음)", "지적 없음"],
    ["VI-0236", "C0", "-", "S5 지원서 작성", "", "", "필드 누락: severity", "추출 실패"],
    ["VI-0237", "C0", "-", "S3 공고 검색", "기능을 못 찾음", "중간", "정렬 기준을 바꾸는 방법이 안 보임", "정상"],
    ["VI-0238", "C1", "(토론)", "S5 지원서 작성", "흐름 중간에 막힘", "높음", "첨부 파일 형식 안내가 없어 업로드에서 막힘", "정상"],
], columns=["ID", "조건", "페르소나", "화면", "문제 유형", "심각도", "지적 요약", "상태"])

RAW_RESPONSES = {
    "VI-0231": "마감 임박한 공고만 보고 싶은데 상단에 검색창밖에 없어서 필터가 없는 줄 알았어요. 한참 스크롤했어요.",
    "VI-0232": "지원서가 길어서 중간에 나갔다 오고 싶은데, 저장 버튼이 안 보여서 날아갈까 봐 끝까지 붙잡고 있었어요.",
}

# ---------------------------------------------------------------- 지표 (예시)
METRICS = pd.DataFrame([
    ["C0 기준선", 64, 27, 6, 29, 2, 0.48, 0.41, 0.44],
    ["C1 토론형", 71, 38, 3, 28, 2, 0.58, 0.52, 0.55],
    ["C2 SimTrust", 96, 61, 5, 27, 3, 0.69, 0.63, 0.66],
], columns=["조건", "가상 이슈", "매칭", "유효 추가", "근거 없음", "판단 불가", "정밀도", "재현율", "F1"])

CONSISTENCY = pd.DataFrame([
    ["C0", 0.52, 0.49], ["C1", 0.61, 0.58], ["C2", 0.67, 0.70],
], columns=["조건", "1↔2회차", "2↔3회차"])
CONSISTENCY["평균"] = CONSISTENCY[["1↔2회차", "2↔3회차"]].mean(axis=1).round(2)

TRUST_MAP = {
    "C2": [["기능을 못 찾음", 0.82, 0.75, 24], ["흐름 중간에 막힘", 0.70, 0.61, 18],
           ["용어를 이해 못 함", 0.54, 0.49, 11], ["취향·감성", 0.31, 0.28, 3]],
    "C1": [["기능을 못 찾음", 0.71, 0.66, 24], ["흐름 중간에 막힘", 0.60, 0.52, 18],
           ["용어를 이해 못 함", 0.50, 0.44, 11], ["취향·감성", 0.35, 0.30, 3]],
    "C0": [["기능을 못 찾음", 0.63, 0.58, 24], ["흐름 중간에 막힘", 0.55, 0.47, 18],
           ["용어를 이해 못 함", 0.49, 0.45, 11], ["취향·감성", 0.29, 0.25, 3]],
}


def f1(p: float, r: float) -> float:
    return round(2 * p * r / (p + r), 2) if p + r else 0.0


def verdict(p: float, r: float, n: int, rules=TRUST_RULES) -> str:
    """문제 유형 하나의 판정. 건수 부족이 다른 조건보다 먼저."""
    if n < rules["min_count"]:
        return "자료 부족"
    low = min(p, r)
    if low >= rules["trust"]:
        return "믿고 써도 됨"
    if low >= rules["reference"]:
        return "참고용"
    return "사람에게 물어볼 것"


# ---------------------------------------------------------------- 창업자 리포트 (예시)
# C2 실행 결과의 이슈 카드를 비슷한 지적끼리 묶은 결과. 실제로는 이슈 카드 묶기 + LLM 요약으로 만든다.
REPORT_SUMMARY = (
    "가상 사용자 20명 중 16명이 **공고 검색(S3)** 에서, 15명이 **지원서 작성(S5)** 에서 막혔습니다. "
    "원하는 공고를 찾는 단계와 지원을 끝내는 단계 모두 이탈 위험이 큽니다. "
    "먼저 고칠 것은 ① 마감일 필터 노출 ② 지원서 자동 저장 ③ 첨부 파일 안내, 세 가지입니다."
)

# 화면별로 막힌 가상 사용자 수 (중복 없이, 플로우 순서)
SCREEN_STUCK = pd.DataFrame([
    ["S1 로그인", 4], ["S2 메인", 3], ["S3 공고 검색", 16], ["S4 공고 상세", 6], ["S5 지원서 작성", 15],
], columns=["화면", "막힌 인원"])

REPORT_ISSUES = [
    {"title": "마감일 필터를 찾지 못함", "screen": "S3 공고 검색", "type": "기능을 못 찾음", "severity": "높음",
     "count": 14, "who": "1·2학년, 대외활동 처음 찾는 사람",
     "quotes": ["마감 임박한 공고만 보고 싶은데 상단에 검색창밖에 없어서 필터가 없는 줄 알았어요.",
                "필터가 접혀 있는 줄 몰랐어요. 스크롤만 계속 내렸어요."],
     "fix": "검색창 바로 아래에 '마감 임박 · 분야 · 온라인/오프라인' 필터 칩을 펼친 상태로 보여주세요.",
     "effort": "작음"},
    {"title": "지원서 중간 저장이 안 보여 불안함", "screen": "S5 지원서 작성", "type": "흐름 중간에 막힘",
     "severity": "높음", "count": 11, "who": "자기소개서 문항이 긴 공고에 지원한 사람",
     "quotes": ["지원서가 길어서 중간에 나갔다 오고 싶은데, 저장 버튼이 안 보여서 날아갈까 봐 끝까지 붙잡고 있었어요."],
     "fix": "입력할 때마다 자동 임시 저장하고, 화면 상단에 '방금 저장됨' 표시를 띄워주세요.",
     "effort": "중간"},
    {"title": "첨부 파일 형식 안내가 없어 업로드에서 막힘", "screen": "S5 지원서 작성", "type": "흐름 중간에 막힘",
     "severity": "높음", "count": 9, "who": "포트폴리오를 PDF 외 형식으로 가진 사람",
     "quotes": ["HWP로 올렸더니 다음 버튼이 안 눌리는데 이유를 안 알려줘요."],
     "fix": "업로드 칸에 허용 형식·용량을 미리 적고, 거절될 때는 이유를 바로 옆에 보여주세요.",
     "effort": "작음"},
    {"title": "정렬 기준을 바꾸는 방법이 안 보임", "screen": "S3 공고 검색", "type": "기능을 못 찾음",
     "severity": "중간", "count": 7, "who": "공고를 여러 개 비교하는 사람",
     "quotes": ["최신순 말고 마감순으로 보고 싶은데 버튼이 어디 있는지 모르겠어요."],
     "fix": "결과 목록 오른쪽 위에 '정렬: 마감 임박순' 드롭다운을 두세요.",
     "effort": "작음"},
    {"title": "'서포터즈'와 '기자단'의 차이를 모름", "screen": "S4 공고 상세", "type": "용어를 이해 못 함",
     "severity": "중간", "count": 6, "who": "대외활동 경험이 없는 사람",
     "quotes": ["'서포터즈'와 '기자단'이 뭐가 다른지 모르겠어요. 하는 일이 비슷해 보여요."],
     "fix": "활동 유형 옆에 물음표 아이콘을 두고 한 줄 설명(주요 활동·필요 시간)을 보여주세요.",
     "effort": "작음"},
    {"title": "소셜 로그인 후 추가 정보 화면에서 멈칫함", "screen": "S1 로그인", "type": "흐름 중간에 막힘",
     "severity": "낮음", "count": 4, "who": "빠르게 둘러보고 싶은 사람",
     "quotes": ["로그인했는데 또 뭘 입력하라고 해서 그냥 나갈 뻔했어요."],
     "fix": "필수가 아닌 항목은 '나중에 입력'으로 건너뛸 수 있게 해주세요.",
     "effort": "작음"},
    {"title": "메인 화면 색감이 딱딱해 보임", "screen": "S2 메인", "type": "취향·감성",
     "severity": "낮음", "count": 3, "who": "-",
     "quotes": ["메인 색감이 딱딱해 보여요. 공공기관 사이트 같아요."],
     "fix": "취향 문제는 가상 사용자 예측이 약한 영역입니다. 실제 사용자에게 한 번 더 물어보세요.",
     "effort": "-"},
]

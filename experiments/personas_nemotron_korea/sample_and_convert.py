"""재학 2칸 · 취준 · 직장, 4칸에서 칸마다 N명씩 뽑아 TinyTroupe TinyPerson 스펙(JSON)으로 변환한다.

칸 (폼 B 2-1 상태 묶음에 맞춤, 11/17):
  S1 재학 19~22세  students_in_progress.parquet  나이마다 고르게, 각 나이 안 성비는 풀 비율
  S2 재학 23~25세  students_in_progress.parquet  성별x나이 비례층화
  J  취준 23~27세  job_seekers.parquet           성별x나이 비례층화
  W  직장 23~27세  workers.parquet               성별x나이 비례층화

S1을 나이마다 고르게 뽑는 건 재학 풀에서 19세가 64%라서 비례로 뽑으면 10명 중 8명이 19세가 되기 때문이다.

매핑 원칙: Nemotron 쪽에 실제로 있는 값만 쓴다. Big Five, 말투(style) 같은
근거 없는 성격 수치는 지어내지 않고, 있는 그대로의 서술형 필드
(professional_persona, family_persona 등 6종 '페르소나 유형' + cultural_background +
skills_and_expertise)를 other_facts 에 담는다. "근사함", "추정" 같은 변환 메모는 모델이
그대로 읽으니 페르소나 글에 넣지 않고 README와 manifest에만 둔다.

출력은 실행기(scripts/run_simulation.py)가 바로 읽는 모양이다. 40명을 한 폴더(panel/)에 두고
manifest.json은 그 폴더 밖에 둔다. 실행기는 파일 이름에서 "_" 앞을 페르소나 ID로 쓴다.

사용:
    .venv-data/bin/python experiments/personas_nemotron_korea/sample_and_convert.py --n-per-cell 10
"""

import argparse
import ast
import json
import pathlib
import random
import re

import pandas as pd

HERE = pathlib.Path(__file__).parent
DATA_DIR = HERE / "data"
OUT_DIR = HERE / "personas_v2"

NAME_RE = re.compile(r"^([가-힣]{2,4})\s*씨")
GENDER_MAP = {"남자": "Male", "여자": "Female"}


def _major(row) -> str:
    field = row.get("bachelors_field")
    return f" ({field})" if isinstance(field, str) and field and field != "해당없음" else ""


CELLS = {
    "S1": {
        "group": "재학",
        "source": "students_in_progress",
        "ages": (19, 22),
        "sampling": "age_even",
        "occupation_title": lambda row: "대학생",
        "education": lambda row: "대학교 재학 중",
    },
    "S2": {
        "group": "재학",
        "source": "students_in_progress",
        "ages": (23, 25),
        "sampling": "proportional",
        "occupation_title": lambda row: "대학생",
        "education": lambda row: "대학교 재학 중",
    },
    "J": {
        "group": "취준",
        "source": "job_seekers",
        "ages": (23, 27),
        "sampling": "proportional",
        "occupation_title": lambda row: "취업준비생",
        "education": lambda row: f"{row['education_level']} 졸업{_major(row)}",
    },
    "W": {
        "group": "직장",
        "source": "workers",
        "ages": (23, 27),
        "sampling": "proportional",
        "occupation_title": lambda row: row["occupation"],
        "education": lambda row: f"{row['education_level']} 졸업{_major(row)}",
    },
}


def parse_list_field(raw) -> list[str]:
    """'[\"a\", \"b\"]' 형태로 문자열화된 리스트 컬럼을 파싱한다."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return list(raw)
    try:
        val = ast.literal_eval(raw)
        return list(val) if isinstance(val, (list, tuple)) else [str(val)]
    except (ValueError, SyntaxError):
        return [raw]


def extract_name(persona_text: str) -> str:
    m = NAME_RE.match(persona_text.strip())
    return m.group(1) if m else "이름미상"


def stratified_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """성별x나이 층화, 각 층의 모집단 비율에 비례 배분 (최대 나머지법으로 합을 n에 맞춤)."""
    if n <= 0 or df.empty:
        return df.head(0)
    strata = df.groupby(["sex", "age"], group_keys=False)
    sizes = strata.size()
    quota_float = sizes / sizes.sum() * n
    quota = quota_float.astype(int)
    remainder = n - quota.sum()
    order = (quota_float - quota).sort_values(ascending=False).index
    for key in order[:remainder]:
        quota[key] += 1

    picked = []
    for key, group in strata:
        k = min(quota.get(key, 0), len(group))
        if k > 0:
            picked.append(group.sample(n=k, random_state=seed))
    out = pd.concat(picked).sample(frac=1, random_state=seed) if picked else df.head(0)
    return out.reset_index(drop=True)


def age_even_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """나이마다 같은 수로 나누고, 남는 인원은 시드로 고른 나이에 한 명씩 더한다.
    각 나이 안에서는 성별 비례층화(stratified_sample)를 그대로 쓴다."""
    ages = sorted(df["age"].unique())
    base, extra = divmod(n, len(ages))
    bonus = set(random.Random(seed).sample(ages, extra))
    picked = [
        stratified_sample(df[df["age"] == age], base + (age in bonus), seed)
        for age in ages
    ]
    return pd.concat(picked).sample(frac=1, random_state=seed).reset_index(drop=True)


def residence_str(row) -> str:
    district = row["district"].split("-", 1)[-1] if "-" in row["district"] else row["district"]
    return f"{row['province']} {district} ({row['family_type']}, {row['housing_type']})"


def to_tinyperson(row, cell: dict) -> tuple[dict, str]:
    name = extract_name(row["persona"])
    gender = GENDER_MAP.get(row["sex"], row["sex"])
    hobbies = parse_list_field(row["hobbies_and_interests_list"])

    other_facts = [
        row["persona"],
        row["professional_persona"],
        row["sports_persona"],
        row["arts_persona"],
        row["travel_persona"],
        row["culinary_persona"],
        row["family_persona"],
        row["cultural_background"],
        f"보유 역량/경험: {row['skills_and_expertise']}",
        f"혼인 상태: {row['marital_status']}, 병역: {row['military_status']}.",
    ]
    other_facts = [f for f in other_facts if isinstance(f, str) and f.strip()]

    persona = {
        "name": name,
        "age": int(row["age"]),
        "gender": gender,
        "nationality": "Korean",
        "residence": residence_str(row),
        "education": cell["education"](row),
        "occupation": {
            "title": cell["occupation_title"](row),
            "organization": "비공개",
            "description": row["career_goals_and_ambitions"],
        },
        "long_term_goals": [row["career_goals_and_ambitions"]],
        "preferences": {
            "likes": hobbies,
        },
        "other_facts": other_facts,
    }
    return {"type": "TinyPerson", "persona": persona}, name


def run_cell(cell_id: str, n: int, seed: int, panel_dir: pathlib.Path, cache: dict) -> list[dict]:
    cell = CELLS[cell_id]
    if cell["source"] not in cache:
        cache[cell["source"]] = pd.read_parquet(DATA_DIR / f"{cell['source']}.parquet")
    df = cache[cell["source"]]
    lo, hi = cell["ages"]
    df = df[df["age"].between(lo, hi)]
    sampler = age_even_sample if cell["sampling"] == "age_even" else stratified_sample
    sample = sampler(df, n, seed)

    manifest = []
    for i, row in sample.iterrows():
        tp_spec, name = to_tinyperson(row, cell)
        pid = f"{cell_id}-{i + 1:02d}"
        fname = f"{pid}_{name}.agent.json"
        (panel_dir / fname).write_text(
            json.dumps(tp_spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append(
            {
                "persona_id": pid,
                "cell": cell_id,
                "group": cell["group"],
                "sampling": cell["sampling"],
                "file": f"panel/{fname}",
                "uuid": row["uuid"],
                "name": name,
                "age": int(row["age"]),
                "sex": row["sex"],
                "province": row["province"],
                "district": row["district"],
                "education_level": row["education_level"],
                "occupation": row["occupation"],
            }
        )
    print(f"[{cell_id} {cell['group']} {lo}~{hi}세, 풀 {len(df)}명] {len(manifest)}명")
    print(sample.groupby(["age", "sex"]).size().unstack(fill_value=0).to_string())
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-per-cell", type=int, default=10, help="칸마다 인원수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=pathlib.Path, default=OUT_DIR)
    args = ap.parse_args()

    panel_dir = args.out_dir / "panel"
    panel_dir.mkdir(parents=True, exist_ok=True)
    for old in panel_dir.glob("*.agent.json"):
        old.unlink()

    manifest, cache = [], {}
    for cell_id in CELLS:
        manifest += run_cell(cell_id, args.n_per_cell, args.seed, panel_dir, cache)

    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"manifest -> {args.out_dir / 'manifest.json'} (총 {len(manifest)}명)")


if __name__ == "__main__":
    main()

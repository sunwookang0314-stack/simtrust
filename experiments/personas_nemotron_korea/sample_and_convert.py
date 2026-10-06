"""재학생/취준생 두 그룹 parquet에서 각각 N명씩 성별x나이 비례층화로 뽑아
TinyTroupe TinyPerson 스펙(JSON)으로 변환한다.

매핑 원칙: Nemotron 쪽에 실제로 있는 값만 쓴다. Big Five, 말투(style) 같은
근거 없는 성격 수치는 지어내지 않고, 있는 그대로의 서술형 필드
(professional_persona, family_persona 등 6종 '페르소나 유형' + cultural_background +
skills_and_expertise)를 other_facts 에 담는다. 자세한 근거는 ../README.md,
../WORK_LOG.md 참고.

사용:
    .venv-data/bin/python experiments/personas_nemotron_korea/sample_and_convert.py \
        --n-students 15 --n-job-seekers 15
"""

import argparse
import ast
import json
import pathlib
import re

import pandas as pd

HERE = pathlib.Path(__file__).parent
DATA_DIR = HERE / "data"
OUT_DIR = HERE / "personas"

NAME_RE = re.compile(r"^([가-힣]{2,4})\s*씨")
GENDER_MAP = {"남자": "Male", "여자": "Female"}

GROUPS = {
    "students_in_progress": {
        "file_prefix": "S",
        "subdir": "students_in_progress",
        "occupation_title": "대학생 (재학 중으로 추정)",
        "education": lambda row: (
            "공개 데이터 특성상 재학 여부를 직접 확인할 수 없어 대학생으로 근사함. "
            f"데이터 상 확인된 최종 완료 학력은 '{row['education_level']}'이며, "
            "아직 상위 학위를 마치지 않은 것으로 보아 재학 중으로 추정함."
        ),
    },
    "job_seekers": {
        "file_prefix": "J",
        "subdir": "job_seekers",
        "occupation_title": "취업준비생 (4년제 대학교 졸업)",
        "education": lambda row: (
            f"{row['education_level']} 졸업 완료 (데이터 상 확정된 최종 학력). "
            "현재 미취업 상태로 구직 중인 것으로 근사함."
        ),
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


def residence_str(row) -> str:
    district = row["district"].split("-", 1)[-1] if "-" in row["district"] else row["district"]
    return f"{row['province']} {district} ({row['family_type']}, {row['housing_type']})"


def to_tinyperson(row, group_key: str) -> tuple[dict, str]:
    spec = GROUPS[group_key]
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
        "education": spec["education"](row),
        "occupation": {
            "title": spec["occupation_title"],
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


def run_group(group_key: str, n: int, seed: int, out_dir: pathlib.Path) -> list[dict]:
    spec = GROUPS[group_key]
    in_path = DATA_DIR / f"{group_key}.parquet"
    df = pd.read_parquet(in_path)
    sample = stratified_sample(df, n, seed)

    group_dir = out_dir / spec["subdir"]
    group_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, row in sample.iterrows():
        tp_spec, name = to_tinyperson(row, group_key)
        fname = f"{spec['file_prefix']}{i + 1:02d}_{name}.agent.json"
        (group_dir / fname).write_text(
            json.dumps(tp_spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append(
            {
                "group": group_key,
                "file": f"{spec['subdir']}/{fname}",
                "uuid": row["uuid"],
                "name": name,
                "age": int(row["age"]),
                "sex": row["sex"],
                "province": row["province"],
                "district": row["district"],
                "education_level": row["education_level"],
            }
        )
    print(f"[{group_key}] saved {len(manifest)} personas -> {group_dir}")
    if not sample.empty:
        print(sample.groupby(["sex", "age"]).size())
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-students", type=int, default=15, help="재학생 그룹 인원수")
    ap.add_argument("--n-job-seekers", type=int, default=15, help="취준생 그룹 인원수")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=pathlib.Path, default=OUT_DIR)
    args = ap.parse_args()

    manifest = []
    manifest += run_group("students_in_progress", args.n_students, args.seed, args.out_dir)
    manifest += run_group("job_seekers", args.n_job_seekers, args.seed, args.out_dir)

    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"manifest -> {args.out_dir / 'manifest.json'} (총 {len(manifest)}명)")


if __name__ == "__main__":
    main()

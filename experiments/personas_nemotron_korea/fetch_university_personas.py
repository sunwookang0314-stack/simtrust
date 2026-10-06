"""nvidia/Nemotron-Personas-Korea에서 '대학생/취준생으로 근사할 수 있는' 레코드를 걸러서 저장한다.

이 데이터셋에는 '대학생' 자체를 나타내는 필드가 없다. occupation에는 직업명 또는 '무직'만 있고,
education_level은 '졸업까지 끝낸 최종 학력'이다.

처음에는 "무직 + (고졸 또는 전문대졸) + 19~26세"로 뭉뚱그렸는데, 샘플 점검 중 이미 전문대를
졸업한 사람(= 재학생이 아니라 그냥 무직 졸업자)이 섞여 있는 걸 발견했고, 나이를 나이별로
쪼개보니 "고졸+무직" 인구가 20~27세 구간에서 거의 평평하다는 것도 확인했다 — 즉 나이가 들수록
졸업해서 줄어드는 게 아니라, 애초에 대학 진학 자체를 안 한 사람들이 섞여서 나이와 무관하게
일정 비율로 존재한다는 뜻이다. 이 데이터셋은애초에 '재학 중'이라는 생애주기 상태를 모델링하지
않는다 (자세한 수치 근거는 WORK_LOG.md).

그래서 "재학생"과 "취준생"을 구분되는 두 그룹으로 나눠 각각 더 명확한 조건으로 근사한다:

  재학생 (아직 학위를 안 끝낸, 가장 흔한 '학생' 나이대):
    occupation = '무직' AND education_level = '고등학교'
    AND age BETWEEN 19 AND 25 AND marital_status = '미혼'
    (전문대 졸업자는 제외 — 이미 학위를 끝낸 사람이라 재학생이 아님)

  취준생 (4년제 졸업 후 아직 취업 전):
    occupation = '무직' AND education_level = '4년제 대학교'
    AND age BETWEEN 23 AND 27 AND marital_status = '미혼'
    (4년제 완료는 22세부터만 나타나므로 '졸업 완료'가 명확함 — 재학생 쪽보다 훨씬 깨끗한 정의)

여전히 완벽한 식별은 아니다 (군필 지연, 조기취업 등은 반영 못함). 근거와 트레이드오프는
WORK_LOG.md 참고.

사용:
    .venv-data/bin/python experiments/personas_nemotron_korea/fetch_university_personas.py
"""

import argparse
import pathlib

import duckdb

DATASET = "nvidia/Nemotron-Personas-Korea"
NUM_SHARDS = 9
RESOLVE_BASE = f"https://huggingface.co/datasets/{DATASET}/resolve/main/data"

OUT_DIR = pathlib.Path(__file__).parent / "data"

GROUPS = {
    "students_in_progress": """
        occupation = '무직'
        AND education_level = '고등학교'
        AND age BETWEEN 19 AND 25
        AND marital_status = '미혼'
    """,
    "job_seekers": """
        occupation = '무직'
        AND education_level = '4년제 대학교'
        AND age BETWEEN 23 AND 27
        AND marital_status = '미혼'
    """,
}


def shard_urls() -> list[str]:
    return [
        f"{RESOLVE_BASE}/train-{i:05d}-of-{NUM_SHARDS:05d}.parquet"
        for i in range(NUM_SHARDS)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=OUT_DIR, type=pathlib.Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    urls = ", ".join(f"'{u}'" for u in shard_urls())

    for name, filter_sql in GROUPS.items():
        out_path = args.out_dir / f"{name}.parquet"
        query = f"""
            SELECT *
            FROM read_parquet([{urls}])
            WHERE {filter_sql}
        """
        con.execute(f"COPY ({query}) TO '{out_path}' (FORMAT PARQUET)")
        count = con.execute(f"SELECT count(*) FROM read_parquet('{out_path}')").fetchone()[0]
        print(f"[{name}] saved {count} rows -> {out_path}")


if __name__ == "__main__":
    main()

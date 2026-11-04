"""AI 응답 추출기 뼈대 (TRD IF-06). 원시 응답에서 기능별 쓸/안 쓸, 이유, 4-6 보기를 뽑는다.

입력은 scripts/run_simulation.py가 남긴 원시 응답(raw_responses.jsonl, 질문 단위 answers)이다.
외부 AI를 쓰지 않고 규칙으로만 뽑는다. 규칙으로 못 가린 줄은 버리지 않고 needs_review로 남겨서 2차 검토가 본다.

- 쓸/안 쓸: Q-AI-USE 답에서 기능마다 판별 (run_simulation.parse_use_answers와 같은 규칙)
- 쓸 이유: Q-AI-WHY-USE 답을 줄(문장)로 나눠 기능 이름이 들어간 줄을 그 기능의 이유로 본다
- 안 쓸 보기: Q-AI-NOUSE 답에서 기능 줄마다 4-6 보기 글자가 들어 있는지 본다 (여러 개 가능)
- 4-7 서술: Q-4-7 답을 같은 방식으로 기능마다 나눈다
- 답 하나당 이유 개수 (프로토콜 3번): 기능에 붙은 줄 수

이유를 코드북 유형으로 나누는 일은 코드북(#28)이 고정된 뒤에 붙인다.
사람 응답은 이 스크립트에 넣지 않는다. 사람 응답은 사람이 정리한다(폼에서 "외부 AI 서비스에 보내지 않는다"고 약속했다).

실행 (리포 루트):
    python scripts/extract_reasons.py --raw runs/dev/raw_responses.jsonl --out runs/dev/extracted

화면에는 숫자만 찍는다. 실제 캡처 시범 결과는 코드북 작성자·정리 담당·판정자에게 비공개다.
종료 코드: 0 정상, 1 입력 파일 없음, 4 입력 검증 실패
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_simulation as rs  # noqa: E402

ROOT = rs.ROOT
EXIT_OK, EXIT_USAGE, EXIT_INPUT = 0, 1, 4
SOURCES = ("talk", "think_talk")
# 폼 서술 답에 어느 출력을 맞출지는 실제 캡처 시범 전에 정한다(프로토콜 10번). 참고 초안 제안은 TALK만이다
DEFAULT_SOURCE = "talk"
# 원시 응답 한 줄에 꼭 있어야 하는 칸
REQUIRED = ["run_id", "service", "platform", "condition", "persona_id", "repeat", "features", "answers"]
CSV_FIELDS = ["run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id", "feature_name",
              "kind", "text", "options", "needs_review"]


def split_pieces(text: str) -> list:
    """줄마다 문장 목록을 돌려준다. 폼 서술 문항이 "기능마다 줄을 바꿔서"라서 한 줄을 한 기능으로 본다."""
    lines = []
    for line in (text or "").split("\n"):
        sentences = [p.strip(" -\u2022\t") for p in re.split(r"(?<=[.!?。])\s+|;", line)]
        sentences = [p for p in sentences if p]
        if sentences:
            lines.append(sentences)
    return lines


def features_in(piece: str, features: list) -> list:
    return [fid for fid, name in features if any(k in piece for k in rs.feature_keys(name))]


def strip_feature_prefix(piece: str, name: str) -> str:
    for key in rs.feature_keys(name):
        if piece.startswith(key):
            rest = piece[len(key):]
            return re.sub(r"^\s*[:\uff1a\-\u2013]\s*|^\s*(은|는|이|가)\s+", "", rest).strip() or piece
    return piece


def assign(text: str, features: list):
    """문장마다 기능을 붙인다. 기능 이름이 없는 문장은 같은 줄 앞 문장의 기능을 이어받는다.
    줄 첫 문장부터 기능 이름이 없거나, 한 문장에 기능 이름이 둘 이상이면 검토 목록으로 보낸다."""
    by_feature = {fid: [] for fid, _ in features}
    review = []
    names = dict(features)
    for sentences in split_pieces(text):
        current = None
        for piece in sentences:
            hits = features_in(piece, features)
            if len(hits) == 1:
                current = hits[0]
                by_feature[current].append(strip_feature_prefix(piece, names[current]))
            elif not hits and current:
                by_feature[current].append(piece)
            else:
                current = None
                review.append({"text": piece, "features": hits,
                               "why": "기능 이름이 없음" if not hits else "기능 이름이 둘 이상"})
    return by_feature, review


def options_in(piece: str, options: list) -> list:
    flat = re.sub(r"\s+", "", piece)
    return [o for o in options if re.sub(r"\s+", "", o) in flat]


def answer_text(answer: dict, source: str) -> str:
    if source == "think_talk":
        return "\n".join(x for x in (answer.get("think"), answer.get("talk")) if x)
    return answer.get("talk") or ""


def extract_episode(line: dict, options: list, source: str) -> tuple:
    features = [(f["feature_id"], f["name"]) for f in line["features"]]
    missing = {a["feature_id"] for a in line["answers"] if not a.get("asked") and a.get("skipped") == "없음"}
    asked_features = [f for f in features if f[0] not in missing]
    answers = {a["question_id"]: a for a in line["answers"] if a.get("asked")}

    use_text = answer_text(answers.get("Q-AI-USE", {}), source)
    use_choice = rs.parse_use_answers(use_text, asked_features) if use_text else {}
    why, why_review = assign(answer_text(answers.get("Q-AI-WHY-USE", {}), source), asked_features)
    nouse, nouse_review = assign(answer_text(answers.get("Q-AI-NOUSE", {}), source), asked_features)
    q47, q47_review = assign(answer_text(answers.get("Q-4-7", {}), source), asked_features)

    base = {k: line.get(k) for k in ("run_id", "batch_id", "service", "platform", "condition", "persona_id",
                                     "repeat", "protocol_version", "snapshot_version", "input_mode")}
    records = []
    for fid, name in features:
        if fid in missing:
            records.append({**base, "feature_id": fid, "feature_name": name, "asked": False, "skipped": "없음",
                            "source": source})
            continue
        picked = sorted({o for piece in nouse[fid] for o in options_in(piece, options)}, key=options.index)
        unmatched = [piece for piece in nouse[fid] if not options_in(piece, options)]
        records.append({
            **base,
            "feature_id": fid,
            "feature_name": name,
            "asked": True,
            "source": source,
            "use_choice": use_choice.get(fid, "unknown"),
            "use_reasons": why[fid],
            "nouse_lines": nouse[fid],
            "nouse_options": picked,
            "q47_details": q47[fid],
            # 프로토콜 3번: 쓸·안 쓸 이유 답 하나당 이유 개수
            "reason_counts": {"why_use": len(why[fid]), "nouse": len(nouse[fid]), "q47": len(q47[fid])},
            "needs_review": ["4-6 보기를 못 찾은 줄"] if unmatched else [],
        })
    review = ([{"question_id": "Q-AI-WHY-USE", **r} for r in why_review]
              + [{"question_id": "Q-AI-NOUSE", **r} for r in nouse_review]
              + [{"question_id": "Q-4-7", **r} for r in q47_review])
    if use_text and any(v == "unknown" for v in use_choice.values()):
        review.append({"question_id": "Q-AI-USE", "text": "", "features": [k for k, v in use_choice.items()
                                                                          if v == "unknown"],
                       "why": "쓸/안 쓸을 못 가림"})
    return records, review


def csv_rows(records: list, reviews: list) -> list:
    rows = []
    for r in records:
        common = {k: r.get(k) for k in ("run_id", "service", "platform", "condition", "persona_id", "repeat",
                                        "feature_id", "feature_name")}
        if not r.get("asked"):
            rows.append({**common, "kind": "skipped", "text": "없음", "options": "", "needs_review": ""})
            continue
        rows.append({**common, "kind": "use_choice", "text": r["use_choice"], "options": "",
                     "needs_review": "Y" if r["use_choice"] == "unknown" else ""})
        for t in r["use_reasons"]:
            rows.append({**common, "kind": "why_use", "text": t, "options": "", "needs_review": ""})
        for t in r["nouse_lines"]:
            opts = [o for o in r["nouse_options"] if re.sub(r"\s+", "", o) in re.sub(r"\s+", "", t)]
            rows.append({**common, "kind": "nouse", "text": t, "options": " / ".join(opts),
                         "needs_review": "" if opts else "Y"})
        for t in r["q47_details"]:
            rows.append({**common, "kind": "q47", "text": t, "options": "", "needs_review": ""})
    for v in reviews:
        rows.append({"run_id": v["run_id"], "feature_id": ",".join(v["features"]), "kind": f"review:{v['question_id']}",
                     "text": v["text"], "options": "", "needs_review": v["why"]})
    return rows


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="AI 응답 추출기 뼈대 (TRD IF-06)")
    ap.add_argument("--raw", required=True, help="원시 응답 JSONL")
    ap.add_argument("--options", default="experiments/runner_dev/protocol/options_4-6.txt",
                    help="4-6 보기 파일 (실행에 쓴 프로토콜과 같은 파일)")
    ap.add_argument("--out", required=True, help="출력 폴더")
    ap.add_argument("--source", default=DEFAULT_SOURCE, choices=SOURCES)
    args = ap.parse_args(argv)

    raw_path, opt_path = root / args.raw, root / args.options
    for path, what in ((raw_path, "원시 응답"), (opt_path, "4-6 보기")):
        if not path.is_file():
            print(f"[중단] {what} 파일이 없다: {path}", file=sys.stderr)
            return EXIT_USAGE
    options = [x.strip() for x in rs._read_text(opt_path).split("\n") if x.strip()]

    lines, problems = [], []
    for n, text in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            line = json.loads(text)
        except json.JSONDecodeError as e:
            problems.append(f"{n}행: JSON으로 읽지 못했다 ({e})")
            continue
        lacking = [k for k in REQUIRED if k not in line]
        if lacking:
            # 1단계 형식(steps)이 섞여 있으면 여기서 걸린다
            problems.append(f"{n}행: 2단계 원시 응답 형식이 아니다 (없는 칸: {', '.join(lacking)})")
            continue
        lines.append(line)
    if problems:
        print("[중단] 입력 검증 실패\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return EXIT_INPUT

    records, reviews = [], []
    for line in lines:
        recs, rev = extract_episode(line, options, args.source)
        records += recs
        reviews += [{"run_id": line["run_id"], **r} for r in rev]

    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    jsonl = out / f"extracted_{stamp}.jsonl"
    jsonl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    review_path = out / f"review_{stamp}.csv"
    # 2차 검토용. 엑셀에서 한글이 안 깨지게 BOM을 붙인다
    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in csv_rows(records, reviews):
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})

    asked = [r for r in records if r["asked"]]
    choices = Counter(r["use_choice"] for r in asked)
    per_answer = {k: [r["reason_counts"][k] for r in asked if r["reason_counts"][k]] for k in ("why_use", "q47")}
    summary = {
        "episodes": len(lines),
        "feature_records": len(records),
        "skipped_features": len(records) - len(asked),
        "use_choice": dict(choices),
        "reasons_per_answer_mean": {k: round(sum(v) / len(v), 2) if v else None for k, v in per_answer.items()},
        "nouse_options": dict(Counter(o for r in asked for o in r["nouse_options"])),
        "needs_review": len(reviews) + sum(1 for r in asked if r["needs_review"]),
        "source": args.source,
        "files": {"records": rs._rel(jsonl, root), "review": rs._rel(review_path, root)},
    }
    (out / f"summary_{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 60)
    print(f"[추출] 에피소드 {summary['episodes']}개, 기능 기록 {summary['feature_records']}개 "
          f"(캡처 없어 안 물은 기능 {summary['skipped_features']}개)")
    print(f"  쓸/안 쓸     : {dict(choices)}")
    print(f"  답당 이유 수 : 쓸 이유 {summary['reasons_per_answer_mean']['why_use']}, "
          f"4-7 {summary['reasons_per_answer_mean']['q47']}")
    print(f"  검토 필요    : {summary['needs_review']}건")
    print(f"  기록: {summary['files']['records']}, 검토표: {summary['files']['review']}")
    print("=" * 60)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

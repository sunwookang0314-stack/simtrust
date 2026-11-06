"""AI 응답 추출기 뼈대 (TRD IF-06). 원시 응답에서 기능별 쓸/안 쓸, 이유, 4-6 보기를 뽑는다.

입력은 scripts/run_simulation.py가 남긴 원시 응답(raw_responses.jsonl, 질문 단위 answers)이다.
외부 AI를 쓰지 않고 규칙으로만 뽑는다. 규칙으로 못 가린 줄은 버리지 않고 needs_review로 남겨서 2차 검토가 본다.

- 쓸/안 쓸: Q-AI-USE 답에서 기능마다 판별 (run_simulation.parse_use_answers와 같은 규칙)
- 쓸 이유: Q-AI-WHY-USE 답을 줄(문장)로 나눠 기능 이름이 들어간 줄을 그 기능의 이유로 본다
- 안 쓸 보기: Q-AI-NOUSE 답에서 기능 줄마다 4-6 보기 글자가 들어 있는지 본다 (여러 개 가능)
- 4-7 서술: Q-4-7 답을 같은 방식으로 기능마다 나눈다. "한 번도 안 써봤습니다."처럼 써 봤는지만 말한 문장은
  이유 줄에서 빼고 q47_status에 따로 둔다 (폼 4-7이 써 봤는지를 먼저 말하게 해서 실제 답에 늘 붙는다)
- 머리말: 기능 줄 앞에 오는 "'쓸 것 같다'고 선택한 기능별 상세 답변입니다." 같은 줄은 검토 목록에 넣지 않고
  검토표에 intro로만 남긴다
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
# 머리말로 보는 말. 기능 이름이 없고, 첫 기능 줄보다 앞에 있고, "입니다"나 ":"로 끝날 때만 본다 (11/5 실제 답)
INTRO_WORDS = ("답변", "의견", "정리", "다음과 같", "아래와 같", "선택한 기능", "고른 기능", "말씀드리")
# "말씀드립니다", "답변드립니다"처럼 받침 ㅂ으로 끝나는 말도 있어서 "니다"로 본다 (11/6 실제 답)
INTRO_END = re.compile(r"니다[.:：]?$|[:：]$")
# 4-7에서 써 봤는지만 말한 문장. 문장 전체가 이것일 때만 뺀다 ("안 써봤고 검색으로 찾습니다"는 이유로 남긴다)
STATUS = re.compile(
    r"^(저는\s*|이\s*기능은\s*|아직\s*)*(한\s*번도\s*)?"
    r"(안\s*(써|사용해)\s*봤|(써|사용해)\s*본\s*적\s*(이|은|도)?\s*(한\s*번도\s*)?없|(써|사용해)\s*보지\s*(않았|못했))"
    r"(습니다|어요|어|다|음|네요|요)?[.!。~\s]*$")


# 폼이 "해당하는 기능이 없다면 없음이라고 적어주세요"라고 시킨 답. 이유도 검토 대상도 아니다
NONE = re.compile(r"^(해당\s*(하는\s*기능\s*)?)?(없음|없습니다|없어요)[.!]?$")
MARKUP = re.compile(r"\*\*|__|`")
BULLET = re.compile(r"^\s*(?:[-*\u2022\u00b7]|\d+[.)])\s+")


def split_pieces(text: str) -> list:
    """줄마다 문장 목록을 돌려준다. 폼 서술 문항이 "기능마다 줄을 바꿔서"라서 한 줄을 한 기능으로 본다.
    문장으로 나누기 전에 굵게(**)와 글머리(-, *, 1.)를 지운다. 안 지우면 "1."이 문장 하나로 떨어진다."""
    lines = []
    for line in (text or "").split("\n"):
        line = BULLET.sub("", MARKUP.sub("", line))
        sentences = [p.strip(" -\u2022\t") for p in re.split(r"(?<=[.!?。])\s+|;", line)]
        sentences = [p for p in sentences if p]
        if sentences:
            lines.append(sentences)
    return lines


def features_in(piece: str, features: list) -> list:
    return [fid for fid, name in features if any(k in piece for k in rs.feature_keys(name))]


def lead_feature(piece: str, features: list):
    """문장이 기능 이름으로 시작하면 그 기능. 뒤에 다른 기능 이름이 나와도 앞 기능 줄로 본다."""
    for fid, name in features:
        if any(piece.startswith(k) for k in rs.feature_keys(name)):
            return fid
    return None


def strip_feature_prefix(piece: str, name: str) -> str:
    """기능 이름을 뗀 나머지. 이름만 있는 줄(목록 머리)이면 빈 문자열."""
    for key in rs.feature_keys(name):
        if piece.startswith(key):
            rest = re.sub(r"^\s*\([^)]*\)", "", piece[len(key):])  # "공고 저장(스크랩, 찜, 북마크):"
            return re.sub(r"^\s*[:\uff1a\-\u2013]\s*|^\s*(은|는|이|가)\s+", "", rest).strip()
    return piece


def is_intro(sentences: list, features: list) -> bool:
    text = " ".join(sentences).strip()
    return (not any(features_in(p, features) for p in sentences)
            and any(w in text for w in INTRO_WORDS) and bool(INTRO_END.search(text)))


def assign(text: str, features: list, sole: str = None):
    """문장마다 기능을 붙인다. 기능 이름이 없는 문장은 같은 줄 앞 문장의 기능을 이어받는다.
    - 기능 이름만 있는 줄(목록 머리) 아래 줄들은 다음 기능 줄이 나올 때까지 그 기능을 이어받는다
    - 문장이 기능 이름으로 시작하면 뒤에 다른 기능 이름이 있어도 앞 기능으로 본다
    - 이 질문의 대상 기능이 하나뿐이면(sole) 기능 이름 없는 줄을 그 기능에 붙이고 attached로 센다
    - 그래도 못 가리면 검토 목록으로 보낸다. 첫 기능 줄보다 앞에 있는 머리말 줄은 intro로 따로 돌려준다."""
    by_feature = {fid: [] for fid, _ in features}
    review, intro, attached = [], [], []
    names = dict(features)
    seen_feature = False
    heading = None
    for sentences in split_pieces(text):
        if not seen_feature and is_intro(sentences, features):
            intro.append(" ".join(sentences))
            continue
        seen_feature = seen_feature or any(features_in(p, features) for p in sentences)
        current = None
        for i, piece in enumerate(sentences):
            if NONE.match(piece):
                continue
            hits = features_in(piece, features)
            lead = lead_feature(piece, features) if len(hits) > 1 else None
            fid = hits[0] if len(hits) == 1 else lead
            if fid:
                current = fid
                rest = strip_feature_prefix(piece, names[fid])
                if rest:
                    by_feature[fid].append(rest)
                heading = fid if (not rest and i == len(sentences) - 1 and len(sentences) == 1) else None
            elif not hits and current:
                by_feature[current].append(piece)
            elif not hits and heading:
                by_feature[heading].append(piece)
                current = heading
            elif not hits and sole:
                by_feature[sole].append(piece)
                attached.append(piece)
                current = sole
            else:
                current = None
                review.append({"text": piece, "features": hits,
                               "why": "기능 이름이 없음" if not hits else "기능 이름이 둘 이상"})
    return by_feature, review, intro, attached


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

    use_ans = answers.get("Q-AI-USE", {})
    # 실행기와 같은 규칙: TALK이 비면 THINK로 판별한다 (run_simulation.py에서 parse_use_answers 부르는 곳)
    use_text = answer_text(use_ans, source) or (use_ans.get("think") or "")
    use_choice = rs.parse_use_answers(use_text, asked_features)
    used = [f for f, v in use_choice.items() if v == "use"]
    unused = [f for f, v in use_choice.items() if v == "nouse"]
    # 이 질문의 대상 기능이 하나뿐이면 기능 이름 없는 줄을 그 기능에 붙인다
    sole_use = used[0] if len(used) == 1 else None
    sole_nouse = unused[0] if len(unused) == 1 else None
    why, why_review, why_intro, why_att = assign(answer_text(answers.get("Q-AI-WHY-USE", {}), source),
                                                 asked_features, sole_use)
    nouse, nouse_review, nouse_intro, nouse_att = assign(answer_text(answers.get("Q-AI-NOUSE", {}), source),
                                                         asked_features, sole_nouse)
    q47_all, q47_review, q47_intro, q47_att = assign(answer_text(answers.get("Q-4-7", {}), source),
                                                     asked_features, sole_nouse)
    q47 = {fid: [p for p in v if not STATUS.match(p)] for fid, v in q47_all.items()}
    q47_status = {fid: [p for p in v if STATUS.match(p)] for fid, v in q47_all.items()}
    notes = []
    for qid, intro_, att in (("Q-AI-WHY-USE", why_intro, why_att), ("Q-AI-NOUSE", nouse_intro, nouse_att),
                             ("Q-4-7", q47_intro, q47_att)):
        notes += [{"question_id": qid, "kind": "intro", "text": t} for t in intro_]
        notes += [{"question_id": qid, "kind": "attached", "text": t} for t in att]

    base = {k: line.get(k) for k in ("run_id", "batch_id", "service", "platform", "condition", "persona_id",
                                     "repeat", "protocol_version", "snapshot_version", "input_mode", "model")}
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
            "q47_status": q47_status[fid],
            # 프로토콜 3번: 쓸·안 쓸 이유 답 하나당 이유 개수
            "reason_counts": {"why_use": len(why[fid]), "nouse": len(nouse[fid]), "q47": len(q47[fid])},
            "needs_review": ["4-6 보기를 못 찾은 줄"] if unmatched else [],
        })
    review = ([{"question_id": "Q-AI-WHY-USE", **r} for r in why_review]
              + [{"question_id": "Q-AI-NOUSE", **r} for r in nouse_review]
              + [{"question_id": "Q-4-7", **r} for r in q47_review])
    if any(v == "unknown" for v in use_choice.values()):
        review.append({"question_id": "Q-AI-USE", "text": "", "features": [k for k, v in use_choice.items()
                                                                          if v == "unknown"],
                       "why": "쓸/안 쓸을 못 가림"})
    runtime = line.get("use_parsed_at_runtime") or {}
    differ = [f for f, v in runtime.items() if f in use_choice and v != use_choice[f]]
    if differ:
        # 실행기는 이 판별로 꼬리 질문을 골랐다. 다르면 물어야 할 질문을 건너뛰었을 수 있다
        review.append({"question_id": "Q-AI-USE", "text": "", "features": differ,
                       "why": "실행 중 쓸/안 쓸 판별과 다름"})
    return records, review, notes


def csv_rows(records: list, reviews: list, notes: list = ()) -> list:
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
        for t in r.get("q47_status", []):
            rows.append({**common, "kind": "q47_status", "text": t, "options": "", "needs_review": ""})
    for v in reviews:
        rows.append({"run_id": v["run_id"], "feature_id": ",".join(v["features"]), "kind": f"review:{v['question_id']}",
                     "text": v["text"], "options": "", "needs_review": v["why"]})
    for v in notes:
        # intro: 머리말이라 뺀 줄, attached: 대상 기능이 하나뿐이라 그 기능에 붙인 줄
        rows.append({"run_id": v["run_id"], "feature_id": "", "kind": f"{v['kind']}:{v['question_id']}",
                     "text": v["text"], "options": "", "needs_review": ""})
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

    records, reviews, notes = [], [], []
    for line in lines:
        recs, rev, note = extract_episode(line, options, args.source)
        records += recs
        reviews += [{"run_id": line["run_id"], **r} for r in rev]
        notes += [{"run_id": line["run_id"], **r} for r in note]

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
        for row in csv_rows(records, reviews, notes):
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
        "intro_lines": sum(1 for v in notes if v["kind"] == "intro"),
        "attached_lines": sum(1 for v in notes if v["kind"] == "attached"),
        "q47_status_lines": sum(len(r.get("q47_status", [])) for r in asked),
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
    print(f"  따로 둔 줄   : 머리말 {summary['intro_lines']}개, 4-7 사용 상태 {summary['q47_status_lines']}개 "
          "(이유로 세지 않음, 검토표에 남김)")
    print(f"  붙인 줄      : 기능 이름 없이 대상 기능 하나에 붙인 줄 {summary['attached_lines']}개 (검토표에 남김)")
    print(f"  기록: {summary['files']['records']}, 검토표: {summary['files']['review']}")
    print("=" * 60)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

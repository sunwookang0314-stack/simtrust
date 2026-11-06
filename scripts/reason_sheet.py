"""AI 이유 판정용 시트 (TRD IF-13 이유 매칭 후보, IF-09 판정 반영을 폼 B v2에 맞춘 것).

make: 추출 결과(extract_reasons.py의 extracted_*.jsonl)에서 AI 이유를 한 줄씩 꺼내 판정자가 코드를 채울 시트를 만든다.
  - 시트에는 조건·페르소나·반복 번호를 넣지 않고 순서도 섞는다. 판정자가 어느 조건 답인지 모르게 하려는 것이다
  - 줄과 에피소드를 잇는 대응표(key)는 따로 둔다. 판정자에게는 시트만 준다
  - 판정자 둘이 따로 code_1, code_2를 채우고, 맞춰 본 뒤 code_final을 채운다
  - 코드는 코드북(#28) 코드를 쓴다. 이유가 아닌 줄은 '-', 한 줄에 이유가 여럿이면 ';'로 나눈다
  - 코드북에 없는 이유는 판정자가 새 코드를 붙인다(같은 이유면 같은 새 코드). 사람 코드와 안 겹치면 통과 못 한 이유로 센다
import: 채운 시트와 대응표를 합쳐 score_reasons.py가 읽는 AI 코드 CSV를 만든다
  - 빈칸이 하나라도 있거나 두 판정자 칸이 덜 찼으면 아무것도 쓰지 않고 멈춘다 (TRD IF 공통 규칙)
  - 두 판정자의 일치율과 Cohen's kappa를 남긴다

사람 응답은 이 스크립트에 넣지 않는다. 시트에는 AI 답만 들어간다.

실행 (리포 루트):
    python scripts/reason_sheet.py make --extracted runs/dev/extracted/extracted_X.jsonl --out runs/dev/sheet
    python scripts/reason_sheet.py import --sheet <채운 시트> --key <대응표> --out runs/dev/coded

화면에는 숫자만 찍는다.
종료 코드: 0 정상, 1 입력 파일 없음·사용법, 4 입력 검증 실패
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXIT_OK, EXIT_USAGE, EXIT_INPUT = 0, 1, 4

SHEET_FIELDS = ["item_id", "service", "platform", "feature_name", "kind", "source", "text", "options_found",
                "code_1", "code_2", "code_final", "note"]
KEY_FIELDS = ["item_id", "run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id",
              "kind", "source", "input_mode", "model"]
AI_CODE_FIELDS = ["item_id", "run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id",
                  "kind", "input_mode", "model", "code"]
REQUIRED = ["run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id", "asked"]
JUDGE_COLS = ("code_1", "code_2", "code_final")
KAPPA_MIN = 0.6  # TRD NFR-07. 못 미치면 판정 기준을 다듬고 다시 판정한다
# 같은 페르소나·회차가 두 번 들어가면(실패 뒤 다시 돌린 경우 등) 한 칸에서 두 번 센다
EPISODE_KEY = ("service", "platform", "condition", "persona_id", "repeat", "input_mode", "model")
DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u30fc"), "-")


class InputError(Exception):
    pass


def item_id(*parts) -> str:
    return "R" + hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:10]


def items_from_record(r: dict) -> tuple:
    """추출 레코드 하나(에피소드 x 기능)에서 판정할 이유 줄을 꺼낸다.

    쓸 이유: Q-AI-WHY-USE 줄. 안 쓸 이유: Q-AI-NOUSE 줄(4-6 보기 포함)과 Q-4-7 줄.
    사람 쪽에서 4-3과 안 맞는 칸을 빼듯이, AI도 쓸/안 쓸 판별과 안 맞는 줄은 넣지 않고 개수만 센다.
    (쓸 것 같다고 한 기능의 안 쓸 이유·4-7 줄, 안 쓸 것 같다고 한 기능의 쓸 이유 줄. 못 가린 기능은 다 넣는다)
    """
    if not r.get("asked"):
        return [], 0
    base = {k: r[k] for k in ("run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id")}
    base.update({k: r.get(k) or "" for k in ("input_mode", "model")})
    choice = r.get("use_choice")
    groups = [("use", "why_use", r.get("use_reasons", []), choice != "nouse"),
              ("nouse", "nouse", r.get("nouse_lines", []), choice != "use"),
              ("nouse", "q47", r.get("q47_details", []), choice != "use")]
    lines = [(kind, source, t) for kind, source, texts, keep in groups if keep for t in texts]
    skipped = sum(len(texts) for _, _, texts, keep in groups if not keep)
    out = []
    squash = re.compile(r"\s+")
    for i, (kind, source, text) in enumerate(lines):
        opts = [o for o in r.get("nouse_options", []) if squash.sub("", o) in squash.sub("", text)] \
            if source == "nouse" else []
        out.append({**base, "item_id": item_id(base["run_id"], base["feature_id"], source, i, text),
                    "feature_name": r.get("feature_name", ""), "kind": kind, "source": source, "text": text,
                    "options_found": " / ".join(opts)})
    return out, skipped


def read_jsonl(path: Path) -> list:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            raise InputError(f"{path.name} {n}행: JSON을 못 읽음") from None
    return rows


def read_csv(path: Path, required: list) -> list:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"{path.name}: 칸이 없음 {missing}")
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]


def write_csv(path: Path, fields: list, rows: list) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def norm_codes(cell: str) -> list:
    """'b; A ;A' -> ['A', 'B']. 순서와 중복은 판정에 상관없다.
    전각 글자와 엑셀이 바꾼 긴 대시를 되돌리고 대문자로 맞춘다 (score_reasons.norm_code와 같은 규칙)."""
    cell = unicodedata.normalize("NFKC", cell).translate(DASHES)
    return sorted({c.strip().upper() for c in cell.split(";") if c.strip()})


def kappa(a: list, b: list):
    """Cohen's kappa. 두 판정자가 붙인 코드 묶음을 한 라벨로 보고 잰다."""
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def cmd_make(args, root: Path) -> int:
    path = root / args.extracted
    if not path.is_file():
        print(f"[오류] 입력 파일 없음: {args.extracted}", file=sys.stderr)
        return EXIT_USAGE
    try:
        records = read_jsonl(path)
        for n, r in enumerate(records, 1):
            missing = [k for k in REQUIRED if k not in r]
            if missing:
                raise InputError(f"{path.name} {n}번째 레코드: 칸이 없음 {missing} (extract_reasons.py 결과가 맞나?)")
    except (InputError, UnicodeDecodeError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        return EXIT_INPUT
    items, skipped = [], 0
    for r in records:
        got, sk = items_from_record(r)
        items += got
        skipped += sk
    if not items:
        print("[입력 오류] 판정할 이유 줄이 없음", file=sys.stderr)
        return EXIT_INPUT
    runs = {}
    for i in items:
        runs.setdefault(tuple(str(i.get(k, "")) for k in EPISODE_KEY), set()).add(i["run_id"])
    twice = sum(1 for v in runs.values() if len(v) > 1)
    if twice:
        print(f"[입력 오류] 같은 페르소나·회차가 실행 ID만 바뀌어 두 번 들어 있음 {twice}건 "
              "(실패 뒤 다시 돌린 기록이 섞였나?). 하나만 남기고 다시 추출한다", file=sys.stderr)
        return EXIT_INPUT
    ids = [i["item_id"] for i in items]
    if len(set(ids)) != len(ids):
        print("[입력 오류] 같은 줄이 두 번 들어 있음 (같은 추출 파일을 두 번 합쳤나?)", file=sys.stderr)
        return EXIT_INPUT
    random.Random(args.seed).shuffle(items)  # 조건·페르소나 순서가 시트 순서로 드러나지 않게
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    sheet = [{**i, "code_1": "", "code_2": "", "code_final": "", "note": ""} for i in items]
    write_csv(out / f"sheet_{stamp}.csv", SHEET_FIELDS, sheet)
    write_csv(out / f"key_{stamp}.csv", KEY_FIELDS, sorted(items, key=lambda i: i["item_id"]))
    kinds = Counter(i["kind"] for i in items)
    print(f"[시트] 이유 줄 {len(items)}개 (쓸 이유 {kinds['use']}, 안 쓸 이유 {kinds['nouse']}), "
          f"에피소드 {len({i['run_id'] for i in items})}개")
    if skipped:
        print(f"  쓸/안 쓸 판별과 안 맞는 줄 {skipped}개는 넣지 않음 (쓴다고 한 기능의 4-7 줄 등)")
    if len({i["condition"] for i in items}) < 2:
        print("  주의: 시트에 조건이 하나뿐이다. 판정자가 조건을 짐작할 수 있으니 본 판정은 조건을 섞어서 만든다")
    print(f"  판정자에게 줄 것: {args.out}/sheet_{stamp}.csv")
    print(f"  판정자에게 주지 않을 것: {args.out}/key_{stamp}.csv (조건이 들어 있음)")
    return EXIT_OK


def cmd_import(args, root: Path) -> int:
    paths = {"sheet": root / args.sheet, "key": root / args.key}
    for name, p in paths.items():
        if not p.is_file():
            print(f"[오류] 입력 파일 없음: --{name}", file=sys.stderr)
            return EXIT_USAGE
    try:
        sheet = read_csv(paths["sheet"], ["item_id", *JUDGE_COLS])
        key = {r["item_id"]: r for r in read_csv(paths["key"], KEY_FIELDS)}
    except (InputError, UnicodeDecodeError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        return EXIT_INPUT
    ids = [r["item_id"] for r in sheet]
    problems = []
    if len(set(ids)) != len(ids):
        problems.append(f"시트에 같은 item_id가 {len(ids) - len(set(ids))}번 더 있음")
    if set(ids) - set(key):
        problems.append(f"대응표에 없는 줄 {len(set(ids) - set(key))}개")
    if set(key) - set(ids):
        problems.append(f"시트에서 빠진 줄 {len(set(key) - set(ids))}개")
    for col in JUDGE_COLS:
        blank = sum(not norm_codes(r[col]) for r in sheet)
        if blank:
            problems.append(f"{col} 빈칸 {blank}개")
        comma = sum("," in unicodedata.normalize("NFKC", r[col]) for r in sheet)
        if comma:
            problems.append(f"{col}에 쉼표 {comma}개 (코드가 여럿이면 ;로 나눈다)")
    if problems:
        print("[입력 오류] 시트를 다 채우지 않았음: " + ", ".join(problems), file=sys.stderr)
        return EXIT_INPUT

    a = [";".join(norm_codes(r["code_1"])) for r in sheet]
    b = [";".join(norm_codes(r["code_2"])) for r in sheet]
    agree = sum(x == y for x, y in zip(a, b))
    k_value = kappa(a, b)
    low_kappa = k_value is None or k_value < KAPPA_MIN
    if low_kappa and not args.accept_low_kappa:
        print(f"[입력 오류] 두 판정자 kappa {k_value}가 {KAPPA_MIN}에 못 미친다 (TRD NFR-07). "
              "판정 기준을 다듬고 다시 판정한다. 그대로 쓰려면 --accept-low-kappa \"사유\"를 붙인다", file=sys.stderr)
        return EXIT_INPUT
    rows = []
    for r in sorted(sheet, key=lambda x: x["item_id"]):
        k = key[r["item_id"]]
        for code in norm_codes(r["code_final"]):
            rows.append({**{f: k[f] for f in AI_CODE_FIELDS if f != "code"}, "code": code})
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / f"ai_codes_{stamp}.csv", AI_CODE_FIELDS, rows)
    report = {"created_at": datetime.now().isoformat(timespec="seconds"),
              "sheet": str(Path(args.sheet)).replace("\\", "/"), "key": str(Path(args.key)).replace("\\", "/"),
              "items": len(sheet), "agreement": round(agree / len(sheet), 4), "kappa": k_value,
              "kappa_min": KAPPA_MIN, "low_kappa_reason": args.accept_low_kappa if low_kappa else None,
              "disagreements": len(sheet) - agree,
              "final_differs_from_both": sum(";".join(norm_codes(r["code_final"])) not in (x, y)
                                             for r, x, y in zip(sheet, a, b)),
              "code_rows": len(rows), "not_reason_rows": sum(r["code"] == "-" for r in rows)}
    (out / f"agreement_{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[가져오기] 줄 {report['items']}개 -> 코드 {report['code_rows']}개 (이유 아님 {report['not_reason_rows']})")
    print(f"  두 판정자 일치율 {report['agreement']}, kappa {report['kappa']}, 다르게 붙인 줄 {report['disagreements']}개")
    print(f"  출력: {args.out}/ai_codes_{stamp}.csv, agreement_{stamp}.json")
    return EXIT_OK


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="AI 이유 판정용 시트 (TRD IF-13, IF-09)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make", help="추출 결과로 판정 시트와 대응표를 만든다")
    mk.add_argument("--extracted", required=True, help="extract_reasons.py의 extracted_*.jsonl")
    mk.add_argument("--out", default="runs/dev/sheet")
    mk.add_argument("--seed", type=int, default=1, help="시트 줄 순서를 섞는 시드")
    im = sub.add_parser("import", help="채운 시트를 AI 코드 CSV로 만든다")
    im.add_argument("--sheet", required=True)
    im.add_argument("--key", required=True)
    im.add_argument("--out", default="runs/dev/coded")
    im.add_argument("--accept-low-kappa", metavar="사유", default="",
                    help="kappa가 0.6에 못 미쳐도 가져온다. 사유를 agreement JSON에 남긴다")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_USAGE
    return cmd_make(args, root) if args.cmd == "make" else cmd_import(args, root)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())

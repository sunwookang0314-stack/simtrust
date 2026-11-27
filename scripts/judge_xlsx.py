"""판정자 엑셀(xlsx)과 판정 가져오기(reason_sheet.py import) 사이를 잇는다.

판정자는 각자 엑셀 파일 하나(탭: 규칙, 판정시트, 코드북)를 받아 판정시트 탭의 '코드' 칸만 채운다.
줄 순서는 판정자가 바꿔도 된다. 줄은 '번호' 칸(item_id)으로 맞춘다.

merge: 두 판정자 파일을 번호로 맞춰 합친다.
  - code_final 전에 두 판정자 일치율과 kappa를 낸다 (reason_sheet.py import와 같은 계산. 쓰는 이유·안 쓰는 이유 따로도)
  - 같게 붙인 줄은 code_final을 미리 채우고, 다르게 붙인 줄만 모은 맞춰 보기 엑셀을 만든다
  - 빈칸, 쉼표, 코드북에 없는 코드(C-01 같은 오타 포함), 빠지거나 겹친 번호가 있으면 아무것도 쓰지 않고 멈춘다
final: 맞춰 보기 엑셀의 '최종 코드'를 넣어 reason_sheet.py import가 읽는 시트 CSV를 만든다

실행 (리포 루트. openpyxl이 필요하다):
    python scripts/judge_xlsx.py merge --sheet runs/main/sheet/sheet_X.csv \
        --coder1 <code_1 판정자 xlsx> --coder2 <code_2 판정자 xlsx> --codebook <코드북.csv> --out runs/main/coded
    python scripts/judge_xlsx.py final --merged runs/main/coded/merged_X.csv \
        --reconciled <맞춰 본 xlsx> --codebook <코드북.csv> --out runs/main/coded
    python scripts/reason_sheet.py import --sheet runs/main/coded/sheet_final_X.csv --key runs/main/sheet/key_X.csv \
        --codebook <코드북.csv> --out runs/main/coded

화면에는 숫자와 번호만 찍는다. 답 글자는 찍지 않는다.
종료 코드: 0 정상, 1 입력 파일 없음·사용법, 4 입력 검증 실패
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reason_sheet as rsh  # noqa: E402

ROOT = rsh.ROOT
EXIT_OK, EXIT_USAGE, EXIT_INPUT = rsh.EXIT_OK, rsh.EXIT_USAGE, rsh.EXIT_INPUT
SHEET_TAB = "판정시트"
ID_COL, CODE_COL, MEMO_COL = "번호", "코드", "메모"
FINAL_COL = "최종 코드"
SHOW_IDS = 10  # 문제 줄 번호를 이만큼만 찍는다


def load_workbook(path: Path):
    try:
        import openpyxl
    except ImportError:
        raise rsh.InputError("openpyxl이 없다. pip install openpyxl") from None
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def read_judge_xlsx(path: Path, code_col: str = CODE_COL) -> dict:
    """판정시트 탭 -> {번호: (코드, 메모)}. 머리 줄에서 칸 이름으로 찾는다."""
    wb = load_workbook(path)
    ws = wb[SHEET_TAB] if SHEET_TAB in wb.sheetnames else wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head = [str(c).strip() if c is not None else "" for c in next(rows, [])]
    if ID_COL not in head or code_col not in head:
        raise rsh.InputError(f"{path.name}: '{ID_COL}', '{code_col}' 칸이 있는 머리 줄이 없음")
    i_id, i_code = head.index(ID_COL), head.index(code_col)
    i_memo = head.index(MEMO_COL) if MEMO_COL in head else None
    out, dup = {}, []
    for r in rows:
        if r is None or i_id >= len(r) or r[i_id] in (None, ""):
            continue
        rid = str(r[i_id]).strip()
        code = "" if i_code >= len(r) or r[i_code] is None else str(r[i_code]).strip()
        memo = "" if i_memo is None or i_memo >= len(r) or r[i_memo] is None else str(r[i_memo]).strip()
        if rid in out:
            dup.append(rid)
        out[rid] = (code, memo)
    wb.close()
    if dup:
        raise rsh.InputError(f"{path.name}: 같은 번호가 두 번 있음 {dup[:SHOW_IDS]}")
    return out


def read_codebook(path: Path) -> set:
    rows = rsh.read_csv(path, ["code"])
    return {c for r in rows for c in rsh.norm_codes(r["code"])}


def code_problems(label: str, cells: dict, allowed) -> list:
    """cells: {번호: 코드 칸}. 빈칸, 쉼표, 코드북에 없는 코드를 번호와 함께 돌려준다."""
    blank = [k for k, v in cells.items() if not rsh.norm_codes(v)]
    comma = [k for k, v in cells.items() if "," in rsh.unicodedata.normalize("NFKC", v)]
    unknown = {}
    if allowed is not None:
        for k, v in cells.items():
            for c in rsh.norm_codes(v):
                if c not in allowed:
                    unknown.setdefault(c, []).append(k)
    out = []
    if blank:
        out.append(f"{label} 빈칸 {len(blank)}개 {sorted(blank)[:SHOW_IDS]}")
    if comma:
        out.append(f"{label} 쉼표 {len(comma)}개 (코드가 여럿이면 ;) {sorted(comma)[:SHOW_IDS]}")
    for c, ids in sorted(unknown.items()):
        out.append(f"{label} 코드북에 없는 코드 '{c}' {len(ids)}개 {sorted(ids)[:SHOW_IDS]}")
    return out


def allowed_codes(path):
    return None if path is None else read_codebook(path) | {"-"}


def stats(ids: list, a: dict, b: dict) -> dict:
    x = [";".join(rsh.norm_codes(a[i])) for i in ids]
    y = [";".join(rsh.norm_codes(b[i])) for i in ids]
    agree = sum(p == q for p, q in zip(x, y))
    return {"items": len(ids), "agreement": round(agree / len(ids), 4) if ids else None,
            "kappa": rsh.kappa(x, y), "disagreements": len(ids) - agree}


def write_reconcile(path: Path, rows: list, name1: str, name2: str) -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET_TAB
    head = [ID_COL, "기능", "종류", "AI가 한 말", f"{name1} 코드", f"{name2} 코드", FINAL_COL,
            f"{name1} 메모", f"{name2} 메모"]
    ws.append(head)
    for r in rows:
        ws.append([r["item_id"], r["feature_name"], {"use": "쓰는 이유", "nouse": "안 쓰는 이유"}.get(r["kind"], r["kind"]),
                   r["text"], r["code_1"], r["code_2"], "", r["memo_1"], r["memo_2"]])
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in ws.iter_rows(min_row=1, min_col=7, max_col=7):
        for c in row:
            c.fill = PatternFill("solid", fgColor="FFF2CC")
    for col, w in zip("ABCDEFGHI", (14, 20, 12, 70, 12, 12, 12, 24, 24)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "E2"
    guide = wb.create_sheet("하는 법")
    for line in ("둘이 다르게 붙인 줄만 모았다. 같이 보고 '최종 코드' 칸을 채운다",
                 "코드 적는 법은 판정 파일의 규칙 탭과 같다 (여럿이면 ;, 이유 아니면 -)",
                 "'번호' 칸은 고치지 않는다. 다 채우면 이 파일을 그대로 보낸다"):
        guide.append([line])
    guide.column_dimensions["A"].width = 90
    wb.save(path)


def cmd_merge(args, root: Path) -> int:
    paths = {"sheet": root / args.sheet, "coder1": root / args.coder1, "coder2": root / args.coder2}
    if args.codebook:
        paths["codebook"] = root / args.codebook
    for name, p in paths.items():
        if not p.is_file():
            print(f"[오류] 입력 파일 없음: --{name}", file=sys.stderr)
            return EXIT_USAGE
    try:
        sheet = rsh.read_csv(paths["sheet"], rsh.SHEET_FIELDS)
        c1 = read_judge_xlsx(paths["coder1"])
        c2 = read_judge_xlsx(paths["coder2"])
        allowed = allowed_codes(paths.get("codebook"))
    except (rsh.InputError, UnicodeDecodeError, KeyError, OSError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        return EXIT_INPUT
    ids = [r["item_id"] for r in sheet]
    problems = []
    for label, c in (("code_1", c1), ("code_2", c2)):
        if set(ids) - set(c):
            problems.append(f"{label} 파일에서 빠진 번호 {len(set(ids) - set(c))}개 {sorted(set(ids) - set(c))[:SHOW_IDS]}")
        if set(c) - set(ids):
            problems.append(f"{label} 파일에만 있는 번호 {len(set(c) - set(ids))}개 {sorted(set(c) - set(ids))[:SHOW_IDS]}")
        problems += code_problems(label, {k: v[0] for k, v in c.items() if k in set(ids)}, allowed)
    if problems:
        print("[입력 오류] 고친 뒤 다시 돌린다:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return EXIT_INPUT

    a = {i: c1[i][0] for i in ids}
    b = {i: c2[i][0] for i in ids}
    report = {"created_at": datetime.now().isoformat(timespec="seconds"),
              "sheet": args.sheet, "coder1": args.coder1, "coder2": args.coder2,
              "coder1_name": args.name1, "coder2_name": args.name2, "codebook": args.codebook,
              "all": stats(ids, a, b), "kappa_min": rsh.KAPPA_MIN}
    for kind in sorted({r["kind"] for r in sheet}):
        report[kind] = stats([r["item_id"] for r in sheet if r["kind"] == kind], a, b)
    merged, diff = [], []
    for r in sheet:
        i = r["item_id"]
        x, y = ";".join(rsh.norm_codes(a[i])), ";".join(rsh.norm_codes(b[i]))
        memo = " | ".join(m for m in (c1[i][1], c2[i][1]) if m)
        row = {**r, "code_1": x, "code_2": y, "code_final": x if x == y else "", "note": memo}
        merged.append(row)
        if x != y:
            diff.append({**row, "memo_1": c1[i][1], "memo_2": c2[i][1]})
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    rsh.write_csv(out / f"merged_{stamp}.csv", rsh.SHEET_FIELDS, merged)
    write_reconcile(out / f"reconcile_{stamp}.xlsx", diff, args.name1, args.name2)
    (out / f"agreement_pre_{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    s = report["all"]
    print(f"[합치기] 줄 {s['items']}개, 일치율 {s['agreement']}, kappa {s['kappa']} (기준 {rsh.KAPPA_MIN}), "
          f"다르게 붙인 줄 {s['disagreements']}개")
    for kind in ("nouse", "use"):
        if kind in report:
            k = report[kind]
            print(f"  {kind}: 줄 {k['items']}개, 일치율 {k['agreement']}, kappa {k['kappa']}, 다름 {k['disagreements']}개")
    print(f"  맞춰 볼 파일: {args.out}/reconcile_{stamp}.xlsx (다른 줄만)")
    print(f"  합친 시트: {args.out}/merged_{stamp}.csv, 숫자: agreement_pre_{stamp}.json")
    return EXIT_OK


def cmd_final(args, root: Path) -> int:
    paths = {"merged": root / args.merged, "reconciled": root / args.reconciled}
    if args.codebook:
        paths["codebook"] = root / args.codebook
    for name, p in paths.items():
        if not p.is_file():
            print(f"[오류] 입력 파일 없음: --{name}", file=sys.stderr)
            return EXIT_USAGE
    try:
        merged = rsh.read_csv(paths["merged"], rsh.SHEET_FIELDS)
        fixed = read_judge_xlsx(paths["reconciled"], code_col=FINAL_COL)
        allowed = allowed_codes(paths.get("codebook"))
    except (rsh.InputError, UnicodeDecodeError, KeyError, OSError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        return EXIT_INPUT
    need = {r["item_id"] for r in merged if not r["code_final"]}
    problems = []
    if need - set(fixed):
        problems.append(f"맞춰 볼 파일에서 빠진 번호 {len(need - set(fixed))}개 {sorted(need - set(fixed))[:SHOW_IDS]}")
    if set(fixed) - need:
        problems.append(f"맞춰 볼 줄이 아닌 번호 {len(set(fixed) - need)}개 {sorted(set(fixed) - need)[:SHOW_IDS]}")
    problems += code_problems(FINAL_COL, {k: v[0] for k, v in fixed.items() if k in need}, allowed)
    if problems:
        print("[입력 오류] 고친 뒤 다시 돌린다:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return EXIT_INPUT
    for r in merged:
        if r["item_id"] in need:
            code, memo = fixed[r["item_id"]]
            r["code_final"] = ";".join(rsh.norm_codes(code))
            r["note"] = " | ".join(m for m in (r["note"], memo) if m)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    rsh.write_csv(out / f"sheet_final_{stamp}.csv", rsh.SHEET_FIELDS, merged)
    print(f"[최종] 줄 {len(merged)}개, 맞춰 본 줄 {len(need)}개를 넣음")
    print(f"  다음: reason_sheet.py import --sheet {args.out}/sheet_final_{stamp}.csv --key <대응표> --codebook <코드북>")
    return EXIT_OK


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="판정자 엑셀 합치기와 최종 시트 만들기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mg = sub.add_parser("merge", help="두 판정자 파일을 합치고 일치율·kappa, 맞춰 볼 파일을 만든다")
    mg.add_argument("--sheet", required=True, help="reason_sheet.py make가 만든 원래 시트 CSV")
    mg.add_argument("--coder1", required=True, help="code_1 판정자 xlsx")
    mg.add_argument("--coder2", required=True, help="code_2 판정자 xlsx")
    mg.add_argument("--name1", default="판정자1", help="맞춰 볼 파일에 쓸 code_1 판정자 이름")
    mg.add_argument("--name2", default="판정자2", help="맞춰 볼 파일에 쓸 code_2 판정자 이름")
    mg.add_argument("--codebook", help="코드북 CSV. 주면 코드북에 없는 코드에서 멈춘다")
    mg.add_argument("--out", default="runs/dev/coded")
    fn = sub.add_parser("final", help="맞춰 본 파일로 import용 시트를 만든다")
    fn.add_argument("--merged", required=True, help="merge가 만든 merged_*.csv")
    fn.add_argument("--reconciled", required=True, help="최종 코드를 채운 reconcile_*.xlsx")
    fn.add_argument("--codebook", help="코드북 CSV. 주면 코드북에 없는 코드에서 멈춘다")
    fn.add_argument("--out", default="runs/dev/coded")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_USAGE
    return cmd_merge(args, root) if args.cmd == "merge" else cmd_final(args, root)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())

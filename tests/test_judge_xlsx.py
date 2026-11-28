"""scripts/judge_xlsx.py 오프라인 테스트. openpyxl이 있어야 돈다.

리포 루트에서:
    python -m unittest tests.test_judge_xlsx -v
"""

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import reason_sheet as rsh  # noqa: E402

try:
    import openpyxl
except ImportError:  # TinyTroupe 가상환경에는 없을 수 있다
    openpyxl = None
if openpyxl is not None:
    import judge_xlsx as jx

TMP = Path(tempfile.mkdtemp(prefix="simtrust_judge_xlsx_"))
IDS = ["R01", "R02", "R03", "R04", "R05", "R06"]
KINDS = ["use", "use", "use", "nouse", "nouse", "use"]


def write_sheet_and_key():
    sheet = [{"item_id": i, "service": "svc", "platform": "app", "feature_name": "마감 알림", "kind": k,
              "source": "why_use" if k == "use" else "q47", "text": f"문장 {i}", "options_found": ""}
             for i, k in zip(IDS, KINDS)]
    key = [{"item_id": i, "run_id": f"run{n}", "service": "svc", "platform": "app", "condition": "2",
            "persona_id": f"P{n}", "repeat": "1", "feature_id": "F3", "kind": k,
            "source": "why_use" if k == "use" else "q47", "input_mode": "image", "model": "m"}
           for n, (i, k) in enumerate(zip(IDS, KINDS))]
    rsh.write_csv(TMP / "sheet.csv", rsh.SHEET_FIELDS, sheet)
    rsh.write_csv(TMP / "key.csv", rsh.KEY_FIELDS, key)
    with (TMP / "codebook.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name"])
        for c in ("U01", "U02", "U03", "C01", "C04", "F3-01"):
            w.writerow([c, c])


def write_judge(name, codes, order=None, memo=None):
    """판정자 파일. 받은 엑셀과 같은 칸 이름. order로 줄 순서를 바꾼다(정렬해도 되는지)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "판정시트"
    ws.append(["번호", "기능", "종류", "AI가 한 말", "코드", "메모"])
    for i in order or IDS:
        ws.append([i, "마감 알림", "", f"문장 {i}", codes[i], (memo or {}).get(i, "")])
    wb.create_sheet("규칙")
    wb.save(TMP / name)
    return name


def run(*argv, mod=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = (mod or jx).main(list(argv), root=TMP)
    return code, out.getvalue() + err.getvalue()


A = {"R01": "U01", "R02": "U02", "R03": "U01;U03", "R04": "C01", "R05": "C04", "R06": "-"}
B = {"R01": "U01", "R02": "U03", "R03": "u03; U01", "R04": "C01", "R05": "C01", "R06": "-"}


@unittest.skipIf(openpyxl is None, "openpyxl 없음")
class TestJudgeXlsx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        write_sheet_and_key()

    def merge(self, name, c1, c2):
        return run("merge", "--sheet", "sheet.csv", "--coder1", c1, "--coder2", c2, "--name1", "선우",
                   "--name2", "정우", "--codebook", "codebook.csv", "--out", name)

    def test_merge_kappa_matches_import_and_reconcile_has_only_diffs(self):
        c1 = write_judge("c1.xlsx", A)
        c2 = write_judge("c2.xlsx", B, order=list(reversed(IDS)))  # 정렬을 바꿔도 번호로 맞춘다
        code, log = self.merge("out_ok", c1, c2)
        self.assertEqual(code, 0, log)
        rep = json.loads(next((TMP / "out_ok").glob("agreement_pre_*.json")).read_text(encoding="utf-8"))
        x = [";".join(rsh.norm_codes(A[i])) for i in IDS]
        y = [";".join(rsh.norm_codes(B[i])) for i in IDS]
        self.assertEqual(rep["all"]["kappa"], rsh.kappa(x, y))  # import와 같은 계산
        self.assertEqual(rep["all"]["disagreements"], 2)  # R02, R05. R03은 순서·대소문자만 다름
        self.assertEqual((rep["nouse"]["items"], rep["nouse"]["disagreements"]), (2, 1))
        merged = {r["item_id"]: r for r in rsh.read_csv(next((TMP / "out_ok").glob("merged_*.csv")), ["item_id"])}
        self.assertEqual(merged["R03"]["code_final"], "U01;U03")
        self.assertEqual(merged["R02"]["code_final"], "")
        wb = openpyxl.load_workbook(next((TMP / "out_ok").glob("reconcile_*.xlsx")))
        rows = list(wb["판정시트"].iter_rows(values_only=True))
        self.assertEqual([r[0] for r in rows[1:]], ["R02", "R05"])
        self.assertEqual(rows[0][4:7], ("선우 코드", "정우 코드", "최종 코드"))

        # 맞춰 본 파일 -> 최종 시트 -> import (코드북 검사까지)
        ws = wb["판정시트"]
        ws["G2"], ws["G3"] = "U02", "C04"
        wb.save(TMP / "fixed.xlsx")
        merged_name = next((TMP / "out_ok").glob("merged_*.csv")).name
        code, log = run("final", "--merged", f"out_ok/{merged_name}", "--reconciled", "fixed.xlsx",
                        "--codebook", "codebook.csv", "--out", "out_ok")
        self.assertEqual(code, 0, log)
        final = next((TMP / "out_ok").glob("sheet_final_*.csv")).name
        code, log = run("import", "--sheet", f"out_ok/{final}", "--key", "key.csv", "--codebook", "codebook.csv",
                        "--out", "out_ok/coded", "--accept-low-kappa", "테스트", mod=rsh)
        self.assertEqual(code, 0, log)
        codes = rsh.read_csv(next((TMP / "out_ok/coded").glob("ai_codes_*.csv")), ["item_id", "code"])
        self.assertEqual(sorted(r["code"] for r in codes if r["item_id"] == "R05"), ["C04"])

    def test_typo_code_blank_and_missing_id_stop(self):
        c1 = write_judge("t1.xlsx", {**A, "R04": "C-01"})  # 공통 코드에 가운데 - 를 넣은 오타
        c2 = write_judge("t2.xlsx", {**B, "R01": ""}, order=IDS[:-1])  # 빈칸, 빠진 줄
        code, log = self.merge("out_bad", c1, c2)
        self.assertEqual(code, 4, log)
        self.assertIn("C-01", log)
        self.assertIn("빈칸", log)
        self.assertIn("빠진 번호", log)
        self.assertFalse((TMP / "out_bad").exists())  # 멈추면 아무것도 안 쓴다

    def test_import_codebook_check_catches_unknown_code(self):
        sheet = rsh.read_csv(TMP / "sheet.csv", ["item_id"])
        for r in sheet:
            r.update(code_1="U01", code_2="U01", code_final="U01")
        sheet[0]["code_final"] = "C-01"
        rsh.write_csv(TMP / "sheet_bad.csv", rsh.SHEET_FIELDS, sheet)
        code, log = run("import", "--sheet", "sheet_bad.csv", "--key", "key.csv", "--codebook", "codebook.csv",
                        "--out", "out_imp", mod=rsh)
        self.assertEqual(code, 4, log)
        self.assertIn("코드북에 없는 코드", log)
        code, log = run("import", "--sheet", "sheet_bad.csv", "--key", "key.csv", "--out", "out_imp2",
                        "--accept-low-kappa", "테스트(두 판정자 코드가 모두 같아 kappa를 못 잼)", mod=rsh)
        self.assertEqual(code, 0, log)  # --codebook을 안 주면 전처럼 받는다


if __name__ == "__main__":
    unittest.main()

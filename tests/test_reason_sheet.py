"""scripts/reason_sheet.py 오프라인 테스트와 추출기 -> 시트 -> 계산기 통합 테스트. API 없이 돈다.

리포 루트에서:
    python -m unittest tests.test_reason_sheet -v
"""

import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

import extract_reasons as er  # noqa: E402
import reason_sheet as rsh  # noqa: E402
import score_reasons as sr  # noqa: E402
from test_extract_reasons import FEATURES, answer, episode  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="simtrust_sheet_test_"))
shutil.copytree(REPO / "experiments/runner_dev/protocol", TMP / "protocol")


def ep(run_id, condition, use, why, nouse, q47):
    line = episode(run_id=run_id, answers=[answer("Q-AI-USE", use), answer("Q-AI-WHY-USE", why),
                                           answer("Q-AI-NOUSE", nouse), answer("Q-4-7", q47)])
    line["condition"] = condition
    line["persona_id"] = run_id.split("_")[-1]
    return line


USE = ("공고 검색·필터: 쓸 것 같다\n공고 저장 (스크랩, 찜, 북마크): 안 쓸 것 같다\n"
       "마감 알림: 쓸 것 같다\n추천 공고 목록 (인기 공고, 맞춤 추천): 안 쓸 것 같다")
EPISODES = [
    ep("c2_S01", 2, USE,
       "공고 검색·필터: 인턴 공고를 찾으려고 쓸 것 같다\n마감 알림: 마감일을 놓치지 않으려고 쓸 것 같다",
       "공고 저장: 나한테 필요 없을 것 같아서, 다른 앱이나 방법으로 해결해서\n추천 공고 목록: 광고 같아서 손이 안 간다",
       "공고 저장: 카톡 나에게 보내기로 모아 둡니다\n공고 검색·필터: 검색은 늘 씁니다"),
    ep("c0_C0-01", 0, USE,
       "공고 검색·필터: 원하는 조건으로 좁히려고\n마감 알림: 편해서",
       "공고 저장: 나한테 필요 없을 것 같아서\n추천 공고 목록: 나한테 필요 없을 것 같아서",
       "공고 저장: 따로 안 모읍니다"),
]


def run(module, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(list(argv), root=TMP)
    return code, out.getvalue() + err.getvalue()


def extracted(name):
    raw = TMP / f"{name}.jsonl"
    raw.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in EPISODES), encoding="utf-8")
    code, log = run(er, "--raw", raw.name, "--options", "protocol/options_4-6.txt", "--out", f"ext_{name}")
    assert code == 0, log
    return str(next((TMP / f"ext_{name}").glob("extracted_*.jsonl")).relative_to(TMP))


def read(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def make(name, seed="1"):
    code, log = run(rsh, "make", "--extracted", extracted(name), "--out", f"sheet_{name}", "--seed", seed)
    assert code == 0, log
    d = TMP / f"sheet_{name}"
    return read(next(d.glob("sheet_*.csv"))), read(next(d.glob("key_*.csv"))), log


# 판정자 대신 글자로 코드를 붙인다. 실제로는 코드북을 보고 사람이 붙인다
CODEBOOK = [("인턴 공고", "U-find"), ("조건으로 좁히", "U-find"), ("놓치지", "U-deadline"),
            ("필요 없을", "N-noneed"), ("다른 앱", "N-other"), ("카톡", "N-other"), ("광고", "N-ad")]


def code_for(text):
    hits = sorted({c for word, c in CODEBOOK if word in text})
    return ";".join(hits) or "-"


def fill(rows, path, disagree=0, blank_col=None):
    for i, r in enumerate(rows):
        c = code_for(r["text"])
        r["code_1"] = c
        r["code_2"] = "N-other" if i < disagree else c
        r["code_final"] = c
    if blank_col:
        rows[0][blank_col] = ""
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rsh.SHEET_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return str(path.relative_to(TMP))


class TestMake(unittest.TestCase):
    def test_sheet_hides_condition_and_key_keeps_it(self):
        sheet, key, log = make("hide")
        self.assertEqual(list(sheet[0]), rsh.SHEET_FIELDS)
        for col in ("condition", "persona_id", "run_id", "repeat"):
            self.assertNotIn(col, sheet[0])
        self.assertEqual({r["condition"] for r in key}, {"0", "2"})
        self.assertEqual({r["item_id"] for r in sheet}, {r["item_id"] for r in key})
        # c2: 쓸 이유 2 + 안 쓸 2(4-6 줄) + 4-7 1 / c0: 쓸 이유 2 + 안 쓸 2 + 4-7 1
        self.assertEqual(len(sheet), 10)
        # 쓸 것 같다고 한 공고 검색·필터의 4-7 줄은 넣지 않는다
        self.assertNotIn("검색은 늘 씁니다", [r["text"] for r in sheet])
        self.assertIn("안 맞는 줄 1개", log)
        both = [r for r in sheet if r["text"].startswith("나한테 필요 없을 것 같아서, 다른")][0]
        self.assertEqual(both["options_found"], "나한테 필요 없을 것 같아서 / 다른 앱이나 방법으로 해결해서")
        self.assertEqual({r["kind"] for r in sheet if r["source"] == "q47"}, {"nouse"})
        self.assertNotIn("인턴", log)  # 화면에는 숫자만

    def test_same_seed_same_order(self):
        a, _, _ = make("seed_a")
        b, _, _ = make("seed_b")
        c, _, _ = make("seed_c", seed="2")
        self.assertEqual([r["item_id"] for r in a], [r["item_id"] for r in b])
        self.assertNotEqual([r["item_id"] for r in a], [r["item_id"] for r in c])

    def test_make_input_errors(self):
        (TMP / "stage1.jsonl").write_text(json.dumps({"run_id": "x"}) + "\n", encoding="utf-8")
        self.assertEqual(run(rsh, "make", "--extracted", "nothing.jsonl", "--out", "sheet_err")[0], 1)
        self.assertEqual(run(rsh, "make", "--extracted", "stage1.jsonl", "--out", "sheet_err")[0], 4)
        self.assertFalse((TMP / "sheet_err").exists())


class TestImport(unittest.TestCase):
    def test_import_and_agreement(self):
        sheet, _, _ = make("imp")
        key = str(next((TMP / "sheet_imp").glob("key_*.csv")).relative_to(TMP))
        filled = fill(sheet, TMP / "filled_imp.csv", disagree=2)
        code, log = run(rsh, "import", "--sheet", filled, "--key", key, "--out", "coded_imp")
        self.assertEqual(code, 0, log)
        rows = read(next((TMP / "coded_imp").glob("ai_codes_*.csv")))
        self.assertEqual(list(rows[0]), rsh.AI_CODE_FIELDS)
        # 4-6 보기 두 개가 든 줄은 코드 두 줄이 된다
        c2_f2 = sorted(r["code"] for r in rows if r["condition"] == "2" and r["feature_id"] == "F2")
        self.assertEqual(c2_f2, ["N-NONEED", "N-OTHER", "N-OTHER"])
        report = json.loads(next((TMP / "coded_imp").glob("agreement_*.json")).read_text(encoding="utf-8"))
        self.assertEqual((report["items"], report["disagreements"]), (10, 2))
        self.assertEqual(report["agreement"], 0.8)
        self.assertEqual(report["not_reason_rows"], 2)  # "편해서", "따로 안 모읍니다"는 코드북에 없어서 '-'

    def test_blank_or_mismatch_writes_nothing(self):
        sheet, key_rows, _ = make("blank")
        key = str(next((TMP / "sheet_blank").glob("key_*.csv")).relative_to(TMP))
        for col in rsh.JUDGE_COLS:
            with self.subTest(col=col):
                filled = fill([dict(r) for r in sheet], TMP / f"blank_{col}.csv", blank_col=col)
                code, log = run(rsh, "import", "--sheet", filled, "--key", key, "--out", "coded_blank")
                self.assertEqual(code, 4, log)
                self.assertIn(f"{col} 빈칸 1개", log)
        short = fill([dict(r) for r in sheet][1:], TMP / "short.csv")
        code, log = run(rsh, "import", "--sheet", short, "--key", key, "--out", "coded_blank")
        self.assertEqual(code, 4, log)
        self.assertIn("시트에서 빠진 줄 1개", log)
        self.assertFalse((TMP / "coded_blank").exists())

    def test_kappa(self):
        self.assertEqual(rsh.kappa(["A", "A", "B", "B"], ["A", "B", "B", "B"]), 0.5)
        self.assertIsNone(rsh.kappa(["A", "A"], ["A", "A"]))  # 우연 일치가 1이면 계산 불가
        self.assertEqual(rsh.norm_codes(" b; A ;A;"), ["A", "B"])
        self.assertEqual(rsh.norm_codes("\u2013"), ["-"])  # 엑셀이 바꾼 대시도 '이유 아님'
        self.assertEqual(rsh.norm_codes("N01\uff1bN02"), ["N01", "N02"])  # 전각 세미콜론

    def test_low_kappa_and_comma_stop(self):
        sheet, _, _ = make("lowk")
        key = str(next((TMP / "sheet_lowk").glob("key_*.csv")).relative_to(TMP))
        # 판정자 2가 전부 다르게 붙이면 kappa가 0.6(NFR-07)에 못 미쳐 멈춘다
        filled = fill([dict(r) for r in sheet], TMP / "filled_lowk.csv", disagree=len(sheet))
        code, log = run(rsh, "import", "--sheet", filled, "--key", key, "--out", "coded_lowk")
        self.assertEqual(code, 4, log)
        self.assertIn("NFR-07", log)
        self.assertFalse((TMP / "coded_lowk").exists())
        code, log = run(rsh, "import", "--sheet", filled, "--key", key, "--out", "coded_lowk",
                        "--accept-low-kappa", "시범 판정")
        self.assertEqual(code, 0, log)
        report = json.loads(next((TMP / "coded_lowk").glob("agreement_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["low_kappa_reason"], "시범 판정")
        # 코드를 쉼표로 나누면 멈춘다
        rows = [dict(r) for r in sheet]
        fill(rows, TMP / "comma.csv")
        rows[0]["code_final"] = "N-other, N-noneed"
        with (TMP / "comma.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rsh.SHEET_FIELDS)
            w.writeheader()
            w.writerows(rows)
        code, log = run(rsh, "import", "--sheet", "comma.csv", "--key", key, "--out", "coded_comma")
        self.assertEqual(code, 4, log)
        self.assertIn("쉼표", log)

    def test_lines_must_match_use_choice(self):
        r = {"asked": True, "run_id": "x", "service": "s", "platform": "app", "condition": 2, "persona_id": "S01",
             "repeat": 1, "feature_id": "F4", "use_choice": "nouse", "use_reasons": ["쓸 이유"],
             "nouse_lines": ["안 쓸 이유"], "q47_details": ["지금은 검색으로 찾습니다"], "nouse_options": []}
        items, skipped = rsh.items_from_record(r)
        self.assertEqual([(i["kind"], i["source"]) for i in items], [("nouse", "nouse"), ("nouse", "q47")])
        self.assertEqual(skipped, 1)
        items, skipped = rsh.items_from_record({**r, "use_choice": "unknown"})  # 못 가린 기능은 다 넣는다
        self.assertEqual((len(items), skipped), (3, 0))

    def test_same_episode_twice_stops(self):
        # 실패 뒤 다시 돌려서 같은 페르소나·회차가 실행 ID만 바뀌어 두 번 들어간 경우
        twice = [EPISODES[0], {**EPISODES[0], "run_id": "c2_retry_S01"}]
        raw = TMP / "twice.jsonl"
        raw.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in twice), encoding="utf-8")
        code, log = run(er, "--raw", raw.name, "--options", "protocol/options_4-6.txt", "--out", "ext_twice")
        self.assertEqual(code, 0, log)
        ext = str(next((TMP / "ext_twice").glob("extracted_*.jsonl")).relative_to(TMP))
        code, log = run(rsh, "make", "--extracted", ext, "--out", "sheet_twice")
        self.assertEqual(code, 4, log)
        self.assertIn("두 번", log)


class TestPipeline(unittest.TestCase):
    def test_extractor_to_score(self):
        # 추출기 -> 시트 -> (판정자) -> 가져오기 -> 계산기. 형식이 어긋나면 여기서 걸린다
        sheet, _, _ = make("pipe")
        key = str(next((TMP / "sheet_pipe").glob("key_*.csv")).relative_to(TMP))
        code, log = run(rsh, "import", "--sheet", fill(sheet, TMP / "filled_pipe.csv"), "--key", key,
                        "--out", "coded_pipe")
        self.assertEqual(code, 0, log)
        ai = str(next((TMP / "coded_pipe").glob("ai_codes_*.csv")).relative_to(TMP))
        # 사람 코드: 공고 저장(F2) 안 쓸 이유를 5명이 답함. 응답 원문 없이 코드만
        people = {"P1": ["N-other"], "P2": ["N-other", "N-noneed"], "P3": ["N-time"], "P4": ["N-other"],
                  "P5": []}
        with (TMP / "human_pipe.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(sr.HUMAN_FIELDS)
            for rid, codes in people.items():
                for c in codes or [""]:
                    w.writerow([rid, "fake", "app", "F2", "nouse", c])
        rules = json.loads((REPO / "configs/rules.draft.json").read_text(encoding="utf-8"))
        rules["resamples"] = 100
        (TMP / "rules_pipe.json").write_text(json.dumps(rules), encoding="utf-8")
        code, log = run(sr, "--human", "human_pipe.csv", "--ai", ai, "--rules", "rules_pipe.json",
                        "--out", "score_pipe", "--allow-draft")
        self.assertEqual(code, 0, log)
        record = json.loads(next((TMP / "score_pipe").glob("metrics_all_*.json")).read_text(encoding="utf-8"))
        cells = {(c["condition"], c["feature_id"], c["kind"]): c for c in record["cells"]}
        c2 = cells[(2, "F2", "nouse")]
        self.assertEqual((c2["n_humans"], c2["ai_episodes"]), (5, 1))
        self.assertEqual(c2["ai_codes"], ["N-NONEED", "N-OTHER"])  # 코드는 대문자로 맞춘다
        self.assertEqual((c2["precision"], c2["recall"]), (1.0, 0.6667))  # 사람 이유 3개 중 2개
        self.assertEqual(cells[(0, "F2", "nouse")]["ai_codes"], ["N-NONEED"])
        self.assertEqual(cells[(2, "F1", "use")]["verdict"], sr.LOW)  # 사람 응답이 없는 칸
        self.assertEqual(record["dropped_ai_rows"], 2)


if __name__ == "__main__":
    unittest.main()

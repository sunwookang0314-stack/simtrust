"""scripts/form_to_sheet.py 오프라인 테스트. 가짜 폼 응답으로만 돈다. 실제 응답 없음.

리포 루트에서:
    python -m unittest tests.test_form_to_sheet -v
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

import form_to_sheet as fts  # noqa: E402
import reason_sheet as rsh  # noqa: E402
import score_reasons as sr  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="simtrust_form_test_"))
shutil.copytree(REPO / "docs/ai-protocol", TMP / "docs/ai-protocol")
FEATURES = fts.load_features(REPO / "docs/ai-protocol/features.txt")
NAMES = [n for _, n in FEATURES]
MAP = "링커리어=linkareer,에브리커리어(캠퍼스픽)=campuspick"
NL = chr(10)


def header():
    cols = ["타임스탬프", fts.Q_CONSENT, "성별", fts.Q_USED, fts.Q_SERVICE, fts.Q_PLATFORM]
    for t in (fts.Q_STATE, fts.Q_QUIT, fts.Q_NEVER):
        cols += [fts.grid_col(t, n) for n in NAMES]
    return cols + [fts.Q_WHY_USE, fts.Q_WHY_NOT]


def response(consent="동의합니다", used="있다", service="링커리어", platform="앱", states=None, quit_=None,
             never=None, why_use="없음", why_not="없음"):
    r = {"타임스탬프": "2026. 11. 7 오후 1:00:00", fts.Q_CONSENT: consent, "성별": "응답하지 않음",
         fts.Q_USED: used, fts.Q_SERVICE: service, fts.Q_PLATFORM: platform,
         fts.Q_WHY_USE: why_use, fts.Q_WHY_NOT: why_not}
    states = states or ["자주 쓴다"] * 4
    for i, n in enumerate(NAMES):
        r[fts.grid_col(fts.Q_STATE, n)] = states[i]
        r[fts.grid_col(fts.Q_QUIT, n)] = (quit_ or {}).get(i, "")
        r[fts.grid_col(fts.Q_NEVER, n)] = (never or {}).get(i, "")
    return r


# 가짜 응답 6개. 1번과 6번만 시트에 들어간다
R1 = response(states=["자주 쓴다", "안 써봤다", "써봤는데 지금은 안 쓴다", "이 서비스에 있는지 모르겠다"],
              never={0: "나한테 필요 없을 것 같아서",  # 4-3과 안 맞는 체크 (자주 쓴다)
                     1: "나한테 필요 없을 것 같아서, 다른 앱이나 방법으로 해결해서"},
              quit_={2: "써보니 불편해서"},
              why_use="공고 검색·필터: 어제 인턴 공고를 찾으려고 썼고 조건을 한 번에 걸어서 편했습니다.",
              why_not=f"공고 저장 (스크랩, 찜, 북마크): 카톡 나에게 보내기로 모아 둡니다.{NL}"
                      "마감 알림: 알림이 너무 많이 와서 껐습니다.")
R2 = response(consent="동의하지 않습니다", used="", service="", platform="")
R3 = response(used="없다", service="", platform="")
R4 = response(used="없다")  # 써본 적 없다면서 서비스를 골랐다
R5 = response(service="사람인")
R6 = response(service="에브리커리어(캠퍼스픽)", platform="웹사이트",
              states=["안 써봤다", "가끔 쓴다", "자주 쓴다", "자주 쓴다"], never={0: "기타"},
              why_not="써본 적은 없습니다. 검색창에 직접 칩니다")


def write_responses(name, rows, cols=None):
    path = TMP / name
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols or header(), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return name


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fts.main(list(argv), root=TMP)
    return code, out.getvalue() + err.getvalue()


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class TestTitlesMatchForm(unittest.TestCase):
    def test_titles_and_options_are_in_generator(self):
        gs = (REPO / "docs/form-b/SimTrust-폼B-v2-생성.gs").read_text(encoding="utf-8")
        for text in [fts.Q_CONSENT, fts.Q_USED, fts.Q_SERVICE, fts.Q_PLATFORM, fts.Q_STATE, fts.Q_WHY_USE,
                     fts.Q_QUIT, fts.Q_NEVER, fts.Q_WHY_NOT, fts.CONSENT_YES, fts.USED_NO,
                     *fts.PLATFORM_OF, *fts.STATE_KIND, *fts.QUIT_OPTIONS, *NAMES]:
            self.assertIn(f"'{text}'", gs)


class TestCountAndMake(unittest.TestCase):
    def setUp(self):
        self.src = write_responses("responses.csv", [R1, R2, R3, R4, R5, R6])

    def test_count_shows_numbers_only(self):
        code, log = run("count", "--responses", self.src, "--service-map", MAP)
        self.assertEqual(code, 0, log)
        self.assertIn("linkareer: 1명 (앱 1, 웹 0)", log)
        self.assertIn("campuspick: 1명 (앱 0, 웹 1)", log)
        for label in ("동의 안 함: 1", "써본 적 없음: 1", "앞뒤 안 맞음", "대조 서비스 아님: 1",
                      "4-3과 안 맞아 뺀 4-6 칸: 1", "F4 1명"):
            self.assertIn(label, log)
        self.assertNotIn("카톡", log)  # 서술은 안 보여준다
        # 지도 없이 세면 폼 보기 이름 그대로 센다
        code, log = run("count", "--responses", self.src)
        self.assertEqual(code, 0, log)
        self.assertIn("사람인: 1명", log)

    def test_count_detail_for_pilot(self):
        # 파일럿 숫자: 개수만 찍고 서술은 안 찍는다. 사람 수 시뮬레이션에 넣을 값까지 낸다
        code, log = run("count", "--responses", self.src, "--service-map", MAP, "--detail")
        self.assertEqual(code, 0, log)
        self.assertIn("응답자 2명", log)
        self.assertIn("F1 4-3: 자주 쓴다 1, 가끔 쓴다 0, 써봤는데 지금은 안 쓴다 0, 안 써봤다 1", log)
        self.assertIn("F2 4-6: 나한테 필요 없을 것 같아서 1, 다른 앱이나 방법으로 해결해서 1", log)
        self.assertIn("F3 4-5: 써보니 불편해서 1", log)
        self.assertIn("4-4 서술을 쓴 사람: 1/2명", log)  # 2번째 응답자는 "없음"
        self.assertIn("4-7 서술을 쓴 사람: 2/2명", log)
        self.assertIn("안 써본 비율: 0.25", log)  # 8칸 중 2칸
        # 기타 뺀 체크 3개, 기능별 서술 줄 3개("써본 적은 없습니다."는 이유가 아니라 빼고 센다)
        self.assertIn("공통 이유 비율 (참고용 대략값): 0.5", log)
        self.assertIn("파일럿 사본 폼 응답에만", log)
        self.assertIn("params로 잰다", log)
        for text in ("카톡", "알림이 너무", "검색창"):
            self.assertNotIn(text, log)
        d = fts.detail_counts(fts.read_responses(TMP / self.src, FEATURES, fts.load_lines(
            REPO / "docs/ai-protocol/options_4-6.txt"), fts.parse_service_map(MAP))["people"], FEATURES,
            fts.load_lines(REPO / "docs/ai-protocol/options_4-6.txt"))
        self.assertEqual((d["common_checks"], d["feature_lines"]), (3, 3))

    def test_make_sheet(self):
        code, log = run("make", "--responses", self.src, "--service-map", MAP, "--out", "out_make")
        self.assertEqual(code, 0, log)
        rows = read(next((TMP / "out_make").glob("sheet_*.csv")))
        got = [(r["respondent_id"], r["service"], r["platform"], r["feature_id"], r["kind"]) for r in rows]
        self.assertEqual(got, [("R001", "linkareer", "app", "F1", "use"),
                               ("R001", "linkareer", "app", "F2", "nouse"),
                               ("R001", "linkareer", "app", "F3", "nouse_quit"),
                               ("R002", "campuspick", "web", "F1", "nouse"),
                               ("R002", "campuspick", "web", "F2", "use"),
                               ("R002", "campuspick", "web", "F3", "use"),
                               ("R002", "campuspick", "web", "F4", "use")])
        by = {r["row_id"]: r for r in rows}
        self.assertEqual(by["R001-F1"]["options"], "")  # 4-3과 안 맞는 4-6 체크는 뺐다
        self.assertEqual(by["R001-F2"]["options"], "나한테 필요 없을 것 같아서 / 다른 앱이나 방법으로 해결해서")
        self.assertEqual(by["R001-F3"]["options"], "써보니 불편해서")
        # 서술은 기능별 줄로 나눠 준다. 원문 전체도 같이 둔다
        self.assertEqual(by["R001-F1"]["text_feature"], "어제 인턴 공고를 찾으려고 썼고 조건을 한 번에 걸어서 편했습니다.")
        self.assertEqual(by["R001-F2"]["text_feature"], "카톡 나에게 보내기로 모아 둡니다.")
        self.assertEqual(by["R001-F3"]["text_feature"], "알림이 너무 많이 와서 껐습니다.")
        self.assertIn("카톡", by["R001-F3"]["text_all"])
        self.assertIn("검색창에 직접 칩니다", by["R002-F1"]["text_feature"])  # 안 써본 기능이 하나뿐
        self.assertEqual((by["R002-F2"]["text_feature"], by["R002-F2"]["text_all"]), ("", ""))  # "없음"
        self.assertTrue(all(r["code_1"] == r["code_2"] == r["code_final"] == "" for r in rows))
        summary = json.loads(next((TMP / "out_make").glob("sheet_*.summary.json")).read_text(encoding="utf-8"))
        self.assertEqual(summary["respondents"], 2)
        self.assertEqual(summary["rows_by_kind"], {"use": 4, "nouse": 2, "nouse_quit": 1})
        self.assertIn("올리지 않는다", log)

    def test_make_errors(self):
        code, log = run("make", "--responses", self.src, "--out", "out_err")  # 지도 없음
        self.assertEqual(code, 1, log)
        bad_state = write_responses("bad_state.csv", [response(states=["많이 쓴다"] + ["자주 쓴다"] * 3)])
        bad_option = write_responses("bad_option.csv", [response(states=["안 써봤다"] + ["자주 쓴다"] * 3,
                                                                 never={0: "그냥"})])
        no_col = write_responses("no_col.csv", [R1], cols=header()[:-1])
        for name in (bad_state, bad_option, no_col):
            with self.subTest(name=name):
                code, log = run("make", "--responses", name, "--service-map", MAP, "--out", "out_err")
                self.assertEqual(code, 4, log)
        code, log = run("make", "--responses", "nothing.csv", "--service-map", MAP, "--out", "out_err")
        self.assertEqual(code, 1, log)
        self.assertFalse((TMP / "out_err").exists())


class TestPilotParams(unittest.TestCase):
    def test_params_from_coded_pilot(self):
        # 사전등록 3장: 안 써본 칸마다 4-6 보기와 4-7 코드를 합친 코드 묶음으로 공통 이유 비율과 이유 2개 비율을 잰다
        src = write_responses("pilot.csv", [R1, R6])
        code, log = run("make", "--responses", src, "--service-map", MAP, "--out", "out_pilot")
        self.assertEqual(code, 0, log)
        rows = read(next((TMP / "out_pilot").glob("sheet_*.csv")))
        fill = {"R001-F2": "C01;C02;F2-01", "R002-F1": "C02"}  # 안 써본 칸 2개. 나머지 칸은 이유 없음(-)
        for r in rows:
            c = fill.get(r["row_id"], "-")
            r.update({"code_1": c, "code_2": c, "code_final": c})
        with (TMP / "pilot_filled.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fts.SHEET_FIELDS)
            w.writeheader()
            w.writerows(rows)
        (TMP / "pilot_book.csv").write_text(f"code,scope{NL}C01,공통{NL}C02,공통{NL}F2-01,기능{NL}", encoding="utf-8")
        code, log = run("import", "--sheet", "pilot_filled.csv", "--codebook", "pilot_book.csv", "--out", "out_pilot_h")
        self.assertEqual(code, 0, log)
        human = next((TMP / "out_pilot_h").glob("human_codes_*.csv")).relative_to(TMP).as_posix()
        code, log = run("params", "--responses", src, "--service-map", MAP, "--human", human,
                        "--codebook", "pilot_book.csv")
        self.assertEqual(code, 0, log)
        # 안 써본 칸 8칸 중 2칸, 코드 4개 중 공통 3개, 코드가 있는 칸 2개 중 2개 이상인 칸 1개(3개짜리)
        self.assertIn("안 써본 비율 (4-3 \"안 써봤다\"만): 0.25", log)
        self.assertIn("공통 이유 비율: 0.75", log)
        self.assertIn("이유 2개 비율: 0.5 (3개 이상인 칸 1개", log)
        self.assertIn('--pilot "p_nouse=0.25,common=0.75,p_two=0.5"', log)
        for text in ("카톡", "알림이 너무", "검색창"):
            self.assertNotIn(text, log)


    def test_params_drop_exclude_codes(self):
        # 제외 코드(C07)는 판정 계산기처럼 공통 이유 비율·이유 2개 비율에서 뺀다 (#43)
        book = {"C01": "common", "C07": "exclude", "F2-01": "feature"}
        rows = [{"kind": "nouse", "service": "s", "respondent_id": rid, "feature_id": fid, "code": code}
                for rid, fid, code in (("R1", "F1", "C01"), ("R1", "F1", "C07"),
                                       ("R2", "F1", "C07"), ("R3", "F2", "F2-01"))]
        rows.append({"kind": "use", "service": "s", "respondent_id": "R4", "feature_id": "F1", "code": "C07"})
        c = fts.pilot_code_params(rows, book)
        self.assertEqual(c["nouse_cells"], 3)  # R2 칸도 안 써본 칸으로는 센다
        self.assertEqual(c["coded_cells"], 2)  # R2는 제외 코드만 있어서 코드 없는 칸
        self.assertEqual(c["codes"], 2)
        self.assertEqual(c["common"], 0.5)
        self.assertEqual(c["p_two"], 0.0)  # R1은 C07을 빼면 1개
        self.assertEqual(c["excluded_codes"], 2)

class TestImport(unittest.TestCase):
    def setUp(self):
        src = write_responses("responses_i.csv", [R1, R6])
        code, log = run("make", "--responses", src, "--service-map", MAP, "--out", "out_i")
        assert code == 0, log
        self.rows = read(next((TMP / "out_i").glob("sheet_*.csv")))
        (TMP / "book.csv").write_text(f"code,scope{NL}NEED,common{NL}ALT,common{NL}HARD,feature{NL}"
                                      f"FIND,feature{NL}", encoding="utf-8")

    def write_sheet(self, name, fill):
        rows = [dict(r) for r in self.rows]
        for r in rows:
            r.update(fill(r))
        with (TMP / name).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fts.SHEET_FIELDS)
            w.writeheader()
            w.writerows(rows)
        return name

    @staticmethod
    def good(r):
        codes = {"R001-F1": "FIND", "R001-F2": "NEED; alt", "R001-F3": "HARD", "R002-F1": "ALT"}.get(r["row_id"], "-")
        return {"code_1": codes, "code_2": codes, "code_final": codes}

    def test_import_to_human_codes(self):
        sheet = self.write_sheet("filled.csv", self.good)
        code, log = run("import", "--sheet", sheet, "--codebook", "book.csv", "--out", "out_h")
        self.assertEqual(code, 0, log)
        human = read(next((TMP / "out_h").glob("human_codes_*.csv")))
        got = [(r["respondent_id"], r["feature_id"], r["kind"], r["code"]) for r in human]
        self.assertIn(("R001", "F2", "nouse", "ALT"), got)  # 소문자도 맞추고 ;로 나눈다
        self.assertIn(("R001", "F2", "nouse", "NEED"), got)
        self.assertIn(("R002", "F2", "use", ""), got)  # 붙일 코드 없음(-)은 빈 코드 한 줄
        self.assertEqual(len(human), 8)
        report = json.loads(next((TMP / "out_h").glob("human_agreement_*.json")).read_text(encoding="utf-8"))
        self.assertEqual((report["agreement"], report["kappa"]), (1.0, 1.0))
        # 계산기가 그대로 읽는다
        loaded = sr.load_human(next((TMP / "out_h").glob("human_codes_*.csv")))
        self.assertEqual(len(loaded), 8)

    def test_import_alt_means_and_subtype(self):
        # 코딩 규칙 v0.1 4장: 대체 수단, 세부 유형(F4만)을 칸으로 받아 사람 코드 CSV에 같이 남긴다
        extra = {"R001-F2": {"alt_means": "범용 앱 ; 사람·학교"}, "R002-F1": {"alt_means": "다른 공고 서비스"}}
        sheet = self.write_sheet("extra.csv", lambda r: {**self.good(r), **extra.get(r["row_id"], {})})
        code, log = run("import", "--sheet", sheet, "--codebook", "book.csv", "--out", "out_x")
        self.assertEqual(code, 0, log)
        human = read(next((TMP / "out_x").glob("human_codes_*.csv")))
        got = {(r["respondent_id"], r["feature_id"], r["code"]): r["alt_means"] for r in human}
        self.assertEqual(got[("R001", "F2", "NEED")], "범용 앱;사람·학교")
        self.assertEqual(got[("R002", "F1", "ALT")], "다른 공고 서비스")
        self.assertEqual(got[("R001", "F1", "FIND")], "")
        self.assertEqual(len(sr.load_human(next((TMP / "out_x").glob("human_codes_*.csv")))), 8)  # 계산기가 읽는다
        # 정해진 값이 아니거나, 세부 유형을 F4가 아닌 기능에 적으면 멈춘다
        bad_alt = self.write_sheet("bad_alt.csv", lambda r: {**self.good(r), "alt_means": "카톡"})
        bad_sub = self.write_sheet("bad_sub.csv", lambda r: {**self.good(r), "subtype": "광고"})
        for name, word in ((bad_alt, "alt_means"), (bad_sub, "F4")):
            with self.subTest(name=name):
                code, log = run("import", "--sheet", name, "--codebook", "book.csv", "--out", "out_bad_x")
                self.assertEqual(code, 4, log)
                self.assertIn(word, log)
        self.assertFalse((TMP / "out_bad_x").exists())
        # 두 칸이 없는 옛 시트도 받는다
        old = [{k: v for k, v in {**r, **self.good(r)}.items() if k not in rsh.EXTRA_COLS} for r in self.rows]
        with (TMP / "old.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[c for c in fts.SHEET_FIELDS if c not in rsh.EXTRA_COLS])
            w.writeheader()
            w.writerows(old)
        code, log = run("import", "--sheet", "old.csv", "--codebook", "book.csv", "--out", "out_old")
        self.assertEqual(code, 0, log)

    def test_import_errors(self):
        blank = self.write_sheet("blank.csv", lambda r: {**self.good(r), "code_2": ""})
        comma = self.write_sheet("comma.csv", lambda r: {**self.good(r), "code_final": "NEED, ALT"})
        unknown = self.write_sheet("unknown.csv", lambda r: {**self.good(r), "code_final": "WHAT"})
        low = self.write_sheet("low.csv", lambda r: {**self.good(r), "code_2": "NEED" if r["code_1"] != "NEED" else "ALT"})
        for name in (blank, comma, unknown, low):
            with self.subTest(name=name):
                code, log = run("import", "--sheet", name, "--codebook", "book.csv", "--out", "out_bad")
                self.assertEqual(code, 4, log)
        self.assertFalse((TMP / "out_bad").exists())
        code, log = run("import", "--sheet", low, "--codebook", "book.csv", "--out", "out_low",
                        "--accept-low-kappa", "시험")
        self.assertEqual(code, 0, log)


if __name__ == "__main__":
    unittest.main()

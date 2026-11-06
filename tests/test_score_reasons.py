"""scripts/score_reasons.py 오프라인 테스트. API 없이 돈다.

리포 루트에서:
    python -m unittest tests.test_score_reasons -v
"""

import contextlib
import copy
import csv
import io
import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import score_reasons as sr  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="simtrust_score_test_"))
RULES = json.loads((REPO / "configs/rules.draft.json").read_text(encoding="utf-8"))
HUMAN_HEAD = ["respondent_id", "service", "platform", "feature_id", "kind", "code", "order"]


def rules(**over):
    r = copy.deepcopy(RULES)
    r["resamples"] = 200
    r.update(over)
    return r


def human_rows(cell, people, service="svc", platform="app", kind="nouse"):
    """people: {응답자: [코드...]} -> 사람 코드 행. 코드가 없으면 빈 code 한 줄."""
    rows = []
    for i, (rid, codes) in enumerate(people.items()):
        for c in codes or [""]:
            rows.append({"respondent_id": rid, "service": service, "platform": platform, "feature_id": cell,
                         "kind": kind, "code": c, "order": str(i)})
    return rows


def ai_rows(cell, episodes, condition=2, service="svc", platform="app", kind="nouse"):
    """episodes: {에피소드: [코드...]} -> AI 코드 행."""
    rows = []
    for run_id, codes in episodes.items():
        for c in codes:
            rows.append({"item_id": f"{run_id}-{cell}-{c}", "run_id": run_id, "service": service,
                         "platform": platform, "condition": condition, "persona_id": run_id, "repeat": "1",
                         "feature_id": cell, "kind": kind, "code": c})
    return rows


def write(name, head, rows):
    path = TMP / name
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head)
        w.writeheader()
        w.writerows(rows)
    return name


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = sr.main(list(argv), root=TMP)
    return code, out.getvalue() + err.getvalue()


def find(cells, **kw):
    hits = [c for c in cells if all(c.get(k) == v for k, v in kw.items())]
    assert len(hits) == 1, (kw, len(hits))
    return hits[0]


# 칸 하나: 사람 5명, AI 에피소드 2개
BASIC_H = human_rows("F1", {"P1": ["A", "B"], "P2": ["A"], "P3": ["C"], "P4": [], "P5": ["A", "D"]})
BASIC_A = ai_rows("F1", {"e1": ["A", "X"], "e2": ["B"]})


class TestNumbers(unittest.TestCase):
    def test_precision_recall_and_reason_filter(self):
        res = sr.score(BASIC_H, BASIC_A, rules())
        c = find(res["cells"], feature_id="F1", condition=2)
        self.assertEqual(c["n_humans"], 5)  # 코드 없이 답한 P4도 사람 수에 든다
        self.assertEqual(c["ai_episodes"], 2)
        self.assertAlmostEqual(c["full"]["precision"], 2 / 3)  # AI 이유 A,B,X 중 사람도 말한 것 A,B
        self.assertAlmostEqual(c["full"]["recall"], 2 / 4)  # 사람 이유 A,B,C,D 중 AI도 말한 것 A,B
        self.assertEqual([(r["code"], r["human_count"], r["passed"]) for r in c["reasons"]],
                         [("A", 3, True), ("B", 1, True), ("X", 0, False)])
        self.assertEqual([(r["code"], r["human_count"]) for r in c["missed"]], [("C", 1), ("D", 1)])

    def test_pr_none_when_empty(self):
        self.assertEqual(sr.pr(set(), {"A"}), (None, 0.0))
        self.assertEqual(sr.pr({"A"}, set()), (0.0, None))

    def test_drop_code_is_not_a_reason(self):
        res = sr.score(BASIC_H, BASIC_A + ai_rows("F1", {"e3": ["-"]}), rules())
        c = find(res["cells"], feature_id="F1", condition=2)
        self.assertEqual(c["ai_episodes"], 3)  # 에피소드는 센다
        self.assertAlmostEqual(c["full"]["precision"], 2 / 3)  # 이유로는 안 센다
        self.assertEqual(res["dropped_ai_rows"], 1)

    def test_same_seed_same_result(self):
        a = sr.score(BASIC_H, BASIC_A, rules())
        b = sr.score(list(reversed(BASIC_H)), list(reversed(BASIC_A)), rules())
        self.assertEqual(a["cells"][0]["draws"], b["cells"][0]["draws"])  # 입력 순서와 상관없이 같은 뽑기

    def test_floor_uses_other_features_only(self):
        h = BASIC_H + human_rows("F2", {"P1": ["A"], "P2": ["E"]}) + human_rows("F1", {"Q1": ["A"]}, kind="use")
        a = BASIC_A + ai_rows("F2", {"e1": ["E"]}) + ai_rows("F1", {"e1": ["A"]}, kind="use") \
            + ai_rows("F3", {"e1": ["A"]}, platform="web")
        res = sr.score(h, a, rules(cell_keys=["service", "platform", "feature_id", "kind"]))
        c = find(res["cells"], feature_id="F1", kind="nouse", platform="app", condition=2)
        self.assertEqual(c["floor_partners"], 1)  # F2 nouse만. 같은 기능 use, 다른 플랫폼은 안 쓴다
        # F2의 AI 코드 {E}는 F1 사람 코드와 하나도 안 겹친다
        self.assertEqual(set(c["draws"]["floor_precision"]), {0.0})
        # 앱·웹을 합친 칸(11/6 D4)에서는 웹 F3도 같은 서비스의 다른 기능이라 짝이 된다
        merged = find(sr.score(h, a, rules())["cells"], feature_id="F1", kind="nouse", condition=2)
        self.assertEqual(merged["floor_partners"], 2)

    def test_ai_sample_matches_human_half(self):
        # 뽑을 때마다 AI도 사람 A와 같은 인원(페르소나 수)만 쓴다. 같은 페르소나의 반복은 하나만 쓴다
        many = {"persona_eps": {f"p{i}": {f"e{i}"} for i in range(10)},
                "ep_codes": {f"e{i}": {f"C{i}"} for i in range(10)}}
        rng = random.Random(1)
        self.assertEqual({len(sr.sample_ai(many, 3, rng)) for _ in range(50)}, {3})
        rep = {"persona_eps": {"p0": {"r1", "r2"}}, "ep_codes": {"r1": {"A"}, "r2": {"B"}}}
        self.assertEqual({frozenset(sr.sample_ai(rep, 3, rng)) for _ in range(50)}, {frozenset("A"), frozenset("B")})

    def test_other_cells_do_not_move_this_split(self):
        # 다른 기능에 AI 코드가 늘어도 이 칸의 사람 나누기는 그대로다 (난수를 따로 쓴다)
        h = BASIC_H + human_rows("F2", {"P1": ["A"], "P2": ["E"]})
        a = BASIC_A + ai_rows("F2", {"e1": ["E"]})
        before = find(sr.score(h, a, rules())["cells"], feature_id="F1", condition=2)
        after = find(sr.score(h, a + ai_rows("F3", {"e9": ["Q"]}), rules())["cells"], feature_id="F1", condition=2)
        self.assertEqual(before["draws"]["human_precision"], after["draws"]["human_precision"])
        self.assertEqual(before["draws"]["ai_precision"], after["draws"]["ai_precision"])

    def test_codes_are_normalized(self):
        self.assertEqual([sr.norm_code(x) for x in ("n01", "\uff2e\uff10\uff11", " N01 ", "\u2013")],
                         ["N01", "N01", "N01", "-"])
        rows = [{"kind": "nouse", "platform": "app", "service": "svc", "feature_id": "F1", "code": "u-find"}]
        sr.check_common(rows, "x")
        self.assertEqual(rows[0]["code"], "U-FIND")
        with self.assertRaises(sr.InputError):
            sr.check_common([{**rows[0], "code": "N01, N02"}], "x")

    def test_quit_reasons_are_a_separate_reference(self):
        # 폼 B v2 210행: 그만둔 사람(4-5)과 안 써본 사람(4-6)의 안 쓸 이유는 따로 센다
        h = BASIC_H + human_rows("F1", {"Q1": ["X"], "Q2": ["B"]}, kind="nouse_quit")
        res = sr.score(h, BASIC_A, rules())
        quit_cell = find(res["cells"], feature_id="F1", kind="nouse_quit", condition=2)
        never = find(res["cells"], feature_id="F1", kind="nouse", condition=2)
        self.assertEqual(quit_cell["ai_codes"], never["ai_codes"])  # 같은 AI 안 쓸 이유를 대 본다
        self.assertEqual((quit_cell["n_humans"], never["n_humans"]), (2, 5))
        self.assertEqual(sum(res["summary"]["verdicts"][2].values()), 1)  # 요약 판정 수에는 본 비교만
        self.assertIn(2, res["summary"]["quit_reference"])
        with self.assertRaises(sr.InputError):
            sr.check_common([{**BASIC_A[0], "kind": "nouse_quit"}], "ai")  # AI 쪽에는 없는 kind

    def test_service_cells_pool_platforms(self):
        # 11/6 D4: 판정 칸은 서비스 x 기능 x 쓸/안 쓸. 플랫폼별 칸은 사람이 하한 이상일 때만 참고로 낸다
        h = (human_rows("F1", {f"A{i}": ["A"] for i in range(3)})
             + human_rows("F1", {f"W{i}": ["A"] for i in range(3)}, platform="web"))
        a = ai_rows("F1", {"e1": ["A"]}) + ai_rows("F1", {"e2": ["A"]}, platform="web")
        res = sr.score(h, a, rules())
        c = find(res["cells"], feature_id="F1", condition=2)
        self.assertEqual((c["n_humans"], c["n_humans_app"], c["n_humans_web"]), (6, 3, 3))
        self.assertNotIn("platform", c)
        self.assertEqual(res["platform_ref"], [])  # 플랫폼마다 3명이라 하한 5명 미만
        res3 = sr.score(h, a, rules(min_humans=3))
        self.assertEqual(sorted(x["platform"] for x in res3["platform_ref"]), ["app", "web"])
        self.assertEqual({x["scope"] for x in res3["platform_ref"]}, {"platform_ref"})
        self.assertEqual(sum(res3["summary"]["verdicts"][2].values()), 1)  # 요약 판정 수에는 본 칸만
        self.assertIn(2, res3["summary"]["platform_reference"])

    def test_ai_sampled_by_human_platform_ratio(self):
        # 사람은 전부 앱이다. AI는 앱 페르소나가 A, 웹 페르소나가 W를 말한다.
        # 사람 비율대로 뽑으면 웹 페르소나는 안 뽑혀서 AI 통과율이 늘 1이다
        h = human_rows("F1", {f"P{i}": ["A"] for i in range(6)})
        a = (ai_rows("F1", {f"a{i}": ["A"] for i in range(4)})
             + ai_rows("F1", {f"w{i}": ["W"] for i in range(4)}, platform="web"))
        c = find(sr.score(h, a, rules())["cells"], feature_id="F1", condition=2)
        self.assertEqual(set(c["draws"]["ai_precision"]), {1.0})
        self.assertEqual(c["ai_platform_short"], 0)
        cell_ = {"persona_eps": {("app", "p1"): {"e1"}, ("web", "p2"): {"e2"}},
                 "ep_codes": {"e1": {"A"}, "e2": {"W"}}}
        rng = random.Random(3)
        self.assertEqual({frozenset(sr.sample_ai(cell_, {"web": 1}, rng)) for _ in range(20)}, {frozenset("W")})

    def test_ai_platform_short_is_counted(self):
        # 사람 A 3명이 다 앱인데 AI 앱 페르소나가 1명뿐이면 모자란 뽑기로 센다
        h = human_rows("F1", {f"P{i}": ["A"] for i in range(6)})
        a = ai_rows("F1", {"a1": ["A"]}) + ai_rows("F1", {f"w{i}": ["W"] for i in range(5)}, platform="web")
        res = sr.score(h, a, rules())
        c = find(res["cells"], feature_id="F1", condition=2)
        self.assertEqual(c["ai_platform_short"], rules()["resamples"])
        self.assertEqual(res["summary"]["ai_platform_short_cells"], 1)

    def test_nocommon_metrics(self):
        # 공통 코드(C1)를 빼고도 잰다. 판정에는 안 쓴다
        h = human_rows("F1", {"P1": ["C1", "F1A"], "P2": ["C1"], "P3": ["F1B"]})
        a = ai_rows("F1", {"e1": ["C1", "F1A"], "e2": ["X"]})
        book = {"C1": "common", "F1A": "feature", "F1B": "feature"}
        c = find(sr.score(h, a, rules(), book)["cells"], feature_id="F1", condition=2)
        self.assertAlmostEqual(c["full"]["precision"], 2 / 3)
        self.assertAlmostEqual(c["full"]["recall"], 2 / 3)
        self.assertEqual((c["nocommon"]["precision"], c["nocommon"]["recall"]), (0.5, 0.5))
        self.assertEqual((c["nocommon"]["ai_codes"], c["nocommon"]["human_codes"]), (2, 2))
        self.assertEqual({r["code"]: r["common"] for r in c["reasons"]}, {"C1": True, "F1A": False, "X": False})
        plain = find(sr.score(h, a, rules())["cells"], feature_id="F1", condition=2)
        self.assertIsNone(plain["nocommon"])

    def test_pooled_cell_keys(self):
        h = human_rows("F1", {"P1": ["A"]}, service="s1") + human_rows("F1", {"P2": ["B"]}, service="s2")
        a = ai_rows("F1", {"e1": ["A"]}, service="s1") + ai_rows("F1", {"e2": ["B"]}, service="s2")
        res = sr.score(h, a, rules(cell_keys=["platform", "feature_id", "kind"]))
        self.assertEqual(len(res["cells"]), 1)
        c = res["cells"][0]
        self.assertEqual((c["n_humans"], c["full"]["precision"], c["full"]["recall"]), (2, 1.0, 1.0))


def cell(ai, human, floor, n=10, codes=("A",), recall=None):
    """judge()만 시험하려고 뽑기 결과를 직접 넣은 칸. recall을 안 주면 precision과 같은 값."""
    draws = {}
    for m in sr.METRICS:
        src = {"ai": [ai] * 3, "human": human, "floor": floor}
        if m == "recall" and recall is not None:
            src = recall
        for who, vals in src.items():
            draws[f"{who}_{m}"] = vals
    return {"n_humans": n, "ai_codes": list(codes), "full": {"precision": ai, "recall": ai}, "draws": draws}


class TestJudge(unittest.TestCase):
    rule = sr.merge_rule(RULES, {})
    HUMAN = [0.6, 0.7, 0.8, 0.9]
    FLOOR = [0.1, 0.2, 0.3]

    def test_order_of_verdicts(self):
        self.assertEqual(sr.judge(cell(0.75, self.HUMAN, self.FLOOR), self.rule), sr.TRUST)
        self.assertEqual(sr.judge(cell(0.5, self.HUMAN, self.FLOOR), self.rule), sr.REF)
        self.assertEqual(sr.judge(cell(0.25, self.HUMAN, self.FLOOR), self.rule), sr.ASK)
        self.assertEqual(sr.judge(cell(0.75, self.HUMAN, self.FLOOR, n=4), self.rule), sr.LOW)
        self.assertEqual(sr.judge(cell(0.75, self.HUMAN, self.FLOOR, codes=()), self.rule), sr.NA)

    def test_overlapping_anchors_are_conservative(self):
        # 사람 범위 아래쪽(0.2)은 넘지만 아무 기능에나 할 말 위쪽(0.5) 안이면 믿지 않는다
        self.assertEqual(sr.judge(cell(0.4, [0.2, 0.5, 0.9], [0.1, 0.3, 0.5]), self.rule), sr.ASK)

    def test_no_floor_partner(self):
        self.assertEqual(sr.judge(cell(0.5, self.HUMAN, [None, None]), self.rule), sr.REF)
        # 아무 기능에나 할 말과 비교할 수 없으면 사람 범위 안이어도 믿음 판정은 안 낸다
        self.assertEqual(sr.judge(cell(0.75, self.HUMAN, [None, None]), self.rule), sr.REF)

    def test_zero_ai_is_not_trusted(self):
        # 사람끼리 구간 아래쪽이 0이어도 AI가 하나도 못 맞히면(중앙값 0) 믿지 않는다
        self.assertEqual(sr.judge(cell(0.0, [0.0, 0.2, 0.5], [None, None]), self.rule), sr.ASK)
        self.assertEqual(sr.judge(cell(0.0, [0.0, 0.2, 0.5], self.FLOOR), self.rule), sr.ASK)

    def test_zero_match_scenario(self):
        # 점검에서 나온 예: 사람 6명이 다 다른 이유, AI는 사람과 안 겹치는 이유, 비교할 다른 기능 없음
        h = human_rows("F4", {f"P{i}": [f"N{i}"] for i in range(6)})
        res = sr.score(h, ai_rows("F4", {"e1": ["Z1"], "e2": ["Z2"]}), rules())
        c = find(res["cells"], feature_id="F4", condition=2)
        self.assertEqual((c["full"]["precision"], c["verdict"]), (0.0, sr.ASK))
        self.assertEqual(c["sensitivity"]["anchors_90"], sr.ASK)

    def test_recall_also_counts(self):
        low_recall = {"ai": [0.3] * 3, "human": self.HUMAN, "floor": self.FLOOR}
        self.assertEqual(sr.judge(cell(0.75, self.HUMAN, self.FLOOR, recall=low_recall), self.rule), sr.REF)
        only_p = {**self.rule, "metrics": ["precision"]}
        self.assertEqual(sr.judge(cell(0.75, self.HUMAN, self.FLOOR, recall=low_recall), only_p), sr.TRUST)

    def test_fixed_thresholds(self):
        fixed = sr.merge_rule(RULES, {"method": "fixed", "trust": 0.7, "reference": 0.5})
        self.assertEqual(sr.judge(cell(0.7, [], []), fixed), sr.TRUST)
        self.assertEqual(sr.judge(cell(0.69, [], []), fixed), sr.REF)
        self.assertEqual(sr.judge(cell(0.49, [], []), fixed), sr.ASK)

    def test_interval(self):
        vals = [i / 100 for i in range(101)]
        self.assertEqual([round(x, 3) for x in sr.interval(vals, 0.95)], [0.025, 0.975])
        self.assertIsNone(sr.interval([None, None], 0.95))


class TestStabilityAndSaturation(unittest.TestCase):
    def test_stable_when_everyone_says_the_same(self):
        h = human_rows("F1", {f"P{i}": ["A", "B"] for i in range(9)})
        res = sr.score(h, ai_rows("F1", {"e1": ["A", "X"]}), rules())
        st = res["cells"][0]["stability"]
        self.assertEqual([r["k"] for r in st["sizes"]], [3, 5, 7, 9])
        self.assertEqual({r["precision_mean"] for r in st["sizes"]}, {0.5})
        self.assertEqual(st["stable_at"], 3)

    def test_saturation_follows_order_column(self):
        people = {"P1": ["a", "b", "c"], "P2": ["a", "d"], "P3": ["e"], "P4": ["a"], "P5": []}
        h = human_rows("F1", people)
        h = list(reversed(h))  # 파일 순서가 아니라 order 칸 순서로 센다
        r = rules(saturation={"group_keys": ["service"], "min_respondents": 3, "run": 3, "max_new": 1})
        sat = sr.saturation(h, r)
        self.assertEqual(sat[0]["new_per_respondent"], [3, 1, 1, 0, 0])
        self.assertEqual(sat[0]["saturated_at"], 4)  # 하한 3명을 넘긴 뒤 2~4번째가 모두 1개 이하
        r["saturation"]["min_respondents"] = 15
        self.assertIsNone(sr.saturation(h, r)[0]["saturated_at"])


class TestCLI(unittest.TestCase):
    def setUp(self):
        (TMP / "rules.json").write_text(json.dumps(rules()), encoding="utf-8")
        self.h = write("human.csv", HUMAN_HEAD, BASIC_H + human_rows("F2", {"P1": ["E"], "P2": ["A"]}))
        self.a = write("ai.csv", sr.AI_FIELDS, BASIC_A + ai_rows("F1", {"z1": ["A"]}, condition=0)
                       + ai_rows("F2", {"e1": ["E"]}))

    def test_outputs(self):
        code, log = run("--human", self.h, "--ai", self.a, "--rules", "rules.json", "--out", "out_ok", "--allow-draft")
        self.assertEqual(code, 0, log)
        out = TMP / "out_ok"
        record = json.loads(next(out.glob("metrics_all_*.json")).read_text(encoding="utf-8"))
        self.assertFalse(record["rules_frozen"])
        self.assertEqual(record["conditions"], [0, 2])
        self.assertEqual(len(record["inputs"]["human"]["sha256"]), 64)
        with next(out.glob("cells_all_*.csv")).open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len([r for r in rows if r["scope"] == "main"]), 4)  # 조건 2개 x 칸 2개
        # 플랫폼별 참고 칸: F1은 앱 5명이라 하한(5명)을 넘고, F2는 2명이라 빠진다
        ref = [r for r in rows if r["scope"] == "platform_ref"]
        self.assertEqual(sorted((r["condition"], r["feature_id"], r["platform"]) for r in ref),
                         [("0", "F1", "app"), ("2", "F1", "app")])
        self.assertEqual({r["platform"] for r in rows if r["scope"] == "main"}, {"*"})
        with next(out.glob("reasons_all_*.csv")).open(encoding="utf-8-sig") as f:
            reasons = list(csv.DictReader(f))
        x = [r for r in reasons if r["condition"] == "2" and r["feature_id"] == "F1" and r["code"] == "X"][0]
        self.assertEqual((x["passed"], x["basis"]), ("N", "응답자 중 이 이유를 말한 사람 없음"))
        a = [r for r in reasons if r["condition"] == "2" and r["feature_id"] == "F1" and r["code"] == "A"][0]
        self.assertEqual(a["basis"], "응답자 5명 중 3명이 같은 이유를 말함")
        self.assertIn("동결 전", log)
        self.assertNotIn("X", log.replace("x ", ""))  # 화면에는 코드를 안 찍는다

    def test_service_filter(self):
        code, log = run("--human", self.h, "--ai", self.a, "--rules", "rules.json", "--out", "out_f",
                        "--service", "svc", "--allow-draft")
        self.assertEqual(code, 0, log)
        self.assertTrue(next((TMP / "out_f").glob("metrics_svc_*.json")))
        code, log = run("--human", self.h, "--ai", self.a, "--rules", "rules.json", "--out", "out_none",
                        "--service", "nothing", "--allow-draft")
        self.assertEqual(code, 4, log)

    def test_input_errors(self):
        bad_kind = write("bad_kind.csv", HUMAN_HEAD, [{**BASIC_H[0], "kind": "maybe"}])
        no_col = TMP / "no_col.csv"
        no_col.write_text("respondent_id,service\nP1,svc\n", encoding="utf-8")
        bad_cond = write("bad_cond.csv", sr.AI_FIELDS, [{**BASIC_A[0], "condition": "7"}])
        empty_code = write("empty_code.csv", sr.AI_FIELDS, [{**BASIC_A[0], "code": ""}])
        broken = TMP / "broken.json"
        broken.write_text("{", encoding="utf-8")
        bad_rule = rules(sensitivity=[{"name": "x", "method": "fixed", "trust": 0.4, "reference": 0.6}])
        (TMP / "bad_rule.json").write_text(json.dumps(bad_rule), encoding="utf-8")
        no_feature = rules(cell_keys=["service", "kind"])
        (TMP / "no_feature.json").write_text(json.dumps(no_feature), encoding="utf-8")
        cases = [
            (["--human", "nothing.csv", "--ai", self.a, "--rules", "rules.json"], 1),
            (["--human", bad_kind, "--ai", self.a, "--rules", "rules.json"], 4),
            (["--human", "no_col.csv", "--ai", self.a, "--rules", "rules.json"], 4),
            (["--human", self.h, "--ai", bad_cond, "--rules", "rules.json"], 4),
            (["--human", self.h, "--ai", empty_code, "--rules", "rules.json"], 4),
            (["--human", self.h, "--ai", self.a, "--rules", "broken.json"], 4),
            (["--human", self.h, "--ai", self.a, "--rules", "bad_rule.json"], 4),
            (["--human", self.h, "--ai", self.a, "--rules", "no_feature.json"], 4),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                code, log = run(*argv, "--out", "out_err", "--allow-draft")
                self.assertEqual(code, expected, log)
        self.assertFalse((TMP / "out_err").exists())

    def test_guards(self):
        # 동결 전 규칙은 --allow-draft 없이 안 돈다
        code, log = run("--human", self.h, "--ai", self.a, "--rules", "rules.json", "--out", "out_g1")
        self.assertEqual(code, 4, log)
        self.assertIn("--allow-draft", log)
        # 사람 칸과 AI 칸이 하나도 안 겹치면 멈춘다 (service 글자가 다른 경우)
        other = write("human_other.csv", HUMAN_HEAD, human_rows("F1", {"P1": ["A"]}, service="가짜공고"))
        code, log = run("--human", other, "--ai", self.a, "--rules", "rules.json", "--out", "out_g2", "--allow-draft")
        self.assertEqual(code, 4, log)
        self.assertIn("안 겹친다", log)
        # 한 조건 안에 입력 방식이 섞이면 멈춘다
        head = sr.AI_FIELDS + ["input_mode"]
        mixed = write("ai_mixed.csv", head, [{**BASIC_A[0], "input_mode": "text"}, {**BASIC_A[1], "input_mode": "image"}])
        code, log = run("--human", self.h, "--ai", mixed, "--rules", "rules.json", "--out", "out_g3", "--allow-draft")
        self.assertEqual(code, 4, log)
        # 규칙 파일의 하위 항목이 빠지면 traceback이 아니라 입력 오류다
        r = rules()
        del r["stability"]["tolerance"]
        (TMP / "no_tol.json").write_text(json.dumps(r), encoding="utf-8")
        code, log = run("--human", self.h, "--ai", self.a, "--rules", "no_tol.json", "--out", "out_g4", "--allow-draft")
        self.assertEqual(code, 4, log)
        self.assertIn("tolerance", log)
        for d in ("out_g1", "out_g2", "out_g3", "out_g4"):
            self.assertFalse((TMP / d).exists())

    def test_codebook_cli(self):
        (TMP / "book.csv").write_text("code,scope,name\nA,공통,필요 없음\nB,feature,\nC,기능,\nD,feature,\nE,feature,\n",
                                      encoding="utf-8")
        code, log = run("--human", self.h, "--ai", self.a, "--rules", "rules.json", "--out", "out_book",
                        "--codebook", "book.csv", "--allow-draft")
        self.assertEqual(code, 0, log)
        self.assertIn("공통 코드 뺀", log)
        self.assertIn("코드북에 없는 AI 코드 1개", log)  # X
        out = TMP / "out_book"
        record = json.loads(next(out.glob("metrics_all_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(record["codebook"], {"codes": 5, "common": 1, "ai_codes_not_in_codebook": 1})
        self.assertIn("codebook", record["inputs"])
        with next(out.glob("cells_all_*.csv")).open(encoding="utf-8-sig") as f:
            f1 = [r for r in csv.DictReader(f) if r["scope"] == "main" and r["condition"] == "2"
                  and r["feature_id"] == "F1"][0]
        # AI {A,B,X}에서 공통 A를 빼면 {B,X}, 사람 {A,B,C,D}에서 빼면 {B,C,D}
        self.assertEqual((f1["precision_nocommon"], f1["recall_nocommon"]), ("0.5", "0.3333"))
        with next(out.glob("reasons_all_*.csv")).open(encoding="utf-8-sig") as f:
            flags = {r["code"]: r["common"] for r in csv.DictReader(f)
                     if r["scope"] == "main" and r["condition"] == "2" and r["feature_id"] == "F1"}
        self.assertEqual(flags["A"], "Y")
        self.assertEqual(flags["B"], "N")
        with next(out.glob("reasons_all_*.csv")).open(encoding="utf-8-sig") as f:
            names = {r["code"]: r["name"] for r in csv.DictReader(f) if r["scope"] == "main"}
        self.assertEqual((names["A"], names["B"]), ("필요 없음", ""))  # 코드북 name 칸을 이유 표에 붙인다
        # 사람 코드가 코드북에 없거나, scope가 이상하거나, 코드가 두 번 나오면 멈춘다
        (TMP / "book_missing.csv").write_text("code,scope\nA,common\n", encoding="utf-8")
        (TMP / "book_scope.csv").write_text("code,scope\nA,maybe\n", encoding="utf-8")
        (TMP / "book_dup.csv").write_text("code,scope\nA,common\na,feature\n", encoding="utf-8")
        for name in ("book_missing.csv", "book_scope.csv", "book_dup.csv", "nothing.csv"):
            with self.subTest(book=name):
                code, log = run("--human", self.h, "--ai", self.a, "--rules", "rules.json", "--out", "out_bad_book",
                                "--codebook", name, "--allow-draft")
                self.assertEqual(code, 1 if name == "nothing.csv" else 4, log)
        self.assertFalse((TMP / "out_bad_book").exists())

    def test_respondent_with_two_platforms_stops(self):
        rows = human_rows("F1", {"P1": ["A"]}) + human_rows("F2", {"P1": ["B"]}, platform="web")
        bad = write("human_two_plat.csv", HUMAN_HEAD, rows)
        code, log = run("--human", bad, "--ai", self.a, "--rules", "rules.json", "--out", "out_tp", "--allow-draft")
        self.assertEqual(code, 4, log)
        self.assertIn("platform", log)

    def test_draft_rules_file_loads(self):
        r = sr.load_rules(REPO / "configs/rules.draft.json")
        self.assertFalse(r["frozen"])
        self.assertEqual((r["method"], r["level"], r["resamples"], r["min_humans"]), ("anchors", 0.95, 1000, 5))


if __name__ == "__main__":
    unittest.main()

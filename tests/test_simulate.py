"""experiments/sample_size_sim/simulate.py 오프라인 테스트. 사전등록 v1 규칙을 코드로 옮긴 부분만 본다.

리포 루트에서:
    python -m unittest tests.test_simulate -v
"""

import json
import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments" / "sample_size_sim"))

import simulate as sim  # noqa: E402

BASE = [{"name": "common0.60", "common": 0.6, "p_nouse": 1 / 3, "p_two": 0.4},
        {"name": "common0.30", "common": 0.3, "p_nouse": 1 / 3, "p_two": 0.4}]
CRIT = {"min_same_trust": 0.8, "max_half_trust": 0.1, "max_common_only_trust": 0.05, "max_low": 0.05}


def kinds(same_trust=0.9, half_trust=0.0, gen_trust=0.0, low=0.0, gen_ask=1.0):
    base = {"trust": 0.0, "reference": 0.0, "ask": 0.0, "low": 0.0, "na": 0.0}
    return {"same": {**base, "trust": same_trust, "low": low}, "half": {**base, "trust": half_trust},
            "common_only": {**base, "trust": gen_trust, "ask": gen_ask}}


class TestPreregistrationRules(unittest.TestCase):
    def test_pilot_only_adds_assumptions(self):
        # 3장: 공통 이유 30~60% 밖이면 그 값을 더하고, 안 써본 비율이 10%p 넘게 다르면 공통 이유 가정마다 더한다
        out = sim.pilot_assumptions(BASE, {"common": 0.71, "p_nouse": 0.5, "p_two": 0.45})
        self.assertEqual(out[:2], BASE)  # 지금 가정은 그대로
        self.assertEqual([(a["common"], round(a["p_nouse"], 3), a["p_two"]) for a in out[2:]],
                         [(0.71, 0.333, 0.4), (0.6, 0.5, 0.4), (0.3, 0.5, 0.4), (0.71, 0.5, 0.4)])
        # 공통 이유가 범위 안이고 안 써본 비율 차이가 10%p 이하면 그 값으로는 안 더한다. 이유 2개 비율만 다르면 그것만 더한다
        out = sim.pilot_assumptions(BASE, {"common": 0.45, "p_nouse": 0.40, "p_two": 0.25})
        self.assertEqual([(a["common"], a["p_two"]) for a in out[2:]], [(0.6, 0.25), (0.3, 0.25)])
        self.assertEqual(sim.pilot_assumptions(BASE, {"common": 0.5}), BASE)

    def test_check_is_point_estimate_with_inclusive_bounds(self):
        self.assertTrue(sim.check(kinds(0.8, 0.1, 0.05, 0.05), CRIT)["pass"])
        self.assertFalse(sim.check(kinds(0.799, 0.1, 0.05, 0.05), CRIT)["pass"])
        self.assertFalse(sim.check(kinds(0.9, 0.101), CRIT)["pass"])
        self.assertFalse(sim.check(kinds(0.9, 0.0, 0.051), CRIT)["pass"])
        self.assertFalse(sim.check(kinds(0.9, 0.0, 0.0, 0.051), CRIT)["pass"])

    def test_low_is_worst_of_three_ai_scenarios(self):
        # 사전등록 v1 1장(11/8 변경 기록): 자료 부족은 세 AI 시나리오 중 가장 큰 값. 순위 뒤집힌 AI는 안 센다
        k = kinds(0.9)
        k["half"]["low"] = 0.051
        out = sim.check(k, CRIT)
        self.assertEqual((out["low"], out["low_same"], out["pass_v1"]), (0.051, 0.0, False))
        k = kinds(0.9)
        k["common_only"]["low"] = 0.05
        self.assertTrue(sim.check(k, CRIT)["pass_v1"])
        k = kinds(0.9)
        k["reversed"] = {"trust": 0.0, "reference": 0.0, "ask": 0.0, "low": 0.3, "na": 0.0}
        self.assertTrue(sim.check(k, {**CRIT, "max_reversed_trust": 0.1})["pass"])

    def test_criteria_files_match_preregistration(self):
        for name in ("criteria_v1.json", "criteria_v1.1.json"):
            crit = json.loads((REPO / "experiments/sample_size_sim" / name).read_text(encoding="utf-8"))
            self.assertEqual({k: crit[k] for k in CRIT}, CRIT, name)

    def test_minimum_n_must_hold_for_all_larger_sizes(self):
        self.assertEqual(sim.minimum_n([(10, False), (15, True), (20, False), (30, True), (45, True)]), 30)
        self.assertEqual(sim.minimum_n([(10, True), (15, True)]), 10)
        self.assertIsNone(sim.minimum_n([(10, True), (15, False)]))

    def test_select_rule_follows_section_2(self):
        t = {"main": {"single_min": 90, "merged_min": 60, "generic_ask": 1.0},
             "fixed_70": {"single_min": 45, "merged_min": 60, "generic_ask": 0.3},
             "gate_fixed_70": {"single_min": 45, "merged_min": 60, "generic_ask": 0.9},
             "fixed_80": {"single_min": None, "merged_min": 50, "generic_ask": 0.0}}
        s = sim.select_rule(t)
        self.assertEqual((s["rule"], s["service_judgment"]), ("gate_fixed_70", True))  # 동점이면 물어볼 것 비율이 큰 쪽
        t["fixed_70"]["merged_min"] = 50
        self.assertEqual(sim.select_rule(t)["rule"], "fixed_70")  # 다음은 합친 구성 최소 인원
        only_merged = {"main": {"single_min": None, "merged_min": 80, "generic_ask": 0.0},
                       "fixed_70": {"single_min": None, "merged_min": 60, "generic_ask": 0.0}}
        s = sim.select_rule(only_merged)
        self.assertEqual((s["rule"], s["service_judgment"]), ("fixed_70", False))
        none = {"main": {"single_min": None, "merged_min": None, "generic_ask": 0.0}}
        self.assertEqual(sim.select_rule(none)["rule"], "main")

    def test_merged_config_splits_services(self):
        human, ai = sim.make_data(20, BASE[0], "same", random.Random(1), "merged")
        self.assertEqual({r["service"] for r in human}, {"s1", "s2"})
        self.assertEqual(len({r["respondent_id"] for r in human if r["service"] == "s1"})
                         + len({r["respondent_id"] for r in human if r["service"] == "s2"}),
                         len({r["respondent_id"] for r in human}))
        # AI는 두 서비스분이고 페르소나 번호가 같다. 계산기가 서비스까지 나눠 센다
        per_service = {s: {r["persona_id"] for r in ai if r["service"] == s} for s in ("s1", "s2")}
        self.assertEqual(per_service["s1"], per_service["s2"])
        self.assertEqual(len(per_service["s1"]), sim.AI_PERSONAS_PER_PLATFORM)


class TestPreregistrationV11(unittest.TestCase):
    """사전등록 v1.1 추가안: 순위 뒤집힌 AI, 두 단계 고르기, 커버리지용 실제 확률."""

    def test_reversed_ai_keeps_codes_and_reverses_order(self):
        h = sim.human_dist(0, 0.6)
        r = sim.ai_dist(0, 0.6, "reversed")
        self.assertEqual(set(r), set(h))  # 이유 종류는 같다
        self.assertAlmostEqual(sum(r.values()), sum(h.values()))
        top, bottom = max(h, key=h.get), min(h, key=h.get)
        self.assertEqual((r[top], r[bottom]), (h[bottom], h[top]))  # 1등과 꼴찌 비율이 바뀐다

    def test_incidence_probs(self):
        self.assertEqual(sim.incidence_probs({"a": 3, "b": 1}, 0.0), {"a": 0.75, "b": 0.25})
        both = sim.incidence_probs({"a": 1, "b": 1}, 1.0)  # 늘 서로 다른 2개면 둘 다 말한다
        self.assertAlmostEqual(both["a"], 1.0)
        # a 0.5, b 0.3, c 0.2에서 2개일 때 a: 0.5 + 0.3*0.5/0.7 + 0.2*0.5/0.8
        p = sim.incidence_probs({"a": 0.5, "b": 0.3, "c": 0.2}, 1.0)
        self.assertAlmostEqual(p["a"], 0.5 + 0.3 * 0.5 / 0.7 + 0.2 * 0.5 / 0.8)
        self.assertAlmostEqual(sum(p.values()), 2.0)

    def test_check_with_reversed_ai(self):
        crit = {**CRIT, "max_reversed_trust": 0.1}
        k = kinds()
        k["reversed"] = {**k["half"], "trust": 0.1}
        out = sim.check(k, crit)
        self.assertTrue(out["pass"] and out["pass_v1"])
        k["reversed"]["trust"] = 0.101
        out = sim.check(k, crit)
        self.assertEqual((out["pass_v1"], out["pass"]), (True, False))  # v1 기준만 넘음
        self.assertTrue(sim.check(kinds(), crit)["pass"])  # 뒤집힌 AI가 없으면 v1 기준만 본다

    def test_select_tiered(self):
        t1 = {"main": {"single_min": None, "merged_min": None, "generic_ask": 0.0},
              "main_dist": {"single_min": 90, "merged_min": 60, "generic_ask": 0.9},
              "main_rank": {"single_min": None, "merged_min": 50, "generic_ask": 0.9}}
        v1 = {"main": {"single_min": 45, "merged_min": 40, "generic_ask": 1.0},
              "main_dist": {"single_min": 60, "merged_min": 50, "generic_ask": 1.0},
              "main_rank": {"single_min": None, "merged_min": 50, "generic_ask": 1.0}}
        s = sim.select_tiered(t1, v1)
        # 1단계: 합친 구성 60명 이하인 main_dist, main_rank 중 두 구성 모두 넘는 main_dist
        self.assertEqual((s["tier"], s["rule"], s["service_judgment"]), (1, "main_dist", True))
        t1["main_dist"]["merged_min"] = 80  # 목표 합 60명을 넘으면 1단계에서 빠진다
        s = sim.select_tiered(t1, v1)
        self.assertEqual((s["tier"], s["rule"], s["service_judgment"]), (1, "main_rank", False))
        t1["main_rank"]["merged_min"] = None
        s = sim.select_tiered(t1, v1)
        self.assertEqual((s["tier"], s["rule"]), (2, "main"))  # 2단계: v1 기준 넷으로 고른다
        self.assertIn("한계", s["case"])

    def test_simulation_rules_include_new_candidates(self):
        r = sim.sim_rules(REPO / "configs/rules.draft.json", 10, "single")
        names = ["main"] + [x["name"] for x in r["sensitivity"]]
        self.assertEqual(sorted(names), sorted(sim.RULE_ORDER))
        self.assertEqual(r["human_equivalent"], {"draws": 0})

    def test_ladder_candidate_in_simulation(self):
        # 사전등록 v1.2 추가안: 가짜 뽑기 500번(다시 뽑기가 더 적으면 그 수), 보고용 사다리는 끈다
        self.assertEqual(sim.sim_rules(REPO / "configs/rules.draft.json", 1000, "single")["ladder"],
                         {"decoy_draws": 500, "rungs": False})
        r = sim.sim_rules(REPO / "configs/rules.draft.json", 200, "single")
        self.assertEqual(r["ladder"]["decoy_draws"], 200)
        self.assertEqual(sim.RULE_ORDER[-1], "ladder_50")  # 동점 순서 맨 뒤
        self.assertEqual({c for c, scope in sim.CODEBOOK.items() if scope == "common"}, set(sim.COMMON))
        job = ("single", "common60", {"common": 0.6, "p_nouse": 1 / 3, "p_two": 0.4}, "same", 30, "t|0",
               {**r, "resamples": 60, "ladder": {"decoy_draws": 60, "rungs": False}})
        _, verdicts, _, _, _ = sim.run_job(job)
        self.assertEqual(sum(verdicts["ladder_50"].values()), 4)  # 칸 넷 모두 판정이 붙는다
        self.assertNotIn(sim.sr.NA, verdicts["ladder_50"])  # 코드북을 넘겨서 계산 불가가 아니다


if __name__ == "__main__":
    unittest.main()

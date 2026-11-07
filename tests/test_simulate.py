"""experiments/sample_size_sim/simulate.py 오프라인 테스트. 사전등록 v1 규칙을 코드로 옮긴 부분만 본다.

리포 루트에서:
    python -m unittest tests.test_simulate -v
"""

import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments" / "sample_size_sim"))

import simulate as sim  # noqa: E402

BASE = [{"name": "common0.60", "common": 0.6, "p_nouse": 1 / 3, "p_two": 0.4},
        {"name": "common0.30", "common": 0.3, "p_nouse": 1 / 3, "p_two": 0.4}]
CRIT = {"min_same_trust": 0.8, "max_half_trust": 0.1, "max_common_only_trust": 0.05, "max_low_same": 0.05}


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


if __name__ == "__main__":
    unittest.main()

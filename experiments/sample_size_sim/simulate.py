"""사람 수 시뮬레이션: 서비스당 응답자가 몇 명이면 판정이 믿을 만하게 나오나.

사람 응답을 모으기 전에 가짜 데이터로 판정 계산기(scripts/score_reasons.py)를 그대로 돌려 본다.
실제 응답은 쓰지 않고 외부 API도 부르지 않는다.

가정 (README에 같이 적는다)
- 한 서비스, 기능 4개, 안 쓸 이유(nouse) 칸만 본다. 앱·웹을 합친 서비스 단위 판정 (11/6 D4)
- 응답자마다 기능별로 1/3 확률로 "안 써봤다" (폼 B 초안의 가정). 안 써본 기능에 이유 1~2개
- 응답자 70%가 앱, 30%가 웹. AI는 조건 2, 플랫폼마다 페르소나 10명, 1회씩
- 이유는 공통 코드 4개(C1~C4)와 기능 코드 4개. 기능마다 가장 많이 나오는 공통 이유가 다르다
- 사람 이유 분포 두 가지: 공통 이유가 60%인 경우, 30%인 경우
- AI 세 가지: 사람과 같은 분포로 답함 / 공통 이유만 말함 / 절반은 사람 분포, 절반은 사람이 안 말하는 이유

재는 것 (응답자 N명마다, 본 규칙과 민감도 규칙 각각)
- 판정 비율: 믿고 써도 됨 / 참고용 / 사람에게 물어볼 것 / 자료 부족
- 나와야 할 판정: 사람과 같은 분포 AI는 "믿고 써도 됨", 공통 이유만 말하는 AI는 "사람에게 물어볼 것",
  절반만 맞는 AI는 "참고용". 그 판정이 나온 비율
- 잘못된 믿음: 사람과 같은 분포가 아닌 AI가 "믿고 써도 됨"을 받은 비율
- 사람끼리 통과율 구간 폭
- 처음에는 응답자 600명으로 돌린 판정을 기준으로 삼았는데, AI 페르소나(20명)보다 사람 절반이 훨씬 많아져
  크기가 안 맞아서 기준이 흔들렸다. 그래서 시나리오마다 나와야 할 판정으로 바꿨다

    python experiments/sample_size_sim/simulate.py --reps 100 --out experiments/sample_size_sim/result.json
"""

import argparse
import copy
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import score_reasons as sr  # noqa: E402

FEATURES = ["F1", "F2", "F3", "F4"]
COMMON = ["C1", "C2", "C3", "C4"]
GROUP_WEIGHTS = [0.4, 0.3, 0.2, 0.1]  # 묶음 안에서 많이 나오는 순서
SHAPES = {"common60": 0.6, "common30": 0.3}  # 사람 이유 중 공통 이유 비율
AI_KINDS = ("same", "common_only", "half")
EXPECTED = {"same": sr.TRUST, "common_only": sr.ASK, "half": sr.REF}
P_NOUSE = 1 / 3
P_TWO_REASONS = 0.4
P_APP = 0.7
AI_PERSONAS_PER_PLATFORM = 10


def human_dist(feature_index: int, common_share: float) -> dict:
    rot = GROUP_WEIGHTS[feature_index:] + GROUP_WEIGHTS[:feature_index]  # 기능마다 1등 공통 이유가 다르다
    f = FEATURES[feature_index]
    dist = {c: w * common_share for c, w in zip(COMMON, rot)}
    dist.update({f"{f}-{i + 1}": w * (1 - common_share) for i, w in enumerate(GROUP_WEIGHTS)})
    return dist


def ai_dist(feature_index: int, common_share: float, kind: str) -> dict:
    h = human_dist(feature_index, common_share)
    if kind == "same":
        return h
    if kind == "common_only":
        total = sum(h[c] for c in COMMON)
        return {c: h[c] / total for c in COMMON}
    f = FEATURES[feature_index]  # half: 절반은 사람이 안 말하는 이유
    out = {k: v * 0.5 for k, v in h.items()}
    out.update({f"{f}-AI{i + 1}": 0.5 / 4 for i in range(4)})
    return out


def draw_reasons(dist: dict, rng: random.Random) -> list:
    k = 2 if rng.random() < P_TWO_REASONS else 1
    codes, weights = list(dist), list(dist.values())
    out = []
    while len(out) < k:
        c = rng.choices(codes, weights)[0]
        if c not in out:
            out.append(c)
    return out


def make_data(n: int, shape: str, ai_kind: str, rng: random.Random) -> tuple:
    share = SHAPES[shape]
    human, ai = [], []
    for r in range(n):
        plat = "app" if rng.random() < P_APP else "web"
        for j, f in enumerate(FEATURES):
            if rng.random() < P_NOUSE:
                for c in draw_reasons(human_dist(j, share), rng):
                    human.append({"respondent_id": f"R{r:03d}", "service": "sim", "platform": plat,
                                  "feature_id": f, "kind": "nouse", "code": c, "order": str(r)})
    for plat in ("app", "web"):
        for p in range(AI_PERSONAS_PER_PLATFORM):
            run_id = f"{plat}-P{p:02d}"
            for j, f in enumerate(FEATURES):
                for c in draw_reasons(ai_dist(j, share, ai_kind), rng):
                    ai.append({"item_id": f"{run_id}-{f}-{c}", "run_id": run_id, "service": "sim",
                               "platform": plat, "condition": 2, "persona_id": f"P{p:02d}", "repeat": "1",
                               "feature_id": f, "kind": "nouse", "code": c})
    return human, ai


def sim_rules(resamples: int) -> dict:
    rules = copy.deepcopy(json.loads((ROOT / "configs/rules.draft.json").read_text(encoding="utf-8")))
    rules["resamples"] = resamples
    # 안정 인원은 판정에 안 쓰고 오래 걸려서 끈다 (시작 인원과 전체 인원만 잼)
    rules["stability"] = {**rules["stability"], "step": 10 ** 6}
    rules["platform_reference"] = False
    return rules


def run_once(n: int, shape: str, ai_kind: str, seed: str, rules: dict) -> list:
    rng = random.Random(seed)
    human, ai = make_data(n, shape, ai_kind, rng)
    res = sr.score(human, ai, {**rules, "seed": seed})
    out = []
    for c in res["cells"]:
        hi = sr.interval(c["draws"]["human_precision"], rules["level"])
        out.append({"feature": c["feature_id"], "n_cell": c["n_humans"],
                    "verdicts": {"main": c["verdict"], **c["sensitivity"]},
                    "human_width": (hi[1] - hi[0]) if hi else None})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="사람 수 시뮬레이션 (가짜 데이터)")
    ap.add_argument("--sizes", default="10,15,20,30,45,60,90", help="서비스당 응답자 수")
    ap.add_argument("--reps", type=int, default=100, help="응답자 수마다 가짜 데이터를 만드는 횟수")
    ap.add_argument("--resamples", type=int, default=200, help="계산기 다시 뽑기 횟수 (본 규칙은 1,000)")
    ap.add_argument("--seed", default="20261106")
    ap.add_argument("--out", default="experiments/sample_size_sim/result.json")
    args = ap.parse_args(argv)
    sizes = [int(x) for x in args.sizes.split(",")]
    rules = sim_rules(args.resamples)
    started = time.time()
    result = {"assumptions": {"features": len(FEATURES), "p_nouse": P_NOUSE, "p_two_reasons": P_TWO_REASONS,
                              "p_app": P_APP, "ai_personas_per_platform": AI_PERSONAS_PER_PLATFORM,
                              "shapes": SHAPES, "ai_kinds": list(AI_KINDS)},
              "expected": EXPECTED,
              "settings": {"sizes": sizes, "reps": args.reps, "resamples": args.resamples, "seed": args.seed,
                           "rules_file": "configs/rules.draft.json", "min_humans": rules["min_humans"],
                           "level": rules["level"]},
              "scenarios": []}
    rule_names = ["main"] + [a["name"] for a in rules["sensitivity"]]
    for shape in SHAPES:
        for kind in AI_KINDS:
            rows = []
            for n in sizes:
                cells = []
                for i in range(args.reps):
                    cells += run_once(n, shape, kind, f"{args.seed}|{n}|{shape}|{kind}|{i}", rules)
                total = len(cells)
                widths = [c["human_width"] for c in cells
                          if c["human_width"] is not None and c["verdicts"]["main"] != sr.LOW]
                n_cells = sorted(c["n_cell"] for c in cells)
                by_rule = {}
                for name in rule_names:
                    v = Counter(c["verdicts"][name] for c in cells)
                    by_rule[name] = {"trust": round(v[sr.TRUST] / total, 3), "reference": round(v[sr.REF] / total, 3),
                                     "ask": round(v[sr.ASK] / total, 3), "low": round(v[sr.LOW] / total, 3),
                                     "expected": round(v[EXPECTED[kind]] / total, 3),
                                     "false_trust": round(v[sr.TRUST] / total, 3) if kind != "same" else 0.0}
                rows.append({"n": n, "cells": total, "median_n_cell": n_cells[len(n_cells) // 2],
                             "human_width_mean": round(sum(widths) / len(widths), 3) if widths else None,
                             "rules": by_rule})
            result["scenarios"].append({"shape": shape, "ai": kind, "expected": EXPECTED[kind], "rows": rows})
            print(f"[{shape} / AI {kind}] 나와야 할 판정: {EXPECTED[kind]}", flush=True)
            for r in rows:
                m = r["rules"]["main"]
                print(f"  N={r['n']:>3} 칸 중앙값 {r['median_n_cell']:>3}명  믿음 {m['trust']:.2f}  참고 {m['reference']:.2f}  "
                      f"물어봄 {m['ask']:.2f}  부족 {m['low']:.2f}  나와야 할 판정 {m['expected']:.2f}  "
                      f"구간 폭 {r['human_width_mean']}", flush=True)
    result["elapsed_sec"] = round(time.time() - started, 1)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기록: {args.out} ({result['elapsed_sec']}초)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

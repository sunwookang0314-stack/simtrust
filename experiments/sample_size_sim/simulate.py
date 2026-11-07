"""사람 수 시뮬레이션: 서비스당 응답자가 몇 명이면 판정이 믿을 만하게 나오나.

사람 응답을 모으기 전에 가짜 데이터로 판정 계산기(scripts/score_reasons.py)를 그대로 돌려 본다.
실제 응답은 쓰지 않고 외부 API도 부르지 않는다.

먼저 기준을 정하고(criteria.draft.json), 그 기준을 넘는 최소 인원을 찾는다 (11/8 강선우 제안).
- 기준 A: 사람과 다르게 답하는 AI(반만 맞는 AI, 공통 이유만 말하는 AI)가 "믿고 써도 됨"을 받는 비율 상한
- 기준 B: 사람과 같은 분포로 답하는 AI가 "믿고 써도 됨"을 받는 비율 하한
- 기준 C: 자료 부족 칸 비율 상한
- 최소 인원은 "이 인원부터 시험한 더 큰 인원에서도 계속 기준을 넘는" 가장 작은 인원이다

가정 (값을 바꿔 가며 돌릴 수 있다. 파일럿 응답이 나오면 그 값을 넣는다)
- 한 판정 단위(서비스 하나, 또는 합친 두 서비스), 기능 4개, 안 쓸 이유(nouse) 칸만 본다. 앱·웹을 합친다 (11/6 D4)
- 응답자마다 기능별로 p_nouse 확률로 "안 써봤다". 안 써본 기능에 이유 1~2개
- 이유는 공통 코드 4개(C1~C4)와 기능 코드 4개. 공통 이유 비율은 common. 서술이 적으면 이 비율이 커진다
- 응답자 70%가 앱, 30%가 웹. AI는 조건 2, 플랫폼마다 페르소나 10명, 1회씩

    python experiments/sample_size_sim/simulate.py --p-nouse 0.25,0.333,0.5 --common 0.3,0.6,0.8
"""

import argparse
import copy
import json
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import score_reasons as sr  # noqa: E402

FEATURES = ["F1", "F2", "F3", "F4"]
COMMON = ["C1", "C2", "C3", "C4"]
GROUP_WEIGHTS = [0.4, 0.3, 0.2, 0.1]  # 묶음 안에서 많이 나오는 순서
SHAPES = {"common60": 0.6, "common30": 0.3}  # 데모 견본(experiments/demo_sample)이 쓰는 이름
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


def make_data(n: int, share: float, ai_kind: str, rng: random.Random, p_nouse: float = P_NOUSE) -> tuple:
    human, ai = [], []
    for r in range(n):
        plat = "app" if rng.random() < P_APP else "web"
        for j, f in enumerate(FEATURES):
            if rng.random() < p_nouse:
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


def run_once(job: tuple) -> tuple:
    """job = (p_nouse, common, ai_kind, n, seed, rules). 반환: (job 키, 칸마다 판정과 구간 폭)"""
    p_nouse, share, kind, n, seed, rules = job
    rng = random.Random(seed)
    human, ai = make_data(n, share, kind, rng, p_nouse)
    res = sr.score(human, ai, {**rules, "seed": seed})
    cells = []
    for c in res["cells"]:
        hi = sr.interval(c["draws"]["human_precision"], rules["level"])
        cells.append({"n_cell": c["n_humans"], "verdicts": {"main": c["verdict"], **c["sensitivity"]},
                      "human_width": (hi[1] - hi[0]) if hi else None})
    return (p_nouse, share, kind, n), cells


def summarize_cells(cells: list, kind: str, rule_names: list) -> dict:
    total = len(cells)
    widths = [c["human_width"] for c in cells if c["human_width"] is not None and c["verdicts"]["main"] != sr.LOW]
    n_cells = sorted(c["n_cell"] for c in cells)
    by_rule = {}
    for name in rule_names:
        v = Counter(c["verdicts"][name] for c in cells)
        by_rule[name] = {"trust": round(v[sr.TRUST] / total, 3), "reference": round(v[sr.REF] / total, 3),
                         "ask": round(v[sr.ASK] / total, 3), "low": round(v[sr.LOW] / total, 3),
                         "expected": round(v[EXPECTED[kind]] / total, 3)}
    return {"cells": total, "median_n_cell": n_cells[len(n_cells) // 2],
            "human_width_mean": round(sum(widths) / len(widths), 3) if widths else None, "rules": by_rule}


def check(rows: dict, n: int, rule: str, crit: dict) -> dict:
    """한 인원에서 기준 A·B·C(와 D)를 넘는지. rows[kind][n]은 summarize_cells 결과."""
    r = {k: rows[k][n]["rules"][rule] for k in AI_KINDS}
    false_trust = max(r["half"]["trust"], r["common_only"]["trust"])
    out = {"false_trust": false_trust, "true_trust": r["same"]["trust"],
           "low": max(x["low"] for x in r.values()), "generic_ask": r["common_only"]["ask"]}
    out["pass"] = (false_trust <= crit["max_false_trust"] and out["true_trust"] >= crit["min_true_trust"]
                   and out["low"] <= crit["max_low"]
                   and (crit.get("min_generic_ask") is None or out["generic_ask"] >= crit["min_generic_ask"]))
    return out


def minimum_n(checks: list) -> int:
    """이 인원부터 시험한 더 큰 인원에서도 계속 기준을 넘는 가장 작은 인원. 없으면 None."""
    best = None
    for n, c in reversed(checks):
        if not c["pass"]:
            break
        best = n
    return best


def floats(text: str) -> list:
    return [round(float(x), 4) for x in text.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="사람 수 시뮬레이션 (가짜 데이터)")
    ap.add_argument("--sizes", default="15,20,30,45,60,90,120", help="판정 단위 하나의 응답자 수")
    ap.add_argument("--p-nouse", default="0.25,0.333,0.5", help="기능을 안 써본 비율. 쉼표로 여러 값")
    ap.add_argument("--common", default="0.3,0.6,0.8", help="사람 이유 중 공통 이유 비율. 쉼표로 여러 값")
    ap.add_argument("--criteria", default="experiments/sample_size_sim/criteria.draft.json")
    ap.add_argument("--reps", type=int, default=50, help="조건마다 가짜 데이터를 만드는 횟수")
    ap.add_argument("--resamples", type=int, default=200, help="계산기 다시 뽑기 횟수 (본 규칙은 1,000)")
    ap.add_argument("--workers", type=int, default=4, help="동시에 돌릴 프로세스 수")
    ap.add_argument("--seed", default="20261108")
    ap.add_argument("--out", default="experiments/sample_size_sim/result.json")
    args = ap.parse_args(argv)
    sizes, p_list, c_list = sorted(int(x) for x in args.sizes.split(",")), floats(args.p_nouse), floats(args.common)
    crit = json.loads((ROOT / args.criteria).read_text(encoding="utf-8"))
    rules = sim_rules(args.resamples)
    rule_names = ["main"] + [a["name"] for a in rules["sensitivity"]]
    jobs = [(p, c, k, n, f"{args.seed}|{p}|{c}|{k}|{n}|{i}", rules)
            for p in p_list for c in c_list for k in AI_KINDS for n in sizes for i in range(args.reps)]
    started = time.time()
    gathered = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for key, cells in pool.map(run_once, jobs, chunksize=8):
            gathered.setdefault(key, []).extend(cells)
    scenarios, table = [], []
    for p in p_list:
        for c in c_list:
            rows = {k: {n: summarize_cells(gathered[(p, c, k, n)], k, rule_names) for n in sizes} for k in AI_KINDS}
            per_rule = {}
            for rule in rule_names:
                checks = [(n, check(rows, n, rule, crit)) for n in sizes]
                per_rule[rule] = {"minimum_n": minimum_n(checks), "checks": {str(n): ck for n, ck in checks}}
                table.append({"p_nouse": p, "common": c, "rule": rule, "minimum_n": per_rule[rule]["minimum_n"]})
            scenarios.append({"p_nouse": p, "common": c,
                              "rows": {k: {str(n): v for n, v in rows[k].items()} for k in AI_KINDS},
                              "rules": per_rule})
    result = {"criteria": crit, "criteria_file": args.criteria,
              "assumptions": {"features": len(FEATURES), "p_two_reasons": P_TWO_REASONS, "p_app": P_APP,
                              "ai_personas_per_platform": AI_PERSONAS_PER_PLATFORM, "p_nouse": p_list,
                              "common": c_list, "ai_kinds": list(AI_KINDS)},
              "expected": EXPECTED,
              "settings": {"sizes": sizes, "reps": args.reps, "resamples": args.resamples, "seed": args.seed,
                           "rules_file": "configs/rules.draft.json", "min_humans": rules["min_humans"],
                           "level": rules["level"]},
              "minimum_n": table, "scenarios": scenarios, "elapsed_sec": round(time.time() - started, 1)}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[기준] 잘못 믿음 {crit['max_false_trust']:.0%} 이하, 제대로 믿음 {crit['min_true_trust']:.0%} 이상, "
          f"자료 부족 {crit['max_low']:.0%} 이하"
          + (f", 공통 이유 AI 물어봄 {crit['min_generic_ask']:.0%} 이상" if crit.get("min_generic_ask") else ""))
    print("[최소 인원] 판정 단위 하나당. '없음'은 시험한 최대 인원까지 기준을 못 넘음")
    print("  안 써본 비율 / 공통 이유 | " + " | ".join(rule_names))
    for p in p_list:
        for c in c_list:
            vals = [next(t["minimum_n"] for t in table if t["p_nouse"] == p and t["common"] == c and t["rule"] == r)
                    for r in rule_names]
            print(f"  {p:.2f} / {c:.1f} | " + " | ".join("없음" if v is None else f"{v}명" for v in vals))
    print(f"기록: {args.out} ({result['elapsed_sec']}초)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

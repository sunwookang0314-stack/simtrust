"""사람 수 시뮬레이션 v2 (사전등록 v1과 v1.1·v1.2 추가안, docs/measurement/사전등록_v1.md, 사전등록_v1.1_추가.md,
사전등록_v1.2_추가.md).

가짜 데이터로 판정 계산기(scripts/score_reasons.py)를 그대로 돌려서, 판정 규칙마다 합격 기준(1장)을 넘는 최소 인원을
찾고 2장의 고르는 법대로 규칙을 고른다. 실제 응답은 쓰지 않고 외부 API도 부르지 않는다.

- 합격 기준 (criteria_v1.1.json): 가정마다 아래를 모두 넘어야 그 인원에서 합격이다
  사람 같은 AI를 "믿고 써도 됨" 80% 이상, 반만 맞는 AI 10% 이하, 공통 이유만 말하는 AI 5% 이하,
  자료 부족 칸 5% 이하(사람 같은 AI 시나리오 칸). 점추정 그대로 댄다 (여기까지 v1 1장)
  순위 뒤집힌 AI(이유 종류는 사람과 같고 많이 말하는 순서만 반대) 10% 이하 (v1.1 추가)
- 고르는 법 (v1.1 추가): 1단계는 다섯 기준을 다 넘고 합친 구성 최소 인원이 목표 합 60명 이하인 규칙 중에서
  2장 고르는 법으로 고른다. 그런 규칙이 없으면 2단계로 v1 기준 넷만 보고 2장 고르는 법 그대로 고른다
- 최소 인원: 그 인원과 그보다 큰 시뮬레이션 인원 전부에서 합격하는 가장 작은 인원
- 구성 두 가지 (사전등록 2장)
  single: 서비스 하나. 인원 10, 15, 20, 30, 35, 40, 45, 60, 90명
  merged: 두 서비스 합친 것. 합 인원 30, 40, 50, 60, 80, 90, 120명을 반씩 나누고 서비스를 빼고 판정한다.
          두 서비스 사람 이유 분포는 같다. AI는 두 서비스분이고 페르소나 번호는 같게 둔다(계산기가 서비스까지 나눠 센다)
- 가정 (assumptions_v1.json): 공통 이유 60%·30%, 안 써본 비율 3분의 1, 이유 2개 40%. 파일럿 값은 --pilot으로 주면
  사전등록 3장 규칙대로 가정을 더한다(빼지 않는다)
- 반복 500번, 시드 20261108. 다시 뽑기는 가정이 4개 이하면 1,000번, 넘으면 200번. 나머지 규칙 값은 규칙 파일 그대로
  (순열 검정 횟수도 다시 뽑기 횟수와 같다. 사람 환산 인원은 판정에 안 써서 끈다)
- 커버리지(v1.1 추가, 판정에 안 씀): 사람 같은 AI 시나리오에서 칸마다 추정 커버리지(Chao 외 2014)와 실제 커버리지,
  90%까지 필요한 전체 응답자 수 추정을 인원별로 모은다
- 코드 시험 실행은 반복 10번 이하로만 하고 그 결과는 고르는 데 쓰지 않는다 (--reps 10 --out runs/...)

    python experiments/sample_size_sim/simulate.py --out experiments/sample_size_sim/result_v2.json
    python experiments/sample_size_sim/simulate.py --pilot "p_nouse=0.42,common=0.71,p_two=0.35" --out ...
"""

import argparse
import copy
import hashlib
import json
import random
import subprocess
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
AI_KINDS = ("same", "common_only", "half", "reversed")
LOW_KINDS = ("same", "common_only", "half")  # 자료 부족을 세는 AI. 사전등록 v1 1장(11/8 변경 기록)의 세 AI 시나리오
P_NOUSE = 1 / 3
P_TWO_REASONS = 0.4
P_APP = 0.7
AI_PERSONAS_PER_PLATFORM = 10  # 본실험: 서비스·플랫폼·조건마다 페르소나 10명. 반복 3회는 계산기가 한 사람으로 묶는다
SIZES = {"single": [10, 15, 20, 30, 35, 40, 45, 60, 90], "merged": [30, 40, 50, 60, 80, 90, 120]}
RULE_ORDER = ["main", "anchors_90", "gate_fixed_70", "fixed_80", "fixed_70", "fixed_60",
              "main_dist", "main_rank", "ladder_50"]  # 사전등록 2장 동점 순서, v1.1·v1.2 추가 후보는 뒤에 붙인다
# 가짜 AI 사다리(v1.2)의 공통 이유만 가짜를 만들 때 쓰는 코드북. 이 시뮬레이션의 공통 코드는 COMMON 넷이다
CODEBOOK = {c: "common" for c in COMMON}
TARGET_TOTAL = 60  # 사전등록 5장 1차 목표 (두 서비스 합). v1.1 1단계는 합친 구성 최소 인원이 이 안이어야 한다


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
    if kind == "reversed":
        # 이유 종류는 사람과 같고, 사람 쪽 많이 말하는 순서를 거꾸로 해서 비율을 바꿔 단다 (같은 값은 코드 순서)
        ranked = sorted(h, key=lambda c: (-h[c], c))
        weights = [h[c] for c in ranked]
        return dict(zip(ranked, reversed(weights)))
    f = FEATURES[feature_index]  # half: 절반은 사람이 안 말하는 이유
    out = {k: v * 0.5 for k, v in h.items()}
    out.update({f"{f}-AI{i + 1}": 0.5 / 4 for i in range(4)})
    return out


def incidence_probs(dist: dict, p_two: float) -> dict:
    """한 사람이 그 코드를 말할 확률. draw_reasons와 같은 뽑기다: 1개, 또는 p_two 확률로 서로 다른 2개.
    2개일 때 c가 들어갈 확률 = w_c + (c 아닌 d마다) w_d x w_c / (1 - w_d)."""
    total = sum(dist.values())
    w = {c: v / total for c, v in dist.items()}
    return {c: wc + p_two * sum(wd * wc / (1 - wd) for d, wd in w.items() if d != c) for c, wc in w.items()}


def draw_reasons(dist: dict, rng: random.Random, p_two: float = P_TWO_REASONS) -> list:
    k = 2 if rng.random() < p_two else 1
    codes, weights = list(dist), list(dist.values())
    out = []
    while len(out) < k:
        c = rng.choices(codes, weights)[0]
        if c not in out:
            out.append(c)
    return out


def make_data(n: int, a: dict, ai_kind: str, rng: random.Random, config: str = "single") -> tuple:
    """a = 가정 {common, p_nouse, p_two}. merged면 사람을 두 서비스에 반씩 나누고 AI도 두 서비스분을 만든다."""
    services = ["s1", "s2"] if config == "merged" else ["s1"]
    human, ai = [], []
    for r in range(n):
        service = services[r * len(services) // n]
        plat = "app" if rng.random() < P_APP else "web"
        for j, f in enumerate(FEATURES):
            if rng.random() < a["p_nouse"]:
                for c in draw_reasons(human_dist(j, a["common"]), rng, a["p_two"]):
                    human.append({"respondent_id": f"R{r:03d}", "service": service, "platform": plat,
                                  "feature_id": f, "kind": "nouse", "code": c, "order": str(r)})
    for service in services:
        for plat in ("app", "web"):
            for p in range(AI_PERSONAS_PER_PLATFORM):
                run_id = f"{service}-{plat}-P{p:02d}"
                for j, f in enumerate(FEATURES):
                    for c in draw_reasons(ai_dist(j, a["common"], ai_kind), rng, a["p_two"]):
                        ai.append({"item_id": f"{run_id}-{f}-{c}", "run_id": run_id, "service": service,
                                   "platform": plat, "condition": 2, "persona_id": f"P{p:02d}", "repeat": "1",
                                   "feature_id": f, "kind": "nouse", "code": c})
    return human, ai


def sim_rules(path: Path, resamples: int, config: str) -> dict:
    rules = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
    rules["resamples"] = resamples
    # 안정 인원은 판정에 안 쓰고 오래 걸려서 끈다 (시작 인원과 전체 인원만 잼). 사전등록 7장에 한계로 적힘
    rules["stability"] = {**rules["stability"], "step": 10 ** 6}
    rules["platform_reference"] = False
    rules["human_equivalent"] = {"draws": 0}  # 판정에 안 쓰고 오래 걸린다
    # 가짜 뽑기는 500번, 다시 뽑기가 그보다 적으면(가정이 4개를 넘을 때 200번) 그 수에 맞춘다 (사전등록 v1.2 추가안)
    lad = rules.get("ladder", {"decoy_draws": 500})
    # 틀린 비율 사다리 세 단(25·50·75%)은 보고용이라 끈다. 판정에 쓰는 가짜는 그대로 만들어서 판정은 같다
    rules["ladder"] = {**lad, "decoy_draws": min(lad["decoy_draws"], resamples), "rungs": False}
    rules["cell_keys"] = ["feature_id", "kind"] if config == "merged" else ["service", "feature_id", "kind"]
    return rules


def run_job(job: tuple) -> tuple:
    """job = (구성, 가정 이름, 가정, AI 종류, 인원, 시드, 규칙). 반환은 칸 수만 센 작은 묶음이다 (메모리 아끼려고).
    사람 같은 AI 작업에서는 칸마다 (추정 커버리지, 실제 커버리지, 90%까지 필요한 전체 응답자 수)도 돌려준다."""
    config, a_name, a, kind, n, seed, rules = job
    human, ai = make_data(n, a, kind, random.Random(seed), config)
    res = sr.score(human, ai, {**rules, "seed": seed}, CODEBOOK)
    verdicts = {name: Counter() for name in ["main"] + [x["name"] for x in rules["sensitivity"]]}
    widths, n_cells, cov = [], [], []
    for c in res["cells"]:
        if kind == "same" and c.get("coverage"):
            probs = incidence_probs(human_dist(FEATURES.index(c["feature_id"]), a["common"]), a["p_two"])
            seen = {r["code"] for r in c["reasons"] if r["human_count"]} | {m["code"] for m in c["missed"]}
            true = sum(v for k, v in probs.items() if k in seen) / sum(probs.values())
            need = c["coverage"]["need"]
            cov.append((c["coverage"]["estimate"], true,
                        need * n / c["n_humans"] if need is not None else None, c["coverage"]["need_reliable"]))
        verdicts["main"][c["verdict"]] += 1
        for name, v in c["sensitivity"].items():
            verdicts[name][v] += 1
        n_cells.append(c["n_humans"])
        hi = sr.interval(c["draws"]["human_precision"], rules["level"])
        if hi and c["verdict"] != sr.LOW:
            widths.append(hi[1] - hi[0])
    return (config, a_name, kind, n), verdicts, widths, n_cells, cov


def pilot_assumptions(base: list, pilot: dict) -> list:
    """사전등록 3장: 파일럿은 가정을 더하기만 한다.
    공통 이유 비율이 30~60% 밖이면 그 값을 공통 이유 가정으로 더하고, 안 써본 비율이 3분의 1과 10%p 넘게 다르거나
    이유 2개 비율이 40%와 10%p 넘게 다르면 그 값 하나만 바꾼 가정을 공통 이유 가정마다 더한다."""
    out = list(base)
    commons = sorted({a["common"] for a in base}, reverse=True)
    if "common" in pilot and not 0.3 <= pilot["common"] <= 0.6:
        out.append({"name": f"pilot_common{pilot['common']:.2f}", "common": pilot["common"],
                    "p_nouse": P_NOUSE, "p_two": P_TWO_REASONS})
        commons.append(pilot["common"])
    if "p_nouse" in pilot and abs(pilot["p_nouse"] - P_NOUSE) > 0.10:
        out += [{"name": f"common{c:.2f}_nouse{pilot['p_nouse']:.2f}", "common": c, "p_nouse": pilot["p_nouse"],
                 "p_two": P_TWO_REASONS} for c in commons]
    if "p_two" in pilot and abs(pilot["p_two"] - P_TWO_REASONS) > 0.10:
        out += [{"name": f"common{c:.2f}_two{pilot['p_two']:.2f}", "common": c, "p_nouse": P_NOUSE,
                 "p_two": pilot["p_two"]} for c in commons]
    return out


def parse_pilot(text: str) -> dict:
    out = {}
    for part in (text or "").split(","):
        if part.strip():
            k, v = part.split("=", 1)
            if k.strip() not in ("p_nouse", "common", "p_two"):
                raise SystemExit(f"--pilot에 모르는 값: {k}")
            out[k.strip()] = float(v)
    return out


def rates(verdicts: Counter) -> dict:
    total = sum(verdicts.values())
    return {"trust": verdicts[sr.TRUST] / total, "reference": verdicts[sr.REF] / total,
            "ask": verdicts[sr.ASK] / total, "low": verdicts[sr.LOW] / total, "na": verdicts[sr.NA] / total}


def check(by_kind: dict, crit: dict) -> dict:
    """가정 하나, 인원 하나에서 합격 기준. pass_v1은 사전등록 v1 1장 기준 넷, pass는 v1.1에서 더한
    순위 뒤집힌 AI 기준까지 (기준이나 그 AI가 없으면 pass = pass_v1).
    자료 부족은 세 AI 시나리오(LOW_KINDS) 중 가장 큰 값으로 댄다 (사전등록 v1 1장, 11/8 변경 기록)."""
    same, half, gen = by_kind["same"], by_kind["half"], by_kind["common_only"]
    low = max(by_kind[k]["low"] for k in LOW_KINDS)
    out = {"same_trust": same["trust"], "half_trust": half["trust"], "common_only_trust": gen["trust"],
           "low": low, "low_same": same["low"], "common_only_ask": gen["ask"]}
    out["pass_v1"] = (same["trust"] >= crit["min_same_trust"] and half["trust"] <= crit["max_half_trust"]
                      and gen["trust"] <= crit["max_common_only_trust"] and low <= crit["max_low"])
    out["pass"] = out["pass_v1"]
    if "reversed" in by_kind and "max_reversed_trust" in crit:
        out["reversed_trust"] = by_kind["reversed"]["trust"]
        out["pass"] = out["pass_v1"] and out["reversed_trust"] <= crit["max_reversed_trust"]
    return out


def minimum_n(passes: list) -> int:
    """passes = [(인원, 합격)] 작은 인원부터. 그 인원부터 끝까지 합격하는 가장 작은 인원. 없으면 None."""
    best = None
    for n, ok in reversed(passes):
        if not ok:
            break
        best = n
    return best


def select_rule(table: dict) -> dict:
    """사전등록 2장 고르는 법. table[rule] = {single_min, merged_min, generic_ask}."""
    order = {r: i for i, r in enumerate(RULE_ORDER)}
    rules = [r for r in RULE_ORDER if r in table]

    def by_single(r):
        t = table[r]
        return (t["single_min"], t["merged_min"], -t["generic_ask"], order[r])

    both = [r for r in rules if table[r]["single_min"] is not None and table[r]["merged_min"] is not None]
    if both:
        r = min(both, key=by_single)
        return {"rule": r, "case": "두 구성 모두 합격", "service_judgment": True}
    merged_only = [r for r in rules if table[r]["merged_min"] is not None]
    if merged_only:
        r = min(merged_only, key=lambda x: (table[x]["merged_min"], -table[x]["generic_ask"], order[x]))
        return {"rule": r, "case": "합친 구성에서만 합격. 서비스별 판정은 하지 않는다", "service_judgment": False}
    single_only = [r for r in rules if table[r]["single_min"] is not None]
    if single_only:
        r = min(single_only, key=by_single)
        return {"rule": r, "case": "서비스 하나 구성에서만 합격. 합쳐서 낸 판정은 전부 미달로 적는다",
                "service_judgment": True}
    return {"rule": "main", "case": "합격하는 규칙 없음. main을 쓰고 모든 판정 옆에 미달로 적는다",
            "service_judgment": False}


def select_tiered(table: dict, table_v1: dict, target_total: int = TARGET_TOTAL) -> dict:
    """사전등록 v1.1 추가안. table은 다섯 기준(순위 뒤집힌 AI 포함), table_v1은 v1 기준 넷으로 잰 최소 인원.
    1단계: 합친 구성 최소 인원이 목표 합 인원 이하인 규칙만 두고 2장 고르는 법(select_rule)으로 고른다.
    2단계: 그런 규칙이 없으면 v1 기준 넷으로 2장 고르는 법 그대로 고르고, 순위 뒤집힌 AI는 한계로 적는다."""
    ok = {r: t for r, t in table.items() if t["merged_min"] is not None and t["merged_min"] <= target_total}
    if ok:
        sel = select_rule(ok)
        return {**sel, "tier": 1, "case": "1단계(순위 뒤집힌 AI 기준 포함): " + sel["case"]}
    sel = select_rule(table_v1)
    return {**sel, "tier": 2, "case": "2단계(v1 기준 넷): " + sel["case"]
            + f". 순위 뒤집힌 AI를 거르는 규칙이 합 {target_total}명 안에서 없어서 한계로 적는다"}


def min_table(results: dict, rule_names: list, key: str) -> dict:
    """규칙마다 두 구성의 최소 인원과, 서비스 하나 최소 인원 줄에서 공통 이유만 AI '물어볼 것' 비율(가정 중 낮은 쪽)."""
    table = {}
    for rule in rule_names:
        smin = results.get("single", {}).get(rule, {}).get(key)
        mmin = results.get("merged", {}).get(rule, {}).get(key)
        gen = None
        if smin is not None:
            row = next(x for x in results["single"][rule]["rows"] if x["n"] == smin)
            gen = min(v["common_only_ask"] for v in row["by_assumption"].values())
        table[rule] = {"single_min": smin, "merged_min": mmin, "generic_ask": gen if gen is not None else 0.0}
    return table


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "scripts", "experiments/sample_size_sim",
                                "configs"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except OSError:
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="사람 수 시뮬레이션 v2 (사전등록 v1)")
    ap.add_argument("--criteria", default="experiments/sample_size_sim/criteria_v1.1.json")
    ap.add_argument("--assumptions", default="experiments/sample_size_sim/assumptions_v1.json")
    ap.add_argument("--pilot", default="", help="파일럿 값. 예: p_nouse=0.42,common=0.71,p_two=0.35")
    ap.add_argument("--rules", default="configs/rules.draft.json")
    ap.add_argument("--configs", default="single,merged")
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--resamples", type=int, default=None, help="안 주면 가정 4개 이하 1,000, 넘으면 200 (사전등록 2장)")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--seed", default="20261108")
    ap.add_argument("--out", default="experiments/sample_size_sim/result_v2.json")
    args = ap.parse_args(argv)
    crit = json.loads((ROOT / args.criteria).read_text(encoding="utf-8"))
    base = json.loads((ROOT / args.assumptions).read_text(encoding="utf-8"))["assumptions"]
    for a in base:
        a.setdefault("p_nouse", P_NOUSE)
        a.setdefault("p_two", P_TWO_REASONS)
    pilot = parse_pilot(args.pilot)
    assumptions = pilot_assumptions(base, pilot) if pilot else base
    resamples = args.resamples or (1000 if len(assumptions) <= 4 else 200)
    configs = [c for c in args.configs.split(",") if c]
    rules_path = ROOT / args.rules
    rules_by_config = {c: sim_rules(rules_path, resamples, c) for c in configs}
    rule_names = ["main"] + [x["name"] for x in rules_by_config[configs[0]]["sensitivity"]]
    if args.reps > 10 and not args.out.startswith("experiments/"):
        print("[주의] 반복 10번을 넘는 실행은 v2 본 실행이다. 결과는 experiments/ 아래에 남긴다")
    jobs = [(cfg, a["name"], a, kind, n, f"{args.seed}|{cfg}|{a['name']}|{kind}|{n}|{i}", rules_by_config[cfg])
            for cfg in configs for a in assumptions for kind in AI_KINDS for n in SIZES[cfg] for i in range(args.reps)]
    print(f"[v2] 구성 {configs}, 가정 {len(assumptions)}개, 반복 {args.reps}, 다시 뽑기 {resamples}, "
          f"작업 {len(jobs):,}개, 프로세스 {args.workers}", flush=True)
    started = time.time()
    agg = {}
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for key, verdicts, widths, n_cells, cov in pool.map(run_job, jobs, chunksize=4):
            slot = agg.setdefault(key, {"verdicts": {r: Counter() for r in rule_names}, "width_sum": 0.0,
                                        "width_n": 0, "n_cells": Counter(), "coverage": []})
            slot["coverage"] += cov
            for r in rule_names:
                slot["verdicts"][r].update(verdicts[r])
            slot["width_sum"] += sum(widths)
            slot["width_n"] += len(widths)
            slot["n_cells"].update(n_cells)
            done += 1
            if done % max(1, len(jobs) // 20) == 0:
                el = time.time() - started
                print(f"  {done:,}/{len(jobs):,} ({el / 60:.1f}분, 남은 시간 약 {el / done * (len(jobs) - done) / 60:.0f}분)",
                      flush=True)

    results = {}
    for cfg in configs:
        results[cfg] = {}
        for rule in rule_names:
            per_n = []
            for n in SIZES[cfg]:
                per_a = {}
                for a in assumptions:
                    by_kind = {k: rates(agg[(cfg, a["name"], k, n)]["verdicts"][rule]) for k in AI_KINDS}
                    per_a[a["name"]] = check(by_kind, crit)
                per_n.append({"n": n, "pass": all(v["pass"] for v in per_a.values()),
                              "pass_v1": all(v["pass_v1"] for v in per_a.values()), "by_assumption": per_a})
            results[cfg][rule] = {"minimum_n": minimum_n([(x["n"], x["pass"]) for x in per_n]),
                                  "minimum_n_v1": minimum_n([(x["n"], x["pass_v1"]) for x in per_n]), "rows": per_n}
    table = min_table(results, rule_names, "minimum_n")
    table_v1 = min_table(results, rule_names, "minimum_n_v1")
    selection = select_tiered(table, table_v1) if set(configs) == {"single", "merged"} else None
    if selection:
        smin = (table if selection["tier"] == 1 else table_v1)[selection["rule"]]["single_min"]
        selection["T"] = max(40, smin) if (smin is not None and selection["service_judgment"]) else None
    coverage_by_n = {}
    for k, v in agg.items():
        if k[2] != "same" or not v["coverage"]:
            continue
        est = [x[0] for x in v["coverage"]]
        true = [x[1] for x in v["coverage"]]
        need = sorted(x[2] for x in v["coverage"] if x[2] is not None)
        coverage_by_n[f"{k[0]}|{k[1]}|{k[3]}"] = {
            "cells": len(est), "estimate_mean": round(sum(est) / len(est), 4),
            "true_mean": round(sum(true) / len(true), 4),
            "estimate_at_least_90": round(sum(e >= 0.9 for e in est) / len(est), 4),
            "true_at_least_90": round(sum(t >= 0.9 for t in true) / len(true), 4),
            "need_total_median": round(need[len(need) // 2], 1) if need else None,
            "need_reliable_share": round(sum(bool(x[3]) for x in v["coverage"]) / len(est), 4)}
    summary_cells = {f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": {
        "width_mean": round(v["width_sum"] / v["width_n"], 4) if v["width_n"] else None,
        "median_n_cell": sorted(v["n_cells"].elements())[sum(v["n_cells"].values()) // 2]} for k, v in agg.items()}
    record = {"version": "v2", "preregistration": ["docs/measurement/사전등록_v1.md",
                                                    "docs/measurement/사전등록_v1.1_추가.md",
                                                    "docs/measurement/사전등록_v1.2_추가.md"],
              "command": "python " + " ".join([Path(sys.argv[0]).as_posix()] + (argv if argv is not None else sys.argv[1:])),
              "code_commit": git_commit(), "criteria": crit, "assumptions": assumptions, "pilot": pilot or None,
              "settings": {"configs": configs, "sizes": {c: SIZES[c] for c in configs}, "reps": args.reps,
                           "resamples": resamples, "seed": args.seed, "rules_file": args.rules,
                           "rules_sha256": hashlib.sha256(rules_path.read_bytes()).hexdigest(),
                           "ai_personas_per_platform_per_service": AI_PERSONAS_PER_PLATFORM, "p_app": P_APP},
              "minimum_n": table, "minimum_n_v1": table_v1, "selection": selection, "results": results,
              "cells": summary_cells, "coverage": coverage_by_n,
              "elapsed_sec": round(time.time() - started, 1)}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()

    print("[합격 기준] 사람 같은 AI 믿음 {:.0%} 이상, 반만 맞는 AI {:.0%} 이하, 공통 이유만 AI {:.0%} 이하, "
          "자료 부족 {:.0%} 이하, 순위 뒤집힌 AI {} 이하. 가정 {}개 중 가장 나쁜 경우".format(
              crit["min_same_trust"], crit["max_half_trust"], crit["max_common_only_trust"], crit["max_low"],
              f"{crit['max_reversed_trust']:.0%}" if "max_reversed_trust" in crit else "(기준 없음)",
              len(assumptions)))
    print("[최소 인원] 규칙 | 서비스 하나 | 두 서비스 합친 것 | (v1 기준 넷) 서비스 하나 | 합친 것")
    for rule in RULE_ORDER:
        if rule in table:
            t, t1 = table[rule], table_v1[rule]
            print(f"  {rule:<14} | {t['single_min'] or '없음'} | {t['merged_min'] or '없음'} | "
                  f"{t1['single_min'] or '없음'} | {t1['merged_min'] or '없음'}")
    if selection:
        print(f"[고른 규칙] {selection['rule']} ({selection['case']}), T = {selection['T']}")
    print(f"기록: {args.out} ({record['elapsed_sec']}초), sha256 {sha}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

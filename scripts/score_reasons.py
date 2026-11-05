"""이유 판정 계산기 (TRD IF-10을 폼 B v2 이유 판정에 맞춘 것).

사람 이유 코드와 AI 이유 코드를 받아 판정 칸마다 통과율(정밀도)과 재현율을 내고,
같은 데이터에서 잰 두 기준점(사람끼리, 아무 기능에나 할 말)에 맞춰 판정을 붙인다.
설계는 docs/measurement/측정대상-판정기준.md (PR #36, #6)를 따른다.

입력
- 사람 코드 CSV (--human): 정리 담당이 사람 응답을 코드북으로 정리한 것. 응답 원문은 넣지 않는다
    respondent_id, service, platform, feature_id, kind(use|nouse), code, order(선택. 응답 순서)
    code가 빈 줄은 "그 칸에 답했지만 붙일 코드가 없음"이다. 사람 수에는 들어가고 이유에는 안 들어간다
- AI 코드 CSV (--ai): scripts/reason_sheet.py import가 만든 것
    item_id, run_id, service, platform, condition, persona_id, repeat, feature_id, kind, code
    (input_mode, model 칸이 있으면 한 조건 안에 다른 값이 섞였을 때 멈춘다)
- 판정 규칙 JSON (--rules): 기준값을 코드에 박지 않는다 (FR-08-01). 동결 전 규칙은 --allow-draft를 붙여야 돈다
- 코드는 양쪽 다 같은 표기로 맞춘다 (전각 글자, 엑셀이 바꾼 대시, 대소문자)

출력 (--out 폴더)
- metrics_{범위}_{시각}.json: 실행 기록, 규칙, 칸별 숫자와 판정, 요약
- cells_{범위}_{시각}.csv: 칸 x 조건마다 한 줄
- reasons_{범위}_{시각}.csv: AI가 말한 이유마다 "응답자 n명 중 m명" (기말 데모 거름망), 놓친 이유

화면에는 숫자만 찍는다.
종료 코드: 0 정상, 1 입력 파일 없음·사용법, 4 입력 검증 실패 (이때는 아무것도 쓰지 않는다)
"""

import argparse
import csv
import hashlib
import json
import math
import os
import platform as _platform
import random
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXIT_OK, EXIT_USAGE, EXIT_INPUT = 0, 1, 4

KINDS = ("use", "nouse")
PLATFORMS = ("app", "web")
CONDITIONS = (0, 1, 2, 3)
METRICS = ("precision", "recall")
CELL_KEYS = ("service", "platform", "feature_id", "kind")
HUMAN_FIELDS = ["respondent_id", "service", "platform", "feature_id", "kind", "code"]
AI_FIELDS = ["item_id", "run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id", "kind",
             "code"]
RUN_FIELDS = ("input_mode", "model")  # 있으면 조건마다 하나여야 한다
DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u30fc"), "-")

LOW, NA, ASK, TRUST, REF = "자료 부족", "계산 불가", "사람에게 물어볼 것", "믿고 써도 됨", "참고용"
VERDICTS = (TRUST, REF, ASK, LOW, NA)

CELL_CSV = ["condition", "service", "platform", "feature_id", "kind", "n_humans", "ai_episodes", "ai_codes",
            "human_codes", "matched", "precision", "recall", "ai_split_precision", "ai_split_recall",
            "human_precision_low", "human_precision_high", "human_recall_low", "human_recall_high",
            "floor_precision_low", "floor_precision_high", "floor_recall_low", "floor_recall_high",
            "verdict", "stable_at"]
REASON_CSV = ["condition", "service", "platform", "feature_id", "kind", "type", "code", "ai_episodes_with_code",
              "ai_episodes", "human_count", "n_humans", "passed", "basis"]


class InputError(Exception):
    pass


# ---------------------------------------------------------------- 입력

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path, required: list) -> list:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"{path.name}: 칸이 없음 {missing}")
        return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]


def norm_code(code: str) -> str:
    """'n01', 전각 'N01', 'N01'을 같은 코드로 본다. 엑셀이 '-'를 긴 대시로 바꾼 것도 되돌린다."""
    return unicodedata.normalize("NFKC", code).translate(DASHES).strip().upper()


def check_common(rows: list, name: str) -> None:
    for i, r in enumerate(rows, 2):
        if r["kind"] not in KINDS:
            raise InputError(f"{name} {i}행: kind는 use 또는 nouse")
        if r["platform"] not in PLATFORMS:
            raise InputError(f"{name} {i}행: platform은 app 또는 web")
        if not r["service"] or not r["feature_id"]:
            raise InputError(f"{name} {i}행: service와 feature_id는 비울 수 없음")
        r["code"] = norm_code(r["code"])
        if any(sep in r["code"] for sep in ",;"):
            raise InputError(f"{name} {i}행: 한 줄에 코드 하나만 넣는다 (코드가 여럿이면 줄을 나눈다)")


def load_human(path: Path) -> list:
    rows = read_csv(path, HUMAN_FIELDS)
    check_common(rows, path.name)
    for i, r in enumerate(rows, 2):
        if not r["respondent_id"]:
            raise InputError(f"{path.name} {i}행: respondent_id가 비었음")
        if r.get("order"):
            try:
                int(r["order"])
            except ValueError:
                raise InputError(f"{path.name} {i}행: order는 정수") from None
    return rows


def load_ai(path: Path) -> list:
    rows = read_csv(path, AI_FIELDS)
    check_common(rows, path.name)
    for i, r in enumerate(rows, 2):
        try:
            r["condition"] = int(r["condition"])
        except ValueError:
            raise InputError(f"{path.name} {i}행: condition은 0~3") from None
        if r["condition"] not in CONDITIONS:
            raise InputError(f"{path.name} {i}행: condition은 0~3")
        if not r["run_id"] or not r["code"]:
            raise InputError(f"{path.name} {i}행: run_id와 code는 비울 수 없음 (이유가 아니면 코드 '-')")
    runs = defaultdict(set)
    for r in rows:
        runs[r["condition"]].add(tuple(r.get(f, "") for f in RUN_FIELDS))
    mixed = sorted(c for c, v in runs.items() if len(v) > 1)
    if mixed:
        raise InputError(f"{path.name}: 조건 {mixed} 안에 입력 방식이나 모델이 다른 실행이 섞여 있음. "
                         "나눠서 계산한다")
    return rows


def load_rules(path: Path) -> dict:
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise InputError(f"{path.name}: JSON을 못 읽음 ({e.msg})") from None
    need = ["cell_keys", "min_humans", "method", "metrics", "level", "resamples", "seed", "fixed",
            "reason_min_humans", "ai_drop_codes", "sensitivity", "stability", "saturation"]
    missing = [k for k in need if k not in rules]
    if missing:
        raise InputError(f"{path.name}: 규칙 항목이 없음 {missing}")
    keys = rules["cell_keys"]
    if not set(keys) <= set(CELL_KEYS) or "feature_id" not in keys or "kind" not in keys:
        raise InputError(f"{path.name}: cell_keys는 {list(CELL_KEYS)} 중에서 고르고 feature_id와 kind는 꼭 넣는다")
    if not rules["metrics"] or not set(rules["metrics"]) <= set(METRICS):
        raise InputError(f"{path.name}: metrics는 precision, recall 중에서 고른다")
    if not isinstance(rules["fixed"], dict):
        raise InputError(f"{path.name}: fixed는 trust와 reference를 담은 객체")
    check_rule(merge_rule(rules, {}), path.name)
    for alt in rules["sensitivity"]:
        if "name" not in alt:
            raise InputError(f"{path.name}: sensitivity 항목마다 name이 필요함")
        check_rule(merge_rule(rules, alt), f"{path.name} sensitivity {alt['name']}")
    if not isinstance(rules["min_humans"], int) or rules["min_humans"] < 1:
        raise InputError(f"{path.name}: min_humans는 1 이상 정수")
    if not isinstance(rules["resamples"], int) or rules["resamples"] < 1:
        raise InputError(f"{path.name}: resamples는 1 이상 정수")
    st, sa = rules["stability"], rules["saturation"]
    for name, part, need_keys in (("stability", st, ("start", "step", "draws", "tolerance")),
                                  ("saturation", sa, ("group_keys", "min_respondents", "run", "max_new"))):
        lacking = [k for k in need_keys if not isinstance(part, dict) or k not in part]
        if lacking:
            raise InputError(f"{path.name}: {name}에 항목이 없음 {lacking}")
    nums = [st["start"], st["step"], st["draws"], st["tolerance"], sa["min_respondents"], sa["run"], sa["max_new"]]
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in nums):
        raise InputError(f"{path.name}: stability, saturation 값은 숫자")
    if st["start"] < 1 or st["step"] < 1 or st["draws"] < 1 or not 0 <= st["tolerance"] < 1:
        raise InputError(f"{path.name}: stability 값이 이상함")
    if not set(sa["group_keys"]) <= {"service", "platform"} or sa["run"] < 1 or sa["max_new"] < 0:
        raise InputError(f"{path.name}: saturation 값이 이상함")
    return rules


def merge_rule(rules: dict, alt: dict) -> dict:
    """민감도 규칙 하나. 안 적은 값은 본 규칙을 따른다."""
    out = {"method": rules["method"], "level": rules["level"], "metrics": rules["metrics"],
           "min_humans": rules["min_humans"], **rules["fixed"]}
    out.update({k: v for k, v in alt.items() if k != "name"})
    return out


def check_rule(rule: dict, where: str) -> None:
    if rule.get("method") not in ("anchors", "fixed"):
        raise InputError(f"{where}: method는 anchors 또는 fixed")
    if not isinstance(rule.get("level"), (int, float)) or not 0 < rule["level"] < 1:
        raise InputError(f"{where}: level은 0과 1 사이")
    t, r = rule.get("trust"), rule.get("reference")
    if not (isinstance(t, (int, float)) and isinstance(r, (int, float)) and 0 <= r <= t <= 1):
        raise InputError(f"{where}: 고정 기준은 0 <= reference <= trust <= 1")


# ---------------------------------------------------------------- 계산 도구

def pr(pred: set, ref: set) -> tuple:
    """통과율(정밀도)과 재현율. 분모가 0이면 None (FR-07-06 계산 불가)."""
    hit = len(pred & ref)
    return (hit / len(pred) if pred else None), (hit / len(ref) if ref else None)


def quantile(values: list, q: float):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    pos = q * (len(v) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def interval(values: list, level: float):
    a = (1 - level) / 2
    lo, hi = quantile(values, a), quantile(values, 1 - a)
    return None if lo is None else [lo, hi]


def rnd(x, n=4):
    return None if x is None else round(x, n)


def mean(values: list):
    v = [x for x in values if x is not None]
    return rnd(sum(v) / len(v)) if v else None


def union(groups: dict, ids) -> set:
    out = set()
    for i in ids:
        out |= groups[i]
    return out


# ---------------------------------------------------------------- 칸 만들기

def build_cells(human: list, ai: list, rules: dict) -> tuple:
    keys = rules["cell_keys"]
    drop = {norm_code(c) for c in rules["ai_drop_codes"]}
    humans = defaultdict(dict)  # 칸 -> {응답자: 코드 집합}
    for r in human:
        codes = humans[tuple(r[k] for k in keys)].setdefault(r["respondent_id"], set())
        if r["code"]:
            codes.add(r["code"])
    ai_cells = defaultdict(lambda: {"episodes": set(), "code_eps": defaultdict(set), "ep_codes": defaultdict(set),
                                    "persona_eps": defaultdict(set)})
    dropped = 0
    for r in ai:
        cell = ai_cells[(r["condition"], tuple(r[k] for k in keys))]
        cell["episodes"].add(r["run_id"])
        cell["persona_eps"][r["persona_id"]].add(r["run_id"])
        cell["ep_codes"].setdefault(r["run_id"], set())
        if r["code"] in drop:
            dropped += 1
            continue
        cell["code_eps"][r["code"]].add(r["run_id"])
        cell["ep_codes"][r["run_id"]].add(r["code"])
    return humans, ai_cells, dropped


def floor_partners(key: tuple, cond: int, ai_cells: dict, keys: list) -> list:
    """같은 조건·같은 칸에서 기능만 다른 AI 칸들 (아무 기능에나 할 말)."""
    fi = keys.index("feature_id")
    out = []
    for (c, k), cell in sorted(ai_cells.items(), key=lambda x: (x[0][0], x[0][1])):
        if c != cond or k[fi] == key[fi] or not cell["code_eps"]:
            continue
        if all(k[i] == key[i] for i in range(len(keys)) if i != fi):
            out.append(cell)
    return out


def sample_ai(cell: dict, k: int, rng: random.Random) -> set:
    """페르소나 k명을 뽑고 페르소나마다 회차 하나의 코드만 합친다. 사람 A(k명)와 같은 크기로 잰다.
    페르소나가 k명보다 적으면 있는 만큼 쓴다. 같은 페르소나의 반복은 서로 다른 사람으로 치지 않는다."""
    personas = sorted(cell["persona_eps"])
    out = set()
    for p in rng.sample(personas, min(k, len(personas))):
        out |= cell["ep_codes"][rng.choice(sorted(cell["persona_eps"][p]))]
    return out


def split_draws(cond: int, key: tuple, groups: dict, aic: dict, partners: list, rules: dict) -> dict:
    """사람을 무작위로 반씩 나눠 B를 기준으로 사람 A, AI, 다른 기능 AI를 잰다.
    같은 B에 대고, AI 쪽도 A와 같은 인원(페르소나 수)으로 뽑아서 재야 크기가 맞는다.
    나누기, AI 뽑기, 다른 기능 뽑기는 난수를 따로 써서 다른 칸 자료가 이 칸 나누기를 바꾸지 않게 한다."""
    ids = sorted(groups)
    draws = {f"{who}_{m}": [] for who in ("human", "ai", "floor") for m in METRICS}
    if len(ids) < 2:
        return draws
    tag = f"{cond}|{'|'.join(key)}"
    rng = random.Random(f"{rules['seed']}|split|{tag}")
    rng_ai = random.Random(f"{rules['seed']}|ai|{tag}")
    rng_floor = random.Random(f"{rules['seed']}|floor|{tag}")
    half = len(ids) // 2
    for _ in range(rules["resamples"]):
        s = ids[:]
        rng.shuffle(s)
        a, b = union(groups, s[:half]), union(groups, s[half:])
        ai_pred = sample_ai(aic, half, rng_ai) if aic["persona_eps"] else None
        floor_pred = sample_ai(rng_floor.choice(partners), half, rng_floor) if partners else None
        for who, pred in (("human", a), ("ai", ai_pred), ("floor", floor_pred)):
            p, r = pr(pred, b) if pred is not None else (None, None)
            draws[f"{who}_precision"].append(p)
            draws[f"{who}_recall"].append(r)
    return draws


def stability(cond: int, key: tuple, groups: dict, ai_codes: set, rules: dict) -> dict:
    """사람 수를 늘려 가며 통과율이 어디서 자리를 잡는지 본다 (측정 문서 5번)."""
    st = rules["stability"]
    ids = sorted(groups)
    n = len(ids)
    if not ai_codes or n < st["start"]:
        return {"sizes": [], "stable_at": None}
    sizes = list(range(st["start"], n + 1, st["step"]))
    if sizes[-1] != n:
        sizes.append(n)
    rng = random.Random(f"{rules['seed']}|stability|{cond}|{'|'.join(key)}")
    rows = []
    for k in sizes:
        ps, rs_ = [], []
        for _ in range(st["draws"] if k < n else 1):
            p, r = pr(ai_codes, union(groups, rng.sample(ids, k)))
            ps.append(p)
            rs_.append(r)
        rows.append({"k": k, "precision_mean": mean(ps),
                     "precision_interval": [rnd(x) for x in (interval(ps, rules["level"]) or [])] or None,
                     "recall_mean": mean(rs_)})
    stable_at = None
    means = [r["precision_mean"] for r in rows]
    for i in range(len(rows) - 1):
        rest = [m for m in means[i:] if m is not None]
        if len(rest) == len(means) - i and max(rest) - min(rest) <= st["tolerance"]:
            stable_at = rows[i]["k"]
            break
    return {"sizes": rows, "stable_at": stable_at}


def saturation(human: list, rules: dict) -> list:
    """응답 순서대로 사람마다 새로 나온 이유 수. 하한을 넘긴 뒤 연속 run명이 max_new개 이하면 다 모은 걸로 본다 (폼 운영 규칙)."""
    sa = rules["saturation"]
    by_group = defaultdict(lambda: defaultdict(set))
    first_seen, order = {}, {}
    for i, r in enumerate(human):
        g = tuple(r[k] for k in sa["group_keys"])
        rid = r["respondent_id"]
        first_seen.setdefault((g, rid), i)
        if r.get("order"):
            order[(g, rid)] = int(r["order"])
        if r["code"]:
            by_group[g][rid].add((r["feature_id"], r["kind"], r["code"]))
        else:
            by_group[g].setdefault(rid, set())
    out = []
    for g, people in sorted(by_group.items()):
        ids = sorted(people, key=lambda rid: (order.get((g, rid), math.inf), first_seen[(g, rid)]))
        seen, new = set(), []
        for rid in ids:
            fresh = people[rid] - seen
            new.append(len(fresh))
            seen |= fresh
        reached = None
        for t in range(max(sa["run"], sa["min_respondents"]), len(new) + 1):
            if all(x <= sa["max_new"] for x in new[t - sa["run"]:t]):
                reached = t
                break
        out.append({**dict(zip(sa["group_keys"], g)), "respondents": len(ids), "reasons": len(seen),
                    "new_per_respondent": new, "saturated_at": reached})
    return out


# ---------------------------------------------------------------- 판정

def anchor_view(draws: dict, level: float, metrics: list) -> dict:
    view = {}
    for m in metrics:
        view[m] = {"ai": quantile(draws[f"ai_{m}"], 0.5),
                   "human": interval(draws[f"human_{m}"], level),
                   "floor": interval(draws[f"floor_{m}"], level)}
    return view


def judge(cell: dict, rule: dict) -> str:
    """판정 하나. 자료 부족, 계산 불가, 물어볼 것, 믿고 써도 됨, 참고용 순서로 본다."""
    if cell["n_humans"] < rule["min_humans"]:
        return LOW
    if not cell["ai_codes"]:
        return NA
    metrics = rule["metrics"]
    if rule["method"] == "fixed":
        vals = [cell["full"][m] for m in metrics]
        if any(v is None for v in vals):
            return NA
        if all(v >= rule["trust"] for v in vals):
            return TRUST
        return REF if all(v >= rule["reference"] for v in vals) else ASK
    view = anchor_view(cell["draws"], rule["level"], metrics)
    if any(view[m]["ai"] is None or view[m]["human"] is None for m in metrics):
        return NA
    # AI가 사람 이유를 거의 못 맞히면(중앙값 0) 사람끼리 구간 아래쪽이 0이어도 믿지 않는다
    if any(view[m]["ai"] == 0 for m in metrics):
        return ASK
    # 아무 기능에나 할 말과 구별이 안 되면 사람 범위에 들어도 믿지 않는다 (두 기준점이 겹칠 때 보수적으로)
    if any(view[m]["floor"] is not None and view[m]["ai"] <= view[m]["floor"][1] for m in metrics):
        return ASK
    # 비교할 다른 기능이 없으면 아무 기능에나 할 말인지 가릴 수 없어서 믿음 판정은 내지 않는다
    if any(view[m]["floor"] is None for m in metrics):
        return REF
    if all(view[m]["ai"] >= view[m]["human"][0] for m in metrics):
        return TRUST
    return REF


def score(human: list, ai: list, rules: dict) -> dict:
    keys = rules["cell_keys"]
    humans, ai_cells, dropped = build_cells(human, ai, rules)
    main_rule = merge_rule(rules, {})
    alts = [(a["name"], merge_rule(rules, a)) for a in rules["sensitivity"]]
    conditions = sorted({c for c, _ in ai_cells})
    all_keys = sorted(set(humans) | {k for _, k in ai_cells})
    cells = []
    for cond in conditions:
        for key in all_keys:
            groups = humans.get(key, {})
            aic = ai_cells.get((cond, key), {"episodes": set(), "code_eps": {}, "ep_codes": {}, "persona_eps": {}})
            ai_codes = set(aic["code_eps"])
            human_count = Counter(c for codes in groups.values() for c in codes)
            p, r = pr(ai_codes, set(human_count))
            partners = floor_partners(key, cond, ai_cells, keys)
            cell = {"condition": cond, **dict(zip(keys, key)), "n_humans": len(groups),
                    "ai_episodes": len(aic["episodes"]), "ai_codes": sorted(ai_codes),
                    "human_codes": len(human_count), "matched": len(ai_codes & set(human_count)),
                    "full": {"precision": p, "recall": r}, "floor_partners": len(partners),
                    "draws": split_draws(cond, key, groups, aic, partners, rules)}
            cell["verdict"] = judge(cell, main_rule)
            cell["sensitivity"] = {name: judge(cell, rule) for name, rule in alts}
            cell["stability"] = stability(cond, key, groups, ai_codes, rules)
            cell["reasons"] = [{"code": c, "ai_episodes_with_code": len(aic["code_eps"][c]),
                                "human_count": human_count.get(c, 0),
                                "passed": human_count.get(c, 0) >= rules["reason_min_humans"]}
                               for c in sorted(ai_codes)]
            cell["missed"] = [{"code": c, "human_count": n} for c, n in sorted(human_count.items())
                              if c not in ai_codes]
            cells.append(cell)
    human_keys, ai_keys = set(humans), {k for _, k in ai_cells}
    coverage = {"both": len(human_keys & ai_keys), "human_only": len(human_keys - ai_keys),
                "ai_only": len(ai_keys - human_keys)}
    return {"cells": cells, "conditions": conditions, "dropped_ai_rows": dropped, "coverage": coverage,
            "saturation": saturation(human, rules), "summary": summarize(cells, conditions, alts, keys)}


def summarize(cells: list, conditions: list, alts: list, keys: list) -> dict:
    out = {"verdicts": {}, "mean": {}, "above_condition0": {}, "sensitivity_changed": {}}
    for cond in conditions:
        mine = [c for c in cells if c["condition"] == cond]
        out["verdicts"][cond] = {v: sum(c["verdict"] == v for c in mine) for v in VERDICTS}
        out["mean"][cond] = {m: mean([c["full"][m] for c in mine if c["verdict"] != LOW]) for m in METRICS}
    if 0 in conditions:
        base = {tuple(c[k] for k in keys): c for c in cells if c["condition"] == 0}
        for cond in conditions:
            if cond == 0:
                continue
            higher = same = lower = 0
            for c in cells:
                b = base.get(tuple(c[k] for k in keys))
                if c["condition"] != cond or b is None or c["verdict"] == LOW:
                    continue
                x, y = c["full"]["precision"], b["full"]["precision"]
                if x is None or y is None:
                    continue
                higher += x > y
                same += x == y
                lower += x < y
            out["above_condition0"][cond] = {"higher": higher, "same": same, "lower": lower}
    for name, _ in alts:
        out["sensitivity_changed"][name] = sum(c["sensitivity"][name] != c["verdict"] for c in cells)
    out["cells"] = len(cells)
    return out


# ---------------------------------------------------------------- 출력

def cell_json(cell: dict, rules: dict) -> dict:
    view = anchor_view(cell["draws"], rules["level"], list(METRICS))
    out = {k: v for k, v in cell.items() if k not in ("draws", "full")}
    out["precision"], out["recall"] = rnd(cell["full"]["precision"]), rnd(cell["full"]["recall"])
    out["anchors"] = {m: {"ai_split_median": rnd(view[m]["ai"]),
                          "human_interval": [rnd(x) for x in view[m]["human"]] if view[m]["human"] else None,
                          "floor_interval": [rnd(x) for x in view[m]["floor"]] if view[m]["floor"] else None}
                      for m in METRICS}
    return out


def cell_row(c: dict) -> dict:
    a = c["anchors"]

    def bound(m, who, i):
        return a[m][who][i] if a[m][who] else None

    return {"condition": c["condition"], **{k: c.get(k, "*") for k in CELL_KEYS},
            "n_humans": c["n_humans"], "ai_episodes": c["ai_episodes"], "ai_codes": len(c["ai_codes"]),
            "human_codes": c["human_codes"], "matched": c["matched"], "precision": c["precision"],
            "recall": c["recall"], "ai_split_precision": a["precision"]["ai_split_median"],
            "ai_split_recall": a["recall"]["ai_split_median"],
            "human_precision_low": bound("precision", "human_interval", 0),
            "human_precision_high": bound("precision", "human_interval", 1),
            "human_recall_low": bound("recall", "human_interval", 0),
            "human_recall_high": bound("recall", "human_interval", 1),
            "floor_precision_low": bound("precision", "floor_interval", 0),
            "floor_precision_high": bound("precision", "floor_interval", 1),
            "floor_recall_low": bound("recall", "floor_interval", 0),
            "floor_recall_high": bound("recall", "floor_interval", 1),
            "verdict": c["verdict"], "stable_at": c["stability"]["stable_at"]}


def reason_rows(c: dict) -> list:
    common = {"condition": c["condition"], **{k: c.get(k, "*") for k in CELL_KEYS},
              "ai_episodes": c["ai_episodes"], "n_humans": c["n_humans"]}
    rows = []
    for r in c["reasons"]:
        basis = (f"응답자 {c['n_humans']}명 중 {r['human_count']}명이 같은 이유를 말함" if r["human_count"]
                 else "응답자 중 이 이유를 말한 사람 없음")
        rows.append({**common, "type": "ai_reason", "code": r["code"],
                     "ai_episodes_with_code": r["ai_episodes_with_code"], "human_count": r["human_count"],
                     "passed": "Y" if r["passed"] else "N", "basis": basis})
    for r in c["missed"]:
        rows.append({**common, "type": "missed", "code": r["code"], "ai_episodes_with_code": 0,
                     "human_count": r["human_count"], "passed": "",
                     "basis": f"응답자 {c['n_humans']}명 중 {r['human_count']}명이 말했는데 AI는 안 말함"})
    return rows


def write_csv(path: Path, fields: list, rows: list) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def print_summary(result: dict, rules: dict, run_id: str) -> None:
    s = result["summary"]
    print("=" * 60)
    print(f"[판정 요약] {run_id}")
    if not rules.get("frozen"):
        print("  주의: 판정 규칙이 아직 동결 전이다 (FR-08-01). 결과는 시험용으로만 본다")
    print(f"  칸 x 조건  : {s['cells']}개, 방법 {rules['method']}, 구간 {int(rules['level'] * 100)}%, "
          f"다시 뽑기 {rules['resamples']}번")
    for cond in result["conditions"]:
        v = s["verdicts"][cond]
        mean = s["mean"][cond]
        print(f"  조건 {cond}     : " + ", ".join(f"{k} {v[k]}" for k in VERDICTS)
              + f" / 평균 통과율 {mean['precision']}, 평균 재현율 {mean['recall']}")
    for cond, x in s["above_condition0"].items():
        print(f"  조건 {cond} vs 0: 통과율 높음 {x['higher']}, 같음 {x['same']}, 낮음 {x['lower']}")
    for name, n in s["sensitivity_changed"].items():
        print(f"  민감도 {name}: 판정이 바뀐 칸 {n}개")
    for g in result["saturation"]:
        label = "/".join(str(g[k]) for k in rules["saturation"]["group_keys"])
        print(f"  포화 {label}: 응답자 {g['respondents']}명, 이유 {g['reasons']}개, "
              f"다 모음 {g['saturated_at'] if g['saturated_at'] else '아직'}")
    cov = result["coverage"]
    print(f"  칸 겹침    : 사람과 AI 둘 다 {cov['both']}칸, 사람만 {cov['human_only']}칸, AI만 {cov['ai_only']}칸")
    if result["dropped_ai_rows"]:
        print(f"  이유 아님으로 뺀 AI 줄: {result['dropped_ai_rows']}개")
    print("=" * 60)


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="이유 판정 계산기 (TRD IF-10)")
    ap.add_argument("--human", required=True, help="사람 코드 CSV")
    ap.add_argument("--ai", required=True, help="AI 코드 CSV (reason_sheet.py import 결과)")
    ap.add_argument("--rules", default="configs/rules.draft.json", help="판정 규칙 JSON")
    ap.add_argument("--out", default="runs/dev/scoring", help="출력 폴더")
    ap.add_argument("--service", help="이 서비스만 계산. 안 주면 전부")
    ap.add_argument("--allow-draft", action="store_true",
                    help="동결 전 규칙으로 시험 삼아 돌린다. 실제 응답에는 쓰지 않는다 (측정 원칙: 기준은 응답을 보기 전에 고정)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_USAGE
    paths = {"human": root / args.human, "ai": root / args.ai, "rules": root / args.rules}
    for name, p in paths.items():
        if not p.is_file():
            print(f"[오류] 입력 파일 없음: --{name} {p.relative_to(root) if p.is_relative_to(root) else p}",
                  file=sys.stderr)
            return EXIT_USAGE
    try:
        rules = load_rules(paths["rules"])
        human, ai = load_human(paths["human"]), load_ai(paths["ai"])
    except (InputError, UnicodeDecodeError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        return EXIT_INPUT
    if not rules.get("frozen") and not args.allow_draft:
        print("[입력 오류] 판정 규칙이 동결 전이다. 시험으로 돌릴 때만 --allow-draft를 붙인다", file=sys.stderr)
        return EXIT_INPUT
    if args.service:
        human = [r for r in human if r["service"] == args.service]
        ai = [r for r in ai if r["service"] == args.service]
    if not ai:
        print("[입력 오류] 계산할 AI 코드가 없음", file=sys.stderr)
        return EXIT_INPUT

    result = score(human, ai, rules)
    if human and not result["coverage"]["both"]:
        print("[입력 오류] 사람 칸과 AI 칸이 하나도 안 겹친다. service, platform, feature_id 글자를 확인한다 "
              "(service는 snapshot.json의 service 값)", file=sys.stderr)
        return EXIT_INPUT
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    scope = args.service or "all"
    run_id = f"score_{scope}_{stamp}_{os.getpid() % 10000}"
    cells = [cell_json(c, rules) for c in result["cells"]]
    record = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "python": _platform.python_version(),
        "inputs": {name: {"path": str(Path(getattr(args, name))).replace("\\", "/"), "sha256": file_hash(p)}
                   for name, p in paths.items()},
        "service_filter": args.service,
        "rules": rules,
        "rules_frozen": bool(rules.get("frozen")),
        "conditions": result["conditions"],
        "dropped_ai_rows": result["dropped_ai_rows"],
        "coverage": result["coverage"],
        "summary": result["summary"],
        "saturation": result["saturation"],
        "cells": cells,
    }
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{scope}_{stamp}"
    (out / f"metrics_{tag}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    write_csv(out / f"cells_{tag}.csv", CELL_CSV, [cell_row(c) for c in cells])
    write_csv(out / f"reasons_{tag}.csv", REASON_CSV, [r for c in cells for r in reason_rows(c)])
    print_summary(result, rules, run_id)
    print(f"  출력: {args.out}/metrics_{tag}.json, cells_{tag}.csv, reasons_{tag}.csv")
    return EXIT_OK


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())

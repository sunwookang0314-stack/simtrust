"""이유 판정 계산기 (TRD IF-10을 폼 B v2 이유 판정에 맞춘 것).

사람 이유 코드와 AI 이유 코드를 받아 판정 칸마다 통과율(정밀도)과 재현율을 내고,
같은 데이터에서 잰 두 기준점(사람끼리, 아무 기능에나 할 말)에 맞춰 판정을 붙인다.
설계는 docs/measurement/측정대상-판정기준.md (PR #36, #6)를 따른다.

지표 (사전등록 v1.1 추가안에서 빈도 지표 둘을 더했다)
- precision(통과율), recall(재현율): AI가 말한 이유 종류와 사람이 말한 이유 종류가 겹치는지
- dist(분포 유사도): 1 - 젠슨-섀넌 발산(밑 2). 이유마다 몇 명이 말했는지 비율 분포가 얼마나 같은지
- rank(순위 일치): 스피어만 상관. 많이 말한 이유 순서가 같은지
칸마다 같이 내는 것 (판정에는 안 씀)
- coverage: 표본 커버리지(Chao 외 2014, incidence 자료). 그 칸 사람 이유를 몇 % 봤는지와, 목표 커버리지까지
  필요한 응답자 수
- human_equivalent: 사람 환산 인원. AI 답 분포가 사람 몇 명을 뽑았을 때만큼 사람 분포에 가까운지

입력
- 사람 코드 CSV (--human): 정리 담당이 사람 응답을 코드북으로 정리한 것. 응답 원문은 넣지 않는다
    respondent_id, service, platform, feature_id, kind(use|nouse|nouse_quit), code, order(선택. 응답 순서)
    nouse는 안 써본 사람(4-6, 4-7), nouse_quit은 써봤다가 그만둔 사람(4-5, 4-7). AI 안 쓸 이유는 nouse와 비교한다
    code가 빈 줄은 "그 칸에 답했지만 붙일 코드가 없음"이다. 사람 수에는 들어가고 이유에는 안 들어간다
- AI 코드 CSV (--ai): scripts/reason_sheet.py import가 만든 것
    item_id, run_id, service, platform, condition, persona_id, repeat, feature_id, kind, code
    (input_mode, model 칸이 있으면 한 조건 안에 다른 값이 섞였을 때 멈춘다)
- 판정 규칙 JSON (--rules): 기준값을 코드에 박지 않는다 (FR-08-01). 동결 전 규칙은 --allow-draft를 붙여야 돈다
- 코드북 CSV (--codebook, 선택): code, scope(common|feature|other|exclude, 공통|기능|기타|제외). 주면 공통 코드를 뺀
  통과율·재현율을 같이 낸다. 판정에는 안 쓰고 옆에 보여준다 (11/6 강선우 제안: AI가 기능을 보고 답했는지 숫자로 보이게)
    기타(C98, U98): 내용이 제각각이라 사람 기타와 AI 기타를 같은 이유로 맞았다고 세지 않는다 (코딩 규칙 v0.1)
    제외(C07, U05): 기능과 상관없는 이유. 그 사람은 칸 인원에 넣고 이유는 판정에서 빼서 따로 센다 (코딩 규칙 R2)
- 코드는 양쪽 다 같은 표기로 맞춘다 (전각 글자, 엑셀이 바꾼 대시, 대소문자)

판정 칸은 규칙 cell_keys로 정한다. 11/6 D4 결정으로 서비스 x 기능 x 쓸/안 쓸이고 앱·웹을 합친다.
- 합칠 때 AI는 매번 사람 A의 앱:웹 비율대로 플랫폼마다 따로 뽑는다. 비율이 다르면 합친 숫자가 플랫폼 차이에 끌려간다
- 플랫폼별 칸은 사람이 min_humans명 이상인 것만 참고로 낸다 (scope=platform_ref). 요약 판정 수에는 안 넣는다

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

KINDS = ("use", "nouse")  # AI 쪽
# 사람 쪽은 안 쓸 이유를 둘로 나눈다 (폼 B v2 210행). nouse: 안 써본 사람(4-6, 4-7), nouse_quit: 써봤다가 그만둔 사람(4-5, 4-7)
# AI 안 쓸 이유는 첫인상이라 nouse와 바로 비교하고, nouse_quit과는 참고로만 비교한다
HUMAN_KINDS = ("use", "nouse", "nouse_quit")
PLATFORMS = ("app", "web")
CONDITIONS = (0, 1, 2, 3)
METRICS = ("precision", "recall")  # 이유 종류가 겹치는지
FREQ_METRICS = ("dist", "rank")  # 이유를 얼마나 자주 말하는지 (사전등록 v1.1 추가안)
ALL_METRICS = METRICS + FREQ_METRICS
CELL_KEYS = ("service", "platform", "feature_id", "kind")
HUMAN_FIELDS = ["respondent_id", "service", "platform", "feature_id", "kind", "code"]
AI_FIELDS = ["item_id", "run_id", "service", "platform", "condition", "persona_id", "repeat", "feature_id", "kind",
             "code"]
RUN_FIELDS = ("input_mode", "model")  # 있으면 조건마다 하나여야 한다
DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u30fc"), "-")

LOW, NA, ASK, TRUST, REF = "자료 부족", "계산 불가", "사람에게 물어볼 것", "믿고 써도 됨", "참고용"
VERDICTS = (TRUST, REF, ASK, LOW, NA)

CELL_CSV = ["scope", "condition", "service", "platform", "feature_id", "kind", "n_humans", "n_humans_app",
            "n_humans_web", "ai_episodes", "ai_codes", "human_codes", "matched", "precision", "recall",
            "precision_nocommon", "recall_nocommon", "ai_codes_nocommon", "human_codes_nocommon",
            "ai_split_precision", "ai_split_recall",
            "human_precision_low", "human_precision_high", "human_recall_low", "human_recall_high",
            "floor_precision_low", "floor_precision_high", "floor_recall_low", "floor_recall_high",
            "verdict", "stable_at", "ai_platform_short",
            "dist", "rank", "ai_split_dist", "ai_split_rank", "human_dist_low", "human_dist_high",
            "human_rank_low", "human_rank_high", "floor_dist_high", "floor_rank_high",
            "perm_p_dist", "perm_p_rank", "coverage", "coverage_need", "coverage_need_reliable",
            "human_equiv_n", "human_equiv_ai_size", "human_equiv_bound"]
REASON_CSV = ["scope", "condition", "service", "platform", "feature_id", "kind", "type", "code", "name", "common",
              "ai_episodes_with_code", "ai_episodes", "human_count", "n_humans", "passed", "basis"]
CODEBOOK_FIELDS = ["code", "scope"]
SCOPE_WORDS = {"common": "common", "공통": "common", "feature": "feature", "기능": "feature",
               "other": "other", "기타": "other", "exclude": "exclude", "제외": "exclude"}
HUMAN_OTHER = "@사람"  # 사람 쪽 기타 코드에 붙여서 AI 기타와 겹치지 않게 한다
MAIN, PLATFORM_REF = "main", "platform_ref"


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


def check_common(rows: list, name: str, kinds: tuple = KINDS) -> None:
    for i, r in enumerate(rows, 2):
        if r["kind"] not in kinds:
            raise InputError(f"{name} {i}행: kind는 {' / '.join(kinds)} 중 하나")
        if r["platform"] not in PLATFORMS:
            raise InputError(f"{name} {i}행: platform은 app 또는 web")
        if not r["service"] or not r["feature_id"]:
            raise InputError(f"{name} {i}행: service와 feature_id는 비울 수 없음")
        r["code"] = norm_code(r["code"])
        if any(sep in r["code"] for sep in ",;"):
            raise InputError(f"{name} {i}행: 한 줄에 코드 하나만 넣는다 (코드가 여럿이면 줄을 나눈다)")


def load_human(path: Path) -> list:
    rows = read_csv(path, HUMAN_FIELDS)
    check_common(rows, path.name, HUMAN_KINDS)
    platform_of = {}
    for i, r in enumerate(rows, 2):
        if not r["respondent_id"]:
            raise InputError(f"{path.name} {i}행: respondent_id가 비었음")
        if r.get("order"):
            try:
                int(r["order"])
            except ValueError:
                raise InputError(f"{path.name} {i}행: order는 정수") from None
        # 폼 3-3(주로 어디서 쓰나)은 한 사람에 답 하나다. 앱·웹을 합칠 때 AI 비율을 이 값으로 맞춘다
        who = (r["service"], r["respondent_id"])
        if platform_of.setdefault(who, r["platform"]) != r["platform"]:
            raise InputError(f"{path.name} {i}행: 같은 응답자의 platform이 줄마다 다름")
    return rows


def load_codebook(path: Path) -> dict:
    """코드 -> common/feature/other/exclude. 화면에는 코드를 안 찍고 행 번호만 알린다."""
    book = {}
    for i, r in enumerate(read_csv(path, CODEBOOK_FIELDS), 2):
        code = norm_code(r["code"])
        scope = SCOPE_WORDS.get(r["scope"].strip().lower())
        if not code:
            raise InputError(f"{path.name} {i}행: code가 비었음")
        if scope is None:
            raise InputError(f"{path.name} {i}행: scope는 common(공통), feature(기능), other(기타), exclude(제외) 중 하나")
        if code in book:
            raise InputError(f"{path.name} {i}행: 앞에 나온 코드가 또 나옴")
        book[code] = scope
    if not book:
        raise InputError(f"{path.name}: 코드가 하나도 없음")
    return book


def apply_scopes(human: list, ai: list, codebook: dict) -> dict:
    """코드북의 기타·제외 코드를 계산 전에 바꾼다. 줄 수는 그대로 두고 바뀐 개수를 돌려준다.

    - 제외: 사람 줄은 코드를 비운다(그 칸에 답한 사람 수에는 들어간다). AI 줄은 이유 아님('-')으로 바꾼다
    - 기타: 사람 줄에만 HUMAN_OTHER를 붙인다. AI 기타는 통과 못 한 이유로, 사람 기타는 놓친 이유로 남는다
    """
    exclude = {c for c, s in codebook.items() if s == "exclude"}
    other = {c for c, s in codebook.items() if s == "other"}
    counts = {"excluded": {"human": Counter(), "ai": Counter()}, "other": {"human": Counter(), "ai": Counter()}}
    for side, rows in (("human", human), ("ai", ai)):
        for r in rows:
            code = r["code"]
            if code in exclude:
                counts["excluded"][side][code] += 1
                r["code"] = "" if side == "human" else "-"
            elif code in other:
                counts["other"][side][code] += 1
                if side == "human":
                    r["code"] = code + HUMAN_OTHER
    return {k: {side: dict(sorted(c.items())) for side, c in v.items()} for k, v in counts.items()}


def codebook_names(path: Path) -> dict:
    """코드북에 name 칸이 있으면 코드 -> 이름. 이유 표(reasons_*.csv)에 사람이 읽을 이름을 붙인다 (기말 데모)."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "name" not in (reader.fieldnames or []):
            return {}
        return {norm_code(r.get("code") or ""): (r.get("name") or "").strip() for r in reader}


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
    if not rules["metrics"] or not set(rules["metrics"]) <= set(ALL_METRICS):
        raise InputError(f"{path.name}: metrics는 {', '.join(ALL_METRICS)} 중에서 고른다")
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
    if not isinstance(rules.get("platform_reference", True), bool):
        raise InputError(f"{path.name}: platform_reference는 true 또는 false")
    target = rules.get("coverage_target", 0.9)
    if not isinstance(target, (int, float)) or not 0 < target < 1:
        raise InputError(f"{path.name}: coverage_target은 0과 1 사이")
    he = rules.get("human_equivalent", {"draws": 0})
    if not isinstance(he, dict) or not isinstance(he.get("draws"), int) or he["draws"] < 0:
        raise InputError(f"{path.name}: human_equivalent는 draws(0 이상 정수)를 담은 객체")
    return rules


def merge_rule(rules: dict, alt: dict) -> dict:
    """민감도 규칙 하나. 안 적은 값은 본 규칙을 따른다."""
    out = {"method": rules["method"], "level": rules["level"], "metrics": rules["metrics"],
           "perm": rules.get("perm", []), "min_humans": rules["min_humans"], **rules["fixed"]}
    out.update({k: v for k, v in alt.items() if k != "name"})
    return out


def check_rule(rule: dict, where: str) -> None:
    if rule.get("method") not in ("anchors", "fixed", "gate"):
        raise InputError(f"{where}: method는 anchors, fixed, gate 중 하나")
    if not rule.get("metrics") or not set(rule["metrics"]) <= set(ALL_METRICS):
        raise InputError(f"{where}: metrics는 {', '.join(ALL_METRICS)} 중에서 고른다")
    perm = rule.get("perm", [])
    if not isinstance(perm, list) or not set(perm) <= set(FREQ_METRICS) or not set(perm) <= set(rule["metrics"]):
        raise InputError(f"{where}: perm은 metrics에 든 {', '.join(FREQ_METRICS)} 중에서 고른다")
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


def counts_of(groups: dict, ids) -> Counter:
    """코드마다 그 코드를 말한 사람 수. 한 사람은 한 코드를 한 번만 센다."""
    out = Counter()
    for i in ids:
        out.update(groups[i])
    return out


def jsd_similarity(p: Counter, q: Counter):
    """분포 유사도 = 1 - 젠슨-섀넌 발산(밑 2라서 0~1). 코드마다 말한 횟수를 비율로 바꿔 잰다.
    같으면 1, 겹치는 코드가 없으면 0. 한쪽이 비면 None.
    코드 순서대로 더하고 반올림한다. 입력 순서가 달라도 같은 값이 나오게 (같은 시드 같은 결과)."""
    tp, tq = sum(p.values()), sum(q.values())
    if not tp or not tq:
        return None
    js = 0.0
    for c in sorted(set(p) | set(q)):
        a, b = p.get(c, 0) / tp, q.get(c, 0) / tq
        m = (a + b) / 2
        if a:
            js += a * math.log2(a / m) / 2
        if b:
            js += b * math.log2(b / m) / 2
    return round(min(1.0, max(0.0, 1 - js)), 12)


def _ranks(values: list) -> list:
    """같은 값은 평균 순위."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def rank_agreement(p: Counter, q: Counter):
    """순위 일치 = 스피어만 상관(-1~1). 두 쪽 중 한 쪽이라도 말한 코드로 재고, 안 말한 쪽은 0번으로 둔다.
    코드가 2개 미만이거나 한쪽 개수가 전부 같으면 순위가 없어서 None."""
    codes = sorted(set(p) | set(q))
    if len(codes) < 2 or not p or not q:
        return None
    x, y = _ranks([p.get(c, 0) for c in codes]), _ranks([q.get(c, 0) for c in codes])
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if not sxx or not syy:
        return None
    return round(sxy / math.sqrt(sxx * syy), 12)


def metric_values(pred: Counter, ref: Counter) -> dict:
    p, r = pr(set(pred), set(ref))
    return {"precision": p, "recall": r, "dist": jsd_similarity(pred, ref), "rank": rank_agreement(pred, ref)}


def sample_coverage(groups: dict, target: float = 0.9):
    """표본 커버리지 (Chao 외 2014, incidence 자료). 응답자 한 명을 표본 단위 하나로 보고 코드마다 말한 사람 수를 센다.
    T = 칸 응답자 수(코드가 없는 응답자 포함), U = 언급 수 합, Q1·Q2 = 한 명·두 명만 말한 코드 수
    추정 커버리지 = 1 - Q1/U x A,  A = (T-1)Q1 / ((T-1)Q1 + 2Q2),  Q2가 0이면 A = (T-1)(Q1-1) / ((T-1)(Q1-1) + 2)
    목표까지 필요한 응답자 수 = T + (log(U/Q1) + log(1 - 목표)) / log(A) - 1 을 올림 (iNEXT invChat.Sam과 같은 식)
    응답자 수의 두 배를 넘는 외삽은 덜 정확하다(Chao 외 2014)고 need_reliable로 표시한다."""
    t = len(groups)
    freq = Counter(c for codes in groups.values() for c in codes)
    u = sum(freq.values())
    if t < 2 or not u:
        return None
    q1 = sum(v == 1 for v in freq.values())
    q2 = sum(v == 2 for v in freq.values())
    if q1 == 0:
        a = 1.0
    elif q2 > 0:
        a = (t - 1) * q1 / ((t - 1) * q1 + 2 * q2)
    elif q1 > 1:
        a = (t - 1) * (q1 - 1) / ((t - 1) * (q1 - 1) + 2)
    else:
        a = 0.0
    est = 1 - q1 / u * a
    if est >= target:
        need = t
    elif 0 < a < 1:
        need = t + max(0, math.ceil((math.log(u / q1) + math.log(1 - target)) / math.log(a) - 1))
    else:
        need = None
    return {"estimate": rnd(est), "respondents": t, "incidences": u, "q1": q1, "q2": q2, "target": target,
            "need": need, "need_reliable": need is not None and need <= 2 * t}


# ---------------------------------------------------------------- 칸 만들기

def build_cells(human: list, ai: list, rules: dict, keys: list = None) -> tuple:
    keys = keys or rules["cell_keys"]
    drop = {norm_code(c) for c in rules["ai_drop_codes"]}
    humans = defaultdict(dict)  # 칸 -> {응답자: 코드 집합}
    platform_of = defaultdict(dict)  # 칸 -> {응답자: app/web}
    for r in human:
        key = tuple(r[k] for k in keys)
        codes = humans[key].setdefault(r["respondent_id"], set())
        platform_of[key][r["respondent_id"]] = r["platform"]
        if r["code"]:
            codes.add(r["code"])
    ai_cells = defaultdict(lambda: {"episodes": set(), "code_eps": defaultdict(set), "ep_codes": defaultdict(set),
                                    "persona_eps": defaultdict(set)})
    dropped = 0
    for r in ai:
        cell = ai_cells[(r["condition"], tuple(r[k] for k in keys))]
        cell["episodes"].add(r["run_id"])
        # 같은 페르소나 번호를 앱·웹, 두 서비스에서 따로 돌리니 (플랫폼, 서비스, 페르소나)를 한 사람으로 센다.
        # 서비스를 빼면 두 서비스를 합쳐 판정할 때 다른 서비스 답이 한 사람으로 묶인다 (사전등록 v1 6장)
        cell["persona_eps"][(r["platform"], r["service"], r["persona_id"])].add(r["run_id"])
        cell["ep_codes"].setdefault(r["run_id"], set())
        if r["code"] in drop:
            dropped += 1
            continue
        cell["code_eps"][r["code"]].add(r["run_id"])
        cell["ep_codes"][r["run_id"]].add(r["code"])
    return humans, platform_of, ai_cells, dropped


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


def _persona_platform(p) -> str:
    return p[0] if isinstance(p, tuple) else ""


def sample_ai_counts(cell: dict, need, rng: random.Random) -> Counter:
    """페르소나를 뽑고 페르소나마다 회차 하나의 코드만 센다. 사람 A와 같은 크기로 잰다.
    need가 {플랫폼: 인원}이면 플랫폼마다 그 인원씩 뽑는다 (사람 A의 앱:웹 비율). 정수면 플랫폼을 안 가린다.
    페르소나가 모자라면 있는 만큼 쓴다. 같은 페르소나의 반복은 서로 다른 사람으로 치지 않는다.
    반환은 코드마다 그 코드를 말한 페르소나 수다 (사람 쪽 counts_of와 같은 단위)."""
    if isinstance(need, int):
        need = {None: need}
    out = Counter()
    for plat in sorted(need, key=lambda x: x or ""):
        personas = sorted((p for p in cell["persona_eps"] if plat is None or _persona_platform(p) == plat),
                          key=str)
        for p in rng.sample(personas, min(need[plat], len(personas))):
            out.update(cell["ep_codes"][rng.choice(sorted(cell["persona_eps"][p]))])
    return out


def sample_ai(cell: dict, need, rng: random.Random) -> set:
    """sample_ai_counts의 코드 종류만."""
    return set(sample_ai_counts(cell, need, rng))


def split_draws(cond: int, key: tuple, groups: dict, aic: dict, partners: list, rules: dict,
                platform_of: dict = None) -> dict:
    """사람을 무작위로 반씩 나눠 B를 기준으로 사람 A, AI, 다른 기능 AI를 잰다.
    같은 B에 대고, AI 쪽도 A와 같은 인원으로 뽑아서 재야 크기가 맞는다. 앱·웹을 합친 칸에서는 A의 플랫폼
    비율대로 플랫폼마다 따로 뽑는다. 그 플랫폼 AI 페르소나가 모자란 뽑기 수는 ai_short_draws에 센다.
    나누기, AI 뽑기, 다른 기능 뽑기는 난수를 따로 써서 다른 칸 자료가 이 칸 나누기를 바꾸지 않게 한다."""
    ids = sorted(groups)
    draws = {f"{who}_{m}": [] for who in ("human", "ai", "floor") for m in ALL_METRICS}
    draws["ai_short_draws"] = 0
    if len(ids) < 2:
        return draws
    platform_of = platform_of or {}
    tag = f"{cond}|{'|'.join(key)}"
    rng = random.Random(f"{rules['seed']}|split|{tag}")
    rng_ai = random.Random(f"{rules['seed']}|ai|{tag}")
    rng_floor = random.Random(f"{rules['seed']}|floor|{tag}")
    have = Counter(_persona_platform(p) for p in aic["persona_eps"])
    half = len(ids) // 2
    for _ in range(rules["resamples"]):
        s = ids[:]
        rng.shuffle(s)
        a, b = counts_of(groups, s[:half]), counts_of(groups, s[half:])
        need = dict(Counter(platform_of.get(i, "") for i in s[:half]))
        if aic["persona_eps"] and any(n > have.get(p, 0) for p, n in need.items()):
            draws["ai_short_draws"] += 1
        ai_pred = sample_ai_counts(aic, need, rng_ai) if aic["persona_eps"] else None
        floor_pred = sample_ai_counts(rng_floor.choice(partners), need, rng_floor) if partners else None
        for who, pred in (("human", a), ("ai", ai_pred), ("floor", floor_pred)):
            vals = metric_values(pred, b) if pred is not None else dict.fromkeys(ALL_METRICS)
            for m in ALL_METRICS:
                draws[f"{who}_{m}"].append(vals[m])
    return draws


def perm_test(cond: int, key: tuple, groups: dict, aic: dict, rules: dict, platform_of: dict = None) -> dict:
    """빈도 지표의 층화 순열 검정 (사전등록 v1.1 추가안).
    귀무가설: 플랫폼마다 AI 페르소나와 사람은 같은 이유 분포에서 나왔다. 플랫폼을 블록으로 두고 그 안에서만
    AI·사람 꼬리표를 섞으니, 사람과 AI의 앱:웹 비율이 달라도 그 차이는 귀무분포에 그대로 들어간다.
    사람은 칸 전원, AI는 페르소나 전원을 쓰고 페르소나마다 회차 하나를 뽑아 한 사람으로 센다.
    매번 회차를 새로 뽑아 관측값을 재고, 같은 회차로 꼬리표를 섞은 값을 잰다. p = (1 + 섞은 값이 관측값 이하인
    횟수) / (1 + 횟수). 값이 작을수록 덜 비슷하다는 뜻이라 p가 작으면 AI 분포가 사람과 다르다는 증거다.
    회차가 여럿이면 관측값도 매번 달라져 검정이 조금 보수적으로 된다(덜 거른다)."""
    out = dict.fromkeys(FREQ_METRICS)
    ids = sorted(groups)
    personas = sorted(aic["persona_eps"], key=str)
    if not ids or not personas:
        return out
    platform_of = platform_of or {}
    rng = random.Random(f"{rules['seed']}|perm|{cond}|{'|'.join(key)}")
    strata = defaultdict(lambda: ([], []))  # 플랫폼 -> (사람, AI 페르소나)
    for i in ids:
        strata[platform_of.get(i, "")][0].append(i)
    for p_ in personas:
        strata[_persona_platform(p_)][1].append(p_)
    hits = dict.fromkeys(FREQ_METRICS, 0)
    valid = dict.fromkeys(FREQ_METRICS, 0)
    n = rules["resamples"]
    human_c = counts_of(groups, ids)
    eps = {p_: sorted(aic["persona_eps"][p_]) for p_ in personas}
    for _ in range(n):
        ai_sets = {p_: aic["ep_codes"][rng.choice(eps[p_])] for p_ in personas}
        ai_c = Counter()
        for p_ in personas:
            ai_c.update(ai_sets[p_])
        obs = {"dist": jsd_similarity(ai_c, human_c), "rank": rank_agreement(ai_c, human_c)}
        perm_h, perm_a = Counter(), Counter()
        for plat in sorted(strata):
            hs, ps = strata[plat]
            pool = [groups[i] for i in hs] + [ai_sets[p_] for p_ in ps]
            rng.shuffle(pool)
            for codes in pool[:len(ps)]:
                perm_a.update(codes)
            for codes in pool[len(ps):]:
                perm_h.update(codes)
        perm = {"dist": jsd_similarity(perm_a, perm_h), "rank": rank_agreement(perm_a, perm_h)}
        for m in FREQ_METRICS:
            if obs[m] is None or perm[m] is None:
                continue
            valid[m] += 1
            hits[m] += perm[m] <= obs[m]
    for m in FREQ_METRICS:
        out[m] = (1 + hits[m]) / (1 + valid[m]) if valid[m] else None
    return out


def human_equivalent(cond: int, key: tuple, groups: dict, aic: dict, rules: dict, platform_of: dict = None):
    """사람 환산 인원: 사람 A와 같은 인원으로 뽑은 AI 답이, 사람 몇 명을 뽑았을 때만큼 사람 B 분포에 가까운지.
    사람을 반씩 나눠 A에서 m명(1명부터 A 전원까지)을 뽑은 분포 유사도의 중앙값 곡선을 그리고,
    AI 분포 유사도 중앙값이 그 곡선과 처음 만나는 m을 선형으로 메워 낸다. 판정에는 안 쓴다.
    Huang 외(2025, "LLM은 사람 응답자 몇 명분인가")와 Broska 외(2025, 혼합 대상 설계의 유효 표본 크기)를
    우리 설계에 맞춘 대응이다. 두 방법은 AI가 같은 응답자의 답을 예측해야(짝) 쓰는데, 우리 AI 페르소나는
    응답자와 짝이 없어서 분포끼리 견준다."""
    draws_n = (rules.get("human_equivalent") or {}).get("draws", 0)
    ids = sorted(groups)
    if not draws_n or len(ids) < 4 or not aic["persona_eps"]:
        return None
    platform_of = platform_of or {}
    half = len(ids) // 2
    rng = random.Random(f"{rules['seed']}|equiv|{cond}|{'|'.join(key)}")
    curve = {m: [] for m in range(1, half + 1)}
    ai_sims = []
    for _ in range(draws_n):
        s = ids[:]
        rng.shuffle(s)
        a_ids, b = s[:half], counts_of(groups, s[half:])
        need = dict(Counter(platform_of.get(i, "") for i in a_ids))
        ai_sims.append(jsd_similarity(sample_ai_counts(aic, need, rng), b))
        acc = Counter()
        for m, i in enumerate(a_ids, 1):  # a_ids는 이미 섞인 순서라 앞 m명이 무작위 m명이다
            acc.update(groups[i])
            curve[m].append(jsd_similarity(acc, b))
    target = quantile(ai_sims, 0.5)
    pts = [(m, quantile(v, 0.5)) for m, v in sorted(curve.items())]
    pts = [(m, v) for m, v in pts if v is not None]
    if target is None or not pts:
        return None
    out = {"ai_size": half, "ai_similarity": rnd(target), "draws": draws_n,
           "curve": [[m, rnd(v)] for m, v in pts]}
    if target < pts[0][1]:
        return {**out, "n_equiv": None, "bound": "below"}  # 사람 1명보다 못함
    if target >= pts[-1][1]:
        return {**out, "n_equiv": pts[-1][0], "bound": "above"}  # A 전원 이상
    prev_m, prev_v = pts[0]
    for m, v in pts[1:]:
        if v >= target:
            frac = (target - prev_v) / (v - prev_v) if v > prev_v else 1.0
            return {**out, "n_equiv": rnd(prev_m + frac * (m - prev_m), 2), "bound": None}
        prev_m, prev_v = m, v
    return {**out, "n_equiv": pts[-1][0], "bound": "above"}


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
    if rule["method"] == "gate":
        return judge_gate(cell, rule, metrics)
    view = anchor_view(cell["draws"], rule["level"], metrics)
    perm = set(rule.get("perm", ()))
    pvals = cell.get("perm") or {}
    if any(view[m]["ai"] is None or (pvals.get(m) if m in perm else view[m]["human"]) is None for m in metrics):
        return NA
    # AI가 사람 이유를 거의 못 맞히면(중앙값 0, 순위 일치는 0 이하) 사람끼리 구간 아래쪽이 0이어도 믿지 않는다
    if any(view[m]["ai"] <= 0 for m in metrics):
        return ASK
    # 아무 기능에나 할 말과 구별이 안 되면 사람 범위에 들어도 믿지 않는다 (두 기준점이 겹칠 때 보수적으로)
    if any(view[m]["floor"] is not None and view[m]["ai"] <= view[m]["floor"][1] for m in metrics):
        return ASK
    # 비교할 다른 기능이 없으면 아무 기능에나 할 말인지 가릴 수 없어서 믿음 판정은 내지 않는다
    if any(view[m]["floor"] is None for m in metrics):
        return REF
    # 기본 지표: AI 중앙값이 사람끼리 구간 아래쪽 끝 이상. 순열 검정 지표(사전등록 v1.1 추가안): 플랫폼 안에서
    # 꼬리표를 섞은 검정의 p가 1 - level 이상, 곧 AI 이유 분포가 사람과 다르다는 증거가 없음
    alpha = round(1 - rule["level"], 10)  # 1 - 0.95가 0.05보다 조금 크게 계산되는 것을 막는다
    if all((pvals[m] >= alpha) if m in perm else (view[m]["ai"] >= view[m]["human"][0])
           for m in metrics):
        return TRUST
    return REF


def judge_gate(cell: dict, rule: dict, metrics: list) -> str:
    """기준점 검사 + 고정 문턱 (사전등록 v1 2장 gate_fixed_70). 1·2번(자료 부족, 계산 불가)은 judge가 먼저 본다.
    3. 다시 뽑기로 잰 중앙값이 0이면 물어볼 것  4. 중앙값이 아무 기능에나 할 말 구간 위쪽 끝 이하이면 물어볼 것
    5. 그 구간이 없으면 6~8번을 보되 믿고 써도 됨 대신 참고용  6~8. 에피소드 전체로 잰 값으로 고정 문턱
    3·4번 중앙값이나 6번 값이 계산 안 되면 계산 불가."""
    view = anchor_view(cell["draws"], rule["level"], metrics)
    full = [cell["full"][m] for m in metrics]
    if any(view[m]["ai"] is None for m in metrics) or any(v is None for v in full):
        return NA
    if any(view[m]["ai"] <= 0 for m in metrics):
        return ASK
    if any(view[m]["floor"] is not None and view[m]["ai"] <= view[m]["floor"][1] for m in metrics):
        return ASK
    if all(v >= rule["trust"] for v in full):
        verdict = TRUST
    elif all(v >= rule["reference"] for v in full):
        verdict = REF
    else:
        verdict = ASK
    if verdict == TRUST and any(view[m]["floor"] is None for m in metrics):
        return REF
    return verdict


def with_platform(keys: list) -> list:
    """플랫폼 참고 칸의 키. CELL_KEYS 순서를 지킨다."""
    return [k for k in CELL_KEYS if k in keys or k == "platform"]


def score_cells(human: list, ai: list, rules: dict, keys: list, codebook: dict = None, scope: str = MAIN) -> tuple:
    humans, platform_of, ai_cells, dropped = build_cells(human, ai, rules, keys)
    main_rule = merge_rule(rules, {})
    alts = [(a["name"], merge_rule(rules, a)) for a in rules["sensitivity"]]
    common = {c for c, s in (codebook or {}).items() if s == "common"}
    conditions = sorted({c for c, _ in ai_cells})
    all_keys = sorted(set(humans) | {k for _, k in ai_cells})
    cells = []
    for cond in conditions:
        for key in all_keys:
            groups = humans.get(key, {})
            if scope == PLATFORM_REF and len(groups) < rules["min_humans"]:
                continue  # 플랫폼별 칸은 사람이 하한 이상인 것만 참고로 낸다 (11/6 D4)
            plats = platform_of.get(key, {})
            aic = ai_cells.get((cond, key), {"episodes": set(), "code_eps": {}, "ep_codes": {}, "persona_eps": {}})
            ai_codes = set(aic["code_eps"])
            human_count = Counter(c for codes in groups.values() for c in codes)
            p, r = pr(ai_codes, set(human_count))
            # 전체 값의 빈도는 에피소드마다 센다 (반복 3회면 한 페르소나가 세 번까지). 다시 뽑기는 페르소나마다 한 회차
            ai_count = Counter(c for codes in aic["ep_codes"].values() for c in codes)
            partners = floor_partners(key, cond, ai_cells, keys)
            cell = {"scope": scope, "condition": cond, **dict(zip(keys, key)), "n_humans": len(groups),
                    "n_humans_app": sum(v == "app" for v in plats.values()),
                    "n_humans_web": sum(v == "web" for v in plats.values()),
                    "ai_episodes": len(aic["episodes"]), "ai_codes": sorted(ai_codes),
                    "human_codes": len(human_count), "matched": len(ai_codes & set(human_count)),
                    "full": {"precision": p, "recall": r, "dist": jsd_similarity(ai_count, human_count),
                             "rank": rank_agreement(ai_count, human_count)},
                    "floor_partners": len(partners),
                    "draws": split_draws(cond, key, groups, aic, partners, rules, plats)}
            # 공통 코드를 뺀 값. 판정에는 안 쓰고 옆에 보여준다. 코드북이 없으면 None
            if codebook is not None:
                ai_nc, h_nc = ai_codes - common, set(human_count) - common
                pn, rn = pr(ai_nc, h_nc)
                cell["nocommon"] = {"precision": pn, "recall": rn, "ai_codes": len(ai_nc), "human_codes": len(h_nc)}
            else:
                cell["nocommon"] = None
            cell["ai_platform_short"] = cell["draws"]["ai_short_draws"]
            cell["perm"] = perm_test(cond, key, groups, aic, rules, plats)
            cell["coverage"] = sample_coverage(groups, rules.get("coverage_target", 0.9))
            cell["human_equivalent"] = (human_equivalent(cond, key, groups, aic, rules, plats)
                                        if scope == MAIN else None)
            cell["verdict"] = judge(cell, main_rule)
            cell["sensitivity"] = {name: judge(cell, rule) for name, rule in alts}
            cell["stability"] = stability(cond, key, groups, ai_codes, rules)
            cell["reasons"] = [{"code": c, "ai_episodes_with_code": len(aic["code_eps"][c]),
                                "human_count": human_count.get(c, 0),
                                "common": (c in common) if codebook is not None else None,
                                "passed": human_count.get(c, 0) >= rules["reason_min_humans"]}
                               for c in sorted(ai_codes)]
            cell["missed"] = [{"code": c, "human_count": n,
                               "common": (c in common) if codebook is not None else None}
                              for c, n in sorted(human_count.items()) if c not in ai_codes]
            cells.append(cell)
    human_keys, ai_keys = set(humans), {k for _, k in ai_cells}
    coverage = {"both": len(human_keys & ai_keys), "human_only": len(human_keys - ai_keys),
                "ai_only": len(ai_keys - human_keys)}
    return cells, conditions, dropped, coverage, alts


def score(human: list, ai: list, rules: dict, codebook: dict = None) -> dict:
    keys = rules["cell_keys"]
    copies = []
    if any(r["kind"] == "nouse_quit" for r in human):
        # 그만둔 사람 칸에도 같은 AI 안 쓸 이유를 대 본다 (참고 비교)
        copies = [{**r, "kind": "nouse_quit"} for r in ai if r["kind"] == "nouse"]
    cells, conditions, dropped, coverage, alts = score_cells(human, ai + copies, rules, keys, codebook)
    drop = {norm_code(c) for c in rules["ai_drop_codes"]}
    dropped -= sum(r["code"] in drop for r in copies)  # 복사한 줄은 두 번 세지 않는다
    platform_ref = []
    if "platform" not in keys and rules.get("platform_reference", True):
        platform_ref = score_cells(human, ai + copies, rules, with_platform(keys), codebook, PLATFORM_REF)[0]
    return {"cells": cells, "platform_ref": platform_ref, "conditions": conditions, "dropped_ai_rows": dropped,
            "coverage": coverage, "saturation": saturation(human, rules),
            "summary": summarize(cells, conditions, alts, keys, platform_ref)}


def summarize(cells: list, conditions: list, alts: list, keys: list, platform_ref: list = ()) -> dict:
    out = {"verdicts": {}, "mean": {}, "mean_nocommon": {}, "above_condition0": {}, "sensitivity_changed": {}}
    for cond in conditions:
        mine = [c for c in cells if c["condition"] == cond and c.get("kind") != "nouse_quit"]  # 본 비교만
        out["verdicts"][cond] = {v: sum(c["verdict"] == v for c in mine) for v in VERDICTS}
        out["mean"][cond] = {m: mean([c["full"][m] for c in mine if c["verdict"] != LOW]) for m in METRICS}
        out["mean_nocommon"][cond] = {m: mean([c["nocommon"][m] for c in mine
                                               if c["verdict"] != LOW and c["nocommon"]]) for m in METRICS}
    if 0 in conditions:
        base = {tuple(c[k] for k in keys): c for c in cells if c["condition"] == 0}
        for cond in conditions:
            if cond == 0:
                continue
            higher = same = lower = 0
            for c in cells:
                b = base.get(tuple(c[k] for k in keys))
                if c["condition"] != cond or b is None or c["verdict"] == LOW or c.get("kind") == "nouse_quit":
                    continue
                x, y = c["full"]["precision"], b["full"]["precision"]
                if x is None or y is None:
                    continue
                higher += x > y
                same += x == y
                lower += x < y
            out["above_condition0"][cond] = {"higher": higher, "same": same, "lower": lower}
    for name, _ in alts:
        out["sensitivity_changed"][name] = sum(c["sensitivity"][name] != c["verdict"] for c in cells
                                               if c.get("kind") != "nouse_quit")
    quit_cells = [c for c in cells if c.get("kind") == "nouse_quit"]
    out["quit_reference"] = {cond: {v: sum(c["verdict"] == v for c in quit_cells if c["condition"] == cond)
                                    for v in VERDICTS} for cond in conditions} if quit_cells else {}
    ref = [c for c in platform_ref if c.get("kind") != "nouse_quit"]
    out["platform_reference"] = {cond: {v: sum(c["verdict"] == v for c in ref if c["condition"] == cond)
                                        for v in VERDICTS} for cond in conditions} if ref else {}
    out["ai_platform_short_cells"] = sum(c["ai_platform_short"] > 0 for c in cells)
    out["cells"] = len(cells)
    return out


# ---------------------------------------------------------------- 출력

def cell_json(cell: dict, rules: dict) -> dict:
    view = anchor_view(cell["draws"], rules["level"], list(ALL_METRICS))
    out = {k: v for k, v in cell.items() if k not in ("draws", "full", "nocommon")}
    for m in ALL_METRICS:
        out[m] = rnd(cell["full"][m])
    nc = cell["nocommon"]
    out["nocommon"] = ({"precision": rnd(nc["precision"]), "recall": rnd(nc["recall"]),
                        "ai_codes": nc["ai_codes"], "human_codes": nc["human_codes"]} if nc else None)
    out["anchors"] = {m: {"ai_split_median": rnd(view[m]["ai"]),
                          "human_interval": [rnd(x) for x in view[m]["human"]] if view[m]["human"] else None,
                          "floor_interval": [rnd(x) for x in view[m]["floor"]] if view[m]["floor"] else None}
                      for m in ALL_METRICS}
    return out


def cell_row(c: dict) -> dict:
    a = c["anchors"]

    def bound(m, who, i):
        return a[m][who][i] if a[m][who] else None

    nc = c["nocommon"] or {}
    cov = c.get("coverage") or {}
    he = c.get("human_equivalent") or {}
    return {"scope": c["scope"], "condition": c["condition"], **{k: c.get(k, "*") for k in CELL_KEYS},
            "n_humans": c["n_humans"], "n_humans_app": c["n_humans_app"], "n_humans_web": c["n_humans_web"],
            "ai_episodes": c["ai_episodes"], "ai_codes": len(c["ai_codes"]),
            "human_codes": c["human_codes"], "matched": c["matched"], "precision": c["precision"],
            "recall": c["recall"], "precision_nocommon": nc.get("precision"), "recall_nocommon": nc.get("recall"),
            "ai_codes_nocommon": nc.get("ai_codes"), "human_codes_nocommon": nc.get("human_codes"),
            "ai_split_precision": a["precision"]["ai_split_median"],
            "ai_split_recall": a["recall"]["ai_split_median"],
            "human_precision_low": bound("precision", "human_interval", 0),
            "human_precision_high": bound("precision", "human_interval", 1),
            "human_recall_low": bound("recall", "human_interval", 0),
            "human_recall_high": bound("recall", "human_interval", 1),
            "floor_precision_low": bound("precision", "floor_interval", 0),
            "floor_precision_high": bound("precision", "floor_interval", 1),
            "floor_recall_low": bound("recall", "floor_interval", 0),
            "floor_recall_high": bound("recall", "floor_interval", 1),
            "verdict": c["verdict"], "stable_at": c["stability"]["stable_at"],
            "ai_platform_short": c["ai_platform_short"],
            "dist": c["dist"], "rank": c["rank"],
            "ai_split_dist": a["dist"]["ai_split_median"], "ai_split_rank": a["rank"]["ai_split_median"],
            "human_dist_low": bound("dist", "human_interval", 0),
            "human_dist_high": bound("dist", "human_interval", 1),
            "human_rank_low": bound("rank", "human_interval", 0),
            "human_rank_high": bound("rank", "human_interval", 1),
            "floor_dist_high": bound("dist", "floor_interval", 1),
            "floor_rank_high": bound("rank", "floor_interval", 1),
            "perm_p_dist": rnd((c.get("perm") or {}).get("dist")),
            "perm_p_rank": rnd((c.get("perm") or {}).get("rank")),
            "coverage": cov.get("estimate"), "coverage_need": cov.get("need"),
            "coverage_need_reliable": yn(cov.get("need_reliable")) if cov else "",
            "human_equiv_n": he.get("n_equiv"), "human_equiv_ai_size": he.get("ai_size"),
            "human_equiv_bound": he.get("bound") or ""}


def yn(flag) -> str:
    return "" if flag is None else ("Y" if flag else "N")


def reason_rows(c: dict, names: dict = None) -> list:
    names = names or {}
    common = {"scope": c["scope"], "condition": c["condition"], **{k: c.get(k, "*") for k in CELL_KEYS},
              "ai_episodes": c["ai_episodes"], "n_humans": c["n_humans"]}
    rows = []
    for r in c["reasons"]:
        basis = (f"응답자 {c['n_humans']}명 중 {r['human_count']}명이 같은 이유를 말함" if r["human_count"]
                 else "응답자 중 이 이유를 말한 사람 없음")
        rows.append({**common, "type": "ai_reason", "code": r["code"], "name": names.get(r["code"], ""),
                     "common": yn(r["common"]),
                     "ai_episodes_with_code": r["ai_episodes_with_code"], "human_count": r["human_count"],
                     "passed": "Y" if r["passed"] else "N", "basis": basis})
    for r in c["missed"]:
        rows.append({**common, "type": "missed", "code": r["code"],
                     "name": names.get(r["code"].removesuffix(HUMAN_OTHER), ""),
                     "common": yn(r["common"]),
                     "ai_episodes_with_code": 0, "human_count": r["human_count"], "passed": "",
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
    print(f"  판정 칸    : {' x '.join(rules['cell_keys'])}")
    for cond in result["conditions"]:
        v = s["verdicts"][cond]
        mean = s["mean"][cond]
        print(f"  조건 {cond}     : " + ", ".join(f"{k} {v[k]}" for k in VERDICTS)
              + f" / 평균 통과율 {mean['precision']}, 평균 재현율 {mean['recall']}")
        nc = s["mean_nocommon"][cond]
        if result.get("codebook_used"):
            print(f"             공통 코드 뺀 평균 통과율 {nc['precision']}, 재현율 {nc['recall']} (판정에는 안 씀)")
    for cond, x in s["above_condition0"].items():
        print(f"  조건 {cond} vs 0: 통과율 높음 {x['higher']}, 같음 {x['same']}, 낮음 {x['lower']}")
    for cond, v in s.get("quit_reference", {}).items():
        print(f"  조건 {cond} 그만둔 사람 칸(참고): " + ", ".join(f"{k} {v[k]}" for k in VERDICTS))
    for cond, v in s.get("platform_reference", {}).items():
        print(f"  조건 {cond} 플랫폼별 칸(참고, 사람 {rules['min_humans']}명 이상만): "
              + ", ".join(f"{k} {v[k]}" for k in VERDICTS))
    if s.get("ai_platform_short_cells"):
        print(f"  AI 페르소나가 플랫폼 비율만큼 없어서 덜 뽑힌 칸: {s['ai_platform_short_cells']}개")
    for name, n in s["sensitivity_changed"].items():
        print(f"  민감도 {name}: 판정이 바뀐 칸 {n}개")
    for g in result["saturation"]:
        label = "/".join(str(g[k]) for k in rules["saturation"]["group_keys"])
        print(f"  포화 {label}: 응답자 {g['respondents']}명, 이유 {g['reasons']}개, "
              f"다 모음 {g['saturated_at'] if g['saturated_at'] else '아직'}")
    main_cells = [c for c in result["cells"] if c.get("kind") != "nouse_quit" and c.get("coverage")]
    if main_cells:
        target = rules.get("coverage_target", 0.9)
        short = sum(c["coverage"]["estimate"] < target for c in main_cells)
        print(f"  커버리지   : 사람 이유를 {target:.0%} 넘게 본 칸 {len(main_cells) - short}개, 못 미친 칸 {short}개 "
              "(판정에는 안 씀)")
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
    ap.add_argument("--codebook", help="코드북 CSV (code, scope). 주면 공통 코드 뺀 통과율·재현율을 같이 낸다")
    ap.add_argument("--allow-draft", action="store_true",
                    help="동결 전 규칙으로 시험 삼아 돌린다. 실제 응답에는 쓰지 않는다 (측정 원칙: 기준은 응답을 보기 전에 고정)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_USAGE
    paths = {"human": root / args.human, "ai": root / args.ai, "rules": root / args.rules}
    if args.codebook:
        paths["codebook"] = root / args.codebook
    for name, p in paths.items():
        if not p.is_file():
            print(f"[오류] 입력 파일 없음: --{name} {p.relative_to(root) if p.is_relative_to(root) else p}",
                  file=sys.stderr)
            return EXIT_USAGE
    try:
        rules = load_rules(paths["rules"])
        human, ai = load_human(paths["human"]), load_ai(paths["ai"])
        codebook = load_codebook(paths["codebook"]) if args.codebook else None
        if codebook is not None:
            # 정리 담당은 코드북 코드만 쓴다. 오타가 기능별 코드로 조용히 세지지 않게 멈춘다
            unknown = {r["code"] for r in human if r["code"] and r["code"] not in codebook}
            if unknown:
                raise InputError(f"사람 코드 중 코드북에 없는 코드가 {len(unknown)}개 있음")
            scope_counts = apply_scopes(human, ai, codebook)
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

    result = score(human, ai, rules, codebook)
    result["codebook_used"] = codebook is not None
    if human and not result["coverage"]["both"]:
        print("[입력 오류] 사람 칸과 AI 칸이 하나도 안 겹친다. service, platform, feature_id 글자를 확인한다 "
              "(service는 snapshot.json의 service 값)", file=sys.stderr)
        return EXIT_INPUT
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    scope = args.service or "all"
    run_id = f"score_{scope}_{stamp}_{os.getpid() % 10000}"
    cells = [cell_json(c, rules) for c in result["cells"]]
    ref_cells = [cell_json(c, rules) for c in result["platform_ref"]]
    drop = {norm_code(c) for c in rules["ai_drop_codes"]}
    ai_not_in_book = (len({r["code"] for r in ai if r["code"] not in drop and r["code"] not in codebook})
                      if codebook is not None else None)
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
        "codebook": ({"codes": len(codebook), "common": sum(s == "common" for s in codebook.values()),
                      "ai_codes_not_in_codebook": ai_not_in_book,
                      # 제외 코드(R2)는 판정에서 빼고 여기서만 센다. 기타 코드는 서로 맞았다고 세지 않는다
                      "excluded_codes": scope_counts["excluded"], "other_codes": scope_counts["other"]}
                     if codebook is not None else None),
        "summary": result["summary"],
        "saturation": result["saturation"],
        "cells": cells,
        "platform_reference_cells": ref_cells,
    }
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{scope}_{stamp}"
    (out / f"metrics_{tag}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    write_csv(out / f"cells_{tag}.csv", CELL_CSV, [cell_row(c) for c in cells + ref_cells])
    names = codebook_names(paths["codebook"]) if codebook is not None else {}
    write_csv(out / f"reasons_{tag}.csv", REASON_CSV,
              [r for c in cells + ref_cells for r in reason_rows(c, names)])
    print_summary(result, rules, run_id)
    if ai_not_in_book:
        print(f"  코드북에 없는 AI 코드 {ai_not_in_book}개는 기능별 코드로 셌다")
    if codebook is not None:
        ex = scope_counts["excluded"]
        if ex["human"] or ex["ai"]:
            print(f"  기능과 상관없는 이유(제외 코드)로 판정에서 뺀 줄: 사람 {sum(ex['human'].values())}, "
                  f"AI {sum(ex['ai'].values())} (metrics의 codebook.excluded_codes)")
    print(f"  출력: {args.out}/metrics_{tag}.json, cells_{tag}.csv, reasons_{tag}.csv")
    return EXIT_OK


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())

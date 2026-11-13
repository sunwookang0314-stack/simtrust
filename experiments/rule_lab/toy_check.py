"""손으로 만든 예로 가짜 AI 사다리 규칙(ladder_50)과 다른 규칙을 나란히 본다. 사전등록 v1.2 추가안 2장의 예다.

- 작성: 김민우, 2026-11-14
- 판정 계산기(scripts/score_reasons.py)를 그대로 부른다. 시뮬레이션(simulate.py)은 쓰지 않는다
- 칸: F1 안 쓸 이유. 공통 이유 C01, C02, C03, 기능 이유 F1-01, F1-02
- 사람 40명판: C01 14, F1-01 10, C02 8, F1-02 6, C03 2. 사람 13명판: C01 5, F1-01 3, C02 3, F1-02 2
- 사람은 3명 중 1명이 웹, AI는 페르소나 20명(앱 10, 웹 10). 한 명이 이유 하나
- F2는 "다른 기능에 한 답" 가짜를 만들려고 둔다

    python experiments/rule_lab/toy_check.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import score_reasons as sr  # noqa: E402

CODEBOOK = {"C01": "common", "C02": "common", "C03": "common", "F1-01": "feature", "F1-02": "feature",
            "F2-01": "feature", "F2-02": "feature"}
HUMANS = {40: [("C01", 14), ("F1-01", 10), ("C02", 8), ("F1-02", 6), ("C03", 2)],
          13: [("C01", 5), ("F1-01", 3), ("C02", 3), ("F1-02", 2)]}
AIS = {
    "사람 같은 AI": [("C01", 7), ("F1-01", 5), ("C02", 4), ("F1-02", 3), ("C03", 1)],
    "순위 뒤집힌 AI": [("C01", 1), ("F1-01", 3), ("C02", 4), ("F1-02", 5), ("C03", 7)],
    "공통 이유만 AI": [("C01", 12), ("C02", 6), ("C03", 2)],
    "반만 맞는 AI": [("C01", 4), ("F1-01", 2), ("C02", 2), ("F1-02", 2), ("Z1", 3), ("Z2", 3), ("Z3", 2), ("Z4", 2)],
    "30% 틀린 AI": [("C01", 5), ("F1-01", 4), ("C02", 3), ("F1-02", 2), ("Z1", 2), ("Z2", 2), ("Z3", 1), ("Z4", 1)],
    "기능 안 가리는 AI": [("C02", 7), ("C01", 4), ("F2-01", 5), ("F2-02", 3), ("C03", 1)],
}
F2 = [("C02", 7), ("C01", 4), ("F2-01", 5), ("F2-02", 3), ("C03", 1)]  # 사람과 AI가 F2에 한 답
OTHER_RULES = ("gate_fixed_70", "fixed_70", "main_dist", "main_rank")


def spread(spec):
    """[(코드, 명수)] -> 코드 목록. 코드가 플랫폼에 고르게 섞이게 번갈아 놓는다."""
    cols = [[c] * n for c, n in spec]
    out = []
    while any(cols):
        for col in cols:
            if col:
                out.append(col.pop())
    return out


def people(spec, web_every, tag):
    return [(f"{tag}{i:02d}", "web" if i % web_every == 0 else "app", c) for i, c in enumerate(spread(spec))]


def rows(n_humans, ai_spec):
    human = [{"respondent_id": i, "service": "s", "platform": p, "feature_id": f, "kind": "nouse", "code": c}
             for f, spec, tag in (("F1", HUMANS[n_humans], "R"), ("F2", F2, "Q")) for i, p, c in people(spec, 3, tag)]
    ai = [{"item_id": f"{f}{i}", "run_id": f"{f}{i}", "service": "s", "platform": p, "condition": 2,
           "persona_id": i, "repeat": "1", "feature_id": f, "kind": "nouse", "code": c}
          for f, spec in (("F1", ai_spec), ("F2", F2)) for i, p, c in people(spec, 2, "P")]
    return human, ai


def run(n_humans, name, **over):
    rules = json.loads((ROOT / "configs/rules.draft.json").read_text(encoding="utf-8"))
    rules.update({"human_equivalent": {"draws": 0}, "platform_reference": False, **over})
    human, ai = rows(n_humans, AIS[name])
    res = sr.score(human, ai, rules, CODEBOOK)
    return next(c for c in res["cells"] if c["feature_id"] == "F1")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for n in (40, 13):
        print()
        print(f"== 사람 {n}명 ==")
        for name in AIS:
            c = run(n, name)
            v = c["ladder_view"]
            dec = " ".join(f"{k}={x:.3f}" for k, x in v["decoys"].items() if x is not None)
            print(f"[{name}] ladder_50: {c['sensitivity']['ladder_50']}" + (f" ({v['why']})" if v["why"] else "")
                  + f" | 못 이긴 가짜 {v['lost']} | 틀린 이유 {v['wrong_below']}% 미만")
            print(f"    p_사람={v['p_human']:.3f} | {dec}")
            print("    다른 규칙: main=" + c["verdict"] + ", "
                  + ", ".join(f"{k}={c['sensitivity'][k]}" for k in OTHER_RULES))

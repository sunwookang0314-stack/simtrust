"""가짜 데이터로 사람 쪽 흐름을 처음부터 끝까지 돌리고, 기말 데모(#35) 화면용 견본 표를 만든다.

전부 가짜다. 실제 응답, 실제 AI 답, 외부 API를 쓰지 않는다.

흐름
1. 가짜 폼 응답 CSV (구글폼 응답 시트와 같은 칸, 서비스 2곳 x 40명)
2. scripts/form_to_sheet.py make   정리 시트
3. 가짜 정리: 만들 때 정한 코드를 두 정리 담당 칸에 채운다 (5%는 일부러 다르게)
4. scripts/form_to_sheet.py import  사람 코드 CSV
5. 가짜 AI 코드: 조건 0, 모델 셋 (사람 같은 모델, 반만 맞는 모델, 공통 이유만 말하는 모델)
6. scripts/score_reasons.py         모델마다 cells, reasons 표

    python experiments/demo_sample/make_demo_sample.py

결과는 experiments/demo_sample/out/ 에 남는다. 표 칸 설명은 README.md.
"""

import csv
import json
import random
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments" / "sample_size_sim"))
import form_to_sheet as fts  # noqa: E402
import score_reasons as sr  # noqa: E402
import simulate as sim  # noqa: E402  이유 분포는 사람 수 시뮬레이션과 같은 가정을 쓴다

SEED = "demo-20261106"
SERVICES = {"링커리어": "linkareer", "에브리커리어(캠퍼스픽)": "campuspick"}
PER_SERVICE = 40
STATE_P = [("자주 쓴다", 0.2), ("가끔 쓴다", 0.2), ("써봤는데 지금은 안 쓴다", 0.15), ("안 써봤다", 1 / 3),
           ("이 서비스에 있는지 모르겠다", 1 - 0.2 - 0.2 - 0.15 - 1 / 3)]
COMMON_NAMES = {"C1": "필요 없을 것 같음", "C2": "다른 앱이나 방법으로 해결", "C3": "쓰기 번거로워 보임",
                "C4": "써볼 생각을 안 해봄"}
NEVER_OPTION = {"C1": "나한테 필요 없을 것 같아서", "C2": "다른 앱이나 방법으로 해결해서",
                "C3": "쓰기 번거로워 보여서", "C4": "딱히 써볼 생각을 안 해봐서"}
QUIT_OPTION = {"C1": "나한테 필요 없어서", "C2": "다른 앱이나 방법으로 해결해서", "C3": "써보니 불편해서"}
USE_COMMON = {"UC1": "찾는 시간이 줄어듦", "UC2": "마감을 안 놓침"}
MODELS = {"model_a": ("same", "사람 같은 모델"), "model_b": ("half", "반만 맞는 모델"),
          "model_c": ("common_only", "공통 이유만 말하는 모델")}
NL = chr(10)


def feature_name_of(code: str, features: list) -> str:
    return dict(features)[code.split("-")[0]]


def codebook_rows(features: list) -> list:
    rows = [{"code": c, "scope": "common", "name": n} for c, n in COMMON_NAMES.items()]
    rows += [{"code": c, "scope": "common", "name": n} for c, n in USE_COMMON.items()]
    for fid, name in features:
        rows += [{"code": f"{fid}-{i}", "scope": "feature", "name": f"{name} 고유 이유 {i} (가짜)"} for i in range(1, 5)]
        rows += [{"code": f"{fid}-U{i}", "scope": "feature", "name": f"{name} 쓰는 이유 {i} (가짜)"} for i in (1, 2)]
        # 판정자가 새로 붙였다고 치는 코드. 사람은 안 쓴다
        rows += [{"code": f"{fid}-AI{i}", "scope": "feature", "name": f"AI만 말한 이유 {i} (가짜)"} for i in range(1, 5)]
    return rows


def use_dist(j: int, kind: str = "same") -> dict:
    fid = sim.FEATURES[j]
    dist = {"UC1": 0.3, "UC2": 0.2, f"{fid}-U1": 0.3, f"{fid}-U2": 0.2}
    if kind == "common_only":
        return {"UC1": 0.6, "UC2": 0.4}
    if kind == "half":
        out = {k: v * 0.5 for k, v in dist.items()}
        out.update({f"{fid}-AI{i}": 0.5 / 4 for i in range(1, 5)})
        return out
    return dist


def fake_responses(features: list, rng: random.Random) -> tuple:
    rows, truth = [], {}
    order = 0
    for shown in SERVICES:
        for _ in range(PER_SERVICE):
            order += 1
            r = {"타임스탬프": f"가짜 {order}", fts.Q_CONSENT: fts.CONSENT_YES, fts.Q_USED: "있다",
                 fts.Q_SERVICE: shown, fts.Q_PLATFORM: "앱" if rng.random() < sim.P_APP else "웹사이트"}
            why_use, why_not = [], []
            for j, (fid, name) in enumerate(features):
                state = rng.choices([s for s, _ in STATE_P], [p for _, p in STATE_P])[0]
                r[fts.grid_col(fts.Q_STATE, name)] = state
                r[fts.grid_col(fts.Q_QUIT, name)] = ""
                r[fts.grid_col(fts.Q_NEVER, name)] = ""
                kind = fts.STATE_KIND[state]
                if kind is None:
                    continue
                if kind == "use":
                    codes = sim.draw_reasons(use_dist(j), rng)
                else:
                    codes = sim.draw_reasons(sim.human_dist(j, sim.SHAPES["common60"]), rng)
                    if kind == "nouse_quit":
                        codes = [c for c in codes if c != "C4"] or ["C1"]  # 그만둔 사람에게는 "써볼 생각 안 함" 보기가 없다
                    option = NEVER_OPTION if kind == "nouse" else QUIT_OPTION
                    col = fts.Q_NEVER if kind == "nouse" else fts.Q_QUIT
                    r[fts.grid_col(col, name)] = ", ".join(option[c] for c in codes if c in option)
                truth[(order, fid)] = codes
                lines = [c for c in codes if not c.startswith(("C", "UC"))]
                for c in lines:
                    text = f"{name}: {c} 에 해당하는 가짜 답입니다."
                    (why_use if kind == "use" else why_not).append(text)
            r[fts.Q_WHY_USE] = NL.join(why_use) or "없음"
            r[fts.Q_WHY_NOT] = NL.join(why_not) or "없음"
            rows.append(r)
    return rows, truth


def fake_ai(model: str, kind: str, features: list, rng: random.Random) -> list:
    rows = []
    for service in SERVICES.values():
        for plat in ("app", "web"):
            for slot in range(1, 11):
                run_id = f"{model}-{service}-{plat}-{slot:02d}"
                for j, (fid, _) in enumerate(features):
                    for akind, dist in (("nouse", sim.ai_dist(j, sim.SHAPES["common60"], kind)),
                                        ("use", use_dist(j, kind))):
                        for c in sim.draw_reasons(dist, rng):
                            rows.append({"item_id": f"{run_id}-{fid}-{akind}-{c}", "run_id": run_id,
                                         "service": service, "platform": plat, "condition": 0,
                                         "persona_id": f"C0-{slot:02d}", "repeat": "1", "feature_id": fid,
                                         "kind": akind, "code": c, "input_mode": "text", "model": model})
    return rows


def write_csv(path: Path, fields: list, rows: list) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    rng = random.Random(SEED)
    features = fts.load_features(ROOT / "docs/ai-protocol/features.txt")
    work = Path(tempfile.mkdtemp(prefix="simtrust_demo_"))
    shutil.copytree(ROOT / "docs/ai-protocol", work / "docs/ai-protocol")
    shutil.copytree(ROOT / "configs", work / "configs")
    out_dir = ROOT / "experiments/demo_sample/out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1~2. 가짜 폼 응답 -> 정리 시트
    responses, truth = fake_responses(features, rng)
    cols = list(responses[0])
    write_csv(work / "responses.csv", cols, responses)
    service_map = ",".join(f"{k}={v}" for k, v in SERVICES.items())
    assert fts.main(["make", "--responses", "responses.csv", "--service-map", service_map, "--out", "coding"],
                    root=work) == 0
    sheet_path = next((work / "coding").glob("sheet_*.csv"))
    with sheet_path.open(encoding="utf-8-sig", newline="") as f:
        sheet = list(csv.DictReader(f))

    # 3. 가짜 정리: 만들 때 정한 코드. 두 번째 정리 담당은 5% 줄에서 코드 하나를 빠뜨린다
    for r in sheet:
        codes = truth[(int(r["order"]), r["feature_id"])]
        final = ";".join(codes)
        second = ";".join(codes[:-1]) if len(codes) > 1 and rng.random() < 0.05 else final
        r.update({"code_1": final, "code_2": second, "code_final": final})
    write_csv(work / "coding/filled.csv", fts.SHEET_FIELDS, sheet)
    write_csv(work / "codebook.csv", ["code", "scope", "name"], codebook_rows(features))

    # 4. 사람 코드 CSV
    assert fts.main(["import", "--sheet", "coding/filled.csv", "--codebook", "codebook.csv", "--out", "coding"],
                    root=work) == 0
    human_path = next((work / "coding").glob("human_codes_*.csv"))

    # 5~6. 모델마다 계산기
    summary = {}
    for model, (kind, label) in MODELS.items():
        ai = fake_ai(model, kind, features, rng)
        write_csv(work / f"ai_{model}.csv", sr.AI_FIELDS + ["input_mode", "model"], ai)
        assert sr.main(["--human", str(human_path.relative_to(work)), "--ai", f"ai_{model}.csv",
                        "--rules", "configs/rules.draft.json", "--codebook", "codebook.csv",
                        "--out", f"scoring_{model}", "--allow-draft"], root=work) == 0
        for prefix in ("cells", "reasons"):
            src = next((work / f"scoring_{model}").glob(f"{prefix}_all_*.csv"))
            shutil.copyfile(src, out_dir / f"{prefix}_{model}.csv")
        with (out_dir / f"cells_{model}.csv").open(encoding="utf-8-sig", newline="") as f:
            cells = [c for c in csv.DictReader(f) if c["scope"] == "main" and c["kind"] == "nouse"]
        summary[model] = {"label": label, "nouse_verdicts": dict(Counter(c["verdict"] for c in cells))}
    shutil.copyfile(work / "codebook.csv", out_dir / "codebook_fake.csv")
    (out_dir / "summary.json").write_text(json.dumps({"seed": SEED, "respondents_per_service": PER_SERVICE,
                                                      "models": summary}, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print("[견본] 안 쓸 이유 칸 판정 (서비스 2곳 x 기능 4개)")
    for model, s in summary.items():
        print(f"  {model} ({s['label']}): {s['nouse_verdicts']}")
    print(f"  출력: {out_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())

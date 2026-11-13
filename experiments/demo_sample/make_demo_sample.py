"""가짜 데이터로 사람 쪽 흐름을 처음부터 끝까지 돌리고, 기말 데모(#35, #44) 화면용 견본 표를 만든다.

전부 가짜다. 실제 응답, 실제 AI 답, 외부 API를 쓰지 않는다.
이유 코드는 코드북 v0.1(docs/codebook/코드북_초안.csv)의 코드를 그대로 쓴다 (11/12, #44).

흐름
1. 가짜 폼 응답 CSV (구글폼 응답 시트와 같은 칸, 서비스 2곳 x 40명)
2. scripts/form_to_sheet.py make   정리 시트
3. 가짜 정리: 만들 때 정한 코드를 두 정리 담당 칸에 채운다 (5%는 일부러 다르게)
4. scripts/form_to_sheet.py import  사람 코드 CSV
5. 가짜 AI 코드
   - 조건 0(페르소나 없음) 모델 셋: 사람 같은 모델, 반만 맞는 모델, 공통 이유만 말하는 모델
   - 조건 2 페르소나 AI: 바탕 모델 하나에 페르소나 10명, 반복 3번
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
import form_to_sheet as fts  # noqa: E402
import score_reasons as sr  # noqa: E402

SEED = "demo-20261112"
CODEBOOK = ROOT / "docs/codebook/코드북_초안.csv"
SERVICES = {"링커리어": "linkareer", "에브리커리어(캠퍼스픽)": "campuspick"}
PER_SERVICE = 40
P_APP = 0.7  # 사람 수 시뮬레이션과 같은 가정
P_TWO = 0.4  # 한 사람이 이유 2개를 대는 비율 (시뮬레이션과 같다)
COMMON_SHARE = 0.6  # 안 쓸 이유 중 공통 이유 비율 (시뮬레이션 common60과 같다)
REPEATS = 3  # 본실험과 같다. 계산기는 반복을 한 사람으로 묶는다
SLOTS = 10  # 서비스·플랫폼마다 페르소나(조건 0은 슬롯) 10명
STATE_P = [("자주 쓴다", 0.2), ("가끔 쓴다", 0.2), ("써봤는데 지금은 안 쓴다", 0.15), ("안 써봤다", 1 / 3),
           ("이 서비스에 있는지 모르겠다", 1 - 0.2 - 0.2 - 0.15 - 1 / 3)]
# 폼 4-6(안 써봄)과 4-5(그만둠) 보기 -> 코드북 v0.1 코드 (코드북 출처 칸)
NEVER_OPTION = {"C03": "쓰기 번거로워 보여서", "C01": "나한테 필요 없을 것 같아서",
                "C02": "다른 앱이나 방법으로 해결해서", "C04": "딱히 써볼 생각을 안 해봐서"}
QUIT_OPTION = {"C01": "나한테 필요 없어서", "C02": "다른 앱이나 방법으로 해결해서", "C03": "써보니 불편해서"}
# 가짜 사람은 아래 코드를 안 말한다고 정했다. 반만 맞는 모델이 이 코드를 대서 "응답자 중 말한 사람 없음"이 나온다
AI_ONLY_COMMON = {"nouse": ["C06"], "use": ["U04"]}
MODELS = {"model_a": (0, "same", "사람 같은 모델 (조건 0)"),
          "model_b": (0, "half", "반만 맞는 모델 (조건 0)"),
          "model_c": (0, "common_only", "공통 이유만 말하는 모델 (조건 0)"),
          "persona": (2, "persona", "바탕 모델 + 페르소나 10명 (조건 2)")}
NL = chr(10)


def load_codebook() -> list:
    with CODEBOOK.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        scope = sr.SCOPE_WORDS.get(r["scope"].strip().lower())
        kind = "nouse" if r["kind"].strip().startswith("안") else "use"
        out.append({"code": r["code"].strip(), "scope": scope, "kind": kind, "name": r["name"].strip()})
    return out


def weights(codes: list, base=(0.35, 0.25, 0.2, 0.12, 0.08), shift: int = 0) -> dict:
    """앞쪽 코드일수록 많이 나오게. shift만큼 돌려서 기능마다 1등이 다르게 한다."""
    w = [base[i % len(base)] for i in range(len(codes))]
    w = w[shift % len(w):] + w[:shift % len(w)] if w else w
    total = sum(w)
    return {c: x / total for c, x in zip(codes, w)}


def mix(parts: list) -> dict:
    out = {}
    for share, dist in parts:
        for c, v in dist.items():
            out[c] = out.get(c, 0) + share * v
    return out


class Book:
    """코드북 v0.1에서 기능·방향마다 사람이 대는 이유 분포를 만든다."""

    def __init__(self, rows: list):
        self.rows = rows
        self.names = {r["code"]: r["name"] for r in rows}
        self.option_codes = {"nouse": list(NEVER_OPTION), "use": []}

    def codes(self, kind: str, scope: str, fid: str = None) -> list:
        return [r["code"] for r in self.rows if r["kind"] == kind and r["scope"] == scope
                and (fid is None or r["code"].startswith(fid + "-"))]

    def feature_split(self, kind: str, fid: str) -> tuple:
        """기능 코드를 사람이 대는 것과 AI만 대는 것으로 나눈다. 3개 이상이면 마지막 하나를 AI만 대게 둔다."""
        f = self.codes(kind, "feature", fid)
        return (f[:-1], f[-1:]) if len(f) >= 3 else (f, [])

    def human(self, kind: str, j: int, fid: str) -> dict:
        common = [c for c in self.codes(kind, "common") if c not in AI_ONLY_COMMON[kind]]
        feat, _ = self.feature_split(kind, fid)
        other, exclude = self.codes(kind, "other"), self.codes(kind, "exclude")
        if kind == "nouse":
            parts = [(COMMON_SHARE, weights(common, shift=j)), (0.35, weights(feat))]
        else:
            # 쓰는 이유는 기능 코드가 없는 기능(F3)도 있어서 그때는 공통 이유로만 댄다
            parts = [(0.5, weights(common, shift=j)), (0.45, weights(feat))] if feat else \
                    [(0.95, weights(common, shift=j))]
        parts += [(0.03, weights(other))] if other else []
        parts += [(0.02, weights(exclude))] if exclude else []  # 기능과 상관없는 이유. 계산기가 판정에서 뺀다
        return mix([(s, d) for s, d in parts if d])

    def ai(self, kind: str, j: int, fid: str, model: str) -> dict:
        h = self.human(kind, j, fid)
        if model == "same":
            return h
        if model == "common_only":
            # 4-6 보기에 있는 흔한 이유만 말한다. 쓰는 이유는 공통 코드만
            pool = self.option_codes["nouse"] if kind == "nouse" else \
                [c for c in self.codes(kind, "common") if c not in AI_ONLY_COMMON[kind]]
            return weights(pool, shift=j)
        # half: 절반은 사람이 안 말하는 이유 (AI만 대는 공통·기능 코드와 기타)
        _, ai_feat = self.feature_split(kind, fid)
        ai_only = AI_ONLY_COMMON[kind] + ai_feat + self.codes(kind, "other")
        return mix([(0.5, h), (0.5, weights(ai_only))])

    def persona(self, kind: str, j: int, fid: str, rng: random.Random) -> dict:
        """페르소나마다 자주 대는 이유가 조금씩 다르다. 사람 분포에서 두 코드를 세 배로 키운다."""
        h = dict(self.human(kind, j, fid))
        for c in rng.sample(sorted(h), min(2, len(h))):
            h[c] *= 3
        return h


def draw(dist: dict, rng: random.Random) -> list:
    k = 2 if rng.random() < P_TWO else 1
    codes, w = list(dist), list(dist.values())
    out = []
    while len(out) < min(k, len(codes)):
        c = rng.choices(codes, w)[0]
        if c not in out:
            out.append(c)
    return out


def fake_responses(book: Book, features: list, rng: random.Random) -> tuple:
    rows, truth = [], {}
    order = 0
    for shown in SERVICES:
        for _ in range(PER_SERVICE):
            order += 1
            r = {"타임스탬프": f"가짜 {order}", fts.Q_CONSENT: fts.CONSENT_YES, fts.Q_USED: "있다",
                 fts.Q_SERVICE: shown, fts.Q_PLATFORM: "앱" if rng.random() < P_APP else "웹사이트"}
            why_use, why_not = [], []
            for j, (fid, name) in enumerate(features):
                state = rng.choices([s for s, _ in STATE_P], [p for _, p in STATE_P])[0]
                r[fts.grid_col(fts.Q_STATE, name)] = state
                r[fts.grid_col(fts.Q_QUIT, name)] = ""
                r[fts.grid_col(fts.Q_NEVER, name)] = ""
                kind = fts.STATE_KIND[state]
                if kind is None:
                    continue
                codes = draw(book.human("use" if kind == "use" else "nouse", j, fid), rng)
                if kind != "use":
                    if kind == "nouse_quit":  # 그만둔 사람에게는 "써볼 생각 안 함" 보기가 없다
                        codes = [c for c in codes if c != "C04"] or ["C01"]
                    option = NEVER_OPTION if kind == "nouse" else QUIT_OPTION
                    col = fts.Q_NEVER if kind == "nouse" else fts.Q_QUIT
                    r[fts.grid_col(col, name)] = ", ".join(option[c] for c in codes if c in option)
                    lines = [c for c in codes if c not in option]  # 보기에 없는 이유는 4-7 서술로 적었다고 친다
                else:
                    lines = codes
                truth[(order, fid)] = codes
                for c in lines:
                    text = f"{name}: {book.names.get(c, c)}에 해당하는 가짜 답입니다."
                    (why_use if kind == "use" else why_not).append(text)
            r[fts.Q_WHY_USE] = NL.join(why_use) or "없음"
            r[fts.Q_WHY_NOT] = NL.join(why_not) or "없음"
            rows.append(r)
    return rows, truth


def fake_ai(book: Book, model: str, condition: int, kind: str, features: list, rng: random.Random) -> list:
    rows = []
    for service in SERVICES.values():
        for plat in ("app", "web"):
            for slot in range(1, SLOTS + 1):
                pid = f"P{slot:02d}" if condition == 2 else f"C0-{slot:02d}"
                tilt = {}
                if kind == "persona":
                    tilt = {(j, fid, akind): book.persona(akind, j, fid, rng)
                            for j, (fid, _) in enumerate(features) for akind in ("nouse", "use")}
                for rep in range(1, REPEATS + 1):
                    run_id = f"{model}-{service}-{plat}-{pid}-r{rep}"
                    for j, (fid, _) in enumerate(features):
                        for akind in ("nouse", "use"):
                            dist = tilt[(j, fid, akind)] if kind == "persona" else book.ai(akind, j, fid, kind)
                            for c in draw(dist, rng):
                                rows.append({"item_id": f"{run_id}-{fid}-{akind}-{c}", "run_id": run_id,
                                             "service": service, "platform": plat, "condition": condition,
                                             "persona_id": pid, "repeat": str(rep), "feature_id": fid,
                                             "kind": akind, "code": c, "input_mode": "image", "model": model})
    return rows


def write_csv(path: Path, fields: list, rows: list) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    rng = random.Random(SEED)
    book = Book(load_codebook())
    features = fts.load_features(ROOT / "docs/ai-protocol/features.txt")
    work = Path(tempfile.mkdtemp(prefix="simtrust_demo_"))
    shutil.copytree(ROOT / "docs/ai-protocol", work / "docs/ai-protocol")
    shutil.copytree(ROOT / "configs", work / "configs")
    shutil.copyfile(CODEBOOK, work / "codebook.csv")
    out_dir = ROOT / "experiments/demo_sample/out"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # 1~2. 가짜 폼 응답 -> 정리 시트
    responses, truth = fake_responses(book, features, rng)
    write_csv(work / "responses.csv", list(responses[0]), responses)
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

    # 4. 사람 코드 CSV
    assert fts.main(["import", "--sheet", "coding/filled.csv", "--codebook", "codebook.csv", "--out", "coding"],
                    root=work) == 0
    human_path = next((work / "coding").glob("human_codes_*.csv"))

    # 5~6. 모델마다 계산기
    summary = {}
    for model, (condition, kind, label) in MODELS.items():
        ai = fake_ai(book, model, condition, kind, features, rng)
        write_csv(work / f"ai_{model}.csv", sr.AI_FIELDS + ["input_mode", "model"], ai)
        assert sr.main(["--human", str(human_path.relative_to(work)), "--ai", f"ai_{model}.csv",
                        "--rules", "configs/rules.draft.json", "--codebook", "codebook.csv",
                        "--out", f"scoring_{model}", "--allow-draft"], root=work) == 0
        for prefix in ("cells", "reasons"):
            src = next((work / f"scoring_{model}").glob(f"{prefix}_all_*.csv"))
            shutil.copyfile(src, out_dir / f"{prefix}_{model}.csv")
        with (out_dir / f"cells_{model}.csv").open(encoding="utf-8-sig", newline="") as f:
            cells = [c for c in csv.DictReader(f) if c["scope"] == "main" and c["kind"] == "nouse"]
        summary[model] = {"label": label, "condition": condition,
                          "ai_answers_per_service_platform": SLOTS * REPEATS,
                          "nouse_verdicts": dict(Counter(c["verdict"] for c in cells))}
    (out_dir / "summary.json").write_text(json.dumps({"seed": SEED, "codebook": "docs/codebook/코드북_초안.csv (v0.1)",
                                                      "respondents_per_service": PER_SERVICE,
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

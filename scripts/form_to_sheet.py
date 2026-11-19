"""폼 B v2 응답을 정리 시트와 사람 코드 CSV로 바꾼다 (정리 담당용).

구글폼 응답 시트를 CSV로 내려받아 넣는다. 외부 API를 부르지 않고 로컬에서만 돈다.
폼 문서 246행: 응답 시트는 정리 담당 2인과 폼 소유자만 본다. 이 스크립트도 그 사람들이 자기 PC에서 돌린다.
출력에 응답 원문이 들어가니 저장소 밖이나 private/(커밋 제외)에 둔다.

    count   서비스·플랫폼별 응답 수만 센다. 서술은 안 보여준다 (폼 소유자가 마감 인원 셀 때, 사전등록 v1 5장)
            --detail은 파일럿 사본 폼 CSV에만 쓴다(사전등록 v1 3장): 4-3 답 개수, 안 써본 비율, 4-5·4-6 보기 개수
    params  파일럿 사본 폼 응답과 코드북 작성자가 코드를 붙인 파일럿 사람 코드로 사전등록 3장 값을 낸다:
            안 써본 비율, 공통 이유 비율, 이유 2개 비율. 사람 수 시뮬레이션 --pilot에 그대로 넣는다
    make    정리 시트를 만든다. 응답자 x 기능마다 한 줄, 정리 담당 두 사람이 코드를 채운다
            서술을 이유 단위로 쪼갠 것(코딩 규칙 0장)은 code 칸에 ';'로 이어 적는다. 대체 수단·세부 유형(F4)은
            alt_means, subtype 칸에 코딩 규칙 v0.1 4장 값으로 적는다 (판정에는 안 쓰고 사람 코드 CSV에 같이 남긴다)
    import  다 채운 정리 시트를 판정 계산기가 읽는 사람 코드 CSV로 바꾼다

    python scripts/form_to_sheet.py count --responses <응답 CSV> --service-map "링커리어=linkareer,에브리커리어(캠퍼스픽)=campuspick"
    python scripts/form_to_sheet.py make --responses <응답 CSV> --service-map "..." --out private/coding
    python scripts/form_to_sheet.py import --sheet <채운 시트> --codebook <코드북 CSV> --out private/coding

폼 운영 규칙(폼 문서 243~245행, 판정계산기.md 2장)을 그대로 적용한다
- 동의하지 않은 응답, "최근 6개월 안에 써본 적" 없다면서 서비스를 고른 응답은 뺀다
- 4-3 "있는지 모르겠다"인 기능은 이유 문항이 없어서 시트에 안 넣고 개수만 센다
- 4-3과 안 맞는 4-5·4-6 체크(자주 쓴다면서 4-6에 체크 등)는 그 칸만 뺀다
- kind: 자주·가끔 쓴다 -> use (4-4), 안 써봤다 -> nouse (4-6, 4-7), 써봤는데 지금은 안 쓴다 -> nouse_quit (4-5, 4-7)

종료 코드: 0 정상, 1 입력 파일 없음·사용법, 4 입력 검증 실패 (이때는 아무것도 쓰지 않는다)
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_reasons as er  # noqa: E402  기능별 줄 나누기를 AI 답과 같은 규칙으로 한다
import reason_sheet as rsh  # noqa: E402  코드 칸 규칙(;, -)과 kappa를 판정 시트와 같게 쓴다
import score_reasons as sr  # noqa: E402

EXIT_OK, EXIT_USAGE, EXIT_INPUT = 0, 1, 4

# 생성 스크립트(docs/form-b/SimTrust-폼B-v2-생성.gs)의 문항 제목. 테스트가 생성 스크립트와 글자를 대조한다
Q_CONSENT = "설문 참여에 동의하시나요?"
Q_USED = "최근 6개월 안에 공모전·대회·인턴·취업 공고 서비스를 써보신 적이 있나요?"
Q_SERVICE = "이 중 가장 자주 쓰시는 서비스 한 곳을 골라주세요."
Q_PLATFORM = "주로 어디서 쓰시나요?"
Q_STATE = "아래 기능을 지금 어떻게 쓰고 계신가요?"
Q_WHY_USE = "자주 쓰거나 가끔 쓰는 기능은 왜 계속 쓰시나요?"
Q_QUIT = "써봤는데 지금은 안 쓰는 기능이 있다면, 안 쓰게 된 이유에 가까운 것을 골라주세요."
Q_NEVER = "한 번도 안 써본 기능이 있다면, 안 써본 이유에 가까운 것을 골라주세요."
Q_WHY_NOT = "안 쓰게 됐거나 안 써본 기능이 있다면, 그 이유를 조금 더 자세히 적어주세요."
CONSENT_YES, USED_NO = "동의합니다", "없다"
PLATFORM_OF = {"앱": "app", "웹사이트": "web"}
STATE_KIND = {"자주 쓴다": "use", "가끔 쓴다": "use", "써봤는데 지금은 안 쓴다": "nouse_quit",
              "안 써봤다": "nouse", "이 서비스에 있는지 모르겠다": None}
QUIT_OPTIONS = ["써보니 불편해서", "나한테 필요 없어서", "다른 앱이나 방법으로 해결해서", "기타"]
KIND_LABEL = {"use": "계속 씀 (4-4)", "nouse": "안 써봄 (4-6, 4-7)", "nouse_quit": "그만둠 (4-5, 4-7)"}

SHEET_FIELDS = ["row_id", "respondent_id", "order", "service", "platform", "feature_id", "feature_name", "kind",
                "kind_label", "options", "text_feature", "text_all", "code_1", "code_2", "code_final",
                *rsh.EXTRA_COLS, "note"]
HUMAN_FIELDS = ["respondent_id", "service", "platform", "feature_id", "kind", "code", "order", *rsh.EXTRA_COLS]
NONE_TEXT = re.compile(r"^\s*(없음|없어요|없습니다)\.?\s*$")


class InputError(Exception):
    pass


def read_csv(path: Path) -> tuple:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]


def load_features(path: Path) -> list:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            fid, name = line.split("|", 1)
            out.append((fid.strip(), name.strip()))
    return out


def load_lines(path: Path) -> list:
    return [x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def parse_service_map(text: str) -> dict:
    out = {}
    for pair in (text or "").split(","):
        if not pair.strip():
            continue
        if "=" not in pair:
            raise InputError("--service-map은 '폼 보기=스냅샷 service' 를 쉼표로 잇는다")
        shown, service = (x.strip() for x in pair.split("=", 1))
        out[shown] = service
    return out


def grid_col(title: str, row: str) -> str:
    return f"{title} [{row}]"


def check_columns(fields: list, features: list) -> None:
    need = [Q_CONSENT, Q_USED, Q_SERVICE, Q_PLATFORM, Q_WHY_USE, Q_WHY_NOT]
    for _, name in features:
        need += [grid_col(Q_STATE, name), grid_col(Q_QUIT, name), grid_col(Q_NEVER, name)]
    missing = [c for c in need if c not in fields]
    if missing:
        raise InputError(f"응답 CSV에 폼 B v2 문항 칸이 {len(missing)}개 없음 (첫 번째: {missing[0]}). "
                         "구글폼 응답 시트를 CSV로 내려받은 파일인지, 폼이 바뀌지 않았는지 확인한다")


def split_checks(cell: str, options: list, where: str) -> list:
    if not cell:
        return []
    picked = [x.strip() for x in re.split(r"[;,]", unicodedata.normalize("NFC", cell)) if x.strip()]
    unknown = [x for x in picked if x not in options]
    if unknown:
        raise InputError(f"{where}: 보기에 없는 값이 있음. 폼 보기가 바뀌었는지 확인한다")
    return picked


def read_responses(path: Path, features: list, options_46: list, service_map: dict = None) -> dict:
    """응답을 읽어 규칙을 적용한다. 반환: 응답자 목록과 센 숫자."""
    fields, rows = read_csv(path)
    check_columns(fields, features)
    counts = Counter()
    unknown_feature = Counter()
    people = []
    for i, r in enumerate(rows, 2):
        if r[Q_CONSENT] != CONSENT_YES:
            counts["동의 안 함"] += 1
            continue
        shown = r[Q_SERVICE]
        if r[Q_USED] == USED_NO:
            counts["앞뒤 안 맞음 (써본 적 없다면서 서비스를 고름)" if shown else "써본 적 없음"] += 1
            continue
        if not shown:
            counts["서비스 답 없음"] += 1
            continue
        platform = PLATFORM_OF.get(r[Q_PLATFORM])
        if platform is None:
            raise InputError(f"응답 CSV {i}행: '{Q_PLATFORM}' 값이 앱/웹사이트가 아님")
        service = service_map.get(shown) if service_map is not None else shown
        if service is None:
            counts["대조 서비스 아님"] += 1
            continue
        person = {"order": len(people) + 1, "service": service, "shown": shown, "platform": platform,
                  "why_use": r[Q_WHY_USE], "why_not": r[Q_WHY_NOT], "features": [], "states": {}}
        for fid, name in features:
            state = r[grid_col(Q_STATE, name)]
            if state not in STATE_KIND:
                raise InputError(f"응답 CSV {i}행: 4-3 [{fid}] 값이 보기에 없음")
            person["states"][fid] = state
            kind = STATE_KIND[state]
            quit_checks = split_checks(r[grid_col(Q_QUIT, name)], QUIT_OPTIONS, f"응답 CSV {i}행 4-5 [{fid}]")
            never_checks = split_checks(r[grid_col(Q_NEVER, name)], options_46, f"응답 CSV {i}행 4-6 [{fid}]")
            # 4-3과 안 맞는 체크는 그 칸만 뺀다 (폼 운영 규칙)
            if quit_checks and kind != "nouse_quit":
                counts["4-3과 안 맞아 뺀 4-5 칸"] += 1
                quit_checks = []
            if never_checks and kind != "nouse":
                counts["4-3과 안 맞아 뺀 4-6 칸"] += 1
                never_checks = []
            if kind is None:
                unknown_feature[fid] += 1
                continue
            person["features"].append({"feature_id": fid, "feature_name": name, "kind": kind,
                                       "options": quit_checks if kind == "nouse_quit" else never_checks})
        people.append(person)
    by_group = Counter((p["service"], p["platform"]) for p in people)
    return {"people": people, "excluded": dict(counts), "unknown_feature": dict(unknown_feature),
            "by_group": by_group, "rows": len(rows)}


def lines_by_feature(text: str, targets: list) -> dict:
    """서술 답을 기능별 줄로 나눈다. 추출기와 같은 규칙이다. 못 나눈 기능은 빈 목록."""
    if not text or NONE_TEXT.match(text) or not targets:
        return {fid: [] for fid, _ in targets}
    sole = targets[0][0] if len(targets) == 1 else None
    by_feature, _, _, _ = er.assign(text, targets, sole)
    return by_feature


def text_by_feature(text: str, targets: list) -> dict:
    """못 나누면 빈칸으로 두고 정리 담당이 원문을 본다."""
    return {fid: " / ".join(lines) for fid, lines in lines_by_feature(text, targets).items()}


def detail_counts(people: list, features: list, options_46: list) -> dict:
    """파일럿 숫자. 서술 원문은 안 남기고 개수만 센다.
    공통 이유 비율은 코드북으로 정리하기 전이라 대략값이다: 기타를 뺀 4-5·4-6 체크를 공통 이유로, 기능별로 나뉜
    서술 줄을 그 밖의 이유로 보고 센다. 서술에 체크와 같은 이유를 또 쓰면 공통 이유 비율이 실제보다 낮게 나온다."""
    n = len(people)
    states = {fid: Counter(p["states"][fid] for p in people) for fid, _ in features}
    never = {fid: Counter() for fid, _ in features}
    quit_ = {fid: Counter() for fid, _ in features}
    checks = lines = 0
    wrote = {"use": [0, 0], "not": [0, 0]}  # [서술을 쓴 사람, 그 문항을 받은 사람]
    for p in people:
        groups = {"use": [], "not": []}
        for f in p["features"]:
            groups["use" if f["kind"] == "use" else "not"].append((f["feature_id"], f["feature_name"]))
            target = never if f["kind"] == "nouse" else quit_ if f["kind"] == "nouse_quit" else None
            if target is not None:
                target[f["feature_id"]].update(f["options"])
                checks += sum(1 for o in f["options"] if o != "기타")
        for g, text in (("use", p["why_use"]), ("not", p["why_not"])):
            if groups[g]:
                wrote[g][1] += 1
                wrote[g][0] += int(bool(text) and not NONE_TEXT.match(text))
        split = lines_by_feature(p["why_not"], groups["not"])
        lines += sum(1 for fid in split for x in split[fid] if not er.STATUS.match(x))
    nouse_cells = sum(states[fid]["안 써봤다"] for fid, _ in features)
    return {"respondents": n, "states": {k: dict(v) for k, v in states.items()},
            "nouse_rate": round(nouse_cells / (n * len(features)), 3) if n else None,
            "nouse_rate_by_feature": {fid: round(states[fid]["안 써봤다"] / n, 3) if n else None for fid, _ in features},
            "options_4_6": {k: dict(v) for k, v in never.items()},
            "options_4_5": {k: dict(v) for k, v in quit_.items()},
            "wrote_4_4": wrote["use"], "wrote_4_7": wrote["not"],
            "common_checks": checks, "feature_lines": lines,
            "common_share_rough": round(checks / (checks + lines), 3) if checks + lines else None}


def print_detail(d: dict, features: list) -> None:
    print(f"[파일럿 숫자] 응답자 {d['respondents']}명. 서술 원문은 찍지 않는다")
    order = list(STATE_KIND)
    for fid, _ in features:
        st = d["states"][fid]
        print(f"  {fid} 4-3: " + ", ".join(f"{s} {st.get(s, 0)}" for s in order))
    for fid, _ in features:
        if d["options_4_6"][fid]:
            print(f"  {fid} 4-6: " + ", ".join(f"{o} {c}" for o, c in sorted(d["options_4_6"][fid].items())))
        if d["options_4_5"][fid]:
            print(f"  {fid} 4-5: " + ", ".join(f"{o} {c}" for o, c in sorted(d["options_4_5"][fid].items())))
    for label, (w, total) in (("4-4", d["wrote_4_4"]), ("4-7", d["wrote_4_7"])):
        print(f"  {label} 서술을 쓴 사람: {w}/{total}명 (나머지는 \"없음\")")
    print(f"  안 써본 비율: {d['nouse_rate']} (기능별 "
          + ", ".join(f"{k} {v}" for k, v in d["nouse_rate_by_feature"].items()) + ")")
    print(f"  공통 이유 비율 (참고용 대략값): {d['common_share_rough']} = 기타 뺀 체크 {d['common_checks']}개 / "
          f"(체크 {d['common_checks']}개 + 기능별 서술 줄 {d['feature_lines']}개)")
    print("  사전등록 3장의 공통 이유 비율과 이유 2개 비율은 4-7에 코드를 붙인 뒤 params로 잰다")


def build_sheet(people: list) -> list:
    rows = []
    for p in people:
        rid = f"R{p['order']:03d}"
        groups = {"use": [], "not": []}
        for f in p["features"]:
            groups["use" if f["kind"] == "use" else "not"].append((f["feature_id"], f["feature_name"]))
        split = {"use": text_by_feature(p["why_use"], groups["use"]),
                 "not": text_by_feature(p["why_not"], groups["not"])}
        for f in p["features"]:
            g = "use" if f["kind"] == "use" else "not"
            text_all = p["why_use"] if g == "use" else p["why_not"]
            rows.append({"row_id": f"{rid}-{f['feature_id']}", "respondent_id": rid, "order": p["order"],
                         "service": p["service"], "platform": p["platform"], "feature_id": f["feature_id"],
                         "feature_name": f["feature_name"], "kind": f["kind"], "kind_label": KIND_LABEL[f["kind"]],
                         "options": " / ".join(f["options"]), "text_feature": split[g].get(f["feature_id"], ""),
                         "text_all": "" if NONE_TEXT.match(text_all or "") else text_all,
                         "code_1": "", "code_2": "", "code_final": "", **dict.fromkeys(rsh.EXTRA_COLS, ""),
                         "note": ""})
    return rows


def print_counts(data: dict) -> None:
    print("=" * 60)
    print(f"[응답 수] 응답 CSV {data['rows']}줄, 시트에 넣을 응답자 {len(data['people'])}명")
    services = sorted({s for s, _ in data["by_group"]})
    for s in services:
        app, web = data["by_group"].get((s, "app"), 0), data["by_group"].get((s, "web"), 0)
        print(f"  {s}: {app + web}명 (앱 {app}, 웹 {web})")
    for k, v in sorted(data["excluded"].items()):
        print(f"  뺀 것 - {k}: {v}")
    if data["unknown_feature"]:
        print("  4-3 '있는지 모르겠다': " + ", ".join(f"{k} {v}명" for k, v in sorted(data["unknown_feature"].items())))
    print("=" * 60)


def common_inputs(args, root: Path) -> tuple:
    paths = {"responses": root / args.responses, "features": root / args.features, "options": root / args.options}
    for name, p in paths.items():
        if not p.is_file():
            raise FileNotFoundError(f"--{name}")
    return paths, load_features(paths["features"]), load_lines(paths["options"])


def cmd_count(args, root: Path) -> int:
    paths, features, options = common_inputs(args, root)
    service_map = parse_service_map(args.service_map) if args.service_map else None
    data = read_responses(paths["responses"], features, options, service_map)
    print_counts(data)
    if args.detail:
        print("  --detail은 파일럿 사본 폼 응답에만 쓴다. 본 응답에는 쓰지 않는다 (사전등록 v1 0·3장)")
        print_detail(detail_counts(data["people"], features, options), features)
    return EXIT_OK


def pilot_code_params(rows: list, codebook: dict) -> dict:
    """사전등록 3장: 응답자 x 기능 칸마다 4-6 보기와 4-7 코드를 합친 서로 다른 코드 묶음(nouse)으로 잰다.
    공통 이유 비율 = 칸 묶음 안 코드 중 공통 코드 비율. 이유 2개 비율 = 코드가 있는 칸 중 2개 이상인 칸 비율
    (3개 이상은 2개로 묶는다. 시뮬레이션이 1개나 2개만 뽑아서다).
    제외 코드(scope 제외, 예: C07)는 판정 계산기처럼 묶음에서 뺀다(코딩규칙 R2). 그 칸은 안 써본 칸으로는 세고,
    제외 코드만 있으면 코드가 없는 칸이 된다 (#43 강선우 지적)."""
    cells = {}
    excluded = 0
    for r in rows:
        if r["kind"] != "nouse":
            continue
        codes = cells.setdefault((r["service"], r["respondent_id"], r["feature_id"]), set())
        if r["code"] and codebook.get(r["code"]) == "exclude":
            excluded += 1
        elif r["code"]:
            codes.add(r["code"])
    coded = [c for c in cells.values() if c]
    total = sum(len(c) for c in coded)
    common = sum(1 for c in coded for x in c if codebook.get(x) == "common")
    return {"nouse_cells": len(cells), "coded_cells": len(coded), "codes": total, "common_codes": common,
            "common": round(common / total, 3) if total else None,
            "p_two": round(sum(len(c) >= 2 for c in coded) / len(coded), 3) if coded else None,
            "three_or_more": sum(len(c) >= 3 for c in coded), "excluded_codes": excluded}


def cmd_params(args, root: Path) -> int:
    paths, features, options = common_inputs(args, root)
    for name in ("human", "codebook"):
        if not (root / getattr(args, name)).is_file():
            raise FileNotFoundError(f"--{name}")
    service_map = parse_service_map(args.service_map) if args.service_map else None
    data = read_responses(paths["responses"], features, options, service_map)
    d = detail_counts(data["people"], features, options)
    codebook = sr.load_codebook(root / args.codebook)
    human = sr.load_human(root / args.human)
    unknown = {r["code"] for r in human if r["code"] and r["code"] not in codebook}
    if unknown:
        raise InputError(f"파일럿 사람 코드 중 코드북에 없는 코드가 {len(unknown)}개 있음")
    c = pilot_code_params(human, codebook)
    print(f"[파일럿 값] 응답자 {d['respondents']}명, 안 써본 칸 {c['nouse_cells']}개 중 코드가 있는 칸 {c['coded_cells']}개")
    print(f"  안 써본 비율 (4-3 \"안 써봤다\"만): {d['nouse_rate']}")
    print(f"  공통 이유 비율: {c['common']} = 공통 코드 {c['common_codes']}개 / 코드 {c['codes']}개")
    print(f"  이유 2개 비율: {c['p_two']} (3개 이상인 칸 {c['three_or_more']}개는 2개로 셌다)")
    print(f"  제외 코드: {c['excluded_codes']}개 (판정 계산기처럼 위 두 비율에서 뺐다)")
    parts = [f"{k}={v}" for k, v in (("p_nouse", d["nouse_rate"]), ("common", c["common"]), ("p_two", c["p_two"]))
             if v is not None]
    print(f"  시뮬레이션에 넣는 값: --pilot \"{','.join(parts)}\"  (사전등록 3장 규칙대로 가정을 더한다)")
    return EXIT_OK


def cmd_make(args, root: Path) -> int:
    paths, features, options = common_inputs(args, root)
    service_map = parse_service_map(args.service_map)
    if not service_map:
        raise InputError("make에는 --service-map이 필요하다 (계산기는 스냅샷 service 값으로 칸을 맞춘다)")
    data = read_responses(paths["responses"], features, options, service_map)
    if not data["people"]:
        raise InputError("시트에 넣을 응답자가 없음")
    rows = build_sheet(data["people"])
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    rsh.write_csv(out / f"sheet_{stamp}.csv", SHEET_FIELDS, rows)
    summary = {"created_at": datetime.now().isoformat(timespec="seconds"), "responses_rows": data["rows"],
               "respondents": len(data["people"]),
               "by_group": {f"{s}/{p}": n for (s, p), n in sorted(data["by_group"].items())},
               "excluded": data["excluded"], "unknown_feature": data["unknown_feature"],
               "sheet_rows": len(rows), "rows_by_kind": dict(Counter(r["kind"] for r in rows)),
               "rows_without_text_feature": sum(1 for r in rows if not r["text_feature"])}
    (out / f"sheet_{stamp}.summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    print_counts(data)
    print(f"  정리 시트 {len(rows)}줄. 기능별 서술이 비어 있는 줄 {summary['rows_without_text_feature']}개는 "
          "보기만 체크했거나 기능 이름 없이 써서 못 나눈 줄이다. text_all을 본다")
    print(f"  출력: {args.out}/sheet_{stamp}.csv  응답 원문이 들어 있다. 저장소에 올리지 않는다")
    return EXIT_OK


def cmd_import(args, root: Path) -> int:
    sheet_path = root / args.sheet
    if not sheet_path.is_file():
        raise FileNotFoundError("--sheet")
    fields, sheet = read_csv(sheet_path)
    missing = [c for c in SHEET_FIELDS if c not in fields and c not in rsh.EXTRA_COLS]  # 옛 시트도 받는다
    if missing:
        raise InputError(f"정리 시트에 칸이 없음 {missing}")
    codebook = sr.load_codebook(root / args.codebook) if args.codebook else None
    problems = []
    ids = [r["row_id"] for r in sheet]
    if len(set(ids)) != len(ids):
        problems.append(f"같은 row_id가 {len(ids) - len(set(ids))}번 더 있음")
    for col in rsh.JUDGE_COLS:
        blank = sum(not rsh.norm_codes(r[col]) for r in sheet)
        if blank:
            problems.append(f"{col} 빈칸 {blank}개 (붙일 코드가 없으면 -)")
        comma = sum("," in unicodedata.normalize("NFKC", r[col]) for r in sheet)
        if comma:
            problems.append(f"{col}에 쉼표 {comma}개 (코드가 여럿이면 ;로 나눈다)")
    problems += rsh.check_extras(sheet, lambda r: r["feature_id"])
    if codebook is not None:
        unknown = {c for r in sheet for c in rsh.norm_codes(r["code_final"]) if c != "-" and c not in codebook}
        if unknown:
            problems.append(f"code_final에 코드북에 없는 코드 {len(unknown)}개")
    if problems:
        raise InputError("정리 시트를 다 채우지 않았음: " + ", ".join(problems))
    a = [";".join(rsh.norm_codes(r["code_1"])) for r in sheet]
    b = [";".join(rsh.norm_codes(r["code_2"])) for r in sheet]
    k_value = rsh.kappa(a, b)
    low = k_value is None or k_value < rsh.KAPPA_MIN
    if low and not args.accept_low_kappa:
        raise InputError(f"두 정리 담당 kappa {k_value}가 {rsh.KAPPA_MIN}에 못 미친다. 코드북 정의를 맞추고 다시 "
                         "정리한다. 그대로 쓰려면 --accept-low-kappa \"사유\"를 붙인다")
    rows = []
    for r in sorted(sheet, key=lambda x: (int(x["order"] or 0), x["row_id"])):
        base = {k: r[k] for k in ("respondent_id", "service", "platform", "feature_id", "kind", "order")}
        base.update({c: ";".join(rsh.norm_extra(r.get(c))) for c in rsh.EXTRA_COLS})
        codes = [c for c in rsh.norm_codes(r["code_final"]) if c != "-"]
        # 붙일 코드가 없으면 code가 빈 줄 하나. 그 칸에 답한 사람 수에는 들어간다 (판정계산기.md 2장)
        for code in codes or [""]:
            rows.append({**base, "code": code})
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    rsh.write_csv(out / f"human_codes_{stamp}.csv", HUMAN_FIELDS, rows)
    report = {"created_at": datetime.now().isoformat(timespec="seconds"), "sheet_rows": len(sheet),
              "agreement": round(sum(x == y for x, y in zip(a, b)) / len(sheet), 4), "kappa": k_value,
              "kappa_min": rsh.KAPPA_MIN, "low_kappa_reason": args.accept_low_kappa if low else None,
              "code_rows": len(rows), "rows_without_code": sum(1 for r in rows if not r["code"]),
              "codebook_checked": codebook is not None}
    (out / f"human_agreement_{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    print(f"[가져오기] 시트 {len(sheet)}줄 -> 사람 코드 {len(rows)}줄 (코드 없음 {report['rows_without_code']})")
    print(f"  두 정리 담당 일치율 {report['agreement']}, kappa {k_value}")
    print(f"  출력: {args.out}/human_codes_{stamp}.csv  판정 계산기 --human에 넣는다")
    return EXIT_OK


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description="폼 B v2 응답 -> 정리 시트 -> 사람 코드 CSV")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("count", "make"):
        p = sub.add_parser(name)
        p.add_argument("--responses", required=True, help="구글폼 응답 시트를 CSV로 내려받은 파일")
        p.add_argument("--service-map", required=(name == "make"),
                       help="폼 보기=스냅샷 service, 쉼표로 잇는다. 예: 링커리어=linkareer")
        p.add_argument("--features", default="docs/ai-protocol/features.txt")
        p.add_argument("--options", default="docs/ai-protocol/options_4-6.txt", help="4-6 보기 파일")
        p.add_argument("--out", default="private/coding")
        if name == "count":
            p.add_argument("--detail", action="store_true",
                           help="파일럿 사본 폼에만: 4-3 답 개수, 안 써본 비율, 4-5·4-6 보기 개수, 서술 쓴 비율")
    p = sub.add_parser("params")
    p.add_argument("--responses", required=True, help="파일럿 사본 폼 응답 CSV")
    p.add_argument("--human", required=True, help="파일럿 정리 시트를 import한 사람 코드 CSV")
    p.add_argument("--codebook", required=True, help="코드북 CSV (code, scope)")
    p.add_argument("--service-map", help="폼 보기=스냅샷 service. 안 주면 모든 서비스를 센다")
    p.add_argument("--features", default="docs/ai-protocol/features.txt")
    p.add_argument("--options", default="docs/ai-protocol/options_4-6.txt", help="4-6 보기 파일")
    p = sub.add_parser("import")
    p.add_argument("--sheet", required=True)
    p.add_argument("--codebook", help="코드북 CSV (code, scope). 주면 코드북에 없는 코드에서 멈춘다")
    p.add_argument("--accept-low-kappa", metavar="사유")
    p.add_argument("--out", default="private/coding")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_USAGE
    try:
        return {"count": cmd_count, "make": cmd_make, "import": cmd_import, "params": cmd_params}[args.cmd](args, root)
    except FileNotFoundError as e:
        print(f"[오류] 입력 파일 없음: {e}", file=sys.stderr)
        return EXIT_USAGE
    except (InputError, sr.InputError, rsh.InputError, UnicodeDecodeError) as e:
        print(f"[입력 오류] {e}", file=sys.stderr)
        return EXIT_INPUT


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())

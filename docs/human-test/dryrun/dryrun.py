# 인터뷰 → 데이터화 설계 드라이런: 가짜 세션 3개로 원자료 → 정답지 → 매칭 → 지표까지 계산하고,
# 규칙이 바뀌는 시나리오에서 재수집 없이 재계산만으로 되는지 확인한다.
import copy, json

# ---------- 규칙 파일 (세션 뒤에도 바꿀 수 있는 것들) ----------
RULES = {
    "first_time_levels": ["없음", "둘러봄"],          # FR-05-02
    "time_cap_sec": 180,                               # FR-05-05 3분
    "types": {"기능을 못 찾음": "기능을 못 찾음", "용어를 이해 못 함": "용어를 이해 못 함",
              "흐름 중간에 막힘": "흐름 중간에 막힘", "취향·감성": "취향·감성"},  # 임시 유형 → 확정 유형
    "exclude_offsnapshot_from_recall": True,           # S? 이슈를 재현율 분모에서 뺄지
    "min_count": 5,                                    # 자료 부족 하한
    "thresholds": {"trust": 0.7, "ref": 0.5},
}
RANK = {"바로 함": 0, "헤매다 함": 1, "못 함": 2}

# ---------- 스냅샷 패키지 (도메인 슬롯: 과제·화면·정답 경로) ----------
EXPECTED_PATH = {("linkareer", "T1"): ["S1", "S2", "S3"], ("linkareer", "T2"): ["S1", "S4"],
                 ("campuspick", "T1"): ["S1", "S2", "S3"], ("campuspick", "T2"): ["S1", "S5"]}

# ---------- 세션에서 나온 원자료 ----------
participant_service = [  # 사용 경험은 3단계 원값 그대로, group은 계산
    {"pid": "P01", "service": "linkareer", "familiarity": "없음", "intent": 2, "current_use": None, "snapshot": "lk-1103"},
    {"pid": "P01", "service": "campuspick", "familiarity": "여러 번", "intent": None, "current_use": "그만둠", "snapshot": "cp-1103"},
    {"pid": "P02", "service": "linkareer", "familiarity": "둘러봄", "intent": 4, "current_use": None, "snapshot": "lk-1103"},
    {"pid": "P02", "service": "campuspick", "familiarity": "없음", "intent": 3, "current_use": None, "snapshot": "cp-1103"},
    {"pid": "P03", "service": "linkareer", "familiarity": "여러 번", "intent": None, "current_use": "자주", "snapshot": "lk-1103"},
    {"pid": "P03", "service": "campuspick", "familiarity": "없음", "intent": 1, "current_use": None, "snapshot": "cp-1103"},
]
participant_task = [  # 긴 형식: 과제 하나 = 한 줄. 결과 라벨은 저장하지 않고 신호만 저장
    {"pid": "P01", "service": "linkareer", "task": "T1", "completed": True, "time_sec": 70, "path": ["S1", "S2", "S3"], "ease": 6},
    {"pid": "P01", "service": "linkareer", "task": "T2", "completed": False, "time_sec": 180, "path": ["S1", "S3", "S1"], "ease": 2},
    {"pid": "P01", "service": "campuspick", "task": "T1", "completed": True, "time_sec": 40, "path": ["S1", "S2", "S3"], "ease": 7},
    {"pid": "P01", "service": "campuspick", "task": "T2", "completed": True, "time_sec": 50, "path": ["S1", "S5"], "ease": 6},
    {"pid": "P02", "service": "linkareer", "task": "T1", "completed": True, "time_sec": 150, "path": ["S1", "S6", "S1", "S2", "S3"], "ease": 3},
    {"pid": "P02", "service": "linkareer", "task": "T2", "completed": True, "time_sec": 95, "path": ["S1", "S4"], "ease": 5},
    {"pid": "P02", "service": "campuspick", "task": "T1", "completed": True, "time_sec": 60, "path": ["S1", "S2", "S3"], "ease": 6},
    {"pid": "P02", "service": "campuspick", "task": "T2", "completed": False, "time_sec": 180, "path": ["S1", "S?"], "ease": 1},
    {"pid": "P03", "service": "linkareer", "task": "T1", "completed": True, "time_sec": 30, "path": ["S1", "S2", "S3"], "ease": 7},
    {"pid": "P03", "service": "linkareer", "task": "T2", "completed": True, "time_sec": 45, "path": ["S1", "S4"], "ease": 6},
    {"pid": "P03", "service": "campuspick", "task": "T1", "completed": True, "time_sec": 120, "path": ["S1", "S2", "S2", "S3"], "ease": 4},
    {"pid": "P03", "service": "campuspick", "task": "T2", "completed": True, "time_sec": 160, "path": ["S1", "S4", "S1", "S5"], "ease": 3},
]
sessions = {"P01": {"sid": "P01-1103", "rec": True}, "P02": {"sid": "P02-1104", "rec": False},  # P02 녹음 실패
            "P03": {"sid": "P03-1104", "rec": True}}
# 단위 원자료: 막힌 순간·이유·괜찮았던 점 하나 = 한 줄. final_id는 2인이 합칠 때 붙인 ID
units = [
    {"kind": "issue", "pid": "P01", "service": "linkareer", "task": "T2", "screen": "S3", "t": "06:10", "tmp_type": "기능을 못 찾음",
     "expect": "상세에 알림 버튼", "actual": "스크랩만 있음", "action": "메인으로 돌아감", "final_id": "GI-1"},
    {"kind": "issue", "pid": "P01", "service": "linkareer", "task": "T2", "screen": "S3", "t": "07:20", "tmp_type": "기능을 못 찾음",
     "expect": "같은 문제 다시", "actual": "", "action": "", "final_id": "GI-1"},     # 같은 사람 같은 문제 두 번 → 1명으로 세야 함
    {"kind": "issue", "pid": "P02", "service": "linkareer", "task": "T1", "screen": "S6", "t": "", "tmp_type": "용어를 이해 못 함",
     "expect": "'큐레이션'이 공모전 목록", "actual": "기사 모음", "action": "뒤로 가기", "final_id": "GI-2"},   # 녹음 실패 → 시각 없음
    {"kind": "issue", "pid": "P02", "service": "campuspick", "task": "T2", "screen": "S?", "t": "", "tmp_type": "흐름 중간에 막힘",
     "expect": "알림 설정 화면", "actual": "앱 설치 유도", "action": "포기", "final_id": "GI-3"},    # 스냅샷 밖 화면
    {"kind": "issue", "pid": "P03", "service": "linkareer", "task": "T2", "screen": "S3", "t": "12:05", "tmp_type": "기능을 못 찾음",
     "expect": "알림 버튼", "actual": "없음", "action": "마이페이지 탐색", "final_id": "GI-1"},     # 써봄 참가자 → 정답지 사람 수에서 빠져야 함
    {"kind": "issue", "pid": "P03", "service": "campuspick", "task": "T1", "screen": "S2", "t": "21:40", "tmp_type": "흐름 중간에 막힘",
     "expect": "필터 적용", "actual": "새로고침", "action": "다시 선택", "final_id": "GI-4"},
    {"kind": "reason", "pid": "P01", "service": "linkareer", "q": "Q_neg", "t": "08:30", "summary": "알림 못 찾음", "final_id": "GR-1"},
    {"kind": "reason", "pid": "P02", "service": "linkareer", "q": "Q_pos", "t": "", "summary": "공고 많음", "final_id": "GR-2"},
    {"kind": "reason", "pid": "P01", "service": "campuspick", "q": "Q_quit", "t": "18:00", "summary": "에타에서 봄", "final_id": "GR-3"},
    {"kind": "reason", "pid": "P03", "service": "campuspick", "q": "Q_neg", "t": "24:10", "summary": "필터 불편", "final_id": "GR-4"},
    {"kind": "positive", "pid": "P02", "service": "campuspick", "screen": "S3", "t": "", "summary": "상세 정리 깔끔", "final_id": "GP-1"},
    {"kind": "positive", "pid": "P03", "service": "linkareer", "screen": "S2", "t": "13:00", "summary": "목록 필터 좋음", "final_id": "GP-2"},
]
Q_CATEGORY = {"Q_pos": "첫인상 긍정", "Q_neg": "첫인상 부정", "Q_keep": "계속 사용", "Q_quit": "실제 이탈"}

# ---------- 계산 ----------
def group_of(row, rules):
    return "처음" if row["familiarity"] in rules["first_time_levels"] else "써봄"

def result_of(t, rules):
    """결과 라벨은 저장값이 아니라 신호(완료, 시간, 경로)에서 규칙으로 계산"""
    if not t["completed"] or t["time_sec"] >= rules["time_cap_sec"]:
        return "못 함"
    return "바로 함" if t["path"] == EXPECTED_PATH[(t["service"], t["task"])] else "헤매다 함"

def build(rules):
    grp = {(r["pid"], r["service"]): group_of(r, rules) for r in participant_service}
    res = {(t["pid"], t["service"], t["task"]): result_of(t, rules) for t in participant_task}
    gt = {}
    for u in units:
        g = gt.setdefault(u["final_id"], {"id": u["final_id"], "kind": u["kind"], "service": u["service"],
                                           "screen": u.get("screen"), "who": set(), "who_all": set(), "worst": "바로 함", "src": []})
        g["who_all"].add(u["pid"])
        if u["kind"] == "issue":
            g["type"] = rules["types"][u["tmp_type"]]
            if grp[(u["pid"], u["service"])] == "처음":          # 사용성 정답지는 처음 쓴 응답만
                g["who"].add(u["pid"])
                r = res[(u["pid"], u["service"], u["task"])]
                g["worst"] = max(g["worst"], r, key=RANK.get)
        else:
            g["who"].add(u["pid"])
            if u["kind"] == "reason":
                g["category"] = Q_CATEGORY[u["q"]]
        sid = sessions[u["pid"]]["sid"]
        g["src"].append(f"{sid}@{u['t']}" if u["t"] else sid)    # 녹음 실패면 세션 ID만
    issues = [g for g in gt.values() if g["kind"] == "issue" and g["who"]]   # 처음 쓴 사람이 0명이면 정답지 이슈 아님
    return grp, res, issues, [g for g in gt.values() if g["kind"] == "reason"], [g for g in gt.values() if g["kind"] == "positive"]

# 가짜 AI 쪽: 가상 이슈와 2인 최종 판정
virtual = [{"vid": "VI-1", "service": "linkareer", "screen": "S3", "type": "기능을 못 찾음"},
           {"vid": "VI-2", "service": "linkareer", "screen": "S2", "type": "흐름 중간에 막힘"},
           {"vid": "VI-3", "service": "campuspick", "screen": "S2", "type": "흐름 중간에 막힘"},
           {"vid": "VI-4", "service": "campuspick", "screen": "S4", "type": "용어를 이해 못 함"}]
matches = {"VI-1": ("GI-1", None), "VI-2": (None, "허위 지적"),   # S2 필터는 P03이 괜찮다고 함(GP-2) → 허위 근거
           "VI-3": ("GI-4", None), "VI-4": (None, "판단 불가")}    # S4는 캠퍼스픽 T2 정답 경로 밖, 거의 안 지나감

def metrics(issues, rules):
    out = {}
    vt = {v["vid"]: rules["types"][v["type"]] for v in virtual}   # 같은 유형 매핑을 AI 쪽에도 적용
    for typ in sorted(set(vt.values()) | {g["type"] for g in issues}):
        vs = [v for v in virtual if vt[v["vid"]] == typ]
        gs = [g for g in issues if g["type"] == typ and not (rules["exclude_offsnapshot_from_recall"] and g["screen"] == "S?")]
        hit = sum(1 for v in vs if matches[v["vid"]][0])
        false = sum(1 for v in vs if matches[v["vid"]][1] == "허위 지적")
        matched_gt = {matches[v["vid"]][0] for v in vs if matches[v["vid"]][0]}
        p = hit / (hit + false) if (hit + false) else None
        r = len([g for g in gs if g["id"] in matched_gt]) / len(gs) if gs else None
        verdict = "자료 부족" if min(len(vs), len(gs)) < rules["min_count"] else "판정"
        out[typ] = {"가상": len(vs), "정답지": len(gs), "주정밀도": p, "재현율": r, "판정": verdict}
    return out

def show(title, rules):
    grp, res, issues, reasons, positives = build(rules)
    print(f"\n=== {title} ===")
    for g in issues:
        print(f"  {g['id']} {g['service']} {g['screen']} {g['type']} | 처음 쓴 사람 {len(g['who'])}명 (전체 {len(g['who_all'])}) | 최악 {g['worst']} | 출처 {g['src']}")
    for g in reasons:
        print(f"  {g['id']} {g['service']} {g['category']} | {len(g['who'])}명 | {g['src']}")
    for g in positives:
        print(f"  {g['id']} {g['service']} {g['screen']} 괜찮았던 점 | {g['src']}")
    print("  과제 결과:", {f"{k[0]}-{k[1][:2]}-{k[2]}": v for k, v in res.items()})
    for k, v in metrics(issues, rules).items():
        print(f"  지표 {k}: {v}")
    return grp, res, issues

# ---------- 기본 실행 + 변경 시나리오 ----------
base = show("기본 규칙", RULES)

r = copy.deepcopy(RULES); r["types"].update({"기능을 못 찾음": "탐색 실패", "흐름 중간에 막힘": "탐색 실패"})
show("시나리오 A: 유형 분류 변경(두 유형 합침) - 재인터뷰 없이 재계산", r)

r = copy.deepcopy(RULES); r["first_time_levels"] = ["없음"]
show("시나리오 B: '둘러봄'을 써봄으로 재분류", r)

r = copy.deepcopy(RULES); r["time_cap_sec"] = 150
show("시나리오 C: 판정 기준 변경(3분→2분30초)", r)

r = copy.deepcopy(RULES); r["exclude_offsnapshot_from_recall"] = False
show("시나리오 D: 스냅샷 밖(S?) 이슈를 재현율에 포함", r)

# 시나리오 E: 과제 3개 - 긴 형식이라 행만 추가하면 됨
EXPECTED_PATH[("linkareer", "T3")] = ["S1", "S7"]
participant_task.append({"pid": "P01", "service": "linkareer", "task": "T3", "completed": True, "time_sec": 60, "path": ["S1", "S7"], "ease": 6})
show("시나리오 E: 과제 T3 추가 (스키마 변경 없음)", RULES)

# 시나리오 F: 시장성 - 질문 ID에서 구분이 자동으로 나오는지, FR-09-04 표본 하한
_, _, _, reasons, _ = build(RULES)
quit_people = {p for g in reasons if g["category"] == "실제 이탈" for p in g["who"]}
print("\n=== 시나리오 F: 실제 이탈 이유 말한 사람", len(quit_people), "명 → 5명 미만이면 '표본 적음' ===")

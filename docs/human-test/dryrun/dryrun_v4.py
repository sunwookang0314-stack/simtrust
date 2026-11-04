# v4에서 새로 넣은 장치 4개가 재계산으로 도는지 확인하는 드라이런
import copy, hashlib, json

RULES = {
    "first_time_levels": ["없음", "둘러봄"],
    "churn_values": ["그만둠"],          # 실제 이탈로 칠 현재 사용 값 (TRD: 실제로 떠난 사람만)
    "exposure_k": 2,                     # 처음 그룹 k명 이상 지나간 화면에서 이슈 0건이면 허위 근거
    "time_cap_sec": 180,
}
def rules_hash(r):
    return hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
FROZEN = rules_hash(RULES)   # AI 본실험 전에 동결한 주 분석 버전

# 모집 설문(과제 보기 전): 사용 경험이 '없음'이 아닌 사람은 전원 현재 사용 + 이탈/계속 이유
form = {("P01", "lk"): {"fam": "없음"},
        ("P02", "lk"): {"fam": "둘러봄", "current": "그만둠", "why": "공고가 너무 많아 피곤"},
        ("P03", "lk"): {"fam": "여러 번", "current": "거의 안 씀", "why": "에타로 충분"},
        ("P04", "lk"): {"fam": "둘러봄", "current": "가끔", "why": "마감 정리용"}}
# 세션(과제 뒤): 그룹 상관없이 전원 의향 + 쓸 이유 + 안 쓸 이유, 결과 자기보고
session = {("P01", "lk"): {"intent": 2, "pos": "", "neg": "알림 못 찾음", "self": {"T1": "바로 함", "T2": "못 함"}},
           ("P02", "lk"): {"intent": 3, "pos": "공고 많음", "neg": "", "self": {"T1": "헤매다 함", "T2": "바로 함"}},
           ("P03", "lk"): {"intent": 4, "pos": "필터 좋음", "neg": "", "self": {"T1": "바로 함", "T2": "바로 함"}},
           ("P04", "lk"): {"intent": 4, "pos": "", "neg": "광고 많음", "self": {"T1": "바로 함", "T2": "헤매다 함"}}}
paths = {("P01", "lk", "T1"): ["S1", "S2", "S3"], ("P02", "lk", "T1"): ["S1", "S6", "S2", "S3"],
         ("P03", "lk", "T1"): ["S1", "S2", "S3"], ("P04", "lk", "T1"): ["S1", "S2", "S3"],
         ("P01", "lk", "T2"): ["S1", "S3"], ("P02", "lk", "T2"): ["S1", "S4"],
         ("P03", "lk", "T2"): ["S1", "S4"], ("P04", "lk", "T2"): ["S1", "S4"]}
gt_issue_screens = {"S3", "S6"}   # 정답지 이슈가 있는 화면
virtual = [("VI-1", "S3"), ("VI-2", "S2"), ("VI-5", "S8")]   # S8은 사람이 아무도 안 간 화면

def run(r, label):
    first = {k for k, v in form.items() if v["fam"] in r["first_time_levels"]}
    # 시장성: 그룹 기준이 바뀌어도 빈 칸이 생기지 않는지
    first_imp = [(k, session[k]["intent"]) for k in first]
    churn = [(k, form[k]["why"]) for k, v in form.items() if v.get("current") in r["churn_values"]]
    keep = [(k, form[k]["why"]) for k, v in form.items() if v.get("current") and v["current"] not in r["churn_values"]]
    # 화면 노출표: 처음 그룹이 지나간 사람 수
    expo = {}
    for (p, s, t), path in paths.items():
        if (p, s) in first:
            for scr in set(path):
                expo.setdefault(scr, set()).add(p)
    cls = {}
    for vid, scr in virtual:
        n = len(expo.get(scr, ()))
        cls[vid] = ("매칭 후보 있음" if scr in gt_issue_screens else
                    "사람 노출 없음(정밀도 제외)" if n == 0 else
                    f"허위 근거({n}명 지나감, 이슈 0)" if n >= r["exposure_k"] else f"판단 불가({n}명만 지나감)")
    h = rules_hash(r)
    print(f"\n=== {label} | 규칙 해시 {h} {'(주 분석)' if h == FROZEN else '(민감도 분석으로만 보고)'} ===")
    print("  처음 그룹 의향:", [(k[0], v) for k, v in first_imp])
    print("  실제 이탈 이유:", [(k[0], v) for k, v in churn])
    print("  계속 사용 이유:", [(k[0], v) for k, v in keep])
    print("  화면 노출(처음 그룹):", {k: len(v) for k, v in sorted(expo.items())})
    print("  AI 지적 분류 근거:", cls)
    print("  AI와 비교할 과제 결과(자기보고):", {k[0]: v["self"] for k, v in session.items() if k in first})

run(RULES, "주 분석")
r = copy.deepcopy(RULES); r["first_time_levels"] = ["없음"]
run(r, "둘러봄을 써봄으로 재분류 - 시장성 칸이 비지 않아야 함")
r = copy.deepcopy(RULES); r["churn_values"] = ["그만둠", "거의 안 씀"]
run(r, "이탈 정의 넓힘")

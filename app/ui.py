"""공통: 화면 목록(SCREENS), CSS, 헤더, 데모 상태, 다음 버튼, 칩."""
import streamlit as st

import demo_data as D

GROUPS = {1: "벤치마크 준비", 2: "시뮬레이션", 3: "판정", 4: "결과", 5: "새 MVP 점검"}
STEPS = {1: "준비", 2: "시뮬레이션", 3: "판정", 4: "결과", 5: "새 MVP"}
INTERNAL_GROUPS = {1, 2, 3, 4}

# 번호·ID·순서 고정. 메뉴, 단계 바, 다음 버튼, README 표가 모두 이 목록에서 나온다.
SCREENS = [
    dict(no="1-1", title="서비스·스냅샷", sid="ST-PR-1001", url="", path="views/p1_1_snapshot.py",   # 기본 페이지라 / 로 열림
         source="data/snapshots/{서비스}/snapshot.json", cmd="IF-03 register_snapshot.py",
         states=[("base", "기본"), ("E1", "E1 · 화면 변경 감지")]),
    dict(no="1-2", title="정답지", sid="ST-PR-1002", url="groundtruth", path="views/p1_2_groundtruth.py",
         source="data/groundtruth/*.csv", cmd="IF-07 import_groundtruth.py",
         states=[("base", "기본"), ("E2", "E2 · 녹취 없는 세션")]),
    dict(no="1-3", title="페르소나 세트", sid="ST-PR-1003", url="personas", path="views/p1_3_personas.py",
         source="data/personas/{서비스}/", cmd="IF-04 make_personas.py",
         states=[("base", "기본"), ("E3", "E3 · 후보 부족 중단")]),
    dict(no="2-1", title="실행 기록", sid="ST-SM-2001", url="runs", path="views/p2_1_runs.py",
         source="data/runs_summary.csv", cmd="IF-05 run_simulation.py",
         states=[("base", "기본"), ("E4", "E4 · 비용 상한 도달")]),
    dict(no="2-2", title="이슈 카드", sid="ST-SM-2002", url="issue-cards", path="views/p2_2_issue_cards.py",
         source="data/virtual/issue_cards.jsonl", cmd="IF-06 extract_responses.py",
         states=[("base", "목록"), ("detail", "상세"), ("E5", "E5 · 지적 없음·파싱 실패")]),
    dict(no="3-1", title="가상 이슈 묶기", sid="ST-JD-3001", url="grouping", path="views/p3_1_grouping.py",
         source="data/eval/virtual_issues.csv", cmd="IF-08·09",
         states=[("base", "기본")]),
    dict(no="3-2", title="이슈 매칭 판정", sid="ST-JD-3002", url="matching", path="views/p3_2_matching.py",
         source="data/eval/matches.csv", cmd="IF-08·09",
         states=[("base", "기본"), ("E6", "E6 · CSV 검증 실패"), ("E7", "E7 · 일치도 미달")]),
    dict(no="4-1", title="지표 대시보드", sid="ST-RP-4001", url="dashboard", path="views/p4_1_dashboard.py",
         source="data/eval/metrics_{서비스}_c{조건}.json", cmd="IF-10 compute_metrics.py",
         states=[("base", "기본"), ("E8", "E8 · 계산 불가 칸")]),
    dict(no="4-2", title="신뢰도 지도", sid="ST-RP-4002", url="trust-map", path="views/p4_2_trust_map.py",
         source="data/eval/metrics_all_c{조건}.json", cmd="IF-10·11", founder=True,
         states=[("base", "기본"), ("c0", "조건 0과 비교")]),
    dict(no="4-3", title="시장성 비교", sid="ST-RP-4003", url="market", path="views/p4_3_market.py",
         source="data/eval/reason_matches.csv", cmd="IF-13·10",
         states=[("base", "기본"), ("E10", "E10 · 표본 적음")]),
    dict(no="5-1", title="점검 결과", sid="ST-MV-5001", url="mvp-check", path="views/p5_1_mvp_check.py",
         source="새 스냅샷 결과 + 신뢰도 지도", cmd="IF-12 check_mvp.py", founder=True,
         states=[("base", "기본"), ("E11", "E11 · 유형 다름")]),
]
BY_NO = {s["no"]: s for s in SCREENS}
for s in SCREENS:
    s["group"] = int(s["no"][0])

VERDICT_COLOR = {
    "믿고 써도 됨": "#D6F0DD",
    "참고용": "#FCEBB6",
    "사람에게 물어볼 것": "#F8D3D3",
    "자료 부족": "#E6E8EC",
}
RESULT_COLOR = {"바로 함": "#D6F0DD", "헤매다 함": "#FCEBB6", "못 함": "#F8D3D3"}

CSS = """
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stAppDeployButton, #MainMenu, footer {display: none !important;}
.block-container {padding-top: 0.6rem; padding-bottom: 1rem; max-width: 1240px;}
h1 {font-size: 1.55rem !important; padding: 0 !important;}
.st-crumb {font-size: 0.75rem; color: #6B7684; text-align: right; margin-bottom: -1.6rem;}
.st-id {font-size: 0.8rem; color: #9AA4B2; font-weight: 500; margin-left: 8px;}
.st-src {font-family: ui-monospace, Menlo, monospace; font-size: 0.74rem; color: #8A94A3; margin: -0.3rem 0 0.5rem;}
.st-step {padding: 5px 0; text-align: center; font-size: 0.8rem; border-radius: 4px;
          background: #2F4B7C; color: #fff; font-weight: 600;}
.st-chip {display: inline-block; padding: 2px 9px; border-radius: 4px; font-size: 0.78rem;
          font-weight: 600; margin-right: 6px; white-space: nowrap;}
.st-badge {display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 0.7rem;
           font-weight: 600; vertical-align: middle; background: #FBE5D6; color: #A4471A; margin-left: 6px;}
.st-note {font-size: 0.8rem; color: #6B7684;}
.st-grey {color: #9AA4B2;}
.st-ph {height: 92px; border: 1px dashed #C3CAD5; border-radius: 6px; background: #F3F5F8; color: #9AA4B2;
        display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 0.75rem;}
.st-ph b {color: #4A5565; font-size: 0.85rem;}
[data-testid="stSidebar"] [data-testid="stPageLink"] p {font-size: 0.86rem;}
[data-testid="stMetricValue"] {font-size: 1.5rem;}
.st-stack {display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 0.78rem;}
.st-stack > span {width: 128px; color: #4A5565;}
.st-stack > div {flex: 1; display: flex; height: 24px; border-radius: 4px; overflow: hidden;}
.st-stack > div > div {display: flex; align-items: center; justify-content: center; white-space: nowrap;
                       overflow: hidden; color: #1F2933;}
table.st-table {width: 100%; border-collapse: collapse; font-size: 0.84rem; margin-bottom: 0.3rem;}
table.st-table th {text-align: left; font-weight: 500; color: #6B7684; background: #F3F5F8; padding: 6px 8px;
                   border-bottom: 1px solid #D5DAE1;}
table.st-table td {padding: 6px 8px; border-bottom: 1px solid #E6E9EF; vertical-align: top;}
[data-testid="stSidebar"] div[data-testid="stPageLink"] {margin-bottom: -0.4rem;}
.st-demo {float: right; font-family: sans-serif; font-size: 0.75rem; color: #B0613A;}
[data-testid="stMain"] [data-testid="stPageLink"] a {border: 1px solid #D5DAE1; border-radius: 4px;
    justify-content: center; padding: 1px 0;}
</style>
"""


def capture() -> bool:
    return st.session_state.get("capture", False)


def service() -> str:
    """사이드바에서 고른 서비스. '전체'면 None."""
    s = st.session_state.get("svc", "전체")
    return None if s == "전체" else s


def cond() -> int:
    return st.session_state.get("cond", 2)


def cond_label(c: int) -> str:
    return f"조건 {c} · {D.CONDITIONS[c]['name']}"


# ---------------------------------------------------------------- 데모 상태
def demo_state_selector(no: str):
    """사이드바 데모 상태 선택기. 화면에 처음 들어올 때 ?state= 쿼리에서 초기값을 읽는다."""
    ss = st.session_state
    codes = [c for c, _ in BY_NO[no]["states"]]
    labels = dict(BY_NO[no]["states"])
    if ss.get("_page") != no:
        ss["_page"] = no
        q = st.query_params.get("state")
        ss["_state"] = q if q in codes else codes[0]
    if len(codes) > 1 and not capture():
        st.selectbox("데모 상태", codes, index=codes.index(ss["_state"]), format_func=labels.get,
                     key=f"_sel-{no}", on_change=lambda: ss.update(_state=ss[f"_sel-{no}"]))
    if ss["_state"] == codes[0]:
        st.query_params.pop("state", None)
    else:
        st.query_params["state"] = ss["_state"]


def state() -> str:
    return st.session_state.get("_state", "base")


# ---------------------------------------------------------------- 헤더 · 다음
def chip(text: str, bg: str = "#E6E9EF", fg: str = "#1F2933") -> str:
    return f'<span class="st-chip" style="background:{bg};color:{fg}">{text}</span>'


def verdict_chip(v: str) -> str:
    return chip(v, VERDICT_COLOR[v])


def html(s: str, container=st):
    container.markdown(s, unsafe_allow_html=True)


def table(df, cell_style=None, container=st):
    """줄바꿈되는 HTML 표. cell_style(row, col) -> CSS 문자열."""
    head = "".join(f"<th>{c}</th>" for c in df.columns)
    body = "".join("<tr>" + "".join(
        f'<td style="{cell_style(row, c) if cell_style else ""}">{row[c]}</td>' for c in df.columns) + "</tr>"
        for _, row in df.iterrows())
    html(f'<table class="st-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>', container)


def header(no: str):
    s = BY_NO[no]
    html(f'<div class="st-crumb">Home &gt; {GROUPS[s["group"]]} &gt; {s["title"]}</div>')
    badge = '<span class="st-badge">창업자 화면</span>' if s.get("founder") else ""
    html(f'<h1>{s["title"]}<span class="st-id">{no} · {s["sid"]}</span>{badge}</h1>')
    demo = "" if capture() else '<span class="st-demo">데모 화면 · 숫자는 예시</span>'
    html(f'<div class="st-src">출처 {s["source"]} · {s["cmd"]}{demo}</div>')
    for col, (g, name) in zip(st.columns(5), STEPS.items()):
        label = f"{g}. {name}"
        if g == s["group"]:
            html(f'<div class="st-step">{label}</div>', col)
        else:
            first = next(x for x in SCREENS if x["group"] == g)
            col.page_link(first["path"], label=label, width="stretch")


def next_button(no: str):
    i = [s["no"] for s in SCREENS].index(no)
    nxt = SCREENS[(i + 1) % len(SCREENS)]
    label = "처음으로" if i == len(SCREENS) - 1 else f"다음 · {nxt['no']} {nxt['title']}"
    _, b = st.columns([4, 1.3])
    if b.button(label, type="primary", width="stretch", icon=":material/arrow_forward:", key=f"next-{no}"):
        st.switch_page(nxt["path"])

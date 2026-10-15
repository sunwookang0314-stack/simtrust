import streamlit as st

import mock
import ui

ui.header("이슈 카드", "시뮬레이션 &gt; 이슈 카드", step=3)

df = mock.VIRTUAL_ISSUES.copy()

f = st.columns([2, 1.3, 1.3, 1])
cond = f[0].segmented_control("조건", ["전체", "C0", "C1", "C2"], default="전체")
screen = f[1].selectbox("화면", ["전체"] + sorted(df["화면"].unique()))
itype = f[2].selectbox("문제 유형", ["전체"] + mock.ISSUE_TYPES)
f[3].selectbox("반복 회차", ["전체", "1회차", "2회차", "3회차"])

if cond and cond != "전체":
    df = df[df["조건"] == cond]
if screen != "전체":
    df = df[df["화면"] == screen]
if itype != "전체":
    df = df[df["문제 유형"] == itype]

counts = mock.VIRTUAL_ISSUES["상태"].value_counts()
chips = (ui.chip(f"정상 {counts.get('정상', 0)}")
         + ui.chip(f"지적 없음 {counts.get('지적 없음', 0)}", "#DCE8F7")
         + ui.chip(f"추출 실패 {counts.get('추출 실패', 0)}", "#F8D8C8"))
c1, c2 = st.columns([4, 1])
c1.markdown(chips, unsafe_allow_html=True)
c2.download_button("CSV 내보내기", df.to_csv(index=False).encode("utf-8-sig"),
                   "issue_cards.csv", width="stretch")

STATUS_BG = {"지적 없음": "background-color:#DCE8F7", "추출 실패": "background-color:#F8D8C8"}
styled = df.style.map(lambda v: STATUS_BG.get(v, ""), subset=["상태"])
event = st.dataframe(styled, hide_index=True, width="stretch",
                     on_select="rerun", selection_mode="single-row", key="issue_table")

failed = df[df["상태"] == "추출 실패"]
if not failed.empty:
    st.caption("추출 실패 카드만 다시 추출할 수 있습니다. 2회 연속 실패하면 분석에서 빠지고 로그에 남습니다.")
    st.button(f"실패 {len(failed)}건 재추출", icon=":material/refresh:")

rows = event.selection.rows
if rows:
    card = df.iloc[rows[0]]
    with st.container(border=True):
        st.markdown(f"**이슈 카드 상세 · {card['ID']}**")
        l, r = st.columns(2)
        l.markdown("가상 사용자 원문 응답")
        l.info(mock.RAW_RESPONSES.get(card["ID"], "(원문 응답 예시 없음)"))
        r.markdown("정규화 결과")
        r.json({"screen": card["화면"], "type": card["문제 유형"], "severity": card["심각도"],
                "evidence": card["지적 요약"], "persona": card["페르소나"], "condition": card["조건"]})
else:
    st.caption("행을 고르면 원문 응답과 정규화 결과를 나란히 보여줍니다.")

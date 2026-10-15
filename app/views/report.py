import altair as alt
import streamlit as st

import mock
import ui

ui.header("서비스 리포트", "리포트 &gt; 서비스 리포트", step=4)
svc = ui.current_service()

if svc["step"] < 3:
    st.info(f"{svc['name']}은(는) 아직 시뮬레이션을 실행하지 않았습니다. 실행이 끝나면 리포트가 만들어집니다.",
            icon=":material/hourglass_empty:")
    st.page_link("views/run_setup.py", label="실행 설정으로 가기", icon=":material/arrow_forward:")
    st.stop()

issues = mock.REPORT_ISSUES
n_people = 20
SEV_COLOR = {"높음": "#F8D3D3", "중간": "#FCEBB6", "낮음": "#E6E8EC"}
# 문제 유형별 신뢰도 판정 (C2 기준) — 이 지적을 얼마나 믿어도 되는지
trust = {t: mock.verdict(p, r, n) for t, p, r, n in mock.TRUST_MAP["C2"]}

st.caption(f"{svc['name']} · `{svc['commit']}` · {svc['flow']} · 가상 사용자 {n_people}명 (C2 SimTrust)")

with st.container(border=True):
    st.markdown("**한눈에 보기**")
    st.markdown(mock.REPORT_SUMMARY)

worst = mock.SCREEN_STUCK.sort_values("막힌 인원", ascending=False).iloc[0]
k = st.columns(4)
k[0].metric("참여 가상 사용자", f"{n_people}명", border=True)
k[1].metric("발견한 문제", f"{len(issues)}건", border=True)
k[2].metric("심각도 높음", f"{sum(i['severity'] == '높음' for i in issues)}건", border=True)
k[3].metric("가장 많이 막힌 화면", worst["화면"].split(" ", 1)[1], f"{worst['막힌 인원']}명", delta_color="off",
            border=True)

left, right = st.columns([3, 2])
with left:
    st.markdown("**어느 화면에서 막혔나** · 핵심 플로우 순서")
    df = mock.SCREEN_STUCK.assign(비율=lambda d: d["막힌 인원"] / n_people)
    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=3).encode(
        y=alt.Y("화면:N", sort=list(df["화면"]), title=None),
        x=alt.X("막힌 인원:Q", scale=alt.Scale(domain=[0, n_people]), title=None),
        color=alt.condition(alt.datum["막힌 인원"] >= n_people / 2, alt.value("#C2452D"), alt.value("#C3CAD5")),
        tooltip=["화면", "막힌 인원", alt.Tooltip("비율:Q", format=".0%")],
    )
    text = bars.mark_text(align="left", dx=4, fontSize=12).encode(
        text=alt.Text("막힌 인원:Q"), color=alt.value("#1F2933"))
    st.altair_chart(bars + text, width="stretch", height=230)
    st.caption("빨간 막대는 절반 이상이 막힌 화면입니다.")
with right:
    st.markdown("**어떤 종류의 문제였나**")
    for t in mock.ISSUE_TYPES:
        n = sum(i["count"] for i in issues if i["type"] == t)
        st.markdown(f"{t} · **{n}건**  {ui.chip(trust[t], ui.VERDICT_COLOR[trust[t]])}", unsafe_allow_html=True)
    st.caption("색 배지는 이 유형의 지적을 얼마나 믿어도 되는지입니다. 근거는 신뢰도 지도에 있습니다.")

st.subheader("문제점과 개선 제안")
st.caption("많은 가상 사용자가 겪은 순서대로 정렬했습니다.")
for rank, it in enumerate(sorted(issues, key=lambda i: -i["count"]), start=1):
    with st.container(border=True):
        h, c = st.columns([4, 1.4])
        h.markdown(f"**{rank}. {it['title']}**")
        c.markdown(f"<div style='text-align:right'>{ui.chip(it['severity'], SEV_COLOR[it['severity']])}"
                   f"{ui.chip(trust[it['type']], ui.VERDICT_COLOR[trust[it['type']]])}</div>",
                   unsafe_allow_html=True)
        st.markdown(f"<span class='st-note'>{it['screen']} · {it['type']} · "
                    f"{it['count']}/{n_people}명 · 주로 {it['who']}</span>", unsafe_allow_html=True)
        l, r = st.columns(2)
        with l:
            st.markdown("가상 사용자의 말")
            for q in it["quotes"]:
                st.markdown(f"> {q}")
        with r:
            st.markdown("개선 제안")
            st.success(it["fix"], icon=":material/lightbulb:")
            if it["effort"] != "-":
                st.caption(f"예상 작업량 · {it['effort']}")

md = [f"# {svc['name']} 리포트", "", mock.REPORT_SUMMARY.replace("**", ""), ""]
for it in sorted(issues, key=lambda i: -i["count"]):
    md += [f"## {it['title']} ({it['screen']}, {it['count']}/{n_people}명, 심각도 {it['severity']})",
           *[f"> {q}" for q in it["quotes"]], "", f"- 개선 제안: {it['fix']}", ""]
st.download_button("리포트 내려받기 (Markdown)", "\n".join(md).encode("utf-8"), f"report_{svc['id']}.md",
                   type="primary", icon=":material/download:")
st.caption("숫자와 문장은 예시입니다. 가상 사용자의 지적은 실제 사용자 테스트를 대신하지 않고, 어디부터 볼지 정하는 데 씁니다.")

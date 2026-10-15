import altair as alt
import streamlit as st

import mock
import ui

ui.header("지표 대시보드", "리포트 &gt; 지표 대시보드", step=4)

f = st.columns([2, 1.3, 2.7])
f[0].selectbox("서비스", [s["name"] for s in st.session_state.services])
f[1].selectbox("반복 회차", ["전체", "1회차", "2회차", "3회차"])
f[2].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
f[2].markdown(f"<div style='text-align:right'>{ui.chip('지표는 예시값', '#FCEBB6')}</div>",
              unsafe_allow_html=True)

M = mock.METRICS
c2 = M[M["조건"] == "C2 SimTrust"].iloc[0]
c0 = M[M["조건"] == "C0 기준선"].iloc[0]
k = st.columns(4)
k[0].metric("발견한 이슈", f"{c2['가상 이슈']}건", border=True)
k[1].metric("C2 정밀도", f"{c2['정밀도']:.2f}", border=True)
k[2].metric("C2 F1", f"{c2['F1']:.2f}", border=True)
k[3].metric("기준선 대비 F1", f"{c2['F1'] - c0['F1']:+.2f}", border=True)

left, right = st.columns([3, 2])
with left:
    st.markdown("**조건별 정밀도 · 재현율 · F1**")
    long = M.melt(id_vars="조건", value_vars=["정밀도", "재현율", "F1"], var_name="지표", value_name="값")
    chart = alt.Chart(long).mark_bar().encode(
        x=alt.X("지표:N", sort=["정밀도", "재현율", "F1"], title=None, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("조건:N", sort=list(M["조건"])),
        y=alt.Y("값:Q", scale=alt.Scale(domain=[0, 1]), title=None),
        color=alt.Color("조건:N", sort=list(M["조건"]),
                        scale=alt.Scale(range=["#C3CAD5", "#7D8CA6", "#2F4B7C"]),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["조건", "지표", alt.Tooltip("값:Q", format=".2f")],
    )
    labels = chart.mark_text(dy=-6, fontSize=11).encode(text=alt.Text("값:Q", format=".2f"),
                                                        color=alt.value("#1F2933"))
    st.altair_chart(chart + labels, width="stretch", height=300)
with right:
    st.markdown("**반복 일관성** · 같은 조건을 반복했을 때 회차 간 지적 일치율")
    st.dataframe(mock.CONSISTENCY, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="%.2f")
                                for c in ["1↔2회차", "2↔3회차", "평균"]})

st.markdown("**조건별 상세 지표**")
st.dataframe(M, hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%.2f") for c in ["정밀도", "재현율", "F1"]})
st.caption("예시 산정: 정밀도 = 매칭 ÷ (매칭 + 근거 없음). 유효 추가·판단 불가는 따로 집계합니다. 산정 규칙은 팀 확정 전입니다.")

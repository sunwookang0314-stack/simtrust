import altair as alt
import pandas as pd
import streamlit as st

import demo_data as D
import ui

NO = "4-1"
ui.header(NO)
e8 = ui.state() == "E8"
M = D.METRICS
COND_COLORS = ["#C3CAD5", "#9AA8BE", "#2F4B7C", "#7D8CA6"]

ui.html(ui.chip(f"서비스 · {ui.service() or '전체 (두 서비스 합산)'}", "#DCE8F7")
        + ui.chip(f"정답지 이슈 {D.GT_ISSUES_TOTAL}건 기준") + ui.chip(f"조건당 과제 실행 {D.TASK_RUNS_PER_COND}건"))

left, right = st.columns([3, 2])
with left:
    st.markdown("**조건별 정밀도 · 재현율 · F1** · 조건 2는 95% 신뢰구간")
    metrics = ["주 정밀도", "보수적 정밀도", "재현율", "F1"]
    long = M.melt(id_vars="조건", value_vars=metrics, var_name="지표", value_name="값")
    long["조건명"] = long["조건"].map(ui.cond_label)
    order = [ui.cond_label(c) for c in D.CONDITIONS]
    enc = dict(x=alt.X("지표:N", sort=metrics, title=None, axis=alt.Axis(labelAngle=0)),
               xOffset=alt.XOffset("조건명:N", sort=order))
    bars = alt.Chart(long).mark_bar().encode(
        **enc, y=alt.Y("값:Q", scale=alt.Scale(domain=[0, 1]), title=None),
        color=alt.Color("조건명:N", sort=order, scale=alt.Scale(domain=order, range=COND_COLORS),
                        legend=alt.Legend(orient="bottom", title=None, columns=4)),
        tooltip=["조건명", "지표", alt.Tooltip("값:Q", format=".2f")])
    ci = pd.DataFrame([{"지표": k, "조건명": ui.cond_label(2), "lo": lo, "hi": hi} for k, (lo, hi) in D.CI_COND2.items()])
    err = alt.Chart(ci).mark_rule(color="#1F2933", strokeWidth=1.5).encode(**enc, y="lo:Q", y2="hi:Q")
    st.altair_chart(bars + err, width="stretch", height=215)
with right:
    st.markdown("**반복 일관성** · 회차 간 지적 일치율")
    st.dataframe(D.CONSISTENCY.assign(조건=D.CONSISTENCY["조건"].map(str)), hide_index=True, width="stretch",
                 height=178, column_config={c: st.column_config.NumberColumn(format="%.2f")
                                            for c in ["1↔2회차", "2↔3회차", "1↔3회차", "평균"]})
    st.markdown("**과제 결과 분포** · 사람 vs AI")
    rows_html = []
    for who, d in D.TASK_RESULTS.groupby("대상", sort=False):
        total = d["건수"].sum()
        segs = "".join(f'<div style="width:{n / total:.1%};background:{ui.RESULT_COLOR[r]}" title="{r} {n}건">'
                       f'{r} {n}</div>' for r, n in zip(d["결과"], d["건수"]))
        rows_html.append(f'<div class="st-stack"><span>{who} <b>n={total}</b></span><div>{segs}</div></div>')
    ui.html("".join(rows_html))
    st.caption("쉬움 점수 평균(1–7) · " + " vs ".join(f"{k} {v}" for k, v in D.EASE.items()))

if e8:
    st.markdown(f"**유형별 지표 · {ui.cond_label(0)}**")
    rows = pd.DataFrame(D.type_table(0))
    rows["정밀도"] = rows["정밀도"].map(lambda v: "계산 불가" if pd.isna(v) else f"{v:.2f}")
    show = rows[["유형", "일치", "허위", "정밀도", "재현율", "재현율 분수", "건수"]]
    st.dataframe(show.style.map(lambda v: "background-color:#F8D3D3;font-weight:600" if v == "계산 불가" else "",
                                subset=["정밀도"]),
                 hide_index=True, width="stretch", height=178,
                 column_config={"재현율": st.column_config.NumberColumn(format="%.2f")})
    st.caption("취향·감성은 조건 0에서 일치도 허위도 0건이라 정밀도 분모가 0입니다. 0으로 채우지 않고 '계산 불가'로 둡니다.")
else:
    st.markdown("**판정 내역** · 주 정밀도 = 일치 ÷ (일치 + 허위) · 보수적 = 일치 ÷ 가상 이슈 · 재현율 = 일치 ÷ 34")
    st.dataframe(M.assign(조건=M["조건"].map(ui.cond_label)), hide_index=True, width="stretch", height=178,
                 column_config={c: st.column_config.NumberColumn(format="%.2f")
                                for c in ["주 정밀도", "보수적 정밀도", "재현율", "F1", "반복 일관성"]})

ui.next_button(NO)

import altair as alt
import pandas as pd
import streamlit as st

import demo_data as D
import ui

NO = "4-3"
ui.header(NO)
e10 = ui.state() == "E10"
WHO = list(D.INTENT_MEAN)

left, right = st.columns([1.2, 1])
with left:
    st.markdown("**사용 의향 1–5 분포** · AI(조건 2) vs 처음 쓴 참가자")
    d = D.INTENT.copy()
    d["비율"] = d["명"] / d.groupby("대상")["명"].transform("sum")
    st.altair_chart(alt.Chart(d).mark_bar().encode(
        x=alt.X("점수:O", title=None, axis=alt.Axis(labelAngle=0)), xOffset=alt.XOffset("대상:N", sort=WHO),
        y=alt.Y("비율:Q", axis=alt.Axis(format="%"), title=None),
        color=alt.Color("대상:N", sort=WHO, scale=alt.Scale(domain=WHO, range=["#C3CAD5", "#2F4B7C"]),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["대상", "점수", "명", alt.Tooltip("비율:Q", format=".0%")]), width="stretch", height=230)
    k = st.columns(2)
    for col, (who, (mean, n)) in zip(k, D.INTENT_MEAN.items()):
        col.metric(f"{who} 평균", f"{mean:.1f}", f"n={n}", delta_color="off", delta_arrow="off", border=True)
with right:
    st.markdown("**쓸·안 쓸 이유 일치율**")
    st.metric("AI 이유가 참가자 이유와 일치", f"{D.REASON_MATCH_RATE:.0%}", border=True)
    st.dataframe(pd.DataFrame(D.REASON_EXAMPLES, columns=["구분", "AI가 말한 이유", "참가자가 말한 이유"]),
                 hide_index=True, width="stretch", height=143)

badge = ui.chip(f"표본 적음 · n={D.CHURN_N}", "#FCEBB6") if e10 else ""
ui.html(f"**안 쓸 이유 vs 실제 이탈 이유** {badge}")
churn = D.CHURN_COMPARE
style = churn.style.map(lambda v: "color:#9AA4B2", subset=["실제 이탈 참가자"]) if e10 else churn
st.dataframe(style, hide_index=True, width="stretch", height=143)
if e10:
    st.caption(f"실제로 서비스를 그만 쓴 참가자가 {D.CHURN_N}명뿐이라 일치 여부를 수치로 말하지 않습니다. 예시로만 봅니다.")
else:
    st.caption(f"실제 이탈 이유는 그 서비스를 그만 쓴 참가자 {D.CHURN_N}명에게서만 나옵니다.")

ui.next_button(NO)

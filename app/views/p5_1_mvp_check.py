import pandas as pd
import streamlit as st

import demo_data as D
import ui

NO = "5-1"
ui.header(NO)
e11 = ui.state() == "E11"
mvp = D.MVP
stype = mvp["type_e11"] if e11 else mvp["type"]

with st.container(border=True):
    c = st.columns([1.6, 1.4, 1, 1, 1])
    c[0].markdown(f"**MVP**  \n{mvp['name']}")
    c[1].markdown(f"**만든 방식**  \n{mvp['made_by']}")
    c[2].markdown(f"**서비스 유형**  \n{stype}")
    c[3].markdown(f"**조건**  \n{ui.cond_label(mvp['condition'])}")
    c[4].markdown(f"**모델**  \n{mvp['model']}")

if e11:
    st.warning(f"서비스 유형이 '{stype}'입니다. 벤치마크와 유형이 달라 참고값의 근거가 약합니다. "
               "판정 배지는 정보 탐색형에서 잰 값이라 그대로 믿지 마세요.", icon=":material/warning:")

rows = [{"화면": scr, "유형": t, "지적 내용": text, "참고 판정": D.TRUST_MAP[t]["판정"]} for scr, t, text in D.MVP_ISSUES]
counts = pd.Series([r["참고 판정"] for r in rows]).value_counts()
ui.html(f"<b>가상 사용자 지적 {len(rows)}건</b> &nbsp;"
        + "".join(ui.verdict_chip(v).replace(f">{v}<", f">{v} {counts.get(v, 0)}<") for v in ui.VERDICT_COLOR))

df = pd.DataFrame(rows)
st.dataframe(df.style.map(lambda v: f"background-color:{ui.VERDICT_COLOR[v]};font-weight:600"
                          if v in ui.VERDICT_COLOR else "", subset=["참고 판정"])
             .map(lambda v: "color:#9AA4B2" if e11 else "", subset=["참고 판정"]),
             hide_index=True, width="stretch", height=248,
             column_config={"지적 내용": st.column_config.TextColumn(width="large")})

st.info("벤치마크(정보 탐색형 서비스 2개)에서 잰 유형별 참고값입니다. 이 지적 하나하나의 정답 여부는 아닙니다.  \n"
        "'믿고 써도 됨'은 바로 고쳐볼 만하고, '사람에게 물어볼 것'과 '자료 부족'은 실제 사용자 몇 명에게 확인하세요.",
        icon=":material/info:")
st.page_link(ui.BY_NO["4-2"]["path"], label="유형별 근거 보기 · 4-2 신뢰도 지도", icon=":material/map:")

ui.next_button(NO)

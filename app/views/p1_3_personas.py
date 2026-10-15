import json

import pandas as pd
import streamlit as st

import demo_data as D
import ui

NO = "1-3"
ui.header(NO)
svc = ui.service() or "링커리어"
R = D.PERSONA_RECORD

with st.container(border=True):
    c = st.columns([1.3, 2.2, 0.6, 2])
    c[0].markdown(f"**비율 파일**  \n<span class='st-note'>{R['ratio']}</span>", unsafe_allow_html=True)
    c[1].markdown("**필터 조건**  \n" + "  \n".join(f"<span class='st-note'>{f}</span>" for f in R["filters"]),
                  unsafe_allow_html=True)
    c[2].markdown(f"**시드**  \n<span class='st-note'>{R['seed']}</span>", unsafe_allow_html=True)
    c[3].markdown(f"**데이터셋**  \n<span class='st-note'>{R['dataset']}<br>{R['pool']}</span>",
                  unsafe_allow_html=True)

if ui.state() == "E3":
    st.error(f"{D.PERSONA_E3}  \n필터를 넓히거나 비율 파일을 고친 뒤 다시 실행하세요. 재학생 그룹 5명은 추출됐지만 저장하지 않았습니다.",
             icon=":material/error:")
    ui.next_button(NO)
    st.stop()

sets, source = D.load_personas()
people = sets[svc]
T = D.as_text
df = pd.DataFrame([{
    "ID": p["__id__"], "그룹": p["__group__"], "이름": T(p.get("name")), "나이": T(p.get("age")),
    "성별": T(p.get("gender")), "직업": T(p.get("occupation")), "거주": T(p.get("residence")).split(" (")[0],
    "비어 있는 필드": f"{len(D.empty_fields(p))}개",
} for p in people])

left, right = st.columns([3, 2])
with left:
    st.markdown(f"**{svc} 페르소나 세트 · {len(people)}명**")
    st.dataframe(df, hide_index=True, width="stretch", height=388)
    st.caption(f"{source} · 말투·성격처럼 Nemotron에 없는 필드는 비워두고 기록함 (경고 아님)")
with right:
    pid = st.selectbox("JSON 미리보기", df["ID"], label_visibility="collapsed")
    shown = next(p for p in people if p["__id__"] == pid)
    empty = D.empty_fields(shown)
    st.caption(f"비어 있는 필드 {len(empty)}개 · {', '.join(empty) or '없음'}")
    clean = {k: v for k, v in shown.items() if not k.startswith("__")}
    st.code(json.dumps({"type": "TinyPerson", "persona": clean}, ensure_ascii=False, indent=2),
            language="json", height=330)

ui.next_button(NO)

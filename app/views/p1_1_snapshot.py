import pandas as pd
import streamlit as st

import demo_data as D
import ui

NO = "1-1"
ui.header(NO)
e1 = ui.state() == "E1"
picked = "캠퍼스픽" if e1 else (ui.service() or "링커리어")

for col, name in zip(st.columns(2), D.SERVICES):
    snap = D.SNAPSHOTS[name]
    dates = D.SNAPSHOT_E1_DATES if e1 and name == "캠퍼스픽" else snap["captured"]
    with col.container(border=True):
        sel = ui.chip("선택됨", "#2F4B7C", "#fff") if name == picked else ""
        ui.html(f"**{D.SERVICE_FULL[name]}** {sel}")
        ui.html(f"{ui.chip(snap['type'])}<span class='st-note'>캡처 {' · '.join(dates)} · "
                f"화면 {len(snap['screens'])}개 · 과제 {len(D.TASKS[name])}개</span>")

if e1:
    st.warning("화면 변경 감지 · 캠퍼스픽이 10/08에 에브리커리어로 리브랜딩되어 캡처가 둘입니다. "
               "리브랜딩 전후 응답을 나눠 봅니다.", icon=":material/compare:")

snap = D.SNAPSHOTS[picked]
st.markdown(f"**{D.SERVICE_FULL[picked]} 스냅샷** · 화면 캡처는 `private/` 폴더에만 두고 공개하지 않습니다")
for col, (sid, name, _) in zip(st.columns(5), snap["screens"]):
    ui.html(f"<div class='st-ph'><b>{sid} {name}</b>private/ · 비공개</div>", col)

left, right = st.columns([3, 2])
with left:
    st.markdown("**화면별 기능 설명**")
    st.dataframe(pd.DataFrame(snap["screens"], columns=["화면", "이름", "기능 설명"]),
                 hide_index=True, width="stretch", height=213)
with right:
    st.markdown(f"**과제** {ui.chip('사람과 AI가 같은 문구를 받음', '#DCE8F7')}", unsafe_allow_html=True)
    for tid, text in D.TASKS[picked].items():
        with st.container(border=True):
            st.markdown(f"**{tid}** {text}")

ui.next_button(NO)

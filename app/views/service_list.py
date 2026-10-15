import streamlit as st

import mock
import ui

ui.header("서비스 목록", "서비스 &gt; 서비스 목록", step=1)

services = st.session_state.services
top_l, top_r = st.columns([4, 1])
top_l.markdown(f"**등록된 서비스 {len(services)}**")
if top_r.button("새 서비스 등록", type="primary", width="stretch"):
    st.switch_page("views/snapshot.py")

BADGE = {"스냅샷 등록됨": "blue", "실행 완료": "violet", "리포트 완료": "green"}

cols = st.columns(3)
for col, svc in zip(cols, services):
    with col.container(border=True):
        st.markdown(f"**{svc['name']}**")
        st.caption(svc["desc"])
        st.markdown(f"버전 `{svc['commit']}` · {svc['frozen']} 고정  \n화면 {len(svc['screens'])}개 · {svc['flow']}")
        st.badge(svc["status"], color=BADGE.get(svc["status"], "gray"))
        st.progress(svc["step"] / len(ui.STEPS))
        if st.button("열기", key=f"open-{svc['id']}", width="stretch",
                     on_click=lambda sid=svc["id"]: st.session_state.update(service_id=sid)):
            target = {1: "views/snapshot.py", 2: "views/personas.py", 3: "views/issue_cards.py",
                      4: "views/report.py"}[svc["step"]]
            st.switch_page(target)

if len(services) < 3:
    with cols[len(services)].container(border=True, height=208):
        st.markdown("<div style='text-align:center;color:#9AA4B2;padding-top:70px'>새 서비스를 등록하면 여기에 표시됩니다</div>",
                    unsafe_allow_html=True)

st.subheader("최근 실행 기록")
st.dataframe(mock.RUNS, hide_index=True, width="stretch")
st.caption("행을 고르면 해당 실행의 이슈 카드로 이동합니다 (초안에서는 표시만)")

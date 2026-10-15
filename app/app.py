"""SimTrust 화면 초안 (스토리보드·중간발표용).

실행: streamlit run app.py
"""
import streamlit as st

import ui

st.set_page_config(page_title="SimTrust", page_icon="🧭", layout="wide")
ui.init_state()

P = lambda path, title, icon: st.Page(path, title=title, icon=icon)

PAGES = {
    "서비스": [
        P("views/service_list.py", "서비스 목록", ":material/apps:"),
        P("views/snapshot.py", "스냅샷 등록", ":material/photo_camera:"),
    ],
    "시뮬레이션": [
        P("views/personas.py", "페르소나 세트", ":material/groups:"),
        P("views/run_setup.py", "실행 설정", ":material/tune:"),
        P("views/issue_cards.py", "이슈 카드", ":material/list_alt:"),
    ],
    "리포트": [
        P("views/report.py", "서비스 리포트", ":material/summarize:"),
        P("views/dashboard.py", "지표 대시보드", ":material/bar_chart:"),
        P("views/trust_map.py", "신뢰도 지도", ":material/map:"),
    ],
}

with st.sidebar:
    st.markdown("### SimTrust")
    names = {s["id"]: f'{s["name"]} · {s["commit"]}' for s in st.session_state.services}
    st.selectbox("서비스 선택", options=list(names), format_func=names.get, key="service_id")

nav = st.navigation(PAGES)
nav.run()

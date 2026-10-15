"""SimTrust 조회 전용 데모 (7주차 스토리보드 · 8주차 중간발표).

실행 (레포 루트에서): streamlit run app/main.py --server.address localhost
"""
import streamlit as st

import demo_data as D
import ui

st.set_page_config(page_title="SimTrust", page_icon="🧭", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)

pages = {s["no"]: st.Page(s["path"], title=f'{s["no"]} {s["title"]}', url_path=s["url"] or None, default=s["no"] == "1-1")
         for s in ui.SCREENS}
nav = st.navigation(list(pages.values()), position="hidden")
current = next(no for no, p in pages.items() if p.url_path == nav.url_path)

with st.sidebar:
    st.markdown("### SimTrust")
    st.selectbox("서비스", ["전체"] + D.SERVICES, key="svc")
    st.selectbox("조건", list(D.CONDITIONS), index=2, key="cond", format_func=ui.cond_label)
    st.divider()
    for g, name in ui.GROUPS.items():
        tag = " · 내부" if g in ui.INTERNAL_GROUPS else ""
        st.markdown(f"**{g}. {name}**<span class='st-note'>{tag}</span>", unsafe_allow_html=True)
        for s in (x for x in ui.SCREENS if x["group"] == g):
            founder = " · 창업자" if s.get("founder") else ""
            st.page_link(pages[s["no"]], label=f'{s["no"]} {s["title"]}{founder}')
    st.divider()
    ui.demo_state_selector(current)
    st.toggle("캡처 모드", key="capture", help="데모 안내 문구와 상태 선택기를 숨깁니다.")

nav.run()

import datetime as dt

import pandas as pd
import streamlit as st

import ui

ui.header("스냅샷 등록", "서비스 &gt; 스냅샷 등록", step=1)
st.caption("저장하면 스냅샷이 잠깁니다. 화면이 바뀌면 새 버전으로 다시 등록하세요.")

with st.container(border=True):
    st.markdown("**기본 정보**")
    c1, c2 = st.columns(2)
    name = c1.text_input("서비스명 *", placeholder="예: 테스트 서비스 C")
    url = c2.text_input("배포 URL *", placeholder="https://")
    commit = c1.text_input("커밋 해시 *", placeholder="예: a6f3c21",
                           help="URL만으로는 버전이 고정되지 않아 커밋 해시를 같이 기록합니다.")
    flow = c2.text_input("핵심 플로우 *", placeholder="예: 가입 → 공고 검색 → 지원 1회 완주",
                         help="플로우는 하나만 등록합니다.")

with st.container(border=True):
    st.markdown("**화면 캡처 \\***")
    files = st.file_uploader("핵심 플로우 순서대로 올려주세요 (PNG·JPG, 화면당 1장)",
                             type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if files:
        st.markdown("화면 ID는 자동으로 붙습니다. 이름만 고쳐주세요.")
        thumbs = st.columns(min(len(files), 5))
        for i, f in enumerate(files[:5]):
            thumbs[i].image(f, caption=f"S{i + 1}", width="stretch")
        screens = st.data_editor(
            pd.DataFrame({"화면 ID": [f"S{i + 1}" for i in range(len(files))],
                          "화면 이름": [f.name.rsplit(".", 1)[0] for f in files]}),
            hide_index=True, disabled=["화면 ID"], width="stretch", key="screen_names")
    else:
        screens = pd.DataFrame(columns=["화면 ID", "화면 이름"])

with st.container(border=True):
    st.markdown("**화면별 기능 설명 (선택)**")
    st.caption("설명이 빠진 화면이 있으면 '설명만' 입력 조건으로는 실행할 수 없습니다.")
    options = [f"{r['화면 ID']} {r['화면 이름']}" for _, r in screens.iterrows()] or ["캡처를 먼저 올려주세요"]
    d1, d2 = st.columns([1, 3])
    target = d1.selectbox("화면", options, disabled=screens.empty)
    d2.text_area("설명", placeholder="이 화면에 무엇이 있고 무엇을 할 수 있는지 적어주세요\n(예: 상단 검색창, 분야·마감일 필터, 공고 카드 목록)",
                 height=110, disabled=screens.empty, key=f"desc-{target}")

_, b1, b2 = st.columns([4, 1, 1])
b1.button("임시 저장", width="stretch")
if b2.button("스냅샷 저장", type="primary", width="stretch"):
    missing = [label for label, v in [("서비스명", name), ("배포 URL", url), ("커밋 해시", commit),
                                       ("핵심 플로우", flow)] if not v.strip()]
    if not files:
        missing.append("화면 캡처")
    if missing:
        st.error(f"필수 항목이 비어 있어 저장하지 않았습니다: {', '.join(missing)}")
    else:
        st.session_state.services.append({
            "id": f"svc-{len(st.session_state.services) + 1}", "name": name, "desc": flow,
            "url": url, "commit": commit, "frozen": dt.date.today().strftime("%Y/%m/%d"),
            "flow": flow, "screens": screens["화면 이름"].tolist(), "status": "스냅샷 등록됨", "step": 1,
        })
        st.success(f"{name} 스냅샷을 저장하고 잠갔습니다.")

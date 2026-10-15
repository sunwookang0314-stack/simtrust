import streamlit as st

import mock

STEPS = ["등록", "페르소나", "실행", "결과"]

VERDICT_COLOR = {
    "믿고 써도 됨": "#D6F0DD",
    "참고용": "#FCEBB6",
    "사람에게 물어볼 것": "#F8D3D3",
    "자료 부족": "#E6E8EC",
}

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1180px;}
.st-crumb {font-size: 0.78rem; color: #6B7684; text-align: right; margin-bottom: -0.4rem;}
.st-steps {display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 0.2rem 0 1.4rem;}
.st-steps div {padding: 6px 0; text-align: center; font-size: 0.8rem; border-radius: 4px;
               border: 1px solid #D5DAE1; color: #9AA4B2; background: #fff;}
.st-steps div.done {background: #E6E9EF; border-color: #E6E9EF; color: #4A5565;}
.st-steps div.now {background: #2F4B7C; border-color: #2F4B7C; color: #fff; font-weight: 600;}
.st-chip {display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem;
          font-weight: 600; margin-right: 6px;}
.st-note {font-size: 0.8rem; color: #6B7684;}
</style>
"""


def init_state():
    ss = st.session_state
    ss.setdefault("service_id", mock.SERVICES[0]["id"])
    ss.setdefault("services", [dict(s) for s in mock.SERVICES])
    ss.setdefault("persona_sets", {})


def current_service() -> dict:
    sid = st.session_state.service_id
    return next(s for s in st.session_state.services if s["id"] == sid)


def header(title: str, crumb: str, step: int):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="st-crumb">Home &gt; {crumb}</div>', unsafe_allow_html=True)
    st.title(title)
    cells = []
    for i, name in enumerate(STEPS, start=1):
        cls = "done" if i < step else "now" if i == step else ""
        cells.append(f'<div class="{cls}">{i}. {name}</div>')
    st.markdown(f'<div class="st-steps">{"".join(cells)}</div>', unsafe_allow_html=True)


def chip(text: str, bg: str = "#E6E9EF", fg: str = "#1F2933") -> str:
    return f'<span class="st-chip" style="background:{bg};color:{fg}">{text}</span>'

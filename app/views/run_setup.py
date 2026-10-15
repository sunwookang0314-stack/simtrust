import time

import pandas as pd
import streamlit as st

import mock
import ui

ui.header("실행 설정", "시뮬레이션 &gt; 실행 설정", step=3)
svc = ui.current_service()

st.info(f"대상 스냅샷  **{svc['name']}** · `{svc['commit']}` · {svc['frozen']} 고정 · 화면 {len(svc['screens'])}개 (잠금)",
        icon=":material/lock:")

st.markdown("**비교 조건**")
chosen = []
for col, (code, c) in zip(st.columns(3), mock.CONDITIONS.items()):
    with col.container(border=True):
        if st.checkbox(f"{code}  {c['name']}", value=True, key=f"cond-{code}"):
            chosen.append(code)
        st.caption(c["sub"])
        st.markdown(f"<span class='st-note'>{c['desc']}</span>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("**실행 옵션**")
    l, r = st.columns(2)
    sets = list(st.session_state.persona_sets) or ["대학생-20-seed42"]
    pset = l.selectbox("페르소나 세트 (C1 · C2에 적용)", sets)
    mode = r.radio("화면 입력 방식 (모든 조건에 동일 적용)", ["캡처 + 설명", "설명만"], horizontal=True)
    reps = l.number_input("반복 횟수", 1, 10, 3)
    r.text_input("모델 · 온도", "설정 파일 고정값", disabled=True)

n_people = 20
calls = n_people * int(reps)
summary = pd.DataFrame([{
    "조건": f"{code} {mock.CONDITIONS[code]['name']}",
    "페르소나": "-" if code == "C0" else f"{n_people}명",
    "반복": int(reps), "호출 수": calls, "출력 상한": "동일",
} for code in chosen])

st.markdown("**실행 요약** · 조건마다 호출 수와 출력 상한을 맞춥니다")
st.dataframe(summary, hide_index=True, width="stretch")

_, b1, b2 = st.columns([4, 1, 1])
b1.button("설정 저장", width="stretch")
if b2.button("실행", type="primary", width="stretch", disabled=not chosen):
    with st.status("시뮬레이션 실행 중", expanded=True) as status:
        for code in chosen:
            st.write(f"{code} {mock.CONDITIONS[code]['name']} · {mode} · {int(reps)}회")
            time.sleep(0.4)
        status.update(label="실행 완료", state="complete")
    st.page_link("views/issue_cards.py", label="이슈 카드 보러 가기", icon=":material/arrow_forward:")

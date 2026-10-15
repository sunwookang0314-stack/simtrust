import json

import pandas as pd
import streamlit as st

import mock
import ui

ui.header("페르소나 세트", "시뮬레이션 &gt; 페르소나 세트", step=2)

FILL_MIN = 15  # 기준값 협의 필요

tab_nv, tab_json = st.tabs(["Nemotron-Personas-Korea", "JSON 직접 업로드"])

with tab_json:
    st.file_uploader("TinyPerson JSON 파일", type=["json"], accept_multiple_files=True)
    st.caption("업로드한 파일도 17개 항목 충족 여부를 같은 기준으로 검사합니다.")

with tab_nv:
    with st.container(border=True):
        c = st.columns([1.4, 1.2, 1.2, 0.8, 0.8, 1])
        age = c[0].slider("연령", 18, 35, (19, 26))
        c[1].selectbox("직업", ["대학생", "대학원생", "취업준비생"])
        c[2].selectbox("거주 지역", ["전체", "수도권", "비수도권"])
        n = c[3].number_input("표본 수", 5, 100, 20, step=5)
        seed = c[4].number_input("시드", 0, 9999, 42, help="같은 조건과 시드면 같은 인원이 다시 뽑힙니다.")
        c[5].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        c[5].button("필터 적용", type="primary", width="stretch")

    people, source = mock.load_personas(int(n), int(seed), age)
    st.caption(source)
    if not people:
        st.info("조건에 맞는 페르소나가 없습니다. 연령 범위를 넓혀보세요.")
        st.stop()
    T = mock.as_text
    df = pd.DataFrame([{
        "선택": i == 0, "ID": p["__id__"], "이름": T(p.get("name")), "나이": T(p.get("age")), "성별": T(p.get("gender")),
        "직업": T(p.get("occupation")), "지역": T(p.get("residence")),
        "필드 충족": f"{mock.field_fill(p)} / {len(mock.PERSONA_FIELDS)}",
    } for i, p in enumerate(people)])

    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"**추출 결과 {len(people)}명**")
        edited = st.data_editor(df, hide_index=True, width="stretch", height=330,
                                disabled=[c for c in df.columns if c != "선택"], key="persona_table")
        short = [p["__id__"] for p in people if mock.field_fill(p) < FILL_MIN]
        if short:
            st.warning(f"필드 충족 {FILL_MIN}개 미만 {len(short)}명: {', '.join(short)}  \n"
                       "빈 항목이 있어도 TinyTroupe는 오류를 내지 않으니 저장 전에 확인하세요.")
    with right:
        picked = edited[edited["선택"]]["ID"].tolist()
        shown = next((p for p in people if p["__id__"] in picked), people[0])
        st.markdown(f"**TinyPerson JSON 미리보기 · {shown['__id__']}**")
        clean = {k: v for k, v in shown.items() if not k.startswith("__")}
        st.code(json.dumps(clean, ensure_ascii=False, indent=2), language="json", height=330)

    s1, s2 = st.columns([3, 1])
    set_name = s1.text_input("세트 이름", value=f"대학생-{int(n)}-seed{int(seed)}")
    s2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if s2.button("세트 저장", type="primary", width="stretch"):
        st.session_state.persona_sets[set_name] = {"n": int(n), "seed": int(seed), "age": age}
        st.success(f"'{set_name}' 세트를 저장했습니다. 실행 설정에서 고를 수 있습니다.")

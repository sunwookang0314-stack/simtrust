import streamlit as st

import demo_data as D
import ui

NO = "2-1"
ui.header(NO)
e4 = ui.state() == "E4"

if e4:
    E = D.RUN_E4
    st.error(f"비용 상한 도달 · 종료 코드 {E['exit']} · 실행 중단  \n"
             f"\\${E['cost']:.2f} / 상한 \\${E['cap']:.2f} (시험 실행용으로 낮춘 상한) · "
             f"과제 실행 {E['done']}/{D.TASK_RUNS}에서 멈춤. 캐시가 남아 있어 이어서 실행하면 완료된 호출은 다시 하지 않습니다.",
             icon=":material/block:")

with st.container(border=True):
    st.markdown("**고정 설정** · 모든 조건에 같게 적용")
    ui.html(" ".join(ui.chip(f"{k} {v}") for k, v in D.RUN_CONFIG))

cols = st.columns(4)
for col, (c, info) in zip(cols, D.CONDITIONS.items()):
    with col.container(border=True, height=118):
        st.markdown(f"**조건 {c}** · {info['name']}")
        st.caption(info["desc"])

df = D.RUNS.copy()
if ui.service():
    df = df[df["서비스"] == ui.service()]
if e4:
    df.loc[df["조건"] == 3, "상태"] = "대기"
    df.loc[df["실행 ID"] == "R-2-C-J11-r3", "상태"] = "중단"
done, cost, cap = (D.RUN_E4["done"], D.RUN_E4["cost"], D.RUN_E4["cap"]) if e4 else (D.TASK_RUNS, D.RUN_COST, D.RUN_COST_CAP)

left, right = st.columns([3.2, 1])
with left:
    st.markdown(f"**실행 기록** · {D.TASK_RUNS}건 중 {len(df)}건 표시")
    styled = df.style.map(lambda v: {"중단": "background-color:#F8D3D3", "대기": "color:#9AA4B2"}.get(v, ""),
                          subset=["상태"])
    st.dataframe(styled, hide_index=True, width="stretch", height=213 if e4 else 248,
                 column_config={"토큰": st.column_config.NumberColumn(format="%d")})
with right:
    st.markdown("**진행 요약**")
    st.metric("과제 실행", f"{done}/{D.TASK_RUNS}", border=True)
    st.progress(done / D.TASK_RUNS)
    st.metric(f"비용 · 상한 \\${cap:.2f}", f"${cost:.2f}", border=True)
    st.caption(f"{D.TASK_RUNS} = 서비스 2 × 페르소나 10 × 조건 4 × 과제 2 × 반복 3")

ui.next_button(NO)

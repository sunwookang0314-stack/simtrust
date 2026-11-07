import streamlit as st

import demo_data as D
import ui

NO = "3-1"
ui.header(NO)
c = ui.cond()
m = D.metrics_row(c)

k = st.columns([1, 1, 1, 2.4])
k[0].metric("원래 카드", f"{D.CARDS_BY_COND[c]}장", border=True)
k[1].metric("가상 이슈", f"{m['가상 이슈']}건", border=True)
k[2].metric("정리자", "2인 1조", border=True)
with k[3]:
    st.info("정밀도·재현율은 이 가상 이슈 단위로 셈. 같은 문제를 여러 페르소나가 지적해도 가상 이슈 1건입니다.",
            icon=":material/info:")

df = D.VIRTUAL_ISSUES
if c != 2:
    st.caption(f"{ui.cond_label(c)} · 가상 이슈 {m['가상 이슈']}건 · 아래 예시 행은 조건 2 기준입니다")
event = st.dataframe(df, hide_index=True, width="stretch", height=248,
                     on_select="rerun", selection_mode="single-row", key="vi")
st.caption(f"조건 2 가상 이슈 {D.METRICS.loc[2, '가상 이슈']}건 중 {len(df)}건 표시 · 가장 나쁜 결과 = 묶인 카드 중 가장 나쁜 과제 결과")

rows = event.selection.rows
vi = df.iloc[rows[0] if rows else 0]
cards = D.GROUPED_CARDS.get(vi["가상 이슈 ID"], [])
with st.container(border=True):
    st.markdown(f"**{vi['가상 이슈 ID']}에 묶인 원래 카드** · {vi['대표 설명']} · {vi['묶인 카드 수']}장 중 {len(cards)}장")
    if cards:
        for col, (cid, who, text) in zip(st.columns(len(cards)), cards):
            with col.container(border=True, height=110):
                ui.html(f"<span class='st-note'>{cid} · {who}</span>")
                st.markdown(text)
    else:
        st.caption("이 가상 이슈의 카드 예시는 VI-2-01, VI-2-02에만 넣어 두었습니다.")

ui.next_button(NO)

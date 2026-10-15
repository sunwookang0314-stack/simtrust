import streamlit as st

import demo_data as D
import ui

NO = "2-2"
ui.header(NO)
st_ = ui.state()

S = D.CARDS_STATUS
c1, c2 = st.columns([3, 2])
ui.html(ui.chip(f"정상 {S['정상']}") + ui.chip(f"지적 없음 {S['지적 없음']}", "#DCE8F7")
        + ui.chip(f"파싱 실패 {S['파싱 실패']}", "#F8D8C8")
        + f"<span class='st-note'>전체 {D.CARDS_TOTAL}장 · 조건별 "
        + " / ".join(f"{c}: {n}" for c, n in D.CARDS_BY_COND.items()) + "</span>", c1)
ui.html(f"<div style='text-align:right'>{ui.chip(f'파싱 실패율 {D.PARSE_FAIL_RATE:.1%} (기준 5% 이하)', '#D6F0DD')}</div>", c2)

df = D.CARDS.copy()
if st_ == "E5":
    df = df[df["상태"] != "정상"]
    st.warning("지적 없음·파싱 실패 카드만 보는 중입니다. 파싱 실패는 한 번 재추출하고, "
               "재추출 후에도 실패하면 분석에서 제외하고 로그에 남김. 지적 없음은 그대로 집계합니다.",
               icon=":material/filter_alt:")

STATUS_BG = {"지적 없음": "background-color:#DCE8F7", "파싱 실패": "background-color:#F8D8C8"}
styled = (df.style.map(lambda v: STATUS_BG.get(v, ""), subset=["상태"])
          .map(lambda v: f"background-color:{ui.RESULT_COLOR[v]}" if v in ui.RESULT_COLOR else "", subset=["결과"]))
event = st.dataframe(styled, hide_index=True, width="stretch", height=178 if st_ == "detail" else 388,
                     on_select="rerun", selection_mode="single-row", key="cards")
st.caption(f"{D.CARDS_TOTAL}장 중 {len(df)}장 표시 · 결과 = 과제 결과(바로 함 / 헤매다 함 / 못 함)")

rows = event.selection.rows
card_id = df.iloc[rows[0]]["카드 ID"] if rows else ("IC-2-0412" if st_ == "detail" else None)
if card_id:
    card = D.CARDS.set_index("카드 ID").loc[card_id]
    with st.container(border=True):
        st.markdown(f"**이슈 카드 상세 · {card_id}** · 조건 {card['조건']} · {card['페르소나']} · {card['회차']}회차 · {card['과제']}")
        l, r = st.columns(2)
        l.markdown("가상 사용자 발화 원문")
        l.info(D.CARD_RAW.get(card_id, "(원문 예시 없음)"))
        r.markdown("정규화된 카드 필드")
        r.json(D.CARD_NORMALIZED.get(card_id, {"status": card["상태"]}), expanded=True)
elif st_ != "E5":
    st.caption("행을 고르면 원문 발화와 정규화된 카드를 나란히 보여줍니다.")

ui.next_button(NO)

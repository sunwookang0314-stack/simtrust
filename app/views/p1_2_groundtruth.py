import streamlit as st

import demo_data as D
import ui

NO = "1-2"
ui.header(NO)
e2 = ui.state() == "E2"
svc = ui.service()


def only(df):
    return df if svc is None else df[df["서비스"] == svc]


k = st.columns([1, 1, 1, 1, 2.2])
k[0].metric("참가자", f"{D.PARTICIPANTS}명", border=True)
k[1].metric("대면 · 화상", f"{D.SESSIONS_FACE} · {D.SESSIONS_VIDEO}", border=True)
k[2].metric("정답지 이슈", f"{D.GT_ISSUES_TOTAL}건", border=True)
k[3].metric("이유 · 괜찮았던 점", f"{D.GT_REASONS_TOTAL} · {D.GT_GOOD_TOTAL}", border=True)
with k[4]:
    st.info("녹취록은 어떤 LLM에도 보내지 않음. 사람이 직접 정리한 기록만 정답지로 씁니다.", icon=":material/lock:")

if e2:
    ui.html(f"{ui.chip(D.SESSION_NO_RECORDING, '#E6E9EF')}{ui.chip('녹취 없음 · 기록표만', '#FCEBB6')}"
            "<span class='st-note'>참가자가 녹음을 원하지 않아 관찰 기록표로만 정리했습니다. "
            "이 세션에서 나온 이슈는 출처에 시각 대신 '기록표'로 적습니다.</span>")

t1, t2, t3, t4 = st.tabs([f"이슈 {D.GT_ISSUES_TOTAL}", f"이유 {D.GT_REASONS_TOTAL}",
                          f"괜찮았던 점 {D.GT_GOOD_TOTAL}", "참가자-서비스 24"])
with t1:
    df = only(D.GT_ISSUES).copy()
    if e2:
        df.loc[df["출처"].str.startswith(D.SESSION_NO_RECORDING), "출처"] = f"{D.SESSION_NO_RECORDING} 기록표"
    st.dataframe(df, hide_index=True, width="stretch", height=318)
    by = " / ".join(f"{t} {n}" for t, n in D.GT_ISSUES_BY_TYPE.items())
    st.caption(f"{D.GT_ISSUES_TOTAL}건 중 {len(df)}건 표시 · 링커리어 {D.GT_ISSUES_BY_SERVICE['링커리어']} / "
               f"캠퍼스픽 {D.GT_ISSUES_BY_SERVICE['캠퍼스픽']} · {by}")
with t2:
    st.dataframe(only(D.GT_REASONS), hide_index=True, width="stretch", height=318)
    st.caption(" / ".join(f"{k} {n}" for k, n in D.GT_REASONS_BY_KIND.items()) + " · 실제 이탈은 그 서비스를 그만 쓴 참가자만")
with t3:
    st.dataframe(only(D.GT_GOOD), hide_index=True, width="stretch", height=318)
    st.caption(f"{D.GT_GOOD_TOTAL}건 중 {len(only(D.GT_GOOD))}건 표시 · 허위 지적을 가릴 때 근거로 씁니다")
with t4:
    st.dataframe(only(D.GT_PARTICIPANTS), hide_index=True, width="stretch", height=318)
    st.caption(f"참가자 {D.PARTICIPANTS}명 × 서비스 2개 = 24쌍 · 처음 쓴 참가자 "
               f"{sum(D.FIRST_TIME_BY_SERVICE.values())}쌍 / 써본 참가자 11쌍 · 쉬움 점수 1–7")

ui.next_button(NO)

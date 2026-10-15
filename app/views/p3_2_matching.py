import streamlit as st

import demo_data as D
import ui

NO = "3-2"
ui.header(NO)
st_ = ui.state()
c = ui.cond()
m = D.metrics_row(c)
kappa = D.KAPPA_E7 if st_ == "E7" else D.KAPPA

k = st.columns([1, 1, 1, 2.2])
k[0].metric("판정 완료", f"미기입 {len(D.MATCHES_E6_BLANK)}칸" if st_ == "E6" else "100%", border=True)
k[1].metric("판정자 간 κ", f"{kappa:.2f}", f"기준 {D.KAPPA_MIN} 이상", delta_color="off", delta_arrow="off", border=True)
k[2].metric("협의", f"{D.DISCUSSED}건", border=True)
with k[3]:
    st.info("판정자 A·B는 각자 판정한 뒤 다른 칸만 협의합니다. 판정자는 기능 설명서 작성자와 다름.",
            icon=":material/group:")

if st_ == "E6":
    st.error(f"판정 칸 미기입 {len(D.MATCHES_E6_BLANK)}건 · CSV 검증 실패 · 종료 코드 4  \n"
             "빈칸을 채운 뒤 matches.csv를 다시 검증해야 지표를 계산합니다.", icon=":material/error:")
if st_ == "E7":
    st.warning(f"κ {D.KAPPA_E7:.2f} · {D.KAPPA_MIN} 미만 · 판정 기준을 다듬고 다시 판정",
               icon=":material/warning:")

df = D.MATCHES.copy()
if st_ == "E6":
    for vid, col in D.MATCHES_E6_BLANK.items():
        df.loc[df["가상 이슈"] == vid, [col, "일치 여부", "최종 결과"]] = ""
blank = {(vid, col) for vid, col in D.MATCHES_E6_BLANK.items()} if st_ == "E6" else set()


def mark(row):
    out = []
    for col in row.index:
        if (row["가상 이슈"], col) in blank:
            out.append("background-color:#F8D3D3")
        elif col == "일치 여부" and row[col] == "불일치":
            out.append("background-color:#FCEBB6")
        else:
            out.append("")
    return out


ui.html("미매칭 분류 " + ui.chip(f"유효한 추가 문제 {m['유효 추가']}", "#DCE8F7")
        + ui.chip(f"허위 지적 {m['허위']}", "#F8D3D3") + ui.chip(f"판단 불가 {m['판단 불가']}")
        + f"<span class='st-note'>{ui.cond_label(c)} · 가상 이슈 {m['가상 이슈']}건 중 일치 {m['일치']}건</span>")
event = st.dataframe(df.style.apply(mark, axis=1), hide_index=True, width="stretch", height=213,
                     on_select="rerun", selection_mode="single-row", key="matches")

rows = event.selection.rows
row = df.iloc[rows[0] if rows else 0]
vid = row["가상 이슈"]
vi = D.VIRTUAL_ISSUES.set_index("가상 이슈 ID").loc[vid]
gt = D.GT_ISSUES.set_index("ID")
left, right = st.columns([1, 1.4])
box_h = 160 if st_ in ("E6", "E7") else 196
with left.container(border=True, height=box_h):
    st.markdown(f"**가상 이슈 {vid}** · 최종 {row['최종 결과'] or '미기입'}")
    st.markdown(f"{vi['화면']} · {vi['유형']} · {vi['가장 나쁜 결과']}  \n{vi['대표 설명']}")
    if row["메모"]:
        st.caption(f"메모 · {row['메모']}")
with right.container(border=True, height=box_h):
    ui.html("**후보 정답지 이슈** <span class='st-note'>임베딩 유사도 · 후보 제시용 · 판정은 사람</span>")
    for gid, sim in D.MATCH_CANDIDATES.get(vid, []):
        a, b = st.columns([4, 1.2])
        a.markdown(f"`{gid}` {gt.loc[gid, '설명']}")
        b.progress(sim, text=f"{sim:.2f}")
if row["최종 결과"] == "허위 지적" and vid in D.FALSE_ALARM_EVIDENCE:
    gid, svc, scr, text, n = D.FALSE_ALARM_EVIDENCE[vid]
    st.success(f"허위 지적 근거 · 괜찮았던 점 {gid} ({svc} {scr}) — \"{text}\" · {n}명", icon=":material/thumb_up:")

ui.next_button(NO)

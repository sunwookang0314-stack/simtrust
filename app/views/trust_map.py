import pandas as pd
import streamlit as st

import mock
import ui

ui.header("신뢰도 지도", "리포트 &gt; 신뢰도 지도", step=4)

f = st.columns([2, 2, 1, 1])
cond = f[0].selectbox("조건", ["C2", "C1", "C0"],
                      format_func=lambda c: f"{c} {mock.CONDITIONS[c]['name']}")
f[1].markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
compare = f[1].checkbox("기준선(C0)과 비교", value=True, disabled=cond == "C0")

rows = []
base = {r[0]: mock.f1(r[1], r[2]) for r in mock.TRUST_MAP["C0"]}
for t, p, r, n in mock.TRUST_MAP[cond]:
    row = {"문제 유형": t, "정밀도": p, "재현율": r, "건수": n}
    if compare and cond != "C0":
        row["C0 대비 F1"] = "-" if n < mock.TRUST_RULES["min_count"] else f"{mock.f1(p, r) - base[t]:+.2f}"
    row["판정"] = mock.verdict(p, r, n)
    rows.append(row)
df = pd.DataFrame(rows)

f[2].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
f[2].download_button("CSV", df.to_csv(index=False).encode("utf-8-sig"), f"trust_map_{cond}.csv",
                     width="stretch")
f[3].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
f[3].button("PDF 내보내기", type="primary", width="stretch")

st.caption("고정된 화면과 설명을 받은 가상 사용자가 실제 사용자의 지적을 얼마나 예측했는지 보여줍니다.")


def paint(col):
    return [f"background-color:{ui.VERDICT_COLOR[v]};font-weight:600" for v in col]


def grey_if_short(row):
    short = row["건수"] < mock.TRUST_RULES["min_count"]
    return ["color:#9AA4B2" if short and c in ("정밀도", "재현율") else "" for c in row.index]


styled = (df.style.apply(paint, subset=["판정"]).apply(grey_if_short, axis=1)
          .format({"정밀도": "{:.2f}", "재현율": "{:.2f}"}))
st.dataframe(styled, hide_index=True, width="stretch")

R = mock.TRUST_RULES
with st.container(border=True):
    st.markdown("**판정 기준** · 예시값, 팀 확정 필요")
    legend = [
        ("믿고 써도 됨", f"정밀도·재현율 모두 {R['trust']} 이상, 건수 {R['min_count']} 이상"),
        ("참고용", f"둘 중 낮은 값이 {R['reference']} 이상 {R['trust']} 미만"),
        ("사람에게 물어볼 것", f"둘 중 하나라도 {R['reference']} 미만"),
        ("자료 부족", f"건수 {R['min_count']} 미만, 점수는 표시하되 판정 보류"),
    ]
    for name, rule in legend:
        st.markdown(f"{ui.chip(name, ui.VERDICT_COLOR[name])} <span class='st-note'>{rule}</span>",
                    unsafe_allow_html=True)

st.caption("숫자는 예시입니다. 버튼 반응 속도, 로딩, 오류 복구처럼 직접 써봐야 보이는 문제는 비교 범위 밖입니다.")

import pandas as pd
import streamlit as st

import demo_data as D
import ui

NO = "4-2"
ui.header(NO)
compare = ui.state() == "c0"
R = D.TRUST_RULES

ui.html(ui.chip(f"기준값 동결 · {D.FROZEN}", "#2F4B7C", "#fff") + ui.chip(ui.cond_label(2))
        + ui.chip("두 서비스 합산") + "<span class='st-note'>고정된 화면과 설명을 받은 가상 사용자가 "
        "실제 사용자의 지적을 얼마나 예측했는지 보여줍니다</span>")


def ci(v):
    return f" [{v[0]:.2f}–{v[1]:.2f}]" if v else ""


def service_ref(svc, t):
    m, f = D.TYPE_BY_SERVICE[svc][t]
    n = D.GT_BY_SERVICE_TYPE[svc][t]
    p = D.precision(m, f)
    return f"P {'-' if p is None else f'{p:.2f}'} · R {m / n:.2f} (n={n})"


base = {r["유형"]: r for r in D.type_table(0)}
rows = []
for t in D.ISSUE_TYPES:
    r = D.TRUST_MAP[t]
    p_ci, r_ci = D.TYPE_CI[t]
    row = {"유형": t,
           "정밀도 [CI]": ("계산 불가" if r["정밀도"] is None else f"{r['정밀도']:.2f}") + ci(p_ci),
           "재현율 [CI]": f"{r['재현율']:.2f} ({r['재현율 분수']})" + ci(r_ci),
           "건수": r["건수"], "판정": r["판정"]}
    if compare:
        b = base[t]["F1"]
        row["조건 0 대비 F1"] = "-" if r["F1"] is None or b is None else f"{r['F1'] - b:+.2f} ({b:.2f}→{r['F1']:.2f})"
    row |= {"한 줄 해석": D.TYPE_NOTE[t],
            "링커리어 참고": service_ref("링커리어", t), "캠퍼스픽 참고": service_ref("캠퍼스픽", t)}
    rows.append(row)
df = pd.DataFrame(rows)


def paint(row, col):
    if col == "판정":
        return f"background:{ui.VERDICT_COLOR[row[col]]};font-weight:600;white-space:nowrap"
    if col == "유형":
        return "font-weight:600;white-space:nowrap"
    if row["판정"] == "자료 부족" and col != "한 줄 해석":
        return "color:#9AA4B2"   # 자료 부족: 숫자는 보이되 회색 (E9)
    return "white-space:nowrap" if "참고" in col or "CI" in col else ""


ui.table(df, paint)
st.caption("건수 = 두 서비스 정답지 이슈 합산 · 서비스별 참고는 건수가 작아 판정에 쓰지 않습니다")

with st.container(border=True):
    st.markdown("**판정 기준** · 위에서부터 차례로 적용")
    legend = [
        ("자료 부족", f"정답지 이슈나 가상 이슈가 {R['min_count']}건 미만 · 먼저 적용, 숫자는 회색으로 표시"),
        ("믿고 써도 됨", f"정밀도·재현율 둘 다 {R['trust']} 이상"),
        ("참고용", f"둘 다 {R['reference']} 이상"),
        ("사람에게 물어볼 것", "그 외"),
    ]
    for name, rule in legend:
        ui.html(f"{ui.verdict_chip(name)} <span class='st-note'>{rule}</span>")

st.caption("버튼 반응 속도, 로딩, 오류 복구처럼 직접 써봐야 보이는 문제는 비교 범위 밖입니다.")
ui.next_button(NO)

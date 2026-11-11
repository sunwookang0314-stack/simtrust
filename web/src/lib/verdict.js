// 판정 이름은 판정 계산기 출력 그대로 (scripts/score_reasons.py VERDICTS)
// 색은 진할수록 믿을 만함 (mockup/base.css --v-*와 같은 규칙)
export const VERDICT_STYLE = {
  "믿고 써도 됨": { key: "trust", rank: 0 },
  "참고용": { key: "ref", rank: 1 },
  "사람에게 물어볼 것": { key: "ask", rank: 2 },
  "자료 부족": { key: "none", rank: 3 },
  "계산 불가": { key: "none", rank: 4 },
};

export const verdictKey = v => VERDICT_STYLE[v]?.key ?? "none";

export const pct = v => (v == null ? "-" : Math.round(v * 100));

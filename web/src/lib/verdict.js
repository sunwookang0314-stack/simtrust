// 판정 이름은 판정 계산기 출력 그대로 (scripts/score_reasons.py VERDICTS)
// 색은 진할수록 믿을 만함 (mockup/base.css --v-*와 같은 규칙)
export const VERDICT_STYLE = {
  "믿고 써도 됨": { key: "trust", rank: 0, say: "사람 답과 충분히 겹쳐요" },
  "참고용": { key: "ref", rank: 1, say: "절반 넘게 겹치지만 확신하긴 일러요" },
  "사람에게 물어볼 것": { key: "ask", rank: 2, say: "아직 사람 답을 대신하기 어려워요" },
  "자료 부족": { key: "none", rank: 3, say: "비교할 대학생 답이 너무 적어요" },
  "계산 불가": { key: "none", rank: 4, say: "비교할 AI 이유가 없어요" },
};

export const verdictKey = v => VERDICT_STYLE[v]?.key ?? "none";

export const pct = v => (v == null ? "-" : Math.round(v * 100));

// 판정 규칙 fixed_70 (v2 시뮬레이션으로 고름 11/19, 김민우 11/22 동결 예정. configs/rules.draft.json fixed):
// 통과율·재현율이 둘 다 70% 이상 = 믿고 써도 됨, 둘 다 50% 이상 = 참고용, 아니면 사람에게 물어볼 것.
// 막대의 눈금과 "왜" 문장은 이 문턱으로 그린다. 판정 자체는 계산기 verdict를 그대로 쓴다
export const RULE = { trust: 0.7, ref: 0.5 };
const METRIC_SAY = { precision: "AI 이유가 맞은 비율", recall: "사람 이유를 찾은 비율" };

/** 칸 하나가 왜 그 판정인지 한 문장. 숫자가 문턱과 안 맞으면(규칙 초안 견본) 일반 문장으로 */
export function verdictWhy(cell) {
  if (!cell) return "";
  const v = cell.verdict, say = VERDICT_STYLE[v]?.say ?? "";
  const below = t => Object.keys(METRIC_SAY).filter(m => cell[m] != null && cell[m] < t);
  if (v === "믿고 써도 됨" && !below(RULE.trust).length) return "두 비율 모두 70%를 넘어요";
  if (v === "참고용" && below(RULE.trust).length && !below(RULE.ref).length)
    return `${below(RULE.trust).map(m => METRIC_SAY[m]).join("·")}이 70%에 못 미쳐요`;
  if (v === "사람에게 물어볼 것" && below(RULE.ref).length)
    return `${below(RULE.ref).map(m => METRIC_SAY[m]).join("·")}이 절반도 안 돼요`;
  return say;
}

/**
 * 동결 규칙(configs/rules.v1.json, 11/24)으로 낸 판정. method fixed: 응답자 min_humans(5)명 미만 = 자료 부족,
 * 통과율·재현율 둘 다 70% 이상 = 믿고 써도 됨, 둘 다 50% 이상 = 참고용, 아니면 사람에게 물어볼 것.
 * 지금 견본(public/data/sample/)은 초안 규칙(rules.draft.json)으로 계산돼 verdict 칸이 다르다. 실제 결과가 v1 규칙으로
 * 나오면 verdict 칸과 이 값이 같아야 한다. 발표용 화면(Quick)이 이것을 쓴다
 */
export function verdictV1(cell) {
  if (!cell) return null;
  if (cell.n_humans < 5) return "자료 부족";
  if (cell.precision == null || cell.recall == null) return "계산 불가";
  if (cell.precision >= RULE.trust && cell.recall >= RULE.trust) return "믿고 써도 됨";
  if (cell.precision >= RULE.ref && cell.recall >= RULE.ref) return "참고용";
  return "사람에게 물어볼 것";
}

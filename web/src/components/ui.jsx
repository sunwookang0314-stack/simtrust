// concept.html에서 쓰던 부품을 React로 옮긴 것: 판정 배지, 통과율·재현율 막대, 이유 칩, 칸 고르기
import { PARAMS } from "../lib/params.js";
import { pct, verdictKey } from "../lib/verdict.js";

export function VerdictBadge({ verdict, size = "md" }) {
  return <span className={`verd v-${verdictKey(verdict)} ${size}`}>{verdict}</span>;
}

/** 막대 하나. 점선 = 참고용 50%, 믿고 써도 됨 70% (사전등록 v1 고정 70% 후보, 11/12 확정 전 예시) */
export function MetricBar({ label, value, sub }) {
  const v = value == null ? 0 : value * 100;
  return (
    <div className={`mbar${v < 70 ? " lo" : ""}`}>
      <span className="lab">{label}{sub && <small>{sub}</small>}</span>
      <div className="track">
        <div className="fill" style={{ width: `${v}%` }} />
        <i style={{ left: "50%" }} /><i style={{ left: "70%" }} />
      </div>
      <strong>{value == null ? "-" : `${pct(value)}%`}</strong>
    </div>
  );
}

/** 이유 칩. passed = 사람도 말함(거름망 통과), missed = 사람만 말함(AI가 놓침) */
export function ReasonChip({ reason }) {
  const missed = reason.type === "missed";
  const passed = reason.passed === "Y";
  const cls = missed ? "missed" : passed ? "pass" : "stuck";
  return (
    <li className={`rchip ${cls}`} title={reason.basis}>
      <span className="nm">
        {reason.common === "Y" && <em className="cm">공통</em>}
        {reason.name || reason.code}
      </span>
      <span className="ct">
        {missed
          ? `사람 ${reason.human_count}명 · AI 0번`
          : `AI ${reason.ai_episodes_with_code}/${reason.ai_episodes}번 · 사람 ${reason.human_count}명`}
      </span>
    </li>
  );
}

export function CellPicker({ params, only = ["service", "feature", "kind"] }) {
  return (
    <div className="picker">
      {only.map(k => (
        <div className="seg" key={k} role="group" aria-label={PARAMS[k].label}>
          {PARAMS[k].list.map(x => (
            <button key={x.id} className={params[k] === x.id ? "on" : ""} aria-pressed={params[k] === x.id}
                    onClick={() => params.set(k, x.id)}>{x.name}</button>
          ))}
        </div>
      ))}
    </div>
  );
}

export function SampleTag() {
  return <span className="sample">가짜 견본 데이터 · 판정 규칙은 11/12 확정 전 초안 (막대 점선 50%·70%는 참고선)</span>;
}

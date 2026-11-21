// 여러 화면이 같이 쓰는 부품: 화면 머리, 판정 배지, 비율 막대, 칸 고르기, 접는 설명
import { PARAMS } from "../lib/params.js";
import { RULE, pct, verdictKey } from "../lib/verdict.js";

/** 화면 머리: 머리글 + 한 줄 제목 + 한 줄 설명. 설명은 한 문장을 넘기지 않는다 */
export function PageHead({ eyebrow, title, sub }) {
  return (
    <div className="phead">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h1>{title}</h1>
      {sub && <p>{sub}</p>}
    </div>
  );
}

/** 발표 때 질문이 나오면 펼쳐 보는 연구 설명. 기본은 접혀 있다 */
export function More({ label = "자세히", children }) {
  return (
    <details className="more">
      <summary>{label}</summary>
      <div className="more-body">{children}</div>
    </details>
  );
}

export function VerdictBadge({ verdict, size = "md" }) {
  return <span className={`verd v-${verdictKey(verdict)} ${size}`}>{verdict}</span>;
}

/** 비율 막대 하나. 숫자는 "몇 개 중 몇 개"로 같이 보여 준다. 눈금 = 판정 문턱 50%·70% (RULE) */
export function MetricBar({ label, value, hit, total }) {
  const v = value == null ? 0 : value * 100;
  return (
    <div className={`mbar${value != null && value < RULE.ref ? " lo" : ""}`}>
      <div className="mtop">
        <span className="lab">{label}</span>
        <strong>{value == null ? "-" : `${pct(value)}%`}</strong>
      </div>
      <div className="track">
        <div className="fill" style={{ width: `${v}%` }} />
        <i style={{ left: `${RULE.ref * 100}%` }} /><i style={{ left: `${RULE.trust * 100}%` }} />
      </div>
      {total != null && <small>{total}개 중 {hit}개</small>}
    </div>
  );
}

export function CellPicker({ params, only = ["service", "feature", "kind"] }) {
  return (
    <div className="picker">
      {only.map(k => (
        <div className="pgroup" key={k}>
          <span className="plab">{PARAMS[k].label}</span>
          <div className="seg" role="group" aria-label={PARAMS[k].label}>
            {PARAMS[k].list.map(x => (
              <button key={x.id} className={params[k] === x.id ? "on" : ""} aria-pressed={params[k] === x.id}
                      onClick={() => params.set(k, x.id)}>{x.name}</button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

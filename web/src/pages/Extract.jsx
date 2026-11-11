// 화면 3. 이유 뽑기: 화면 2의 답 원문에서 추출기(scripts/extract_reasons.py)가 이유 줄만 뽑는다
// 쓸 이유는 Q-AI-WHY-USE 서술, 안 쓸 이유는 Q-AI-NOUSE에서 고른 보기. 머리말 같은 줄은 가린다
import { Link } from "react-router-dom";
import { EVERYONE, allLines, fname } from "../lib/examples.js";

function Row({ ai }) {
  const lines = allLines(ai);
  return (
    <section className="xrow">
      <div className="xraw">
        <header><b>{ai.name}</b><small>{ai.who ?? ai.sub}</small></header>
        {ai.masked.map(m => <p key={m} className="xmask" title="추출기가 이유가 아니라고 가린 줄">{m}</p>)}
        <p><span className="qb">Q-AI-WHY-USE</span>{ai.why.text}</p>
        {Object.entries(ai.nouse).map(([f, os]) => (
          <p key={f}><span className="qb">Q-AI-NOUSE</span>{fname(f)}: {os.map(o => `☑ ${o}`).join("  ")}</p>
        ))}
      </div>
      <div className="xarrow" aria-hidden="true">→</div>
      <ol className="xlines">
        {lines.map((l, i) => (
          <li key={l.id} style={{ animationDelay: `${i * 120}ms` }}>
            <span className={`kd ${l.kind}`}>{l.kind === "use" ? "쓸 이유" : "안 쓸 이유"}</span>
            <span className="ft">{fname(l.feature)}</span>
            <span className="tx">{l.text}{l.option && <em>보기</em>}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function Extract() {
  const n = EVERYONE.reduce((a, ai) => a + allLines(ai).length, 0);
  const masked = EVERYONE.reduce((a, ai) => a + ai.masked.length, 0);
  return (
    <div className="page">
      <div className="phead">
        <span className="no">3 · 이유 뽑기</span><span className="sample">화면 2의 예시 답</span>
        <h1>AI 답에서 이유만 {n}줄 뽑았어요</h1>
        <p>추출기가 답을 기능과 쓸/안 쓸로 나누고, 이유 하나에 한 줄로 쪼개요. 머리말처럼 이유가 아닌 줄 {masked}개는 가렸어요. 규칙으로 못 가린 줄은 2차 검토표로 보내요.</p>
      </div>
      <div className="xrows">{EVERYONE.map(ai => <Row key={ai.id} ai={ai} />)}</div>
      <div className="next">
        <span className="basis">다음 단계에서 이 줄마다 코드북 코드를 붙여요</span>
        <Link className="btn pri" to="/coding">코드 붙이러 가기 →</Link>
      </div>
    </div>
  );
}

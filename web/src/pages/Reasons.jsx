// 화면 5. 이유별 판정: 칸 하나(서비스 × 기능 × 쓸/안 쓸)에서 AI 셋의 이유를 거름망에 걸러 나란히 본다
import { useEffect, useState } from "react";
import { CellPicker, MetricBar, ReasonChip, SampleTag, VerdictBadge } from "../components/ui.jsx";
import { useCellParams } from "../lib/params.js";
import { FEATURES, KINDS, SERVICES, cellOf, loadAll, reasonsOf } from "../lib/data.js";
import { VERDICT_STYLE } from "../lib/verdict.js";

const byCount = (a, b) => b.ai_episodes_with_code - a.ai_episodes_with_code || b.human_count - a.human_count;

function ModelColumn({ model, params }) {
  const cell = cellOf(model, params.service, params.feature, params.kind);
  const rs = reasonsOf(model, params.service, params.feature, params.kind);
  const passed = rs.filter(r => r.type === "ai_reason" && r.passed === "Y").sort(byCount);
  const stuck = rs.filter(r => r.type === "ai_reason" && r.passed !== "Y").sort(byCount);
  const missed = rs.filter(r => r.type === "missed").sort((a, b) => b.human_count - a.human_count);
  if (!cell) return <section className="mcol empty"><h3>{model.name}</h3><p>이 칸에는 결과가 없어요</p></section>;
  return (
    <section className="mcol">
      <header>
        <div>
          <h3>{model.name}</h3>
          <small>{model.seat} · {model.note}</small>
        </div>
        <VerdictBadge verdict={cell.verdict} />
      </header>
      <MetricBar label="통과율" sub="AI 이유 중 사람도 말한 것" value={cell.precision} />
      <MetricBar label="재현율" sub="사람 이유 중 AI가 맞힌 것" value={cell.recall} />
      <p className="basis">AI 답 {cell.ai_episodes}개 · 응답자 {cell.n_humans}명과 비교</p>

      <div className="sieve-flow">
        <h4>AI가 말한 이유 {passed.length + stuck.length}개</h4>
        <div className="group">
          <span className="glab pass">사람도 말함 · 통과 {passed.length}</span>
          <ul>{passed.map(r => <ReasonChip key={r.code} reason={r} />)}</ul>
        </div>
        <div className="mesh" aria-hidden="true" />
        <div className="group">
          <span className="glab stuck">사람은 안 말함 · 걸림 {stuck.length}</span>
          {stuck.length ? <ul>{stuck.map(r => <ReasonChip key={r.code} reason={r} />)}</ul> : <p className="none">없음</p>}
        </div>
        <div className="group">
          <span className="glab missed">AI가 놓친 이유 {missed.length}</span>
          {missed.length ? <ul>{missed.map(r => <ReasonChip key={r.code} reason={r} />)}</ul> : <p className="none">없음</p>}
        </div>
      </div>
    </section>
  );
}

export default function Reasons() {
  const params = useCellParams();
  const [models, setModels] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { loadAll().then(setModels, e => setErr(e.message)); }, []);

  const label = k => ({ service: SERVICES, feature: FEATURES, kind: KINDS })[k].find(x => x.id === params[k]).name;
  let headline = "";
  if (models) {
    const vs = models.map(m => [m.name, cellOf(m, params.service, params.feature, params.kind)?.verdict]).filter(x => x[1]);
    const best = Math.min(...vs.map(([, v]) => VERDICT_STYLE[v]?.rank ?? 9));
    const top = vs.filter(([, v]) => (VERDICT_STYLE[v]?.rank ?? 9) === best);
    const who = top.length === vs.length ? "AI 셋 모두" : top.map(x => x[0]).join("·");
    headline = best === 0 ? `${label("feature")}의 ${label("kind")}는 ${who} 말을 믿고 써도 돼요`
      : best === 1 ? `${label("feature")}의 ${label("kind")}는 ${who} 말을 참고할 만해요`
      : `${label("feature")}의 ${label("kind")}는 ${who} 아직 사람에게 물어봐야 해요`;
  }

  return (
    <div className="page">
      <div className="phead">
        <span className="no">5 · 이유별 판정</span><SampleTag />
        <h1>{headline || "불러오는 중"}</h1>
        <p>같은 캡처와 질문에 AI 셋이 답한 이유를 {label("service")} 응답자 데이터로 걸렀어요. 통과율·재현율이 높아도, 사람끼리 잰 범위에 못 들거나 "아무 기능에나 할 말"과 구별이 안 되면 사람에게 물어봐요.</p>
      </div>
      <CellPicker params={params} />
      {err && <p className="err">{err}</p>}
      {models && <div className="mcols">{models.map(m => <ModelColumn key={m.id} model={m} params={params} />)}</div>}
      <p className="foot">칩 위에 마우스를 올리면 근거 문장이 보여요. <em className="cm">공통</em>은 어느 기능에나 할 말(필요 없음 등)이에요.</p>
    </div>
  );
}

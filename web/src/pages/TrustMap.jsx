// 결과 지도(신뢰도 지도): 기능 × AI 넷(페르소나 없는 모델 3개 + 페르소나 AI). 칸을 누르면 시연 3장 거름망에서 그 칸을 본다
// 바탕 모델 열과 페르소나 AI 열을 견주면 페르소나 효과(조건 0 대비)가 보인다. 바탕 모델은 주소 ?base= (팀 결정 대기)
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CellPicker, PageHead } from "../components/ui.jsx";
import { useBaseModel, useCellParams } from "../lib/params.js";
import { FEATURES, KINDS, POOLED, cellOf, loadAll } from "../lib/data.js";
import { VERDICT_STYLE, pct, verdictKey } from "../lib/verdict.js";

export default function TrustMap() {
  const params = useCellParams();
  const nav = useNavigate();
  const [base] = useBaseModel();
  const [models, setModels] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { loadAll().then(setModels, e => setErr(e.message)); }, []);

  const kind = KINDS.find(k => k.id === params.kind).name;
  const trustCount = m => FEATURES.filter(f => cellOf(m, POOLED, f.id, params.kind)?.verdict === "믿고 써도 됨").length;
  const ranked = models ? [...models].sort((a, b) => trustCount(b) - trustCount(a)) : [];
  const open = (f, m) => nav(`/demo?feature=${f}&kind=${params.kind}&ai=${m}&go=sieve`);
  const baseM = models?.find(m => m.id === base), personaM = models?.find(m => m.persona);
  const effect = baseM && personaM ? trustCount(personaM) - trustCount(baseM) : null;

  return (
    <div className="page">
      <PageHead eyebrow="결과 지도 · 기능 4개 전체"
                title={!models ? "불러오는 중" : trustCount(ranked[0])
                  ? `${kind}는 ${ranked[0].name} 말을 기능 ${FEATURES.length}개 중 ${trustCount(ranked[0])}개에서 믿어도 돼요`
                  : `${kind}는 아직 어느 AI 말도 그대로 믿기 어려워요`}
                sub="진한 파랑일수록 믿을 만해요. 칸을 누르면 그 칸의 거름망을 볼 수 있어요." />
      <div className="map-top">
        <CellPicker params={params} only={["kind"]} />
        <div className="legend">
          {Object.entries(VERDICT_STYLE).filter(([, s]) => s.rank < 3).map(([v, s]) => <span key={v}><i className={`v-${s.key}`} />{v}</span>)}
        </div>
      </div>
      {err && <p className="err">{err}</p>}
      {models && (
        <div className="map" style={{ gridTemplateColumns: `180px repeat(${models.length}, 1fr)` }}>
          <div className="mh" />
          {models.map(m => (
            <div className={`mh${m.persona ? " pz" : ""}`} key={m.id}>
              {m.persona ? "페르소나 AI" : m.name}
              <small>{m.persona ? `${baseM?.name ?? ""} + 가상 대학생 10명` : "그대로 물어봄"}</small>
            </div>
          ))}
          {FEATURES.map(f => [
            <div className="fc" key={f.id}>{f.name}</div>,
            ...models.map(m => {
              const c = cellOf(m, POOLED, f.id, params.kind);
              const shown = c && VERDICT_STYLE[c.verdict]?.key !== "none";
              return (
                <button key={m.id + f.id} className={`vc v-${verdictKey(c?.verdict)}`} onClick={() => open(f.id, m.id)}
                        aria-label={`${f.name} ${m.name} ${c?.verdict ?? "결과 없음"} 이유 보기`}>
                  <span className="vn">{c?.verdict ?? "-"}</span>
                  {shown && <span className="vp">맞음 {pct(c.precision)}% · 찾음 {pct(c.recall)}%</span>}
                  {c?.verdict === "자료 부족" && <span className="vp">대학생 {c.n_humans}명뿐</span>}
                </button>
              );
            }),
          ])}
        </div>
      )}
      <p className="mnote"><b>맞음</b> = AI가 말한 이유 중 대학생도 말한 비율 · <b>찾음</b> = 대학생이 말한 이유 중 AI도 말한 비율</p>
      {effect != null && (
        <p className="effect">
          <b>페르소나를 씌우면?</b> {baseM.name} 그대로 믿을 칸 {trustCount(baseM)}개 → 페르소나 AI {trustCount(personaM)}개
          {" "}({effect > 0 ? `${effect}개 늘었어요` : effect < 0 ? `${-effect}개 줄었어요` : "같아요"})
        </p>
      )}
    </div>
  );
}

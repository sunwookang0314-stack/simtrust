// 화면 6. 신뢰도 지도: 기능 × AI 넷(페르소나 없는 모델 3개 + 페르소나 AI). 칸을 누르면 화면 5에서 그 칸의 이유를 본다
// 바탕 모델 열과 페르소나 AI 열을 견주면 페르소나 효과(조건 0 대비)가 보인다
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CellPicker, SampleTag } from "../components/ui.jsx";
import { useBaseModel, useCellParams } from "../lib/params.js";
import { FEATURES, KINDS, SERVICES, cellOf, loadAll } from "../lib/data.js";
import { VERDICT_STYLE, pct, verdictKey } from "../lib/verdict.js";

export default function TrustMap() {
  const params = useCellParams();
  const nav = useNavigate();
  const [base] = useBaseModel();
  const [models, setModels] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { loadAll().then(setModels, e => setErr(e.message)); }, []);

  const svc = SERVICES.find(s => s.id === params.service).name;
  const kind = KINDS.find(k => k.id === params.kind).name;
  const trustCount = m => FEATURES.filter(f => cellOf(m, params.service, f.id, params.kind)?.verdict === "믿고 써도 됨").length;
  const ranked = models ? [...models].sort((a, b) => trustCount(b) - trustCount(a)) : [];
  const open = (f, m) => nav(`/reasons?service=${params.service}&feature=${f}&kind=${params.kind}&ai=${m}`);
  const baseM = models?.find(m => m.id === base), personaM = models?.find(m => m.persona);
  const effect = baseM && personaM ? trustCount(personaM) - trustCount(baseM) : null;

  return (
    <div className="page">
      <div className="phead">
        <span className="no">6 · 신뢰도 지도</span><SampleTag />
        <h1>{!models ? "불러오는 중" : trustCount(ranked[0])
          ? `${svc} ${kind}는 ${ranked[0].name} 말을 기능 ${FEATURES.length}개 중 ${trustCount(ranked[0])}개에서 믿고 써도 돼요`
          : `${svc} ${kind}는 아직 어느 AI 말도 그대로 믿기 어려워요`}</h1>
        <p>기능마다 거름망을 돌린 결과예요. 진할수록 믿을 만하고, 칸을 누르면 어떤 이유가 통과했는지 볼 수 있어요.</p>
        {effect != null && (
          <p className="effect">페르소나 효과: {baseM.name} 그냥 <b>{trustCount(baseM)}칸</b> → {baseM.name}+페르소나 <b>{trustCount(personaM)}칸</b>
            {" "}({effect > 0 ? `${effect}칸 늘었어요` : effect < 0 ? `${-effect}칸 줄었어요` : "같아요"}) <span className="sample">자리표시 견본</span></p>
        )}
      </div>
      <CellPicker params={params} only={["service", "kind"]} />
      {err && <p className="err">{err}</p>}
      {models && (
        <div className="map" style={{ gridTemplateColumns: `200px repeat(${models.length}, 1fr)` }}>
          <div className="mh">기능</div>
          {models.map(m => (
            <div className={`mh${m.persona ? " pz" : ""}${m.id === base ? " bz" : ""}`} key={m.id}>
              {m.persona ? `${baseM?.name ?? ""} + 페르소나` : m.name}
              <small>{m.persona ? "본실험 · 10명 × 3번" : m.id === base ? "페르소나 없음 · 바탕 모델" : "페르소나 없음"}</small>
            </div>
          ))}
          {FEATURES.map(f => [
            <div className="fc" key={f.id}>{f.name}</div>,
            ...models.map(m => {
              const c = cellOf(m, params.service, f.id, params.kind);
              return (
                <button key={m.id + f.id} className={`vc v-${verdictKey(c?.verdict)}`} onClick={() => open(f.id, m.id)}
                        aria-label={`${f.name} ${m.name} ${c?.verdict ?? "결과 없음"} 이유 보기`}>
                  <span className="vn">{c?.verdict ?? "-"}</span>
                  {c && VERDICT_STYLE[c.verdict]?.key !== "none" &&
                    <span className="vp">{pct(c.precision)}<small>·</small>{pct(c.recall)}</span>}
                  {c?.verdict === "자료 부족" && <span className="vs">응답자 {c.n_humans}명</span>}
                </button>
              );
            }),
          ])}
        </div>
      )}
      <div className="legend">
        {Object.entries(VERDICT_STYLE).filter(([, s]) => s.rank < 4).map(([v, s]) => <span key={v}><i className={`v-${s.key}`} />{v}</span>)}
        <span className="mnote">숫자 = 통과율 · 재현율 (%)</span>
      </div>
    </div>
  );
}

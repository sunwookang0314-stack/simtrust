// 화면 6. 신뢰도 지도: 기능 × AI 셋. 칸을 누르면 화면 5에서 그 칸의 이유를 본다
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CellPicker, SampleTag } from "../components/ui.jsx";
import { useCellParams } from "../lib/params.js";
import { FEATURES, KINDS, SERVICES, cellOf, loadAll } from "../lib/data.js";
import { VERDICT_STYLE, pct, verdictKey } from "../lib/verdict.js";

export default function TrustMap() {
  const params = useCellParams();
  const nav = useNavigate();
  const [models, setModels] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { loadAll().then(setModels, e => setErr(e.message)); }, []);

  const svc = SERVICES.find(s => s.id === params.service).name;
  const kind = KINDS.find(k => k.id === params.kind).name;
  const trustCount = m => FEATURES.filter(f => cellOf(m, params.service, f.id, params.kind)?.verdict === "믿고 써도 됨").length;
  const ranked = models ? [...models].sort((a, b) => trustCount(b) - trustCount(a)) : [];
  const open = f => nav(`/reasons?service=${params.service}&feature=${f}&kind=${params.kind}`);

  return (
    <div className="page">
      <div className="phead">
        <span className="no">6 · 신뢰도 지도</span><SampleTag />
        <h1>{!models ? "불러오는 중" : trustCount(ranked[0])
          ? `${svc} ${kind}는 ${ranked[0].name} 말을 기능 ${FEATURES.length}개 중 ${trustCount(ranked[0])}개에서 믿고 써도 돼요`
          : `${svc} ${kind}는 아직 어느 AI 말도 그대로 믿기 어려워요`}</h1>
        <p>기능마다 거름망을 돌린 결과예요. 진할수록 믿을 만하고, 칸을 누르면 어떤 이유가 통과했는지 볼 수 있어요.</p>
      </div>
      <CellPicker params={params} only={["service", "kind"]} />
      {err && <p className="err">{err}</p>}
      {models && (
        <div className="map" style={{ gridTemplateColumns: `200px repeat(${models.length}, 1fr)` }}>
          <div className="mh">기능</div>
          {models.map(m => <div className="mh" key={m.id}>{m.name}<small>{m.seat}</small></div>)}
          {FEATURES.map(f => [
            <div className="fc" key={f.id}>{f.name}</div>,
            ...models.map(m => {
              const c = cellOf(m, params.service, f.id, params.kind);
              return (
                <button key={m.id + f.id} className={`vc v-${verdictKey(c?.verdict)}`} onClick={() => open(f.id)}
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

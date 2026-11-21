// 거름망 장면 (mockup/concept.html 3~4단계를 실제 칸 데이터로).
// 위 = AI 영역(이유 칩, 클수록 많이 나온 이유), 아래 = 사람 영역(구멍 = 응답자가 말한 이유)
// ① 사람도 말한 이유는 구멍을 통과하고, 사람이 안 말한 이유는 망에 걸린다
// ② 걸린 이유는 AI 다수결 망으로 가서, AI 답에서 많이 나온 것만 "사람에게 확인할 후보"로 남는다 (11/11 확정)
// 마지막에 AI가 못 맞힌 구멍이 빨갛게 깜빡인다.
// 11/21: 시연 페이지의 "다음" 버튼이 upto(어느 단계까지 갈지)를 정하고, 장면은 거기까지 한 걸음씩 걸어간다.
// stamp가 켜지면 마지막 단계 뒤에 판정 도장이 가운데에 찍힌다. 판정은 도장으로만 보여 준다
import { useEffect, useRef, useState } from "react";
import { POOLED, cellOf, isCandidate, reasonsOf } from "../lib/data.js";
import { reduceMotion, useFit } from "../lib/motion.js";
import { AI_ZONE_H, W, aiHome, chipScale, spread, tier } from "../lib/stage.js";
import { verdictKey, verdictWhy } from "../lib/verdict.js";

const H = 470;
const MESH_Y = 250, REST_Y = 204;
const SIEVE1_R = 900, S2X = 1050;      // ① 사람 거름망은 왼쪽(40~900), ② 다수결 망은 오른쪽 가운데 S2X
const passY = i => (i % 2 ? 386 : 340);   // 통과한 칩은 두 줄로 엇갈려 겹치지 않게
// 단계: 0 칩 등장 → 1 통과할 칩이 구멍 위로 → 2 통과 → 3 나머지가 ① 망에 걸림
//       → 4 걸린 칩이 ② 다수결 망으로 → 5 적게 나온 칩은 빠져 사라지고 후보만 남음 → 6 놓친 이유 깜빡임
const LAST = 6;
const STEP_MS = 1000;

export default function SieveStage({ models, params, pick, onPick, upto = LAST, stamp = false, cellLabel = "" }) {
  const [phase, setPhase] = useState(-1);
  const [run, setRun] = useState(0);
  // 페르소나 AI일 때: 칩에 올리면 그 말을 한 페르소나를, 페르소나 원에 올리면 그 페르소나가 한 말을 켠다
  const [hover, setHover] = useState({ code: null, pid: null });
  const box = useRef(null);
  const scale = useFit(box, W);

  const model = models.find(m => m.id === pick) ?? models[0];
  const cell = cellOf(model, POOLED, params.feature, params.kind);
  const rows = reasonsOf(model, POOLED, params.feature, params.kind);
  const ai = rows.filter(r => r.type === "ai_reason")
    .sort((a, b) => b.ai_episodes_with_code - a.ai_episodes_with_code);
  // 사람 구멍: 이 칸에서 응답자가 말한 코드 전부 (AI 넷 어느 쪽 행에서 봐도 같다)
  const holeMap = new Map();
  for (const m of models)
    for (const r of reasonsOf(m, POOLED, params.feature, params.kind))
      if (r.human_count > 0 && !holeMap.has(r.code)) holeMap.set(r.code, r);
  const holes = [...holeMap.values()].sort((a, b) => b.human_count - a.human_count);
  const holeIdx = new Map(holes.map((h, i) => [h.code, i]));
  const holeX = new Map(holes.map((h, i) => [h.code, spread(holes.length, i, 110, SIEVE1_R - 70)]));
  const holeW = Math.min(150, (SIEVE1_R - 120) / Math.max(holes.length, 1) - 12);
  const passed = new Set(ai.filter(r => r.passed === "Y").map(r => r.code));
  const nPassed = passed.size, nStuck = ai.length - nPassed;
  const cands = ai.filter(r => !passed.has(r.code) && isCandidate(r));
  const candIdx = new Map(cands.map((r, i) => [r.code, i]));
  const nMissed = holes.filter(h => !ai.some(r => r.code === h.code)).length;
  const pids = [...new Set(ai.flatMap(r => [...(r.personas?.keys() ?? [])]))].sort();
  const hoverRow = ai.find(r => r.code === hover.code);
  const saidBy = pid => hoverRow?.personas?.get(pid) ?? 0;
  const said = r => (hover.pid ? r.personas?.get(hover.pid) ?? 0 : null);

  // upto까지 한 걸음씩. AI·칸이 바뀌거나 다시 보기면 처음부터 upto까지 다시 걷는다. 뒤로 가기는 바로 그 단계로
  const key = `${model.id}|${params.feature}|${params.kind}|${run}`;
  const keyRef = useRef(key), phaseRef = useRef(-1);
  useEffect(() => {
    const go = p => { phaseRef.current = p; setPhase(p); };
    const restart = keyRef.current !== key;
    keyRef.current = key;
    if (reduceMotion()) { go(upto); return; }
    const from = restart ? -1 : phaseRef.current;
    if (restart) go(-1);
    if (upto <= from) { go(upto); return; }
    const ts = [];
    for (let p = from + 1, k = 0; p <= upto; p++, k++) ts.push(setTimeout(() => go(p), 80 + k * STEP_MS));
    return () => ts.forEach(clearTimeout);
  }, [key, upto]);

  const chipPos = (r, i) => {
    const home = aiHome(i, ai.length);
    if (phase < 1) return home;
    if (passed.has(r.code)) {
      const x = holeX.get(r.code);
      return phase === 1 ? { x, y: MESH_Y - 54 } : { x, y: passY(holeIdx.get(r.code)) };
    }
    if (phase < 3) return home;
    if (phase === 3) return { x: Math.min(home.x, SIEVE1_R - 90), y: REST_Y };
    if (phase === 4) return { x: S2X, y: REST_Y };
    // 후보는 ② 망 위에 쌓이고, 나머지는 망 사이로 빠진다
    return candIdx.has(r.code) ? { x: S2X, y: REST_Y - candIdx.get(r.code) * 40 } : { x: S2X, y: H - 40 };
  };

  const stamped = stamp && phase >= LAST;
  if (!cell) return <section className="stage-card empty">이 칸에는 결과가 없어요</section>;
  return (
    <section className={`stage-card${stamped ? " thud" : ""}`} aria-label="거름망 장면">
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
        <filter id="ink"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed="3" result="n" /><feDisplacementMap in="SourceGraphic" in2="n" scale="3" /></filter>
      </svg>
      <div className="stage-top">
        <div className="seg" role="group" aria-label="AI 고르기">
          {models.map(m => (
            <button key={m.id} className={m.id === model.id ? "on" : ""} aria-pressed={m.id === model.id}
                    onClick={() => onPick?.(m.id)}>{m.name}</button>
          ))}
        </div>
        <div className={`stage-sum${phase >= LAST ? " on" : ""}`} aria-live="polite">
          <span className="ss pass"><b>{nPassed}</b>대학생도 말함</span>
          <span className="ss stuck"><b>{nStuck}</b>AI만 말함{cands.length > 0 && <small> (확인할 후보 {cands.length})</small>}</span>
          <span className="ss miss"><b>{nMissed}</b>AI가 놓침</span>
        </div>
        <button className="replay" onClick={() => setRun(x => x + 1)} disabled={upto < 0}>↻ 다시 보기</button>
      </div>

      <div className="stage-box" ref={box} style={{ height: H * scale }}>
        {stamped && (
          <div className="stamp-wrap" key={key} role="status">
            <div className={`stamp k-${verdictKey(cell.verdict)}`}>
              <b>{cell.verdict}</b>
              <small>{model.name}{cellLabel && ` · ${cellLabel}`}</small>
            </div>
            <p className="stamp-why">{verdictWhy(cell)}</p>
          </div>
        )}
        <div className="stage" style={{ width: W, height: H, transform: `scale(${scale})` }}>
          <div className="zone za" style={{ left: 0, top: 0, width: W, height: AI_ZONE_H }}>
            <span className="ztag a">{model.name}가 말한 이유 {ai.length}개 <small>· 클수록 자주 말함</small></span>
          </div>
          {model.persona && pids.length > 0 && (
            <div className="pstrip" style={{ left: W - 20 - 300, top: 10, width: 300 }} aria-label={`페르소나 ${pids.length}명`}>
              {pids.map(pid => {
                const n = saidBy(pid);
                const cls = hover.code ? (n ? " hl" : " dim") : hover.pid === pid ? " hl" : "";
                return (
                  <button key={pid} className={`pd${cls}`} title={`페르소나 ${pid}`}
                          onMouseEnter={() => setHover({ code: null, pid })} onMouseLeave={() => setHover({ code: null, pid: null })}
                          onFocus={() => setHover({ code: null, pid })} onBlur={() => setHover({ code: null, pid: null })}>
                    {pid.replace("P", "")}{n > 0 && <sup>{n}</sup>}
                  </button>
                );
              })}
              <small>{hover.code ? `${hoverRow?.name}: ${[...(hoverRow?.personas?.keys() ?? [])].length}명이 말함`
                : hover.pid ? `가상 대학생 ${hover.pid}가 한 말이 켜져요` : `가상 대학생 ${pids.length}명 · 올려 보면 누가 말했는지 보여요`}</small>
            </div>
          )}
          <div className="zone zh" style={{ left: 0, top: 184, width: SIEVE1_R + 16, height: H - 184 }}>
            <span className="ztag h bottom">진짜 대학생 {cell.n_humans}명이 말한 이유 {holes.length}개 = 거름망 구멍</span>
          </div>
          <div className="zone zm" style={{ left: SIEVE1_R + 30, top: 184, width: W - SIEVE1_R - 30, height: H - 184 }}>
            <span className="ztag m bottom">AI가 자주 말한 것만 남김</span>
          </div>
          <span className="s2note" style={{ left: S2X, top: MESH_Y + 46 }}>답 3개 중 1개 이상에서 나온 것</span>
          <span className={`candlab${phase >= 5 && cands.length ? " on" : ""}`}
                style={{ left: S2X, top: REST_Y - (cands.length - 1) * 40 - 22 }}>사람에게 확인할 후보</span>

          <div className={`mesh-band${phase === 3 ? " shake" : ""}`} style={{ left: 40, width: SIEVE1_R - 60, top: MESH_Y - 30, height: 60 }} />
          <div className={`mesh-band coarse${phase === 5 ? " shake" : ""}`} style={{ left: S2X - 105, width: 210, top: MESH_Y - 30, height: 60 }} />
          {holes.map(h => {
            const hit = phase >= 2 && passed.has(h.code);
            const missed = phase >= LAST && !ai.some(r => r.code === h.code);
            return (
              <div key={h.code} className={`hole${hit ? " hit" : ""}${missed ? " missed" : ""}`}
                   style={{ left: holeX.get(h.code), top: MESH_Y, width: holeW }} title={h.basis}>
                <span>{h.name || h.code}</span>
                <small>대학생 {h.human_count}명</small>
              </div>
            );
          })}
          {holes.map(h => (phase >= LAST && !ai.some(r => r.code === h.code)) && (
            <span key={h.code + "m"} className="missnote" style={{ left: holeX.get(h.code), top: passY(holeIdx.get(h.code)) - 8 }}>AI가 놓친 이유</span>
          ))}

          {ai.map((r, i) => {
            const p = chipPos(r, i), share = r.ai_episodes_with_code / r.ai_episodes;
            const isPass = passed.has(r.code);
            const cand = candIdx.has(r.code);
            const state = phase >= 2 && isPass ? " pass" : phase >= 5 && cand ? " cand" : phase >= 3 && !isPass ? " stuck" : "";
            const gone = phase >= 5 && !isPass && !cand;
            const s = said(r);
            const lit = s == null ? "" : s > 0 ? " hl" : " dim";
            return (
              <div key={r.code} className={`schip t${tier(share)}${state}${lit}`} title={`AI 답 ${r.ai_episodes}개 중 ${r.ai_episodes_with_code}개에서 나옴 · ${r.basis}`} tabIndex={0}
                   onMouseEnter={() => setHover({ code: r.code, pid: null })} onMouseLeave={() => setHover({ code: null, pid: null })}
                   onFocus={() => setHover({ code: r.code, pid: null })} onBlur={() => setHover({ code: null, pid: null })}
                   style={{ left: p.x, top: p.y, opacity: phase < 0 || gone ? 0 : 1,
                            "--s": phase < 0 ? 0.3 : chipScale(share),
                            transitionDelay: `${(phase <= 0 ? i * 70 : isPass ? i * 90 : phase >= 4 ? i * 60 : 0)}ms` }}>
                {r.name || r.code}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

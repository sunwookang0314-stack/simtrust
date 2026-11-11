// 거름망 장면 (mockup/concept.html 3~4단계를 실제 칸 데이터로).
// 위 = AI 영역(이유 칩, 클수록 많이 나온 이유), 아래 = 사람 영역(구멍 = 응답자가 말한 이유)
// ① 사람도 말한 이유는 구멍을 통과하고, 사람이 안 말한 이유는 망에 걸린다
// ② 걸린 이유는 AI 다수결 망으로 가서, AI 답에서 많이 나온 것만 "사람에게 확인할 후보"로 남는다 (11/11 확정)
// 마지막에 AI가 못 맞힌 구멍이 빨갛게 깜빡인다
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { cellOf, isCandidate, reasonsOf } from "../lib/data.js";
import { VerdictBadge } from "./ui.jsx";

const W = 1200, H = 470;              // 무대 좌표. 화면 폭에 맞춰 줄이고 키운다
const AI_ROWS = [64, 118], MESH_Y = 250, REST_Y = 204;
const SIEVE1_R = 900, S2X = 1050;      // ① 사람 거름망은 왼쪽(40~900), ② 다수결 망은 오른쪽 가운데 S2X
const passY = i => (i % 2 ? 386 : 340);   // 통과한 칩은 두 줄로 엇갈려 겹치지 않게
// 단계: 0 칩 등장 → 1 통과할 칩이 구멍 위로 → 2 통과 → 3 나머지가 ① 망에 걸림
//       → 4 걸린 칩이 ② 다수결 망으로 → 5 적게 나온 칩은 빠져 사라지고 후보만 남음 → 6 놓친 이유 깜빡임
const PHASE_AT = [60, 1300, 2300, 3300, 4300, 5200, 6100];
const LAST = PHASE_AT.length - 1;
const reduce = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const spread = (n, i, left = 90, right = W - 90) => (n === 1 ? W / 2 : left + (i * (right - left)) / (n - 1));
const tier = share => (share >= 0.3 ? 3 : share >= 0.12 ? 2 : 1);

function useFit(ref) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setScale(el.clientWidth / W));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return scale;
}

export default function SieveStage({ models, params }) {
  // 고른 AI는 주소(?ai=model_b)에 남겨서 링크로 같은 장면을 열 수 있게
  const [sp, setSp] = useSearchParams();
  const pick = models.some(m => m.id === sp.get("ai")) ? sp.get("ai") : models[0].id;
  const setPick = id => { const n = new URLSearchParams(sp); n.set("ai", id); setSp(n, { replace: true }); };
  const [phase, setPhase] = useState(-1);
  const [run, setRun] = useState(0);
  const box = useRef(null);
  const scale = useFit(box);

  const model = models.find(m => m.id === pick) ?? models[0];
  const cell = cellOf(model, params.service, params.feature, params.kind);
  const rows = reasonsOf(model, params.service, params.feature, params.kind);
  const ai = rows.filter(r => r.type === "ai_reason")
    .sort((a, b) => b.ai_episodes_with_code - a.ai_episodes_with_code);
  // 사람 구멍: 이 칸에서 응답자가 말한 코드 전부 (AI 셋 어느 쪽 행에서 봐도 같다)
  const holeMap = new Map();
  for (const m of models)
    for (const r of reasonsOf(m, params.service, params.feature, params.kind))
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

  // 칸이나 AI가 바뀌거나 다시 보기를 누르면 처음부터 돈다
  useEffect(() => {
    if (reduce()) { setPhase(LAST); return; }
    setPhase(-1);
    const ts = PHASE_AT.map((t, i) => setTimeout(() => setPhase(i), t));
    return () => ts.forEach(clearTimeout);
  }, [pick, params.service, params.feature, params.kind, run]);

  const perRow = Math.ceil(ai.length / 2);
  const chipPos = (r, i) => {
    const row = i < perRow ? 0 : 1, k = row ? i - perRow : i, n = row ? ai.length - perRow : perRow;
    const home = { x: spread(n, k, 150, W - 150), y: AI_ROWS[row] };
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

  if (!cell) return null;
  return (
    <section className="stage-card" aria-label="거름망 장면">
      <div className="stage-top">
        <div className="seg" role="group" aria-label="AI 고르기">
          {models.map(m => (
            <button key={m.id} className={m.id === pick ? "on" : ""} aria-pressed={m.id === pick}
                    onClick={() => setPick(m.id)}>{m.name}<small> {m.seat}</small></button>
          ))}
        </div>
        <div className={`stage-sum${phase >= LAST ? " on" : ""}`} aria-live="polite">
          <span><b className="c-pass">통과 {nPassed}</b> · <b className="c-stuck">걸림 {nStuck}</b> (<b className="c-cand">확인할 후보 {cands.length}</b>) · <b className="c-miss">놓침 {nMissed}</b></span>
          <VerdictBadge verdict={cell.verdict} />
          <button className="replay" onClick={() => setRun(x => x + 1)}>↻ 다시 보기</button>
        </div>
      </div>

      <div className="stage-box" ref={box} style={{ height: H * scale }}>
        <div className="stage" style={{ width: W, height: H, transform: `scale(${scale})` }}>
          <div className="zone za" style={{ left: 0, top: 0, width: W, height: 170 }}>
            <span className="ztag a">AI 답 {cell.ai_episodes}개에서 나온 이유 {ai.length}개</span>
          </div>
          <div className="zone zh" style={{ left: 0, top: 184, width: SIEVE1_R + 16, height: H - 184 }}>
            <span className="ztag h bottom">① 응답자 {cell.n_humans}명이 말한 이유 {holes.length}개 = 거름망 구멍</span>
          </div>
          <div className="zone zm" style={{ left: SIEVE1_R + 30, top: 184, width: W - SIEVE1_R - 30, height: H - 184 }}>
            <span className="ztag m bottom">② AI 다수결 망</span>
          </div>
          <span className="s2note" style={{ left: S2X, top: MESH_Y + 46 }}>답의 1/3 이상 나온 것만 남아요</span>
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
                <small>사람 {h.human_count}명</small>
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
            return (
              <div key={r.code} className={`schip t${tier(share)}${state}`} title={r.basis}
                   style={{ left: p.x, top: p.y, opacity: phase < 0 || gone ? 0 : 1,
                            "--s": phase < 0 ? 0.3 : 0.86 + Math.min(share, 0.6) * 0.5,
                            transitionDelay: `${(phase <= 0 ? i * 70 : isPass ? i * 90 : phase >= 4 ? i * 60 : 0)}ms` }}>
                {r.common === "Y" && <em>공통</em>}{r.name || r.code}
                <small>{r.ai_episodes_with_code}번</small>
              </div>
            );
          })}

        </div>
      </div>
    </section>
  );
}

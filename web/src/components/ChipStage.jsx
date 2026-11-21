// 칩 만들기 장면 (시연 2장, 11/21). 옛 화면 3 이유 뽑기 + 화면 4 코드 붙이기를 한 무대에서 움직임으로 보여 준다.
// 장 안 박자(step) 0 형광펜 → 1 떼어 냄 → 2 이름표(같은 뜻 합치기) → 3 다른 답도 → 4 답 120개가 쏟아지며 칩이 커짐.
// step -1 = 아직 안 온 장. 박자 4의 칩 자리는 거름망 장면 AI 영역(aiHome)과 똑같아서, 스크롤을 내리면 같은 칩이 거름망 위에 있는 것처럼 이어진다
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useFit, useRamp, useSub } from "../lib/motion.js";
import { AI_ZONE_H, W, aiHome, chipScale, tier } from "../lib/stage.js";

const H = 470;
const CARD = { a1: 20, a2: 172, a3: 300 };           // 답 카드 윗변
const RAW_X = 770, PILE_X = 1062;                    // 떼어 낸 칩 자리, 이름표 더미 자리 (가운데 기준)
const RAW_Y = { "a1-0": 74, "a1-1": 134, "a2-0": 214, "a3-0": 340, "a3-1": 398 };
const PILE_YS = [92, 214, 340];                     // 이름표 더미 자리: 처음 나온 순서대로 답 1·2·3 높이에
// 박자 안의 잔걸음(ms): 2 = 이름표 → 합치기, 3 = 답 2·3이 글 → 칠함 → 떼어 냄 → 이름표 → 합치기
const OFFSETS = { 2: [0, 1600], 3: [0, 500, 1300, 2300, 3900] };
const GRID = { cols: 20, rows: 6, x: 70, y: 226, dx: 54, dy: 38 };
// 박자 4: 답 카드가 깔린 뒤(POUR_AT) 칩 알갱이 N_FLY개가 답에서 이름표 더미로 날아가고, 그동안 숫자가 오른다
const POUR_AT = 450, N_FLY = 56, FLY_GAP = 42, FLY_MS = 750;
const POUR_MS = N_FLY * FLY_GAP + FLY_MS;

function ansState(ans, step, sub) {
  if (ans === "a1") {
    if (step < 0) return "text";
    if (step === 0) return "hl";
    if (step === 1) return "raw";
    if (step === 2) return sub ? "merged" : "named";
    return "merged";
  }
  if (step < 3) return "none";
  if (step === 3) return ["text", "hl", "raw", "named", "merged"][sub];
  return "merged";
}

/** 알갱이 i가 어느 이름표로 가는지: 답 120개에서 나온 횟수 비율대로 고르게 나눈다 (늘 같은 결과) */
function flyTargets(ai) {
  const total = ai.reduce((a, r) => a + r.ai_episodes_with_code, 0) || 1;
  const quota = ai.map(r => (r.ai_episodes_with_code / total) * N_FLY);
  const given = ai.map(() => 0), out = [];
  for (let i = 0; i < N_FLY; i++) {
    let best = 0;
    ai.forEach((_, k) => { if (quota[k] - given[k] > quota[best] - given[best]) best = k; });
    given[best]++;
    out.push(best);
  }
  return out;
}

export default function ChipStage({ step, story, rows, modelName = "GPT" }) {
  const { answers, pieces } = story;
  const codes = [...new Set(pieces.map(p => p.code))];
  const PILE_Y = Object.fromEntries(codes.map((c, i) => [c, PILE_YS[Math.min(i, PILE_YS.length - 1)]]));
  const box = useRef(null), stage = useRef(null), spans = useRef({});
  const scale = useFit(box, W);
  const sub = useSub(step, OFFSETS[step] ?? [0]);
  const [spanPos, setSpanPos] = useState({});
  const band = step >= 4;

  // 이유 조각이 문장 안 어디 있는지 잰다 (칩이 거기서 떨어져 나온다)
  useLayoutEffect(() => {
    const measure = () => {
      const st = stage.current?.getBoundingClientRect();
      if (!st) return;
      const out = {};
      for (const [id, el] of Object.entries(spans.current)) {
        if (!el) continue;
        const r = el.getBoundingClientRect();
        out[id] = { x: Math.round((r.left + r.width / 2 - st.left) / scale), y: Math.round((r.top + r.height / 2 - st.top) / scale) };
      }
      setSpanPos(p => (JSON.stringify(p) === JSON.stringify(out) ? p : out));
    };
    measure();
    document.fonts?.ready.then(measure);
  }, [scale, step, story]);

  const state = Object.fromEntries(answers.map(a => [a.id, ansState(a.id, step, sub)]));
  const pieceState = p => state[p.ans];

  // 더미에 도착한 칩 수. 칩이 날아가는 동안(0.7초) 기다렸다가 센다. 뒤로 갈 때는 바로
  const merged = {};
  for (const p of pieces) if (pieceState(p) === "merged") merged[p.code] = (merged[p.code] ?? 0) + 1;
  const mergedKey = JSON.stringify(merged);
  const [arrived, setArrived] = useState(merged);
  useEffect(() => {
    const m = JSON.parse(mergedKey);
    const up = Object.keys(m).some(k => m[k] > (arrived[k] ?? 0));
    if (!up) { setArrived(m); return; }
    const t = setTimeout(() => setArrived(m), 700);
    return () => clearTimeout(t);
    // arrived는 비교에만 쓴다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mergedKey]);

  // 답 120개 기준 이름표 (거름망 장면과 같은 순서)
  const ai = (rows ?? []).filter(r => r.type === "ai_reason").sort((a, b) => b.ai_episodes_with_code - a.ai_episodes_with_code);
  const nameOf = code => ai.find(r => r.code === code)?.name ?? code;
  const ramp = useRamp(band, POUR_MS + POUR_AT);
  const fly = band ? flyTargets(ai) : [];
  const tileOf = i => (i * 37 + 11) % (GRID.cols * GRID.rows);
  const ping = new Map(fly.map((_, i) => [tileOf(i), POUR_AT + i * FLY_GAP]));

  return (
    <section className="stage-card chip-card" aria-label="칩 만들기 장면">
      <div className="stage-box" ref={box} style={{ height: H * scale }}>
        <div className="stage chipstage" ref={stage} style={{ width: W, height: H, transform: `scale(${scale})` }}>
          {/* 박자 6: 거름망 장면과 같은 AI 영역 */}
          <div className={`zone za band${band ? " on" : ""}`} style={{ left: 0, top: 0, width: W, height: AI_ZONE_H }}>
            <span className="ztag a">{modelName}가 말한 이유 {ai.length}개 <small>· 클수록 자주 말함</small></span>
          </div>

          <span className={`colhead${step >= 1 && !band ? " on" : ""}`} style={{ left: RAW_X, top: 6 }}>떼어 낸 말</span>
          <span className={`colhead${step >= 2 && !band ? " on" : ""}`} style={{ left: PILE_X, top: 6 }}>이름표</span>

          {answers.map((a, n) => {
            const s = state[a.id];
            return (
              <div key={a.id} className={`acard s-${s}${band ? " away" : ""}`} style={{ left: 20, top: CARD[a.id], width: 600 }}>
                <header>{modelName} 답 {n + 1}</header>
                <p>{a.segs.map((g, i) => {
                  if (typeof g === "string") return <span key={i} className="plain">{g}</span>;
                  const p = pieces.find(x => x.ans === a.id && x.t === g.t);
                  return <span key={i} ref={el => { spans.current[p.id] = el; }} className="pc" style={{ transitionDelay: `${p.idx * 0.35}s` }}>{g.t}</span>;
                })}</p>
              </div>
            );
          })}

          {/* 떼어 낸 칩: 문장 안 자리 → 떼어 낸 말 → 이름표 → 더미로 */}
          {pieces.map(p => {
            const s = pieceState(p);
            const at = s === "merged" ? { x: PILE_X, y: PILE_Y[p.code] }
              : s === "raw" || s === "named" ? { x: RAW_X, y: RAW_Y[p.id] }
              : spanPos[p.id] ?? { x: RAW_X, y: RAW_Y[p.id] };
            const shown = s === "raw" || s === "named";
            return (
              <div key={p.id} className={`ichip s-${s}${band ? " away" : ""}`}
                   style={{ left: at.x, top: at.y, opacity: shown ? 1 : 0, transitionDelay: s === "raw" ? `${p.idx * 0.15}s` : undefined }}>
                {s === "named" && <small className="was">{p.t}</small>}
                <span key={s === "named" || s === "merged" ? "n" : "r"} className="tx">
                  {s === "named" || s === "merged" ? nameOf(p.code) : `“${p.t}”`}
                </span>
              </div>
            );
          })}

          {/* 이름표 더미. 박자 6에서 거름망 장면 칩 자리로 옮겨 가며 커진다 */}
          {ai.map((r, i) => {
            const have = arrived[r.code] ?? 0;
            if (!band && !have) return null;
            const pos = band ? aiHome(i, ai.length) : { x: PILE_X, y: PILE_Y[r.code] };
            // 박자 4: 알갱이가 들어오는 동안 숫자가 오르고, 그만큼 칩이 진해지고 커진다
            const count = band ? Math.round(have + (r.ai_episodes_with_code - have) * ramp) : have;
            const share = count / r.ai_episodes, final = r.ai_episodes_with_code / r.ai_episodes;
            const s = band ? 0.7 + (chipScale(final) - 0.7) * ramp : 1;
            return (
              <div key={r.code} className={`schip pile ${band ? `t${tier(share)}` : "t2 big"}${band && ramp < 1 ? " filling" : ""}`}
                   style={{ left: pos.x, top: pos.y, "--s": s, transitionDelay: band && ramp === 0 ? `${i * 80}ms` : "0s" }}>
                {r.name}<small key={band ? "b" : count} className="cnt">{band ? `${count}번` : `×${count}`}</small>
              </div>
            );
          })}

          {/* 박자 6: 같은 질문에 답 120개 */}
          <span className={`gridtag${band ? " on" : ""}`} style={{ left: GRID.x - 20, top: GRID.y - 34 }}>
            {modelName}에게 같은 질문을 여러 번 해서 모은 답 {ai[0]?.ai_episodes ?? 120}개
          </span>
          {Array.from({ length: GRID.cols * GRID.rows }, (_, i) => (
            <i key={i} className={`mini${band ? " on" : ""}${ping.has(i) ? " ping" : ""}`}
               style={{ left: GRID.x + (i % GRID.cols) * GRID.dx, top: GRID.y + Math.floor(i / GRID.cols) * GRID.dy,
                        transitionDelay: band ? `${(i % GRID.cols) * 12 + Math.floor(i / GRID.cols) * 40}ms` : "0s",
                        animationDelay: ping.has(i) ? `${ping.get(i)}ms` : undefined }} />
          ))}
          {/* 답 카드에서 칩 알갱이가 튀어나와 이름표 더미로 날아간다 */}
          {fly.map((k, i) => {
            const tile = tileOf(i);
            const fx = GRID.x + (tile % GRID.cols) * GRID.dx + 22, fy = GRID.y + Math.floor(tile / GRID.cols) * GRID.dy + 14;
            const to = aiHome(k, ai.length);
            return (
              <i key={i} className="fly" style={{ left: fx, top: fy, "--dx": `${to.x - fx}px`, "--dy": `${to.y - fy}px`,
                                                  animationDelay: `${POUR_AT + i * FLY_GAP}ms`, animationDuration: `${FLY_MS}ms` }} />
            );
          })}
        </div>
      </div>
    </section>
  );
}

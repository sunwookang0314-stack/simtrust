// 화면 2. AI에게 묻기: 화면 1의 캡처 4장과 설문과 같은 질문을 AI에게 보내고 답을 받는 장면
// 질문 문구는 docs/ai-protocol/questions/ 그대로(실행기 순서: Q-AI-USE → Q-AI-WHY-USE → Q-AI-NOUSE).
// 답은 지어낸 예시다. 실제 답은 실행기(scripts/run_simulation.py) 기록이 나오면 붙인다
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Shot from "../components/Shot.jsx";
import { CellPicker } from "../components/ui.jsx";
import { FEATURES, SERVICES } from "../lib/data.js";
import { useCellParams } from "../lib/params.js";
import { PERSONAS, REPEATS } from "../lib/personas.js";

const OPTIONS_46 = ["쓰기 번거로워 보여서", "나한테 필요 없을 것 같아서", "다른 앱이나 방법으로 해결해서", "딱히 써볼 생각을 안 해봐서", "기타"];
const QUESTIONS = [
  { id: "Q-AI-USE", text: `아래 기능 각각에 대해 "쓸 것 같다" 또는 "안 쓸 것 같다" 중 하나로 답해주세요.\n${FEATURES.map(f => `- ${f.name}`).join("\n")}` },
  { id: "Q-AI-WHY-USE", text: "쓸 것 같다고 고른 기능마다 줄을 바꿔서 적어주세요.\n- 기능 이름\n- 그 기능을 쓴다면 뭘 하려고 쓸 것 같은지\n- 그 기능 덕분에 뭐가 편할 것 같은지" },
  { id: "Q-AI-NOUSE", text: `안 쓸 것 같다고 고른 기능마다, 안 쓸 것 같은 이유에 가까운 것을 골라주세요. 여러 개 골라도 됩니다.\n${OPTIONS_46.map(o => `- ${o}`).join("\n")}` },
];

// 예시 답 (지어낸 것). use = 쓸 것 같다고 한 기능
const AIS = [
  { id: "gpt", name: "GPT", sub: "페르소나 없음 · 조건 0", use: ["F1", "F2", "F3"],
    why: "마감 알림: 지원할 공고 마감을 놓치지 않으려고 쓸 것 같아요. 따로 달력을 안 봐도 돼서 편할 것 같아요.",
    nouse: ["나한테 필요 없을 것 같아서"] },
  { id: "claude", name: "Claude", sub: "페르소나 없음 · 조건 0", use: ["F1", "F3"],
    why: "공고 검색·필터: 인턴 공고만 분야별로 보려고 쓸 것 같아요. 필요 없는 공고를 안 봐도 돼요.",
    nouse: ["쓰기 번거로워 보여서", "다른 앱이나 방법으로 해결해서"] },
  { id: "gemini", name: "Gemini", sub: "페르소나 없음 · 조건 0", use: ["F1", "F2", "F4"],
    why: "공고 저장: 괜찮은 공고를 모아 두고 주말에 비교하려고 쓸 것 같아요.",
    nouse: ["딱히 써볼 생각을 안 해봐서"] },
];
const PERSONA_USE = { F1: 24, F2: 18, F3: 21, F4: 9 };   // 답 30개 중 쓸 것 같다 (예시)
const N_ANS = PERSONAS.length * REPEATS;

// 0 캡처 준비 → 질문 q를 보내고(2q+1) 답을 받는다(2q+2) → 7 끝
const PHASE_AT = [100, 900, 2000, 3400, 4500, 5900, 7000, 7800];

function useTimeline(deps) {
  const [phase, setPhase] = useState(-1);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setPhase(PHASE_AT.length - 1); return; }
    setPhase(-1);
    const ts = PHASE_AT.map((t, i) => setTimeout(() => setPhase(i), t));
    return () => ts.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return phase;
}

function Answer({ ai, phase }) {
  return (
    <div className="ans">
      {phase >= 2 && (
        <div className="ausel">{FEATURES.map(f => {
          const u = ai.use.includes(f.id);
          return <span key={f.id} className={u ? "u" : "n"}>{f.name} <b>{u ? "쓸 것 같다" : "안 쓸 것 같다"}</b></span>;
        })}</div>
      )}
      {phase >= 4 && <p className="abub">{ai.why}</p>}
      {phase >= 6 && <div className="aopt">{ai.nouse.map(o => <span key={o}>☑ {o}</span>)}</div>}
    </div>
  );
}

export default function Ask() {
  const params = useCellParams();
  const [run, setRun] = useState(0);
  const phase = useTimeline([params.service, params.platform, run]);
  const q = phase < 1 ? -1 : Math.min(Math.floor((phase - 1) / 2), QUESTIONS.length - 1);
  const sending = phase >= 1 && phase % 2 === 1 && phase < 7;
  const thinking = sending;
  const svc = SERVICES.find(s => s.id === params.service).name;
  const lit = phase >= 2 ? Math.min(N_ANS, Math.round(((phase - 1) / 6) * N_ANS)) : 0;

  return (
    <div className="page">
      <div className="phead">
        <span className="no">2 · AI에게 묻기</span><span className="sample">답은 지어낸 예시</span>
        <h1>{svc} 화면 4장과 설문과 같은 질문을 AI에게 보내요</h1>
        <p>사람은 써 본 경험으로, AI는 캡처를 보고 답해요. 질문 문구는 실제 대학생 설문과 같아요.</p>
      </div>
      <div className="ask-top">
        <CellPicker params={params} only={["service", "platform"]} />
        <button className="replay" onClick={() => setRun(x => x + 1)}>↻ 다시 보기</button>
      </div>

      <div className="askflow">
        <div className={`acaps${sending ? " send" : ""}`}>
          <h4>보여주는 화면</h4>
          {FEATURES.map(f => <Shot key={f.id} small service={params.service} platform={params.platform} feature={f.id} />)}
        </div>

        <div className="aq">
          <h4>질문 {q >= 0 ? `${q + 1}/${QUESTIONS.length}` : ""}</h4>
          <ol className="qsteps">{QUESTIONS.map((x, i) => <li key={x.id} className={i === q ? "on" : i < q ? "done" : ""}>{x.id}</li>)}</ol>
          <pre className={`qtext${q >= 0 ? " on" : ""}`}>{q >= 0 ? QUESTIONS[q].text : "캡처를 준비하고 있어요"}</pre>
          <div className={`pipe${sending ? " go" : ""}`} aria-hidden="true"><i /><i /><i /><i /></div>
        </div>

        <div className="aais">
          {AIS.map(ai => (
            <div key={ai.id} className={`aicard${thinking ? " think" : ""}`}>
              <header><b>{ai.name}</b><small>{ai.sub}</small>{thinking && <em>읽는 중…</em>}</header>
              <Answer ai={ai} phase={phase} />
            </div>
          ))}
          <div className={`aicard persona${thinking ? " think" : ""}`}>
            <header><b>AI + 페르소나</b><small>본실험 · 조건 2 · {PERSONAS.length}명 × {REPEATS}번</small>{thinking && <em>읽는 중…</em>}</header>
            <div className="pdots">
              {Array.from({ length: N_ANS }, (_, i) => {
                const p = PERSONAS[i % PERSONAS.length];
                return <i key={i} className={`${p.job ? "jo" : ""}${i < lit ? " on" : ""}`}
                          title={`${p.n} ${p.a}세 · ${p.job ? "취준생" : "재학생"} · ${Math.floor(i / PERSONAS.length) + 1}회차`} />;
              })}
            </div>
            {phase >= 2 && (
              <div className="ausel">{FEATURES.map(f => (
                <span key={f.id} className="u">{f.name} <b>쓸 것 같다 {PERSONA_USE[f.id]}/{N_ANS}</b></span>
              ))}</div>
            )}
            {phase >= 4 && <p className="abub">{PERSONAS[0].n}({PERSONAS[0].a}세): 마감 알림 — 스크랩한 인턴 공고를 놓치지 않으려고 쓸 것 같아요.</p>}
          </div>
        </div>
      </div>

      <div className="next">
        <span className="basis">다음 단계에서 이 답들에서 이유만 뽑아요</span>
        <Link className="btn pri" to="/extract">이유 뽑으러 가기 →</Link>
      </div>
    </div>
  );
}

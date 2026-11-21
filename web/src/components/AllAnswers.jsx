// "AI 4개 답 전체 보기" (시연 1장 끝에 접어 둠). 옛 화면 2 AI에게 묻기의 답 카드를 멈춘 상태로 보여 준다.
// 질문 문구는 docs/ai-protocol/questions/ 그대로. ① GPT·Claude·Gemini는 페르소나 없이(조건 0, #35),
// ② 페르소나 AI는 바탕 모델 + 페르소나 10명 × 3번(본실험 조건 2). 답은 지어낸 예시
import { BASE_MODELS, FEATURES } from "../lib/data.js";
import { PERSONAS, REPEATS } from "../lib/personas.js";
import { AIS, OPTIONS_46, PERSONA_EXAMPLE, fname } from "../lib/examples.js";

const QUESTIONS = [
  `아래 기능 각각에 대해 "쓸 것 같다" 또는 "안 쓸 것 같다" 중 하나로 답해주세요.\n${FEATURES.map(f => `- ${f.name}`).join("\n")}`,
  "쓸 것 같다고 고른 기능마다 줄을 바꿔서 적어주세요.\n- 기능 이름\n- 그 기능을 쓴다면 뭘 하려고 쓸 것 같은지\n- 그 기능 덕분에 뭐가 편할 것 같은지",
  `안 쓸 것 같다고 고른 기능마다, 안 쓸 것 같은 이유에 가까운 것을 골라주세요. 여러 개 골라도 됩니다.\n${OPTIONS_46.map(o => `- ${o}`).join("\n")}`,
];
const PERSONA_USE = { F1: 24, F2: 18, F3: 21, F4: 9 };   // 답 30개 중 쓸 것 같다 (예시)
const N_ANS = PERSONAS.length * REPEATS;

function Card({ ai }) {
  return (
    <div className="aicard">
      <header><b>{ai.name}</b></header>
      <div className="ausel">{FEATURES.map(f => {
        const u = ai.use.includes(f.id);
        return <span key={f.id} className={u ? "u" : "n"}>{f.name} <b>{u ? "쓸래요" : "안 쓸래요"}</b></span>;
      })}</div>
      <p className="abub">{ai.why.text}</p>
      <div className="aopt">{Object.entries(ai.nouse).flatMap(([f, os]) => os.map(o => <span key={f + o}>{fname(f)}: {o}</span>))}</div>
    </div>
  );
}

export default function AllAnswers({ base = BASE_MODELS[0].id }) {
  const baseName = BASE_MODELS.find(m => m.id === base)?.name ?? "GPT";
  return (
    <>
      <ol className="qlist">{QUESTIONS.map((q, i) => <li key={i}><b>질문 {i + 1}</b><pre>{q}</pre></li>)}</ol>
      <div className="aais">
        {AIS.map(ai => <Card key={ai.id} ai={ai} />)}
        <div className="aicard persona">
          <header><b>페르소나 AI</b><small>{baseName}에게 가상 대학생 {PERSONAS.length}명을 연기시켜 {REPEATS}번씩 · 답 {N_ANS}개</small></header>
          <div className="ausel">{FEATURES.map(f => (
            <span key={f.id} className="u">{f.name} <b>쓸래요 {PERSONA_USE[f.id]}/{N_ANS}</b></span>
          ))}</div>
          <p className="abub"><small>{PERSONA_EXAMPLE.who}</small>{PERSONA_EXAMPLE.why.text}</p>
        </div>
      </div>
    </>
  );
}

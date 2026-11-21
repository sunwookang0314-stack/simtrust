// 묻기 장면 (시연 1장). 장 안 박자(step) 0 = 마감 알림 화면과 질문, 1 = 질문이 GPT로 가고 답이 한 글자씩 온다. -1 = 아직 안 온 장.
// 실제 실행기는 질문 세 개(Q-AI-USE → Q-AI-WHY-USE → Q-AI-NOUSE)를 차례로 보낸다. 여기서는 쓸 이유 질문만 줄여 보여 주고,
// 원문은 "AI 4개 답 전체 보기"(AllAnswers)에 둔다
import { useEffect, useState } from "react";
import Shot from "./Shot.jsx";
import { answerText } from "../lib/story.js";
import { reduceMotion, useSub } from "../lib/motion.js";

function Typer({ text, run }) {
  const [n, setN] = useState(run ? 0 : text.length);
  useEffect(() => {
    if (!run || reduceMotion()) { setN(text.length); return; }
    setN(0);
    const t = setInterval(() => setN(x => { if (x >= text.length) { clearInterval(t); return x; } return x + 1; }), 38);
    return () => clearInterval(t);
  }, [run, text]);
  return <>{text.slice(0, n)}{n < text.length && <i className="caret" />}</>;
}

export default function AskScene({ step, story, service, platform }) {
  const sub = useSub(step, step === 1 ? [0, 1100] : [0]);
  const sent = step >= 1;
  const thinking = step === 1 && sub === 0;
  const answering = step === 1 && sub === 1;
  return (
    <div className="askscene">
      <figure className="ask-shot">
        <Shot service={service} platform={platform} feature={story.feature} />
        <figcaption>{story.name} 화면</figcaption>
      </figure>

      <div className={`qmove${sent ? " sent" : ""}`}>
        <div className="qbub">{story.question}</div>
        <small>대학생 설문과 같은 질문</small>
        <div className={`pipe${thinking ? " go" : ""}`} aria-hidden="true"><i /><i /><i /><i /></div>
      </div>

      <div className={`gpt${thinking ? " think" : ""}`}>
        <header><b>GPT</b>{thinking && <em>읽는 중…</em>}</header>
        {step <= 0 && <p className="wait">질문을 기다리는 중</p>}
        {step >= 1 && !thinking && (
          <p className="abub big"><Typer text={answerText(story.answers[0])} run={answering} /></p>
        )}
      </div>
    </div>
  );
}

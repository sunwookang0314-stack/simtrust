// 화면 2. AI 셋에게 묻기 (틀). 질문 문구는 프로토콜 파일 그대로 (docs/ai-protocol/questions/)
import Frame from "../components/Frame.jsx";
import { MODELS } from "../lib/data.js";

export default function Ask() {
  return (
    <Frame no={2} title="같은 화면, 같은 질문을 AI 셋에게 물어요"
           lead="페르소나 없이(조건 0) 묻고, 질문 문구는 실제 대학생 설문과 같아요."
           blocks={["실행기 scripts/run_simulation.py 실행 기록 (runs/…/meta)", "질문 순서: Q-AI-USE → Q-AI-WHY-USE → Q-AI-NOUSE → Q-4-7"]}
           waits={["유료 키 3개와 비용 승인 (강선우)", "데모 방식: 미리 돌린 기록 재생(A) / 실시간"]}>
      <div className="ask-grid">
        {MODELS.map((m, i) => (
          <div className="ask" key={m.id}>
            <b>{m.name}</b><small>{m.seat}</small>
            <div className="prog"><div style={{ width: `${[100, 70, 35][i]}%` }} /></div>
            <span>{["답 받음", "Q-AI-NOUSE 묻는 중", "Q-AI-WHY-USE 묻는 중"][i]}</span>
          </div>
        ))}
      </div>
    </Frame>
  );
}

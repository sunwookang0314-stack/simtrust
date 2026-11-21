// 오프닝 (시연 0장, 11/21). 과정을 보여 주기 전에 "이 말 믿어도 돼?"라는 질문을 먼저 던진다.
// 장 안 박자(step) 0 = GPT 답 120개가 깔리고 가장 많이 나온 말을 인용, 1 = 큰 질문.
// 인용 횟수는 판정 계산기 견본(reasons_model_a.csv, 그 기능 · 쓸 이유)에서 인용한 말의 이름표 행. 배경 말풍선은 지어낸 예시
import { useRamp } from "../lib/motion.js";

// 말풍선 자리 (가로 %, 세로 %). 가운데 인용 카드 자리는 비운다
const SPOTS = Array.from({ length: 30 }, (_, i) => {
  const col = i % 6, row = Math.floor(i / 6);
  return { x: 4 + col * 16 + ((row * 7 + col * 3) % 6), y: 4 + row * 19 + ((col * 5) % 7) };
}).filter(p => !(p.x > 18 && p.x < 74 && p.y > 14 && p.y < 80));

export default function HookScene({ step, story, top }) {
  const on = step >= 0;
  const n = Math.round((top?.ai_episodes ?? 120) * useRamp(on, 1600));
  return (
    <div className={`hook${on ? " on" : ""}${step >= 1 ? " asked" : ""}`}>
      <div className="voices" aria-hidden="true">
        {SPOTS.map((p, i) => (
          <span key={i} style={{ left: `${p.x}%`, top: `${p.y}%`, transitionDelay: `${(i * 53) % 1400}ms` }}>
            {story.voices[i % story.voices.length]}
          </span>
        ))}
      </div>
      <div className="hook-main">
        <p className="hook-count"><b>{n}</b>번</p>
        <p className="hook-lead">GPT에게 "{story.name}, 왜 쓸 것 같아요?"라고 물었어요</p>
        <blockquote>
          “{story.quote}”
          <small>{top ? `답 ${top.ai_episodes}개 중 ${top.ai_episodes_with_code}개가 이렇게 말했어요` : ""}</small>
        </blockquote>
        <h2 className="hook-q">이 말, 믿고 서비스를 만들어도 될까요?</h2>
        <p className="hook-sub">진짜 대학생 답과 하나하나 견줘 볼게요.</p>
      </div>
    </div>
  );
}

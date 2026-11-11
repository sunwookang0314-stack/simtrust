// 화면 3. 답 → 이유 추출 (틀). 추출기 scripts/extract_reasons.py 출력(extracted_*.jsonl)을 보여줄 자리
import Frame from "../components/Frame.jsx";

// 지어낸 예시 답. 실제 AI 답이나 응답 원문이 아니다
const ANSWER = "마감 알림은 안 쓸 것 같아요. 알림이 하루에도 여러 번 오면 귀찮을 것 같고, 스크랩을 해야만 알림이 온다면 저는 스크랩을 잘 안 해서 받을 일이 없을 것 같아요.";
const LINES = ["알림이 하루에도 여러 번 오면 귀찮을 것 같음", "스크랩을 해야만 알림이 와서 받을 일이 없음"];

export default function Extract() {
  return (
    <Frame no={3} title="AI 답에서 이유만 뽑아요"
           lead="추출기가 답 원문을 이유 단위로 나눠요. 못 가린 줄은 2차 검토표로 보내요."
           blocks={["extracted_*.jsonl (질문마다 쓸/안 쓸 판별과 이유 줄)", "2차 검토표 CSV (김승하)"]}
           waits={["원시 응답 형식 합의 날짜 (김민우·김승하)"]}>
      <div className="extract">
        <div className="raw"><span className="tag">AI A 답 원문 · 마감 알림 (예시)</span><p>{ANSWER}</p></div>
        <div className="arrow" aria-hidden="true">→</div>
        <ul className="lines">{LINES.map((l, i) => <li key={l}><b>이유 {i + 1}</b>{l}</li>)}</ul>
      </div>
    </Frame>
  );
}

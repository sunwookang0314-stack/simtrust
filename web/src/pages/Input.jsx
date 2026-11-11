// 화면 1. 검사할 화면 넣기 (틀). 입력 방식은 #32 결정 대기 (캡처 업로드 / 기능별 URL)
import Frame from "../components/Frame.jsx";
import { FEATURES } from "../lib/data.js";

export default function Input() {
  return (
    <Frame no={1} title="검사할 서비스 화면을 넣어요"
           lead="기능마다 화면 캡처를 올려요. AI는 실제 앱 대신 이 캡처를 보고 답해요. 앱과 웹은 따로 검사해요."
           blocks={["캡처 촬영 규칙 (벤치마크와 같은 규칙이어야 참고값을 붙일 수 있음)", "기능 목록 docs/ai-protocol/features.txt"]}
           waits={["#32 입력 방식: 캡처 업로드 / 기능별 URL (강선우, 11/13)", "올린 캡처를 받는 서버 (데모 방식 A면 필요 없음)"]}>
      <div className="form-row"><label>서비스 이름</label><div className="fake-input">예: 동아리 모집 모아보기</div></div>
      <div className="form-row"><label>플랫폼</label><div className="seg"><button className="on">앱</button><button>웹</button></div></div>
      <div className="slots">
        {FEATURES.map(f => (
          <div className="slot" key={f.id}><b>{f.id}</b>{f.name}<span>캡처를 끌어다 놓기</span></div>
        ))}
      </div>
    </Frame>
  );
}

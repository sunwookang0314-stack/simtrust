// 화면 7. 새 MVP 점검 (미리보기). 원래 목표(창업자가 새 서비스를 점검, TRD IF-12)를 보여준다.
// 이번 학기는 벤치마크 두 서비스로 신뢰도 지도를 만드는 데까지라 실제 업로드 흐름은 범위 밖이다
import { Link } from "react-router-dom";
import Frame from "../components/Frame.jsx";
import { FEATURES } from "../lib/data.js";

export default function Mvp() {
  return (
    <Frame no={7} title="새 서비스를 올리면, 믿어도 되는 AI 의견만 골라 드려요"
           lead="창업자가 기능별 캡처를 올리면 AI(+페르소나)가 답하고, 이유마다 신뢰도 지도를 붙여 '믿어도 됨 / 사람에게 확인'으로 나눠요. 이번 학기 범위 밖이라 미리보기예요."
           blocks={["신뢰도 지도 (화면 6 결과)", "새 서비스 AI 답의 이유 코드 (자동 매칭이 필요, WBS 5.1)"]}
           waits={["#32 입력 방식: 캡처 업로드 / 기능별 URL (강선우)", "새 서비스에는 사람 설문이 없어서 거름망 대신 지도를 적용한다"]}>
      <div className="form-row"><label>서비스 이름</label><div className="fake-input">예: 동아리 모집 모아보기</div></div>
      <div className="form-row"><label>플랫폼</label><div className="seg"><button className="on">앱</button><button>웹</button></div></div>
      <div className="slots">
        {FEATURES.map(f => (
          <div className="slot" key={f.id}><b>{f.id}</b>{f.name}<span>캡처를 끌어다 놓기</span></div>
        ))}
      </div>
      <p className="basis" style={{ marginTop: 16 }}>벤치마크 결과는 <Link to="/map" style={{ textDecoration: "underline" }}>신뢰도 지도</Link>에서 볼 수 있어요.</p>
    </Frame>
  );
}

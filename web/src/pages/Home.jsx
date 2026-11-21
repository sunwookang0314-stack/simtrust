// 화면 0. 메인: 처음 보는 사람이 10초 안에 "무엇을 하는 도구인지" 알게 한다
// 그림 세 칸(묻기 → 견주기 → 알려주기)으로 전체 흐름을 먼저 보여 주고, 단계 목록은 아래에 작게
import { Link } from "react-router-dom";
import { CHAPTERS } from "../lib/steps.js";
import { HUMAN_POOL } from "../lib/data.js";

// 개념 애니메이션은 레포 mockup/에 있어서 개발 서버에는 없다. 공개 주소로 연다
const CONCEPT_URL = "https://sunwookang0314-stack.github.io/simtrust/mockup/concept.html";

export default function Home() {
  return (
    <div className="page home">
      <section className="hero">
        <h1>AI가 대신 답한 사용자 의견,<br /><span>믿어도 될까요?</span></h1>
        <p>요즘은 사용자 조사를 AI에게 시키기도 해요. SimTrust는 AI가 말한 이유를 <b>진짜 대학생 답</b>과 견줘서, 믿어도 되는지 알려 줘요.</p>
      </section>

      <ol className="idea">
        <li>
          <span className="ino">1</span>
          <h3>AI에게 물어요</h3>
          <div className="ivis">
            <span className="ibub ai">마감 알림, 쓸 것 같아요?<br />왜요?</span>
            <div className="ichips"><i>GPT</i><i>Claude</i><i>Gemini</i><i>페르소나</i></div>
          </div>
          <p>서비스 화면을 보여 주고 기능마다 쓸 이유, 안 쓸 이유를 물어요</p>
        </li>
        <li>
          <span className="ino">2</span>
          <h3>진짜 대학생과 견줘요</h3>
          <div className="ivis">
            <div className="icmp">
              <span className="ok">마감을 안 놓치려고</span>
              <span className="ok">달력을 안 봐도 돼서</span>
              <span className="no">디자인이 예뻐서</span>
            </div>
            <span className="ihum">대학생 {HUMAN_POOL.respondents}명</span>
          </div>
          <p>같은 질문에 답한 대학생도 그 이유를 말했는지 하나씩 맞춰 봐요</p>
        </li>
        <li>
          <span className="ino">3</span>
          <h3>믿어도 되는지 알려줘요</h3>
          <div className="ivis">
            <div className="imap">
              <span className="v-trust">믿고 써도 됨</span>
              <span className="v-ref">참고용</span>
              <span className="v-ask">사람에게 물어볼 것</span>
            </div>
          </div>
          <p>기능마다, AI마다 결과를 지도로 보여 줘요</p>
        </li>
      </ol>

      <div className="cta">
        <Link className="btn pri lg" to="/demo">시연 시작하기 →</Link>
        <Link className="btn lg" to="/map">결과부터 보기</Link>
        <a className="btn ghost" href={CONCEPT_URL} target="_blank" rel="noreferrer">개념 애니메이션 ↗</a>
      </div>

      <nav className="steps-mini" aria-label="시연 순서">
        {CHAPTERS.filter(c => c.no > 0).map(c => <Link key={c.id} to={`/demo?go=${c.id}`}><b>{c.no}</b>{c.name}</Link>)}
      </nav>
    </div>
  );
}

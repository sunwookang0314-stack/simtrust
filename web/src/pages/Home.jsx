// 화면 0. 메인: SimTrust 소개와 검사 흐름
import { Link } from "react-router-dom";
import { STEPS } from "../lib/steps.js";

// 개념 애니메이션은 레포 mockup/에 있어서 개발 서버에는 없다. 공개 주소로 연다
const CONCEPT_URL = "https://sunwookang0314-stack.github.io/simtrust/mockup/concept.html";

export default function Home() {
  return (
    <div className="page home">
      <section className="hero">
        <span className="no">대학생 공고·취업 서비스용 · 오픈소스</span>
        <h1>AI 가상 사용자가 말한 이유,<br />믿어도 될까요?</h1>
        <p>서비스 화면을 AI에게 보여 주고 기능마다 쓸 이유와 안 쓸 이유를 물어요. 그 답을 실제 대학생 설문과 비교해서, 어떤 이유를 믿어도 되는지 판정해 드려요.</p>
        <div className="cta">
          <Link className="btn pri" to="/input">검사 시작</Link>
          <Link className="btn" to="/map">결과 예시 보기</Link>
          <a className="btn ghost" href={CONCEPT_URL} target="_blank" rel="noreferrer">어떻게 판정하나요? ↗</a>
        </div>
      </section>
      <ol className="flow">
        {STEPS.map(s => (
          <li key={s.path}>
            <Link to={`/${s.path}`}>
              <b>{s.no}</b><span>{s.name}</span>
              <small>{s.ready ? "가짜 견본 데이터로 동작" : "화면 틀"}</small>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}

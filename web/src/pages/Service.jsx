// 화면 1. 서비스 고르기: 미리 찍어 둔 벤치마크 서비스(링커리어·캠퍼스픽)의 기능별 화면을 본다
import { Link } from "react-router-dom";
import Shot from "../components/Shot.jsx";
import { CellPicker } from "../components/ui.jsx";
import { FEATURES, HUMAN_POOL, SERVICES } from "../lib/data.js";
import { useCellParams } from "../lib/params.js";

export default function Service() {
  const params = useCellParams();
  const svc = SERVICES.find(s => s.id === params.service).name;

  return (
    <div className="page">
      <div className="phead">
        <span className="no">1 · 서비스 고르기</span>
        <h1>{svc} {params.platform === "app" ? "앱" : "웹"} 화면을 AI에게 보여줄게요</h1>
        <p>AI에게는 화면을 미리 찍어 둔 두 서비스(링커리어·캠퍼스픽)를 보여줘요. 기능 4개마다 한 장씩이에요.</p>
      </div>
      <CellPicker params={params} only={["service", "platform"]} />
      <div className="svc-info">
        <span>사람 쪽은 설문 응답자 <b>{HUMAN_POOL.respondents}명</b>을 합쳐서 비교해요. 공고 서비스 {HUMAN_POOL.services}개 중 자주 쓰는 걸 골라 답했고, 검색·필터·저장·마감 알림·추천은 어느 서비스에나 있는 기능이에요</span>
        <span className="sample">사전등록 11/16 기록</span>
      </div>
      <div className="shots">
        {FEATURES.map(f => (
          <figure key={f.id}>
            <Shot service={params.service} platform={params.platform} feature={f.id} />
            <figcaption><b>{f.id}</b>{f.name}</figcaption>
          </figure>
        ))}
      </div>
      <p className="foot">실제 캡처는 비공개라 그린 화면으로 보여줘요. 발표 때는 <code>web/public/captures/</code>에 캡처를 넣으면 그걸 띄워요 (커밋 안 됨).</p>
      <div className="next">
        <Link className="btn pri" to={`/ask?service=${params.service}&platform=${params.platform}`}>이 화면으로 AI에게 묻기 →</Link>
      </div>
    </div>
  );
}

// 화면 1. 서비스 고르기: 미리 찍어 둔 벤치마크 서비스(링커리어·캠퍼스픽)의 기능별 화면을 본다
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Shot from "../components/Shot.jsx";
import { CellPicker } from "../components/ui.jsx";
import { FEATURES, SERVICES } from "../lib/data.js";
import { useCellParams } from "../lib/params.js";

export default function Service() {
  const params = useCellParams();
  const [total, setTotal] = useState(null);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/sample/summary.json`).then(r => r.json())
      .then(s => setTotal(s.respondents_per_service), () => setTotal(null));
  }, []);
  const svc = SERVICES.find(s => s.id === params.service).name;

  return (
    <div className="page">
      <div className="phead">
        <span className="no">1 · 서비스 고르기</span>
        <h1>{svc} {params.platform === "app" ? "앱" : "웹"} 화면을 AI에게 보여줄게요</h1>
        <p>설문은 여러 공고 서비스로 받았고, 그중 화면을 미리 찍어 둔 두 서비스로 AI와 비교해요. 기능 4개마다 한 장씩이에요.</p>
      </div>
      <CellPicker params={params} only={["service", "platform"]} />
      <div className="svc-info">
        <span>설문에서 가장 자주 쓰는 서비스로 <b>{svc}</b>를 고른 응답자 <b>{total ?? "-"}명</b>과 비교해요</span>
        <span className="sample">가짜 견본 인원</span>
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

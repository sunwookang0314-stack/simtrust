// 기능 화면 한 장. public/captures/에 실제 캡처가 있으면 그걸, 없으면 그린 화면(와이어프레임)을 띄운다
import { useState } from "react";
import { SCREENS } from "../lib/services.js";

const CAPTURE_DIR = `${import.meta.env.BASE_URL}captures/`;

function Wire({ service, platform, feature }) {
  const s = SCREENS[service];
  const line = w => <div className="wl" style={{ width: `${w}%` }} />;
  if (feature === "F1") return (
    <div className="wire">
      <b>{s.F1.title}</b>
      <div className="wsearch">⌕ {s.F1.search}</div>
      <div className="wchips">{s.F1.chips.map(c => <span key={c}>{c} ▾</span>)}</div>
      {[80, 65, 72].map(w => <div className="wcard" key={w}>{line(w)}{line(w - 30)}</div>)}
    </div>
  );
  if (feature === "F2") return (
    <div className="wire">
      <b>{s.F2.title}</b>
      {s.F2.items.map(t => <div className="wcard row" key={t}><span>{t}</span><i className="bm">★</i></div>)}
    </div>
  );
  if (feature === "F3") {
    const f = s.F3[platform];
    return (
      <div className="wire">
        <b>{f.title}</b>
        <div className="whl"><span>{f.row}<small>{f.sub}</small></span>{platform === "app" && <s className="tg" />}</div>
        {line(70)}{line(50)}
      </div>
    );
  }
  return (
    <div className="wire">
      <b>{s.F4[platform]}</b>
      <div className="wcar">{[1, 2, 3].map(i => <div key={i}>{line(80)}{line(50)}</div>)}</div>
      {line(75)}{line(55)}
    </div>
  );
}

export default function Shot({ service, platform, feature, small = false }) {
  const [real, setReal] = useState(true);
  const src = `${CAPTURE_DIR}${service}/${platform}/${feature}.png`;
  return (
    <div className={`shotbox${small ? " small" : ""}`} style={{ "--svc": SCREENS[service].color }}>
      <div className="sbar"><i /><i /><i /><span>{platform === "app" ? "앱" : "웹"} 캡처</span></div>
      {real
        ? <img src={src} alt={`${service} ${feature} 캡처`} onError={() => setReal(false)} />
        : <Wire service={service} platform={platform} feature={feature} />}
    </div>
  );
}

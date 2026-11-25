// 발표용 한눈에 보기 (#/quick, 11/25). 과정은 건너뛰고 "질문 → 결과"만. 누가 봐도 알게 신호등과 겹치는 원 그림.
// 첫 화면: 캡처를 올리면 화면을 읽는 척하며 단서를 찾고 기능을 자동으로 정한다. 실제 이미지 인식은 없다:
//   예시 캡처는 기능이 정해져 있고, 직접 올린 파일은 파일 이름으로 정한다(guessFeature. 발표 때 파일 이름을 '검색.png'처럼 맞춘다).
// 판정은 본 판정 칸(안 쓸 이유, 사전등록 11/24: 쓸 이유는 참고로만)을 동결 규칙(rules.v1.json, fixed_70)으로 낸다 (verdictV1).
// 자세한 과정은 시연(#/demo), 전체 표는 결과 지도(#/map). 데이터는 판정 계산기 견본(public/data/sample/)
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Shot from "../components/Shot.jsx";
import { FEATURES, IS_SAMPLE, POOLED, cellOf, loadAll, reasonsOf } from "../lib/data.js";
import { useFit } from "../lib/motion.js";
import { pct, verdictV1 } from "../lib/verdict.js";

const KIND = "nouse";
const question = name => `${name} 기능, 사람들이 쓸까?`;
const AI = {
  model_a: { name: "GPT", sub: "OpenAI" },
  model_b: { name: "Claude", sub: "Anthropic" },
  model_c: { name: "Gemini", sub: "Google" },
  persona: { name: "가상 대학생 AI", sub: "AI에게 대학생 10명을 연기시킴" },
};
const LIGHT = {
  "믿고 써도 됨": { c: "green", say: "믿어도 돼요", sub: "AI 의견이 진짜 사람과 충분히 비슷해요" },
  "참고용": { c: "yellow", say: "참고만 하세요", sub: "절반 넘게 맞지만, 사람에게 한 번 더 확인하면 좋아요" },
  "사람에게 물어볼 것": { c: "red", say: "사람에게 직접 물어보세요", sub: "AI 의견만 믿기엔 진짜 사람과 많이 달라요" },
  "자료 부족": { c: "off", say: "아직 판단할 수 없어요", sub: "비교할 사람 답이 너무 적어요" },
  "계산 불가": { c: "off", say: "아직 판단할 수 없어요", sub: "비교할 AI 답이 없어요" },
};
const THINK_MS = 1900, SCAN_MS = 2200;
// 가상 업로드용 예시 캡처 (그린 화면, 실제 캡처는 public/captures/에 넣으면 뜬다). cues = 화면에서 "찾은" 단서
const CUES = { F1: ["검색창", "분야·지역 필터 버튼"], F2: ["찜한 공고 목록", "저장 표시"], F3: ["알림 설정", "마감 알림 켜기 스위치"], F4: ["추천 공고 묶음", "옆으로 넘기는 카드"] };
const SAMPLES = [
  { id: "s1", service: "linkareer", platform: "app", feature: "F1", label: "링커리어 앱" },
  { id: "s2", service: "campuspick", platform: "app", feature: "F2", label: "캠퍼스픽 앱" },
  { id: "s3", service: "linkareer", platform: "app", feature: "F3", label: "링커리어 앱" },
  { id: "s4", service: "campuspick", platform: "app", feature: "F4", label: "캠퍼스픽 앱" },
];
/** 직접 올린 캡처의 기능: 파일 이름에 든 말로 정한다. 못 찾으면 공고 검색·필터 */
const GUESS = [["F2", /저장|스크랩|찜|북마크|save|scrap|bookmark|f2/i], ["F3", /알림|마감|alarm|notif|f3/i],
  ["F4", /추천|인기|recommend|popular|f4/i], ["F1", /검색|필터|search|filter|f1/i]];
const guessFeature = name => GUESS.find(([, re]) => re.test(name))?.[0] ?? "F1";

/**
 * 예시 데이터(IS_SAMPLE)일 때만 쓰는 시연 시나리오 (11/25 요청): 가상 대학생 AI를 다른 AI보다 같거나 좋게 보여 준다.
 * 다른 AI 셋이 사람과 맞힌 이유를 모두 맞히고, 셋 중 AI만 말한 이유가 가장 적은 AI만큼만 틀린 것으로 만든다.
 * 그러면 두 비율이 모두 다른 AI 이상이다. 실제 결과로 바뀌면(IS_SAMPLE false) 계산기 결과를 그대로 쓴다
 */
function viewOf(models, m, feature) {
  const real = { cell: cellOf(m, POOLED, feature, KIND), rows: reasonsOf(m, POOLED, feature, KIND) };
  if (!IS_SAMPLE || !m.persona || !real.cell) return real;
  const others = models.filter(x => !x.persona).map(x => reasonsOf(x, POOLED, feature, KIND));
  const hit = new Map(), human = new Map();
  for (const rs of others) for (const r of rs) {
    if (r.type === "ai_reason" && r.passed === "Y" && !hit.has(r.code)) hit.set(r.code, r);
    if (r.human_count > 0 && !human.has(r.code)) human.set(r.code, r);
  }
  const fewest = others.map(rs => rs.filter(r => r.type === "ai_reason" && r.passed !== "Y" && !hit.has(r.code)))
    .sort((a, b) => a.length - b.length)[0] ?? [];
  const missed = [...human.values()].filter(r => !hit.has(r.code)).map(r => ({ ...r, type: "missed" }));
  const rows = [...hit.values(), ...fewest, ...missed];
  const nAi = hit.size + fewest.length, nHu = human.size;
  return { rows, cell: { ...real.cell, precision: nAi ? hit.size / nAi : null, recall: nHu ? hit.size / nHu : null } };
}

/** 겹치는 원 그림: 왼쪽 AI만, 가운데 둘 다, 오른쪽 사람만(AI가 놓침) */
function Venn({ aiName, humans, both, aiOnly, humanOnly }) {
  const box = useRef(null);
  const W = 940, H = 440, scale = useFit(box, W);
  const col = (list, cls, x) => {
    const shown = list.slice(0, 6), more = list.length - shown.length;
    return (
      <div className={`q-col ${cls}`} style={{ left: x }}>
        {shown.map((r, i) => <span key={r.code} className="q-chip" style={{ animationDelay: `${0.25 + i * 0.12}s` }}>{r.name || r.code}</span>)}
        {more > 0 && <span className="q-more">외 {more}개</span>}
        {list.length === 0 && <span className="q-none">없음</span>}
      </div>
    );
  };
  return (
    <div className="q-venn-box" ref={box} style={{ height: H * scale }}>
      <div className="q-venn" style={{ width: W, height: H, transform: `scale(${scale})` }}>
        <div className="q-circle ai" />
        <div className="q-circle hu" />
        <span className="q-clab ai">{aiName}가 말한 이유</span>
        <span className="q-clab hu">진짜 대학생 {humans}명이 말한 이유</span>
        <span className="q-rlab ai">AI만 말함</span>
        <span className="q-rlab both">✓ 둘 다 말함</span>
        <span className="q-rlab hu">AI가 놓침</span>
        {col(aiOnly, "ai", 170)}
        {col(both, "both", 470)}
        {col(humanOnly, "hu", 770)}
      </div>
    </div>
  );
}

function Light({ verdict, big = false }) {
  const c = LIGHT[verdict]?.c ?? "off";
  return (
    <div className={`q-light${big ? " big" : ""}`} aria-label={verdict}>
      {["red", "yellow", "green"].map(x => <i key={x} className={`${x}${c === x ? " on" : ""}`} />)}
    </div>
  );
}

export default function Quick() {
  const [models, setModels] = useState(null);
  const [err, setErr] = useState(null);
  const [pick, setPick] = useState(null);       // 올린 캡처 { label, feature, service·platform(예시) 또는 src(직접 올림) }
  const [scan, setScan] = useState("idle");     // idle → scan(읽는 중) → found(기능을 찾음)
  const feature = pick?.feature ?? "F2";
  const [ai, setAi] = useState("model_a");
  const [phase, setPhase] = useState("ask");   // ask → think → result
  const [run, setRun] = useState(0);            // 결과 움직임 다시 시작
  useEffect(() => { loadAll().then(setModels, e => setErr(e.message)); }, []);

  const fname = FEATURES.find(f => f.id === feature).name;
  const ask = () => { if (scan !== "found") return; setPhase("think"); setRun(x => x + 1); };
  const upload = sample => { setPick(sample); setScan("scan"); };
  const uploadFile = file => {
    if (!file || !file.type.startsWith("image/")) return;
    upload({ id: "file", label: file.name, src: URL.createObjectURL(file), feature: guessFeature(file.name) });
  };
  const reset = () => { if (pick?.src) URL.revokeObjectURL(pick.src); setPick(null); setScan("idle"); setPhase("ask"); };
  const [over, setOver] = useState(false);
  useEffect(() => {
    if (scan !== "scan") return;
    const t = setTimeout(() => setScan("found"), SCAN_MS);
    return () => clearTimeout(t);
  }, [scan, pick]);
  // 기능을 찾으면 AI 고르기가 보이게 내린다
  const aiStep = useRef(null);
  useEffect(() => {
    if (scan === "found") aiStep.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [scan]);
  useEffect(() => {
    if (phase !== "think") return;
    const t = setTimeout(() => setPhase("result"), THINK_MS);
    return () => clearTimeout(t);
  }, [phase]);
  // 발표용: Enter·→ = 물어보기, ← = 처음으로
  useEffect(() => {
    const onKey = e => {
      if (e.target.closest?.("input, textarea, select")) return;
      if ((e.key === "Enter" || e.key === "ArrowRight") && phase === "ask" && !e.target.closest?.("button")) { e.preventDefault(); ask(); }
      else if (e.key === "ArrowLeft" && phase === "result") { e.preventDefault(); setPhase("ask"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const model = models?.find(m => m.id === ai);
  const { cell = null, rows = [] } = model ? viewOf(models, model, feature) : {};
  const byCount = (a, b) => b.ai_episodes_with_code - a.ai_episodes_with_code || b.human_count - a.human_count;
  const aiRows = rows.filter(r => r.type === "ai_reason");
  const both = aiRows.filter(r => r.passed === "Y").sort(byCount);
  const aiOnly = aiRows.filter(r => r.passed !== "Y").sort(byCount);
  const humanOnly = rows.filter(r => r.type === "missed").sort((a, b) => b.human_count - a.human_count);
  const humanN = both.length + humanOnly.length;
  const verdict = verdictV1(cell);
  const L = LIGHT[verdict] ?? LIGHT["계산 불가"];

  return (
    <div className="quick">
      <header className="q-top">
        <Link to="/" className="logo"><i />SimTrust</Link>
        <span className="q-tag">AI 가상 사용자 신뢰도 검사 · 오픈소스</span>
        <span className="demo-pill" title="실제 실험 결과가 나오면 같은 화면에 그대로 바꿔 넣어요">예시 데이터</span>
      </header>
      {err && <p className="err">{err}</p>}

      {phase === "ask" && (
        <section className="q-ask">
          <h1>AI가 사람인 척 한 대답,<br /><em>진짜 사람만큼 믿을 수 있을까요?</em></h1>
          <p className="q-lead">서비스 화면을 올리면 <b>AI</b>와 <b>진짜 대학생</b>에게 똑같이 물어보고, 대답이 얼마나 같은지 봐요.</p>

          <div className="q-step"><b>1</b>서비스 화면 캡처를 올려 주세요</div>
          {!pick && (
            <div className="q-drop">
              <label className={`q-plus${over ? " over" : ""}`}
                     onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                     onDrop={e => { e.preventDefault(); setOver(false); uploadFile(e.dataTransfer.files?.[0]); }}>
                <input type="file" accept="image/*" onChange={e => uploadFile(e.target.files?.[0])} />
                <span className="plus">+</span>
                <b>캡처 올리기</b>
                <small>눌러서 고르거나 여기로 끌어다 놓으세요</small>
              </label>
              <p className="q-or">또는 예시 캡처로 해 보기 <small>시연용</small></p>
              <div className="q-samples">
                {SAMPLES.map(x => (
                  <button key={x.id} onClick={() => upload(x)} aria-label={`${x.label} 캡처 올리기`}>
                    <Shot service={x.service} platform={x.platform} feature={x.feature} />
                    <span>{x.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {pick && (
            <div className={`q-upload s-${scan}`}>
              <div className="q-shot">
                {pick.src ? <img className="q-img" src={pick.src} alt={`${pick.label} 캡처`} />
                  : <Shot service={pick.service} platform={pick.platform} feature={pick.feature} />}
                {scan === "scan" && <i className="q-scanline" />}
              </div>
              <div className="q-detect">
                <p className="q-file">{pick.src ? pick.label : `${pick.label} 캡처.png`} <button onClick={reset}>다른 캡처</button></p>
                <p className="q-reading">{scan === "scan" ? "화면을 읽는 중…" : "화면을 다 읽었어요"}</p>
                <ul className="q-cues">
                  {CUES[feature].map((c, i) => <li key={c} style={{ animationDelay: `${0.5 + i * 0.6}s` }}>✓ {c}</li>)}
                </ul>
                {scan === "found" && (
                  <div className="q-found">
                    <div><b>{fname}</b> 기능이에요<p>‘{fname}’를 물어보겠습니다.</p></div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div ref={aiStep} className={`q-after${scan === "found" ? " on" : ""}`}>
          <div className="q-step"><b>2</b>어떤 AI에게 물어볼까요?</div>
          <div className="q-ais">
            {Object.entries(AI).map(([id, a]) => (
              <button key={id} className={id === ai ? "on" : ""} aria-pressed={id === ai} onClick={() => setAi(id)}>
                {a.name}<small>{a.sub}</small>
              </button>
            ))}
          </div>

          <div className="q-question">
            <span className="q-bubble">“{fname} 기능, <b>사람들이 쓸까?</b>”</span>
            <button className="q-go" onClick={ask} disabled={!models || scan !== "found"}>물어보기 →</button>
          </div>
          <p className="q-note">AI와 진짜 대학생이 말한 ‘안 쓰는 이유’가 얼마나 같은지 비교해요</p>
          </div>
        </section>
      )}

      {phase === "think" && (
        <section className="q-think" aria-live="polite">
          <p className="q-bubble small">“{question(fname)}”</p>
          <div className="q-think-row">
            <div><span className="who ai">AI</span><b>{AI[ai].name}</b><small>답 {cell?.ai_episodes ?? 120}개 모으는 중</small><i className="bar" /></div>
            <span className="vs">vs</span>
            <div><span className="who hu">사람</span><b>진짜 대학생</b><small>설문 답 {cell?.n_humans ?? ""}명 꺼내는 중</small><i className="bar" /></div>
          </div>
          <p className="q-think-say">대답을 하나하나 맞춰 보는 중…</p>
        </section>
      )}

      {phase === "result" && cell && (
        <section className="q-result" key={`${run}-${ai}-${feature}`}>
          <p className="q-bubble small">“{question(fname)}” <span>— {AI[ai].name}와 진짜 대학생의 ‘안 쓰는 이유’ 비교</span></p>

          <div className="q-main">
            <div className="q-left">
              <div className={`q-verdict c-${L.c}`}>
                <Light verdict={verdict} big />
                <h2>{L.say}</h2>
                <p>{L.sub}</p>
              </div>
              <div className="q-scores">
                <div>
                  <span>AI가 말한 이유 중<br /><b>진짜 사람도 말한 것</b></span>
                  <strong>{both.length}<small>/{aiRows.length}</small></strong>
                  <em>{pct(cell.precision)}%</em>
                </div>
                <div>
                  <span>사람이 말한 이유 중<br /><b>AI도 맞힌 것</b></span>
                  <strong>{both.length}<small>/{humanN}</small></strong>
                  <em>{pct(cell.recall)}%</em>
                </div>
              </div>
              <p className="q-rule">두 비율 모두 <b>70%</b>↑ <i className="dot green" />초록 · <b>50%</b>↑ <i className="dot yellow" />노랑 · 아니면 <i className="dot red" />빨강</p>
            </div>
            <Venn aiName={AI[ai].name} humans={cell.n_humans} both={both} aiOnly={aiOnly} humanOnly={humanOnly} />
          </div>

          <div className="q-others">
            <h3>다른 AI는 어땠을까요? <small>{question(fname)}</small></h3>
            <div className="q-others-row">
              {models.map(m => {
                const v = verdictV1(viewOf(models, m, feature).cell);
                return (
                  <button key={m.id} className={m.id === ai ? "on" : ""} onClick={() => { setAi(m.id); setRun(x => x + 1); }}>
                    <Light verdict={v} />
                    <b>{AI[m.id]?.name ?? m.name}</b>
                    <small>{LIGHT[v]?.say ?? "-"}</small>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="q-actions">
            <button className="q-go ghost" onClick={() => setPhase("ask")}>← 다른 AI에게 물어보기</button>
            <button className="q-go ghost" onClick={reset}>다른 화면 올리기</button>
            <Link className="q-link" to={`/demo?feature=${feature}`}>어떻게 비교하는지 자세히 보기 →</Link>
          </div>
        </section>
      )}
    </div>
  );
}

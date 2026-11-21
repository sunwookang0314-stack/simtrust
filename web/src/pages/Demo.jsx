// 시연 한 페이지 (11/21 개편). 질문부터 거름망까지 기능 하나(1장 토글, 기본 마감 알림) · 쓸 이유 칸을 GPT로 따라간다.
// 0장 시작(오프닝 질문) → 1장 묻기 → 2장 칩 만들기 → 3장 거름망(판정 도장, 다른 AI로 바꿔 봄) → 4장 결과. 기능 전체는 결과 지도(/map)에서.
// "다음"(또는 → 키·스페이스) 한 번 = 박자 하나. 장이 바뀌면 그 장으로 스크롤한다. 각 장면은 자기 장 안 박자(localOf)만 안다.
// 주소: ?beat=N (발표 연습용), ?go=장 id (그 장부터), ?feature= (따라갈 기능, 3장 칸도 같이), ?kind= (3장 칸), ?ai= (3장 AI), ?service=&platform= (1장 화면)
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AskScene from "../components/AskScene.jsx";
import AllAnswers from "../components/AllAnswers.jsx";
import ChipStage from "../components/ChipStage.jsx";
import HookScene from "../components/HookScene.jsx";
import ReasonBook from "../components/ReasonBook.jsx";
import SieveStage from "../components/SieveStage.jsx";
import { CellPicker, MetricBar, More, VerdictBadge } from "../components/ui.jsx";
import { FEATURES, HUMAN_POOL, KINDS, POOLED, cellOf, loadAll, reasonsOf } from "../lib/data.js";
import { reduceMotion } from "../lib/motion.js";
import { useBaseModel, useCellParams } from "../lib/params.js";
import { BEATS, CHAPTERS, firstBeat, lastBeat, localOf } from "../lib/steps.js";
import { STORY_KIND, STORY_MODEL, getStory } from "../lib/story.js";
import { VERDICT_STYLE, verdictWhy } from "../lib/verdict.js";

// 3장 거름망 장면을 어느 단계까지 걸릴지 (장 안 박자 → SieveStage 단계 0~6). 박자 4 = 판정 도장
const SIEVE_UPTO = [0, 2, 5, 6, 6];

// 장마다 박자별 제목과 한 줄 설명
function chapterText(ch, k, x) {
  const T = {
    ask: [
      { title: `GPT에게 ${x.name} 화면을 보여 주고 물어봐요`, sub: "진짜 대학생에게 한 설문과 똑같은 질문이에요. 위 토글로 다른 기능도 볼 수 있어요." },
      { title: "GPT가 답했어요", sub: "답은 이렇게 긴 글이에요. 여기서 이유만 골라내야 사람 답과 견줄 수 있어요." },
    ],
    chip: [
      { title: "답에서 이유인 부분만 칠해요", sub: "\"왜 쓸 것 같은지\"에 해당하는 말만 골라요." },
      { title: "칠한 부분을 떼어 내면 이유 칩이 돼요", sub: "답 하나에서 이유 칩 두 개가 나왔어요." },
      { title: "말은 달라도 뜻이 같으면 같은 이름표를 붙여요", sub: `두 칩 모두 이름표는 '${x.n1}'. 이름표는 두 사람이 따로 붙여 보고 맞춰요.` },
      { title: "다른 답도 똑같이 해요", sub: `"${x.p2}" → '${x.n2}'. 표현만 다를 뿐 같은 이유예요.` },
      { title: `답 ${x.episodes}개를 전부 이렇게 하면, 자주 나온 이유일수록 칩이 커져요`, sub: "이제 이 칩들을 진짜 대학생 답과 견줘요." },
    ],
    sieve: [
      { title: "진짜 대학생 답으로 걸러요", sub: `아래 구멍 = 대학생 ${x.humans}명이 말한 이유예요. 구멍을 지나가면 사람도 한 말이에요.` },
      { title: "대학생도 말한 이유는 구멍을 통과해요", sub: "" },
      { title: "대학생이 안 말한 이유는 걸러져요", sub: "AI만 말한 이유예요. 자주 나온 것만 사람에게 확인할 후보로 남겨요." },
      { title: "대학생은 말했는데 AI가 놓친 이유도 있어요", sub: "" },
      { title: `그래서, ${x.model} 말을 믿어도 될까요?`, sub: "위 버튼으로 Claude·Gemini·페르소나 AI도 걸러 볼 수 있어요." },
    ],
    result: [{ title: x.headline, sub: "두 비율이 모두 70%를 넘어야 믿고 써도 돼요. 카드를 누르면 그 AI의 거름망을 다시 봐요." }],
  };
  return T[ch]?.[Math.max(k, 0)];
}

function ModelCard({ model, params, on, pick }) {
  const cell = cellOf(model, POOLED, params.feature, params.kind);
  const rs = reasonsOf(model, POOLED, params.feature, params.kind);
  const ai = rs.filter(r => r.type === "ai_reason");
  const hit = ai.filter(r => r.passed === "Y").length;
  const humans = rs.filter(r => r.human_count > 0).length;
  const found = ai.filter(r => r.human_count > 0).length;
  if (!cell) return <section className="mcol empty"><h3>{model.name}</h3><p>이 칸에는 결과가 없어요</p></section>;
  return (
    <button className={`mcol${on ? " on" : ""}`} onClick={pick} aria-pressed={on}>
      <header>
        <h3>{model.name}</h3>
        <small>{model.persona ? "가상 대학생 10명" : "그대로 물어봄"}</small>
      </header>
      <VerdictBadge verdict={cell.verdict} />
      <p className="why">{verdictWhy(cell)}</p>
      <MetricBar label="AI 이유가 맞은 비율" value={cell.precision} hit={hit} total={ai.length} />
      <MetricBar label="사람 이유를 찾은 비율" value={cell.recall} hit={found} total={humans} />
    </button>
  );
}

export default function Demo() {
  const params = useCellParams();
  const [sp, setSp] = useSearchParams();
  const [base] = useBaseModel();
  const [models, setModels] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { loadAll().then(setModels, e => setErr(e.message)); }, []);

  // 처음 박자: ?beat=N (발표 연습용), ?go=장 (지도·메인에서 올 때). 거름망·결과는 그 장 끝, 나머지는 그 장 처음
  const [beat, setBeat] = useState(() => {
    const n = Number(sp.get("beat")), go = sp.get("go");
    if (Number.isInteger(n) && n > 0) return Math.min(n, BEATS.length - 1);
    if (go === "sieve" || go === "result") return lastBeat(go);
    if (CHAPTERS.some(c => c.id === go)) return firstBeat(go);
    return 0;
  });
  const ch = BEATS[beat].ch;
  const chIdx = CHAPTERS.findIndex(c => c.id === ch);
  const secs = useRef({});

  // 장이 바뀌면 그 장으로 스크롤 (주소로 가운데 장부터 열었으면 처음에도)
  const prevCh = useRef(beat > 0 ? null : ch);
  useEffect(() => {
    if (prevCh.current === ch) return;
    prevCh.current = ch;
    secs.current[ch]?.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
  }, [ch]);

  const next = () => setBeat(b => Math.min(b + 1, BEATS.length - 1));
  const prev = () => setBeat(b => Math.max(b - 1, 0));
  useEffect(() => {
    const onKey = e => {
      if (e.target.closest?.("input, textarea, select")) return;
      const onButton = e.target.closest?.("button, summary, a");
      if (e.key === "ArrowRight" || (e.key === " " && !onButton)) { e.preventDefault(); setBeat(b => Math.min(b + 1, BEATS.length - 1)); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); setBeat(b => Math.max(b - 1, 0)); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pickId = models?.some(m => m.id === sp.get("ai")) ? sp.get("ai") : STORY_MODEL;
  const setPick = id => { const n = new URLSearchParams(sp); n.set("ai", id); setSp(n, { replace: true }); };

  const story = getStory(params.feature);
  const storyM = models?.find(m => m.id === STORY_MODEL);
  const storyRows = storyM ? reasonsOf(storyM, POOLED, story.feature, STORY_KIND) : null;
  const nameOf = code => storyRows?.find(r => r.code === code)?.name ?? code;
  const quoteRow = storyRows?.find(r => r.type === "ai_reason" && r.code === story.quoteCode);
  const [p1, , p2] = story.pieces;
  const pickM = models?.find(m => m.id === pickId);
  const sieveCell = pickM ? cellOf(pickM, POOLED, params.feature, params.kind) : null;
  const label = k => ({ feature: FEATURES, kind: KINDS })[k].find(x => x.id === params[k]).name;
  let headline = "결과";
  if (models) {
    const vs = models.map(m => [m.name, cellOf(m, POOLED, params.feature, params.kind)?.verdict]).filter(x => x[1]);
    const best = Math.min(...vs.map(([, v]) => VERDICT_STYLE[v]?.rank ?? 9));
    const top = vs.filter(([, v]) => (VERDICT_STYLE[v]?.rank ?? 9) === best);
    const who = top.length === vs.length ? "AI 넷 모두" : top.map(x => x[0]).join("·");
    headline = `${label("feature")}의 ${label("kind")}: ${who} ${best === 0 ? "믿고 써도 돼요" : best === 1 ? "참고할 만해요" : "아직 사람에게 물어봐야 해요"}`;
  }
  const ctx = { episodes: quoteRow?.ai_episodes ?? 120, humans: sieveCell?.n_humans ?? "", headline, model: pickM?.name ?? "GPT",
                name: story.name, n1: nameOf(p1.code), p2: p2.t, n2: nameOf(p2.code) };
  const local = id => localOf(beat, id);
  const chapState = i => (i < chIdx ? "past" : i === chIdx ? "now" : "future");

  // 장 하나. 컴포넌트로 만들면 렌더마다 다시 붙어서 움직임이 끊기니 함수로 부른다
  const sec = (c, body, { bare = false } = {}) => {
    const t = chapterText(c.id, local(c.id), ctx);
    return (
      <section ref={el => { secs.current[c.id] = el; }} className={`chap ch-${c.id} ${chapState(CHAPTERS.indexOf(c))}`} aria-label={`${c.name}`}>
        {!bare && t && (
          <div className="chead">
            <span className="cno">{c.no} · {c.name}</span>
            <h2 key={t.title}>{t.title}</h2>
            {t.sub && <p key={t.sub}>{t.sub}</p>}
          </div>
        )}
        {body}
      </section>
    );
  };
  const byId = Object.fromEntries(CHAPTERS.map(c => [c.id, c]));

  return (
    <div className="page demo">
      {err && <p className="err">{err}</p>}

      {sec(byId.hook, <HookScene key={story.feature} step={local("hook")} story={story} top={quoteRow} />, { bare: true })}

      {sec(byId.ask, <>
        <div className="svc-toggle"><CellPicker params={params} only={["feature", "service", "platform"]} /></div>
        <AskScene step={local("ask")} story={story} service={params.service} platform={params.platform} />
        <More label="AI 4개 답 전체 보기"><AllAnswers base={base} /></More>
      </>)}

      {sec(byId.chip, <>
        <ChipStage key={story.feature} step={local("chip")} story={story} rows={storyRows} />
        <More label="뽑은 이유 전체 보기"><ReasonBook /></More>
      </>)}

      {sec(byId.sieve, models && (
        <SieveStage models={models} params={params} pick={pickId} onPick={setPick}
                    upto={SIEVE_UPTO[local("sieve")] ?? -1} stamp={local("sieve") >= 4} cellLabel={`${label("feature")} ${label("kind")}`} />
      ))}

      {sec(byId.result, <>
        <div className="other-cell"><span>다른 칸도 볼 수 있어요</span><CellPicker params={params} only={["feature", "kind"]} /></div>
        {models && (
          <div className="mcols">
            {models.map(m => <ModelCard key={m.id} model={m} params={params} on={m.id === pickId}
                                        pick={() => { setPick(m.id); setBeat(lastBeat("sieve")); }} />)}
          </div>
        )}
        <div className="result-foot">
          <More label="판정은 어떻게 하나요?">
            <p>두 비율이 <b>모두 70% 이상이면 믿고 써도 됨</b>, 모두 50% 이상이면 참고용, 아니면 사람에게 물어볼 것이에요. 막대의 눈금 두 개가 50%와 70%예요.</p>
            <p>비교 대상은 같은 질문에 답한 대학생 {HUMAN_POOL.respondents}명({HUMAN_POOL.services}개 공고 서비스 합침)이에요.
              대학생은 안 말했지만 AI 답의 1/3 이상에서 나온 이유는 버리지 않고 <b>사람에게 확인할 후보</b>로 남겨요 (판정 점수에는 안 넣어요).</p>
            <p className="basis">판정 규칙 fixed_70 (11/22 동결) · 지금 견본은 규칙 초안(main)으로 낸 판정이라 막대와 판정이 안 맞는 칸이 있어요</p>
          </More>
          <Link className="btn pri lg" to={`/map?kind=${params.kind}`}>기능 전체 결과 보기 →</Link>
        </div>
      </>)}

      <nav className="ctrl" aria-label="시연 진행">
        <button className="cprev" onClick={prev} disabled={beat === 0} aria-label="이전">←</button>
        <ol>
          {CHAPTERS.map((c, i) => (
            <li key={c.id} className={chapState(i)}>
              <button onClick={() => setBeat(firstBeat(c.id))}>{c.no > 0 && <b>{c.no}</b>}{c.name}</button>
            </li>
          ))}
        </ol>
        {BEATS[beat].next
          ? <button className="cnext" onClick={next}>다음: {BEATS[beat].next} →</button>
          : <Link className="cnext" to={`/map?kind=${params.kind}`}>기능 전체 결과 보기 →</Link>}
      </nav>
    </div>
  );
}

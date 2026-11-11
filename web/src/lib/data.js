// 판정 계산기(scripts/score_reasons.py) 결과 파일을 읽는다.
// 지금은 public/data/sample/의 가짜 견본이고, 실제 결과가 나오면 DATA_DIR의 파일만 바꾼다.

const DATA_DIR = `${import.meta.env.BASE_URL}data/sample/`;

// 기말 데모(#35)의 세 AI 자리. 견본은 model_a/b/c라 이름만 붙여 둔다
export const MODELS = [
  { id: "model_a", name: "AI A", seat: "GPT 자리", note: "사람 같은 모델 (가짜)" },
  { id: "model_b", name: "AI B", seat: "Claude 자리", note: "반만 맞는 모델 (가짜)" },
  { id: "model_c", name: "AI C", seat: "Gemini 자리", note: "공통 이유만 말하는 모델 (가짜)" },
];

// 폼 B v2 4-3 행 (docs/ai-protocol/features.txt)
export const FEATURES = [
  { id: "F1", name: "공고 검색·필터" },
  { id: "F2", name: "공고 저장" },
  { id: "F3", name: "마감 알림" },
  { id: "F4", name: "추천 공고 목록" },
];

// 스냅샷 service 값 → 화면 이름
export const SERVICES = [
  { id: "linkareer", name: "링커리어" },
  { id: "campuspick", name: "캠퍼스픽" },
];

// 사람 쪽 kind. nouse_quit(그만둔 사람)은 참고용이라 화면 기본 목록에서 뺀다
export const KINDS = [
  { id: "nouse", name: "안 쓸 이유" },
  { id: "use", name: "쓸 이유" },
];

/** 따옴표 칸과 BOM을 처리하는 작은 CSV 파서. 첫 줄을 칸 이름으로 쓴다. */
export function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  const src = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"' && src[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && src[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows;
  return body.map(r => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}

const num = v => (v === "" || v == null ? null : Number(v));

async function fetchCsv(name) {
  const res = await fetch(DATA_DIR + name);
  if (!res.ok) throw new Error(`${name}을 못 읽었어요 (${res.status})`);
  return parseCsv(await res.text());
}

let cache = null;

/** 모델마다 칸(cells)과 이유(reasons). 판정 칸(scope=main)만 남긴다. */
export function loadAll() {
  cache ??= Promise.all(MODELS.map(async m => {
    const [cells, reasons] = await Promise.all([fetchCsv(`cells_${m.id}.csv`), fetchCsv(`reasons_${m.id}.csv`)]);
    return {
      ...m,
      cells: cells.filter(c => c.scope === "main").map(c => ({
        ...c, n_humans: num(c.n_humans), ai_episodes: num(c.ai_episodes),
        precision: num(c.precision), recall: num(c.recall),
      })),
      reasons: reasons.filter(r => r.scope === "main").map(r => ({
        ...r, human_count: num(r.human_count), n_humans: num(r.n_humans),
        ai_episodes_with_code: num(r.ai_episodes_with_code), ai_episodes: num(r.ai_episodes),
      })),
    };
  }));
  return cache;
}

// ② AI 다수결 망 (11/11 확정): 사람이 안 말한 이유 중 AI 답의 이 비율 이상에서 나온 것은
// "사람에게 확인할 후보"로 따로 보여준다. 판정 점수에는 안 넣는다. 값은 개념 애니메이션(답 30개 중 10개)과 같다
export const MAJORITY_SHARE = 1 / 3;
export const isCandidate = r =>
  r.type === "ai_reason" && r.passed !== "Y" && r.ai_episodes_with_code / r.ai_episodes >= MAJORITY_SHARE;

export const cellOf = (model, service, feature, kind) =>
  model.cells.find(c => c.service === service && c.feature_id === feature && c.kind === kind);

export const reasonsOf = (model, service, feature, kind) =>
  model.reasons.filter(r => r.service === service && r.feature_id === feature && r.kind === kind);

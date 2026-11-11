// 화면 2~4가 같이 쓰는 예시 답 (지어낸 것. 실제 AI 답이나 응답 원문이 아니다).
// 실제 데이터가 나오면 화면 2는 실행기 기록, 화면 3은 추출기 출력(extracted_*.jsonl),
// 화면 4는 판정 시트 가져오기 결과(ai_codes_*.csv, agreement_*.json)로 바꾼다.
import { FEATURES } from "./data.js";

// 폼 4-6 보기 (docs/ai-protocol/options_4-6.txt) → 코드북 v0.1 공통 코드
export const OPTIONS_46 = ["쓰기 번거로워 보여서", "나한테 필요 없을 것 같아서", "다른 앱이나 방법으로 해결해서", "딱히 써볼 생각을 안 해봐서", "기타"];
export const OPTION_CODE = { "쓰기 번거로워 보여서": "C03", "나한테 필요 없을 것 같아서": "C01",
  "다른 앱이나 방법으로 해결해서": "C02", "딱히 써볼 생각을 안 해봐서": "C04", "기타": "C98" };

export const fname = id => FEATURES.find(f => f.id === id)?.name ?? id;

/*
 * use: 쓸 것 같다고 한 기능
 * why: Q-AI-WHY-USE 답 (기능, 원문)
 * nouse: Q-AI-NOUSE 답 (기능 → 고른 보기)
 * masked: 추출기가 이유가 아니라고 가린 줄 (머리말 등)
 * lines: 추출기가 뽑은 이유 줄. c1·c2 = 판정자 두 명이 붙인 코드, fin = 맞춰 본 최종 코드
 */
export const AIS = [
  {
    id: "gpt", name: "GPT", sub: "페르소나 없음 · 조건 0", use: ["F1", "F2", "F3"],
    why: { feature: "F3", text: "마감 알림: 지원할 공고 마감을 놓치지 않으려고 쓸 것 같아요. 따로 달력을 안 봐도 돼서 편할 것 같아요." },
    nouse: { F4: ["나한테 필요 없을 것 같아서"] },
    masked: [],
    lines: [
      { feature: "F3", kind: "use", text: "지원할 공고 마감을 놓치지 않으려고", c1: "U02", c2: "U02" },
      // 코드북 U02 '알아서 알려 줘서 안 챙겨도 된다'에 들어간다. 판정자 1은 결과 표현(편하다)만 보고 U01을 붙임
      { feature: "F3", kind: "use", text: "따로 달력을 안 봐도 돼서 편함", c1: "U01", c2: "U02", fin: "U02" },
    ],
  },
  {
    id: "claude", name: "Claude", sub: "페르소나 없음 · 조건 0", use: ["F1", "F3"],
    why: { feature: "F1", text: "공고 검색·필터: 인턴 공고만 분야별로 보려고 쓸 것 같아요. 필요 없는 공고를 안 봐도 돼요." },
    nouse: { F2: ["쓰기 번거로워 보여서"], F4: ["다른 앱이나 방법으로 해결해서"] },
    masked: [],
    lines: [
      { feature: "F1", kind: "use", text: "인턴 공고만 분야별로 보려고", c1: "F1-U01", c2: "F1-U01" },
      // R1 구체적인 코드 우선: 거른다는 방법이 나오니 F1-U01
      { feature: "F1", kind: "use", text: "필요 없는 공고를 안 봐도 됨", c1: "U01", c2: "F1-U01", fin: "F1-U01" },
    ],
  },
  {
    id: "gemini", name: "Gemini", sub: "페르소나 없음 · 조건 0", use: ["F1", "F2", "F4"],
    why: { feature: "F2", text: "공고 저장: 괜찮은 공고를 모아 두고 주말에 비교하려고 쓸 것 같아요." },
    nouse: { F3: ["딱히 써볼 생각을 안 해봐서"] },
    masked: ["좋은 질문이네요. 기능별로 말씀드리겠습니다."],
    lines: [
      { feature: "F2", kind: "use", text: "괜찮은 공고를 모아 두고 주말에 비교하려고", c1: "F2-U01", c2: "F2-U01" },
    ],
  },
];

// AI + 페르소나 (본실험 조건 2)는 답 30개 중 한 개만 예시로 보여준다
export const PERSONA_EXAMPLE = {
  id: "persona", name: "페르소나 AI", sub: "바탕 모델 + 페르소나 · 답 30개 중 1개", who: "황민정(22세, 재학생) 1회차",
  why: { feature: "F3", text: "마감 알림: 스크랩한 인턴 공고를 놓치지 않으려고 쓸 것 같아요." },
  nouse: { F4: ["다른 앱이나 방법으로 해결해서"] },
  masked: [],
  lines: [{ feature: "F3", kind: "use", text: "스크랩한 인턴 공고를 놓치지 않으려고", c1: "U02", c2: "U02" }],
};

/** 보기 선택(Q-AI-NOUSE)도 이유 줄이 된다. 보기 → 코드는 정해져 있어서 두 판정자가 같다 */
export function allLines(ai) {
  const opts = Object.entries(ai.nouse).flatMap(([feature, os]) =>
    os.map(o => ({ feature, kind: "nouse", text: o, option: true, c1: OPTION_CODE[o], c2: OPTION_CODE[o] })));
  return [...ai.lines, ...opts].map((l, i) => ({ ...l, id: `${ai.id}-${i + 1}`, ai: ai.id, fin: l.fin ?? l.c1 }));
}

export const EVERYONE = [...AIS, PERSONA_EXAMPLE];

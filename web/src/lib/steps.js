// 기말 시연 흐름 (docs/work-orders/kim-seungha/할일.md 3-1, 11/21 개편).
// 위쪽 메뉴는 시연(한 페이지)과 결과 지도 둘. 옛 화면 1~5(서비스 고르기·AI에게 묻기·이유 뽑기·코드 붙이기·거름망)는
// 시연 한 페이지의 장으로 합쳤고, 새 MVP 점검(학기 범위 밖)은 뺐다. 한눈에(#/quick, 11/25)는 과정을 건너뛴 발표용 질문 → 결과
export const NAV = [
  { path: "quick", name: "한눈에" },
  { path: "demo", name: "시연" },
  { path: "map", name: "결과 지도" },
];

// 시연 한 페이지의 장. 장 안에서는 "다음"이 박자를 넘기고, 장이 바뀌면 스크롤이 내려간다.
// next = 그 장의 박자마다 "다음" 버튼에 쓰는 말(다음에 일어날 일). 길이 = 그 장의 박자 수
export const CHAPTERS = [
  { id: "hook", no: 0, name: "시작", next: ["믿어도 될까?", "직접 확인하기"] },
  { id: "ask", no: 1, name: "묻기", next: ["질문 보내기", "이유 칠하기"] },
  { id: "chip", no: 2, name: "칩 만들기", next: ["떼어 내기", "이름표 붙이기", "다른 답도", "답 120개 모으기", "대학생 답으로 거르기"] },
  { id: "sieve", no: 3, name: "거름망", next: ["통과시키기", "남은 칩 보기", "놓친 이유 보기", "판정 찍기", "AI 넷 비교하기"] },
  { id: "result", no: 4, name: "결과", next: [null] },
];

/** 박자 하나 = "다음" 한 번. { ch: 장 id, local: 장 안 몇 번째, next } */
export const BEATS = CHAPTERS.flatMap(c => c.next.map((next, local) => ({ ch: c.id, local, next })));
export const firstBeat = ch => BEATS.findIndex(b => b.ch === ch);
export const lastBeat = ch => BEATS.findLastIndex(b => b.ch === ch);

/** 장 ch가 지금 박자 beat에서 몇 번째 박자인지. 지난 장 = 마지막 박자, 아직 안 온 장 = -1 */
export function localOf(beat, ch) {
  if (beat < firstBeat(ch)) return -1;
  return Math.min(beat, lastBeat(ch)) - firstBeat(ch);
}

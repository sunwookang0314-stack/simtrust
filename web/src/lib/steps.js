// 기말 화면 흐름 (docs/work-orders/kim-seungha/할일.md 3-1). ready = 데이터가 붙은 화면
export const STEPS = [
  { path: "input", no: 1, name: "검사할 화면" },
  { path: "ask", no: 2, name: "AI에게 묻기" },
  { path: "extract", no: 3, name: "이유 추출" },
  { path: "coding", no: 4, name: "코드 붙이기" },
  { path: "reasons", no: 5, name: "이유별 판정", ready: true },
  { path: "map", no: 6, name: "신뢰도 지도", ready: true },
];

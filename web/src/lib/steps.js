// 기말 화면 흐름 (docs/work-orders/kim-seungha/할일.md 3-1). ready = 데이터나 장면이 붙은 화면
// 1~6 = 벤치마크 검증(이번 학기 본편), 7 = 새 MVP 점검(학기 범위 밖, 미리보기)
export const STEPS = [
  { path: "service", no: 1, name: "서비스 고르기", ready: true },
  { path: "ask", no: 2, name: "AI에게 묻기", ready: true },
  { path: "extract", no: 3, name: "이유 뽑기", ready: true },
  { path: "coding", no: 4, name: "코드 붙이기", ready: true },
  { path: "reasons", no: 5, name: "거름망", ready: true },
  { path: "map", no: 6, name: "신뢰도 지도", ready: true },
  { path: "mvp", no: 7, name: "새 MVP 점검", preview: true },
];

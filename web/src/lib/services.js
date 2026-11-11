// 벤치마크 서비스의 기능별 화면. 실제 캡처는 비공개(TRD SEC-12)라 레포에는 그린 화면(와이어프레임)만 둔다.
// 발표 때 public/captures/{service}/{platform}/{F1~F4}.png 를 넣으면 그 캡처를 띄운다 (.gitignore)
// 문구 근거: docs/form-b/SimTrust-폼B-v2-초안.md 217행 (11/1·11/2 두 서비스 앱·웹 확인 기록)

export const PLATFORMS = [
  { id: "app", name: "앱" },
  { id: "web", name: "웹" },
];

export const SCREENS = {
  linkareer: {
    color: "#3B5BDB",
    F1: { title: "대외활동 · 공모전", search: "검색어를 입력하세요", chips: ["분야", "대상", "지역", "활동 기간"] },
    F2: { title: "스크랩", items: ["2026 대학생 서포터즈 모집", "SW 아이디어 공모전", "하계 인턴십 채용"] },
    F3: { app: { title: "알림 설정", row: "스크랩 공고 알림", sub: "마감 D-1에 알려 드려요" },
          web: { title: "알림함", row: "스크랩한 공고 마감일이 3일 남았습니다", sub: "웹에는 설정이 없고 알림만 와요" } },
    F4: { app: "금주의 인기공고", web: "링커리어 추천활동" },
  },
  campuspick: {
    color: "#E8590C",
    F1: { title: "대외활동", search: "공고 검색", chips: ["분야", "주최", "혜택", "마감순"] },
    F2: { title: "찜한 공고", items: ["대학생 마케터 3기", "환경 공모전", "IT 기업 체험형 인턴"] },
    F3: { app: { title: "알림 설정", row: "마감 임박 알림", sub: "마감 D-3에 알려 드려요" },
          web: { title: "알림 페이지 없음", row: "웹에는 마감 알림 화면이 없어요", sub: "대체 화면으로 보여줘요 (폼 문서 342행)" } },
    F4: { app: "추천 대외활동 공고", web: "추천 대외활동 공고" },
  },
};

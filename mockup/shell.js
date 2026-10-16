// 11개 화면 공통 상단 껍데기. 화면 번호·ID·제목·상태·고정 필터는 app/ui.py SCREENS와 같다.
// 각 페이지는 <body data-no="4-1" data-state="base"> 로 자기 번호를 알려준다.
const GROUPS = {1: "벤치마크 준비", 2: "시뮬레이션", 3: "판정", 4: "결과", 5: "새 MVP 점검"};
const SCREENS = [
  {no: "1-1", title: "서비스·스냅샷", sid: "ST-PR-1001", fixed: {cond: "조건과 무관"}, states: ["기본", "E1 · 화면 변경 감지"], src: "data/snapshots/링커리어/snapshot.json", cmd: "IF-03 register_snapshot.py"},
  {no: "1-2", title: "정답지", sid: "ST-PR-1002", fixed: {cond: "사람 정답지라 조건과 무관"}, states: ["기본", "E2 · 녹취 없는 세션"], src: "data/groundtruth/*.csv", cmd: "IF-07 import_groundtruth.py"},
  {no: "1-3", title: "페르소나 세트", sid: "ST-PR-1003", fixed: {cond: "조건 1~3이 이 세트를 씀 (조건 0은 페르소나 없음)"}, states: ["기본", "E3 · 후보 부족 중단"], src: "data/personas/링커리어/", cmd: "IF-04 make_personas.py"},
  {no: "2-1", title: "실행 기록", sid: "ST-SM-2001", fixed: {cond: "조건 4개 실행을 함께 표시"}, states: ["기본", "E4 · 비용 상한 도달"], src: "data/runs_summary.csv", cmd: "IF-05 run_simulation.py"},
  {no: "2-2", title: "이슈 카드", sid: "ST-SM-2002", fixed: {svc: "두 서비스 합산", cond: "조건 4개 함께 표시"}, states: ["목록", "상세", "E5 · 지적 없음·파싱 실패"], src: "data/virtual/issue_cards.jsonl", cmd: "IF-06 extract_responses.py"},
  {no: "3-1", title: "가상 이슈 묶기", sid: "ST-JD-3001", fixed: {svc: "두 서비스 합산"}, states: ["기본"], src: "data/eval/virtual_issues.csv", cmd: "IF-08·09"},
  {no: "3-2", title: "이슈 매칭 판정", sid: "ST-JD-3002", fixed: {svc: "두 서비스 합산"}, states: ["기본", "E6 · CSV 검증 실패", "E7 · 일치도 미달"], src: "data/eval/matches.csv", cmd: "IF-08·09"},
  {no: "4-1", title: "지표 대시보드", sid: "ST-RP-4001", fixed: {svc: "두 서비스 합산", cond: "조건 4개를 나란히 비교"}, states: ["기본", "E8 · 계산 불가 칸"], src: "data/eval/metrics_all_c0~c3.json", cmd: "IF-10 compute_metrics.py"},
  {no: "4-2", title: "신뢰도 지도", sid: "ST-RP-4002", founder: true, fixed: {svc: "두 서비스 합산", cond: "조건 2 고정 (기준값 동결)"}, states: ["기본", "조건 0과 비교"], src: "data/eval/metrics_all_c2.json", cmd: "IF-10·11"},
  {no: "4-3", title: "시장성 비교", sid: "ST-RP-4003", fixed: {svc: "두 서비스 합산", cond: "AI는 조건 2 고정"}, states: ["기본", "E10 · 표본 적음"], src: "data/eval/reason_matches.csv", cmd: "IF-13·10"},
  {no: "5-1", title: "점검 결과", sid: "ST-MV-5001", founder: true, fixed: {svc: "새 MVP 하나를 점검", cond: "조건 2로 점검"}, states: ["기본", "E11 · 유형 다름"], src: "새 스냅샷 결과 + 신뢰도 지도", cmd: "IF-12 check_mvp.py"},
];
const COND = {0: "페르소나 없음", 1: "나이·직업만", 2: "전체 페르소나", 3: "후기 보강"};
// 창업자 화면은 내부 필터·통계 대신 "무엇과 비교한 판정인지" 한 줄만 보여준다 (PRODUCT.md: 창업자 화면에 조건 번호·CI 금지)
const FOUNDER_CONTEXT = {
  "4-2": "실제 사용자 지적 34건과 비교했어요 · 2026/10/24 기준 (예시)",
  "5-1": "가상 사용자 10명 · 화면 4개 · 판정 기준은 비슷한 서비스 2곳의 실제 사용자 지적 34건",
};
const FOUNDER_NAV = [["4-2", "신뢰도 지도 · 유형별 근거"], ["5-1", "점검 결과 · 내 MVP"]];

const chev = '<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="#8B95A1" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const lock = '<svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1.5" fill="#6B7684"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2" fill="none" stroke="#6B7684" stroke-width="1.6"/></svg>';
const right = '<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function filterPill(label, fixedText, freeText) {
  // 화면이 따르지 않는 필터는 잠그고 고정값을 보여준다
  if (fixedText) return `<span class="fl lock" title="${label} 필터 잠김 · 이 화면은 ${fixedText}">${lock}${fixedText}</span>`;
  // 잠기지 않은 필터는 진짜 select (목업이라 바꿔도 숫자는 그대로다)
  const opts = label === "서비스"
    ? ["전체", "링커리어", "캠퍼스픽"].map(v => v === freeText ? `<option selected>${v}</option>` : `<option disabled>${v} (목업 없음)</option>`).join("")
    : Object.entries(COND).map(([c, n]) => c === "2" ? `<option selected>${c} · ${n}</option>` : `<option disabled>${c} · ${n} (목업 없음)</option>`).join("");
  return `<label class="fl"><span>${label}</span><select aria-label="${label}">${opts}</select>${chev}</label>`;
}

function renderShell() {
  const no = document.body.dataset.no;
  const stateIdx = Number(document.body.dataset.state || 0);
  const s = SCREENS.find(x => x.no === no);
  const g = Number(no[0]);
  const mvp = g === 5;
  const nav = Object.entries(GROUPS).map(([k, v]) => {
    const first = SCREENS.find(x => x.no[0] === k);
    return `<a href="${first.no}.html" class="${Number(k) === g ? "on" : ""}"${Number(k) === g ? " aria-current=\"page\"" : ""}>${v}${Number(k) <= 4 ? "" : "<small>창업자</small>"}</a>`;
  }).join("");
  const subj = mvp
    ? `<div class="subj"><span class="ic">동</span><span class="nm">동아리 모집 모아보기</span><span class="ty">정보 탐색형 · 바이브코딩 (1인 창업자)</span></div>`
    : `<div class="subj"><span class="ic">B</span><span class="nm">벤치마크</span><span class="ty">링커리어 · 캠퍼스픽</span></div>`;
  const filters = `<div class="filters">${filterPill("서비스", s.fixed.svc, "전체")}${filterPill("조건", s.fixed.cond, "조건 2 · 전체 페르소나")}</div>`;
  const stats = mvp
    ? [["가상 사용자", "10명"], ["점검한 화면", "4개"], ["벤치마크 정답지", "34건"]]
    : g === 4 ? [["정답지 이슈", "34건"], ["비교 조건", "4개"], ["조건당 과제 실행", "120건"], ["기준값 동결", "2026/10/24 (예시)"]] : [];
  const tabs = SCREENS.filter(x => x.no[0] === no[0]).map(x =>
      `<a href="${x.no}.html" class="${x.no === no ? "on" : ""}"${x.no === no ? " aria-current=\"page\"" : ""}><i>${x.no}</i>${x.title}${x.founder ? '<span class="tag">창업자</span>' : ""}</a>`).join("");
  const founderTabs = FOUNDER_NAV.map(([n, label]) => `<a href="${n}.html" class="${n === no ? "on" : ""}"${n === no ? " aria-current=\"page\"" : ""}>${label}</a>`).join("");
  // 데모 상태: 목업으로 그린 상태만 고를 수 있고, 안 그린 상태는 "(목업 없음)"으로 막는다
  const DRAWN = {"2-2": {1: "2-2.html?state=detail#detail"}};
  const stateOpts = s.states.map((name, k) => {
    const url = k === 0 ? `${no}.html` : (DRAWN[no] || {})[k];
    return `<option value="${url || ""}"${k === stateIdx ? " selected" : ""}${url ? "" : " disabled"}>${name}${url ? "" : " (목업 없음)"}</option>`;
  }).join("");
  const state = s.states.length > 1
    ? `<label class="state"><span>데모 상태</span><select aria-label="데모 상태" onchange="if(this.value)location.href=this.value">${stateOpts}</select>${chev}</label>` : "";
  const tabRow = s.founder
    ? `<div class="tabs"><span class="tabs-label">창업자 화면</span>${founderTabs}</div>`
    : `<div class="tabs">${tabs}<div class="sp"></div><span class="sid">${s.sid}</span>${state}</div>`;
  const headRight = s.founder
    ? `<div class="ctx">${FOUNDER_CONTEXT[no]}</div>`
    : `${filters}<div class="stats">${stats.map(([a, b]) => `<div><span>${a}</span><b>${b}</b></div>`).join("")}</div>`;
  const top = document.createElement("header");
  top.className = "top";
  top.innerHTML = `<div class="in">
    <div class="gnb"><a class="logo" href="1-1.html"><i></i>SimTrust</a><nav aria-label="단계">${nav}</nav><div class="sp"></div><span class="demo">데모 화면 · 숫자는 예시</span></div>
    <div class="head">${subj}${headRight}</div>
    ${tabRow}</div>`;
  document.body.prepend(top);

  // 바닥: 출처 + 다음 화면
  const i = SCREENS.indexOf(s);
  const last = i === SCREENS.length - 1;
  const nxt = SCREENS[(i + 1) % SCREENS.length];
  const bottom = document.createElement("footer");
  bottom.className = "in bottom";
  const extra = document.body.dataset.extra ? document.body.dataset.extra.split("|").map(t => `<br>${t}`).join("") : "";
  const src = s.founder
    ? `<details class="srcfold"><summary>${document.body.dataset.extra ? "데이터 출처 · 점검 설정" : "데이터 출처"}${chev}</summary><div class="src">출처 <code>${s.src}</code> · ${s.cmd}${extra}<br>화면 ID ${s.sid}${s.states.length > 1 ? ` · 데모 상태 ${s.states[stateIdx]} (상태 ${s.states.length}개: ${s.states.join(", ")})` : ""}<br>발표 순서 <a class="lnk" href="${nxt.no}.html">${last ? "처음으로 · 1-1 서비스·스냅샷" : `다음 · ${nxt.no} ${nxt.title}`}</a></div></details>`
    : `<div class="src">출처 <code>${s.src}</code> · ${s.cmd}</div>`;
  // 창업자 화면에서 주 버튼이 내부 화면으로 보내지 않게: 4-2는 내 점검 결과로 돌아가고, 5-1은 본문의 "판정 근거" 링크가 다음 행동이다
  const nextBtn = s.founder
    ? (no === "4-2" ? `<a class="next" href="5-1.html">내 점검 결과로 돌아가기${right}</a>` : "")
    : `<a class="next${last ? " ghost" : ""}" href="${nxt.no}.html">${last ? "처음으로" : `다음 · ${nxt.no} ${nxt.title}`}${right}</a>`;
  bottom.innerHTML = `${src}${nextBtn}`;
  document.body.append(bottom);
}
renderShell();

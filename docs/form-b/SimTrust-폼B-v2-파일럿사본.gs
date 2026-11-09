// SimTrust 폼 B v2 파일럿 사본 스크립트 (11/9)
// 사전등록 v1 3장 "지인 3~5명에게 폼 사본으로 받는다"를 그대로 하는 스크립트다.
// 본 폼을 드라이브 "사본 만들기"로 복사하고, 사본 제목 앞에 [파일럿]만 붙이고, 사본만 게시한다.
// 11/3 생성 스크립트로 폼을 새로 만들지 않고 복사하는 이유: 본 폼을 띄운 뒤 손으로 고친 게 있어도 사본에는 그대로 들어간다.
// 본 폼은 읽기만 한다. 본 폼의 제목·문항·설정·응답·응답 시트는 하나도 안 고친다.
//
// 사용법
// 1. script.google.com → 새 프로젝트 (본 폼을 만들 때 쓴 프로젝트에 붙여넣지 않는다)
// 2. 기본 코드(function myFunction)를 지우고 이 코드 전체 붙여넣기
// 3. 바로 아래 MAIN_FORM_EDIT_URL 따옴표 안에 본 폼 "편집" 링크를 붙여넣기
//    (구글폼 편집 화면 주소창에 있는, /edit 로 끝나는 링크. 응답자에게 뿌린 viewform·forms.gle 링크는 안 된다)
// 4. 함수 선택에서 createPilotCopy → 실행. 권한 요청이 뜨면 허용한다 (드라이브 권한은 사본 만들기에 쓴다)
// 5. 실행 로그 마지막 줄이 "검사 통과"일 때만 다음으로 간다.
//    "멈춤"이나 "보내지 마라"가 찍히면 로그 전체를 복사해서 가져온다.
//    사본이 만들어진 뒤에 실패했으면 드라이브에서 [파일럿] 사본을 지우고 다시 실행한다 (안 지우면 "이미 있다"로 멈춘다).
// 6. 지인에게 보낼 바로 그 링크(로그의 "파일럿 응답 링크")를 시크릿 창에서 열어 첫 페이지가 뜨는지만 본다.
//    [제출]을 누르면 그 응답이 파일럿 응답 CSV에 들어가니, 실수로 끝까지 가지 않게 [다음]도 누르지 않는다.
//    로그인 화면이나 권한 요청 화면이 뜨면 사본 편집 화면의 게시 설정에서 응답자를 "링크가 있는 모든 사용자"로 바꾸고 다시 연다.
// 7. 로그의 응답 링크 두 개(파일럿, 본 폼)를 복사해서 Claude에게 준다. 6단계에서 연 것 말고는 더 열지 않는다.
//    응답자 화면 데이터를 읽기만 해서 글자 단위로 대조한다(제출하지 않으니 응답이 안 생긴다).

// 본 폼 편집 링크
const MAIN_FORM_EDIT_URL = '';

// 사본 제목 앞에 붙이는 말. 응답자 화면 맨 위에 보인다
const PREFIX = '[파일럿] ';

// 본 폼이 11/3 생성 스크립트 구조와 다르면 사본을 만들기 전에 멈춘다.
// 다른 곳을 로그로 확인한 뒤에 그래도 본 폼 그대로 복사할 거면 true 로 바꾼다
const ALLOW_DIFF_FROM_SCRIPT = false;

// 이미 [파일럿] 사본이 드라이브에 있으면 하나 더 만들지 않는다. 지인마다 다른 링크가 가는 사고를 막는다
const MAKE_ANOTHER_COPY = false;

// ── 11/3 생성 스크립트(SimTrust-폼B-v2-생성.gs)가 만든 구조. 글자 하나까지 그 파일에서 가져왔다 ──
// v1 폼과 드라이브 이름이 같아서, v1 링크를 잘못 넣으면 여기서 걸린다
const EXP_DURATION = '8~10분';
const EXP_CONTACT = 'sunwookang0314@gmail.com';
const EXP_PURPOSES = ['공모전·대회', '인턴·채용 공고', '대외활동·서포터즈', '동아리·학회', '합격 후기·자소서', '커뮤니티 글', '기타'];
const EXP_FEATURES = ['공고 검색·필터', '공고 저장 (스크랩, 찜, 북마크)', '마감 알림', '추천 공고 목록 (인기 공고, 맞춤 추천)'];
const EXP_SERVICES = ['링커리어', '에브리커리어(캠퍼스픽)', '위비티', '캐치', '씽굿', '올콘', '사람인', '잡코리아'];

function expectedSettings() {
  return {
    description:
      '안녕하세요. 한성대학교 오픈소스 프로젝트 팀 SimTrust입니다.\n\n' +
      '공모전·대회·인턴·취업 공고 서비스에서 어떤 기능을 왜 쓰고 왜 안 쓰는지, 쓰면서 불편했던 점은 뭐였는지 모으고 있습니다. ' +
      '응답은 연구에만 쓰고, 이름이나 연락처는 받지 않습니다. ' +
      '성별이나 출생연도 같은 기본 정보는 응답자 구성을 파악하고, 그 구성에 맞춰 비교용 AI 가상 응답자를 고르는 데 씁니다. ' +
      '응답 내용은 외부 AI 서비스에 보내지 않습니다. ' +
      '원문은 공개하지 않고 익명으로 정리한 결과만 공개합니다.\n\n' +
      '중간에 그만두셔도 괜찮습니다.\n\n' +
      '소요 시간 ' + EXP_DURATION + ' / 문의 ' + EXP_CONTACT,
    confirmationMessage: '응답해주셔서 감사합니다.',
    progressBar: true,
    collectsEmail: false,
  };
}

function expectedItems() {
  const birthYears = [];
  for (let y = 2008; y >= 1990; y--) birthYears.push(y + '년');
  birthYears.push('1989년 이전', '응답하지 않음');
  const mc = (title, choices, other, help) =>
    ({ type: 'MULTIPLE_CHOICE', title: title, help: help || '', required: true, other: !!other, choices: choices });
  const page = (title, help) => ({ type: 'PAGE_BREAK', title: title, help: help || '', nav: '' });
  const para = (title, help, required) => ({ type: 'PARAGRAPH_TEXT', title: title, help: help, required: required });
  return [
    mc('설문 참여에 동의하시나요?', ['동의합니다', '동의하지 않습니다 → SUBMIT']),
    page('기본 정보'),
    mc('학년 또는 현재 상태', [
      '1학년', '2학년', '3학년', '4학년 이상', '휴학 중', '졸업유예',
      '졸업 후 취업 준비 중 (졸업 1년 이내)', '졸업 후 취업 준비 중 (졸업 1년 넘음)',
      '졸업 후 직장 다니는 중',
    ], true),
    mc('학교 구분 (졸업했다면 졸업한 학교)', ['4년제 대학', '전문대학', '기타']),
    mc('성별', ['남성', '여성', '응답하지 않음']),
    { type: 'LIST', title: '출생연도', help: '', required: true, choices: birthYears },
    mc('전공 계열', ['인문', '사회', '경영·경제', '공학', '자연', '예체능', '기타']),
    mc('최근 6개월 안에 공모전·대회·인턴·취업 공고 서비스를 써보신 적이 있나요?',
      ['있다 → 페이지: 서비스 고르기', '없다 → 페이지: 마무리']),
    page('서비스 고르기'),
    { type: 'CHECKBOX', title: '최근 6개월 안에 써보신 서비스를 모두 골라주세요.', help: '', required: true, other: false,
      choices: EXP_SERVICES.concat(['기타']) },
    mc('이 중 가장 자주 쓰시는 서비스 한 곳을 골라주세요.', EXP_SERVICES, true, '여기서부터는 이 서비스에 대해서만 여쭙니다.'),
    mc('주로 어디서 쓰시나요?', ['앱', '웹사이트']),
    page('기능별 사용 경험', '앞에서 고르신 서비스를 최근에 썼던 때를 떠올리며 답해주세요.'),
    { type: 'CHECKBOX', title: '주로 무엇을 찾으려고 쓰셨나요?', help: '', required: true, other: false, choices: EXP_PURPOSES },
    mc('가장 최근에 쓰셨을 때, 찾던 걸 찾으셨나요?', [
      '바로 찾았다', '좀 헤매다가 찾았다', '못 찾고 나왔다', '딱히 찾던 건 없었다 (그냥 둘러봤다)', '기억나지 않는다',
    ]),
    { type: 'GRID', title: '아래 기능을 지금 어떻게 쓰고 계신가요?', help: '', required: true, rows: EXP_FEATURES,
      columns: ['자주 쓴다', '가끔 쓴다', '써봤는데 지금은 안 쓴다', '안 써봤다', '이 서비스에 있는지 모르겠다'] },
    para('자주 쓰거나 가끔 쓰는 기능은 왜 계속 쓰시나요?', [
      '위 표에서 자주 쓰거나 가끔 쓴다고 고른 기능마다 줄을 바꿔서 적어주세요.',
      '한 줄에 아래 세 가지가 들어가면 됩니다.',
      '- 기능 이름',
      '- 가장 최근에 뭘 하려고 그 기능을 썼는지',
      '- 그 기능 덕분에 뭐가 편해졌는지',
      '',
      '"편해서"처럼 한 마디로 끝내지 말고 아래처럼 적어주세요.',
      '',
      '예시 (위 표에 없는 기능으로 들었습니다)',
      '합격 후기: 지난주 인턴 면접 전에 작년 합격자 후기를 보려고 썼습니다. 실제로 나온 면접 질문이 정리돼 있어서 다른 데서 따로 안 찾아보고 그것만 보고 준비했습니다.',
      '공고 공유: 어제 같이 공모전 나갈 친구한테 공고를 보내려고 썼습니다. 카톡 공유 버튼을 한 번 누르니까 바로 보내져서 링크를 따로 복사할 필요가 없었습니다.',
      '',
      '계속 쓰는 기능이 없다면 "없음"이라고 적어주세요.',
    ].join('\n'), true),
    { type: 'CHECKBOX_GRID', title: '써봤는데 지금은 안 쓰는 기능이 있다면, 안 쓰게 된 이유에 가까운 것을 골라주세요.',
      help: '위에서 "써봤는데 지금은 안 쓴다"를 고른 기능 줄만 골라주세요. 여러 개 골라도 됩니다.', required: false,
      rows: EXP_FEATURES, columns: ['써보니 불편해서', '나한테 필요 없어서', '다른 앱이나 방법으로 해결해서', '기타'] },
    { type: 'CHECKBOX_GRID', title: '한 번도 안 써본 기능이 있다면, 안 써본 이유에 가까운 것을 골라주세요.',
      help: '위에서 "안 써봤다"를 고른 기능 줄만 골라주세요. 여러 개 골라도 됩니다.', required: false,
      rows: EXP_FEATURES, columns: ['쓰기 번거로워 보여서', '나한테 필요 없을 것 같아서', '다른 앱이나 방법으로 해결해서', '딱히 써볼 생각을 안 해봐서', '기타'] },
    para('안 쓰게 됐거나 안 써본 기능이 있다면, 그 이유를 조금 더 자세히 적어주세요.', [
      '위 표에서 안 쓰게 됐거나 안 써봤다고 고른 기능마다 줄을 바꿔서 적어주세요.',
      '- 써봤다가 안 쓰게 된 기능: 마지막으로 썼을 때 뭐가 걸렸는지',
      '- 한 번도 안 써본 기능: 그 기능 대신 지금은 어떻게 하고 계신지',
      '',
      '예시 (위 표에 없는 기능으로 들었습니다)',
      '커뮤니티: 한 달 전쯤 공모전 팀원을 구하려고 글을 올렸는데 사흘 동안 댓글이 하나도 안 달렸습니다. 그 뒤로는 과 단톡방에서 구합니다.',
      '지원 현황 관리: 써본 적은 없습니다. 지원한 공고는 메모장에 날짜랑 결과를 직접 적어서 관리합니다.',
      '',
      '해당하는 기능이 없다면 "없음"이라고 적어주세요.',
    ].join('\n'), true),
    para('계속 쓰는 기능이든 안 쓰는 기능이든, 쓰면서 불편했던 점이 있나요?', [
      '헤맸던 때가 있다면 그때 얘기를 적어주세요.',
      '어느 화면에서, 뭘 하려다가, 뭐가 불편했는지가 들어가면 됩니다.',
      '',
      '예시',
      '공고 상세 화면에서 지원 방법을 찾으려고 했는데, 공고 이미지 맨 아래에만 작게 적혀 있어서 확대해서 읽느라 한참 걸렸습니다.',
      '',
      '없으면 "없음"이라고 적어주세요.',
    ].join('\n'), true),
    para('어떻게 바뀌었으면 하나요?', [
      '위에 적은 불편한 점이 어떻게 바뀌면 좋을지 적어주세요.',
      '',
      '예시',
      '지원 방법은 이미지 말고 공고 맨 위에 글자로 따로 적어주면 좋겠습니다.',
    ].join('\n'), false),
    page('마무리', '아래 [제출] 버튼을 눌러야 응답이 저장됩니다.'),
  ];
}

function createPilotCopy() {
  const started = new Date();
  const mainId = formIdFromEditUrl(MAIN_FORM_EDIT_URL);

  // ── 1. 본 폼 읽기 (읽기만 한다) ──
  const main = FormApp.openById(mainId);
  const mainTitle = main.getTitle();
  if (mainTitle.indexOf(PREFIX) === 0) {
    throw new Error('멈춤: 이 링크는 이미 파일럿 사본이다. 본 폼 편집 링크를 넣어라.');
  }
  const mainItems = describeForm(main);
  const mainSettings = describeSettings(main);
  const mainDest = destinationOf(main);
  // 응답 내용은 안 쓰고 건수만 센다. 0건이면 응답을 받고 있는 본 폼이 아니다(시험용으로 만든 다른 v2 폼 등)
  const mainResponseCount = main.getResponses().length;
  Logger.log('본 폼: ' + mainTitle + ' / 문항·페이지 ' + mainItems.length + '개 / 응답 ' + mainResponseCount + '건');
  if (mainResponseCount === 0) {
    throw new Error('멈춤: 이 폼은 응답이 0건이다. 지금 응답을 받고 있는 본 폼의 편집 링크인지 확인한다. ' +
      '(폼 편집 화면에서 응답을 지우고 응답 시트에만 남겨 둔 경우도 0건으로 나온다.) 사본은 안 만들었다.');
  }

  // ── 2. 본 폼이 11/3 스크립트 구조와 같은지 (사본을 만들기 전에 본다) ──
  const scriptDiffs = diffItems(expectedItems(), mainItems)
    .concat(diffSettings(expectedSettings(), mainSettings, ['description', 'confirmationMessage', 'progressBar', 'collectsEmail']));
  if (scriptDiffs.length > 0) {
    Logger.log('본 폼이 11/3 생성 스크립트와 ' + scriptDiffs.length + '곳 다르다:');
    scriptDiffs.forEach(function (d) { Logger.log('  - ' + d); });
    if (!ALLOW_DIFF_FROM_SCRIPT) {
      throw new Error('멈춤: 사본을 만들지 않았다. 위 차이를 확인하고, 본 폼 그대로 복사할 거면 ALLOW_DIFF_FROM_SCRIPT 를 true 로 바꿔 다시 실행한다.');
    }
    Logger.log('ALLOW_DIFF_FROM_SCRIPT = true 라서 본 폼 그대로 복사한다.');
  } else {
    Logger.log('본 폼 구조 = 11/3 생성 스크립트 구조 (차이 0곳)');
  }

  // ── 3. 이미 만든 파일럿 사본이 있으면 멈춤 ──
  const mainFile = DriveApp.getFileById(mainId);
  const copyName = PREFIX + mainFile.getName();
  const existing = [];
  const found = DriveApp.getFilesByName(copyName);
  while (found.hasNext()) {
    const f = found.next();
    if (!f.isTrashed()) existing.push(f.getUrl());
  }
  if (existing.length > 0 && !MAKE_ANOTHER_COPY) {
    Logger.log('이미 있는 파일럿 사본: ' + existing.join(' , '));
    throw new Error('멈춤: 파일럿 사본이 이미 있다. 그걸 쓰거나, 지우고 다시 실행하거나, 하나 더 만들 거면 MAKE_ANOTHER_COPY 를 true 로 바꾼다.');
  }

  // ── 4. 사본 만들기 (여기서부터는 사본만 고친다) ──
  const pilotId = mainFile.makeCopy(copyName).getId();
  if (pilotId === mainId) throw new Error('멈춤: 사본 ID가 본 폼과 같다. 아무것도 고치지 않았다.');
  const pilot = FormApp.openById(pilotId);
  pilot.setTitle(PREFIX + mainTitle);
  // 여기서부터 생기는 문제는 전부 모아서 마지막에 "검사 통과" 여부를 정한다
  const problems = [];

  // 사본에 응답 시트가 따라붙었으면 끊는다. 그대로 두면 파일럿 응답이 본 응답 시트로 들어갈 수 있다
  const pilotDest = destinationOf(pilot);
  if (pilotDest) {
    pilot.removeDestination();
    Logger.log('사본에 붙어 있던 응답 시트 연결을 끊었다 (본 폼 연결은 그대로).');
    if (pilotDest !== mainDest) {
      // 사본을 만들면서 응답 시트까지 새로 복사된 경우다. 본 응답이 들어 있을 수 있어서 바로 휴지통으로 보낸다
      // 방금 생긴 파일만 지운다. 본 폼 응답 시트는 ID가 같으면 절대 안 건드린다
      const sheetFile = DriveApp.getFileById(pilotDest);
      if (sheetFile.getId() !== mainDest && sheetFile.getDateCreated().getTime() >= started.getTime() - 60 * 1000) {
        sheetFile.setTrashed(true);
        Logger.log('사본과 같이 복사된 응답 시트를 휴지통으로 옮겼다. 열어 보지 말고 드라이브 휴지통에서 영구삭제한다: ' + sheetFile.getName());
      } else {
        problems.push('사본에 본 폼과 다른, 원래 있던 응답 시트가 연결돼 있었다(연결은 끊음). 그 시트가 뭔지 확인 전까지 링크를 보내지 않는다: ' + sheetFile.getName());
      }
    }
  }

  // 사본에 응답이 따라왔으면 사본에서만 지운다 (본 폼 응답은 그대로)
  const copied = pilot.getResponses().length;
  if (copied > 0) {
    pilot.deleteAllResponses();
    Logger.log('사본에 딸려 온 응답 ' + copied + '건을 사본에서 지웠다.');
  }

  // 게시가 먼저다. 미게시 폼에 응답 받기를 켜면 오류가 난다(Form 문서 setAcceptingResponses Throws 항목)
  if (!pilot.isPublished()) pilot.setPublished(true);
  if (!pilot.isAcceptingResponses()) pilot.setAcceptingResponses(true);

  // ── 5. 검사: 사본 = 본 폼 (제목만 다름), 본 폼은 그대로 ──
  diffItems(mainItems, describeForm(pilot)).forEach(function (d) { problems.push('사본 문항이 본 폼과 다름: ' + d); });
  const pilotSettings = describeSettings(pilot);
  diffSettings(mainSettings, pilotSettings, Object.keys(mainSettings)).forEach(function (d) { problems.push('사본 설정이 본 폼과 다름: ' + d); });
  if (pilot.getTitle() !== PREFIX + mainTitle) problems.push('사본 제목이 이상하다: ' + pilot.getTitle());
  if (pilot.getResponses().length !== 0) problems.push('사본 응답이 0건이 아니다');
  if (destinationOf(pilot)) problems.push('사본에 응답 시트가 아직 연결돼 있다');
  if (!pilot.isPublished() || !pilot.isAcceptingResponses()) problems.push('사본이 게시되지 않았거나 응답을 안 받는다');

  const mainAfter = FormApp.openById(mainId);
  if (mainAfter.getTitle() !== mainTitle) problems.push('본 폼 제목이 바뀌었다');
  if (diffItems(mainItems, describeForm(mainAfter)).length > 0) problems.push('본 폼 문항이 바뀌었다');
  if (destinationOf(mainAfter) !== mainDest) problems.push('본 폼 응답 시트 연결이 바뀌었다');

  Logger.log('파일럿 편집 링크: ' + pilot.getEditUrl());
  Logger.log('파일럿 응답 링크(지인에게 보낼 것, 이 링크 하나만): ' + pilot.getPublishedUrl());
  Logger.log('비교용 본 폼 응답 링크(열지 말고 복사만): ' + main.getPublishedUrl());
  Logger.log('사본 응답 시트: ' + destinationNote(pilot));
  Logger.log('15자 검사(정규식)는 스크립트로 읽을 수 없어서 위 검사에 없다. 두 응답 링크를 Claude에게 주면 응답자 화면 데이터로 한 번 더 대조한다.');

  if (problems.length > 0) {
    problems.forEach(function (p) { Logger.log('  - ' + p); });
    Logger.log('보내지 마라: 검사 ' + problems.length + '곳 실패. 로그 전체를 복사해서 가져온다.');
    return;
  }
  Logger.log('검사 통과');
}

// 편집 링크에서 폼 ID를 꺼낸다. 응답 링크는 ID가 달라서 받지 않는다
function formIdFromEditUrl(url) {
  const s = String(url || '').trim();
  if (!s) throw new Error('멈춤: MAIN_FORM_EDIT_URL 이 비어 있다. 본 폼 편집 링크를 따옴표 안에 넣어라.');
  // 계정이 여러 개면 /forms/u/0/d/... 처럼 계정 번호가 끼어 있다
  if (/\/forms\/(?:u\/\d+\/)?d\/e\//.test(s) || /forms\.gle\//.test(s)) {
    throw new Error('멈춤: 응답자용 링크(viewform·forms.gle)다. 구글폼 편집 화면 주소창의 /edit 링크를 넣어라.');
  }
  const m = s.match(/\/forms\/(?:u\/\d+\/)?d\/([A-Za-z0-9_-]{20,})/);
  if (m) return m[1];
  if (/^[A-Za-z0-9_-]{20,}$/.test(s)) return s;
  throw new Error('멈춤: 구글폼 편집 링크가 아니다: ' + s);
}

// 문항 하나를 비교용 값으로 바꾼다. 응답 CSV 열 이름과 보기가 여기서 다 정해진다
// 구글 enum 을 이름으로 바꾼다. String(enum) 결과 형식에 기대지 않고 FormApp 의 값과 직접 맞춰 본다
const ITEM_TYPE_NAMES = ['MULTIPLE_CHOICE', 'CHECKBOX', 'LIST', 'GRID', 'CHECKBOX_GRID', 'PARAGRAPH_TEXT', 'TEXT',
  'PAGE_BREAK', 'SECTION_HEADER', 'SCALE', 'DATE', 'TIME', 'DATETIME', 'DURATION', 'IMAGE', 'VIDEO', 'RATING'];
const NAV_NAMES = ['CONTINUE', 'GO_TO_PAGE', 'RESTART', 'SUBMIT'];
function enumName(table, names, value) {
  if (value === null || value === undefined) return '';
  for (let i = 0; i < names.length; i++) {
    if (table[names[i]] !== undefined && table[names[i]] == value) return names[i];
  }
  return String(value);
}

function describeItem(item) {
  const type = enumName(FormApp.ItemType, ITEM_TYPE_NAMES, item.getType());
  const d = { type: type, title: item.getTitle() || '', help: item.getHelpText() || '' };
  if (type === 'MULTIPLE_CHOICE') {
    const x = item.asMultipleChoiceItem();
    d.required = x.isRequired(); d.other = x.hasOtherOption(); d.choices = x.getChoices().map(describeChoice);
  } else if (type === 'CHECKBOX') {
    const x = item.asCheckboxItem();
    d.required = x.isRequired(); d.other = x.hasOtherOption(); d.choices = x.getChoices().map(describeChoice);
  } else if (type === 'LIST') {
    const x = item.asListItem();
    d.required = x.isRequired(); d.choices = x.getChoices().map(describeChoice);
  } else if (type === 'GRID') {
    const x = item.asGridItem();
    d.required = x.isRequired(); d.rows = x.getRows(); d.columns = x.getColumns();
  } else if (type === 'CHECKBOX_GRID') {
    const x = item.asCheckboxGridItem();
    d.required = x.isRequired(); d.rows = x.getRows(); d.columns = x.getColumns();
  } else if (type === 'PARAGRAPH_TEXT') {
    d.required = item.asParagraphTextItem().isRequired();
  } else if (type === 'PAGE_BREAK') {
    const x = item.asPageBreakItem();
    d.nav = navText(x.getPageNavigationType(), x.getGoToPage());
  } else {
    d.unknownType = true;
  }
  return d;
}

// 보기 이름 + 분기. 그냥 다음으로 넘어가는 보기는 이름만 남긴다
function describeChoice(c) {
  const nav = navText(c.getPageNavigationType(), c.getGotoPage());
  return nav ? c.getValue() + ' → ' + nav : c.getValue();
}

function navText(type, page) {
  if (page) return '페이지: ' + page.getTitle();
  const t = enumName(FormApp.PageNavigationType, NAV_NAMES, type);
  return (t === '' || t === 'CONTINUE') ? '' : t;
}

function describeForm(form) {
  return form.getItems().map(describeItem);
}

// 응답자 화면에 영향을 주는 폼 설정. 읽기가 안 되는 설정은 오류 문구를 값으로 남겨 두 폼을 같은 기준으로 비교한다
function describeSettings(form) {
  const read = function (f) { try { return f(); } catch (e) { return '읽기 실패: ' + e.message; } };
  return {
    description: read(function () { return form.getDescription(); }),
    confirmationMessage: read(function () { return form.getConfirmationMessage(); }),
    progressBar: read(function () { return form.hasProgressBar(); }),
    collectsEmail: read(function () { return form.collectsEmail(); }),
    editAfterSubmit: read(function () { return form.canEditResponse(); }),
    limitOneResponse: read(function () { return form.hasLimitOneResponsePerUser(); }),
    respondAgainLink: read(function () { return form.hasRespondAgainLink(); }),
    publishingSummary: read(function () { return form.isPublishingSummary(); }),
    shuffleQuestions: read(function () { return form.getShuffleQuestions(); }),
    quiz: read(function () { return form.isQuiz(); }),
  };
}

function diffItems(a, b) {
  const out = [];
  if (a.length !== b.length) out.push('문항·페이지 수 ' + a.length + ' → ' + b.length);
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const keys = Object.keys(a[i]).concat(Object.keys(b[i])).filter(function (k, j, all) { return all.indexOf(k) === j; });
    keys.forEach(function (k) {
      const va = JSON.stringify(a[i][k]);
      const vb = JSON.stringify(b[i][k]);
      if (va !== vb) out.push((i + 1) + '번째 "' + (a[i].title || b[i].title) + '" ' + k + ': ' + va + ' → ' + vb);
    });
  }
  return out;
}

function diffSettings(a, b, keys) {
  return keys
    .filter(function (k) { return JSON.stringify(a[k]) !== JSON.stringify(b[k]); })
    .map(function (k) { return '설정 ' + k + ': ' + JSON.stringify(a[k]) + ' → ' + JSON.stringify(b[k]); });
}

// 응답 시트가 연결돼 있지 않으면 getDestinationId 가 오류를 내서 null 로 바꾼다
function destinationOf(form) {
  try { return form.getDestinationId(); } catch (e) { return null; }
}

// 로그용. "없음"이 진짜 연결이 없어서인지 다른 오류 때문인지 메시지로 남긴다
function destinationNote(form) {
  try { return '연결됨 (' + form.getDestinationId() + ')'; } catch (e) { return '없음 (' + e.message + ')'; }
}

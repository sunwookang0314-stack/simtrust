// SimTrust 폼 B v2(기능별 사용 경험 설문) 자동 생성 스크립트. 문항 원본은 SimTrust-폼B-v2-초안.md
// 사용법: script.google.com → 새 프로젝트 → 기본 코드(function myFunction)를 지우고 이 코드 전체 붙여넣기
//        → 함수 선택에서 createSurveyV2 → 실행 (배포 버튼은 누르지 않는다)
// 실행이 끝나면 아래 "실행 로그"에 편집 링크와 응답 링크가 찍힌다. 폼은 내 구글 드라이브에도 생긴다.
// 다시 실행하면 폼이 새로 하나 더 생긴다. 예전 폼은 구글 드라이브에서 지운다.
// v1 폼과 드라이브 파일 이름이 같으니, 만든 뒤 드라이브에서 이름 끝에 v2를 붙여 두면 헷갈리지 않는다.

// 응답자에게 보이는 문의처
const CONTACT = 'sunwookang0314@gmail.com';
// 추정치(필수 서술 3개 × 2분 + 객관식·그리드 20여 개). 파일럿에서 잰 시간으로 고칠 것
const DURATION = '8~10분';

// 기억을 끌어내는 도입 질문 보기
const PURPOSES = [
  '대외활동·서포터즈',
  '공모전',
  '인턴·채용 공고',
  '동아리·학회',
  '합격 후기·자소서',
  '커뮤니티 글',
  '기타',
];

// 기능 행. 10/31에 정하고 11/1에 넷째 행 이름을 바꿨다(두 대조 서비스 웹·앱 확인, 초안 217행)
// 서비스마다 메뉴 이름이 달라서 일반 이름에 괄호로 예시를 붙였다(추천 행 괄호는 서비스마다 다른 추천 방식을 묶은 것). AI에게도 이 이름 그대로 준다
const FEATURES = [
  '공고 검색·필터',
  '공고 저장 (스크랩, 찜, 북마크)',
  '마감 알림',
  '추천 공고 목록 (인기 공고, 맞춤 추천)',
];

const SERVICES = ['링커리어', '에브리커리어(캠퍼스픽)', '위비티', '캐치', '씽굿', '올콘', '사람인', '잡코리아'];

// "없음" 아니면 15자 이상만 받는다. "편해서" 한 마디로 끝나는 답을 막으려는 장치
const MIN_TEXT_PATTERN = '^\\s*(없음|없어요|없습니다)\\.?\\s*$|^[\\s\\S]{15,}$';
const MIN_TEXT_ERROR = '한두 마디보다 조금만 더 적어주세요. 없으면 "없음"이라고 적어주세요.';

function createSurveyV2() {
  // ── 섹션 1. 안내·동의 (첫 페이지) ──
  const form = FormApp.create('대외활동·공모전·취업 공고 서비스 사용 경험 설문');
  form.setDescription(
    '안녕하세요. 한성대학교 오픈소스 프로젝트 팀 SimTrust입니다.\n\n' +
    '대외활동·공모전·취업 공고 서비스에서 어떤 기능을 왜 쓰고 왜 안 쓰는지, 쓰면서 불편했던 점은 뭐였는지 모으고 있습니다. ' +
    '응답은 연구에만 쓰고, 이름이나 연락처는 받지 않습니다. ' +
    '성별이나 출생연도 같은 기본 정보는 응답자 구성을 파악하고, 그 구성에 맞춰 비교용 AI 가상 응답자를 고르는 데 씁니다. ' +
    '응답 내용은 외부 AI 서비스에 보내지 않습니다. ' +
    '원문은 공개하지 않고 익명으로 정리한 결과만 공개합니다.\n\n' +
    '중간에 그만두셔도 괜찮습니다.\n\n' +
    `소요 시간 ${DURATION} / 문의 ${CONTACT}`
  );
  form.setProgressBar(true);
  // 설명에 "연락처는 받지 않습니다"라고 했으니 기본값에 기대지 않고 명시한다
  form.setCollectEmail(false);
  // 제출 버튼을 누른 뒤에 뜨는 문구
  form.setConfirmationMessage('응답해주셔서 감사합니다.');

  // 동의 안 하면 바로 제출(종료)
  const consent = form.addMultipleChoiceItem()
    .setTitle('설문 참여에 동의하시나요?')
    .setRequired(true);
  consent.setChoices([
    consent.createChoice('동의합니다', FormApp.PageNavigationType.CONTINUE),
    consent.createChoice('동의하지 않습니다', FormApp.PageNavigationType.SUBMIT),
  ]);

  // ── 섹션 2. 기본 정보 ──
  // AI 가상 사용자(페르소나)를 응답자 성별·재학/취준 비율대로 뽑는다(TRD FR-02)
  // 이 문항들은 비공개 파일에만 두고 공개는 비율 파일로만 한다
  form.addPageBreakItem().setTitle('기본 정보');

  // 재학/취준 구분에 쓴다. 학년만 받으면 "졸업"이 취업 준비인지 직장인인지 모른다
  // 1년 이내/넘음은 TRD 대상이 "졸업 1년 이내 취준생"이라 나눴다. 기타는 직접 입력(대학원생 등)
  form.addMultipleChoiceItem()
    .setTitle('학년 또는 현재 상태')
    .setRequired(true)
    .setChoiceValues([
      '1학년', '2학년', '3학년', '4학년 이상', '휴학 중', '졸업유예',
      '졸업 후 취업 준비 중 (졸업 1년 이내)', '졸업 후 취업 준비 중 (졸업 1년 넘음)',
      '졸업 후 직장 다니는 중',
    ])
    .showOtherOption(true);

  // 취준생 페르소나 필터가 "4년제 졸업"이라 전문대 응답자가 얼마나 섞였는지 본다
  form.addMultipleChoiceItem()
    .setTitle('학교 구분 (졸업했다면 졸업한 학교)')
    .setRequired(true)
    .setChoiceValues(['4년제 대학', '전문대학', '기타']);

  // "응답하지 않음"은 비율 계산에서 뺀다
  form.addMultipleChoiceItem()
    .setTitle('성별')
    .setRequired(true)
    .setChoiceValues(['남성', '여성', '응답하지 않음']);

  // 학년만으로는 나이를 못 맞춘다(군 복무, 휴학, 재수). 페르소나 나이 범위를 맞추는 데 쓴다
  // 보기가 많아서 드롭다운으로 둔다
  const birthYears = [];
  for (let y = 2008; y >= 1990; y--) birthYears.push(y + '년');
  birthYears.push('1989년 이전', '응답하지 않음');
  form.addListItem()
    .setTitle('출생연도')
    .setRequired(true)
    .setChoiceValues(birthYears);

  // 응답자 구성 설명용. Nemotron에 대응 필드가 없어서 페르소나에는 안 쓴다
  form.addMultipleChoiceItem()
    .setTitle('전공 계열')
    .setRequired(true)
    .setChoiceValues(['인문', '사회', '경영·경제', '공학', '자연', '예체능', '기타']);

  // 분기 문항. 보기마다 이동할 섹션을 걸어야 해서, 섹션들을 다 만든 뒤에 보기를 채운다
  const used = form.addMultipleChoiceItem()
    .setTitle('최근 6개월 안에 대외활동·공모전·취업 공고 서비스를 써보신 적이 있나요?')
    .setRequired(true);

  // ── 섹션 3. 서비스 고르기 ──
  const servicePage = form.addPageBreakItem().setTitle('서비스 고르기');

  // 서비스를 여러 개 섞은 건 뭘 조사하는지 티가 덜 나게 하려는 것
  form.addCheckboxItem()
    .setTitle('최근 6개월 안에 써보신 서비스를 모두 골라주세요.')
    .setRequired(true)
    .setChoiceValues(SERVICES.concat(['기타']));

  // AI와 대조할 서비스를 고르는 기준이라 필수. 목록에 없는 서비스는 "기타"에 직접 적는다
  form.addMultipleChoiceItem()
    .setTitle('이 중 가장 자주 쓰시는 서비스 한 곳을 골라주세요.')
    .setHelpText('여기서부터는 이 서비스에 대해서만 여쭙니다.')
    .setRequired(true)
    .setChoiceValues(SERVICES)
    .showOtherOption(true);

  // 앱/웹으로 나눠서 앱 캡처 AI·웹 캡처 AI와 각각 비교한다. "둘 다"는 뺐다(초안 222행)
  form.addMultipleChoiceItem()
    .setTitle('주로 어디서 쓰시나요?')
    .setRequired(true)
    .setChoiceValues(['앱', '웹사이트']);

  // ── 섹션 4. 기능별 사용 경험 ──
  form.addPageBreakItem()
    .setTitle('기능별 사용 경험')
    .setHelpText('앞에서 고르신 서비스를 최근에 썼던 때를 떠올리며 답해주세요.');

  // 도입 질문 1: 쓴 목적을 떠올리게 해서 기억을 깨운다
  form.addCheckboxItem()
    .setTitle('주로 무엇을 찾으려고 쓰셨나요?')
    .setRequired(true)
    .setChoiceValues(PURPOSES);

  // 도입 질문 2: 최근 장면 하나를 꺼내게 한다. 분석할 때는 심각도 대용으로도 쓴다
  form.addMultipleChoiceItem()
    .setTitle('가장 최근에 쓰셨을 때, 찾던 걸 찾으셨나요?')
    .setRequired(true)
    .setChoiceValues([
      '바로 찾았다',
      '좀 헤매다가 찾았다',
      '못 찾고 나왔다',
      '딱히 찾던 건 없었다 (그냥 둘러봤다)',
      '기억나지 않는다',
    ]);

  // 기능별 사용 상태. 필수로 걸면 행마다 답해야 넘어간다
  // "있는지 모르겠다"는 이유를 묻지 않고, 비율 자체를 기능이 눈에 안 띈다는 불편 신호로 센다
  form.addGridItem()
    .setTitle('아래 기능을 지금 어떻게 쓰고 계신가요?')
    .setRequired(true)
    .setRows(FEATURES)
    .setColumns(['자주 쓴다', '가끔 쓴다', '써봤는데 지금은 안 쓴다', '안 써봤다', '이 서비스에 있는지 모르겠다']);

  // 쓸 이유 정답지. "가장 최근에 언제, 뭘 하려고"를 같이 물어 의견 대신 실제로 한 일을 받는다
  // 서술 문항 예시는 공고 서비스로 들되 FEATURES 4개는 피한다
  // 같은 기능을 예시로 들면 사람과 AI가 예시 이유를 따라 써서 일치율이 부푼다
  addMinTextParagraph(form,
    '자주 쓰거나 가끔 쓰는 기능은 왜 계속 쓰시나요?',
    [
      '위 표에서 자주 쓰거나 가끔 쓴다고 고른 기능마다 줄을 바꿔서 적어주세요.',
      '한 줄에 아래 세 가지가 들어가면 됩니다.',
      '- 기능 이름',
      '- 가장 최근에 뭘 하려고 그 기능을 썼는지',
      '- 그 기능 덕분에 뭐가 편해졌는지',
      '',
      '"편해서"처럼 한 마디로 끝내지 말고 아래처럼 적어주세요.',
      '',
      '예시 (위 표에 없는 기능으로 들었습니다)',
      '합격 후기: 지난주 서포터즈 면접 전에 작년 합격자 후기를 보려고 썼습니다. 실제로 나온 면접 질문이 정리돼 있어서 다른 데서 따로 안 찾아보고 그것만 보고 준비했습니다.',
      '공고 공유: 어제 같이 공모전 나갈 친구한테 공고를 보내려고 썼습니다. 카톡 공유 버튼을 한 번 누르니까 바로 보내져서 링크를 따로 복사할 필요가 없었습니다.',
      '',
      '계속 쓰는 기능이 없다면 "없음"이라고 적어주세요.',
    ].join('\n')
  );

  // 써봤다가 그만둔 사람의 안 쓸 이유. 구글폼은 그리드 행 단위로 분기를 못 해서 모든 행이 보인다
  // 위 문항과 안 맞게 체크한 칸은 분석할 때 그 칸만 뺀다
  form.addCheckboxGridItem()
    .setTitle('써봤는데 지금은 안 쓰는 기능이 있다면, 안 쓰게 된 이유에 가까운 것을 골라주세요.')
    .setHelpText('위에서 "써봤는데 지금은 안 쓴다"를 고른 기능 줄만 골라주세요. 여러 개 골라도 됩니다.')
    .setRows(FEATURES)
    .setColumns(['써보니 불편해서', '나한테 필요 없어서', '다른 앱이나 방법으로 해결해서', '기타']);

  // 한 번도 안 써본 사람의 안 쓸 이유. AI와 같은 첫인상 조건이라 AI 답과 바로 비교한다
  // 보기를 "~보여서", "~것 같아서" 첫인상 말투로 쓴 건 AI에게 한 글자도 안 바꾸고 주려는 것
  form.addCheckboxGridItem()
    .setTitle('한 번도 안 써본 기능이 있다면, 안 써본 이유에 가까운 것을 골라주세요.')
    .setHelpText('위에서 "안 써봤다"를 고른 기능 줄만 골라주세요. 여러 개 골라도 됩니다.')
    .setRows(FEATURES)
    .setColumns(['쓰기 번거로워 보여서', '나한테 필요 없을 것 같아서', '다른 앱이나 방법으로 해결해서', '딱히 써볼 생각을 안 해봐서', '기타']);

  // 안 쓸 이유 정답지. 그만둔 기능은 "마지막에 뭐가 걸렸나", 안 써본 기능은 "대신 지금 어떻게 하나"
  addMinTextParagraph(form,
    '안 쓰게 됐거나 안 써본 기능이 있다면, 그 이유를 조금 더 자세히 적어주세요.',
    [
      '위 표에서 안 쓰게 됐거나 안 써봤다고 고른 기능마다 줄을 바꿔서 적어주세요.',
      '- 써봤다가 안 쓰게 된 기능: 마지막으로 썼을 때 뭐가 걸렸는지',
      '- 한 번도 안 써본 기능: 그 기능 대신 지금은 어떻게 하고 계신지',
      '',
      '예시 (위 표에 없는 기능으로 들었습니다)',
      '커뮤니티: 한 달 전쯤 공모전 팀원을 구하려고 글을 올렸는데 사흘 동안 댓글이 하나도 안 달렸습니다. 그 뒤로는 과 단톡방에서 구합니다.',
      '지원 현황 관리: 써본 적은 없습니다. 지원한 공고는 메모장에 날짜랑 결과를 직접 적어서 관리합니다.',
      '',
      '해당하는 기능이 없다면 "없음"이라고 적어주세요.',
    ].join('\n')
  );

  // 불편 정답지. 창업자 화면에서 "고치는 법"을 붙이는 대상
  form.addParagraphTextItem()
    .setTitle('계속 쓰는 기능이든 안 쓰는 기능이든, 쓰면서 불편했던 점이 있나요?')
    .setHelpText([
      '헤맸던 때가 있다면 그때 얘기를 적어주세요.',
      '어느 화면에서, 뭘 하려다가, 뭐가 불편했는지가 들어가면 됩니다.',
      '',
      '예시',
      '공고 상세 화면에서 지원 방법을 찾으려고 했는데, 공고 이미지 맨 아래에만 작게 적혀 있어서 확대해서 읽느라 한참 걸렸습니다.',
      '',
      '없으면 "없음"이라고 적어주세요.',
    ].join('\n'))
    .setRequired(true);

  // 정답지에 안 섞고, AI가 낸 고치는 법과 비교할 때만 쓴다
  form.addParagraphTextItem()
    .setTitle('어떻게 바뀌었으면 하나요?')
    .setHelpText([
      '위에 적은 불편한 점이 어떻게 바뀌면 좋을지 적어주세요.',
      '',
      '예시',
      '지원 방법은 이미지 말고 공고 맨 위에 글자로 따로 적어주면 좋겠습니다.',
    ].join('\n'));

  // ── 섹션 5. 마무리 (맨 끝에 둬야 자동으로 제출된다) ──
  // 여기서 "감사합니다"를 띄우면 끝난 줄 알고 제출 전에 탭을 닫는 사람이 생긴다
  const endPage = form.addPageBreakItem()
    .setTitle('마무리')
    .setHelpText('아래 [제출] 버튼을 눌러야 응답이 저장됩니다.');

  // 분기 연결: 써봤다 → 서비스 고르기, 안 써봤다 → 마무리
  used.setChoices([
    used.createChoice('있다', servicePage),
    used.createChoice('없다', endPage),
  ]);

  Logger.log('편집 링크: ' + form.getEditUrl());
  Logger.log('응답 링크(이걸 뿌리면 된다): ' + form.getPublishedUrl());
}

// "없음" 아니면 15자 이상만 받는 필수 서술 문항. 계속 쓰는 이유·안 쓰는 이유 두 문항에 쓴다
function addMinTextParagraph(form, title, helpText) {
  const validation = FormApp.createParagraphTextValidation()
    .setHelpText(MIN_TEXT_ERROR)
    .requireTextMatchesPattern(MIN_TEXT_PATTERN)
    .build();
  return form.addParagraphTextItem()
    .setTitle(title)
    .setHelpText(helpText)
    .setRequired(true)
    .setValidation(validation);
}

// 시연이 따라가는 칸: 기능 하나(?feature=, 기본 마감 알림) · 쓸 이유 · GPT(model_a). 11/21 정함, 기능은 1장 토글로 바꾼다.
// 쓸 이유는 서술형 답(Q-AI-WHY-USE)이라 "답에서 이유를 칠해 떼어 낸다"를 그대로 보여 줄 수 있다
// (안 쓸 이유는 보기 체크라 떼어 낼 문장이 없다).
// 답은 지어낸 예시다. 이름표(코드)는 코드북 v1.0 작업본과 판정 계산기 견본(reasons_model_a.csv)에 있는 것만 쓴다.
// 기능마다 이야기 모양이 같다 (칩 만들기 무대 자리를 같이 쓰려고):
//   답 1 = 같은 뜻 두 조각(합치기), 답 2 = 표현만 다른 한 조각(이름표로 바뀜), 답 3 = 새 이유 + 답 1과 같은 이유
// quote = 오프닝에 인용하는 말, quoteCode = 그 말의 이름표(답 120개 중 몇 번인지 견본에서 읽는다), voices = 오프닝 배경 말풍선(이유 조각에 더해)
import { FEATURES } from "./data.js";

export const STORY_MODEL = "model_a";
export const STORY_KIND = "use";

const STORIES = {
  F1: {
    quote: "원하는 조건만 골라 보려고 쓸 거예요.", quoteCode: "F1-U01",
    voices: ["인턴만 따로 보려고", "학교 근처 공고만", "원하는 기간만 보려고", "조건이 많아서", "최신순으로 보려고", "공고가 너무 많아서"],
    answers: [
      ["관심 있는 ", { t: "분야만 골라 보려고", code: "F1-U01" }, " 쓸 것 같아요. ", { t: "필요 없는 공고를 안 봐도 돼서", code: "F1-U01" }, " 편할 것 같아요."],
      [{ t: "마감임박순으로 정렬해서", code: "F1-U02" }, " 급한 것부터 보려고요."],
      [{ t: "넘겨 보는 시간이 줄어서", code: "U01" }, " 좋을 것 같아요. ", { t: "지역별로 걸러 볼 수 있으니까요", code: "F1-U01" }, "."],
    ],
  },
  F2: {
    quote: "나중에 비교하려고 모아 둘 거예요.", quoteCode: "F2-U01",
    voices: ["나중에 다시 보려고", "마감 전에 정리하려고", "북마크처럼 쓰려고", "괜찮은 것만 모아서", "지원 목록 만들려고", "잊어버릴까 봐"],
    answers: [
      ["괜찮은 공고를 ", { t: "모아 두고 나중에 비교하려고", code: "F2-U01" }, " 쓸 것 같아요. ", { t: "바로 정하지 않아도 돼서", code: "F2-U01" }, " 편할 것 같아요."],
      [{ t: "지원할 공고만 따로 챙겨 두려고", code: "F2-U02" }, " 쓸 것 같아요."],
      [{ t: "흩어진 공고를 한 번에 봐서", code: "U03" }, " 좋을 것 같아요. ", { t: "주말에 몰아서 비교하려고요", code: "F2-U01" }, "."],
    ],
  },
  F3: {
    quote: "마감을 놓치지 않으려고 쓸 거예요.", quoteCode: "U02",
    voices: ["지원 일정 관리하려고", "알림 오면 바로 보려고", "깜빡하는 일이 많아서", "마감 직전에 알려 줘서", "따로 메모 안 해도 돼서", "놓친 적이 있어서"],
    answers: [
      ["지원할 공고 ", { t: "마감을 놓치지 않으려고", code: "U02" }, " 쓸 것 같아요. ", { t: "따로 달력을 안 봐도 돼서", code: "U02" }, " 편할 것 같아요."],
      ["스크랩한 공고들을 ", { t: "한곳에서 챙기려고", code: "U03" }, " 쓸 것 같아요."],
      [{ t: "마감일을 일일이 확인하는 수고가 줄어서", code: "U01" }, " 좋을 것 같아요. ", { t: "놓칠 일이 없으니까요", code: "U02" }, "."],
    ],
  },
  F4: {
    quote: "몰랐던 공고를 찾으려고 볼 거예요.", quoteCode: "F4-U01",
    voices: ["뭘 찾을지 모를 때", "다른 사람들은 뭘 보나", "새 공고가 올라와서", "둘러보려고", "인기 공고가 궁금해서", "추천이 잘 맞으면"],
    answers: [
      [{ t: "생각 못 한 공고를 찾으려고", code: "F4-U01" }, " 쓸 것 같아요. ", { t: "몰랐던 대외활동을 알게 돼서", code: "F4-U01" }, " 좋을 것 같아요."],
      [{ t: "요즘 다들 많이 보는 공고가 궁금해서", code: "F4-U02" }, " 볼 것 같아요."],
      [{ t: "따로 검색 안 해도 돼서", code: "U01" }, " 편할 것 같아요. ", { t: "새로운 공고를 발견할 수 있으니까요", code: "F4-U01" }, "."],
    ],
  },
};

export const answerText = a => a.segs.map(s => (typeof s === "string" ? s : s.t)).join("");

/** 기능 하나의 이야기: 질문, 답 셋(segs), 이유 조각 전부(pieces: { id, ans, idx, t, code }) */
export function getStory(feature) {
  const f = STORIES[feature] ? feature : "F3";
  const name = FEATURES.find(x => x.id === f).name;
  const answers = STORIES[f].answers.map((segs, i) => ({ id: `a${i + 1}`, segs }));
  const pieces = answers.flatMap(a =>
    a.segs.filter(s => typeof s !== "string").map((s, i) => ({ id: `${a.id}-${i}`, ans: a.id, idx: i, ...s })));
  return {
    feature: f, kind: STORY_KIND, model: STORY_MODEL, name,
    question: `${name}, 쓸 것 같나요?\n쓴다면 뭘 하려고, 뭐가 편할 것 같나요?`,
    quote: STORIES[f].quote, quoteCode: STORIES[f].quoteCode, answers, pieces,
    voices: [...pieces.map(p => p.t), ...STORIES[f].voices],
  };
}

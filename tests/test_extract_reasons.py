"""scripts/extract_reasons.py 오프라인 테스트. API와 TinyTroupe 없이 돈다.

리포 루트에서:
    python -m unittest tests.test_extract_reasons -v
"""

import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import extract_reasons as er  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="simtrust_extract_test_"))
shutil.copytree(REPO / "experiments/runner_dev/protocol", TMP / "protocol")
FEATURES = [{"feature_id": f"F{i}", "name": n} for i, n in
            enumerate(["공고 검색·필터", "공고 저장 (스크랩, 찜, 북마크)", "마감 알림", "추천 공고 목록 (인기 공고, 맞춤 추천)"], 1)]


def answer(qid, talk, asked=True, think="", feature_id="", skipped=None):
    return {"question_id": qid, "feature_id": feature_id, "asked": asked, "skipped": skipped, "captures": [],
            "images_in_request": 0, "actions": [], "think": think, "talk": talk}


def episode(run_id="r1", answers=None):
    return {"run_id": run_id, "batch_id": "b1", "service": "fake", "platform": "app", "condition": 2,
            "persona_id": "S01", "repeat": 1, "protocol_version": None, "snapshot_version": "fake-0.3",
            "input_mode": "text", "question_order": "b", "status": "성공", "features": FEATURES,
            "answers": answers}


GOOD = episode(answers=[
    answer("Q-AI-USE", "공고 검색·필터: 쓸 것 같다\n공고 저장 (스크랩, 찜, 북마크): 안 쓸 것 같다\n"
                       "마감 알림: 쓸 것 같다\n추천 공고 목록 (인기 공고, 맞춤 추천): 안 쓸 것 같다"),
    answer("Q-AI-WHY-USE", "공고 검색·필터: 인턴 공고를 찾으려고 쓸 것 같다. 조건을 한 번에 걸 수 있어 편하다\n"
                           "마감 알림: 마감일을 놓치지 않으려고 쓸 것 같다\n그 밖에는 잘 모르겠다"),
    answer("Q-AI-NOUSE", "공고 저장: 나한테 필요 없을 것 같아서, 다른 앱이나 방법으로 해결해서\n"
                         "추천 공고 목록: 광고 같아서 손이 안 간다"),
    answer("Q-4-7", "공고 저장: 지금은 카톡 나에게 보내기로 모아 둡니다\n추천 공고 목록: 안 써봤고 검색으로 찾습니다"),
], run_id="good")


def write_raw(name, lines):
    path = TMP / f"{name}.jsonl"
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
    return path.name


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = er.main(list(argv), root=TMP)
    return code, out.getvalue() + err.getvalue()


def outputs(name):
    d = TMP / f"out_{name}"
    records = [json.loads(x) for x in next(d.glob("extracted_*.jsonl")).read_text(encoding="utf-8").splitlines()]
    with next(d.glob("review_*.csv")).open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    summary = json.loads(next(d.glob("summary_*.json")).read_text(encoding="utf-8"))
    return records, rows, summary


class TestExtractReasons(unittest.TestCase):
    def test_features_reasons_and_options(self):
        code, log = run("--raw", write_raw("good", [GOOD]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_good")
        self.assertEqual(code, 0, log)
        records, rows, summary = outputs("good")
        by = {r["feature_id"]: r for r in records}
        self.assertEqual({k: v["use_choice"] for k, v in by.items()},
                         {"F1": "use", "F2": "nouse", "F3": "use", "F4": "nouse"})
        # 한 줄에 두 문장이면 문장으로 나누고, 기능 이름이 없는 뒤 문장은 같은 줄 기능을 이어받는다
        self.assertEqual(by["F1"]["use_reasons"], ["인턴 공고를 찾으려고 쓸 것 같다.", "조건을 한 번에 걸 수 있어 편하다"])
        self.assertEqual(by["F1"]["reason_counts"]["why_use"], 2)
        self.assertEqual(by["F3"]["use_reasons"], ["마감일을 놓치지 않으려고 쓸 것 같다"])
        self.assertEqual(by["F2"]["nouse_options"], ["나한테 필요 없을 것 같아서", "다른 앱이나 방법으로 해결해서"])
        self.assertEqual(by["F4"]["nouse_options"], [])
        self.assertEqual(by["F4"]["needs_review"], ["4-6 보기를 못 찾은 줄"])  # 보기 글자가 없는 답
        self.assertEqual(by["F2"]["q47_details"], ["지금은 카톡 나에게 보내기로 모아 둡니다"])
        # 기능 이름이 없는 줄은 버리지 않고 검토 목록으로 간다
        reviews = [r for r in rows if r["kind"].startswith("review:")]
        self.assertEqual([(r["kind"], r["text"]) for r in reviews], [("review:Q-AI-WHY-USE", "그 밖에는 잘 모르겠다")])
        self.assertEqual(summary["use_choice"], {"use": 2, "nouse": 2})
        self.assertEqual(summary["nouse_options"], {"나한테 필요 없을 것 같아서": 1, "다른 앱이나 방법으로 해결해서": 1})
        self.assertNotIn("인턴 공고", log)  # 화면에는 숫자만

    def test_sentences_are_split(self):
        line = episode(run_id="split", answers=[
            answer("Q-AI-USE", "공고 검색·필터: 쓸 것 같다"),
            answer("Q-AI-WHY-USE", "공고 검색·필터: 인턴 공고를 찾으려고 쓸 것 같다. 공고 검색·필터 덕분에 조건을 한 번에 건다"),
            answer("Q-AI-NOUSE", "", asked=False, skipped="안 쓸 것 같은 기능 없음"),
            answer("Q-4-7", "없음"),
        ])
        code, log = run("--raw", write_raw("split", [line]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_split")
        self.assertEqual(code, 0, log)
        records, _, summary = outputs("split")
        f1 = records[0]
        self.assertEqual(f1["reason_counts"]["why_use"], 2)
        self.assertEqual(summary["reasons_per_answer_mean"]["why_use"], 2.0)

    def test_missing_feature_and_source(self):
        line = episode(run_id="miss", answers=[
            answer("Q-AI-USE", "", think="공고 검색·필터: 쓸 것 같다"),
            answer("Q-4-7", "없음"),
            answer("", "", asked=False, feature_id="F3", skipped="없음"),
        ])
        code, log = run("--raw", write_raw("miss", [line]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_miss", "--source", "think_talk")
        self.assertEqual(code, 0, log)
        records, rows, summary = outputs("miss")
        by = {r["feature_id"]: r for r in records}
        self.assertEqual((by["F3"]["asked"], by["F3"]["skipped"]), (False, "없음"))
        self.assertEqual(by["F1"]["use_choice"], "use")  # TALK이 비어도 think_talk이면 THINK에서 읽는다
        self.assertEqual(summary["skipped_features"], 1)

        # talk만 봐도 쓸/안 쓸 판별은 실행기처럼 TALK이 비면 THINK을 쓴다. 안 그러면 실행기와 판별이 갈린다
        code, log = run("--raw", write_raw("miss", [line]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_miss_talk")
        records, _, _ = outputs("miss_talk")
        self.assertEqual({r["feature_id"]: r.get("use_choice") for r in records}["F1"], "use")

    def test_intro_lines_and_q47_status(self):
        # 11/5 gemini-3.6-flash 실제 답 모양: 머리말 줄 + "- 기능: ..." 목록, 4-7 앞에 "한 번도 안 써봤습니다."
        line = episode(run_id="real", answers=[
            answer("Q-AI-USE", "요청해주신 4가지 기능에 대한 의견입니다.\n\n- 공고 검색·필터: 쓸 것 같다\n"
                               "- 공고 저장 (스크랩, 찜, 북마크): 안 쓸 것 같다\n- 마감 알림: 쓸 것 같다\n"
                               "- 추천 공고 목록 (인기 공고, 맞춤 추천): 안 쓸 것 같다"),
            answer("Q-AI-WHY-USE", "'쓸 것 같다'고 선택한 기능별 상세 답변입니다.\n\n"
                                   "- 공고 검색·필터: 조건으로 좁히려고 쓰며, 시간이 줄어 편할 것 같습니다.\n"
                                   "- 마감 알림: 마감일을 놓치지 않으려고 쓸 것 같습니다.\n"
                                   "더 궁금한 점은 없습니다."),
            answer("Q-AI-NOUSE", "'안 쓸 것 같다'고 선택한 기능의 이유입니다.\n\n"
                                 "- 공고 저장 (스크랩, 찜, 북마크): 나한테 필요 없을 것 같아서\n"
                                 "- 추천 공고 목록 (인기 공고, 맞춤 추천): 나한테 필요 없을 것 같아서"),
            answer("Q-4-7", "공고 저장 (스크랩, 찜, 북마크): 한 번도 안 써봤습니다. 엑셀에 직접 적어 둡니다.\n"
                            "추천 공고 목록 (인기 공고, 맞춤 추천): 써본 적은 없습니다.\n"
                            "공고 검색·필터: 안 써봤고 검색창에 직접 칩니다"),
        ])
        code, log = run("--raw", write_raw("real", [line]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_real")
        self.assertEqual(code, 0, log)
        records, rows, summary = outputs("real")
        by = {r["feature_id"]: r for r in records}
        self.assertEqual({k: v["use_choice"] for k, v in by.items()},
                         {"F1": "use", "F2": "nouse", "F3": "use", "F4": "nouse"})
        # 머리말 줄은 검토 목록에 안 가고 intro로만 남는다. 기능 줄 뒤에 온 말은 지금처럼 검토로 간다
        reviews = [(r["kind"], r["text"]) for r in rows if r["kind"].startswith("review:")]
        self.assertEqual(reviews, [("review:Q-AI-WHY-USE", "더 궁금한 점은 없습니다.")])
        intros = [r["kind"] for r in rows if r["kind"].startswith("intro:")]
        self.assertEqual(intros, ["intro:Q-AI-WHY-USE", "intro:Q-AI-NOUSE"])
        self.assertEqual(summary["intro_lines"], 2)
        # 써 봤는지만 말한 문장은 이유에서 빠지고 q47_status로 간다. 이유가 같이 있는 문장은 그대로 둔다
        self.assertEqual(by["F2"]["q47_details"], ["엑셀에 직접 적어 둡니다."])
        self.assertEqual(by["F2"]["q47_status"], ["한 번도 안 써봤습니다."])
        self.assertEqual(by["F2"]["reason_counts"]["q47"], 1)
        self.assertEqual((by["F4"]["q47_details"], by["F4"]["q47_status"]), ([], ["써본 적은 없습니다."]))
        self.assertEqual(by["F1"]["q47_details"], ["안 써봤고 검색창에 직접 칩니다"])
        self.assertEqual(summary["q47_status_lines"], 2)
        self.assertIn("q47_status", {r["kind"] for r in rows})

    def test_markdown_shapes(self):
        # 모델마다 목록 모양이 다르다: 굵게, 번호, 기능 이름만 있는 머리 줄 + 하위 목록, 괄호 앞 공백 없음
        line = episode(run_id="md", answers=[
            answer("Q-AI-USE", "1. **공고 검색·필터**: 쓸 것 같다\n2. **공고 저장**: 쓸 것 같다\n"
                               "3. **마감 알림**: 쓸 것 같지 않다\n4. **추천 공고 목록**: 안 쓸 것 같다"),
            answer("Q-AI-WHY-USE", "1. **공고 검색·필터**: 조건으로 좁히려고 씁니다.\n"
                                   "2. **공고 저장(스크랩, 찜, 북마크)**: 모아 두려고 쓰고, 마감 알림과 같이 보면 편합니다."),
            answer("Q-AI-NOUSE", "- **마감 알림**\n  - 나한테 필요 없을 것 같아서\n"
                                 "- **추천 공고 목록 (인기 공고, 맞춤 추천)**\n  - 광고 같아서\n  - 다른 앱이나 방법으로 해결해서"),
            answer("Q-4-7", "마감 알림: 캘린더에 직접 적습니다.\n추천 공고 목록: 한 번도 안 써봤습니다."),
        ])
        line["use_parsed_at_runtime"] = {"F1": "use", "F2": "use", "F3": "use", "F4": "nouse"}
        code, log = run("--raw", write_raw("md", [line]), "--options", "protocol/options_4-6.txt", "--out", "out_md")
        self.assertEqual(code, 0, log)
        records, rows, _ = outputs("md")
        by = {r["feature_id"]: r for r in records}
        self.assertEqual(by["F3"]["use_choice"], "nouse")  # "쓸 것 같지 않다"
        self.assertEqual(by["F1"]["use_reasons"], ["조건으로 좁히려고 씁니다."])
        # 뒤에 다른 기능 이름이 나와도 앞 기능 줄이다. 괄호는 이유에 안 남는다
        self.assertEqual(by["F2"]["use_reasons"], ["모아 두려고 쓰고, 마감 알림과 같이 보면 편합니다."])
        # 기능 이름만 있는 머리 줄 아래 하위 목록은 그 기능의 이유다. 머리 줄은 이유가 아니다
        self.assertEqual(by["F3"]["nouse_lines"], ["나한테 필요 없을 것 같아서"])
        self.assertEqual(by["F4"]["nouse_lines"], ["광고 같아서", "다른 앱이나 방법으로 해결해서"])
        reviews = [(r["kind"], r["needs_review"]) for r in rows if r["kind"].startswith("review:")]
        # 실행 중 판별(F3 use)과 다르면 검토로 보낸다. 그때는 꼬리 질문을 잘못 골랐을 수 있다
        self.assertEqual(reviews, [("review:Q-AI-USE", "실행 중 쓸/안 쓸 판별과 다름")])

    def test_sole_target_attach(self):
        # 안 쓸 기능이 하나뿐이면 기능 이름 없는 문단도 그 기능의 이유로 붙인다 (11/5 이미지 실행에서 빠졌던 줄)
        line = episode(run_id="sole", answers=[
            answer("Q-AI-USE", "공고 검색·필터: 쓸 것 같다\n공고 저장: 쓸 것 같다\n마감 알림: 쓸 것 같다\n"
                               "추천 공고 목록: 안 쓸 것 같다"),
            answer("Q-AI-NOUSE", "- 추천 공고 목록: 나한테 필요 없을 것 같아서\n\n"
                                 "저는 자동 추천보다 직접 찾는 편이라 필요하지 않을 것 같습니다."),
            answer("Q-4-7", "없음"),
        ])
        code, log = run("--raw", write_raw("sole", [line]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_sole")
        self.assertEqual(code, 0, log)
        records, rows, summary = outputs("sole")
        f4 = {r["feature_id"]: r for r in records}["F4"]
        self.assertEqual(f4["nouse_lines"], ["나한테 필요 없을 것 같아서",
                                             "저는 자동 추천보다 직접 찾는 편이라 필요하지 않을 것 같습니다."])
        self.assertEqual(summary["attached_lines"], 1)
        self.assertIn("attached:Q-AI-NOUSE", {r["kind"] for r in rows})
        self.assertFalse([r for r in rows if r["kind"].startswith("review:")])

    def test_use_negation(self):
        feats = [("F1", "공고 검색·필터"), ("F4", "추천 공고 목록 (인기 공고, 맞춤 추천)")]
        cases = {"공고 검색·필터: 쓸 것 같다\n추천 공고 목록: 쓸 것 같지 않다": {"F1": "use", "F4": "nouse"},
                 "공고 검색·필터: 별로 쓸 것 같진 않아요\n추천 공고 목록: 안 쓸 것 같다": {"F1": "nouse", "F4": "nouse"},
                 "공고 검색·필터: 사용할 것 같지 않습니다\n추천 공고 목록: 쓰지 않을 것 같다": {"F1": "nouse", "F4": "nouse"},
                 "공고 검색·필터: 사용할 것 같다\n추천 공고 목록: 쓸 것 같습니다": {"F1": "use", "F4": "use"}}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(er.rs.parse_use_answers(text, feats), expected)

    def test_status_pattern(self):
        status = ["한 번도 안 써봤습니다.", "써본 적은 없습니다.", "써 본 적 없음", "아직 한 번도 써본 적이 없어요",
                  "사용해 본 적이 없습니다.", "써보지 않았습니다"]
        reasons = ["안 써봤고 검색으로 찾습니다", "써본 적은 없지만 광고 같아서 손이 안 갑니다.",
                   "한 번 써봤는데 알림이 너무 많았습니다.", "엑셀에 직접 적어 둡니다."]
        for s in status:
            self.assertTrue(er.STATUS.match(s), s)
        for s in reasons:
            self.assertFalse(er.STATUS.match(s), s)

    def test_input_errors(self):
        stage1 = {"run_id": "old", "service": "fake", "steps": []}
        cases = [
            (["--raw", "nothing.jsonl", "--out", "out_x"], 1),
            (["--raw", write_raw("stage1", [stage1]), "--options", "protocol/options_4-6.txt", "--out", "out_x"], 4),
            (["--raw", write_raw("good2", [GOOD]), "--options", "nothing.txt", "--out", "out_x"], 1),
        ]
        (TMP / "broken.jsonl").write_text("{\n", encoding="utf-8")
        cases.append((["--raw", "broken.jsonl", "--options", "protocol/options_4-6.txt", "--out", "out_x"], 4))
        for argv, expected in cases:
            with self.subTest(argv=argv):
                code, log = run(*argv)
                self.assertEqual(code, expected, log)
        self.assertFalse((TMP / "out_x").exists())


if __name__ == "__main__":
    unittest.main()

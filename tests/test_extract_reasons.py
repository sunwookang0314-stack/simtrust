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

        code, log = run("--raw", write_raw("miss", [line]), "--options", "protocol/options_4-6.txt",
                        "--out", "out_miss_talk")
        records, _, _ = outputs("miss_talk")
        self.assertEqual({r["feature_id"]: r.get("use_choice") for r in records}["F1"], "unknown")

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

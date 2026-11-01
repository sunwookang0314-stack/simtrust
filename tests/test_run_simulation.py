"""scripts/run_simulation.py 오프라인 테스트. API 키 없이 돈다.

TinyTroupe의 실제 API 호출 함수(_raw_model_call)만 가짜로 바꾸고, 에이전트, 캐시, 실행기는 그대로 쓴다.
그래서 실제 Gemini, gpt-5-mini 응답으로 도는지는 이 테스트로 확인되지 않는다.

리포 루트에서:
    python -m unittest tests.test_run_simulation -v
"""

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# 임시 폴더에 리포 모양을 만든다: config.ini, 가짜 스냅샷, 임시 페르소나 2명
TMP = Path(tempfile.mkdtemp(prefix="simtrust_runner_test_"))
shutil.copyfile(REPO / "config.gemini.ini", TMP / "config.ini")
shutil.copytree(REPO / "experiments/runner_dev/snapshots", TMP / "snapshots")
(TMP / "personas").mkdir()
PERSONA_SRC = sorted((REPO / "experiments/personas_nemotron_korea/personas/students_in_progress").glob("*.json"))[:2]
for p in PERSONA_SRC:
    shutil.copyfile(p, TMP / "personas" / p.name)

os.environ["OPENAI_BASE_URL"] = GEMINI_URL
os.environ["OPENAI_API_KEY"] = "test-not-a-real-key"

# TinyTroupe는 import 할 때 현재 폴더의 config.ini를 읽는다
os.chdir(TMP)
with contextlib.redirect_stdout(io.StringIO()):
    import tinytroupe  # noqa: F401
import httpx
import openai
from openai.types.chat import ChatCompletion
from tinytroupe.clients.openai_client import OpenAIClient

import run_simulation as rs


class FakeAPI:
    """실제 API 대신 응답한다. mode로 정상, 빈 응답, 인증 오류를 고른다."""

    def __init__(self):
        self.reset()

    def reset(self, mode="ok"):
        self.mode = mode
        self.calls = 0
        self.prompts = []

    def sent_text(self):
        # TinyTroupe는 페르소나와 메시지를 json.dumps 기본값으로 넣어서 한글이 \uXXXX로 나간다
        # (agent/tiny_person.py:319, agent/action_generator.py:125). 비교하려고 되돌린다.
        joined = "\n".join(self.prompts)
        return re.sub(r"\\+u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), joined)

    def __call__(self, client_self, model, params):
        self.calls += 1
        self.prompts.append(json.dumps(params.get("messages"), ensure_ascii=False, default=str))
        request = httpx.Request("POST", "https://example.invalid")
        if self.mode == "auth":
            raise openai.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
        if self.mode == "gemini_bad_key":
            body = [{"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                               "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}]
            raise openai.BadRequestError("API key not valid", response=httpx.Response(400, request=request), body=body)
        if self.mode == "not_found":
            raise openai.NotFoundError("model not found", response=httpx.Response(404, request=request), body=None)
        if self.mode == "empty":
            content, finish = "", "length"
        else:
            # 호출마다 문구가 달라서, 캐시가 안 먹으면 결과가 달라진다
            content = json.dumps({
                "actions": [
                    {"type": "THINK", "content": f"공모전 탭부터 봐야겠다 {self.calls}", "target": ""},
                    {"type": "TALK", "content": f"공모전 탭을 누를게요 {self.calls}", "target": ""},
                    {"type": "DONE", "content": "", "target": ""},
                ],
                "cognitive_state": {"goals": "과제", "context": ["앱"], "attention": "탭", "emotions": "보통"},
            }, ensure_ascii=False)
            finish = "stop"
        return ChatCompletion.model_validate({
            "id": f"fake-{self.calls}", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
        })


FAKE = FakeAPI()
# 실행기가 감싸기 전에 바꿔 둔다. 실행기는 이 함수를 감싼다.
OpenAIClient._raw_model_call = lambda self, model, params: FAKE(self, model, params)

BASE_CFG = json.loads((REPO / "configs/simulation.dev.json").read_text(encoding="utf-8"))
BASE_CFG["snapshot_root"] = "snapshots"
BASE_CFG["personas_dir"] = "personas"


def write_cfg(name, **override):
    cfg = dict(BASE_CFG)
    cfg.update({
        "raw_responses_path": f"out_{name}/raw.jsonl",
        "meta_dir": f"out_{name}/meta",
        "cache_dir": f"out_{name}/cache",
    })
    cfg.update(override)
    path = TMP / f"cfg_{name}.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return path.name


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = rs.main(list(argv), root=TMP)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue() + err.getvalue()


def read_raw(name):
    path = TMP / f"out_{name}" / "raw.jsonl"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def read_summaries(name):
    return sorted((TMP / f"out_{name}" / "meta").glob("*.summary.json"))


def args(cfg, condition=2, repeat=1, limit=1, service="fake"):
    return ["--service", service, "--condition", str(condition), "--repeat", str(repeat),
            "--seed", "7", "--config", cfg, "--limit-personas", str(limit)]


class TestRunSimulation(unittest.TestCase):
    def setUp(self):
        FAKE.reset()
        os.environ["OPENAI_BASE_URL"] = GEMINI_URL
        os.environ["OPENAI_API_KEY"] = "test-not-a-real-key"

    def test_ok_then_cache_rerun_gives_same_result(self):
        cfg = write_cfg("cache")
        code, log = run(*args(cfg, repeat=2))
        self.assertEqual(code, 0, log)
        first = read_raw("cache")
        self.assertEqual(len(first), 2)
        calls_first = FAKE.calls
        self.assertGreater(calls_first, 0)
        # 회차마다 캐시가 따로라서 두 회차 응답이 다르다 (같이 쓰면 같아진다)
        self.assertNotEqual(first[0]["steps"], first[1]["steps"])

        FAKE.reset()
        code, log = run(*args(cfg, repeat=2))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 0, "다시 돌렸는데 API를 불렀다 (캐시 재현 실패)")
        second = read_raw("cache")[2:]
        self.assertEqual([x["steps"] for x in first], [x["steps"] for x in second])

        summary = json.loads(read_summaries("cache")[-1].read_text(encoding="utf-8"))
        self.assertEqual(summary["calls_real"], 0)
        self.assertEqual(summary["calls_cached"], calls_first)

    def test_meta_has_trd_fields_and_no_key(self):
        cfg = write_cfg("meta")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        metas = [p for p in (TMP / "out_meta" / "meta").glob("*.json") if not p.name.endswith(".summary.json")]
        self.assertEqual(len(metas), 1)
        text = metas[0].read_text(encoding="utf-8")
        meta = json.loads(text)
        for key in ["run_id", "timestamp", "provider", "base_url", "model", "tinytroupe_commit", "service",
                    "condition", "persona_id", "repeat", "seed", "input_mode", "cache_file",
                    "max_completion_tokens", "tokens_in", "tokens_out", "elapsed_sec", "status",
                    "protocol_version", "snapshot_version"]:
            self.assertIn(key, meta)
        self.assertEqual(meta["status"], "성공")
        self.assertEqual(meta["seed"], 7)
        self.assertNotIn("test-not-a-real-key", text)
        line = read_raw("meta")[0]
        self.assertEqual([s["task_id"] for s in line["steps"]], ["T1", "T2"])
        self.assertTrue(line["steps"][0]["talk"])

    def test_feature_description_not_sent(self):
        cfg = write_cfg("feature")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        sent = FAKE.sent_text()
        self.assertIn("마감이 가까운 공고", sent)  # S1 화면 설명은 들어간다
        self.assertNotIn("FEATURE-ONLY", sent)  # 기능 설명은 안 들어간다

    def test_condition0_uses_slots(self):
        cfg = write_cfg("c0")
        code, log = run(*args(cfg, condition=0, limit=2))
        self.assertEqual(code, 0, log)
        self.assertEqual([x["persona_id"] for x in read_raw("c0")], ["C0-01", "C0-02"])
        caches = sorted(p.name for p in (TMP / "out_c0" / "cache").rglob("*.json"))
        self.assertEqual(caches, ["C0-01_r1.json", "C0-02_r1.json"])

    def test_condition1_keeps_only_age_and_occupation(self):
        spec = json.loads(PERSONA_SRC[0].read_text(encoding="utf-8"))["persona"]
        cfg = write_cfg("c1")
        code, log = run(*args(cfg, condition=1))
        self.assertEqual(code, 0, log)
        sent = FAKE.sent_text()
        self.assertIn(spec["occupation"]["title"], sent)
        self.assertNotIn(spec["name"], sent)
        self.assertNotIn(spec["residence"], sent)

        FAKE.reset()
        cfg = write_cfg("c2")
        code, log = run(*args(cfg, condition=2))
        self.assertEqual(code, 0, log)
        self.assertIn(spec["residence"], FAKE.sent_text())  # 조건 2는 그대로 들어간다

    def test_cost_cap_exit_3(self):
        cfg = write_cfg("cap", token_cap=1)
        code, log = run(*args(cfg))
        self.assertEqual(code, 3, log)
        self.assertEqual(FAKE.calls, 1)  # 첫 호출 뒤 다음 호출 전에 멈춘다
        self.assertEqual(read_raw("cap"), [])

    def test_auth_error_stops_without_retry(self):
        for mode in ["auth", "gemini_bad_key"]:
            with self.subTest(mode=mode):
                FAKE.reset(mode)
                cfg = write_cfg(f"auth_{mode}")
                code, log = run(*args(cfg))
                self.assertEqual(code, 2, log)
                self.assertEqual(FAKE.calls, 1, "인증 오류인데 다시 시도했다")
                self.assertEqual(read_raw(f"auth_{mode}"), [])

    def test_model_not_found_stops_without_retry(self):
        FAKE.reset("not_found")
        cfg = write_cfg("notfound")
        code, log = run(*args(cfg))
        self.assertEqual(code, 2, log)
        self.assertEqual(FAKE.calls, 1, "모델이 없는데 다시 시도했다")

    def test_empty_key_exit_2_writes_nothing(self):
        os.environ["OPENAI_API_KEY"] = ""
        cfg = write_cfg("nokey")
        code, log = run(*args(cfg))
        self.assertEqual(code, 2, log)
        self.assertEqual(FAKE.calls, 0)
        self.assertFalse((TMP / "out_nokey").exists())

    def test_provider_mismatch_exit_2(self):
        os.environ["OPENAI_BASE_URL"] = ""  # OpenAI 주소인데 config.ini 모델은 gemini
        cfg = write_cfg("mismatch")
        code, log = run(*args(cfg))
        self.assertEqual(code, 2, log)
        self.assertEqual(FAKE.calls, 0)

    def test_empty_response_retries_then_exit_5(self):
        FAKE.reset("empty")
        cfg = write_cfg("empty", empty_retries=2)
        code, log = run(*args(cfg))
        self.assertEqual(code, 5, log)
        self.assertEqual(FAKE.calls, 3)  # 처음 1번 + 재시도 2번 (빈 응답 캐시를 지우고 다시 부른다)
        summary = json.loads(read_summaries("empty")[-1].read_text(encoding="utf-8"))
        self.assertEqual(summary["empty_rate"], 1.0)
        self.assertEqual(summary["length_cutoff_rate"], 1.0)

    def test_input_errors(self):
        bad = json.loads((TMP / "snapshots/fake/snapshot.json").read_text(encoding="utf-8"))
        bad["service"] = "bad"
        bad["tasks"][0]["start_screen"] = "S9"
        (TMP / "snapshots/bad").mkdir(exist_ok=True)
        (TMP / "snapshots/bad/snapshot.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        cfg = write_cfg("input")
        cases = [
            ("start_screen 오류", args(cfg, service="bad"), 4),
            ("스냅샷 없음", args(cfg, service="nothing"), 1),
            ("조건 3", args(cfg, condition=3), 1),
            ("옵션 누락", ["--service", "fake"], 1),
            ("호출 상한 초과 설정", args(write_cfg("input_calls", max_calls_per_action=5)), 4),
            ("모르는 설정 키", args(write_cfg("input_key", tokn_cap=10)), 4),
        ]
        for label, argv, expected in cases:
            with self.subTest(label):
                code, log = run(*argv)
                self.assertEqual(code, expected, log)
        self.assertEqual(FAKE.calls, 0)
        self.assertFalse((TMP / "out_input").exists())


if __name__ == "__main__":
    unittest.main()

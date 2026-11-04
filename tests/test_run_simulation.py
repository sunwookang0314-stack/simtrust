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

# 임시 폴더에 리포 모양을 만든다: config.ini, 가짜 스냅샷(앱·웹), 임시 페르소나 2명
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
    """실제 API 대신 응답한다. mode로 정상, 빈 응답, 인증 오류 등을 고른다."""

    def __init__(self):
        self.reset()

    def reset(self, mode="ok"):
        self.mode = mode
        self.calls = 0
        self.prompts = []

    def decoded(self, i):
        # TinyTroupe는 페르소나와 메시지를 json.dumps 기본값으로 넣어서 한글이 \uXXXX로 나간다
        # (agent/tiny_person.py:319, agent/action_generator.py:125). 비교하려고 되돌린다.
        return re.sub(r"\\+u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), self.prompts[i])

    def sent_text(self):
        return "\n".join(self.decoded(i) for i in range(len(self.prompts)))

    def __call__(self, client_self, model, params):
        self.calls += 1
        self.prompts.append(json.dumps(params.get("messages"), ensure_ascii=False, default=str))
        request = httpx.Request("POST", "https://example.invalid")
        if self.mode == "auth":
            raise openai.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
        if self.mode == "gemini_bad_key":
            # 2026-11-04 Gemini 호환 주소에 틀린 키로 실제 호출했을 때 받은 응답 그대로
            body = [{"error": {"code": 400, "message": "Please pass a valid API key", "status": "INVALID_ARGUMENT"}}]
            raise openai.BadRequestError(f"Error code: 400 - {body}", response=httpx.Response(400, request=request),
                                         body=body)
        if self.mode == "not_found":
            raise openai.NotFoundError("model not found", response=httpx.Response(404, request=request), body=None)
        if self.mode == "empty" or (self.mode == "empty_once" and self.calls == 1):
            content, finish = "", "length"
        elif self.mode == "read_screen":
            # 이미지 확인 스크립트용. 화면 글자 일부만 읽은 답
            content = json.dumps({
                "actions": [{"type": "TALK", "content": "공모전, 대외활동, 채용 탭과 마감 3일 전 알림이 보여요", "target": ""},
                            {"type": "DONE", "content": "", "target": ""}],
                "cognitive_state": {"goals": "읽기", "context": ["화면"], "attention": "글자", "emotions": "보통"},
            }, ensure_ascii=False)
            finish = "stop"
        else:
            # 호출마다 #001 같은 표시가 붙는다. 캐시가 안 먹으면 결과가 달라지고, 기억이 새면 다음 프롬프트에 보인다
            mark = f"#{self.calls:03d}"
            actions = [
                {"type": "THINK", "content": f"공모전 탭부터 봐야겠다 {mark}", "target": ""},
                {"type": "TALK", "content": f"공모전 탭을 누를게요 {mark}", "target": ""},
            ]
            if self.mode == "long":
                # 행동 상한보다 긴 목록. TinyTroupe가 잘라야 한다
                actions = [{"type": "THINK", "content": f"생각 {k} {mark}", "target": ""} for k in range(6)] + actions
            actions.append({"type": "DONE", "content": "", "target": ""})
            content = json.dumps({
                "actions": actions,
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


def read_metas(name):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((TMP / f"out_{name}" / "meta").glob("*.json")) if not p.name.endswith(".summary.json")]


def last_summary(name):
    paths = sorted((TMP / f"out_{name}" / "meta").glob("*.summary.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def args(cfg, condition=2, repeat=1, limit=1, service="fake", platform="app"):
    argv = ["--service", service, "--platform", platform, "--condition", str(condition),
            "--repeat", str(repeat), "--seed", "7", "--config", cfg]
    if limit is not None:
        argv += ["--limit-personas", str(limit)]
    return argv


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

        summary = last_summary("cache")
        self.assertEqual(summary["calls_real"], 0)
        self.assertEqual(summary["calls_cached"], calls_first)

    def test_meta_has_trd_fields_and_no_key(self):
        cfg = write_cfg("meta")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        metas = read_metas("meta")
        self.assertEqual(len(metas), 1)
        meta = metas[0]
        for key in ["run_id", "timestamp", "provider", "base_url", "model", "tinytroupe_commit", "service",
                    "platform", "condition", "persona_id", "repeat", "seed", "input_mode", "cache_file",
                    "max_completion_tokens", "tokens_in", "tokens_out", "elapsed_sec", "status",
                    "protocol_version", "snapshot_version", "action_truncations"]:
            self.assertIn(key, meta)
        self.assertEqual(meta["status"], "성공")
        self.assertEqual(meta["platform"], "app")
        self.assertEqual(meta["seed"], 7)
        self.assertEqual(meta["max_actions_before_done"], 15)
        self.assertNotIn("test-not-a-real-key", json.dumps(meta, ensure_ascii=False))
        line = read_raw("meta")[0]
        self.assertEqual(line["platform"], "app")
        self.assertEqual([s["task_id"] for s in line["steps"]], ["T1", "T2"])
        self.assertTrue(line["steps"][0]["talk"])

    def test_platforms_use_own_snapshot_and_cache(self):
        cfg = write_cfg("platform")
        code, log = run(*args(cfg, platform="web"))
        self.assertEqual(code, 0, log)
        self.assertIn("PC 브라우저 화면이다", FAKE.sent_text())  # 웹 스냅샷에만 있는 문장
        code, log = run(*args(cfg, platform="app"))
        self.assertEqual(code, 0, log)
        self.assertEqual([x["platform"] for x in read_raw("platform")], ["web", "app"])
        groups = sorted(p.name for p in (TMP / "out_platform" / "cache").iterdir())
        self.assertEqual(len(groups), 2)
        self.assertTrue(groups[0].startswith("fake_app_c2_") and groups[1].startswith("fake_web_c2_"), groups)

    def test_feature_description_not_sent(self):
        cfg = write_cfg("feature")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        sent = FAKE.sent_text()
        self.assertIn("마감이 가까운 공고", sent)  # S1 화면 설명은 들어간다
        self.assertNotIn("FEATURE-ONLY", sent)  # 기능 설명은 안 들어간다

    def test_condition0_uses_ten_slots_and_neutral_name(self):
        cfg = write_cfg("c0")
        code, log = run(*args(cfg, condition=0, limit=None))
        self.assertEqual(code, 0, log)
        self.assertEqual([x["persona_id"] for x in read_raw("c0")], [f"C0-{i:02d}" for i in range(1, 11)])
        caches = sorted(p.name for p in (TMP / "out_c0" / "cache").rglob("*.json"))
        self.assertEqual(caches, [f"C0-{i:02d}_r1.json" for i in range(1, 11)])
        self.assertIn("참여자", FAKE.decoded(0))
        self.assertNotIn("C0-01", FAKE.decoded(0))  # 슬롯 ID는 기록용이고 AI한테는 안 간다

    def test_condition1_keeps_only_age_and_occupation(self):
        spec = json.loads(PERSONA_SRC[0].read_text(encoding="utf-8"))["persona"]
        cfg = write_cfg("c1")
        code, log = run(*args(cfg, condition=1))
        self.assertEqual(code, 0, log)
        sent = FAKE.sent_text()
        self.assertIn(spec["occupation"]["title"], sent)
        self.assertIn("참여자", sent)
        self.assertNotIn(spec["name"], sent)
        self.assertNotIn(spec["residence"], sent)

        FAKE.reset()
        cfg = write_cfg("c2")
        code, log = run(*args(cfg, condition=2))
        self.assertEqual(code, 0, log)
        self.assertIn(spec["residence"], FAKE.sent_text())  # 조건 2는 그대로 들어간다

    def test_second_episode_has_no_memory_of_first(self):
        name_a = json.loads(PERSONA_SRC[0].read_text(encoding="utf-8"))["persona"]["name"]
        cfg = write_cfg("memory", cache=False)
        code, log = run(*args(cfg, limit=2))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 4)  # 에피소드 2개 x 과제 2개
        # 같은 에피소드 안에서는 앞 과제 답을 기억한다. 이게 안 보이면 아래 검사가 의미 없다
        self.assertIn("#001", FAKE.decoded(1))
        for i in (2, 3):
            sent = FAKE.decoded(i)
            self.assertNotIn("#001", sent, "두 번째 에피소드에 첫 번째 에피소드 답이 들어갔다")
            self.assertNotIn("#002", sent, "두 번째 에피소드에 첫 번째 에피소드 답이 들어갔다")
            self.assertNotIn(name_a, sent, "두 번째 에피소드에 첫 번째 페르소나가 들어갔다")

    def test_action_truncation_is_counted(self):
        cfg = write_cfg("trunc", max_actions_before_done=4)
        FAKE.reset("long")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        summary = last_summary("trunc")
        self.assertEqual(summary["action_truncations"], FAKE.calls)
        self.assertEqual(read_metas("trunc")[0]["action_truncations"], FAKE.calls)
        self.assertIn("행동 잘림    : 2회", log)

        FAKE.reset()
        cfg = write_cfg("notrunc")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        self.assertEqual(last_summary("notrunc")["action_truncations"], 0)

    def test_cost_cap_exit_3(self):
        cfg = write_cfg("cap", token_cap=1)
        code, log = run(*args(cfg))
        self.assertEqual(code, 3, log)
        self.assertEqual(FAKE.calls, 1)  # 첫 호출 뒤 다음 호출 전에 멈춘다
        self.assertEqual(read_raw("cap"), [])

    def test_cost_cap_counts_previous_runs(self):
        # 첫 실행: 호출 2번 x 1,100 토큰 = 2,200
        cfg = write_cfg("cumul", cache=False)
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        # 다른 제공자 기록은 이 예산에서 빠진다
        (TMP / "out_cumul/meta/other_provider.json").write_text(
            json.dumps({"provider": "openai", "tokens_in": 10**9, "tokens_out": 0}), encoding="utf-8")

        FAKE.reset()
        cfg = write_cfg("cumul", cache=False, token_cap=2500)
        code, log = run(*args(cfg))
        self.assertEqual(code, 3, log)
        self.assertEqual(FAKE.calls, 1)  # 2,200에서 한 번 부르면 3,300이라 다음 호출 전에 멈춘다
        summary = last_summary("cumul")
        self.assertEqual(summary["tokens_before"], 2200)

        # 이전 기록을 못 읽으면 누적을 셀 수 없으니 아무것도 안 하고 멈춘다
        FAKE.reset()
        (TMP / "out_cumul/meta/broken.json").write_text("{", encoding="utf-8")
        code, log = run(*args(cfg))
        self.assertEqual(code, 4, log)
        self.assertEqual(FAKE.calls, 0)

    def test_auth_error_stops_without_retry(self):
        for mode in ["auth", "gemini_bad_key"]:
            with self.subTest(mode=mode):
                FAKE.reset(mode)
                cfg = write_cfg(f"auth_{mode}")
                code, log = run(*args(cfg, limit=2))
                self.assertEqual(code, 2, log)
                self.assertEqual(FAKE.calls, 1, "인증 오류인데 다시 시도했거나 다음 에피소드로 넘어갔다")
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
        summary = last_summary("empty")
        self.assertEqual(summary["empty_rate"], 1.0)
        self.assertEqual(summary["length_cutoff_rate"], 1.0)

    def test_failed_episode_does_not_stop_the_run(self):
        # 에피소드 2개 중 1개 실패: 다음 에피소드는 돌지만 실패율 50%라 종료 코드 5
        FAKE.reset("empty_once")
        cfg = write_cfg("cont2", empty_retries=0)
        code, log = run(*args(cfg, limit=2))
        self.assertEqual(code, 5, log)
        metas = read_metas("cont2")
        self.assertEqual(len(metas), 2)
        self.assertEqual(sorted(m["status"].split(":")[0] for m in metas), ["성공", "실패(API)"])
        self.assertEqual(len(read_raw("cont2")), 1)  # 실패한 에피소드는 원시 응답에 안 쓴다

        # 에피소드 20개 중 1개 실패: 실패율 5%는 문턱을 넘지 않아서 종료 코드 0
        FAKE.reset("empty_once")
        cfg = write_cfg("cont20", empty_retries=0)
        code, log = run(*args(cfg, condition=0, repeat=2, limit=None))
        self.assertEqual(code, 0, log)
        summary = last_summary("cont20")
        self.assertEqual((summary["episodes_run"], summary["episodes_ok"]), (20, 19))
        self.assertEqual(summary["failure_rate"], 0.05)

    def test_input_errors(self):
        bad = json.loads((TMP / "snapshots/fake/app/snapshot.json").read_text(encoding="utf-8"))
        bad["service"] = "bad"
        bad["tasks"][0]["start_screen"] = "S9"
        (TMP / "snapshots/bad/app").mkdir(parents=True, exist_ok=True)
        (TMP / "snapshots/bad/app/snapshot.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        wrong = json.loads((TMP / "snapshots/fake/web/snapshot.json").read_text(encoding="utf-8"))
        wrong["service"] = "mixed"  # 웹 스냅샷을 앱 자리에 둔 경우
        (TMP / "snapshots/mixed/app").mkdir(parents=True, exist_ok=True)
        (TMP / "snapshots/mixed/app/snapshot.json").write_text(json.dumps(wrong, ensure_ascii=False), encoding="utf-8")
        cfg = write_cfg("input")
        cases = [
            ("start_screen 오류", args(cfg, service="bad"), 4),
            ("플랫폼이 다른 스냅샷", args(cfg, service="mixed"), 4),
            ("스냅샷 없음", args(cfg, service="nothing"), 1),
            ("조건 3", args(cfg, condition=3), 1),
            ("옵션 누락", ["--service", "fake"], 1),
            ("플랫폼 값 오류", args(cfg, platform="tablet"), 1),
            ("행동 상한 0", args(write_cfg("input_actions", max_actions_before_done=0)), 4),
            ("중립 이름 비어 있음", args(write_cfg("input_name", neutral_agent_name=" ")), 4),
            ("모르는 설정 키", args(write_cfg("input_key", tokn_cap=10)), 4),
        ]
        for label, argv, expected in cases:
            with self.subTest(label):
                code, log = run(*argv)
                self.assertEqual(code, expected, log)
        self.assertEqual(FAKE.calls, 0)
        self.assertFalse((TMP / "out_input").exists())


import check_image_input as cii  # noqa: E402

shutil.copytree(REPO / "experiments/runner_dev/images", TMP / "images")


class TestCheckImageInput(unittest.TestCase):
    def setUp(self):
        FAKE.reset("read_screen")
        os.environ["OPENAI_BASE_URL"] = GEMINI_URL
        os.environ["OPENAI_API_KEY"] = "test-not-a-real-key"

    def run_check(self, name, *extra):
        out, err = io.StringIO(), io.StringIO()
        argv = ["--service", "fake", "--platform", "app", "--snapshot-root", "snapshots",
                "--images-root", "images", "--out", f"out_{name}", *extra]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cii.main(argv, root=TMP)
        reports = sorted((TMP / f"out_{name}").glob("*.json"))
        return code, out.getvalue() + err.getvalue(), json.loads(reports[-1].read_text(encoding="utf-8"))

    def test_images_bundled_without_auto_description(self):
        code, log, report = self.run_check("imgcheck")
        self.assertEqual(code, 0, log)
        by_mode = {x["mode"]: x for x in report["results"]}
        # 캡처 3장을 see() 한 번에 묶어서 요청 하나에 같이 들어간다
        self.assertEqual(by_mode["image"]["images_per_request"], [3])
        self.assertEqual(by_mode["text"]["images_per_request"], [0])
        # 자동 영어 요약 요청이 따로 나가지 않는다 (질문 하나에 호출 하나)
        self.assertEqual(by_mode["image"]["auto_description_requests"], 0)
        self.assertEqual(FAKE.calls, 2)
        self.assertNotIn("Describe the image", FAKE.sent_text())
        self.assertEqual(report["settings"]["max_image_stimuli_to_recall"], 1)
        # 답에 있는 공통 글자만 맞은 것으로 센다
        shared = by_mode["image"]["score_talk"]["shared"]
        self.assertEqual(shared["hit"], 4)
        self.assertIn("마이", shared["missed"])

    def test_bad_modes_and_recall_are_usage_errors(self):
        for argv in (["--modes", "video"], ["--recall", "0"]):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as cm:
                        cii.main(argv, root=TMP)
                self.assertEqual(cm.exception.code, 1)
        self.assertEqual(FAKE.calls, 0)


if __name__ == "__main__":
    unittest.main()

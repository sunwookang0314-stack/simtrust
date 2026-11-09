"""scripts/run_simulation.py, scripts/check_image_input.py 오프라인 테스트. API 키 없이 돈다.

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
PROTOCOL = REPO / "docs/ai-protocol"

# 임시 폴더에 리포 모양을 만든다: config.ini, 가짜 스냅샷(앱·웹), 가짜 화면, 프로토콜 파일, 임시 페르소나 2명
TMP = Path(tempfile.mkdtemp(prefix="simtrust_runner_test_"))
# 사본에서만 호출 사이 대기(WAITING_TIME=2초)를 0으로 둔다. 가짜 API인데도 호출마다 2초씩 쉬어서 테스트가 몇 분 걸렸다
(TMP / "config.ini").write_text(
    re.sub(r"(?m)^WAITING_TIME=.*$", "WAITING_TIME=0", (REPO / "config.gemini.ini").read_text(encoding="ascii")),
    encoding="ascii")
shutil.copytree(REPO / "experiments/runner_dev/snapshots", TMP / "snapshots")
shutil.copytree(REPO / "experiments/runner_dev/images", TMP / "images")
shutil.copytree(PROTOCOL, TMP / "protocol")
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

import check_image_input as cii
import run_simulation as rs

FEATURES = [line.split("|", 1)[1] for line in (PROTOCOL / "features.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def decode(text):
    # TinyTroupe 기본 동작은 한글을 이스케이프해서 보낸다 (agent/tiny_person.py:319, agent/action_generator.py:125).
    # 11/6부터 실행기가 고쳐서 그대로 가지만, 이스케이프가 남아도 문구 비교가 되게 되돌린다.
    text = re.sub(r"\\+u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return text.replace("\\n", "\n").replace('\\"', '"')


def squash(text):
    # 역슬래시, 공백·줄바꿈, 따옴표를 뺀다
    return re.sub(r'[\\\s"]', "", text)


def message_text(message):
    content = message.get("content")
    if isinstance(content, list):  # 이미지가 든 메시지
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)


class FakeAPI:
    """실제 API 대신 응답한다. 마지막 사용자 메시지를 보고 어느 질문인지 가려 그럴듯한 답을 준다."""

    def __init__(self):
        self.reset()

    def reset(self, mode="ok"):
        self.mode = mode
        self.calls = 0
        self.prompts = []  # 요청 전체 (디코딩 전)
        self.last_user = []  # 요청마다 마지막 사용자 메시지 (디코딩 후)

    def decoded(self, i):
        return decode(self.prompts[i])

    def sent_text(self):
        return "\n".join(self.decoded(i) for i in range(len(self.prompts)))

    def answer_for(self, question, mark):
        if self.mode == "read_screen":
            return "공모전, 대외활동, 채용 탭과 마감 3일 전 알림이 보여요"
        if question == "use":
            if self.mode == "all_use":
                return "\n".join(f"{f}: 쓸 것 같다 {mark}" for f in FEATURES)
            verdict = ["쓸 것 같다", "안 쓸 것 같다", "쓸 것 같다", "안 쓸 것 같다"]
            return "\n".join(f"{f}: {v} {mark}" for f, v in zip(FEATURES, verdict))
        if question == "why":
            return f"공고 검색·필터: 인턴 공고를 찾으려고 쓸 것 같고 조건을 한 번에 걸 수 있어서 편할 것 같다 {mark}"
        if question == "nouse":
            return f"공고 저장: 나한테 필요 없을 것 같아서 {mark}"
        if question == "q47":
            return f"공고 저장: 지금은 카톡 나에게 보내기로 따로 모아 둡니다 {mark}"
        return f"화면을 봤어요 {mark}"

    def __call__(self, client_self, model, params):
        self.calls += 1
        # 진짜 TinyTroupe _raw_model_call처럼 받은 dict에서 stream을 지운다 (응답 형식을 줄 때, openai_client.py 438행)
        params.pop("stream", None)
        messages = params.get("messages") or []
        self.prompts.append(json.dumps(messages, ensure_ascii=False, default=str))
        users = [m for m in messages if m.get("role") == "user"]
        last = decode(message_text(users[-1])) if users else ""
        self.last_user.append(last)
        request = httpx.Request("POST", "https://example.invalid")
        if self.mode == "timeout_once" and self.calls == 1:
            raise openai.APITimeoutError(request=request)  # TinyTroupe가 기다리지 않고 바로 다시 부른다
        if self.mode == "interrupt_at_2" and self.calls == 2:
            raise KeyboardInterrupt
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
        else:
            question = ("q47" if "안 쓰게 됐거나 안 써본 기능이 있다면" in last else
                        "nouse" if "안 쓸 것 같은 이유에 가까운" in last else
                        "why" if "쓸 것 같다고 고른 기능마다" in last else
                        "use" if "중 하나로 답해주세요" in last else "other")
            # 호출마다 #001 같은 표시가 붙는다. 캐시가 안 먹으면 결과가 달라지고, 기억이 새면 다음 프롬프트에 보인다
            mark = f"#{self.calls:03d}"
            actions = [{"type": "THINK", "content": f"화면을 다시 떠올려 본다 {mark}", "target": ""},
                       {"type": "TALK", "content": self.answer_for(question, mark), "target": ""}]
            if self.mode == "long":
                # 행동 상한보다 긴 목록. TinyTroupe가 잘라야 한다
                actions = [{"type": "THINK", "content": f"생각 {k} {mark}", "target": ""} for k in range(6)] + actions
            actions.append({"type": "DONE", "content": "", "target": ""})
            content = json.dumps({
                "actions": actions,
                "cognitive_state": {"goals": "답하기", "context": ["화면"], "attention": "질문", "emotions": "보통"},
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
BASE_CFG.update({"snapshot_root": "snapshots", "personas_dir": "personas", "images_root": "images",
                 "protocol_dir": "protocol"})


def write_cfg(name, **override):
    cfg = dict(BASE_CFG)
    cfg.update({
        "raw_responses_path": f"out_{name}/raw.jsonl",
        "meta_dir": f"out_{name}/meta",
        "cache_dir": f"out_{name}/cache",
        "tinytroupe_log_dir": f"out_{name}/logs",
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


def make_snapshot(service, **change):
    snap = json.loads((TMP / "snapshots/fake/app/snapshot.json").read_text(encoding="utf-8"))
    snap["service"] = service
    snap.update(change)
    (TMP / "snapshots" / service / "app").mkdir(parents=True, exist_ok=True)
    (TMP / "snapshots" / service / "app" / "snapshot.json").write_text(json.dumps(snap, ensure_ascii=False),
                                                                       encoding="utf-8")


def qids(line):
    return [(a["question_id"], a["asked"]) for a in line["answers"]]


ALL_ASKED = [("Q-AI-USE", True), ("Q-AI-WHY-USE", True), ("Q-AI-NOUSE", True), ("Q-4-7", True)]


class TestRunSimulation(unittest.TestCase):
    def setUp(self):
        FAKE.reset()
        os.environ["OPENAI_BASE_URL"] = GEMINI_URL
        os.environ["OPENAI_API_KEY"] = "test-not-a-real-key"

    def test_question_flow_and_raw_format(self):
        cfg = write_cfg("flow")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 4)  # 질문 4개, 질문마다 호출 1번
        line = read_raw("flow")[0]
        self.assertEqual(qids(line), ALL_ASKED)
        self.assertEqual(line["use_parsed_at_runtime"], {"F1": "use", "F2": "nouse", "F3": "use", "F4": "nouse"})
        self.assertEqual([f["name"] for f in line["features"]], FEATURES)
        for a in line["answers"]:
            self.assertTrue(a["talk"])
            self.assertTrue(a["think"])
            self.assertEqual(a["feature_id"], "")
        self.assertEqual((line["platform"], line["question_order"]), ("app", "b"))

    def test_raw_output_feeds_extractor(self):
        # 실행기가 남긴 원시 응답을 추출기가 그대로 읽는지 (형식이 어긋나면 여기서 걸린다)
        import extract_reasons as er

        cfg = write_cfg("toextract")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        with contextlib.redirect_stdout(io.StringIO()):
            code = er.main(["--raw", "out_toextract/raw.jsonl", "--options", "protocol/options_4-6.txt",
                            "--out", "out_toextract/extracted"], root=TMP)
        self.assertEqual(code, 0)
        records = [json.loads(x) for x in
                   next((TMP / "out_toextract/extracted").glob("extracted_*.jsonl")).read_text(encoding="utf-8")
                   .splitlines()]
        by = {r["feature_id"]: r for r in records}
        self.assertEqual({k: v["use_choice"] for k, v in by.items()},
                         {"F1": "use", "F2": "nouse", "F3": "use", "F4": "nouse"})
        self.assertEqual(by["F2"]["nouse_options"], ["나한테 필요 없을 것 같아서"])
        self.assertEqual(by["F1"]["reason_counts"]["why_use"], 1)

    def test_meta_has_trd_fields_and_no_key(self):
        cfg = write_cfg("meta")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        metas = read_metas("meta")
        self.assertEqual(len(metas), 1)
        meta = metas[0]
        for key in ["run_id", "timestamp", "provider", "base_url", "model", "tinytroupe_commit", "simtrust_commit", "service",
                    "platform", "condition", "persona_id", "repeat", "seed", "input_mode", "cache_file",
                    "max_completion_tokens", "tokens_in", "tokens_out", "elapsed_sec", "status",
                    "protocol_version", "snapshot_version", "action_truncations"]:
            self.assertIn(key, meta)
        self.assertEqual(meta["status"], "성공")
        self.assertEqual(meta["questions_asked"], [q for q, _ in ALL_ASKED])
        self.assertEqual(meta["images_per_request"], [0, 0, 0, 0])  # 텍스트 모드
        self.assertEqual(meta["max_actions_before_done"], 15)
        self.assertNotIn("test-not-a-real-key", json.dumps(meta, ensure_ascii=False))

    def test_korean_is_sent_without_escapes(self):
        # 11/6 결정: 한글을 \\uXXXX로 바꾸지 않고 그대로 보낸다 (patch_tinytroupe_json)
        cfg = write_cfg("unicode")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        hangul_escape = re.compile(r"\\+u(?:a[c-f]|b[0-9a-f]|c[0-9a-f]|d[0-7])[0-9a-f]{2}", re.I)
        for i, prompt in enumerate(FAKE.prompts):
            self.assertIsNone(hangul_escape.search(prompt), f"요청 {i + 1}에 한글 이스케이프가 남았다")
        persona = json.loads(PERSONA_SRC[0].read_text(encoding="utf-8"))
        occupation = persona.get("persona", persona).get("occupation")
        if isinstance(occupation, dict):
            occupation = occupation.get("title")
        self.assertTrue(occupation)
        self.assertIn(occupation, FAKE.prompts[0])
        self.assertIs(read_metas("unicode")[0]["json_ensure_ascii"], False)
        # 표준 json 모듈은 그대로다 (다른 코드가 쓰는 동작은 안 바뀐다)
        self.assertEqual(json.dumps("한"), '"\\ud55c"')

    def test_question_texts_are_sent_as_written(self):
        cfg = write_cfg("texts")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        sent = FAKE.sent_text()
        q = lambda name: (PROTOCOL / "questions" / f"{name}.txt").read_text(encoding="utf-8").strip()  # noqa: E731
        # 폼 4-7 문구가 글자 그대로 간다. JSON 이스케이프가 몇 겹인지와 상관없이 보려고 공백·역슬래시·따옴표를 빼고 비교한다
        self.assertIn(squash(q("Q-4-7")), squash(sent))
        self.assertIn(squash(q("START")), squash(sent))
        self.assertIn("아래는 가짜공고 앱 화면입니다", sent)
        for name in FEATURES:
            self.assertIn(name, FAKE.last_user[0])
        for option in (PROTOCOL / "options_4-6.txt").read_text(encoding="utf-8").split("\n"):
            if option.strip():
                self.assertIn(option.strip(), FAKE.last_user[2])
        self.assertNotRegex(sent, r"\{(features|options_4_6|service_name|platform_label)\}")
        self.assertIn("마감이 가까운 공고", sent)  # 화면 설명은 들어간다
        self.assertNotIn("FEATURE-ONLY", sent)  # 기능 설명은 안 들어간다 (프로토콜 2번)

    def test_follow_up_skipped_when_no_feature_needs_it(self):
        FAKE.reset("all_use")
        cfg = write_cfg("allyes")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 3)
        line = read_raw("allyes")[0]
        self.assertEqual(qids(line), [("Q-AI-USE", True), ("Q-AI-WHY-USE", True), ("Q-AI-NOUSE", False),
                                      ("Q-4-7", True)])
        self.assertEqual(line["answers"][2]["skipped"], "안 쓸 것 같은 기능 없음")

    def test_missing_feature_is_recorded_not_asked(self):
        make_snapshot("miss", missing_features=["F3"])
        cfg = write_cfg("miss")
        code, log = run(*args(cfg, service="miss"))
        self.assertEqual(code, 0, log)
        self.assertNotIn("마감 알림", FAKE.last_user[0])
        line = read_raw("miss")[0]
        self.assertIn({"question_id": "", "feature_id": "F3", "asked": False, "skipped": "없음", "captures": [],
                       "images_in_request": 0, "actions": [], "think": "", "talk": ""}, line["answers"])

    def test_image_mode_bundles_captures_without_auto_description(self):
        cfg = write_cfg("image", input_mode="image")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 4)  # 자동 영어 요약 호출이 따로 없다
        self.assertNotIn("Describe the image", FAKE.sent_text())
        line = read_raw("image")[0]
        for a in line["answers"]:
            # 캡처 3장을 see() 한 번에 줬고, 이전 화면 다시 보여주기 1이라 질문마다 3장이 들어간다
            self.assertEqual(a["images_in_request"], 3, a["question_id"])
            self.assertEqual(a["captures"], ["S1.png", "S2.png", "S3.png"])
        meta = read_metas("image")[0]
        self.assertEqual(meta["capture_files"], ["images/fake/app/S1.png", "images/fake/app/S2.png",
                                                 "images/fake/app/S3.png"])
        self.assertEqual(last_summary("image")["images_per_request_max"], 3)

    def test_random_capture_names_can_be_required(self):
        cfg = write_cfg("randname", input_mode="image", require_random_capture_names=True)
        code, log = run(*args(cfg))
        self.assertEqual(code, 4, log)
        self.assertIn("무작위 16진수", log)
        self.assertEqual(FAKE.calls, 0)

    def test_tinytroupe_log_is_moved(self):
        cfg = write_cfg("logs")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        self.assertTrue(list((TMP / "out_logs" / "logs").glob("tinytroupe.*.log")))
        self.assertEqual(list(TMP.glob("tinytroupe.*.log")), [])

    def test_ok_then_cache_rerun_gives_same_result(self):
        cfg = write_cfg("cache")
        code, log = run(*args(cfg, repeat=2))
        self.assertEqual(code, 0, log)
        first = read_raw("cache")
        self.assertEqual(len(first), 2)
        calls_first = FAKE.calls
        # 회차마다 캐시가 따로라서 두 회차 응답이 다르다 (같이 쓰면 같아진다)
        self.assertNotEqual(first[0]["answers"], first[1]["answers"])

        # 같은 원시 응답 파일로는 끝난 에피소드를 건너뛰니, 캐시만 같이 쓰는 새 출력으로 다시 돌린다
        FAKE.reset()
        cfg2 = write_cfg("cache_again", cache_dir="out_cache/cache")
        code, log = run(*args(cfg2, repeat=2))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 0, "다시 돌렸는데 API를 불렀다 (캐시 재현 실패)")
        second = read_raw("cache_again")
        self.assertEqual([x["answers"] for x in first], [x["answers"] for x in second])
        summary = last_summary("cache_again")
        self.assertEqual((summary["calls_real"], summary["calls_cached"]), (0, calls_first))

    def test_retry_keeps_cache_key(self):
        # 11/9 김승하 #37 리뷰: 재시도하면 TinyTroupe가 같은 dict로 캐시 키를 다시 만드는데, 앞 시도에서 dict가
        # 바뀌어(penalty·stream 삭제) 재시도로 받은 응답이 다른 키로 저장됐다. 다시 돌리면 API를 또 불렀다
        FAKE.reset("timeout_once")
        cfg = write_cfg("retrykey")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 5)  # 첫 호출이 시간 초과로 한 번 더 불렀다
        first = read_raw("retrykey")
        FAKE.reset()
        cfg2 = write_cfg("retrykey_again", cache_dir="out_retrykey/cache")
        code, log = run(*args(cfg2))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 0, "재시도로 받은 응답을 캐시에서 못 찾았다")
        self.assertEqual(read_raw("retrykey_again")[0]["answers"], first[0]["answers"])

    def test_rerun_skips_recorded_episodes(self):
        # 11/9 김승하 #37 리뷰: 같은 명령을 다시 돌리면 같은 에피소드가 원시 응답에 두 번 쌓였다.
        # 이제 끝난 에피소드는 건너뛰고 남은 것만 돈다 (중간에 멈춘 실행 이어 돌리기)
        cfg = write_cfg("resume")
        code, log = run(*args(cfg, repeat=1))
        self.assertEqual(code, 0, log)
        FAKE.reset()
        code, log = run(*args(cfg, repeat=2))
        self.assertEqual(code, 0, log)
        self.assertEqual(FAKE.calls, 4)  # 2회차만 돈다
        self.assertIn("[이어서]", log)
        self.assertEqual([x["repeat"] for x in read_raw("resume")], [1, 2])
        self.assertEqual(last_summary("resume")["episodes_skipped"], 1)
        FAKE.reset()
        code, log = run(*args(cfg, repeat=2))
        self.assertEqual((code, FAKE.calls, len(read_raw("resume"))), (0, 0, 2))
        # 조건이 다르면 다른 에피소드다
        code, log = run(*args(cfg, condition=1))
        self.assertEqual((code, len(read_raw("resume"))), (0, 3), log)

    def test_ctrl_c_keeps_tokens_and_summary(self):
        # 11/9 김승하 #37 리뷰: Ctrl-C로 멈추면 그 에피소드에서 쓴 토큰이 실행 기록에 안 남아서
        # 다음 실행의 누적 토큰(비용 상한)을 모자라게 셌다
        FAKE.reset("interrupt_at_2")
        cfg = write_cfg("ctrlc", cache=False)
        code, log = run(*args(cfg, limit=2))
        self.assertEqual(code, rs.EXIT_INTERRUPTED, log)
        self.assertEqual(FAKE.calls, 2)
        metas = read_metas("ctrlc")
        self.assertEqual(len(metas), 1)  # 두 번째 페르소나는 시작하지 않는다
        self.assertTrue(metas[0]["status"].startswith("중단(Ctrl-C)"), metas[0]["status"])
        self.assertEqual(metas[0]["tokens_in"] + metas[0]["tokens_out"], 1100)  # 멈추기 전 호출 1번
        self.assertEqual(read_raw("ctrlc"), [])
        self.assertEqual(last_summary("ctrlc")["exit_code"], rs.EXIT_INTERRUPTED)
        FAKE.reset()
        code, log = run(*args(cfg, limit=2))
        self.assertEqual(code, 0, log)
        self.assertEqual(last_summary("ctrlc")["tokens_before"], 1100)

    def test_platforms_use_own_snapshot_and_cache(self):
        cfg = write_cfg("platform")
        code, log = run(*args(cfg, platform="web"))
        self.assertEqual(code, 0, log)
        sent = FAKE.sent_text()
        self.assertIn("PC 브라우저 화면이다", sent)  # 웹 스냅샷에만 있는 문장
        self.assertIn("아래는 가짜공고 웹사이트 화면입니다", sent)  # 폼 3-3 보기와 같은 이름
        code, log = run(*args(cfg, platform="app"))
        self.assertEqual(code, 0, log)
        self.assertEqual([x["platform"] for x in read_raw("platform")], ["web", "app"])
        groups = sorted(p.name for p in (TMP / "out_platform" / "cache").iterdir())
        self.assertTrue(groups[0].startswith("fake_app_c2_") and groups[1].startswith("fake_web_c2_"), groups)

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
        self.assertEqual(FAKE.calls, 8)  # 에피소드 2개 x 질문 4개
        # 같은 에피소드 안에서는 앞 질문 답을 기억한다. 이게 안 보이면 아래 검사가 의미 없다
        self.assertIn("#001", FAKE.decoded(1))
        for i in range(4, 8):
            sent = FAKE.decoded(i)
            for mark in ("#001", "#002", "#003", "#004"):
                self.assertNotIn(mark, sent, "두 번째 에피소드에 첫 번째 에피소드 답이 들어갔다")
            self.assertNotIn(name_a, sent, "두 번째 에피소드에 첫 번째 페르소나가 들어갔다")

    def test_action_truncation_is_counted(self):
        cfg = write_cfg("trunc", max_actions_before_done=4)
        FAKE.reset("long")
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        summary = last_summary("trunc")
        self.assertEqual(summary["action_truncations"], FAKE.calls)
        self.assertEqual(read_metas("trunc")[0]["action_truncations"], FAKE.calls)
        self.assertIn(f"행동 잘림    : {FAKE.calls}회", log)

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
        # 첫 실행: 호출 4번 x 1,100 토큰 = 4,400
        cfg = write_cfg("cumul", cache=False)
        code, log = run(*args(cfg))
        self.assertEqual(code, 0, log)
        # 다른 제공자 기록은 이 예산에서 빠진다
        (TMP / "out_cumul/meta/other_provider.json").write_text(
            json.dumps({"provider": "openai", "tokens_in": 10**9, "tokens_out": 0}), encoding="utf-8")

        FAKE.reset()
        cfg = write_cfg("cumul", cache=False, token_cap=5000)
        code, log = run(*args(cfg, repeat=2))  # 1회차는 이미 있어서 건너뛰고 2회차를 돈다
        self.assertEqual(code, 3, log)
        self.assertEqual(FAKE.calls, 1)  # 4,400에서 한 번 부르면 5,500이라 다음 호출 전에 멈춘다
        self.assertEqual(last_summary("cumul")["tokens_before"], 4400)

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

    def test_feature_id_with_space_is_duplicate(self):
        # 11/9 김승하 리뷰: "F1 |..."과 "F1|..."은 같은 기능인데 공백을 안 지우고 겹침을 봐서 못 잡았다
        proto = TMP / "protocol_dupid"
        shutil.copytree(TMP / "protocol", proto, dirs_exist_ok=True)
        (proto / "features.txt").write_text("F1|공고 검색·필터\nF1 |공고 저장\n", encoding="utf-8")
        _, problems = rs.load_protocol(proto)
        self.assertIn("기능 ID가 겹친다: F1", problems)

    def test_input_errors(self):
        make_snapshot("noname", service_name="")
        wrong = json.loads((TMP / "snapshots/fake/web/snapshot.json").read_text(encoding="utf-8"))
        wrong["service"] = "mixed"  # 웹 스냅샷을 앱 자리에 둔 경우
        (TMP / "snapshots/mixed/app").mkdir(parents=True, exist_ok=True)
        (TMP / "snapshots/mixed/app/snapshot.json").write_text(json.dumps(wrong, ensure_ascii=False), encoding="utf-8")
        make_snapshot("badmiss", missing_features=["F9"])
        shutil.copytree(TMP / "protocol", TMP / "protocol_bad")
        (TMP / "protocol_bad/questions/Q-4-7.txt").write_text("{features} 안 쓰게 됐거나", encoding="utf-8")
        shutil.copytree(TMP / "protocol", TMP / "protocol_noopt")
        (TMP / "protocol_noopt/options_4-6.txt").unlink()
        cfg = write_cfg("input")
        cases = [
            ("서비스 이름 없음", args(cfg, service="noname"), 4),
            ("플랫폼이 다른 스냅샷", args(cfg, service="mixed"), 4),
            ("없는 기능 ID", args(cfg, service="badmiss"), 4),
            ("스냅샷 없음", args(cfg, service="nothing"), 1),
            ("조건 3", args(cfg, condition=3), 1),
            ("옵션 누락", ["--service", "fake"], 1),
            ("플랫폼 값 오류", args(cfg, platform="tablet"), 1),
            ("행동 상한 0", args(write_cfg("input_actions", max_actions_before_done=0)), 4),
            ("중립 이름 비어 있음", args(write_cfg("input_name", neutral_agent_name=" ")), 4),
            ("질문 순서 a", args(write_cfg("input_order", question_order="a")), 4),
            ("이전 화면 0", args(write_cfg("input_recall", max_image_stimuli_to_recall=0)), 4),
            ("프로토콜 폴더 없음", args(write_cfg("input_proto", protocol_dir="nothing")), 4),
            ("4-7에 자리", args(write_cfg("input_q47", protocol_dir="protocol_bad")), 4),
            ("4-6 보기 없음", args(write_cfg("input_opt", protocol_dir="protocol_noopt")), 4),
            ("모르는 설정 키", args(write_cfg("input_key", tokn_cap=10)), 4),
        ]
        for label, argv, expected in cases:
            with self.subTest(label):
                code, log = run(*argv)
                self.assertEqual(code, expected, log)
        self.assertEqual(FAKE.calls, 0)
        self.assertFalse((TMP / "out_input").exists())


class TestParseUseAnswers(unittest.TestCase):
    FEATS = [(f"F{i}", name) for i, name in enumerate(FEATURES, 1)]

    def test_line_per_feature(self):
        text = ("공고 검색·필터: 쓸 것 같다\n공고 저장 (스크랩, 찜, 북마크): 안 쓸 것 같다\n"
                "마감 알림 - 쓸 거 같아요\n추천 공고 목록: 쓰지 않을 것 같아요")
        self.assertEqual(rs.parse_use_answers(text, self.FEATS),
                         {"F1": "use", "F2": "nouse", "F3": "use", "F4": "nouse"})

    def test_short_names_and_unknown(self):
        text = "공고 저장은 쓸 것 같아요. 마감 알림은 잘 모르겠어요."
        self.assertEqual(rs.parse_use_answers(text, self.FEATS),
                         {"F1": "unknown", "F2": "use", "F3": "unknown", "F4": "unknown"})

    def test_mixed_sentence_is_unknown(self):
        # 한 문장에 쓸·안 쓸이 같이 있으면 어느 기능 답인지 못 가려서 unknown으로 둔다
        text = "공고 검색·필터는 쓸 것 같고 마감 알림은 안 쓸 것 같다"
        result = rs.parse_use_answers(text, self.FEATS)
        self.assertEqual((result["F1"], result["F3"]), ("unknown", "unknown"))


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
        # 11/9 김승하 리뷰: PC 경로(임시 폴더 이름)가 모델 입력과 기록에 안 들어간다. 실행기처럼 리포 기준 상대 경로
        self.assertNotIn(TMP.name, "".join(FAKE.prompts))
        self.assertEqual(report["images"], [f"images/fake/app/{s}" for s in ("S1.png", "S2.png", "S3.png")])

    def test_unexpected_error_still_writes_report(self):
        # 11/9 김승하 리뷰: 예상 못 한 오류가 나도 그 회차만 실패로 남기고 기록을 쓴다
        from unittest import mock
        from tinytroupe.agent import TinyPerson
        with mock.patch.object(TinyPerson, "listen_and_act", side_effect=ValueError("가짜 오류")):
            code, log, report = self.run_check("imgerr")
        self.assertEqual(code, rs.EXIT_API, log)
        self.assertEqual([(x["mode"], x["ok"]) for x in report["results"]], [("image", False), ("text", False)])
        self.assertIn("ValueError", report["results"][0]["error"])

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

"""AI 실행기 (TRD IF-05, FR-03). 1단계 뼈대.

페르소나마다 스냅샷의 화면과 과제를 주고, AI 응답과 실행 기록을 파일로 남긴다.
작업 범위는 docs/work-orders/kim-minwoo/AI실행기.md(11/1 개정판),
요구사항은 TRD FR-03, NFR-02/04/05/06, 6장 공통 규칙, 7장 실행 기록.

사용법:
    python scripts/use_provider.py gemini
    python scripts/run_simulation.py --service fake --platform app --condition 2 --repeat 1 --seed 1 \
        --config configs/simulation.dev.json --limit-personas 1

1단계라서 아직 안 하는 것
- 폼 B 질문 순서대로 묻기, 이미지 입력 다듬기, 질문 파일 읽기: 프로토콜 v0.1이 나오면 2단계에서 넣는다.
  지금은 과제마다 시작 화면 하나를 보여주고 한 번 행동하게 한다.
- 조건 3(후기 검색 붙이기): 후기 출처가 정해지면 넣는다. 지금은 종료 코드 1로 막는다.

종료 코드 (TRD 6장)
    0 정상 / 1 사용법 오류, 입력 파일 없음 / 2 설정 불일치, 인증
    3 비용 상한 / 4 입력 검증 실패 / 5 API 실패 (전부 실패했거나 실패율이 NFR-06 문턱을 넘을 때)
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = "configs/simulation.json"
GEMINI_HOST = "generativelanguage.googleapis.com"
PLATFORMS = ("app", "web")

EXIT_OK, EXIT_USAGE, EXIT_SETTINGS, EXIT_COST, EXIT_INPUT, EXIT_API = 0, 1, 2, 3, 4, 5

# NFR-04: 호출 1회 응답 토큰 상한. NFR-05: 동시 호출 상한.
MAX_COMPLETION_LIMIT = {"openai": 2048, "gemini": 8192}
CONCURRENCY_LIMIT = {"openai": 2, "gemini": 1}

# FR-03-01: 조건 0은 슬롯 C0-01~C0-10으로 돌린다 (다른 조건의 페르소나 10명과 호출 수를 맞춘다)
CONDITION0_SLOTS = 10

# NFR-06: 에피소드 실패율이 이 값을 넘으면 종료 코드 5
FAILURE_RATE_LIMIT = 0.05

# 시간 환산용. 대조 서비스 2 x 조건 4 x 페르소나 10 x 반복 3 x 플랫폼 2 (AI제시프로토콜.md 235행)
PLANNED_EPISODES = 480


class Stop(Exception):
    """검사에서 멈출 때 쓴다. 종료 코드와 이유를 들고 main까지 올라간다."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# 실행 도중 멈추는 신호들. 일부러 Exception이 아니라 BaseException을 상속한다.
# TinyTroupe send_message가 except Exception으로 오류를 전부 잡아 재시도한 뒤 None을 돌려주기 때문에,
# Exception으로 던지면 TinyTroupe 안에서 삼켜지고 빈 응답만 조용히 쌓인다.
# fatal이 True면 다음 에피소드도 같은 이유로 실패하니 실행 전체를 멈춘다.
class AbortRun(BaseException):
    code = EXIT_API
    label = "실패"
    fatal = False


class AuthFailed(AbortRun):
    code = EXIT_SETTINGS
    label = "실패(인증)"
    fatal = True


class SettingsFailed(AbortRun):
    code = EXIT_SETTINGS
    label = "실패(설정)"
    fatal = True


class CostCapReached(AbortRun):
    code = EXIT_COST
    label = "중단(비용 상한)"
    fatal = True


class ApiFailed(AbortRun):
    code = EXIT_API
    label = "실패(API)"


class _Parser(argparse.ArgumentParser):
    # argparse는 사용법 오류에 2를 내는데, TRD 표에서 2는 설정 불일치다. 1로 맞춘다.
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"[중단] {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def parse_args(argv):
    ap = _Parser(description="AI 실행기 (TRD IF-05)")
    ap.add_argument("--service", required=True)
    ap.add_argument("--platform", required=True, choices=PLATFORMS, help="캡처 플랫폼. 에이전트 하나에는 한 플랫폼 화면만 준다")
    ap.add_argument("--condition", required=True, type=int, choices=[0, 1, 2, 3])
    ap.add_argument("--repeat", required=True, type=int)
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--config", default=DEFAULT_CONFIG, help=f"실행 설정 JSON (기본 {DEFAULT_CONFIG})")
    ap.add_argument("--limit-personas", type=int, default=None, help="시범 실행용. 앞에서부터 N명(조건 0은 N슬롯)만 쓴다")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        ap.error("--repeat 는 1 이상이어야 한다")
    if args.limit_personas is not None and args.limit_personas < 1:
        ap.error("--limit-personas 는 1 이상이어야 한다")
    return args


# ---------------------------------------------------------------------------
# 입력 검사. 여기서 걸리면 아무것도 쓰지 않고 멈춘다 (TRD 6장 공통 규칙)
# ---------------------------------------------------------------------------

# 실행 설정 JSON의 필수 키와 타입. "_"로 시작하는 키는 설명용이라 무시한다.
CONFIG_KEYS = {
    "snapshot_root": (str,),
    "personas_dir": (str,),
    "images_root": (str, type(None)),
    "input_mode": (str,),
    "token_cap": (int,),
    "empty_retries": (int,),
    "max_actions_before_done": (int,),
    "neutral_agent_name": (str,),
    "cache": (bool,),
    "raw_responses_path": (str,),
    "meta_dir": (str,),
    "cache_dir": (str,),
    "protocol_version": (str, type(None)),
    "task_prompt_template": (str,),
}


def load_json(path: Path, what: str):
    if not path.is_file():
        raise Stop(EXIT_USAGE, f"{what} 파일이 없다: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise Stop(EXIT_INPUT, f"{what} 파일을 JSON으로 읽지 못했다: {path} ({e})")


def _type_ok(value, types):
    # bool은 int의 하위 클래스라서 따로 막는다. "token_cap": true 가 통과하면 안 된다.
    if isinstance(value, bool) and bool not in types:
        return False
    return isinstance(value, types)


def validate_config(cfg) -> list:
    if not isinstance(cfg, dict):
        return ["실행 설정의 최상위가 객체가 아니다"]
    problems = []
    for key, types in CONFIG_KEYS.items():
        if key not in cfg:
            problems.append(f"실행 설정에 {key} 가 없다")
        elif not _type_ok(cfg[key], types):
            problems.append(f"실행 설정 {key} 의 타입이 맞지 않다: {cfg[key]!r}")
    for key in cfg:
        if key not in CONFIG_KEYS and not key.startswith("_"):
            problems.append(f"실행 설정에 모르는 키가 있다: {key}")
    if problems:
        return problems

    if cfg["input_mode"] not in ("text", "image"):
        problems.append(f"input_mode 는 text 또는 image 여야 한다: {cfg['input_mode']!r}")
    if cfg["input_mode"] == "image" and not cfg["images_root"]:
        problems.append("input_mode 가 image 인데 images_root 가 비어 있다")
    if cfg["token_cap"] <= 0:
        problems.append("token_cap 은 1 이상이어야 한다")
    if not 0 <= cfg["empty_retries"] <= 5:
        problems.append("empty_retries 는 0~5 여야 한다")
    if cfg["max_actions_before_done"] < 1:
        problems.append("max_actions_before_done 은 1 이상이어야 한다 (기본값 15를 쓴다)")
    if not _nonempty_str(cfg["neutral_agent_name"]):
        problems.append("neutral_agent_name 이 비어 있다 (조건 0·1 에이전트 이름)")
    if "{task}" not in cfg["task_prompt_template"]:
        problems.append("task_prompt_template 에 {task} 자리가 없다")
    return problems


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate_snapshot(snap, service: str, platform: str, input_mode: str, images_dir) -> list:
    if not isinstance(snap, dict):
        return ["스냅샷의 최상위가 객체가 아니다"]
    problems = []
    if snap.get("service") != service:
        problems.append(f"스냅샷 service 가 {service!r} 가 아니다: {snap.get('service')!r}")
    if snap.get("platform") != platform:
        problems.append(f"스냅샷 platform 이 {platform!r} 가 아니다: {snap.get('platform')!r}")
    if not _nonempty_str(snap.get("snapshot_version")):
        problems.append("스냅샷에 snapshot_version 이 없다")

    screens = snap.get("screens")
    if not isinstance(screens, list) or not screens:
        problems.append("스냅샷 screens 가 비어 있거나 목록이 아니다")
        screens = []
    screen_ids = set()
    for i, s in enumerate(screens):
        if not isinstance(s, dict):
            problems.append(f"screens[{i}] 가 객체가 아니다")
            continue
        sid = s.get("screen_id")
        if not (isinstance(sid, str) and re.fullmatch(r"S\d+", sid)):
            problems.append(f"screens[{i}].screen_id 가 S숫자 형식이 아니다: {sid!r}")
            continue
        if sid in screen_ids:
            problems.append(f"screen_id 가 겹친다: {sid}")
        screen_ids.add(sid)
        if input_mode == "text" and not _nonempty_str(s.get("text")):
            problems.append(f"{sid}: 텍스트 입력인데 text 가 비어 있다")
        if input_mode == "image":
            img = s.get("image")
            if not _nonempty_str(img):
                problems.append(f"{sid}: 이미지 입력인데 image 가 비어 있다")
            elif images_dir is not None and not (images_dir / img).is_file():
                problems.append(f"{sid}: 화면 캡처 파일이 없다: {images_dir / img}")

    tasks = snap.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        problems.append("스냅샷 tasks 가 비어 있거나 목록이 아니다")
        tasks = []
    task_ids = set()
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            problems.append(f"tasks[{i}] 가 객체가 아니다")
            continue
        tid = t.get("task_id")
        if not (isinstance(tid, str) and re.fullmatch(r"T\d+", tid)):
            problems.append(f"tasks[{i}].task_id 가 T숫자 형식이 아니다: {tid!r}")
            continue
        if tid in task_ids:
            problems.append(f"task_id 가 겹친다: {tid}")
        task_ids.add(tid)
        if not _nonempty_str(t.get("text")):
            problems.append(f"{tid}: 과제 문구 text 가 비어 있다")
        if t.get("start_screen") not in screen_ids:
            problems.append(f"{tid}: start_screen 이 screens 에 없다: {t.get('start_screen')!r}")
    return problems


def persona_id_from_path(path: Path) -> str:
    # 임시 페르소나는 "S01_김지원.agent.json" 형식이다. 앞의 ID만 쓴다.
    stem = path.name
    for suffix in (".json", ".agent"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem.split("_")[0]


def load_personas(personas_dir: Path, limit):
    files = sorted(personas_dir.glob("*.json"))
    if limit is not None:
        files = files[:limit]
    problems, units, seen = [], [], set()
    if not files:
        problems.append(f"페르소나 파일이 없다: {personas_dir}")
    for path in files:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            problems.append(f"{path.name}: JSON으로 읽지 못했다 ({e})")
            continue
        persona = spec.get("persona") if isinstance(spec, dict) else None
        if not isinstance(spec, dict) or spec.get("type") != "TinyPerson" or not isinstance(persona, dict):
            problems.append(f"{path.name}: TinyPerson 형식이 아니다")
            continue
        if not _nonempty_str(persona.get("name")):
            problems.append(f"{path.name}: persona.name 이 없다")
        if not _type_ok(persona.get("age"), (int,)):
            problems.append(f"{path.name}: persona.age 가 정수가 아니다")
        occ = persona.get("occupation")
        if not (isinstance(occ, dict) and _nonempty_str(occ.get("title"))):
            problems.append(f"{path.name}: persona.occupation.title 이 없다 (조건 1에 필요)")
        pid = persona_id_from_path(path)
        if pid in seen:
            problems.append(f"페르소나 ID가 겹친다: {pid}")
        seen.add(pid)
        units.append({"persona_id": pid, "path": path, "spec": spec})
    return units, problems


def previous_tokens(meta_dir: Path, provider: str) -> int:
    """비용 상한은 본실험 전체 누적으로 센다. 같은 실행 기록 폴더에 남은 이전 에피소드의 토큰을 더한다.

    명령은 서비스 x 플랫폼 x 조건으로 나눠 도니까 명령마다 따로 세면 상한의 몇 배까지 쓸 수 있다.
    제공자가 다른 기록(예: 무료 Gemini로 돌린 개발 기록)은 이 예산에서 돈이 나가지 않아서 뺀다.
    """
    if not meta_dir.is_dir():
        return 0
    total, broken = 0, []
    for path in sorted(meta_dir.glob("*.json")):
        if path.name.endswith(".summary.json"):
            continue  # 요약은 에피소드 기록을 다시 더한 것이라 두 번 세게 된다
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            broken.append(path.name)
            continue
        if meta.get("provider") == provider:
            total += int(meta.get("tokens_in") or 0) + int(meta.get("tokens_out") or 0)
    if broken:
        # 못 읽은 기록을 빼고 세면 상한보다 더 쓸 수 있다. 고친 뒤에 다시 돌린다.
        raise Stop(EXIT_INPUT, f"이전 실행 기록을 읽지 못해서 누적 토큰을 셀 수 없다: {', '.join(broken)}")
    return total


# ---------------------------------------------------------------------------
# 설정 검사 (종료 코드 2)
# ---------------------------------------------------------------------------

def check_env(root: Path):
    from dotenv import load_dotenv

    # smoke_tinytroupe.py와 같은 이유로 override=True. 셸에 남은 OPENAI_* 가 .env를 가리면
    # 의도와 반대쪽(유료/무료)으로 호출이 나간다.
    load_dotenv(root / ".env", override=True)
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()

    if not api_key:
        raise Stop(EXIT_SETTINGS, "OPENAI_API_KEY 가 비어 있다. .env 나 환경변수에 넣어라.")
    if not (root / "config.ini").is_file():
        raise Stop(EXIT_SETTINGS, "config.ini 가 없다. 먼저 python scripts/use_provider.py gemini")
    if not base_url:
        provider = "openai"
    elif GEMINI_HOST in base_url:
        provider = "gemini"
    else:
        raise Stop(EXIT_SETTINGS, f"OPENAI_BASE_URL 이 OpenAI 기본 주소도 Gemini 도 아니다: {base_url}")
    return provider, base_url


def check_tinytroupe_settings(config_manager, provider: str):
    model = str(config_manager.get("model"))
    if ("gemini" in model.lower()) != (provider == "gemini"):
        raise Stop(
            EXIT_SETTINGS,
            f"config.ini 의 모델({model})과 OPENAI_BASE_URL({provider})이 어긋난다. "
            "python scripts/use_provider.py [openai|gemini] 로 맞춰라.",
        )
    mct = config_manager.get("max_completion_tokens")
    if mct is None or int(mct) > MAX_COMPLETION_LIMIT[provider]:
        raise Stop(
            EXIT_SETTINGS,
            f"MAX_COMPLETION_TOKENS={mct} 가 상한 {MAX_COMPLETION_LIMIT[provider]} 을 넘는다 (NFR-04)",
        )
    conc = config_manager.get("max_concurrent_model_calls")
    if conc is None or int(conc) > CONCURRENCY_LIMIT[provider]:
        raise Stop(
            EXIT_SETTINGS,
            f"MAX_CONCURRENT_MODEL_CALLS={conc} 가 상한 {CONCURRENCY_LIMIT[provider]} 을 넘는다 (NFR-05)",
        )
    return model, int(mct)


def tinytroupe_commit() -> str:
    """실행 기록용. 이 PC는 TinyTroupe/, 팀 README는 external/TinyTroupe 라서 import 위치에서 찾는다."""
    import tinytroupe

    repo = Path(tinytroupe.__file__).resolve().parents[1]
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15
        )
        if out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    # git이 없거나 폴더 소유자 검사(safe.directory)에 걸리면 .git 파일을 직접 읽는다
    try:
        head = (repo / ".git" / "HEAD").read_text().strip()
        if not head.startswith("ref:"):
            return head
        ref = head.split(" ", 1)[1]
        ref_file = repo / ".git" / ref
        if ref_file.is_file():
            return ref_file.read_text().strip()
        for line in (repo / ".git" / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# TinyTroupe 감싸기: 비용 상한, 인증 오류, 빈 응답, 호출 집계, 행동 목록 잘림
# ---------------------------------------------------------------------------

def _new_counts():
    return {
        "calls_real": 0,  # 실제 API 호출 (돈이 드는 것)
        "calls_cached": 0,  # 캐시에서 나온 응답
        "tokens_in": 0,
        "tokens_out": 0,
        "messages": 0,  # send_message 결과 수 (재시도 포함)
        "empty": 0,  # 그중 빈 응답 또는 실패(None)
        "length": 0,  # finish_reason=length
        "truncated": 0,  # 행동 목록이 MAX_ACTIONS_BEFORE_DONE보다 길어서 잘린 횟수
    }


class RunState:
    """이번 실행의 호출 집계. 아래 감싼 함수들이 여기에 쓴다."""

    def __init__(self, token_cap: int, empty_retries: int, tokens_before: int = 0):
        self.token_cap = token_cap
        self.empty_retries = empty_retries
        self.tokens_before = tokens_before  # 이전 실행에서 이미 쓴 토큰
        self.tokens_used = tokens_before  # 실제 호출만 센다. 캐시 응답은 돈이 안 든다
        self.totals = _new_counts()
        self.episode = _new_counts()

    def add(self, key, n=1):
        self.totals[key] += n
        self.episode[key] += n


_STATE = None
_GUARDS_INSTALLED = False


def _is_empty(result) -> bool:
    if result is None:
        return True
    if isinstance(result, dict):
        content = result.get("content")
        return content is None or (isinstance(content, str) and not content.strip())
    return False


def _is_auth_error(e) -> bool:
    import openai

    if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return True
    # Gemini 호환 주소는 틀린 키에 401 대신 400을 준다. 2026-11-04 틀린 키로 실제 호출해 보니
    # 400, INVALID_ARGUMENT, "Please pass a valid API key" 였다 (API_KEY_INVALID 표시는 없었다).
    # TinyTroupe는 400을 받으면 None을 돌려주므로, 여기서 못 가려내면 빈 응답 재시도 뒤 종료 코드 5로 끝난다.
    if isinstance(e, openai.BadRequestError):
        text = f"{e} {getattr(e, 'body', '')}"
        return any(s in text for s in ("valid API key", "API key not valid", "API_KEY_INVALID"))
    return False


def install_guards():
    """한 프로세스에서 한 번만 감싼다. 감싼 함수는 모듈 전역 _STATE를 본다."""
    global _GUARDS_INSTALLED
    if _GUARDS_INSTALLED:
        return
    import openai
    from tinytroupe.agent import TinyPerson
    from tinytroupe.agent.action_generator import ActionGenerator
    from tinytroupe.clients.openai_client import OpenAIClient

    orig_raw = OpenAIClient._raw_model_call
    orig_update = OpenAIClient._update_cost_stats
    orig_send = OpenAIClient.send_message
    orig_generate = ActionGenerator.generate_next_actions

    def guarded_raw(self, model, chat_api_params):
        st = _STATE
        # 상한은 다음 실제 호출 전에 본다. 그래서 마지막 호출 하나만큼은 넘을 수 있다.
        if st is not None and st.tokens_used >= st.token_cap:
            raise CostCapReached(
                f"누적 토큰 {st.tokens_used:,}(이전 실행 {st.tokens_before:,} 포함)이 상한 {st.token_cap:,} 에 닿았다"
            )
        # Gemini 호환 주소는 frequency/presence_penalty를 400으로 거부한다 (FINDINGS 3번, run_smoke.py와 같은 처리)
        base_url = os.getenv("OPENAI_BASE_URL") or ""
        if base_url and "openai.com" not in base_url:
            chat_api_params.pop("frequency_penalty", None)
            chat_api_params.pop("presence_penalty", None)
        try:
            return orig_raw(self, model, chat_api_params)
        except Exception as e:
            if _is_auth_error(e):
                # 오류 문구에 키 일부가 섞여 나올 수 있어서 종류만 남긴다
                raise AuthFailed(f"인증 오류 ({type(e).__name__})") from None
            if isinstance(e, openai.NotFoundError):
                # 모델 이름이 없어졌거나 틀린 경우. 다시 물어도 같아서 설정 오류로 바로 멈춘다.
                # (2026-11-01 새 Gemini 키로 gemini-2.5-flash를 부르자 404가 왔다)
                raise SettingsFailed(f"모델을 찾지 못했다 ({model}). config.ini 의 MODEL 을 확인해라") from None
            raise

    def counting_update(self, response, was_cached):
        orig_update(self, response, was_cached)
        st = _STATE
        if st is None:
            return
        usage = getattr(response, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        if was_cached:
            st.add("calls_cached")
        else:
            st.add("calls_real")
            st.add("tokens_in", tokens_in)
            st.add("tokens_out", tokens_out)
            st.tokens_used += tokens_in + tokens_out
        try:
            if response.choices[0].finish_reason == "length":
                st.add("length")
        except Exception:
            pass

    def checked_send(self, *args, **kwargs):
        st = _STATE
        attempts = 1 + (st.empty_retries if st is not None else 0)
        for _ in range(attempts):
            result = orig_send(self, *args, **kwargs)
            if st is not None:
                st.add("messages")
            if not _is_empty(result):
                return result
            if st is not None:
                st.add("empty")
            # 빈 응답이 캐시에 들어가 있으면 다시 물어도 같은 빈 응답이 나온다. 지우고 다시 묻는다.
            self.invalidate_last_cache_entry()
        raise ApiFailed(f"빈 응답 또는 API 실패 ({attempts}번 시도)")

    def counting_generate(self, agent, current_messages):
        # TinyTroupe는 행동 목록이 상한보다 길면 앞부분만 남기고 마지막을 DONE으로 바꾸면서 로그를 안 남긴다
        # (tiny_person.py 872~875행). 잘리면 답(TALK)이 사라질 수 있어서 여기서 센다.
        result = orig_generate(self, agent, current_messages)
        st = _STATE
        actions = result[0] if isinstance(result, tuple) and result else None
        if st is not None and isinstance(actions, list) and len(actions) > TinyPerson.MAX_ACTIONS_BEFORE_DONE:
            st.add("truncated")
        return result

    OpenAIClient._raw_model_call = guarded_raw
    OpenAIClient._update_cost_stats = counting_update
    OpenAIClient.send_message = checked_send
    ActionGenerator.generate_next_actions = counting_generate
    _GUARDS_INSTALLED = True


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def _rel(path: Path, root: Path) -> str:
    """기록에는 리포 기준 경로를 남긴다. 설정에서 리포 밖 경로를 주면 그대로 남긴다."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def hangul_ratio(text: str) -> float:
    """공백, 숫자, 구두점을 뺀 글자 중 한글 비율 (run_smoke.py와 같은 정의)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ko = sum(1 for c in letters if "가" <= c <= "힣" or "ㄱ" <= c <= "ㆎ")
    return ko / len(letters)


def build_agent(condition: int, unit: dict, neutral_name: str):
    from tinytroupe.agent import TinyPerson

    # 에피소드마다 새 에이전트를 만든다. 같은 에이전트를 다시 쓰면 이전 에피소드가 기억 앞부분에 남고,
    # 같은 이름으로 다시 만들면 TinyTroupe가 "이미 쓰는 이름" 오류를 낸다. 그래서 등록부터 비운다.
    TinyPerson.clear_agents()
    if condition == 0:
        # FR-03-01: 페르소나 없이 같은 과제. 이름은 조건 0·1 공통 중립 이름 (프로토콜 7번)
        return TinyPerson(name=neutral_name)
    persona = unit["spec"]["persona"]
    if condition == 1:
        # FR-03-02: 나이와 직업만 남긴다. 한국 이름은 성별 단서라서 중립 이름으로 바꾼다.
        spec = {
            "type": "TinyPerson",
            "persona": {
                "name": neutral_name,
                "age": persona["age"],
                "occupation": {"title": persona["occupation"]["title"]},
            },
        }
        return TinyPerson.load_specification(spec)
    # 조건 2: Nemotron 페르소나 필드 그대로
    return TinyPerson.load_specification(json.loads(json.dumps(unit["spec"])))


def make_step(task: dict, screen: dict, actions) -> dict:
    raw = []
    for a in actions or []:
        act = a.get("action", {}) if isinstance(a, dict) else {}
        raw.append({"type": act.get("type"), "content": act.get("content"), "target": act.get("target")})
    think = "\n".join(x["content"] for x in raw if x["type"] == "THINK" and x["content"])
    talk = "\n".join(x["content"] for x in raw if x["type"] == "TALK" and x["content"])
    return {
        "task_id": task["task_id"],
        "screen_shown": screen["screen_id"],
        "actions": raw,  # AI 행동 원문
        "think": think,
        "talk": talk,
    }


def run_episode(ctx: dict, unit: dict, repeat: int):
    from tinytroupe.clients import force_api_cache

    st = _STATE
    st.episode = _new_counts()
    pid = unit["persona_id"]
    run_id = f"{ctx['batch_id']}_{pid}_r{repeat}"

    cache_file = None
    if ctx["cfg"]["cache"]:
        # FR-03-05: 서비스 x 플랫폼 x 조건 x 페르소나(조건 0은 슬롯) x 회차마다 캐시를 따로 쓴다.
        # 같이 쓰면 TinyTroupe가 같은 요청에 같은 답을 돌려줘서 반복이 전부 똑같아진다.
        # force_api_cache는 모든 클라이언트에 걸리는 전역 설정이라 에피소드마다 다시 지정하고 순서대로 돈다.
        group = f"{ctx['service']}_{ctx['platform']}_c{ctx['condition']}_{ctx['model_tag']}"
        cache_file = ctx["cache_dir"] / group / f"{pid}_r{repeat}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        force_api_cache(True, str(cache_file))
    else:
        force_api_cache(False)

    started = time.time()
    steps, abort, error_detail = [], None, None
    try:
        agent = build_agent(ctx["condition"], unit, ctx["cfg"]["neutral_agent_name"])
        for task in ctx["tasks"]:
            screen = ctx["screens"][task["start_screen"]]
            # 프로토콜 2번: 화면별 기능 설명(feature_description)은 사람이 못 보는 정보라 넣지 않는다
            if ctx["input_mode"] == "text":
                agent.see(description=screen["text"])
            else:
                agent.see(images=[str(ctx["images_dir"] / screen["image"])])
            prompt = ctx["cfg"]["task_prompt_template"].replace("{task}", task["text"])
            actions = agent.listen_and_act(prompt, return_actions=True, communication_display=False)
            steps.append(make_step(task, screen, actions))
    except AbortRun as e:
        abort = e
    except Exception as e:
        # TinyTroupe 안에서 예상 못 한 오류. 원인을 볼 수 있게 기록에 남기고 실패로 친다.
        abort = ApiFailed(f"예상 못 한 오류 ({type(e).__name__}: {e})")
        error_detail = traceback.format_exc()
    elapsed = round(time.time() - started, 1)

    status = "성공" if abort is None else f"{abort.label}: {abort}"
    meta = {
        # TRD 7장 실행 기록 13칸 (platform은 TRD v0.3에 추가)
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "provider": ctx["provider"],
        "base_url": ctx["base_url"] or None,
        "model": ctx["model"],
        "tinytroupe_commit": ctx["tinytroupe_commit"],
        "service": ctx["service"],
        "platform": ctx["platform"],
        "condition": ctx["condition"],
        "persona_id": pid,
        "repeat": repeat,
        "seed": ctx["seed"],
        "input_mode": ctx["input_mode"],
        "cache_file": _rel(cache_file, ctx["root"]) if cache_file else None,
        "max_completion_tokens": ctx["max_completion_tokens"],
        "tokens_in": st.episode["tokens_in"],
        "tokens_out": st.episode["tokens_out"],
        "elapsed_sec": elapsed,
        "status": status,
        # AI실행기.md에서 더하기로 한 칸 (TRD v0.3에 들어감)
        "protocol_version": ctx["cfg"]["protocol_version"],
        "snapshot_version": ctx["snapshot_version"],
        "action_truncations": st.episode["truncated"],
        # 아래는 이 구현에서 더한 칸 (TRD 6장: 입력 파일 경로와 설정을 남긴다)
        "batch_id": ctx["batch_id"],
        "calls_real": st.episode["calls_real"],
        "calls_cached": st.episode["calls_cached"],
        "empty_responses": st.episode["empty"],
        "length_cutoffs": st.episode["length"],
        "max_actions_before_done": ctx["cfg"]["max_actions_before_done"],
        "neutral_agent_name": ctx["cfg"]["neutral_agent_name"] if ctx["condition"] in (0, 1) else None,
        "config_file": ctx["config_file"],
        "snapshot_file": ctx["snapshot_file"],
        "persona_file": _rel(unit["path"], ctx["root"]) if "path" in unit else None,
    }
    if error_detail:
        meta["error_detail"] = error_detail
    ctx["meta_dir"].mkdir(parents=True, exist_ok=True)
    (ctx["meta_dir"] / f"{run_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if abort is None:
        # 한 줄 = 한 에피소드 (서비스 x 플랫폼 x 조건 x 페르소나 x 회차). 실패한 에피소드는 실행 기록에만 남긴다.
        # 형식은 2단계에서 프로토콜 10번에 맞춰 질문 단위(answers)로 바꾼다.
        line = {
            "run_id": run_id,
            "batch_id": ctx["batch_id"],
            "service": ctx["service"],
            "platform": ctx["platform"],
            "condition": ctx["condition"],
            "persona_id": pid,
            "repeat": repeat,
            "protocol_version": ctx["cfg"]["protocol_version"],
            "snapshot_version": ctx["snapshot_version"],
            "input_mode": ctx["input_mode"],
            "status": "성공",
            "steps": steps,
        }
        ctx["raw_path"].parent.mkdir(parents=True, exist_ok=True)
        with ctx["raw_path"].open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    text = "\n".join(s["think"] + "\n" + s["talk"] for s in steps)
    return {"run_id": run_id, "ok": abort is None, "elapsed": elapsed, "text": text, "abort": abort}


def decide_exit_code(episodes: list, fatal) -> int:
    if fatal is not None:
        return fatal.code
    failed = sum(1 for e in episodes if not e["ok"])
    if episodes and (failed == len(episodes) or failed / len(episodes) > FAILURE_RATE_LIMIT):
        return EXIT_API
    return EXIT_OK


def summarize(ctx: dict, episodes: list, exit_code: int) -> dict:
    st = _STATE
    t = st.totals
    ok = [e for e in episodes if e["ok"]]
    responses = t["calls_real"] + t["calls_cached"]
    all_text = "\n".join(e["text"] for e in ok)
    per_episode = [hangul_ratio(e["text"]) for e in ok]
    elapsed = round(sum(e["elapsed"] for e in episodes), 1)
    sec_per_episode = round(sum(e["elapsed"] for e in ok) / len(ok), 1) if ok else None

    def rate(n, d):
        return round(n / d, 3) if d else None

    return {
        "batch_id": ctx["batch_id"],
        "service": ctx["service"],
        "platform": ctx["platform"],
        "condition": ctx["condition"],
        "seed": ctx["seed"],
        "provider": ctx["provider"],
        "model": ctx["model"],
        "input_mode": ctx["input_mode"],
        "exit_code": exit_code,
        "episodes_planned": ctx["episodes_planned"],
        "episodes_run": len(episodes),
        "episodes_ok": len(ok),
        "calls_real": t["calls_real"],
        "calls_cached": t["calls_cached"],
        "tokens_in": t["tokens_in"],
        "tokens_out": t["tokens_out"],
        "tokens_total": t["tokens_in"] + t["tokens_out"],
        "tokens_before": st.tokens_before,
        "tokens_cumulative": st.tokens_used,
        "token_cap": st.token_cap,
        "failure_rate": rate(len(episodes) - len(ok), len(episodes)),
        "empty_rate": rate(t["empty"], t["messages"]),
        "length_cutoff_rate": rate(t["length"], responses),
        "action_truncations": t["truncated"],
        "hangul_ratio": round(hangul_ratio(all_text), 3) if ok else None,
        "hangul_ratio_min_episode": round(min(per_episode), 3) if per_episode else None,
        "elapsed_sec": elapsed,
        "sec_per_episode": sec_per_episode,
        # NFR-05 참고용: 계획한 에피소드 전체를 지금 속도로 순서대로 돌리면 걸릴 시간. 캐시 응답이면 의미 없다
        "hours_for_planned_episodes": (
            round(sec_per_episode * PLANNED_EPISODES / 3600, 1) if sec_per_episode and t["calls_real"] else None
        ),
    }


def print_summary(s: dict) -> None:
    # 프로토콜 시범 실행 규칙: 실제 스냅샷 시범의 응답 내용은 정답지 정리자, 판정자가 보면 안 된다.
    # 그래서 화면에는 숫자만 찍는다.
    def pct(v):
        return "-" if v is None else f"{v * 100:.1f}%"

    print("=" * 60)
    print(f"[요약] {s['batch_id']}  종료 코드 {s['exit_code']}")
    print(f"  에피소드     : 성공 {s['episodes_ok']} / 실행 {s['episodes_run']} / 계획 {s['episodes_planned']}")
    print(f"  호출         : 실제 {s['calls_real']}회, 캐시 {s['calls_cached']}회")
    print(f"  토큰         : 이번 {s['tokens_total']:,} (입력 {s['tokens_in']:,} + 출력 {s['tokens_out']:,})")
    print(f"  누적 토큰    : {s['tokens_cumulative']:,} / 상한 {s['token_cap']:,} (이전 실행 {s['tokens_before']:,})")
    print(f"  실패 비율    : {pct(s['failure_rate'])} (NFR-06 문턱 {FAILURE_RATE_LIMIT * 100:.0f}%)")
    print(f"  빈 응답 비율 : {pct(s['empty_rate'])}")
    print(f"  길이 초과    : {pct(s['length_cutoff_rate'])} (finish_reason=length)")
    print(f"  행동 잘림    : {s['action_truncations']}회")
    print(f"  한글 비율    : 전체 {pct(s['hangul_ratio'])}, 에피소드 최저 {pct(s['hangul_ratio_min_episode'])}")
    per_ep = "-" if s["sec_per_episode"] is None else f"{s['sec_per_episode']}초"
    print(f"  걸린 시간    : {s['elapsed_sec']}초, 에피소드 평균 {per_ep}")
    if s["hours_for_planned_episodes"] is not None:
        print(f"  {PLANNED_EPISODES}에피소드 환산: {s['hours_for_planned_episodes']}시간 (순서대로 돌릴 때)")
    print("=" * 60)


def run(args, root: Path) -> int:
    global _STATE

    if args.condition == 3:
        raise Stop(EXIT_USAGE, "조건 3(후기 검색)은 아직 자리만 있다. 후기 출처가 정해진 뒤 넣는다 (FR-03-03)")

    # --- 입력 검사 (여기까지는 아무것도 쓰지 않는다) ---
    config_path = root / args.config
    cfg = load_json(config_path, "실행 설정")
    problems = validate_config(cfg)
    if problems:
        raise Stop(EXIT_INPUT, "실행 설정 검증 실패\n  - " + "\n  - ".join(problems))

    # 앱과 웹은 화면이 달라서 스냅샷도 플랫폼마다 따로 둔다
    snapshot_path = root / cfg["snapshot_root"] / args.service / args.platform / "snapshot.json"
    snap = load_json(snapshot_path, "스냅샷")
    images_dir = root / cfg["images_root"] / args.service / args.platform if cfg["images_root"] else None
    problems = validate_snapshot(snap, args.service, args.platform, cfg["input_mode"], images_dir)

    personas_dir = root / cfg["personas_dir"].replace("{service}", args.service)
    if not personas_dir.is_dir():
        raise Stop(EXIT_USAGE, f"페르소나 폴더가 없다: {personas_dir}")
    personas, persona_problems = load_personas(personas_dir, args.limit_personas)
    problems += persona_problems
    if problems:
        raise Stop(EXIT_INPUT, "입력 검증 실패\n  - " + "\n  - ".join(problems))

    if args.condition == 0:
        n_slots = min(CONDITION0_SLOTS, args.limit_personas or CONDITION0_SLOTS)
        units = [{"persona_id": f"C0-{i:02d}"} for i in range(1, n_slots + 1)]
    else:
        units = personas

    # --- 설정 검사 ---
    provider, base_url = check_env(root)
    tokens_before = previous_tokens(root / cfg["meta_dir"], provider)
    os.chdir(root)  # TinyTroupe는 import 시점에 현재 폴더의 config.ini를 읽는다
    import tinytroupe  # noqa: F401
    from tinytroupe import config_manager
    from tinytroupe.agent import TinyPerson

    model, max_completion_tokens = check_tinytroupe_settings(config_manager, provider)

    install_guards()
    # 기본값 15를 그대로 쓴다. 3으로 낮추면 [THINK, THINK, TALK, DONE]이 [THINK, THINK, DONE]이 돼서 답이 사라진다.
    # (TRD FR-03-07의 "호출 3회"는 TRD v0.3에서 고친다)
    TinyPerson.MAX_ACTIONS_BEFORE_DONE = cfg["max_actions_before_done"]
    # 응답 내용이 화면에 찍히지 않게 한다 (print_summary 주석 참고)
    TinyPerson.communication_display = False

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    batch_id = f"{args.service}_{args.platform}_c{args.condition}_{stamp}_{secrets.token_hex(2)}"
    ctx = {
        "root": root,
        "cfg": cfg,
        "service": args.service,
        "platform": args.platform,
        "condition": args.condition,
        "seed": args.seed,  # 지금은 기록만 한다. TinyTroupe가 API에 seed를 넘기지 않는다
        "batch_id": batch_id,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "model_tag": re.sub(r"[^A-Za-z0-9.-]+", "_", model),
        "max_completion_tokens": max_completion_tokens,
        "tinytroupe_commit": tinytroupe_commit(),
        "input_mode": cfg["input_mode"],
        "images_dir": images_dir,
        "snapshot_version": snap["snapshot_version"],
        "screens": {s["screen_id"]: s for s in snap["screens"]},
        "tasks": snap["tasks"],
        "config_file": _rel(config_path, root),
        "snapshot_file": _rel(snapshot_path, root),
        "raw_path": root / cfg["raw_responses_path"],
        "meta_dir": root / cfg["meta_dir"],
        "cache_dir": root / cfg["cache_dir"],
        "episodes_planned": len(units) * args.repeat,
    }
    _STATE = RunState(cfg["token_cap"], cfg["empty_retries"], tokens_before)

    print(f"[실행] {batch_id}: {provider}/{model}, {args.platform}, 조건 {args.condition}, "
          f"{'슬롯' if args.condition == 0 else '페르소나'} {len(units)} x 반복 {args.repeat}, 과제 {len(ctx['tasks'])}개")

    episodes, fatal = [], None
    for unit in units:
        for repeat in range(1, args.repeat + 1):
            ep = run_episode(ctx, unit, repeat)
            episodes.append(ep)
            print(f"  {ep['run_id']}: {'성공' if ep['ok'] else ep['abort'].label} ({ep['elapsed']}초)")
            if ep["ok"]:
                continue
            if ep["abort"].fatal:
                # 인증, 설정, 비용 상한은 다음 에피소드도 같은 이유로 막힌다. 바로 멈춘다.
                fatal = ep["abort"]
                print(f"[중단] {ep['abort']}", file=sys.stderr)
                break
            # 그 밖의 실패는 실행 기록에 남기고 다음 에피소드로 간다. 종료 코드는 끝에서 실패율로 정한다.
            print(f"[실패] {ep['abort']} (다음 에피소드로 넘어간다)", file=sys.stderr)
        if fatal is not None:
            break

    exit_code = decide_exit_code(episodes, fatal)
    summary = summarize(ctx, episodes, exit_code)
    ctx["meta_dir"].mkdir(parents=True, exist_ok=True)
    (ctx["meta_dir"] / f"{batch_id}.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print_summary(summary)
    return exit_code


def main(argv=None, root: Path = ROOT) -> int:
    args = parse_args(argv)
    try:
        return run(args, Path(root))
    except Stop as e:
        print(f"[중단] {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    raise SystemExit(main())

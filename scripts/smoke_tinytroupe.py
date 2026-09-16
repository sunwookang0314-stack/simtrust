"""TinyTroupe 최소 동작 확인(스모크 테스트).

목적은 두 가지다.
1) 지금 설정(config.ini + .env)으로 실제 호출이 되는지 확인한다.
2) 한국어로 기획안을 물었을 때 가상 사용자가 답을 하는지 본다.

호출을 최소로 묶어뒀다. 1단계는 한 줄 응답 확인이고, 2단계에서만 에이전트를 쓴다.
결과와 실행 메타데이터(제공자, 모델, 커밋 해시, 비용)는 runs/ 아래 JSON 으로 남긴다.
메타데이터를 남기는 이유는 나중에 어떤 결과가 무료 제공자로 돌린 것인지 구분하기 위해서다.

사용법:
    python scripts/use_provider.py gemini   # 또는 openai
    python scripts/smoke_tinytroupe.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

# TinyTroupe 는 "현재 작업 폴더"의 config.ini 를 읽는다. 그래서 import 전에 폴더를 옮긴다.
os.chdir(ROOT)

# override=True 가 중요하다. 셸에 이미 OPENAI_* 가 떠 있으면 .env 가 무시돼서
# 의도와 반대쪽(유료/무료)으로 호출이 나갈 수 있다.
load_dotenv(ROOT / ".env", override=True)

# API 캐시 파일이 runs/ 아래에 저장되는데, 폴더가 없으면 호출에 성공하고도
# 캐시 저장에서 죽는다. 호출 전에 미리 만들어둔다.
(ROOT / "runs").mkdir(exist_ok=True)

API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
BASE_URL = (os.getenv("OPENAI_BASE_URL") or "").strip()
GEMINI_HOST = "generativelanguage.googleapis.com"

if not API_KEY:
    print("[중단] .env 의 OPENAI_API_KEY 가 비어 있다.")
    print("       Gemini 키: https://aistudio.google.com/apikey")
    print("       OpenAI 키: https://platform.openai.com/api-keys")
    raise SystemExit(2)

if not (ROOT / "config.ini").exists():
    print("[중단] config.ini 가 없다. 먼저 제공자를 골라라.")
    print("       python scripts/use_provider.py gemini")
    raise SystemExit(2)

PROVIDER = "gemini" if GEMINI_HOST in BASE_URL else "openai"

# 실제 기획안 대신 쓰는 예시. 사람 데이터가 아니라서 무료 제공자로 보내도 된다.
PLAN = """
[서비스 기획안] 대학생 스터디 모집 앱

- 학교 이메일로 가입한다. 인증 메일을 받아야 가입이 완료된다.
- 스터디를 만들 때 요일, 시간, 장소, 인원, 목표를 입력한다.
- 참여 신청을 하면 개설자가 수락해야 확정된다.
- 무단 결석이 3회 쌓이면 다음 학기까지 신규 신청이 막힌다.
- 스터디가 끝나면 서로를 5점 만점으로 평가한다. 평균 3점 미만이면 프로필에 경고 표시가 붙는다.
"""

QUESTION = """위 기획안을 읽고 아래 세 가지에 답해줘.
1) 이 서비스를 실제로 쓸 것 같은지, 쓴다면/안 쓴다면 이유는 무엇인지
2) 가입부터 스터디 참여까지 과정에서 불편하거나 걱정되는 점
3) 기획안에 안 적혀 있어서 궁금한 점

당신의 상황과 성향에 비추어 구체적으로 답해줘. 좋은 말만 하지 말고 걸리는 점을 솔직히 말해줘."""


def git_commit(path: Path) -> str:
    """재현성 기록용. 실패해도 스모크 자체는 계속 진행한다."""
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def package_version(name: str) -> str:
    """tinytroupe 는 __version__ 속성이 없어서 메타데이터에서 읽는다."""
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return "unknown"


def main() -> int:
    started = time.time()

    import tinytroupe  # noqa: F401  (import 시점에 config 를 읽고 배너를 출력한다)
    from tinytroupe import config_manager
    from tinytroupe.agent import TinyPerson
    from tinytroupe.clients import client

    model = config_manager.get("model")

    # 제공자와 모델이 어긋나면 여기서 멈춘다. 이걸 안 막으면
    # 유료 키가 구글 엔드포인트로 나가거나 그 반대가 된다.
    model_is_gemini = "gemini" in str(model).lower()
    if model_is_gemini != (PROVIDER == "gemini"):
        print("[중단] config.ini 의 모델과 .env 의 base_url 이 어긋난다.")
        print(f"       모델    : {model}")
        print(f"       base_url: {BASE_URL or '(기본 OpenAI 주소)'}")
        print("       python scripts/use_provider.py [openai|gemini] 로 맞춰라.")
        return 2

    # 기본값이 15라서 listen_and_act 한 번이 최대 15회 호출로 번질 수 있다.
    # listen_and_act 는 호출 수 인자를 안 받으므로 클래스 속성으로 조인다.
    TinyPerson.MAX_ACTIONS_BEFORE_DONE = 3

    print("=" * 60)
    print(f"제공자   : {PROVIDER}")
    print(f"base_url : {BASE_URL or '(기본 OpenAI 주소)'}")
    print(f"모델     : {model}")
    print(f"응답상한 : {config_manager.get('max_completion_tokens')} 토큰")
    print(f"캐시     : {config_manager.get('cache_api_calls')}")
    print("=" * 60)

    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "provider": PROVIDER,
        "base_url": BASE_URL or None,
        "model": model,
        "max_completion_tokens": config_manager.get("max_completion_tokens"),
        "tinytroupe_version": package_version("tinytroupe"),
        "tinytroupe_commit": git_commit(ROOT / "external" / "TinyTroupe"),
        "python": sys.version.split()[0],
    }

    # --- 1단계: 연결 확인. 제일 싼 호출 하나로 끝낸다 ---
    print("\n[1단계] 연결 확인")
    try:
        resp = client().send_message(
            [{"role": "user", "content": "'연결 확인 완료'라고만 한국어로 답해줘."}]
        )
    except Exception as e:
        print(f"  [실패] {type(e).__name__}: {e}")
        result["stage1"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        save(result, started, None)
        return 1

    # send_message 는 실패해도 예외 대신 None 을 돌려준다.
    # 여기서 안 걸러내면 실패한 실행이 성공으로 기록된다.
    text = resp.get("content") if isinstance(resp, dict) else None
    if not text:
        print(f"  [실패] 응답이 비어 있다. 원본: {resp!r}")
        print("         빈 응답이면 MAX_COMPLETION_TOKENS 를 먼저 의심해라.")
        result["stage1"] = {"ok": False, "error": f"empty response: {resp!r}"}
        save(result, started, client())
        return 1

    print(f"  응답: {text}")
    result["stage1"] = {"ok": True, "response": text}

    # --- 2단계: 가상 사용자에게 한국어로 기획안 물어보기 ---
    print("\n[2단계] 가상 사용자에게 기획안 질문 (한국어)")
    try:
        from tinytroupe.examples.agents import create_lisa_the_data_scientist

        agent = create_lisa_the_data_scientist()
        actions = agent.listen_and_act(PLAN + "\n" + QUESTION, return_actions=True)

        # act() 는 [{"action": {...}, "cognitive_state": {...}}, ...] 를 돌려준다
        said = []
        for a in actions or []:
            action = a.get("action", {}) if isinstance(a, dict) else {}
            if action.get("type") in ("TALK", "THINK") and action.get("content"):
                said.append({"type": action["type"], "content": action["content"]})

        result["stage2"] = {"ok": True, "agent": agent.name, "utterances": said}
        print(f"  에이전트: {agent.name}")
        print(f"  발화 수: {len(said)}")
        if not said:
            print("  [주의] 발화가 하나도 없다. 응답 상한이나 모델 호환을 확인해라.")
    except Exception as e:
        print(f"  [실패] {type(e).__name__}: {e}")
        result["stage2"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        save(result, started, client())
        return 1

    save(result, started, client())
    return 0


def save(result: dict, started: float, api_client) -> None:
    result["elapsed_sec"] = round(time.time() - started, 1)

    # 이번 실행에서 토큰을 얼마나 썼는지 같이 남긴다.
    # 차터 KPI 의 "실행 비용 자동 기록" 이 이 항목이다.
    if api_client is not None:
        try:
            result["cost_stats"] = api_client.get_cost_stats()
        except Exception as e:
            result["cost_stats"] = f"수집 실패: {type(e).__name__}"

    out_dir = ROOT / "runs"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"smoke_{result['provider']}_{stamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n[저장] {path}")
    print(f"[소요] {result['elapsed_sec']}초")
    if "cost_stats" in result:
        print(f"[사용량] {result['cost_stats']}")


if __name__ == "__main__":
    raise SystemExit(main())

"""실행에 쓸 모델 제공자를 고른다.

사용법:
    python scripts/use_provider.py openai   # 유료. 최종 실험 수치용
    python scripts/use_provider.py gemini   # 무료. 개발/디버깅용

TinyTroupe 는 실행 폴더의 config.ini 를 읽으므로, config.<provider>.ini 를
config.ini 로 복사하는 방식으로 제공자를 바꾼다.

중요: .env 의 OPENAI_BASE_URL 과 고른 제공자가 어긋나면 **복사하지 않고 중단한다.**
경고만 하고 복사해두면, 그 경고를 무시한 다음 실행에서 유료 키가 구글 엔드포인트로
나가거나 그 반대가 된다. 그래서 검사를 먼저 하고 통과할 때만 바꾼다.
"""

import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
GEMINI_HOST = "generativelanguage.googleapis.com"


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("openai", "gemini"):
        print("사용법: python scripts/use_provider.py [openai|gemini]")
        return 1

    provider = sys.argv[1]
    src = ROOT / f"config.{provider}.ini"
    if not src.exists():
        print(f"[오류] 설정 파일이 없다: {src}")
        return 1

    env = dotenv_values(ROOT / ".env")
    base_url = (env.get("OPENAI_BASE_URL") or "").strip()
    api_key = (env.get("OPENAI_API_KEY") or "").strip()

    print(f"[.env] OPENAI_API_KEY  : {'설정됨' if api_key else '비어 있음'}")
    print(f"[.env] OPENAI_BASE_URL : {base_url or '(없음 = OpenAI 기본 주소)'}")

    # --- 검사 먼저. 어긋나면 config.ini 를 건드리지 않는다 ---
    if provider == "gemini" and GEMINI_HOST not in base_url:
        print("\n[중단] gemini 설정인데 OPENAI_BASE_URL 이 제미나이를 가리키지 않는다.")
        print("       config.ini 는 바꾸지 않았다. .env 에 아래 두 줄을 넣어라.")
        print("       OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/")
        print("       OPENAI_API_KEY=<https://aistudio.google.com/apikey 에서 발급>")
        return 2

    if provider == "openai" and base_url:
        print("\n[중단] openai 설정인데 OPENAI_BASE_URL 이 남아 있다.")
        print("       config.ini 는 바꾸지 않았다. 그대로 두면 유료 키가 그 주소로 나간다.")
        print("       .env 에서 OPENAI_BASE_URL 줄을 지우거나 주석 처리해라.")
        return 2

    # --- 검사 통과. 이제 바꾼다 ---
    shutil.copyfile(src, ROOT / "config.ini")
    print(f"\n[적용] {src.name} -> config.ini")

    if not api_key:
        print("[경고] OPENAI_API_KEY 가 비어 있어서 실제 호출은 실패한다.")
        return 2

    print("[확인] 설정과 .env 가 일치한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

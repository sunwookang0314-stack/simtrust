"""이미지 입력 확인 (AI실행기.md 1-b, AI 제시 프로토콜 3번 1단계).

가짜 화면을 이미지로 줄 때와 텍스트(화면 설명)로 줄 때 AI가 화면 글자를 맞게 말하는지 비교한다.
프로토콜 3번에서 정한 설정을 그대로 쓴다.
- 자동 영어 요약(_describe_images)은 끈다. 사람은 못 받는 해석 문장이라서다
- 이전 화면 다시 보여주기 수는 1 (MAX_IMAGE_STIMULI_TO_RECALL)
- 캡처는 see() 한 번에 묶어서 준다
요청 한 번에 들어간 이미지 장수도 센다. 이미지 처리 코드는 2단계에서 실행기로 옮긴다.

실행 (리포 루트):
    python scripts/use_provider.py gemini
    python scripts/check_image_input.py --service fake --platform app

가짜 화면만 쓴다. 실제 캡처나 참여자 응답은 넣지 않는다.
종료 코드는 실행기와 같다 (0 정상, 1 사용법, 2 설정·인증, 3 비용 상한, 5 API 실패).
"""

import argparse
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_simulation as rs  # noqa: E402

QUESTION = (
    "방금 본 화면들에 적힌 글자를 화면마다 빠짐없이 그대로 적어 주세요. "
    "버튼, 탭, 메뉴, 목록에 보이는 글자를 모두 포함해 주세요. 모든 답은 한국어로 해 주세요."
)
NEUTRAL_NAME = "참여자"


def parse_args(argv):
    ap = rs._Parser(description="이미지 입력 확인 (AI실행기.md 1-b)")
    ap.add_argument("--service", default="fake")
    ap.add_argument("--platform", default="app", choices=rs.PLATFORMS)
    ap.add_argument("--modes", default="image,text", help="쉼표로 구분 (image, text)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--recall", type=int, default=1, help="이전 화면 다시 보여주기 수 (프로토콜 3번: 1)")
    ap.add_argument("--snapshot-root", default="experiments/runner_dev/snapshots")
    ap.add_argument("--images-root", default="experiments/runner_dev/images")
    ap.add_argument("--labels", default=None, help="기본값: {images-root}/{service}/labels.json")
    ap.add_argument("--out", default="runs/dev/image_check")
    ap.add_argument("--token-cap", type=int, default=100000)
    args = ap.parse_args(argv)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    if not modes or any(m not in ("image", "text") for m in modes):
        ap.error("--modes 는 image, text 중에서 고른다")
    if args.repeat < 1 or args.recall < 1:
        ap.error("--repeat, --recall 은 1 이상이어야 한다 (recall 0은 TinyTroupe에서 전부 다시 넣는다)")
    args.modes = modes
    return args


def count_images(messages) -> int:
    n = 0
    for m in messages or []:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, list):
            n += sum(1 for p in content if isinstance(p, dict) and p.get("type") == "image_url")
    return n


def has_auto_description(messages) -> bool:
    # _describe_images가 보내는 영어 요청 문구. 끄면 이 요청이 없어야 한다
    return any("Describe the image" in json.dumps(m, ensure_ascii=False, default=str) for m in messages or [])


_REQUESTS = []
_COUNTER_INSTALLED = False


def install_request_counter(client_cls):
    """요청마다 이미지 장수를 센다. 캐시에서 나온 응답도 세려고 캐시보다 앞인 send_message에서 본다.
    한 프로세스에서 한 번만 감싼다 (두 번 감싸면 요청을 두 번 센다)."""
    global _COUNTER_INSTALLED
    if _COUNTER_INSTALLED:
        return
    guarded_send = client_cls.send_message

    def counting_send(self, *a, **kw):
        messages = a[0] if a else kw.get("current_messages", [])
        _REQUESTS.append({"images": count_images(messages), "auto_description": has_auto_description(messages)})
        return guarded_send(self, *a, **kw)

    client_cls.send_message = counting_send
    _COUNTER_INSTALLED = True


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def score(answer: str, labels: dict) -> dict:
    flat = normalize(answer)
    out = {}
    for kind in ("shared", "image_only"):
        words = [w for ws in labels[kind].values() for w in ws]
        hit = [w for w in words if normalize(w) in flat]
        out[kind] = {"hit": len(hit), "total": len(words), "missed": [w for w in words if w not in hit]}
    return out


def run(args, root: Path) -> int:
    snap_path = root / args.snapshot_root / args.service / args.platform / "snapshot.json"
    snap = rs.load_json(snap_path, "스냅샷")
    images_dir = root / args.images_root / args.service / args.platform
    problems = rs.validate_snapshot(snap, args.service, args.platform, "image", images_dir)
    problems += rs.validate_snapshot(snap, args.service, args.platform, "text", None)
    if problems:
        raise rs.Stop(rs.EXIT_INPUT, "입력 검증 실패\n  - " + "\n  - ".join(sorted(set(problems))))
    labels_path = Path(args.labels) if args.labels else root / args.images_root / args.service / "labels.json"
    labels = rs.load_json(labels_path if labels_path.is_absolute() else root / labels_path, "글자 목록")

    provider, base_url = rs.check_env(root)
    os.chdir(root)  # TinyTroupe는 import 시점에 현재 폴더의 config.ini를 읽는다
    import tinytroupe  # noqa: F401
    from tinytroupe import config_manager
    from tinytroupe.agent import TinyPerson
    from tinytroupe.clients import force_api_cache
    from tinytroupe.clients.openai_client import OpenAIClient

    model, _ = rs.check_tinytroupe_settings(config_manager, provider)
    rs.install_guards()
    rs.patch_tinytroupe_json()
    rs._STATE = rs.RunState(args.token_cap, 2)

    # 프로토콜 3번 설정
    TinyPerson._describe_images = lambda self, image_refs, user_context=None: ""
    TinyPerson.MAX_IMAGE_STIMULI_TO_RECALL = args.recall
    TinyPerson.communication_display = False

    install_request_counter(OpenAIClient)
    requests = _REQUESTS

    screens = snap["screens"]
    image_paths = [str(images_dir / s["image"]) for s in screens]
    screen_text = "\n\n".join(f"[화면 {i}] {s['text']}" for i, s in enumerate(screens, 1))
    model_tag = re.sub(r"[^A-Za-z0-9.-]+", "_", model)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_dir = root / args.out
    results, fatal = [], None

    print(f"[확인] {provider}/{model}, {args.service}/{args.platform}, 화면 {len(screens)}장, "
          f"방식 {','.join(args.modes)} x {args.repeat}회, 이전 화면 {args.recall}")
    for mode in args.modes:
        for r in range(1, args.repeat + 1):
            st = rs._STATE
            st.episode = rs._new_counts()
            before = len(requests)
            cache_file = out_dir / "cache" / f"{args.service}_{args.platform}_{mode}_{model_tag}_r{r}.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            force_api_cache(True, str(cache_file))
            started = time.time()
            talk = think = ""
            error = None
            try:
                TinyPerson.clear_agents()
                agent = TinyPerson(name=NEUTRAL_NAME)
                if mode == "image":
                    agent.see(images=image_paths)  # 한 번에 묶어서 준다
                else:
                    agent.see(description=screen_text)
                actions = agent.listen_and_act(QUESTION, return_actions=True, communication_display=False)
                acts = [a.get("action", {}) for a in actions or [] if isinstance(a, dict)]
                talk = "\n".join(a.get("content") or "" for a in acts if a.get("type") == "TALK")
                think = "\n".join(a.get("content") or "" for a in acts if a.get("type") == "THINK")
            except rs.AbortRun as e:
                error = f"{e.label}: {e}"
                if e.fatal:
                    fatal = e
            reqs = requests[before:]
            results.append({
                "mode": mode,
                "repeat": r,
                "ok": error is None,
                "error": error,
                "elapsed_sec": round(time.time() - started, 1),
                "calls_real": st.episode["calls_real"],
                "calls_cached": st.episode["calls_cached"],
                "tokens_in": st.episode["tokens_in"],
                "tokens_out": st.episode["tokens_out"],
                "images_per_request": [q["images"] for q in reqs],
                "auto_description_requests": sum(1 for q in reqs if q["auto_description"]),
                "score_talk": score(talk, labels),
                "hangul_ratio_talk": round(rs.hangul_ratio(talk), 3),
                "talk": talk,
                "think": think,
                "cache_file": rs._rel(cache_file, root),
            })
            print(f"  {mode} r{r}: {'성공' if error is None else error}")
            if fatal:
                break
        if fatal:
            break

    report = {
        "check_id": f"{args.service}_{args.platform}_{stamp}_{secrets.token_hex(2)}",
        "provider": provider,
        "base_url": base_url or None,
        "model": model,
        "tinytroupe_commit": rs.tinytroupe_commit(),
        "settings": {"auto_description": "off", "max_image_stimuli_to_recall": args.recall,
                     "see_bundled": True, "json_ensure_ascii": False, "question": QUESTION},
        "snapshot_file": rs._rel(snap_path, root),
        "snapshot_version": snap["snapshot_version"],
        "images": [rs._rel(Path(p), root) for p in image_paths],
        "results": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{report['check_id']}.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 60)
    print(f"[요약] {report['check_id']}")
    for x in results:
        s = x["score_talk"]
        print(f"  {x['mode']:5} r{x['repeat']}: 공통 글자 {s['shared']['hit']}/{s['shared']['total']}, "
              f"이미지에만 있는 글자 {s['image_only']['hit']}/{s['image_only']['total']}, "
              f"요청별 이미지 {x['images_per_request']}, 자동 요약 요청 {x['auto_description_requests']}회, "
              f"토큰 {x['tokens_in']:,}+{x['tokens_out']:,}")
    print(f"  기록: {rs._rel(out_file, root)}")
    print("=" * 60)

    if fatal is not None:
        return fatal.code
    return rs.EXIT_OK if all(x["ok"] for x in results) else rs.EXIT_API


def main(argv=None, root: Path = rs.ROOT) -> int:
    args = parse_args(argv)
    try:
        return run(args, Path(root))
    except rs.Stop as e:
        print(f"[중단] {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    raise SystemExit(main())

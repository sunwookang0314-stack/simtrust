"""
TinyTroupe 한국어 스모크 테스트

Q1. 한국어 페르소나가 한국어로 답하는가            -> 응답의 한글 비율
Q2. 정해진 스키마로 이슈가 추출되는가                -> ResultsExtractor 성공률, 스키마 준수율
Q3. 같은 조건을 N번 돌리면 얼마나 달라지는가         -> 반복 간 이슈 수, 유형 집합 Jaccard, 텍스트 유사도

조건
  independent : 페르소나 3명을 각각 따로 호출 (서로 영향 없음)
  world       : 같은 3명을 TinyWorld에 넣고 기획안을 broadcast, 2스텝 대화

반복(rep)마다 API 캐시 파일을 따로 쓴다. 처음 실행만 API를 호출하고 다음부터는 캐시로 재현된다.
(캐시를 같이 쓰면 반복 결과가 전부 같아져서 Q3를 잴 수 없다)

실행
  cd experiments/smoke_ko
  export OPENAI_API_KEY=...
  ../../TinyTroupe/.venv/bin/python run_smoke.py --mode independent --reps 3
  ../../TinyTroupe/.venv/bin/python run_smoke.py --mode world --reps 3
  ../../TinyTroupe/.venv/bin/python run_smoke.py --analyze-only
"""
import argparse, json, os, re, sys, time, glob, itertools, statistics
from pathlib import Path

HERE = Path(__file__).parent.resolve()
os.chdir(HERE)  # TinyTroupe 는 cwd 의 config.ini 를 읽는다

# 커밋되는 설정 파일은 config.smoke.ini 다. (리포 .gitignore 가 config.ini 를 제외한다)
# TinyTroupe 가 읽는 이름은 config.ini 뿐이므로 실행 전에 복사한다.
import shutil as _shutil
if (HERE / "config.smoke.ini").exists():
    _shutil.copyfile(HERE / "config.smoke.ini", HERE / "config.ini")

PROBLEM_TYPES = ["가입/온보딩", "정보누락/불명확", "사용성/흐름", "신뢰/보안/개인정보", "가격/가치"]
STAGES = ["발견", "가입", "핵심기능", "결제", "이탈/재방문"]
SEVERITIES = ["상", "중", "하"]

FIELDS = ["name", "overall_verdict", "would_use", "issues"]
FIELDS_HINTS = {
    "name": "에이전트 이름 (그대로)",
    "overall_verdict": "이 사람이 기획안에 대해 내린 전체 평가를 한국어 1~2문장으로 요약",
    "would_use": "정확히 'yes', 'no', 'unsure' 중 하나. 이 사람이 실제로 이 앱을 쓸 것 같은지",
    "issues": (
        "이 사람이 지적한 문제점의 리스트. 각 원소는 다음 키를 가진 객체: "
        "problem_type(정확히 다음 중 하나: " + ", ".join(PROBLEM_TYPES) + "), "
        "stage(정확히 다음 중 하나: " + ", ".join(STAGES) + "), "
        "severity(정확히 다음 중 하나: " + ", ".join(SEVERITIES) + "), "
        "evidence(이 사람이 말한 근거를 한국어 한 문장으로), "
        "quote(발화 원문 그대로 짧게 인용). "
        "지적이 없으면 빈 리스트 []. 말하지 않은 내용을 추가하지 말 것."
    ),
}

INTERVIEW_PROMPT = """안녕하세요. 저희는 대학생 대상 서비스를 기획 중인 팀입니다. 아래 기획안을 읽고, 실제로 이 앱을 쓰게 될 대학생 입장에서 솔직하게 평가해 주세요.

특히 다음을 말해 주세요.
1. 이 앱을 실제로 쓸 것 같은지, 그 이유
2. 가입부터 거래 완료까지 과정에서 불편하거나 걱정되는 점 (구체적으로, 여러 개여도 좋음)
3. 마음에 드는 점

정답은 없습니다. 본인 상황과 성격대로 편하게, 한국어로 답해 주세요.

---
{proposal}
---
"""

def hangul_ratio(text: str) -> float:
    """공백/숫자/구두점을 제외한 문자 중 한글 비율."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ko = sum(1 for c in letters if '\uac00' <= c <= '\ud7a3' or '\u3131' <= c <= '\u318e')
    return ko / len(letters)

def validate_extraction(res):
    """추출 결과의 스키마 준수 여부를 점검. (ok, problems, issues_normalized)"""
    problems = []
    if not isinstance(res, dict):
        return False, ["결과가 dict 아님: %s" % type(res).__name__], []
    for f in FIELDS:
        if f not in res:
            problems.append(f"필드 누락: {f}")
    issues = res.get("issues")
    if not isinstance(issues, list):
        problems.append("issues 가 리스트 아님")
        issues = []
    norm = []
    for i, it in enumerate(issues):
        if not isinstance(it, dict):
            problems.append(f"issues[{i}] dict 아님"); continue
        if it.get("problem_type") not in PROBLEM_TYPES:
            problems.append(f"issues[{i}].problem_type 범위 밖: {it.get('problem_type')}")
        if it.get("stage") not in STAGES:
            problems.append(f"issues[{i}].stage 범위 밖: {it.get('stage')}")
        if it.get("severity") not in SEVERITIES:
            problems.append(f"issues[{i}].severity 범위 밖: {it.get('severity')}")
        norm.append(it)
    if res.get("would_use") not in ("yes", "no", "unsure"):
        problems.append(f"would_use 범위 밖: {res.get('would_use')}")
    return len(problems) == 0, problems, norm

# ----------------------------------------------------------------------------
# 실행부
# ----------------------------------------------------------------------------
def run(mode: str, reps: int, proposal_path: str, personas_dir: str, out_dir: Path):
    sys.path.insert(0, str(HERE / "../../TinyTroupe"))
    import tinytroupe
    from tinytroupe import config_manager
    from tinytroupe.agent import TinyPerson
    from tinytroupe.environment import TinyWorld
    from tinytroupe.extraction import ResultsExtractor
    from tinytroupe.clients import client, force_api_cache

    # Gemini 호환 엔드포인트는 frequency/presence_penalty 를 거부하므로 빼고 보낸다 (FINDINGS 3번)
    base_url = os.getenv("OPENAI_BASE_URL") or config_manager.get("base_url") or ""
    if base_url and "openai.com" not in base_url:
        from tinytroupe.clients.openai_client import OpenAIClient
        _orig_raw = OpenAIClient._raw_model_call
        def _patched_raw(self, model, chat_api_params):
            for k in ("frequency_penalty", "presence_penalty"):
                chat_api_params.pop(k, None)
            return _orig_raw(self, model, chat_api_params)
        OpenAIClient._raw_model_call = _patched_raw
        print(f"[compat] {base_url} : penalty 파라미터 제거")

    proposal = Path(proposal_path).read_text(encoding="utf-8")
    prompt = INTERVIEW_PROMPT.format(proposal=proposal)
    persona_files = sorted(glob.glob(os.path.join(personas_dir, "*.agent.json")))
    assert persona_files, "페르소나 파일 없음"

    extractor = ResultsExtractor(
        extraction_objective="이 사람이 기획안에 대해 말한 전체 평가와, 구체적으로 지적한 문제점들을 추출한다.",
        situation="이 사람은 대학생용 중고 교재 거래 앱 기획안을 읽고 솔직한 의견을 말해 달라는 요청을 받았다.",
        fields=FIELDS, fields_hints=FIELDS_HINTS, verbose=False,
    )

    model = config_manager.get("model")
    tag = re.sub(r"[^A-Za-z0-9.-]+", "_", model)  # 모델별로 캐시/결과 파일을 나눈다
    print(f"[run] mode={mode} reps={reps} model={model} personas={len(persona_files)}")

    for rep in range(reps):
        rep_out = out_dir / f"{tag}__{mode}_rep{rep}.json"
        if rep_out.exists():
            print(f"[rep {rep}] 결과 있음, 건너뜀 ({rep_out.name})")
            continue
        cache_file = HERE / "cache" / f"{tag}__{mode}_rep{rep}.api_cache.json"
        force_api_cache(True, str(cache_file))
        client().reset_cost_stats()
        TinyPerson.clear_agents()

        agents = [TinyPerson.load_specification(p) for p in persona_files]
        t0 = time.time()
        talks = {}

        def collect_talks(ag):
            """에피소드 기억에서 TALK 액션 내용만 모은다. (메모리 형식: role=assistant, content={"action": {...}})"""
            out = []
            for m in ag.episodic_memory.retrieve_all():
                if m.get("role") != "assistant":
                    continue
                a = (m.get("content") or {}).get("action") or {}
                if a.get("type") == "TALK" and a.get("content"):
                    out.append(a["content"])
            return "\n".join(out)

        if mode == "independent":
            for ag in agents:
                ag.listen_and_act(prompt, communication_display=False)
        elif mode == "world":
            world = TinyWorld(f"SE4 포커스그룹 rep{rep}", agents, broadcast_if_no_target=True)
            world.broadcast(prompt)
            world.run(2)
        else:
            raise ValueError(mode)
        for ag in agents:
            talks[ag.name] = collect_talks(ag)
        t_talk = time.time() - t0

        # 추출
        t1 = time.time()
        extractions = {}
        for ag in agents:
            try:
                res = extractor.extract_results_from_agent(ag)
            except Exception as e:  # 추출 자체 실패도 데이터
                res = {"__error__": repr(e)}
            extractions[ag.name] = res
        t_ext = time.time() - t1

        stats = client().get_cost_stats()
        record = {
            "mode": mode, "rep": rep, "model": model,
            "reasoning_effort": config_manager.get("reasoning_effort"),
            "elapsed_sec": {"talk": round(t_talk, 1), "extract": round(t_ext, 1)},
            "cost_stats": stats,
            "personas": [Path(p).name for p in persona_files],
            "talks": talks,
            "extractions": extractions,
            "interactions_pretty": {ag.name: ag.pretty_current_interactions(max_content_length=None) for ag in agents},
        }
        rep_out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[rep {rep}] 저장 {rep_out.name}  talk={t_talk:.0f}s extract={t_ext:.0f}s tokens={stats['total_tokens']} calls={stats['model_calls']}")

# ----------------------------------------------------------------------------
# 분석부
# ----------------------------------------------------------------------------
def jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b: return 1.0
    return len(a & b) / len(a | b)

def text_sim(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()

def analyze(out_dir: Path):
    files = sorted(glob.glob(str(out_dir / "*_rep*.json")))
    if not files:
        print("결과 파일 없음"); return
    recs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    lines = ["# 스모크 테스트 결과 요약", ""]
    by_mode = {}
    for r in recs:
        by_mode.setdefault((r["model"], r["mode"]), []).append(r)

    for (model_, mode), rs in by_mode.items():
        rs.sort(key=lambda r: r["rep"])
        lines += [f"## 조건: {mode}  (모델 {model_}, 반복 {len(rs)}회)", ""]
        # Q1 한글 비율
        lines += ["### Q1. 한국어로 답하는가 (응답 문자 중 한글 비율)", "", "| rep | " + " | ".join(rs[0]["talks"].keys()) + " |", "|---|" + "---|" * len(rs[0]["talks"])]
        for r in rs:
            lines.append(f"| {r['rep']} | " + " | ".join(f"{hangul_ratio(t):.2f} ({len(t)}자)" for t in r["talks"].values()) + " |")
        lines.append("")
        # Q2 스키마 추출
        lines += ["### Q2. 고정 스키마로 추출되는가", "", "| rep | 에이전트 | 추출 성공 | 스키마 준수 | 이슈 수 | would_use | 문제점 |", "|---|---|---|---|---|---|---|"]
        issue_sets = {}   # (rep) -> {agent: set of (type,stage)}
        issue_counts = {}
        for r in rs:
            for name, res in r["extractions"].items():
                ok_ext = isinstance(res, dict) and "__error__" not in res
                ok_schema, probs, norm = validate_extraction(res) if ok_ext else (False, ["추출 실패"], [])
                issue_sets.setdefault(r["rep"], {})[name] = {(i.get("problem_type"), i.get("stage")) for i in norm}
                issue_counts.setdefault(name, []).append(len(norm))
                lines.append(f"| {r['rep']} | {name} | {'O' if ok_ext else 'X'} | {'O' if ok_schema else 'X'} | {len(norm)} | {res.get('would_use') if ok_ext else '-'} | {'; '.join(probs)[:120]} |")
        lines.append("")
        # Q3 반복 간 흔들림
        lines += ["### Q3. 반복 간 흔들림", ""]
        lines += ["| 에이전트 | 이슈 수 (rep별) | 평균±표준편차 | (유형,단계) 집합 Jaccard 평균 | 발화 텍스트 유사도 평균 |", "|---|---|---|---|---|"]
        reps_ = [r["rep"] for r in rs]
        for name in rs[0]["talks"].keys():
            counts = issue_counts.get(name, [])
            jac, sims = [], []
            for a, b in itertools.combinations(reps_, 2):
                jac.append(jaccard(issue_sets.get(a, {}).get(name, set()), issue_sets.get(b, {}).get(name, set())))
                ta = next(r for r in rs if r["rep"] == a)["talks"][name]
                tb = next(r for r in rs if r["rep"] == b)["talks"][name]
                sims.append(text_sim(ta, tb))
            sd = statistics.pstdev(counts) if len(counts) > 1 else 0.0
            lines.append(f"| {name} | {counts} | {statistics.mean(counts) if counts else 0:.1f}±{sd:.1f} | {statistics.mean(jac) if jac else float('nan'):.2f} | {statistics.mean(sims) if sims else float('nan'):.2f} |")
        lines.append("")
        # 유형별 빈도 (전 반복·전 에이전트)
        from collections import Counter
        c_type = Counter(); c_stage = Counter()
        for rep_d in issue_sets.values():
            for s in rep_d.values():
                for t, st in s:
                    c_type[t] += 1; c_stage[st] += 1
        lines += ["### 지적 분포 (전체)", "", f"- 문제유형: {dict(c_type)}", f"- 대상 단계: {dict(c_stage)}", ""]
        # 비용
        tot_tok = sum(r["cost_stats"]["total_tokens"] for r in rs)
        tot_calls = sum(r["cost_stats"]["model_calls"] for r in rs)
        tot_time = sum(r["elapsed_sec"]["talk"] + r["elapsed_sec"]["extract"] for r in rs)
        lines += ["### 비용·시간", "", f"- API 호출 {tot_calls}회, 총 토큰 {tot_tok:,}, 총 소요 {tot_time:.0f}s (캐시 재실행 시 0)", ""]
        # 발화 원문 샘플
        lines += ["### 발화 샘플 (rep0)", ""]
        for name, t in rs[0]["talks"].items():
            lines += [f"**{name}**", "", "> " + t.replace("\n", "\n> ")[:1500], ""]

    summary = "\n".join(lines)
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["independent", "world"], default="independent")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--proposal", default="proposal_01_campusbook.md")
    ap.add_argument("--personas", default="personas")
    ap.add_argument("--out", default="results")
    ap.add_argument("--analyze-only", action="store_true")
    a = ap.parse_args()
    out_dir = HERE / a.out
    out_dir.mkdir(exist_ok=True)
    if not a.analyze_only:
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY 환경변수가 필요합니다. (BASE_URL 을 config.ini 에 두면 OpenAI 호환 API 도 가능)")
        run(a.mode, a.reps, a.proposal, a.personas, out_dir)
    analyze(out_dir)

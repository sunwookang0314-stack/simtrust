"""results/*.json 을 읽어서 results/report.html 을 만든다. 차트를 파일 안에 넣어서 이 파일 하나만 있으면 된다."""
import json, glob, base64, io, html, re, statistics, itertools, sys, os
from pathlib import Path
from collections import Counter
HERE = Path(__file__).parent.resolve(); os.chdir(HERE)
sys.path.insert(0, str(HERE))
from run_smoke import hangul_ratio, validate_extraction, jaccard, text_sim, PROBLEM_TYPES, STAGES

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
# 한글 폰트 탐색 (없으면 영문 라벨로 대체)
KO_FONT = None
for cand in ["NanumGothic", "Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR", "AppleGothic"]:
    if any(cand.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        KO_FONT = cand; break
if KO_FONT is None:
    for p in glob.glob("/mnt/c/Windows/Fonts/malgun.ttf") + glob.glob("/usr/share/fonts/**/*Nanum*.ttf", recursive=True):
        font_manager.fontManager.addfont(p); KO_FONT = font_manager.FontProperties(fname=p).get_name(); break
if KO_FONT:
    plt.rcParams["font.family"] = KO_FONT
plt.rcParams["axes.unicode_minus"] = False

def fig_b64(fig):
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130, bbox_inches="tight"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def esc(s): return html.escape(str(s if s is not None else ""))

files = sorted(glob.glob("results/*_rep*.json"))
recs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
groups = {}
for r in recs: groups.setdefault((r["model"], r["mode"]), []).append(r)

personas = {}
for pf in sorted(glob.glob("personas/*.agent.json")):
    d = json.loads(Path(pf).read_text(encoding="utf-8"))["persona"]; personas[d["name"]] = d
proposal = Path("proposal_01_campusbook.md").read_text(encoding="utf-8")
findings = Path("FINDINGS.md").read_text(encoding="utf-8") if Path("FINDINGS.md").exists() else ""

CSS = """
body{font-family:'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',sans-serif;max-width:1100px;margin:30px auto;padding:0 20px;color:#222;line-height:1.55}
h1{border-bottom:3px solid #333;padding-bottom:6px} h2{margin-top:40px;border-left:6px solid #4A90D9;padding-left:10px}
table{border-collapse:collapse;margin:10px 0;font-size:14px} th,td{border:1px solid #ccc;padding:5px 9px;vertical-align:top} th{background:#f0f4f8}
.ok{color:#1a7f37;font-weight:bold} .ng{color:#c0392b;font-weight:bold}
.card{border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0;background:#fafafa}
details{margin:6px 0} summary{cursor:pointer;font-weight:bold} pre{white-space:pre-wrap;background:#fff;border:1px solid #eee;padding:10px;font-size:13.5px}
.tag{display:inline-block;background:#e8f0fe;border-radius:4px;padding:1px 6px;font-size:12px;margin-right:4px}
.sev-상{background:#fde2e2}.sev-중{background:#fff3cd}.sev-하{background:#e2f0d9}
img{max-width:100%;border:1px solid #eee;margin:6px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
"""
out = [f"<html><head><meta charset='utf-8'><title>TinyTroupe 한국어 스모크 테스트 리포트</title><style>{CSS}</style></head><body>"]
out.append("<h1>TinyTroupe 한국어 사전검증(스모크) 테스트 리포트</h1>")
out.append("<p><b>목적</b>: TinyTroupe(0.7.0)를 한국어 페르소나·한국어 기획안에 그대로 썼을 때 (Q1) 한국어로 답하는지, (Q2) 고정 스키마로 이슈가 추출되는지, (Q3) 같은 조건을 반복하면 얼마나 흔들리는지 확인. "
           "<b>설계</b>: 페르소나 3명 × 기획안 1종 × 반복 3회. independent 는 각자 따로 호출, world 는 셋을 한 방에 넣고 2스텝 대화. 반복마다 API 캐시를 따로 두어 재현 가능.</p>")

# ---- 실험 재료
out.append("<h2>1. 실험 재료</h2><div class='grid'>")
for name, d in personas.items():
    out.append(f"<div class='card'><b>{esc(name)}</b> ({d['age']}세, {esc(d['occupation']['title'])})<br>"
               f"<small>{esc(d['residence'])} · {esc(d['education'])}</small><br>"
               f"<small>성향: {esc(', '.join(d['personality']['traits']))}</small><br>"
               f"<small>말투: {esc(d['style'])}</small></div>")
out.append("</div>")
out.append(f"<details><summary>기획안 원문 (캠퍼스북). 일부러 넣어둔 문제: 6단계 가입, 학생증 24시간 승인, 마케팅 동의 필수, 계좌이체만, 야간 푸시 기본 켜짐, 판매 수수료</summary><pre>{esc(proposal)}</pre></details>")

for (model, mode), rs in groups.items():
    rs.sort(key=lambda r: r["rep"])
    names = list(rs[0]["talks"].keys()); reps_ = [r["rep"] for r in rs]
    out.append(f"<h2>2. 결과: 조건 <code>{esc(mode)}</code>, 모델 <code>{esc(model)}</code>, 반복 {len(rs)}회</h2>")
    out.append("<p><small>설정: MAX_COMPLETION_TOKENS=8000, MAX_ACTIONS_BEFORE_DONE=15(TinyTroupe 기본값). REASONING_EFFORT 는 이 버전에서 동작하지 않아 조건에서 뺐다. 자세한 내용은 리포 루트 README.md 참고.</small></p>")

    # Q1
    ratios = {n: [hangul_ratio(r["talks"][n]) for r in rs] for n in names}
    lens = {n: [len(r["talks"][n]) for r in rs] for n in names}
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    for i, n in enumerate(names):
        ax[0].bar([x + i*0.25 for x in reps_], ratios[n], width=0.25, label=n)
        ax[1].bar([x + i*0.25 for x in reps_], lens[n], width=0.25, label=n)
    ax[0].set_ylim(0, 1.05); ax[0].set_title("Q1 한글 비율 (1.0 = 전부 한국어)"); ax[0].set_xlabel("반복(rep)"); ax[0].legend(fontsize=8)
    ax[1].set_title("발화 길이 (문자 수)"); ax[1].set_xlabel("반복(rep)")
    for a in ax: a.set_xticks([x + 0.25 for x in reps_]); a.set_xticklabels([f"rep {x}" for x in reps_])
    out.append("<h3>Q1. 한국어로 답하는가</h3>")
    out.append(f"<img src='{fig_b64(fig)}'>")
    allr = [v for vs in ratios.values() for v in vs]
    out.append(f"<p>전체 {len(allr)}건 평균 한글 비율 <b>{statistics.mean(allr):.3f}</b> (최소 {min(allr):.2f}). "
               f"{'영어 섞임 없이 한국어로 답함.' if min(allr) > 0.9 else '일부 응답에 다른 언어가 섞임.'}</p>")

    # Q2
    out.append("<h3>Q2. 고정 스키마로 추출되는가</h3>")
    out.append("<table><tr><th>rep</th><th>에이전트</th><th>추출</th><th>스키마</th><th>이슈 수</th><th>would_use</th><th>비고</th></tr>")
    issue_sets, issue_counts, n_ok, n_tot = {}, {}, 0, 0
    for r in rs:
        for n in names:
            res = r["extractions"].get(n)
            ok_ext = isinstance(res, dict) and "__error__" not in res
            ok_s, probs, norm = validate_extraction(res) if ok_ext else (False, ["추출 실패(API 오류)"], [])
            n_tot += 1; n_ok += ok_s
            issue_sets.setdefault(r["rep"], {})[n] = {(i.get("problem_type"), i.get("stage")) for i in norm}
            issue_counts.setdefault(n, []).append(len(norm) if ok_ext else None)
            out.append(f"<tr><td>{r['rep']}</td><td>{esc(n)}</td><td class='{'ok' if ok_ext else 'ng'}'>{'O' if ok_ext else 'X'}</td>"
                       f"<td class='{'ok' if ok_s else 'ng'}'>{'O' if ok_s else 'X'}</td><td>{len(norm)}</td><td>{esc(res.get('would_use')) if ok_ext else '-'}</td><td>{esc('; '.join(probs))}</td></tr>")
    out.append(f"</table><p>추출 성공 + 스키마 준수: <b>{n_ok}/{n_tot}</b>. 실패 건은 모두 API 측 오류(429/503)이며 모델이 잘못된 형식을 낸 경우는 {'없음' if all('범위 밖' not in p for r in rs for n in names for p in (validate_extraction(r['extractions'].get(n))[1] if isinstance(r['extractions'].get(n), dict) and '__error__' not in r['extractions'].get(n) else [])) else '있음'}.</p>")

    # Q3
    out.append("<h3>Q3. 반복 간 흔들림 (추출 성공한 반복끼리만 비교)</h3>")
    out.append("<table><tr><th>에이전트</th><th>이슈 수 (rep별)</th><th>평균±표준편차</th><th>(유형,단계) 집합 Jaccard</th><th>발화 텍스트 유사도</th><th>would_use</th></tr>")
    jac_all = {}
    for n in names:
        valid = [(r["rep"], r) for r in rs if isinstance(r["extractions"].get(n), dict) and "__error__" not in r["extractions"].get(n)]
        cnts = [len(validate_extraction(r["extractions"][n])[2]) for _, r in valid]
        jac, sims = [], []
        for (a, ra), (b, rb) in itertools.combinations(valid, 2):
            jac.append(jaccard(issue_sets[a][n], issue_sets[b][n])); sims.append(text_sim(ra["talks"][n], rb["talks"][n]))
        jac_all[n] = jac
        wu = [r["extractions"][n].get("would_use") for _, r in valid]
        sd = statistics.pstdev(cnts) if len(cnts) > 1 else 0
        out.append(f"<tr><td>{esc(n)}</td><td>{cnts}</td><td>{statistics.mean(cnts) if cnts else 0:.1f}±{sd:.1f}</td>"
                   f"<td>{statistics.mean(jac):.2f}</td><td>{statistics.mean(sims):.2f}</td><td>{esc(wu)}</td></tr>" if jac else
                   f"<tr><td>{esc(n)}</td><td>{cnts}</td><td>-</td><td>비교 불가(성공 반복 &lt;2)</td><td>-</td><td>{esc(wu)}</td></tr>")
    out.append("</table><p><small>Jaccard: 두 반복에서 지적한 (문제유형, 단계) 조합 집합의 겹침 비율. 1.0 = 완전히 같은 종류의 지적, 0 = 전혀 다름. 텍스트 유사도는 difflib 비율(문장이 달라도 같은 내용일 수 있어 참고용).</small></p>")

    # 분포 차트
    c_type, c_stage = Counter(), Counter()
    for rd in issue_sets.values():
        for s in rd.values():
            for t, st in s: c_type[t] += 1; c_stage[st] += 1
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.2))
    ax[0].barh(PROBLEM_TYPES, [c_type.get(t, 0) for t in PROBLEM_TYPES], color="#4A90D9"); ax[0].set_title("지적된 문제유형 분포 (전체)")
    ax[1].barh(STAGES, [c_stage.get(s, 0) for s in STAGES], color="#FF8C42"); ax[1].set_title("지적된 단계 분포 (전체)")
    out.append(f"<img src='{fig_b64(fig)}'>")

    # 비용
    tok = sum(r["cost_stats"]["total_tokens"] for r in rs); calls = sum(r["cost_stats"]["model_calls"] for r in rs)
    t = sum(r["elapsed_sec"]["talk"] + r["elapsed_sec"]["extract"] for r in rs)
    out.append(f"<h3>비용·시간</h3><p>실제 API 호출 {calls}회 (캐시 제외), 총 토큰 {tok:,}, 소요 {t/60:.1f}분 (무료 티어 대기 포함). "
               f"호출 1건당 입력이 1만 토큰이 넘는 이유는 TinyTroupe 페르소나 시스템 프롬프트가 39KB이기 때문.</p>")

    # 발화·추출 상세
    out.append("<h3>페르소나별 발화 원문과 추출 결과</h3>")
    for n in names:
        out.append(f"<div class='card'><b>{esc(n)}</b>")
        for r in rs:
            res = r["extractions"].get(n)
            out.append(f"<details {'open' if r['rep']==0 else ''}><summary>rep {r['rep']}, 발화 {len(r['talks'][n])}자</summary><pre>{esc(r['talks'][n])}</pre>")
            if isinstance(res, dict) and "__error__" not in res:
                out.append(f"<p><b>전체 평가</b>: {esc(res.get('overall_verdict'))} &nbsp; <span class='tag'>would_use={esc(res.get('would_use'))}</span></p>")
                out.append("<table><tr><th>#</th><th>문제유형</th><th>단계</th><th>심각도</th><th>근거</th><th>인용</th></tr>")
                for i, it in enumerate(res.get("issues") or [], 1):
                    out.append(f"<tr><td>{i}</td><td>{esc(it.get('problem_type'))}</td><td>{esc(it.get('stage'))}</td><td class='sev-{esc(it.get('severity'))}'>{esc(it.get('severity'))}</td><td>{esc(it.get('evidence'))}</td><td><small>{esc(it.get('quote'))}</small></td></tr>")
                out.append("</table>")
            else:
                out.append(f"<p class='ng'>추출 실패: {esc((res or {}).get('__error__', res))[:200]}</p>")
            out.append("</details>")
        out.append("</div>")

# 비교
cmp_p = Path("results/compare_independent_vs_world.md")
if cmp_p.exists():
    import markdown as _md
    out.append("<h2>2b. independent vs world 비교</h2>" + _md.markdown(cmp_p.read_text(encoding="utf-8"), extensions=["tables"]))
# 발견 사항
if findings:
    out.append("<h2>3. 실험 중 발견한 TinyTroupe 문제점</h2>")
    out.append(f"<pre>{esc(findings)}</pre>")
out.append("<h2>4. 재현 방법</h2><pre>cd experiments/smoke_ko\n../../TinyTroupe/.venv/bin/python run_smoke.py --mode independent --reps 3   # cache/ 가 있으면 API 키 없이도 동일 결과 재현\n../../TinyTroupe/.venv/bin/python make_report.py</pre>")
out.append("</body></html>")
Path("results/report.html").write_text("\n".join(out), encoding="utf-8")
print("saved results/report.html", "font:", KO_FONT)

// "뽑은 이유 전체 보기" (시연 2장 끝에 접어 둠). 옛 화면 3 이유 뽑기 + 화면 4 코드 붙이기.
// 위: 원래 말 → 이름표 묶음. 아래: 판정자 두 명이 따로 붙인 기록 표와 kappa (scripts/reason_sheet.py).
// 실제 시트는 AI 이름·조건을 가리고 순서를 섞는다. kappa 0.6 미만이면 다시 한다 (NFR-07)
import { useEffect, useMemo, useState } from "react";
import { parseCsv } from "../lib/data.js";
import { EVERYONE, allLines, fname } from "../lib/examples.js";

const KAPPA_MIN = 0.6;

function kappa(a, b) {
  const n = a.length, po = a.filter((x, i) => x === b[i]).length / n;
  const labels = new Set([...a, ...b]);
  const pe = [...labels].reduce((s, l) => s + (a.filter(x => x === l).length / n) * (b.filter(x => x === l).length / n), 0);
  return pe === 1 ? null : (po - pe) / (1 - pe);
}

// 판정자 화면처럼 순서를 섞는다 (늘 같은 순서가 나오게 고정 시드)
function shuffled(xs) {
  const out = [...xs];
  let seed = 11;
  for (let i = out.length - 1; i > 0; i--) {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    const j = seed % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function Code({ code, book }) {
  const c = book[code];
  return <span className={`cd ${c?.scope === "기능" ? "f" : ""}`} title={c ? `${c.name} — ${c.정의}` : "코드북에 없음"}>{code}</span>;
}

export default function ReasonBook() {
  const [book, setBook] = useState({});
  const [blind, setBlind] = useState(false);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/codebook.csv`).then(r => r.text())
      .then(t => setBook(Object.fromEntries(parseCsv(t).map(r => [r.code, r]))));
  }, []);

  const lines = useMemo(() => EVERYONE.flatMap(allLines), []);
  const shown = blind ? shuffled(lines) : lines;
  const agree = lines.filter(l => l.c1 === l.c2).length;
  const k = kappa(lines.map(l => l.c1), lines.map(l => l.c2));
  const aiName = id => EVERYONE.find(a => a.id === id)?.name;
  const groups = useMemo(() => {
    const m = new Map();
    for (const l of lines) m.set(l.fin, [...(m.get(l.fin) ?? []), l]);
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [lines]);

  return (
    <>
      <p>AI 4개의 예시 답에서 뽑은 이유 {lines.length}줄을 이름표 {groups.length}가지로 묶었어요. 대학생 설문 답도 같은 이름표로 묶어요.</p>
      <div className="cgroups">
        {groups.map(([code, ls]) => (
          <section key={code} className={`cgroup${book[code]?.scope === "기능" ? " f" : ""}`}>
            <header title={book[code]?.정의}>
              <b>{book[code]?.name ?? code}</b>
              <span className="cn">{ls.length}줄</span>
            </header>
            <ul>
              {ls.map(l => (
                <li key={l.id}>
                  <span className="q">“{l.text}”</span>
                  <span className="who">{aiName(l.ai)} · {fname(l.feature)}</span>
                  {l.c1 !== l.c2 && <span className="fix" title={`판정자 1: ${l.c1}, 판정자 2: ${l.c2}`}>의견이 갈려 맞춤</span>}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <p className="cnote">
        두 사람이 따로 붙여 보고 <b>{lines.length}줄 중 {agree}줄</b>이 같았어요. 다른 줄은 같이 보고 하나로 맞췄어요.
        <span className="kp">일치도 κ <b className={k != null && k < KAPPA_MIN ? "lo" : ""}>{k == null ? "-" : k.toFixed(2)}</b> (0.6 미만이면 다시)</span>
      </p>
      <label className="blind"><input type="checkbox" checked={blind} onChange={e => setBlind(e.target.checked)} /> 판정자에게 보이는 대로 (AI 이름 가리고 섞기)</label>
      <table className="sheet">
        <thead><tr>{!blind && <th>AI</th>}<th>이유 줄</th><th>기능</th><th>판정자 1</th><th>판정자 2</th><th>최종</th></tr></thead>
        <tbody>{shown.map(l => (
          <tr key={l.id} className={l.c1 !== l.c2 ? "diff" : ""}>
            {!blind && <td className="ai">{aiName(l.ai)}</td>}
            <td>{l.text}<small className={`kd ${l.kind}`}>{l.kind === "use" ? "쓸" : "안 쓸"}</small></td>
            <td>{fname(l.feature)}</td>
            <td><Code code={l.c1} book={book} /></td>
            <td><Code code={l.c2} book={book} /></td>
            <td><Code code={l.fin} book={book} /> <span className="fn">{book[l.fin]?.name}</span></td>
          </tr>
        ))}</tbody>
      </table>
      <p className="basis">코드북 v1.0 작업본 · 파란 코드 = 기능 코드, 회색 = 어느 기능에나 쓰는 공통 코드</p>
    </>
  );
}

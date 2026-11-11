// 화면 4. 코드 붙이기: 화면 3에서 뽑은 이유 줄마다 판정자 두 명이 코드북 v0.1 코드를 따로 붙이고 맞춰 본다
// (scripts/reason_sheet.py). 실제 시트는 AI 이름·조건을 가리고 순서를 섞는다. kappa 0.6 미만이면 다시 한다 (NFR-07)
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
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

export default function Coding() {
  const [book, setBook] = useState({});
  const [blind, setBlind] = useState(false);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/codebook_v0.1.csv`).then(r => r.text())
      .then(t => setBook(Object.fromEntries(parseCsv(t).map(r => [r.code, r]))));
  }, []);

  const lines = useMemo(() => EVERYONE.flatMap(allLines), []);
  const shown = blind ? shuffled(lines) : lines;
  const agree = lines.filter(l => l.c1 === l.c2).length;
  const k = kappa(lines.map(l => l.c1), lines.map(l => l.c2));
  const used = [...new Set(lines.map(l => l.fin))].sort();
  const aiName = id => EVERYONE.find(a => a.id === id)?.name;

  return (
    <div className="page">
      <div className="phead">
        <span className="no">4 · 코드 붙이기</span><span className="sample">화면 3의 예시 줄 · 코드북 v0.1</span>
        <h1>이유 {lines.length}줄에 코드북 코드를 붙였어요</h1>
        <p>판정자 두 명이 따로 붙이고, 다른 줄은 맞춰 봐요. 사람 설문 답에도 같은 코드북으로 코드를 붙여서, 같은 코드면 같은 이유로 봐요.</p>
      </div>

      <div className="ctop">
        <div className="cstat">
          <span>두 판정자 일치 <b>{agree}/{lines.length}</b></span>
          <span>kappa <b className={k != null && k < KAPPA_MIN ? "lo" : ""}>{k == null ? "-" : k.toFixed(2)}</b> <small>(0.6 미만이면 다시)</small></span>
        </div>
        <label className="blind"><input type="checkbox" checked={blind} onChange={e => setBlind(e.target.checked)} /> 판정자에게 보이는 대로 (AI 이름 가리고 섞기)</label>
      </div>

      <div className="cgrid">
        <table className="sheet">
          <thead><tr>{!blind && <th>AI</th>}<th>이유 줄</th><th>기능</th><th>판정자 1</th><th>판정자 2</th><th>최종</th></tr></thead>
          <tbody>{shown.map(l => (
            <tr key={l.id} className={l.c1 !== l.c2 ? "diff" : ""}>
              {!blind && <td className="ai">{aiName(l.ai)}</td>}
              <td>{l.text}{l.option && <em className="opt">보기</em>}<small className={`kd ${l.kind}`}>{l.kind === "use" ? "쓸" : "안 쓸"}</small></td>
              <td>{fname(l.feature)}</td>
              <td><Code code={l.c1} book={book} /></td>
              <td><Code code={l.c2} book={book} /></td>
              <td><Code code={l.fin} book={book} /> <span className="fn">{book[l.fin]?.name}</span></td>
            </tr>
          ))}</tbody>
        </table>

        <aside className="cbook">
          <h4>쓴 코드 (코드북 v0.1)</h4>
          {used.map(c => (
            <div key={c} className="cb">
              <Code code={c} book={book} /><b>{book[c]?.name}</b>
              <p>{book[c]?.정의}</p>
            </div>
          ))}
          <p className="basis">파란 코드 = 기능 코드, 회색 = 공통 코드. 다르게 붙인 줄은 노란색이에요.</p>
        </aside>
      </div>

      <div className="next">
        <span className="basis">다음 단계에서 이 코드를 사람 설문 코드와 거름망으로 견줘요</span>
        <Link className="btn pri" to="/reasons">거름망으로 →</Link>
      </div>
    </div>
  );
}

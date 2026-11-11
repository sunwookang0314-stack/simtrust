// 화면 4. 코드 붙이기 (틀). 지금 설계는 판정자 2명이 시트에 코드북 코드를 붙인다 (scripts/reason_sheet.py)
import Frame from "../components/Frame.jsx";

const ROWS = [
  { line: "알림이 하루에도 여러 번 오면 귀찮을 것 같음", c1: "F3-01", c2: "F3-01", fin: "F3-01 알림이 너무 잦음" },
  { line: "스크랩을 해야만 알림이 와서 받을 일이 없음", c1: "F3-05", c2: "C01", fin: "F3-05 스크랩과 묶여 있음" },
];

export default function Coding() {
  return (
    <Frame no={4} title="뽑은 이유에 코드북 코드를 붙여요"
           lead="판정자 두 명이 따로 코드를 붙이고 맞춰 봐요. 두 사람 일치도(kappa)가 0.6보다 낮으면 다시 해요."
           blocks={["코드북 v0.1 docs/codebook/코드북_초안.csv (33개)", "판정 시트 가져오기 결과 agreement_*.json (kappa)"]}
           waits={["데모 방식: 판정자가 붙인 결과 보여주기(A) / 임베딩 자동 후보 + '판정자 확인 전' 표시(B)"]}>
      <table className="sheet">
        <thead><tr><th>이유 줄</th><th>판정자 1</th><th>판정자 2</th><th>최종</th></tr></thead>
        <tbody>{ROWS.map(r => (
          <tr key={r.line} className={r.c1 !== r.c2 ? "diff" : ""}>
            <td>{r.line}</td><td>{r.c1}</td><td>{r.c2}</td><td>{r.fin}</td>
          </tr>
        ))}</tbody>
      </table>
      <p className="basis">두 판정자가 다르게 붙인 줄은 노란색이에요 (예시)</p>
    </Frame>
  );
}

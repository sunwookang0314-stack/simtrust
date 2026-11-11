// 데이터가 아직 안 붙은 화면(1~4)의 틀. 무엇을 보여줄지, 무엇을 기다리는지 같이 적어 둔다
export default function Frame({ no, title, lead, blocks = [], waits = [], children }) {
  return (
    <div className="page">
      <div className="phead">
        <span className="no">{no} · 화면 틀</span>
        <h1>{title}</h1>
        <p>{lead}</p>
      </div>
      <div className="frame-body">{children}</div>
      {(blocks.length > 0 || waits.length > 0) && (
        <aside className="todo">
          {blocks.length > 0 && <><h4>붙일 데이터</h4><ul>{blocks.map(b => <li key={b}>{b}</li>)}</ul></>}
          {waits.length > 0 && <><h4>정해야 할 것</h4><ul>{waits.map(w => <li key={w}>{w}</li>)}</ul></>}
        </aside>
      )}
    </div>
  );
}

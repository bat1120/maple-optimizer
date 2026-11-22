// AI 답변의 마크다운을 화면 요소로 바꾼다: 굵게(**), 표(| |), 제목(#), 목록(- / 1.), 문단.
// 2026-11-22 화면 검증에서 답변의 ** 와 | 가 기호 그대로 보였다. 라이브러리 없이 React 요소만 만든다(HTML을 문자열로 넣지 않는다).

function inline(text) {
  // 백틱(`아이템 이름`)은 기호만 떼고 글자는 그대로 둔다 — 2026-11-23 운영 화면에서 `도미네이터 펜던트`가 기호째 보였다
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <strong key={i}>{part.slice(2, -2).replace(/`([^`\n]+)`/g, "$1")}</strong> : part.replace(/`([^`\n]+)`/g, "$1"));
}

const cells = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
const isRow = (line) => /^\s*\|.*\|\s*$/.test(line);
const isDivider = (line) => isRow(line) && cells(line).every((c) => /^:?-{2,}:?$/.test(c));
const bullet = (line) => line.match(/^\s*[-*•]\s+(.*)$/);
const numbered = (line) => line.match(/^\s*\d+[.)]\s+(.*)$/);
const heading = (line) => line.match(/^\s*#{1,6}\s+(.*)$/);

export function blocks(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i += 1; continue; }
    if (isRow(line) && lines[i + 1] !== undefined && isDivider(lines[i + 1])) {
      const rows = [];
      let j = i + 2;
      while (j < lines.length && isRow(lines[j])) rows.push(cells(lines[j++]));
      out.push({ type: "table", head: cells(line), rows });
      i = j;
    } else if (heading(line)) {
      out.push({ type: "heading", text: heading(line)[1] });
      i += 1;
    } else if (bullet(line) || numbered(line)) {
      const pick = bullet(line) ? bullet : numbered;
      const items = [];
      while (i < lines.length && pick(lines[i])) items.push(pick(lines[i++])[1]);
      out.push({ type: pick === bullet ? "bullets" : "numbers", items });
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !heading(lines[i]) && !bullet(lines[i]) && !numbered(lines[i])
             && !(isRow(lines[i]) && lines[i + 1] !== undefined && isDivider(lines[i + 1]))) para.push(lines[i++]);
      out.push({ type: "para", lines: para });
    }
  }
  return out;
}

export default function Markdown({ text }) {
  return (
    <div className="answer">
      {blocks(text).map((b, i) => {
        if (b.type === "heading") return <p key={i} className="answer-heading"><strong>{inline(b.text)}</strong></p>;
        if (b.type === "bullets") return <ul key={i}>{b.items.map((t, k) => <li key={k}>{inline(t)}</li>)}</ul>;
        if (b.type === "numbers") return <ol key={i}>{b.items.map((t, k) => <li key={k}>{inline(t)}</li>)}</ol>;
        if (b.type === "table") {
          return (
            <div key={i} className="answer-table">
              <table>
                <thead><tr>{b.head.map((c, k) => <th key={k}>{inline(c)}</th>)}</tr></thead>
                <tbody>{b.rows.map((r, k) => <tr key={k}>{r.map((c, n) => <td key={n}>{inline(c)}</td>)}</tr>)}</tbody>
              </table>
            </div>
          );
        }
        return <p key={i}>{b.lines.map((l, k) => <span key={k}>{k > 0 && <br />}{inline(l)}</span>)}</p>;
      })}
    </div>
  );
}

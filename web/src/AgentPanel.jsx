import { useState } from "react";
import { adminLogin, streamAgent } from "./api.js";

// 관리자 전용 AI 에이전트 채팅. 숫자는 서버가 도구 결과와 대조하고, 대조되지 않은 숫자는 경고로 보여준다.
// 화면 분석에서 읽은 매물을 질문에 붙인다. 엔진 평가 숫자는 붙이지 않는다 — 에이전트가 도구로 다시 계산해야
// 답변 숫자의 출처 검사가 된다.
export function withScreenItems(question, name, items) {
  if (!items?.length) return question;
  const listings = items.map((i) => ({ slot: i.slot || i.read?.category, part: i.read?.part || i.read?.category, name: i.read?.name,
    starforce: i.read?.starforce ?? 0, total: i.read?.total || {}, potentials: i.read?.potentials || [], price: i.read?.price ?? null }));
  return `${question}

[캐릭터: ${name || "미지정"}]
[경매장 화면에서 읽은 매물 — evaluate_listings로 평가해서 답해 줘. 가격이 null이면 가격을 물어봐]
${JSON.stringify(listings)}`;
}

export default function AgentPanel({ name = "", screenItems = [] }) {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]); // Claude에 보낼 {role, content}
  const [log, setLog] = useState([]); // 화면 표시용 이벤트
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const login = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await adminLogin(password);
      setAuthed(true);
      setPassword("");
    } catch (err) {
      setError(err);
    }
  };

  const send = async (e) => {
    e.preventDefault();
    if (!question.trim() || busy) return;
    const messages = [...history, { role: "user", content: withScreenItems(question.trim(), name, screenItems) }];
    setLog((l) => [...l, { type: "user", text: question.trim() }]);
    setQuestion("");
    setBusy(true);
    setError(null);
    let answer = "";
    try {
      await streamAgent(messages, (ev) => {
        if (ev.type === "text") answer += ev.text;
        if (ev.type === "error") setError({ message: ev.message });
        setLog((l) => [...l, ev]);
      });
      setHistory([...messages, ...(answer ? [{ role: "assistant", content: answer }] : [])]);
    } catch (err) {
      setError(err);
      if (err.status === 401) setAuthed(false);
    } finally {
      setBusy(false);
    }
  };

  if (!authed) {
    return (
      <form onSubmit={login} className="panel">
        <h3>AI 에이전트 (관리자)</h3>
        <label>관리자 비밀번호<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <button type="submit">로그인</button>
        {error && <p role="alert" className="error">{error.message}</p>}
      </form>
    );
  }
  return (
    <section className="panel">
      <h3>AI 에이전트</h3>
      {screenItems.length > 0 && <p className="muted">화면 매물 {screenItems.length}개를 함께 보내요</p>}
      <div className="chat">
        {log.map((ev, i) => {
          if (ev.type === "user") return <p key={i} className="me">🙋 {ev.text}</p>;
          if (ev.type === "text") return <p key={i}>{ev.text}</p>;
          if (ev.type === "tool_call") return <p key={i} className="muted">🔧 {ev.name} 호출</p>;
          if (ev.type === "done" && ev.unverified_numbers?.length)
            return <p key={i} className="error">⚠ 검증되지 않은 숫자: {ev.unverified_numbers.join(", ")}</p>;
          return null;
        })}
      </div>
      <form onSubmit={send} className="search">
        <label>질문<input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="내신부레테 50억으로 뭐부터 할까?" /></label>
        <button type="submit" disabled={busy}>보내기</button>
      </form>
      {error && <p role="alert" className="error">{error.message}</p>}
    </section>
  );
}

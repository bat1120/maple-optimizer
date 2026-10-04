import { useState } from "react";
import { adminLogin, streamAgent } from "./api.js";

// 관리자 전용 AI 에이전트 채팅. 숫자는 서버가 도구 결과와 대조하고, 대조되지 않은 숫자는 경고로 보여준다.
export default function AgentPanel() {
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
    const messages = [...history, { role: "user", content: question.trim() }];
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

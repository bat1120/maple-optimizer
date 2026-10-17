import { useEffect, useState } from "react";
import { adminLogin, getAgentQuota, streamAgent } from "./api.js";
import ScreenWatch from "./ScreenWatch.jsx";

// 관리자 전용 AI 에이전트 채팅. 숫자는 서버가 도구 결과와 대조하고, 대조되지 않은 숫자는 경고로 보여준다.
// 화면 분석에서 읽은 매물을 질문에 붙인다. 엔진 평가 숫자는 붙이지 않는다 — 에이전트가 도구로 다시 계산해야
// 답변 숫자의 출처 검사가 된다.
const isListOnly = (i) => !Object.keys(i.read?.total || {}).length && !(i.read?.potentials || []).length;

export function withScreenItems(question, name, items, feeRate = null) {
  const who = name ? `${question}

[조회한 캐릭터: ${name}]` : question;
  const head = feeRate ? `${who}
[경매장 판매 수수료: ${Math.round(feeRate * 1000) / 10}% — fee_rate ${feeRate}]` : who;
  // 목록 행만 읽은 매물(총옵션·잠재 없음)은 평가할 수 없어 보내지 않는다. 대신 같은 이름의 목록 가격을 가격 후보로 쓴다.
  const rows = (items || []).filter((i) => !isListOnly(i));
  if (!rows.length) return head;
  const prices = (n) => (items || []).filter((i) => isListOnly(i) && i.read?.name === n && i.read?.price).map((i) => i.read.price);
  const listings = rows.map((i) => {
    const x = { slot: i.slot || i.read?.category, part: i.read?.part || i.read?.category, name: i.read?.name,
      starforce: i.read?.starforce ?? 0, total: i.read?.total || {}, potentials: i.read?.potentials || [], price: i.read?.price ?? null };
    const cand = x.price == null ? prices(x.name) : [];
    if (i.read?.special_ring_level) x.special_ring_level = i.read.special_ring_level;
    if (i.special_ring_note) x.special_ring_note = i.special_ring_note; // 특수 반지 효과는 실딜에 없다 — 레벨로 비교
    const withCheck = i.unverified_lines?.length ? { ...x, unverified_lines: i.unverified_lines } : x;
    return cand.length ? { ...withCheck, list_prices: cand } : withCheck;
  });
  return `${head}
[경매장 화면에서 읽은 매물 — evaluate_listings로 평가해서 답해 줘. price가 null이면 list_prices 후보로 계산하거나 가격을 물어봐]
${JSON.stringify(listings)}`;
}

export const QUICK_QUESTIONS = ["지금 뭐부터 올리면 돼?", "경매장에서 뭘 검색할까?", "예산 100억으로 뭐 할까?"];

const searchText = (s) => [s.category,
  s.potentials?.length ? `잠재 ${s.potentials.join(" / ")}` : null,
  s.additional?.length ? `에디 ${s.additional.join(" / ")}` : null,
  `${s.min_starforce ?? 0}성 이상`].filter(Boolean).join(" · ");

// AI가 request_auction_screen을 부르면 채팅 안에 뜨는 카드: 검색 조건 → [화면 연결] → 읽은 매물을 [AI에게 보내기](2026-10-12)
function ScreenRequest({ search, note, name, watchProps, onSend, busy }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const ready = items.filter((i) => !isListOnly(i));
  return (
    <div role="group" aria-label="경매장 화면 요청" className="card small">
      <p><strong>경매장에서 이 조건으로 검색해 주세요</strong>{note ? <span className="muted"> — {note}</span> : null}</p>
      <p className="chips"><span className="chip">{searchText(search)}</span></p>
      {!open ? (
        <button type="button" onClick={() => setOpen(true)}>화면 연결</button>
      ) : (
        <>
          <ScreenWatch name={name} admin={false} {...watchProps} onItems={setItems} />
          <button type="button" disabled={!ready.length || busy} onClick={() => onSend(items)}>
            {`매물 ${ready.length}개 AI에게 보내기`}
          </button>
        </>
      )}
    </div>
  );
}

export default function AgentPanel({ name = "", screenItems = [], feeRate = null, initialAuthed = false, watchProps = {},
                                     title = "AI 에이전트", showQuota = false }) {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(initialAuthed);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]); // 모델에 보낼 {role, content}
  const [log, setLog] = useState([]); // 화면 표시용 이벤트
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [quota, setQuota] = useState(null); // 일반 사용자 하루 질문 수(2026-10-17 공개) — 관리자는 제한 없음
  const loadQuota = () => { if (showQuota) getAgentQuota().then(setQuota).catch(() => setQuota(null)); };
  useEffect(loadQuota, [showQuota]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // text: 화면에 보일 질문, items: 같이 보낼 화면 매물(채팅 안 화면 요청 카드에서 온 것 또는 아래 화면 평가)
  const ask = async (text, items = screenItems) => {
    if (!text.trim() || busy) return;
    const messages = [...history, { role: "user", content: withScreenItems(text.trim(), name, items, feeRate) }];
    setLog((l) => [...l, { type: "user", text: text.trim() }]);
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
      loadQuota();
    }
  };
  const send = (e) => { e.preventDefault(); ask(question); };

  if (!authed) {
    return (
      <form onSubmit={login} className="panel">
        <h3>{title} (관리자)</h3>
        <label>관리자 비밀번호<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <button type="submit">로그인</button>
        {error && <p role="alert" className="error">{error.message}</p>}
      </form>
    );
  }
  return (
    <section className="panel">
      <h3>{title}</h3>
      {quota && !quota.admin && <p className="muted small">오늘 남은 질문 {quota.remaining}/{quota.limit}회</p>}
      <p className="muted small">질문과 답변은 품질 확인을 위해 기록돼요(IP는 남기지 않아요).</p>
      {name && <p className="muted">조회한 캐릭터 {name} 기준으로 답해요{screenItems.some((i) => !isListOnly(i)) ? ` · 화면 매물 ${screenItems.filter((i) => !isListOnly(i)).length}개를 함께 보내요` : ""}</p>}
      <div className="chat">
        {log.map((ev, i) => {
          if (ev.type === "user") return <p key={i} className="me">🙋 {ev.text}</p>;
          if (ev.type === "text") return <p key={i}>{ev.text}</p>;
          if (ev.type === "tool_call" && ev.name === "request_auction_screen")
            return <ScreenRequest key={i} search={ev.input || {}} note={ev.input?.note} name={name} watchProps={watchProps} busy={busy}
                                  onSend={(items) => ask("검색한 경매장 매물이에요. 내 캐릭터 기준으로 평가하고 추천해 줘.", items)} />;
          if (ev.type === "tool_call") return <p key={i} className="muted">🔧 {ev.name} 호출</p>;
          if (ev.type === "done" && ev.unverified_numbers?.length)
            return <p key={i} className="error">⚠ 검증되지 않은 숫자: {ev.unverified_numbers.join(", ")}</p>;
          return null;
        })}
      </div>
      {name && (
        <p className="chips" aria-label="바로 물어보기">
          {QUICK_QUESTIONS.map((q) => (
            <button key={q} type="button" className="ghost small" disabled={busy} onClick={() => ask(q)}>{q}</button>
          ))}
        </p>
      )}
      <form onSubmit={send} className="search">
        <label>질문<input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="내신부레테 50억으로 뭐부터 할까?" /></label>
        <button type="submit" disabled={busy}>보내기</button>
      </form>
      {error && <p role="alert" className="error">{error.message}</p>}
    </section>
  );
}

import { useEffect, useRef, useState } from "react";
import { getVisionDataset, postListings, postVision, postVisionCorrect, postVisionEvaluate } from "./api.js";
import { formatMeso, formatPct, formatStat, parsePrice } from "./format.js";
import { createWatcher, frameHash } from "./watch.js";

// 공유한 게임 창(또는 웹 경매장 탭)을 1.5초마다 작게 캡처해 변화를 보고, 화면이 바뀌어 안정되면 서버(GPT 비전)로 보내 평가한다.
// 넥슨 서버에는 아무 요청도 하지 않는다 — 사용자 화면에 보이는 픽셀만 읽는다.

export const browserCapture =
  typeof navigator !== "undefined" && navigator.mediaDevices?.getDisplayMedia
    ? {
        async start() {
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: "window" }, audio: false });
          const video = document.createElement("video");
          video.srcObject = stream;
          video.muted = true;
          await video.play();
          const small = document.createElement("canvas");
          small.width = small.height = 64;
          const big = document.createElement("canvas");
          return {
            hash() {
              const c = small.getContext("2d");
              c.drawImage(video, 0, 0, 64, 64);
              return frameHash(c.getImageData(0, 0, 64, 64));
            },
            image() {
              // 1920(FHD)까지는 줄이지 않는다 — 줄이면 툴팁 숫자를 잘못 읽는다(2026-10-04 측정: 255→2550)
              const scale = Math.min(1, 1920 / (video.videoWidth || 1920));
              big.width = Math.round((video.videoWidth || 1920) * scale);
              big.height = Math.round((video.videoHeight || 900) * scale);
              big.getContext("2d").drawImage(video, 0, 0, big.width, big.height);
              return big.toDataURL("image/jpeg", 0.85);
            },
            stop() { stream.getTracks().forEach((t) => t.stop()); },
          };
        },
      }
    : null;

const TOTAL_LABEL = { HP: "HP", ATK: "공격력", MATK: "마력", "ALL%": "올스탯", BOSS: "보공", IED: "방무", DMG: "데미지" };
const PCT = new Set(["ALL%", "BOSS", "IED", "DMG"]);

export function formatTotals(total) {
  const parts = Object.entries(total || {}).map(([k, v]) => `${TOTAL_LABEL[k] ?? k} ${v}${PCT.has(k) ? "%" : ""}`);
  return parts.length ? `총옵션 ${parts.join(" · ")}` : "총옵션 못 읽음";
}

const lines = (t) => t.split("\n").map((s) => s.trim()).filter(Boolean);

// 잘못 읽은 값 고치기: 정답으로 저장(내 PC 학습 데이터)하고 고친 값으로 다시 평가한다
function EditForm({ item, name, defense, onSaved, onCancel }) {
  const r = item.read || {};
  const [f, setF] = useState({
    name: r.name || "", starforce: String(r.starforce ?? ""), price: r.price ? String(r.price) : "",
    potentials: (r.potential_lines || r.potentials || []).join("\n"), additional: (r.additional || []).join("\n"),
  });
  const [error, setError] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    const price = /^\d+$/.test(f.price) ? Number(f.price) : parsePrice(f.price);
    const fields = { name: f.name.trim(), starforce: f.starforce === "" ? null : Number(f.starforce),
                     potentials: lines(f.potentials), additional: lines(f.additional), price: price ?? null };
    try {
      const res = await postVisionCorrect({ frame_id: item.frame_id, signature: item.signature, name, boss_defense: defense, fields });
      onSaved(res.item);
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <span className="inline">
      <label>이름<input value={f.name} onChange={set("name")} /></label>
      <label>스타포스<input inputMode="numeric" value={f.starforce} onChange={set("starforce")} /></label>
      <label>윗잠 (한 줄에 하나)<textarea rows={3} value={f.potentials} onChange={set("potentials")} /></label>
      <label>에디 (한 줄에 하나)<textarea rows={3} value={f.additional} onChange={set("additional")} /></label>
      <label>가격<input value={f.price} onChange={set("price")} /></label>
      <button type="button" onClick={save}>저장</button> <button type="button" onClick={onCancel}>취소</button>
      {error && <span className="error"> {error}</span>}
    </span>
  );
}

// 화면에서 읽은 내용을 그대로 보여 준다(잘못 읽었는지 사용자가 확인할 수 있게). 가격을 못 읽었으면 직접 넣는다.
function Row({ item, name, defense, onUpdate, onReplace }) {
  const r = item.read || {};
  const [price, setPrice] = useState("");
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const calc = async () => {
    const p = parsePrice(price);
    if (!p) return setError("가격을 예: 45억 3000만 처럼 입력해 주세요.");
    try {
      const res = await postListings(name, { setting: item.setting, boss_defense: defense, listings: [{
        slot: item.slot, part: r.part || r.category || item.slot, name: r.name || "?", total: r.total || {},
        potentials: r.potentials || [], starforce: r.starforce || 0, price: p }] });
      const top = res.ranking[0];
      onUpdate({ ...item, read: { ...r, price: p }, per_100m: top.per_100m, main_stat_gain_per_100m: top.main_stat_gain_per_100m });
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <li>
      <strong>{r.name}</strong>{r.starforce ? <span title={item.starforce_note}> {r.starforce}성{r.starforce_source === "별 세기" ? "" : "(확인 필요)"}</span> : ""} · {r.price ? formatMeso(r.price) : "가격 못 읽음"}
      <br />
      <span className="muted">{formatTotals(r.total)}{r.potentials?.length ? ` · ${r.potentials.join(" / ")}` : ""}</span>
      {item.unverified_lines?.length ? (
        // 공식 큐브 옵션표에 없는 줄: 화면 글자와 다르게 읽었을 수 있다 — 툴팁과 대조해 달라고 알린다
        <span className="error"> · 확인 필요: {item.unverified_lines.join(" / ")}</span>
      ) : null}
      <br />
      {item.evaluated ? (
        <span>
          {item.slot} 자리 · 실딜 {formatPct(item.delta_pct)}
          {item.per_100m != null ? ` · 억당 ${formatPct(item.per_100m)}` : ""}
          {item.main_stat_gain != null ? ` · 환산 ${formatStat(item.main_stat_gain)}` : ""}
          {item.excluded?.length ? <span className="muted"> · 계산 제외: {item.excluded.join(", ")}</span> : null}
        </span>
      ) : (
        <span className="muted">{item.reason || "목록만 보여요 — 툴팁을 띄우면 평가해요"}</span>
      )}
      {item.evaluated && !r.price && name && (
        <span className="inline">
          <input aria-label={`${r.name} 가격`} value={price} placeholder="45억" onChange={(e) => setPrice(e.target.value)} />
          <button type="button" onClick={calc}>억당 계산</button>
        </span>
      )}
      {r.corrected && <span className="muted"> · 고친 값</span>}
      {item.frame_id && name && !editing && <> <button type="button" onClick={() => setEditing(true)}>고치기</button></>}
      {editing && <EditForm item={item} name={name} defense={defense} onCancel={() => setEditing(false)}
                            onSaved={(u) => { setEditing(false); onReplace(item.signature, u); }} />}
      {error && <span className="error"> {error}</span>}
    </li>
  );
}

export default function ScreenWatch({ name, defense, capture, intervalMs = 1500, initialItems = [], onItems, onFeeRate }) {
  const cap = capture === undefined ? browserCapture : capture;
  const [session, setSession] = useState(null);
  const [items, setItems] = useState(initialItems); // signature 기준 중복 없는 목록
  useEffect(() => { onItems?.(items); }, [items, onItems]);
  const [count, setCount] = useState(0);
  const [stats, setStats] = useState(null); // 내 PC 학습 데이터(켜졌을 때만)
  const refreshStats = () => getVisionDataset().then((s) => s.enabled && setStats(s)).catch(() => {});
  const [error, setError] = useState(null);
  const watcher = useRef(createWatcher());
  const seen = useRef(new Set());
  const busy = useRef(false);

  // 캐릭터 조회 전에 읽은 매물: 조회되면 이미 읽은 내용으로 다시 평가한다(비전 재호출 없음)
  useEffect(() => {
    if (!name) return;
    const pending = items.filter((it) => !it.evaluated && it.reason?.startsWith("캐릭터를 먼저"));
    if (!pending.length) return;
    postVisionEvaluate({ name, boss_defense: defense, listings: pending.map((p) => p.read) })
      .then((r) => {
        const bySig = new Map(r.items.map((x, i) => [pending[i].signature, { ...x, signature: pending[i].signature }]));
        bySig.forEach((x, sig) => { if (x.evaluated) seen.current.add(sig); });
        setItems((prev) => prev.map((p) => bySig.get(p.signature) || p));
      })
      .catch((e) => setError(e));
  }, [name, defense]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!session) return undefined;
    const timer = setInterval(async () => {
      if (busy.current) return;
      if (!watcher.current.step(session.hash(), Date.now())) return;
      busy.current = true;
      try {
        const r = await postVision({ image: session.image(), name: name || null, boss_defense: defense, seen: [...seen.current] });
        setCount((c) => c + 1);
        if (r.frame_id) refreshStats();
        if (r.fee_rate != null) onFeeRate?.(r.fee_rate); // 판매 등록 창 등에서 읽은 수수료
        const fresh = r.items.filter((it) => !seen.current.has(it.signature));
        fresh.filter((it) => it.evaluated).forEach((it) => seen.current.add(it.signature));
        if (fresh.length) {
          setItems((prev) => {
            const known = new Set(prev.map((p) => p.signature));
            return [...prev.filter((p) => !fresh.some((f) => f.signature === p.signature && f.evaluated)),
                    ...fresh.filter((f) => !known.has(f.signature) || f.evaluated)];
          });
        }
        setError(null);
      } catch (e) {
        setError(e);
      } finally {
        busy.current = false;
      }
    }, intervalMs);
    return () => clearInterval(timer);
  }, [session, name, defense, intervalMs, onFeeRate]);

  const connect = async () => {
    setError(null);
    if (!cap) return setError({ message: "이 브라우저는 화면 공유를 지원하지 않아요. PC 크롬·엣지에서 열어 주세요." });
    try {
      setSession(await cap.start());
    } catch (e) {
      setError({ message: `화면 공유를 시작하지 못했어요: ${e.message || e}` });
    }
  };
  const disconnect = () => {
    session?.stop();
    setSession(null);
  };

  // 툴팁 없이 목록 행만 읽은 매물은 평가할 수 없으니 한 줄로 접는다
  const isListOnly = (it) => !it.evaluated && !Object.keys(it.read?.total || {}).length && !(it.read?.potentials || []).length;
  const listOnly = items.filter(isListOnly);
  const detailed = items.filter((it) => !isListOnly(it));

  return (
    <section className="panel">
      <h3>경매장 화면 분석 (관리자)</h3>
      <p className="muted">
        공유 창에서 '창' 탭을 골라 게임 창을 공유하세요(게임은 창 모드 권장 — 전체 화면은 검게 잡힐 수 있어요). 웹 경매장 탭도 돼요.
        화면이 바뀔 때마다 매물을 읽어 평가하고, 공유한 화면은 분석을 위해 OpenAI로 전송돼요 — 경매장 화면만 공유해 주세요.
      </p>
      {session ? (
        <p>연결됨 · 분석 {count}회 <button type="button" onClick={disconnect}>연결 끊기</button></p>
      ) : (
        <button type="button" onClick={connect}>경매장 화면 연결</button>
      )}
      {error && <p role="alert" className="error">{error.message}</p>}
      {stats && <p className="muted">학습 데이터: 프레임 {stats.frames}장 · 고친 것 {stats.corrected}건</p>}
      {listOnly.length > 0 && (
        <details>
          <summary>목록에서 본 매물 {listOnly.length}개 (툴팁을 띄우면 평가해요)</summary>
          <p className="muted">{listOnly.map((it) => `${it.read?.name}${it.read?.price ? ` ${formatMeso(it.read.price)}` : ""}`).join(" · ")}</p>
        </details>
      )}
      {detailed.length > 0 && (
        <ul className="plain">
          {detailed.map((it) => (
            <Row key={it.signature} item={it} name={name} defense={defense}
                 onUpdate={(u) => setItems((prev) => prev.map((p) => (p.signature === u.signature ? u : p)))}
                 onReplace={(old, u) => { setItems((prev) => prev.map((p) => (p.signature === old ? u : p))); refreshStats(); }} />
          ))}
        </ul>
      )}
    </section>
  );
}

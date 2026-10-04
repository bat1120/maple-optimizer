import { useEffect, useRef, useState } from "react";
import { postListings, postVision } from "./api.js";
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
              const scale = Math.min(1, 1600 / (video.videoWidth || 1600));
              big.width = Math.round((video.videoWidth || 1600) * scale);
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

// 화면에서 읽은 내용을 그대로 보여 준다(잘못 읽었는지 사용자가 확인할 수 있게). 가격을 못 읽었으면 직접 넣는다.
function Row({ item, name, defense, onUpdate }) {
  const r = item.read || {};
  const [price, setPrice] = useState("");
  const [error, setError] = useState(null);
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
      <strong>{r.name}</strong>{r.starforce ? ` ${r.starforce}성` : ""} · {r.price ? formatMeso(r.price) : "가격 못 읽음"}
      <br />
      <span className="muted">{formatTotals(r.total)}{r.potentials?.length ? ` · ${r.potentials.join(" / ")}` : ""}</span>
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
      {error && <span className="error"> {error}</span>}
    </li>
  );
}

export default function ScreenWatch({ name, defense, capture, intervalMs = 1500, initialItems = [], onItems }) {
  const cap = capture === undefined ? browserCapture : capture;
  const [session, setSession] = useState(null);
  const [items, setItems] = useState(initialItems); // signature 기준 중복 없는 목록
  useEffect(() => { onItems?.(items); }, [items, onItems]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState(null);
  const watcher = useRef(createWatcher());
  const seen = useRef(new Set());
  const busy = useRef(false);

  useEffect(() => {
    if (!session) return undefined;
    const timer = setInterval(async () => {
      if (busy.current) return;
      if (!watcher.current.step(session.hash(), Date.now())) return;
      busy.current = true;
      try {
        const r = await postVision({ image: session.image(), name: name || null, boss_defense: defense, seen: [...seen.current] });
        setCount((c) => c + 1);
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
  }, [session, name, defense, intervalMs]);

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
      {items.length > 0 && (
        <ul className="plain">
          {items.map((it) => (
            <Row key={it.signature} item={it} name={name} defense={defense}
                 onUpdate={(u) => setItems((prev) => prev.map((p) => (p.signature === u.signature ? u : p)))} />
          ))}
        </ul>
      )}
    </section>
  );
}

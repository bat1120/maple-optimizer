import { useEffect, useRef, useState } from "react";
import { postVision } from "./api.js";
import { formatMeso, formatPct, formatStat } from "./format.js";
import { createWatcher, frameHash } from "./watch.js";

// 공유한 경매장 탭을 1.5초마다 작게 캡처해 변화를 보고, 화면이 바뀌어 안정되면 서버(GPT 비전)로 보내 평가한다.
// 넥슨 서버에는 아무 요청도 하지 않는다 — 사용자 화면에 보이는 픽셀만 읽는다.

export const browserCapture =
  typeof navigator !== "undefined" && navigator.mediaDevices?.getDisplayMedia
    ? {
        async start() {
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: "browser" }, audio: false });
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

function Row({ item }) {
  const r = item.read || {};
  return (
    <li>
      <strong>{r.name}</strong>{r.starforce ? ` ${r.starforce}성` : ""}{r.price ? ` · ${formatMeso(r.price)}` : ""}
      {r.potentials?.length ? <span className="muted"> · {r.potentials.join(" / ")}</span> : null}
      <br />
      {item.evaluated ? (
        <span>
          {item.slot} 자리 · 실딜 {formatPct(item.delta_pct)}
          {item.per_100m != null ? ` · 억당 ${formatPct(item.per_100m)}` : ""}
          {item.main_stat_gain != null ? ` · 환산 ${formatStat(item.main_stat_gain)}` : ""}
          {item.excluded?.length ? <span className="muted"> · 계산 제외: {item.excluded.join(", ")}</span> : null}
        </span>
      ) : (
        <span className="muted">목록만 보여요 — 툴팁을 띄우면 평가해요</span>
      )}
    </li>
  );
}

export default function ScreenWatch({ name, defense, capture, intervalMs = 1500 }) {
  const cap = capture === undefined ? browserCapture : capture;
  const [session, setSession] = useState(null);
  const [items, setItems] = useState([]); // signature 기준 중복 없는 목록
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
    if (!cap) return setError({ message: "이 브라우저는 탭 화면 공유를 지원하지 않아요. PC 크롬·엣지에서 열어 주세요." });
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
        웹 경매장 탭을 공유하면 화면이 바뀔 때마다 매물을 읽어 평가해요. 공유한 탭의 화면은 분석을 위해 OpenAI로 전송돼요 — 경매장 탭만 공유해 주세요.
      </p>
      {session ? (
        <p>연결됨 · 분석 {count}회 <button type="button" onClick={disconnect}>연결 끊기</button></p>
      ) : (
        <button type="button" onClick={connect}>경매장 화면 연결</button>
      )}
      {error && <p role="alert" className="error">{error.message}</p>}
      {items.length > 0 && <ul className="plain">{items.map((it) => <Row key={it.signature} item={it} />)}</ul>}
    </section>
  );
}

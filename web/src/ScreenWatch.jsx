import { useEffect, useRef, useState } from "react";
import { getVisionDataset, postListings, postVision, postVisionCorrect, postVisionEvaluate, postVisionScore, postVisionScoreReset } from "./api.js";
import { clipboardText, sampleScouter, scouterInfoUrl } from "./scouter.js";
import { formatMeso, formatPct, formatStat, parsePrice } from "./format.js";
import { createWatcher, tipHash, tipSame } from "./watch.js";

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
          small.width = 256; // 툴팁 칸 비교용(32×32 칸에 가로 8px·세로 4.5px)
          small.height = 144;
          const big = document.createElement("canvas");
          return {
            hash() {
              const c = small.getContext("2d");
              c.drawImage(video, 0, 0, 256, 144);
              return tipHash(c.getImageData(0, 0, 256, 144)); // 남회색(툴팁) 칸만 비교 — 소환수·이펙트 움직임은 무시
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
// 환산 계산기(MapleScouter)에 옮길 변화량 복사 — 그쪽 화면에서 '환산 채우기' 북마크를 누르면 칸에 더해진다(#/scouter)
function CopyScouter({ item, label = "환산용 복사" }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(clipboardText(item.scouter, { price: item.read?.price, delta_pct: item.delta_pct }));
      setDone(true);
    } catch {
      setDone(false);
    }
  };
  return (
    <span className="inline">
      <button type="button" className="ghost small" onClick={copy}>{label}</button>
      {done && <span className="muted small">복사했어요 — <a href={scouterInfoUrl(item.scouter.name)} target="_blank" rel="noopener noreferrer">MapleScouter 열기 ↗</a> → 새로 열린 MapleScouter 탭에서 즐겨찾기 막대의 '환산 채우기'(내 캐릭터로 교체 후 채워요)</span>}
    </span>
  );
}

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
          {item.special_ring_note ? <><br /><span className="error">{item.special_ring_note}</span></> : null}
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
      {item.evaluated && item.scouter && <CopyScouter item={item} />}
      {r.corrected && <span className="muted"> · 고친 값</span>}
      {item.frame_id && name && !editing && <> <button type="button" onClick={() => setEditing(true)}>고치기</button></>}
      {editing && <EditForm item={item} name={name} defense={defense} onCancel={() => setEditing(false)}
                            onSaved={(u) => { setEditing(false); onReplace(item.signature, u); }} />}
      {error && <span className="error"> {error}</span>}
    </li>
  );
}

// admin=false: 일반 유저 화면(2026-10-07) — 채점·학습 데이터·목록 읽기 같은 관리자 기능을 숨기고 오늘 남은 분석 횟수를 보여준다
// 임시(2026-10-07, 테스트용): 경매장을 못 읽을 때 [환산용 복사]→MapleScouter 열기→환산 채우기 흐름을 시험하는 견본 한 줄.
// 실딜·가격 같은 수치는 만들지 않고 MapleScouter 칸에 더할 값(보스 +10%, 크뎀 +5%)만 담는다.
function TestItem({ name, job, level }) {
  const item = { scouter: sampleScouter({ name, job, level }), read: {} };
  return (
    <p className="card small">
      <strong>테스트 템</strong> <span className="muted">(임시 · 보스 데미지 +10%, 크리 데미지 +5%)</span>{" "}
      <CopyScouter item={item} label="테스트 템 복사" />
    </p>
  );
}

export default function ScreenWatch({ name, job, level, defense, capture, intervalMs = 250, initialItems = [], onItems, onFeeRate, admin = true }) {
  const cap = capture === undefined ? browserCapture : capture;
  const [session, setSession] = useState(null);
  const [items, setItems] = useState(initialItems); // signature 기준 중복 없는 목록
  useEffect(() => { onItems?.(items); }, [items, onItems]);
  const [count, setCount] = useState(0);
  const [stats, setStats] = useState(null); // 내 PC 학습 데이터(켜졌을 때만)
  const refreshStats = () => (admin ? getVisionDataset().then((s) => s.enabled && setStats(s)).catch(() => {}) : null);
  const [remaining, setRemaining] = useState(null); // 일반 유저: 오늘 남은 AI 분석 횟수(서버가 센다)
  const [error, setError] = useState(null);
  const [score, setScore] = useState(null); // 장비창 훑기 채점 결과(정답 = 넥슨 API 착용 템)
  // 장비창 툴팁은 '착용 템'으로 분류돼 매물 목록에서 빠진다 — 채점용으로 이름별 마지막 판독을 따로 모은다
  const [equipped, setEquipped] = useState(new Map());
  const reads = [...items.map((i) => i.read || {}), ...equipped.values()];
  const resetScore = async () => {
    try {
      await postVisionScoreReset();
      setEquipped(new Map());
      setScore(null);
    } catch (e) {
      setError(e);
    }
  };
  const scoreReads = async () => {
    try {
      setScore(await postVisionScore({ name, reads }));
    } catch (e) {
      setError(e);
    }
  };
  // 0.25초마다 보고 두 번 연속 같으면 툴팁이 뜬 것으로 본다(0.5초 간격이면 1초 미만으로 훑은 템을 놓친다 — 실측 0.7초 8/20). 툴팁끼리 바뀌면 화면 일부만 바뀌므로 바뀐 칸 비율(3%)도 본다
  // (2026-10-06: 1~2초씩 훑은 착용 템 중 일부만 읽힘 — 평균 차이로는 툴팁 전환을 놓치고, 한 장씩 보내 줄이 넘쳤다)
  // 2026-10-06 2차: 이펙트가 움직이면 화면 전체 비교로는 툴팁을 띄워도 안 멈춘 것으로 봐서 거의 안 보냈다 → 툴팁 칸만 비교
  // 2026-10-06 3차: 별 반짝이 때문에 툴팁이 '멈춘' 적이 없어 별 있는 템을 거의 안 보냈다(25개 대고 5개 인식).
  // 멈춤을 기다리지 않고 바뀌면 0.5초마다 보낸다 — 툴팁 찾기·같은 툴팁 재사용·툴팁 없는 화면 건너뛰기는 서버가 AI 없이 한다.
  const watcher = useRef(createWatcher({ stableFrames: 1, cooldownMs: 500, same: tipSame }));
  const queue = useRef([]); // 읽는 중에 바뀐 화면은 버리지 않고 줄 세운다(최대 120장). 같은 툴팁·툴팁 없는 화면은 서버가 AI 없이 거른다
  // 기본은 툴팁이 뜬 화면만 AI에 보낸다(실측: 툴팁 없는 화면 67%, 판독 0). 가격만 보이는 목록 화면도 읽으려면 켠다
  const [readLists, setReadLists] = useState(false);
  const seen = useRef(new Set());
  const inflight = useRef(0); // AI 판독은 한 장 7~10초 — 동시에 6장까지 보낸다(건너뛸 화면이 AI 판독 뒤에 밀리지 않게)

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
    const timer = setInterval(() => {
      if (watcher.current.step(session.hash(), Date.now())) {
        queue.current.push(session.image());
        if (queue.current.length > 120) queue.current.shift();
      }
      while (inflight.current < 6 && queue.current.length) send(queue.current.shift());
    }, intervalMs);
    const send = (image) => {
      inflight.current += 1;
      (async () => {
        try {
          const r = await postVision({ image, name: name || null, boss_defense: defense, seen: [...seen.current],
                                       tooltips_only: !readLists });
          setCount((c) => c + 1);
          if (r.frame_id) refreshStats();
          if (r.ai_remaining != null) setRemaining(r.ai_remaining);
          if (r.fee_rate != null) onFeeRate?.(r.fee_rate); // 판매 등록 창 등에서 읽은 수수료
          if (r.equipped_items?.length) {
            setEquipped((prev) => {
              const next = new Map(prev);
              r.equipped_items.forEach((x) => x.name && next.set(x.name, x));
              return next;
            });
          }
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
          inflight.current -= 1;
        }
      })();
    };
    return () => clearInterval(timer);
  }, [session, name, defense, intervalMs, onFeeRate, readLists]);

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
      <h3>{admin ? "경매장 화면 분석 (관리자)" : "경매장 화면 평가"}</h3>
      <p className="muted">
        공유 창에서 '창' 탭을 골라 게임 창을 공유하세요(게임은 창 모드 권장 — 전체 화면은 검게 잡힐 수 있어요). 웹 경매장 탭도 돼요.
        화면이 바뀔 때마다 매물을 읽어 평가하고, 공유한 화면은 분석을 위해 OpenAI로 전송돼요 — 경매장 화면만 공유해 주세요.
      </p>
      <p className="muted small">
        매물 옆 [환산용 복사] → MapleScouter에서 북마크 한 번으로 칸에 넣기: <a href="#/scouter">환산 채우기 설치·사용법</a>
      </p>
      {!admin && name && <TestItem name={name} job={job} level={level} />}
      {!admin && (
        <p className="muted small">
          게임 경매장(또는 장비창)에서 매물에 마우스를 0.5초씩 대면, 툴팁을 읽어 내 캐릭터 기준 실딜·억당 효율로 평가해요.
          {" "}읽은 매물의 가격·옵션은 익명 시세 데이터로 쌓여요(IP·화면 이미지는 저장하지 않아요).
          {remaining != null ? <strong> 오늘 남은 분석 {remaining}회</strong> : null}
        </p>
      )}
      <details className="howto">
        <summary>사용 방법</summary>
        <ol>
          <li><strong>PC 크롬·엣지</strong>로 이 화면을 여세요. 휴대폰 브라우저는 화면 공유를 지원하지 않아요.</li>
          <li>메이플을 <strong>창 모드</strong>(또는 창 모드 전체화면)로 두세요. 전체화면이면 공유 화면이 검게 잡힐 수 있어요.</li>
          <li>[경매장 화면 연결]을 누르고, 뜨는 창에서 <strong>'창' 탭 → MapleStory</strong>를 골라 [공유]를 누르세요. 다른 창·전체 화면은 고르지 마세요(개인 정보가 같이 전송돼요).</li>
          <li>게임에서 경매장(또는 장비창)을 열고, 볼 매물에 <strong>마우스를 0.5초쯤</strong> 대세요. 툴팁이 뜬 화면만 읽고, 같은 툴팁은 다시 읽지 않아요.</li>
          <li>아래 목록에 매물이 쌓여요: 내 캐릭터 기준 <strong>실딜 상승·억당 효율</strong>, 들어갈 자리. 위에서 캐릭터를 조회해 둬야 평가돼요.</li>
          <li>다 봤으면 [연결 끊기]. 브라우저 위쪽의 '공유 중지'를 눌러도 돼요.</li>
        </ol>
        <p className="muted small">
          잘 안 될 때: 화면이 검게 나오면 창 모드로 · 툴팁이 화면 밖으로 잘리면 매물 위치를 바꿔서 · 숫자가 틀려 보이면 게임 해상도를 1366×768 이상으로 ·
          스타포스는 툴팁 위 별을 세서 맞추고, 못 세면 '확인 필요'로 표시돼요. 공유한 화면은 판독을 위해 OpenAI로 전송되고 저장하지 않아요.
        </p>
      </details>
      {session ? (
        <p>연결됨 · 분석 {count}회 <button type="button" onClick={disconnect}>연결 끊기</button></p>
      ) : (
        <button type="button" onClick={connect}>경매장 화면 연결</button>
      )}
      {admin && <label className="muted">
        <input type="checkbox" checked={readLists} onChange={(e) => setReadLists(e.target.checked)} />
        {" "}목록 화면도 읽기 (툴팁 없이 가격만 보이는 화면 — AI 토큰을 더 써요)
      </label>}
      {error && <p role="alert" className="error">{error.message}</p>}
      {stats && <p className="muted">학습 데이터: 프레임 {stats.frames}장 · 고친 것 {stats.corrected}건</p>}
      {admin && name && (
        <p className="muted">
          장비창 채점: 게임에서 장비창을 열고 착용 템 위로 마우스를 한 칸에 1초씩 훑은 뒤 누르면, 읽은 값을 넥슨 API의 착용 템(정답)과 비교해요.
          {reads.length ? ` (이 화면에서 읽은 툴팁 ${reads.length}개 — 서버가 기억한 판독도 함께 채점해요)` : " (서버가 기억한 판독으로 채점해요)"}{" "}
          <button type="button" onClick={scoreReads}>장비창 채점</button>{" "}
          <button type="button" onClick={resetScore}>채점 초기화</button>
        </p>
      )}
      {equipped.size > 0 && <p className="muted">착용 템 {equipped.size}개: {[...equipped.keys()].join(", ")}</p>}
      {score && (
        <div>
          <p>착용 템 {score.matched}개 채점 · 항목 정확도 {score.accuracy == null ? "—" : `${(score.accuracy * 100).toFixed(1)}%`} ({score.fields_ok}/{score.fields})
            {score.unmatched.length ? <span className="muted"> · 착용 템과 못 맞춘 판독 {score.unmatched.length}개</span> : null}</p>
          <ul className="plain">
            {score.items.map((it) => (
              <li key={it.name} className={it.miss.length ? "error" : "muted"}>
                {it.miss.length ? `✗ ${it.name} ${it.ok}/${it.n} — ${it.miss.join(" / ")}` : `✓ ${it.name} ${it.ok}/${it.n}`}
              </li>
            ))}
          </ul>
          <p className="muted">{score.note}</p>
        </div>
      )}
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

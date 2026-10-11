import { useEffect, useRef, useState } from "react";
import { gradeClass } from "./grades.js";
import { EmptyState } from "../ui/Guide.jsx";

// 장비창 = 게임 장비창 배치(5열×6줄, 2026-10-11 심사 4회차: 유저 판사 '게임과 달라 어색'). [부위, 열, 줄]
//   반지4  ·      모자     ·        엠블렘
//   반지3  펜던트2 얼굴장식  ·        뱃지
//   반지2  펜던트  눈장식   귀고리    훈장
//   반지1  무기    상의     어깨장식  보조무기
//   포켓   벨트    하의     장갑     망토
//   예비 특수 반지 · 신발   ·        기계 심장
export const LAYOUT = [
  ["반지4", 1, 1], ["모자", 3, 1], ["엠블렘", 5, 1],
  ["반지3", 1, 2], ["펜던트2", 2, 2], ["얼굴장식", 3, 2], ["뱃지", 5, 2],
  ["반지2", 1, 3], ["펜던트", 2, 3], ["눈장식", 3, 3], ["귀고리", 4, 3], ["훈장", 5, 3],
  ["반지1", 1, 4], ["무기", 2, 4], ["상의", 3, 4], ["어깨장식", 4, 4], ["보조무기", 5, 4],
  ["포켓 아이템", 1, 5], ["벨트", 2, 5], ["하의", 3, 5], ["장갑", 4, 5], ["망토", 5, 5],
  ["예비 특수 반지", 1, 6], ["신발", 3, 6], ["기계 심장", 5, 6],
];

function Slot({ slot, col, row, item, open, onOpen }) {
  const style = { gridColumn: col, gridRow: row };
  if (!item) return <div className="slot slot-empty" style={style} title={slot}><span className="slot-label">{slot}</span></div>;
  return (
    <button type="button" className={`slot ${gradeClass(item.potential_grade)}${open ? " open" : ""}`} style={style}
            aria-label={`${slot} ${item.name}`} aria-expanded={open} onClick={onOpen} title={`${slot} · ${item.name}`}>
      {item.icon ? <img src={item.icon} alt="" width={38} height={38} /> : <span className="slot-abbr" aria-hidden="true">{item.name.slice(0, 2)}</span>}
      {item.starforce > 0 && <span className="star-badge">★{item.starforce}</span>}
      {item.special_ring_level > 0 && <span className="ring-badge">Lv.{item.special_ring_level}</span>}
      <span className="slot-name">{item.name}</span>
      <span className="slot-label">{slot}</span>
    </button>
  );
}

// 별 줄: 강화된 별만 5개씩 묶는다(아이템별 최대 성 수는 API에 없어 빈 별은 그리지 않는다)
function StarRow({ count }) {
  if (!count) return null;
  const groups = Array.from({ length: Math.ceil(count / 5) }, (_, g) => "★".repeat(Math.min(5, count - g * 5)));
  return (
    <p className="tip-stars">
      <span className="sr-only">스타포스 {count}성</span>
      {groups.map((s, i) => <span key={i} aria-hidden="true">{s}</span>)}
    </p>
  );
}

// 스탯 줄(게임 툴팁 문법): 'STR : +150 (100 +30 +8 +12)' — 기본(흰)·추옵(연두)·주문서(보라)·강화(노랑)·익셉셔널(빨강)
const PARTS = [["base", "기본"], ["add", "추가옵션"], ["etc", "주문서"], ["sf", "스타포스"], ["exc", "익셉셔널"]];
const num = (v, pct) => `${Number.isInteger(v) ? v : v.toFixed(1)}${pct ? "%" : ""}`;
function StatLines({ stats }) {
  if (!stats?.length) return null;
  return (
    <ul className="plain tip-stat-lines" aria-label="장비 스탯">
      {stats.map((l) => {
        const parts = PARTS.filter(([k]) => l[k]);
        const split = parts.length > 1 || (parts.length === 1 && parts[0][0] !== "base");
        return (
          <li key={l.label} className={split ? "tip-up" : undefined}>
            {l.label} : +{num(l.total, l.pct)}
            {split && (
              <span className="tip-parts"> ({parts.map(([k, name], i) => (
                <span key={k} className={`tip-${k}`} title={name}>{i ? " +" : ""}{num(l[k], l.pct)}</span>
              ))})</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// 상세 = 게임 툴팁 순서: 별 줄 → 이름 → 스탯 줄 → 잠재 블록 → 에디 블록
function Detail({ item }) {
  return (
    <section className="item-detail tooltip" aria-label={`${item.name} 상세`}>
      <StarRow count={item.starforce} />
      <h4 className={`tip-name ${gradeClass(item.potential_grade)}`}>{item.name}</h4>
      <div className="tip-head">
        {item.icon && <img className={`tip-icon ${gradeClass(item.potential_grade)}`} src={item.icon} alt="" width={48} height={48} />}
        <p className="tip-meta">{item.slot}{item.level ? ` · ${item.level}제` : ""}{item.starforce ? ` · ${item.starforce}성` : ""}</p>
      </div>
      <StatLines stats={item.stats} />
      <div className="lines">
        <div className="tip-block">
          <span className={`grade-tag ${gradeClass(item.potential_grade)}`}>잠재 {item.potential_grade || "없음"}</span>
          <ul className="plain">{item.potentials.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
        <div className="tip-block">
          <span className={`grade-tag ${gradeClass(item.additional_grade)}`}>에디 {item.additional_grade || "없음"}</span>
          <ul className="plain">{item.additional.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
      </div>
    </section>
  );
}

// 목록 보기(maple.gg 문법): 아이콘 · 부위 · 이름 · ★성 · 잠재/에디 줄
function ItemList({ items }) {
  return (
    <ul className="item-list" aria-label="장비 목록">
      {items.map((it) => (
        <li key={it.slot} className={`item-card ${gradeClass(it.potential_grade)}`}>
          <div className="item-head">
            {it.icon ? <img src={it.icon} alt="" width={36} height={36} /> : <span className="slot-abbr" aria-hidden="true">{it.name.slice(0, 2)}</span>}
            <div className="item-title">
              <span className="item-slot">{it.slot}</span>
              <strong>{it.name}</strong>
              {it.starforce > 0 && <span className="star-chip">★{it.starforce}</span>}
            </div>
          </div>
          <dl className="item-lines">
            <div><dt className={gradeClass(it.potential_grade)}>잠재</dt><dd>{(it.potentials || []).join(" · ") || "—"}</dd></div>
            <div><dt className={gradeClass(it.additional_grade)}>에디</dt><dd>{(it.additional || []).join(" · ") || "—"}</dd></div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

export default function EquipmentGrid({ presets, active, image, name }) {
  const keys = Object.keys(presets || {});
  const [preset, setPreset] = useState(keys.includes(String(active)) ? String(active) : keys[0]);
  // PC는 처음에 무기 툴팁을 열어 둔다(오른쪽 칸이 비지 않게). 휴대폰은 툴팁이 장비창 아래로 길게 붙어
  // 페이지를 밀어내므로 닫아 두고, 칸을 누르면 툴팁으로 스크롤한다(2026-10-11 심사 5회차).
  const wide = typeof window !== "undefined" && window.matchMedia?.("(min-width: 721px)").matches;
  const first = wide ? "무기" : null;
  const [openSlot, setOpenSlot] = useState(first);
  const detailRef = useRef(null);
  const userOpened = useRef(false);
  useEffect(() => {
    if (!wide && userOpened.current && openSlot) detailRef.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [openSlot, wide]);
  const [view, setView] = useState("grid"); // grid = 장비창, list = 목록
  if (!keys.length) {
    return (
      <section className="card equipment">
        <h3 className="panel-title">장비</h3>
        <EmptyState title="불러온 장비가 없어요">넥슨 Open API가 장비 정보를 주지 않았어요. [정보 갱신]으로 다시 불러와 보세요.</EmptyState>
      </section>
    );
  }
  const items = presets[preset] || [];
  const bySlot = Object.fromEntries(items.map((it) => [it.slot, it]));
  const opened = openSlot && bySlot[openSlot];
  return (
    <section className="card equipment">
      <div className="equipment-head">
        <div className="panel-head-text">
          <h3 className="panel-title">장비</h3>
          <p className="panel-sub">칸을 누르면 잠재·에디 옵션이 열려요. 테두리 색 = 잠재 등급</p>
        </div>
        <div className="equipment-tools">
          <div className="seg" role="group" aria-label="장비 프리셋">
            {keys.map((k) => (
              <button key={k} type="button" className={k === preset ? "on" : ""} aria-pressed={k === preset}
                      onClick={() => { setPreset(k); setOpenSlot(first); }}>프리셋 {k}</button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="장비 보기">
            <button type="button" className={view === "grid" ? "on" : ""} aria-pressed={view === "grid"} onClick={() => setView("grid")}>장비창</button>
            <button type="button" className={view === "list" ? "on" : ""} aria-pressed={view === "list"} onClick={() => setView("list")}>목록</button>
          </div>
        </div>
      </div>
      {view === "grid" ? (
        <div className="equip-body">
          <div>
            <div className="equip-grid">
              {LAYOUT.map(([slot, col, row]) => (
                <Slot key={slot} slot={slot} col={col} row={row} item={bySlot[slot]} open={openSlot === slot}
                      onOpen={() => { userOpened.current = true; setOpenSlot(openSlot === slot ? null : slot); }} />
              ))}
              {/* 게임에서도 비는 자리(4열 1~2줄)에 캐릭터를 둔다 */}
              <div className="equip-avatar" style={{ gridColumn: 4, gridRow: "1 / span 2" }}>
                {image ? <img src={image} alt={`${name} 캐릭터`} /> : <span className="muted small">캐릭터</span>}
              </div>
            </div>
            <div className="grade-legend muted small" aria-label="잠재 등급 색">
              {["레어", "에픽", "유니크", "레전드리"].map((g) => <span key={g}><i className={`swatch ${gradeClass(g)}`} />{g}</span>)}
            </div>
          </div>
          {/* 츄츄지지 문법: 오른쪽 고정 칸에 선택한 장비의 게임 툴팁 */}
          <div className="equip-detail" ref={detailRef}>
            {opened ? <Detail item={opened} /> : <p className="detail-empty muted small">장비 칸을 누르면 여기에 게임 툴팁처럼 옵션이 보여요.</p>}
          </div>
        </div>
      ) : (
        <ItemList items={items} />
      )}
    </section>
  );
}

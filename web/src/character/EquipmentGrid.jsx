import { useState } from "react";
import { gradeClass } from "./grades.js";
import { EmptyState } from "../ui/Guide.jsx";

// 장비창(PC 5열: 좌 액세서리 2열 · 가운데 캐릭터 · 우 방어구 2열). 인게임 칸 위치는 확인 못 해 이 구성으로 정했다(설계 Ruling).
// 휴대폰(≤720px)에서는 CSS가 같은 칸을 한 줄 목록으로 바꾼다.
export const LAYOUT = [
  ["반지1", 1, 1], ["반지2", 1, 2], ["반지3", 1, 3], ["반지4", 1, 4], ["포켓 아이템", 1, 5], ["예비 특수 반지", 1, 6],
  ["얼굴장식", 2, 1], ["눈장식", 2, 2], ["귀고리", 2, 3], ["펜던트", 2, 4], ["펜던트2", 2, 5], ["벨트", 2, 6],
  ["무기", 3, 5], ["보조무기", 3, 6],
  ["모자", 4, 1], ["망토", 4, 2], ["상의", 4, 3], ["하의", 4, 4], ["장갑", 4, 5], ["신발", 4, 6],
  ["엠블렘", 5, 1], ["어깨장식", 5, 2], ["기계 심장", 5, 3], ["훈장", 5, 4], ["뱃지", 5, 5],
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

// 상세 = 게임 툴팁 순서: 별 줄 → 이름 → 구분선 → 잠재 블록 → 에디 블록
function Detail({ item }) {
  return (
    <section className="item-detail tooltip" aria-label={`${item.name} 상세`}>
      <StarRow count={item.starforce} />
      <h4 className={`tip-name ${gradeClass(item.potential_grade)}`}>{item.name}</h4>
      <p className="tip-meta">{item.slot}{item.level ? ` · ${item.level}제` : ""}{item.starforce ? ` · ${item.starforce}성` : ""}</p>
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

export default function EquipmentGrid({ presets, active, image, name }) {
  const keys = Object.keys(presets || {});
  const [preset, setPreset] = useState(keys.includes(String(active)) ? String(active) : keys[0]);
  const [openSlot, setOpenSlot] = useState(null);
  if (!keys.length) {
    return (
      <section className="card equipment">
        <h3 className="panel-title">장비</h3>
        <EmptyState title="불러온 장비가 없어요">넥슨 Open API가 장비 정보를 주지 않았어요. [정보 갱신]으로 다시 불러와 보세요.</EmptyState>
      </section>
    );
  }
  const bySlot = Object.fromEntries((presets[preset] || []).map((it) => [it.slot, it]));
  const opened = openSlot && bySlot[openSlot];
  return (
    <section className="card equipment">
      <div className="equipment-head">
        <div className="panel-head-text">
          <h3 className="panel-title">장비</h3>
          <p className="panel-sub">칸을 누르면 잠재·에디 옵션이 열려요. 테두리 색 = 잠재 등급</p>
        </div>
        <div className="seg" role="group" aria-label="장비 프리셋">
          {keys.map((k) => (
            <button key={k} type="button" className={k === preset ? "on" : ""} aria-pressed={k === preset}
                    onClick={() => { setPreset(k); setOpenSlot(null); }}>프리셋 {k}</button>
          ))}
        </div>
      </div>
      <div className="equip-grid">
        {LAYOUT.map(([slot, col, row]) => (
          <Slot key={slot} slot={slot} col={col} row={row} item={bySlot[slot]} open={openSlot === slot}
                onOpen={() => setOpenSlot(openSlot === slot ? null : slot)} />
        ))}
        <div className="equip-avatar" style={{ gridColumn: 3, gridRow: "1 / span 4" }}>
          {image ? <img src={image} alt={`${name} 캐릭터`} /> : <span className="muted small">캐릭터</span>}
        </div>
      </div>
      <div className="grade-legend muted small" aria-label="잠재 등급 색">
        {["레어", "에픽", "유니크", "레전드리"].map((g) => <span key={g}><i className={`swatch ${gradeClass(g)}`} />{g}</span>)}
      </div>
      {opened && <Detail item={opened} />}
    </section>
  );
}

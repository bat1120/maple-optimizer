import { useState } from "react";
import { gradeClass } from "./grades.js";

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
      {item.icon ? <img src={item.icon} alt="" /> : <span className="slot-abbr" aria-hidden="true">{item.name.slice(0, 2)}</span>}
      {item.starforce > 0 && <span className="star-badge">★{item.starforce}</span>}
      {item.special_ring_level > 0 && <span className="ring-badge">Lv.{item.special_ring_level}</span>}
      <span className="slot-name">{item.name}</span>
      <span className="slot-label">{slot}</span>
    </button>
  );
}

function Detail({ item }) {
  return (
    <section className="card item-detail" aria-label={`${item.name} 상세`}>
      <h4>{item.name} <span className="muted small">{item.slot}{item.level ? ` · ${item.level}제` : ""}{item.starforce ? ` · ${item.starforce}성` : ""}</span></h4>
      <div className="lines">
        <div>
          <span className={`grade-tag ${gradeClass(item.potential_grade)}`}>잠재 {item.potential_grade || "없음"}</span>
          <ul className="plain">{item.potentials.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
        <div>
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
  if (!keys.length) return null;
  const bySlot = Object.fromEntries((presets[preset] || []).map((it) => [it.slot, it]));
  const opened = openSlot && bySlot[openSlot];
  return (
    <section className="card equipment">
      <div className="equipment-head">
        <h3>장비</h3>
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
      {opened && <Detail item={opened} />}
    </section>
  );
}

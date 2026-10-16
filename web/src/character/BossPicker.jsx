// 보스 고르기(2026-10-11): 보스 목록(/api/bosses, 나무위키·공지 출처)에서 보스·난이도를 고르거나 방어율을 직접 넣는다.
// value: 보스 id(문자열) 또는 방어율 숫자(직접 입력). 포스 보정은 서버가 계산하고 ForceNote가 그 결과를 보여 준다.
const CUSTOM = "custom";

export const bossLabel = (b) => [b.name, b.difficulty, b.phase].filter(Boolean).join(" ");

export default function BossPicker({ value, bosses = [], onChange }) {
  const custom = typeof value !== "string";
  const pick = (id) => {
    if (id !== CUSTOM) return onChange(id);
    const cur = bosses.find((b) => b.id === value);
    onChange(cur ? cur.defense : 300);
  };
  return (
    <>
      <label className="field">보스
        <select value={custom ? CUSTOM : value} onChange={(e) => pick(e.target.value)}>
          {bosses.map((b) => (
            <option key={b.id} value={b.id}>{`${bossLabel(b)} (방어율 ${b.defense}%)`}</option>
          ))}
          <option value={CUSTOM}>직접 입력(방어율)</option>
        </select>
      </label>
      {custom && (
        <label className="field">보스 방어율(%)
          <input type="number" inputMode="numeric" value={value} onChange={(e) => onChange(Number(e.target.value) || 0)} />
        </label>
      )}
    </>
  );
}

// 서버 응답의 force: { kind, required, current, damage_pct } — 요구 포스가 없는 보스는 null
export function ForceNote({ force }) {
  if (!force) return null;
  if (force.current == null) {
    return <p className="muted small">요구 {force.kind} {force.required} — 지금 포스를 몰라 보정하지 않았어요</p>;
  }
  const short = force.damage_pct < 100;
  return (
    <p className={short ? "small force-short" : "muted small"} role={short ? "status" : undefined}>
      {`요구 ${force.kind} ${force.required}, 지금 ${force.current} — 피해 ${force.damage_pct}%`}
    </p>
  );
}

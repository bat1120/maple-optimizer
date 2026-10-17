import { useState } from "react";

// 펼칠 때만 안을 그리고(=계산을 부르고) 접으면 치운다(2026-10-17 업그레이드 탭 정리 — 패널 5개가 한꺼번에 계산해
// 처음 온 사람이 헷갈리고 서버도 바빴다). 자주 쓰지 않는 패널을 감싼다
export default function LazyPanel({ label, hint, children }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="card lazy-panel">
      <button type="button" className="ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? `${label} 접기` : `${label} 펼치기`}
      </button>
      {!open && hint && <p className="muted small">{hint}</p>}
      {open && children}
    </section>
  );
}

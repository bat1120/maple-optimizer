import Icon from "./icons.jsx";

// 패널 머리말: 제목 + '이 화면에서 할 수 있는 것' 한 줄 + 오른쪽 동작(버튼 등).
export function PanelHead({ title, subtitle, icon, level = 3, children }) {
  const H = `h${level}`;
  return (
    <header className="panel-head">
      <div className="panel-head-text">
        <H className="panel-title">{icon && <Icon name={icon} className="panel-icon" />}{title}</H>
        {subtitle && <p className="panel-sub">{subtitle}</p>}
      </div>
      {children && <div className="panel-actions">{children}</div>}
    </header>
  );
}

// 접히는 '사용 방법' — 번호 단계 2~4개. 실제로 있는 기능만 적는다.
export function HowTo({ steps, title = "사용 방법", note, open = false }) {
  return (
    <details className="howto guide" open={open}>
      <summary><Icon name="info" size={16} />{title}</summary>
      <ol className="steps">
        {steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
      {note && <p className="muted small guide-note">{note}</p>}
    </details>
  );
}

// 빈 상태: 무엇이 없는지 + 다음에 할 일.
export function EmptyState({ icon = "box", title, children, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon name={icon} size={22} /></span>
      <div>
        <p className="empty-title">{title}</p>
        {children && <p className="muted small">{children}</p>}
        {action}
      </div>
    </div>
  );
}

// 오류 상태: 서버가 준 문구 그대로 + 다시 시도.
export function ErrorState({ message, onRetry, children }) {
  return (
    <div className="card error-card" role="alert">
      <span className="error-icon"><Icon name="alert" size={20} /></span>
      <div className="error-body">
        <p className="error-title">{message}</p>
        {children && <p className="muted small">{children}</p>}
      </div>
      {onRetry && <button type="button" onClick={onRetry}><Icon name="refresh" size={16} />다시 시도</button>}
    </div>
  );
}

// 패널 안 짧은 로딩 막대(내용 모양 뼈대)
export function RowsSkeleton({ rows = 3 }) {
  return (
    <div className="skeleton rows-skel" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => <span key={i} />)}
    </div>
  );
}

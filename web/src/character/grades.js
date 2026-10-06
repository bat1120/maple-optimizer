// 잠재 등급 → CSS 클래스(색은 styles.css 토큰 --grade-*). 공식 hex를 못 찾아 인게임 계열색으로 정한 임시값(설계 Ruling).
export const GRADE_CLASS = { 레어: "rare", 에픽: "epic", 유니크: "unique", 레전드리: "legendary" };
export const gradeClass = (g) => (GRADE_CLASS[g] ? `grade-${GRADE_CLASS[g]}` : "grade-none");

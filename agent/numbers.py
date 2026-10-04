"""숫자 출처 검사: 답변에 나온 계산 숫자가 도구 입력·결과에 실제로 있는지 본다 (스펙 §10 "숫자 원칙").

- "45억 3000만", "1.2억", "3000만" → 메소로 환산해 비교 ("2만의"처럼 조사가 붙은 "만"은 '오직'이라 숫자가 아니다)
- "2.765%" → 그대로 또는 도구 값×100(0~1 확률)과 비교
- 30 이하 소수점 없는 정수(성·프리셋·레벨 같은 서수)는 검사하지 않는다
- 허용 오차: 답변 숫자의 표시 자릿수 반올림 범위, 최소 0.1%
"""
import re

_EOK = re.compile(r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*만)?")
_MAN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*만(?![의이을를으에은는도과와만])")  # "프리셋 2만의" = 오직
_NUM = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(%|배)?")


def _decimals(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


def extract(text: str) -> list[tuple[str, float, float]]:
    """(원문, 값, 표시 단위) 목록. 표시 단위는 반올림 허용 폭 계산에 쓴다."""
    out, used = [], []
    for m in _EOK.finditer(text):
        eok, man = m[1], m[2]
        value = float(eok) * 1e8 + (float(man) * 1e4 if man else 0)
        unit = 1e4 if man else 1e8 * 10 ** -_decimals(eok)
        out.append((m[0], value, unit))
        used.append(m.span())
    for m in _MAN.finditer(text):
        if any(a <= m.start() < b for a, b in used):
            continue
        out.append((m[0], float(m[1]) * 1e4, 1e4 * 10 ** -_decimals(m[1])))
        used.append(m.span())
    for m in _NUM.finditer(text):
        if any(a <= m.start() < b for a, b in used):
            continue
        raw = m[1].replace(",", "")
        value = float(raw)
        if m[2] is None and "." not in raw and value <= 30:
            continue
        out.append((m[0], value, 10 ** -_decimals(raw)))
    return out


def _numbers(obj, acc):
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, str):  # 잠재 문자열 "INT +12%", 아이템 설명 속 숫자도 출처다
        acc.extend(v for _, v, _ in extract(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers(v, acc)
    return acc


def unverified_numbers(text: str, sources: list) -> list[str]:
    values = _numbers(sources, [])
    values += [abs(v) for v in values if v < 0]  # 답변의 "-10.43%"는 부호 없이 추출된다
    candidates = values + [v * 100 for v in values if -1 <= v <= 1] + [(v - 1) * 100 for v in values if 0 < v < 10]
    bad = []
    for raw, n, unit in extract(text):
        tol = lambda v: max(0.5 * unit, 0.001 * abs(v))  # noqa: E731
        if not any(abs(n - v) <= tol(v) for v in candidates):
            bad.append(raw.strip())
    return bad

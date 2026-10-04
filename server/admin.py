"""관리자 인증(비밀번호 해시 + 서명 쿠키)과 에이전트 일일 토큰 사용량. 표준 라이브러리만 쓴다.

비밀번호 해시 만들기: uv run python -c "from server.admin import make_password_hash as h; print(h('비밀번호'))"
→ .env 의 ADMIN_PASSWORD_HASH 에 넣는다. SESSION_SECRET 은 32자 이상 임의 문자열.
"""
import datetime as dt
import hashlib
import hmac
import secrets
import sqlite3
from collections.abc import Callable

COOKIE = "mo_admin"
SESSION_TTL = 12 * 3600


def make_password_hash(password: str, iterations: int = 200_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it)).hex()
    return hmac.compare_digest(got, digest)


def sign_session(secret: str, now: float) -> str:
    exp = str(int(now + SESSION_TTL))
    return f"{exp}.{hmac.new(secret.encode(), exp.encode(), hashlib.sha256).hexdigest()}"


def valid_session(token: str | None, secret: str, now: float) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    good = hmac.new(secret.encode(), exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and exp.isdigit() and int(exp) > now


class UsageStore:
    """하루(KST) 단위 에이전트 토큰 사용량."""

    def __init__(self, path: str, clock: Callable[[], float]):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS agent_usage (day TEXT PRIMARY KEY, tokens INTEGER)")
        self._clock = clock

    def _day(self) -> str:
        kst = dt.timezone(dt.timedelta(hours=9))
        return dt.datetime.fromtimestamp(self._clock(), kst).date().isoformat()

    def used(self) -> int:
        row = self._db.execute("SELECT tokens FROM agent_usage WHERE day = ?", (self._day(),)).fetchone()
        return row[0] if row else 0

    def add(self, tokens: int) -> None:
        self._db.execute("INSERT INTO agent_usage VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET tokens = tokens + ?",
                         (self._day(), tokens, tokens))
        self._db.commit()

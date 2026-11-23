"""버프 없는 기준(2026-11-23): 넥슨 스탯창은 접속 종료 시점 값이라 그때 켜져 있던 버프가 섞인다.
실측(같은 캐릭터 15일치): 장비·세팅이 같은데 데미지 91→209%, 최종뎀 186.7→220.7%. 이때 잠재·에디 추천의 상승폭이 최대 1.2배 달라지고 1위가 바뀌었다.
과거 날짜들의 잔차 중 가장 낮은 값을 기준으로 쓰면 같은 답이 나온다."""
import dataclasses
import datetime as dt

from fastapi.testclient import TestClient

from engine.stats.evaluate import evaluate_setting, swap_item
from engine.stats.model import StatBlock
from engine.stats.metrics import BossProfile
from engine.stats.residual import _raw_calibrate, calibrate, clean_floors
from engine.stats.sets import SetCatalog
from helpers import bundle
from nexon.convert import snapshot
from server.app import create_app

CAT, BOSS = SetCatalog.load(), BossProfile("기준", 300.0)


def _buffed(snap, dmg=118.0, boss=66.0, fd_mult=1.118):
    """스탯창에 버프를 얹은 스냅샷(데미지·보공은 더하고 최종뎀은 곱한다)."""
    f = snap.final
    return dataclasses.replace(snap, final=dataclasses.replace(f, dmg=f.dmg + dmg, boss=f.boss + boss, fd=((1 + f.fd / 100) * fd_mult - 1) * 100))


def test_floors_take_the_lowest_value_per_item():
    clean = snapshot(bundle("레테"))
    a, b = _raw_calibrate(clean, CAT), _raw_calibrate(_buffed(clean), CAT)
    fl = clean_floors([b, a])
    assert fl["dmg"] == a.dmg < b.dmg and fl["boss"] == a.boss and abs(fl["fd_factor"] - a.fd_factor) < 1e-9
    assert clean_floors([]) == {}


def test_buffed_snapshot_with_floors_calibrates_like_the_clean_one():
    clean = snapshot(bundle("레테"))
    buffed = _buffed(clean)
    assert calibrate(buffed, CAT).dmg > calibrate(clean, CAT).dmg                      # 기준이 없으면 버프가 잔차에 들어간다
    fixed = dataclasses.replace(buffed, floors=clean_floors([_raw_calibrate(clean, CAT), _raw_calibrate(buffed, CAT)]))
    x, y = calibrate(fixed, CAT), calibrate(clean, CAT)
    assert (x.dmg, x.boss, x.cd, x.cr) == (y.dmg, y.boss, y.cd, y.cr) and abs(x.fd_factor - y.fd_factor) < 1e-9
    # 주스탯 잔차와 방무는 건드리지 않는다(실제로 변하는 값)
    assert x.stat_pct == _raw_calibrate(buffed, CAT).stat_pct and x.ied_remain == _raw_calibrate(buffed, CAT).ied_remain


def test_recommendation_no_longer_depends_on_buffs_at_logout():
    """같은 장비인데 조회 시점의 버프 때문에 '보공 줄'의 가치가 달라지던 것 — 기준을 쓰면 같아진다."""
    clean = snapshot(bundle("레테"))
    buffed = _buffed(clean)
    setting = clean.active_setting
    def boss_line_gain(s):
        it = s.equipment_presets[setting.equipment]["보조무기"]
        better = dataclasses.replace(it, stats=it.stats + StatBlock(boss=30.0))
        return swap_item(s, setting, "보조무기", better, BOSS, CAT) / evaluate_setting(s, setting, BOSS, CAT)
    fixed = dataclasses.replace(buffed, floors=clean_floors([_raw_calibrate(clean, CAT), _raw_calibrate(buffed, CAT)]))
    assert abs(boss_line_gain(buffed) - boss_line_gain(clean)) > 0.002      # 버프가 섞이면 답이 달라진다
    assert abs(boss_line_gain(fixed) - boss_line_gain(clean)) < 1e-9        # 기준을 쓰면 같다


def test_server_fetches_past_anchor_dates_only_when_enabled(tmp_path):
    calls = []
    def fetch(name, day):
        calls.append(day)
        return bundle("레테")
    now = dt.datetime(2026, 11, 23, 12, tzinfo=dt.timezone(dt.timedelta(hours=9))).timestamp()
    off = TestClient(create_app(fetch, str(tmp_path / "a.sqlite3"), clock=lambda: now))
    assert off.get("/api/character/레테").json()["baseline"] is None
    assert calls == [None]
    calls.clear()
    on = TestClient(create_app(fetch, str(tmp_path / "b.sqlite3"), clock=lambda: now, baseline_dates=2, baseline_background=False))
    body = on.get("/api/character/레테").json()
    assert calls[0] is None and len(calls) == 3
    assert all(d.toordinal() % 4 == 0 and d <= dt.date(2026, 11, 21) for d in calls[1:]) and calls[1] - calls[2] == dt.timedelta(days=4)
    assert body["baseline"] == {"pending": False, "buffed": False, "lowered": [], "note": "최근 며칠의 스탯창과 비교해 버프가 섞이지 않은 것을 확인했어요."}
    calls.clear()
    on.get("/api/character/레테/settings")                                  # 과거 날짜는 캐시에서 — 다시 부르지 않는다
    assert calls == []


def test_baseline_failure_never_breaks_the_lookup(tmp_path):
    from nexon.client import RateLimited
    def fetch(name, day):
        if day is not None:
            raise RateLimited("OPENAPI00007", "호출량 초과", 429)
        return bundle("레테")
    calls = []
    def counting(name, day):
        calls.append(day)
        return fetch(name, day)
    c = TestClient(create_app(counting, str(tmp_path / "c.sqlite3"), baseline_dates=3, baseline_background=False))
    r = c.get("/api/character/레테")
    assert r.status_code == 200 and r.json()["baseline"] is None
    n = len(calls)
    assert c.get("/api/character/레테/settings").status_code == 200
    assert len(calls) == n                                                  # 실패한 뒤에는 잠시 다시 두드리지 않는다


def test_background_fetch_answers_first_then_fills_the_baseline(tmp_path):
    """2026-11-23 사용자 결정: 과거 날짜는 뒤에서 불러온다 — 첫 조회는 바로 답하고 pending, 다 불러오면 다음 조회부터 기준을 쓴다."""
    import threading
    gate, calls = threading.Event(), []
    def fetch(name, day):
        calls.append(day)
        if day is not None:
            gate.wait(5)                                                    # 과거 날짜는 느리다
        return bundle("레테")
    now = dt.datetime(2026, 11, 23, 12, tzinfo=dt.timezone(dt.timedelta(hours=9))).timestamp()
    app = create_app(fetch, str(tmp_path / "d.sqlite3"), clock=lambda: now, baseline_dates=2)
    c = TestClient(app)
    first = c.get("/api/character/레테").json()                              # 과거 날짜를 기다리지 않는다
    assert first["baseline"]["pending"] is True and first["baseline"]["buffed"] is False
    assert c.get("/api/character/레테").json()["baseline"]["pending"] is True
    assert len(app.state.baseline_jobs) == 1                                # 같은 캐릭터로 두 번 시작하지 않는다
    gate.set()
    for t in app.state.baseline_jobs:
        t.join(5)
    done = c.get("/api/character/레테").json()["baseline"]
    assert done["pending"] is False and done["buffed"] is False
    assert [d for d in calls if d is not None] and len([d for d in calls if d is not None]) == 2

import pytest

from engine.enhance.starforce import StarforceConditions, attempt_cost, expected_cost, simulate, transition

BASE = StarforceConditions()


def test_cost_formula_low_and_high_stars():
    assert attempt_cost(200, 0, BASE) == 223200          # 1000 + 200³·1/36 = 223222.2 → 십의 자리 반올림
    expected_17 = round((1000 + 200 ** 3 * 18 ** 2.7 / 150) / 100) * 100
    assert attempt_cost(200, 17, BASE) == expected_17


def test_discount_and_protect_surcharge():
    base16 = attempt_cost(200, 16, BASE)
    assert attempt_cost(200, 16, StarforceConditions(discount30=True)) == pytest.approx(base16 * 0.7)
    # 파괴 방지 추가금(기본의 200%)에는 할인이 붙지 않는다
    assert attempt_cost(200, 16, StarforceConditions(discount30=True, protect=True)) == pytest.approx(base16 * 0.7 + base16 * 2)
    assert attempt_cost(200, 18, StarforceConditions(protect=True)) == attempt_cost(200, 18, BASE)  # 18성은 방지 불가


def test_transitions_and_events():
    assert transition(15, BASE) == pytest.approx((0.315, 0.66445, 0.02055))
    assert transition(15, StarforceConditions(guarantee_5_10_15=True)) == (1.0, 0.0, 0.0)
    assert transition(16, StarforceConditions(protect=True)) == pytest.approx((0.315, 0.685, 0.0))
    s, k, d = transition(20, StarforceConditions(destroy_down30=True))
    assert d == pytest.approx(0.10275 * 0.7) and s == pytest.approx(0.315) and s + k + d == pytest.approx(1)
    assert transition(22, StarforceConditions(destroy_down30=True)) == pytest.approx((0.1575, 0.674, 0.1685))


def test_expected_cost_single_step_closed_form():
    s, k, d = transition(21, BASE)
    c = attempt_cost(200, 21, BASE)
    D = 3_000_000_000
    assert expected_cost(200, 21, 22, D, BASE) == pytest.approx((c + d * D) / s)


def test_basic_restore_is_more_expensive_than_full_when_spare_is_cheap():
    full = expected_cost(200, 17, 22, 0, BASE)
    basic = expected_cost(200, 17, 22, 0, StarforceConditions(restore="basic"))
    assert basic > full


def test_target_above_level_cap_is_error():
    with pytest.raises(ValueError):
        expected_cost(130, 0, 22, 0, BASE)  # 128~137레벨은 20성까지


def test_simulation_is_deterministic_with_seed():
    a = simulate(160, 10, 17, 10**9, BASE, trials=2000, seed=1)
    b = simulate(160, 10, 17, 10**9, BASE, trials=2000, seed=1)
    assert a == b and a.median <= a.p75 <= a.p90

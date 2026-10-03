import math

import pytest

from engine.enhance.cube import CubeTable, cubes_needed, lines_at_least, stat_sum_at_least, success_probability, \
    tier_up_tries

T = CubeTable.load("레전드리/무기/200")


def test_line_probabilities_are_normalized():
    for line in T.lines:
        assert sum(p for _, p in line) == pytest.approx(1.0)


def test_three_boss_lines_equals_product_of_line_probabilities():
    def boss_p(line):
        return sum(p for opt, p in line if any(l.key == "BOSS" for l in opt))
    expected = math.prod(boss_p(line) for line in T.lines)
    assert success_probability(T, lines_at_least("BOSS", 3)) == pytest.approx(expected)


def test_stat_sum_predicate():
    assert success_probability(T, stat_sum_at_least("MATK", True, 0)) == pytest.approx(1.0)
    assert success_probability(T, stat_sum_at_least("MATK", True, 37)) == 0.0  # 12+12+12=36이 최대


def test_cubes_needed_geometric():
    d = cubes_needed(0.1)
    assert d.mean == pytest.approx(10)
    assert d.median == math.ceil(math.log(0.5) / math.log(0.9))


def test_tier_up_with_ceiling():
    p, n = 0.035, 42
    expected = sum(k * p * (1 - p) ** (k - 1) for k in range(1, n)) + n * (1 - p) ** (n - 1)
    d = tier_up_tries(p, n)
    assert d.mean == pytest.approx(expected) and d.p90 <= n


def test_unknown_table_is_error():
    with pytest.raises(KeyError):
        CubeTable.load("에픽/모자/100")

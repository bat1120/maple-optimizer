from tools.collect_skill_shares import merge_job


def test_fewer_samples_do_not_overwrite():
    data = {"jobs": {"렌": {"samples": 6, "shares": {"a": 1.0}}}}
    assert merge_job(data, "렌", {"samples": 1, "shares": {"b": 1.0}}) is False
    assert data["jobs"]["렌"]["samples"] == 6


def test_new_or_larger_sample_replaces():
    data = {"jobs": {"렌": {"samples": 3, "shares": {}}}}
    assert merge_job(data, "렌", {"samples": 3, "shares": {"x": 1.0}}) is True
    assert merge_job(data, "히어로", {"samples": 2, "shares": {}}) is True
    assert data["jobs"]["렌"]["shares"] == {"x": 1.0} and "히어로" in data["jobs"]

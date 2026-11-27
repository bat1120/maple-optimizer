import pytest

from nexon.client import NexonError, RateLimited
from tools.collect_skill_shares import collect, merge_job, rank_classes


def test_fewer_samples_do_not_overwrite():
    data = {"jobs": {"렌": {"samples": 6, "shares": {"a": 1.0}}}}
    assert merge_job(data, "렌", {"samples": 1, "shares": {"b": 1.0}}) is False
    assert data["jobs"]["렌"]["samples"] == 6


def test_new_or_larger_sample_replaces():
    data = {"jobs": {"렌": {"samples": 3, "shares": {}}}}
    assert merge_job(data, "렌", {"samples": 3, "shares": {"x": 1.0}}) is True
    assert merge_job(data, "히어로", {"samples": 2, "shares": {}}) is True
    assert data["jobs"]["렌"]["shares"] == {"x": 1.0} and "히어로" in data["jobs"]


class _Client:
    """랭킹은 주고, n번째 캐릭터 조회부터 err를 던지는 가짜 클라이언트."""
    def __init__(self, err, after=0):
        self.err, self.after, self.calls = err, after, 0

    def _request(self, path, params):
        if path == "ranking/overall":
            return {"ranking": [{"character_name": f"c{i}", "class_name": "히어로"} for i in range(20)]}
        self.calls += 1
        if self.calls > self.after:
            raise self.err
        return {"replay_list": []}

    def get_ocid(self, name):
        return name


def test_rate_limit_stops_collection_instead_of_reading_as_no_record():
    """호출 한도(429)를 '연무장 기록 없음'으로 삼키면 한도에 걸린 채 남은 캐릭터를 끝까지 부른다(2026-11-27 운영 키로 실제 발생)."""
    c = _Client(RateLimited("OPENAPI00007", "Please try again later", 429), after=2)
    with pytest.raises(RateLimited):
        collect(c, "히어로", 3, "2026-11-26")
    assert c.calls == 3                                   # 걸린 그 호출에서 멈췄다
    c = _Client(NexonError("OPENAPI00004", "no record", 400))
    assert collect(c, "히어로", 3, "2026-11-26") is None   # 기록이 없는 것은 전처럼 건너뛴다


def test_rank_class_candidates_try_the_job_group_first():
    """시그너스·레지스탕스·데몬은 랭킹 class의 직업군 이름이 따로라, 그 후보를 먼저 묻고 전의 후보도 그대로 둔다."""
    assert rank_classes("소울마스터")[:2] == ["기사단-소울마스터", "전사-소울마스터"]
    assert rank_classes("데몬어벤져")[0] == "데몬-데몬어벤져" and rank_classes("블래스터")[0] == "레지스탕스-블래스터"
    assert rank_classes("히어로") == ["전사-히어로", "히어로-히어로", "히어로-전체 전직"]

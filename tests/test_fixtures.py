import json

from helpers import ENDPOINTS, FIXTURES, classes, load

FORBIDDEN = {"character_name", "character_guild_name", "character_image", "item_description"}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for x in o:
            yield from _keys(x)


def test_46_classes_with_all_endpoints():
    cs = classes()
    assert len(cs) == 46
    assert "레테" in cs and "제논" in cs and "데몬어벤져" in cs
    for c in cs:
        for ep in ENDPOINTS:
            assert (FIXTURES / c / (ep.replace("/", "_") + ".json")).exists(), (c, ep)


def test_fixtures_are_anonymized():
    for c in classes():
        for ep in ENDPOINTS:
            keys = set(_keys(load(c, ep)))
            assert not keys & FORBIDDEN, (c, ep, keys & FORBIDDEN)
            assert not any(k.endswith("_icon") for k in keys), (c, ep)


def test_directory_name_matches_character_class():
    for c in classes():
        assert load(c, "character/basic")["character_class"] == c

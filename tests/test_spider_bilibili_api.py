import datetime

from spider.utils import clean_html, parse_count, parse_duration, parse_time


def test_parse_count_basic():
    assert parse_count(123) == 123
    assert parse_count("456") == 456
    assert parse_count("1.2万") == 12000
    assert parse_count("3亿") == 300000000
    assert parse_count("-") == 0
    assert parse_count(None) == 0


def test_parse_duration():
    assert parse_duration("12:34") == 754
    assert parse_duration("1:02:03") == 3723
    assert parse_duration(90) == 90
    assert parse_duration("") == 0


def test_clean_html():
    assert clean_html('<em class="keyword">高数</em>') == "高数"
    assert clean_html("&quot;线代&quot;") == '"线代"'


def test_parse_time_seconds_and_ms():
    dt1 = parse_time(1700000000)
    dt2 = parse_time(1700000000000)
    assert isinstance(dt1, datetime.datetime)
    assert isinstance(dt2, datetime.datetime)


def test_normalize_from_detail_uses_search_typename_fallback():
    from spider.bilibili_api import normalize_from_detail

    detail = {
        "bvid": "BV_FAKE",
        "aid": 1,
        "title": "t",
        "desc": "",
        "owner": {"name": "u", "mid": 2, "face": "f"},
        "stat": {"view": 1, "favorite": 0},
        "tid": 208,
        "tname": "",
        "duration": 1,
        "pubdate": 1700000000,
        "pic": "p",
    }

    out = normalize_from_detail(
        detail,
        fallback_title="t",
        fallback_up_name="u",
        fallback_up_mid=2,
        fallback_up_face="f",
        fallback_pic_url="p",
        fallback_bili_tid=208,
        fallback_bili_tname="校园学习",
        source_keyword="k",
        phase="ph",
        subject="sub",
    )

    assert out["bili_tid"] == 208
    assert out["bili_tname"] == "校园学习"

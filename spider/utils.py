import re
import time
from datetime import datetime
from html import unescape
from typing import Any


def clean_html(text: str) -> str:
    """去除 HTML 标签并反转义。"""
    if not text:
        return ""
    return unescape(re.sub(r"<[^>]+>", "", text)).strip()


def parse_count(value: Any) -> int:
    """兼容 B 站常见计数：int / '123' / '1.2万' / '3亿'。"""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    s = str(value).strip().replace(",", "")
    if not s or s == "-":
        return 0

    m = re.fullmatch(r"(\d+(?:\.\d+)?)([万亿]?)", s)
    if not m:
        try:
            return int(float(s))
        except Exception:
            return 0

    num = float(m.group(1))
    unit = m.group(2)
    if unit == "万":
        num *= 10_000
    elif unit == "亿":
        num *= 100_000_000
    return int(num)


def parse_time(timestamp: Any) -> datetime:
    """B 站返回的是时间戳（秒/毫秒），统一转为 datetime。"""
    try:
        ts = int(float(timestamp))
        if ts > 10**12:
            ts //= 1000
        return datetime.fromtimestamp(ts)
    except Exception:
        return datetime.fromtimestamp(time.time())


def parse_duration(duration_str: Any) -> int:
    """支持 '12:34'/'1:02:03' 或 int，返回秒数。"""
    try:
        if isinstance(duration_str, int):
            return duration_str
        if isinstance(duration_str, str) and duration_str.isdigit():
            return int(duration_str)
        if not duration_str:
            return 0

        parts = str(duration_str).split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except Exception:
        return 0


def build_video_url(bvid: str) -> str:
    if not bvid:
        return ""
    return f"https://www.bilibili.com/video/{bvid}"


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0

    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default

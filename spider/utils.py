import re  # 导入 re 模块
import time  # 导入 time 模块
from datetime import datetime  # 从其他模块导入依赖
from html import unescape  # 从其他模块导入依赖
from typing import Any  # 从其他模块导入依赖


def clean_html(text: str) -> str:  # 定义函数：clean_html
    if not text:  # 条件判断
        return ""  # 返回结果
    return unescape(re.sub(r"<[^>]+>", "", text)).strip()  # 返回结果


def parse_count(value: Any) -> int:  # 定义函数：parse_count
    """兼容 B 站常见计数：int / '123' / '1.2万' / '3亿'。"""  # 执行逻辑
    if value is None:  # 条件判断
        return 0  # 返回结果
    if isinstance(value, int):  # 条件判断
        return value  # 返回结果
    if isinstance(value, float):  # 条件判断
        return int(value)  # 返回结果
    s = str(value).strip()  # 设置变量：s
    if not s or s == "-":  # 条件判断
        return 0  # 返回结果
    s = s.replace(",", "")  # 设置变量：s
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([万亿]?)", s)  # 设置变量：m
    if not m:  # 条件判断
        try:  # 开始捕获异常
            return int(float(s))  # 返回结果
        except Exception:  # 异常分支处理
            return 0  # 返回结果
    num = float(m.group(1))  # 设置变量：num
    unit = m.group(2)  # 设置变量：unit
    if unit == "万":  # 条件判断
        num *= 10_000  # 变量赋值/配置
    elif unit == "亿":  # 条件分支
        num *= 100_000_000  # 变量赋值/配置
    return int(num)  # 返回结果


def parse_time(timestamp: Any) -> datetime:  # 定义函数：parse_time
    """B 站返回的是时间戳（秒/毫秒），统一转为 datetime。"""  # 执行逻辑
    try:  # 开始捕获异常
        ts = int(float(timestamp))  # 设置变量：ts
        if ts > 10**12:  # 条件判断
            ts //= 1000  # 变量赋值/配置
        return datetime.fromtimestamp(ts)  # 返回结果
    except Exception:  # 异常分支处理
        return datetime.fromtimestamp(time.time())  # 返回结果


def parse_duration(duration_str: Any) -> int:  # 定义函数：parse_duration
    """支持 '12:34'/'1:02:03' 或 int，返回秒数。"""  # 执行逻辑
    try:  # 开始捕获异常
        if isinstance(duration_str, int):  # 条件判断
            return duration_str  # 返回结果
        if isinstance(duration_str, str) and duration_str.isdigit():  # 条件判断
            return int(duration_str)  # 返回结果
        if not duration_str:  # 条件判断
            return 0  # 返回结果
        parts = str(duration_str).split(":")  # 设置变量：parts
        if len(parts) == 2:  # 条件判断
            return int(parts[0]) * 60 + int(parts[1])  # 返回结果
        if len(parts) == 3:  # 条件判断
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])  # 返回结果
        return 0  # 返回结果
    except Exception:  # 异常分支处理
        return 0  # 返回结果


def build_video_url(bvid: str) -> str:  # 定义函数：build_video_url
    if not bvid:  # 条件判断
        return ""  # 返回结果
    return f"https://www.bilibili.com/video/{bvid}"  # 返回结果


def parse_bool(value: Any, default: bool = False) -> bool:  # 定义函数：parse_bool
    if value is None:  # 条件判断
        return default  # 返回结果
    if isinstance(value, bool):  # 条件判断
        return value  # 返回结果
    if isinstance(value, int):  # 条件判断
        return value != 0  # 返回结果
    s = str(value).strip().lower()  # 设置变量：s
    if s in {"1", "true", "yes", "y", "on"}:  # 条件判断
        return True  # 返回结果
    if s in {"0", "false", "no", "n", "off"}:  # 条件判断
        return False  # 返回结果
    return default  # 返回结果

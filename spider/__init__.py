"""爬虫模块（Spider）：用于采集 B 站高数相关数据。

说明：
- 推荐入口：`python -m spider.bilibili_api`
- 这里保持“轻量”，避免在 import spider 时触发网络/数据库等副作用。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "BiliAPI",
    "BiliSpider",
    "crawl",
    "run_spider",
    "get_existing_bvids",
    "save_to_mysql",
    "CRAWL_CONFIG",
    "MAX_PAGES",
]


def __getattr__(name: str) -> Any:
    """
    延迟导入 spider.bilibili_api，避免：
    - `python -m spider.bilibili_api` 时出现 runpy 的重复导入警告
    - 仅导入 spider.utils 时被动拉起 bilibili_api
    """
    if name in __all__:
        mod = import_module(".bilibili_api", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


"""B 站爬虫模块 - 类封装重构版

提供两个核心类：
- BiliAPI: B站 API 客户端，负责网络请求和 WBI 签名
- BiliSpider: 爬虫主类，负责采集逻辑和数据库操作
"""

import os
import random
import re
import time
from datetime import datetime
from hashlib import md5
from typing import Any, Callable, Dict, List, Optional, Sequence, Set
from urllib.parse import urlencode

# 注：此爬虫仅负责采集数据，分类由 classifier/topic_classifier.py 完成
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# 说明：
# - 推荐从项目根目录用 `python -m spider.bilibili_api` 运行
# - 兼容直接运行脚本：`python spider/bilibili_api.py`
try:
    from spider.utils import (
        build_video_url, clean_html, parse_bool,
        parse_count, parse_duration, parse_time,
    )
except ModuleNotFoundError as e:
    # 当以脚本方式运行时，sys.path[0] 指向 spider/，导致 `import spider` 失败
    if getattr(e, "name", "") not in {"spider", "spider.utils"}:
        raise
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from spider.utils import (
        build_video_url, clean_html, parse_bool,
        parse_count, parse_duration, parse_time,
    )

# 关闭 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# 配置常量
# ============================================================================

# 从 config.py 加载配置（可选）
try:
    from config import BILI_COOKIE
except Exception:
    BILI_COOKIE = ""

# 采集关键词（按三科分类，不含人名 - 由分类脚本识别讲师）
# 分类将由 topic_classifier 脚本自动完成

# 高等数学采集关键词
CALCULUS_KEYWORDS = [
    "高等数学", "微积分",
    "极限", "连续", "无穷小",
    "导数", "微分", "求导", "链式法则",
    "积分", "定积分", "不定积分", "换元", "分部积分",
    "微分方程", "一阶", "二阶", "通解",
    "级数", "幂级数", "泰勒级数", "收敛",
    "多元函数", "偏导", "全微分", "重积分",
]

# 线性代数采集关键词
LINEAR_ALGEBRA_KEYWORDS = [
    "线性代数",
    "行列式", "矩阵", "矩阵运算",
    "向量", "向量空间", "线性相关", "线性无关",
    "线性方程组", "齐次", "非齐次",
    "特征值", "特征向量", "相似", "对角化",
    "二次型", "正定", "负定",
]

# 概率论与数理统计采集关键词
PROBABILITY_KEYWORDS = [
    "概率论", "统计学", "数理统计",
    "概率", "古典概型", "条件概率", "全概率", "贝叶斯",
    "随机变量", "分布", "期望", "方差", "协方差",
    "大数定律", "中心极限定理",
    "假设检验", "置信区间", "点估计",
    "回归分析", "相关系数",
]

# 合并所有关键词
CRAWL_KEYWORDS = CALCULUS_KEYWORDS + LINEAR_ALGEBRA_KEYWORDS + PROBABILITY_KEYWORDS

# 兼容旧代码：将 CRAWL_KEYWORDS 转换为 CRAWL_CONFIG 格式
CRAWL_CONFIG = [{"q": kw, "phase": "", "subject": ""} for kw in CRAWL_KEYWORDS]

MAX_PAGES = 15
REQUEST_TIMEOUT = 15
CRAWL_DELAY_RANGE = (1.8, 3.5)
DETAIL_DELAY_RANGE = (0.4, 0.9)

# WBI 签名用的固定映射表
WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def _get_flask_app():
    """获取 Flask 应用实例，用于数据库操作"""
    from flask import Flask
    from config import Config
    from models import db
    
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app, db


# ============================================================================
# BiliAPI 类 - B站 API 客户端
# ============================================================================

class BiliAPI:
    """B站 API 客户端，封装网络请求和 WBI 签名"""

    def __init__(self, cookie: str = ""):
        self.cookie = (cookie or BILI_COOKIE or "").strip()
        self.headers = self._build_headers()
        self.session = self._create_session()
        self.mixin_key = ""
        self._init_wbi()

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        # 说明：
        # - 仅做“温和重试”，避免网络抖动/偶发 5xx 直接中断
        # - 429/5xx 视为可重试；对 4xx 风控类返回仍需上层做退避/降频
        retry_kwargs = dict(
            total=5,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.8,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
            respect_retry_after_header=True,
        )
        try:
            retries = Retry(**retry_kwargs, backoff_jitter=0.3)
        except TypeError:
            # 兼容较旧 urllib3：没有 backoff_jitter 参数
            retries = Retry(**retry_kwargs)
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def _init_wbi(self):
        """初始化 WBI 签名密钥"""
        try:
            data = self._request("https://api.bilibili.com/x/web-interface/nav")
            if isinstance(data, dict):
                wbi_img = data.get("wbi_img") or {}
                img_url = (wbi_img.get("img_url") or "").strip()
                sub_url = (wbi_img.get("sub_url") or "").strip()
                if img_url and sub_url:
                    img_key = img_url.rsplit("/", 1)[-1].split(".", 1)[0]
                    sub_key = sub_url.rsplit("/", 1)[-1].split(".", 1)[0]
                    s = img_key + sub_key
                    if len(s) >= 64:
                        self.mixin_key = "".join([s[i] for i in WBI_MIXIN_KEY_ENC_TAB])[:32]
        except Exception:
            pass

    def _request(self, url: str, params: Optional[Dict] = None) -> Any:
        """通用请求方法"""
        resp = self.session.get(
            url, headers=self.headers, params=params,
            timeout=REQUEST_TIMEOUT, verify=False
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # B 站风控/限流时可能直接返回 HTML，给出更可读的错误信息
            snippet = (resp.text or "").strip().replace("\n", " ")[:200]
            raise RuntimeError(f"HTTP {resp.status_code}: {snippet}") from e

        try:
            payload = resp.json()
        except ValueError as e:
            snippet = (resp.text or "").strip().replace("\n", " ")[:200]
            raise RuntimeError(f"Non-JSON response: {snippet}") from e

        if payload.get("code") != 0:
            raise RuntimeError(f"API error: {payload.get('code')} {payload.get('message')}")
        return payload.get("data")

    def _sign_params(self, params: Dict) -> Dict:
        """WBI 参数签名"""
        if not self.mixin_key:
            return params
        params = dict(params)
        params["wts"] = int(time.time())
        filtered = {k: re.sub(r"[!'()*]", "", str(v)) for k, v in params.items()}
        query = urlencode(sorted(filtered.items()))
        filtered["w_rid"] = md5((query + self.mixin_key).encode()).hexdigest()
        return filtered

    def search(self, keyword: str, page: int = 1, page_size: int = 20, order: str = "click") -> List[Dict]:
        """搜索视频"""
        if not self.mixin_key:
            return []
        params = self._sign_params({
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "order": order,
        })
        data = self._request("https://api.bilibili.com/x/web-interface/wbi/search/type", params)
        return data.get("result", []) if isinstance(data, dict) else []

    def get_detail(self, bvid: str) -> Dict:
        """获取视频详情"""
        data = self._request("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid})
        return data if isinstance(data, dict) else {}

    def get_tags(self, bvid: str) -> List[Dict]:
        """获取视频标签"""
        data = self._request("https://api.bilibili.com/x/web-interface/view/detail/tag", {"bvid": bvid})
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return data["data"]
        return []


# ============================================================================
# BiliSpider 类 - 爬虫主类
# ============================================================================

class BiliSpider:
    """B站视频爬虫，支持智能分类和数据库存储"""

    def __init__(self, cookie: str = ""):
        self.api = BiliAPI(cookie)
        self._detail_cache: Dict[str, Dict] = {}
        self._flask_app, self._db = _get_flask_app()
        self._tag_cache: Dict[str, List] = {}
        self._topic_classifier = None

    def _cached_fetch(self, cache: Dict[str, Any], key: str, fetch_fn: Callable[[], Any], default_factory: Callable[[], Any]) -> Any:
        """缓存式获取：命中缓存直接返回；未命中则延迟 + 尝试请求；失败回退默认值。"""
        if key in cache:
            return cache[key]
        time.sleep(random.uniform(*DETAIL_DELAY_RANGE))
        try:
            cache[key] = fetch_fn()
        except Exception:
            cache[key] = default_factory()
        return cache[key]

    def _normalize_video(self, detail: Dict, item: Dict) -> Dict:
        """规范化视频数据"""
        stat = detail.get("stat") or {}
        owner = detail.get("owner") or {}
        bvid = detail.get("bvid") or item.get("bvid") or ""

        # 优先使用详情数据，否则用搜索结果
        view = parse_count(stat.get("view") or item.get("play", 0))
        fav = parse_count(stat.get("favorite") or item.get("favorites", 0))

        raw_pic = item.get("pic", "") or ""
        fallback_pic = ("https:" + raw_pic) if raw_pic.startswith("//") else raw_pic

        return {
            "视频ID": bvid,
            "AV号": parse_count(detail.get("aid") or item.get("aid", 0)),
            "视频链接": build_video_url(bvid),
            "标题": clean_html(detail.get("title") or item.get("title") or ""),
            "描述": (detail.get("desc") or "").strip(),
            "UP主名称": owner.get("name") or (item.get("author") or "").strip(),
            "UP主ID": parse_count(owner.get("mid") or item.get("mid", 0)),
            "UP主头像": owner.get("face") or item.get("upic") or "",
            "封面图": detail.get("pic") or fallback_pic,
            "播放量": view,
            "弹幕数": parse_count(stat.get("danmaku") or item.get("video_review", 0)),
            "评论数": parse_count(stat.get("reply") or item.get("review", 0)),
            "收藏数": fav,
            "点赞数": parse_count(stat.get("like", 0)),
            "投币数": parse_count(stat.get("coin", 0)),
            "分享数": parse_count(stat.get("share", 0)),
            "时长": parse_count(detail.get("duration") or parse_duration(item.get("duration", "0"))),
            "发布时间": parse_time(detail.get("pubdate") or item.get("pubdate", time.time())),
            "标签": "",
            "爬取时间": datetime.now(),
        }

    def _merge_tags(self, video: Dict, tags: List[Dict]):
        """合并标签"""
        tag_names = [t.get("tag_name", "").strip() for t in (tags or []) if t.get("tag_name")]
        merged = ",".join(dict.fromkeys(tag_names))
        video["标签"] = merged

    def smart_classify(self, title: str, tags: str = "", desc: str = "") -> str:
        """
        轻量“智能分类”：
        - 仅用于补充一个更结构化的知识点标签（不会替代后续 enrich 流程）
        - 失败时返回空字符串，避免影响爬虫稳定性
        """
        try:
            if self._topic_classifier is None:
                from core.topic_classifier import TopicClassifier
                self._topic_classifier = TopicClassifier()
            topics, _difficulty = self._topic_classifier.classify(title or "", tags or "", desc or "")
            return topics[0] if topics else ""
        except Exception:
            return ""

    def get_existing_bvids(self) -> Set[str]:
        """获取数据库中已存在的 bvid"""
        from models import Video
        try:
            with self._flask_app.app_context():
                result = {v.视频ID for v in Video.query.with_entities(Video.视频ID).all()}
            return result
        except Exception:
            return set()

    def save_to_db(self, data_list: Sequence[Dict]):
        """批量保存到数据库"""
        from models import Video
        if not data_list:
            return
        try:
            with self._flask_app.app_context():
                video_fields = {c.name for c in Video.__table__.columns}
                for item in data_list:
                    bvid = item.get("视频ID")
                    if not bvid:
                        continue

                    data = {k: v for k, v in item.items() if k in video_fields}
                    # 检查是否已存在
                    existing = self._db.session.get(Video, bvid)
                    if existing:
                        # 更新已存在的记录
                        for key, value in data.items():
                            if key != "视频ID":
                                setattr(existing, key, value)
                    else:
                        # 创建新记录
                        self._db.session.add(Video(**data))
                self._db.session.commit()
        except Exception as e:
            print(f"  数据库写入失败: {e}")
            try:
                self._db.session.rollback()
            except Exception:
                pass

    def crawl(
        self,
        tasks: List[Dict] = None,
        max_pages: int = MAX_PAGES,
        save_to_db: bool = True,
        skip_existing: bool = True,
        fetch_detail: bool = True,
        fetch_tags: bool = True,
        progress_cb: Callable = None,
        stop_flag=None,
    ) -> List[Dict]:
        """
        执行爬取任务

        Args:
            tasks: 爬取任务列表，格式 [{"q": "关键词", "phase": "阶段", "subject": "科目"}]
            max_pages: 每个关键词最大爬取页数
            save_to_db: 是否保存到数据库
            skip_existing: 是否跳过已存在视频
            fetch_detail: 是否获取视频详情
            fetch_tags: 是否获取视频标签
            progress_cb: 进度回调函数 (done, total, message)
            stop_flag: 停止标志 (threading.Event)

        Returns:
            爬取到的视频数据列表
        """
        tasks = tasks or CRAWL_CONFIG
        max_pages = max(1, min(max_pages, MAX_PAGES))

        if not self.api.mixin_key:
            if progress_cb:
                progress_cb(0, 1, "WBI 初始化失败，请检查 BILI_COOKIE 配置")
            return []

        # 加载已存在视频
        existing = self.get_existing_bvids() if skip_existing and save_to_db else set()
        if progress_cb and existing:
            progress_cb(0, 1, f"已加载 {len(existing)} 条已采集视频")

        total_steps = len(tasks) * max_pages
        steps_done = 0
        all_results = []
        seen_in_run: Set[str] = set()

        for task in tasks:
            keyword = task.get("q") or task.get("keyword") or ""
            if not keyword:
                continue

            if progress_cb:
                progress_cb(steps_done, total_steps, f"抓取: {keyword}")

            for page in range(1, max_pages + 1):
                if stop_flag and stop_flag.is_set():
                    break

                try:
                    time.sleep(random.uniform(*CRAWL_DELAY_RANGE))
                    items = self.api.search(keyword, page)
                    if not items:
                        break

                    batch, skipped = [], 0
                    for item in items:
                        bvid = item.get("bvid")
                        if not bvid:
                            continue
                        if bvid in seen_in_run:
                            continue
                        if bvid in existing:
                            skipped += 1
                            continue
                        seen_in_run.add(bvid)

                        # 获取详情
                        detail = {}
                        if fetch_detail:
                            detail = self._cached_fetch(
                                self._detail_cache,
                                bvid,
                                lambda: self.api.get_detail(bvid),
                                dict,
                            )

                        # 规范化数据
                        video = self._normalize_video(detail, item)

                        # 获取标签
                        tags = []
                        if fetch_tags:
                            tags = self._cached_fetch(
                                self._tag_cache,
                                bvid,
                                lambda: self.api.get_tags(bvid),
                                list,
                            )
                        self._merge_tags(video, tags)

                        # 智能分类
                        predicted = self.smart_classify(video["标题"], video["标签"] + " " + keyword, video.get("描述", ""))
                        if predicted and predicted not in video["标签"]:
                            video["标签"] = (video["标签"] + "," + predicted).strip(",")

                        batch.append(video)

                    if save_to_db:
                        self.save_to_db(batch)
                    all_results.extend(batch)

                except Exception as e:
                    if progress_cb:
                        progress_cb(steps_done, total_steps, f"  第{page}页异常: {e}")
                    time.sleep(5)

                steps_done += 1
                if progress_cb:
                    skip_msg = f"（跳过{skipped}条）" if skipped else ""
                    progress_cb(steps_done, total_steps, f"{keyword} 第{page}页，新增{len(batch)}条{skip_msg}")

            if stop_flag and stop_flag.is_set():
                break

        return all_results


# ============================================================================
# 兼容性函数 - 保持原有 API 可用
# ============================================================================

# 全局实例（延迟初始化）
_spider: Optional[BiliSpider] = None


def _get_spider() -> BiliSpider:
    global _spider
    if _spider is None:
        _spider = BiliSpider()
    return _spider


def save_to_mysql(data, **kw):
    """兼容旧版函数"""
    _get_spider().save_to_db(data)


def crawl(params=None, progress_cb=None, stop_flag=None) -> List[Dict]:
    """兼容原有 crawl 函数签名"""
    params = params or {}
    spider = _get_spider()
    return spider.crawl(
        tasks=params.get("tasks"),
        max_pages=params.get("max_pages", MAX_PAGES),
        save_to_db=parse_bool(params.get("save_to_db", params.get("save", True)), True),
        skip_existing=parse_bool(params.get("skip_existing", True), True),
        fetch_detail=parse_bool(params.get("fetch_detail", True), True),
        fetch_tags=parse_bool(params.get("fetch_tags", True), True),
        progress_cb=progress_cb,
        stop_flag=stop_flag,
    )


def run_spider():
    """命令行入口"""
    print("爬虫启动...")

    def log_progress(done, total, msg=None):
        if msg:
            print(msg)
        if total:
            print(f"进度: {done}/{total}")

    crawl({"tasks": CRAWL_CONFIG, "max_pages": MAX_PAGES}, progress_cb=log_progress)
    print("爬虫结束")


# 导出旧版函数以保持兼容
get_existing_bvids = lambda: _get_spider().get_existing_bvids()


if __name__ == "__main__":
    run_spider()

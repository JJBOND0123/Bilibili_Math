"""B 站采集脚本：按配置关键词抓取视频 -> 计算核心指标 -> 智能分类 -> 写入 MySQL。"""  # 执行逻辑

import os  # 导入 os 模块
import random  # 导入 random 模块
import re  # 导入 re 模块
import time  # 导入 time 模块
from datetime import datetime  # 从其他模块导入依赖
from hashlib import md5  # 从其他模块导入依赖
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple  # 从其他模块导入依赖

import joblib  # 导入 joblib 模块
import pymysql  # 导入 pymysql 模块
import requests  # 导入 requests 模块
from requests.adapters import HTTPAdapter  # 从其他模块导入依赖
from urllib3.util.retry import Retry  # 从其他模块导入依赖
import urllib3  # 导入 urllib3 模块

from spider.utils import build_video_url, clean_html, parse_bool, parse_count, parse_duration, parse_time  # 从其他模块导入依赖

# 采集时会使用 verify=False 规避部分地区的证书问题，这里提前关闭告警。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # 执行逻辑

# === 1. 加载可选的文本分类模型（没有也能运行，退回关键词规则模式） ===
MODEL_PATH = "subject_classifier.pkl"  # 设置变量：MODEL_PATH
ML_MODEL = None  # 设置变量：ML_MODEL
if os.path.exists(MODEL_PATH):  # 条件判断
    try:  # 开始捕获异常
        ML_MODEL = joblib.load(MODEL_PATH)  # 设置变量：ML_MODEL
        print("AI 模型加载成功")  # 调用函数：print
    except Exception as e:  # 异常分支处理
        print(f"AI 模型加载失败: {e}")  # 调用函数：print
else:  # 兜底分支
    print("未找到 AI 模型，使用关键词规则模式")  # 调用函数：print

# === 2. Cookie/数据库配置（本项目用 config.py 本地变量，避免提交真实凭据） ===
try:  # 开始捕获异常
    from config import BILI_COOKIE  # 从其他模块导入依赖
except Exception:  # 异常分支处理
    BILI_COOKIE = ""  # 设置变量：BILI_COOKIE

COOKIE = (BILI_COOKIE or "").strip()  # 设置变量：COOKIE
if not COOKIE:  # 条件判断
    print("未在 config.py 设置 BILI_COOKIE：将以匿名方式请求，可能更容易触发风控/限流。")  # 调用函数：print

from urllib.parse import parse_qs, unquote, urlencode, urlparse  # 从其他模块导入依赖


def build_db_config_from_sqlalchemy_uri(uri: str) -> Dict[str, Any]:  # 定义函数：build_db_config_from_sqlalchemy_uri
    # 例：mysql+pymysql://root:123456@localhost/bilibili_math_db?charset=utf8mb4
    uri = (uri or '').strip()  # 设置变量：uri
    if not uri:  # 条件判断
        return {}  # 返回结果
    if uri.startswith('mysql+pymysql://'):  # 条件判断
        uri = 'mysql://' + uri[len('mysql+pymysql://'):]  # 设置变量：uri
    parsed = urlparse(uri)  # 设置变量：parsed
    query = parse_qs(parsed.query)  # 设置变量：query
    charset = (query.get('charset', ['utf8mb4']) or ['utf8mb4'])[0]  # 设置变量：charset
    return {  # 返回结果
        'host': parsed.hostname or 'localhost',  # 设置字典字段：host
        'user': unquote(parsed.username or 'root'),  # 设置字典字段：user
        'password': unquote(parsed.password or ''),  # 设置字典字段：password
        'db': (parsed.path or '/').lstrip('/') or 'bilibili_math_db',  # 设置字典字段：db
        'port': parsed.port or 3306,  # 设置字典字段：port
        'charset': charset,  # 设置字典字段：charset
        'cursorclass': pymysql.cursors.DictCursor,  # 设置字典字段：cursorclass
    }  # 结构结束/分隔


try:  # 开始捕获异常
    from config import Config  # 从其他模块导入依赖
    _db_from_uri = build_db_config_from_sqlalchemy_uri(getattr(Config, 'SQLALCHEMY_DATABASE_URI', ''))  # 设置变量：_db_from_uri
except Exception:  # 异常分支处理
    _db_from_uri = {}  # 设置变量：_db_from_uri

DB_CONFIG = _db_from_uri or {  # 设置变量：DB_CONFIG
    'host': 'localhost',  # 设置字典字段：host
    'user': 'root',  # 设置字典字段：user
    'password': '123456',  # 设置字典字段：password
    'db': 'bilibili_math_db',  # 设置字典字段：db
    'port': 3306,  # 设置字典字段：port
    'charset': 'utf8mb4',  # 设置字典字段：charset
    'cursorclass': pymysql.cursors.DictCursor,  # 设置字典字段：cursorclass
}  # 结构结束/分隔

# === 3. 关键词与分类映射配置 ===
CRAWL_CONFIG = [  # 设置变量：CRAWL_CONFIG
    # 校内同步：基础课与典型难点
    {"q": "高等数学 同济第五版", "phase": "校内同步", "subject": "高等数学"},  # 执行逻辑
    {"q": "宋浩 高数", "phase": "校内同步", "subject": "高等数学"},  # 执行逻辑
    {"q": "线性代数 同步", "phase": "校内同步", "subject": "线性代数"},  # 执行逻辑
    {"q": "宋浩 线性代数", "phase": "校内同步", "subject": "线性代数"},  # 执行逻辑
    {"q": "概率论与数理统计 浙大", "phase": "校内同步", "subject": "概率论与数理统计"},  # 执行逻辑
    {"q": "宋浩 概率论", "phase": "校内同步", "subject": "概率论与数理统计"},  # 执行逻辑
    {"q": "泰勒公式 讲解", "phase": "校内同步", "subject": "高等数学"},  # 执行逻辑
    {"q": "中值定理证明", "phase": "校内同步", "subject": "高等数学"},  # 执行逻辑
    {"q": "二重积分", "phase": "校内同步", "subject": "高等数学"},  # 执行逻辑
    {"q": "特征值与特征向量", "phase": "校内同步", "subject": "线性代数"},  # 执行逻辑
    {"q": "极大似然估计", "phase": "校内同步", "subject": "概率论与数理统计"},  # 执行逻辑
    {"q": "高数 期末复习", "phase": "校内同步", "subject": "期末突击"},  # 执行逻辑
    {"q": "线性代数不挂科", "phase": "校内同步", "subject": "期末突击"},  # 执行逻辑
    {"q": "概率论期末速成", "phase": "校内同步", "subject": "期末突击"},  # 执行逻辑
    # 升学备考：考研/专升本名师矩阵/真题
    {"q": "考研数学 基础", "phase": "升学备考", "subject": "考研数学"},  # 执行逻辑
    {"q": "考研数学 强化", "phase": "升学备考", "subject": "考研数学"},  # 执行逻辑
    {"q": "专升本数学", "phase": "升学备考", "subject": "专升本"},  # 执行逻辑
    {"q": "张宇 高数", "phase": "升学备考", "subject": "张宇"},  # 执行逻辑
    {"q": "汤家凤高数", "phase": "升学备考", "subject": "汤家凤"},  # 执行逻辑
    {"q": "武忠祥高数", "phase": "升学备考", "subject": "武忠祥"},  # 执行逻辑
    {"q": "李永乐线性代数", "phase": "升学备考", "subject": "线性代数"},  # 执行逻辑
    {"q": "余丙森概率论", "phase": "升学备考", "subject": "概率论与数理统计"},  # 执行逻辑
    {"q": "考研数学 真题", "phase": "升学备考", "subject": "真题实战"},  # 执行逻辑
    {"q": "1800题讲解", "phase": "升学备考", "subject": "习题精讲"},  # 执行逻辑
    {"q": "660题讲解", "phase": "升学备考", "subject": "习题精讲"},  # 执行逻辑
    # 科普与竞赛
    {"q": "3Blue1Brown 中文", "phase": "直观科普", "subject": "3Blue1Brown"},  # 执行逻辑
    {"q": "线性代数的本质", "phase": "直观科普", "subject": "可视化"},  # 执行逻辑
    {"q": "微积分的本质", "phase": "直观科普", "subject": "可视化"},  # 执行逻辑
    {"q": "大学生数学竞赛", "phase": "高阶/竞赛", "subject": "数学竞赛"},  # 执行逻辑
    {"q": "数学建模 国赛", "phase": "高阶/竞赛", "subject": "数学建模"},  # 执行逻辑
]  # 结构结束/分隔

MAX_PAGES = 15  # 设置变量：MAX_PAGES
REQUEST_TIMEOUT = 15  # 设置变量：REQUEST_TIMEOUT
CRAWL_DELAY_RANGE: Tuple[float, float] = (1.8, 3.5)  # 变量赋值/配置
DETAIL_DELAY_RANGE: Tuple[float, float] = (0.4, 0.9)  # 变量赋值/配置


def build_headers(cookie: str) -> Dict[str, str]:  # 定义函数：build_headers
    headers = {  # 设置变量：headers
        "User-Agent": (  # 设置字典字段：User-Agent
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "  # 执行逻辑
            "AppleWebKit/537.36 (KHTML, like Gecko) "  # 执行逻辑
            "Chrome/120.0.0.0 Safari/537.36"  # 执行逻辑
        ),  # 结构结束/分隔
        "Referer": "https://www.bilibili.com/",  # 设置字典字段：Referer
        "Accept": "application/json, text/plain, */*",  # 设置字典字段：Accept
        "Accept-Language": "zh-CN,zh;q=0.9",  # 设置字典字段：Accept-Language
    }  # 结构结束/分隔
    if cookie:  # 条件判断
        headers["Cookie"] = cookie  # 变量赋值/配置
    return headers  # 返回结果


HEADERS = build_headers(COOKIE)  # 设置变量：HEADERS

def smart_classify(title: str, tags: str, original_subject: str) -> str:  # 定义函数：smart_classify
    """
    智能分类：
    1) 若存在训练好的 ML 模型，则使用 TF-IDF + 朴素贝叶斯做预测；
    2) 预测置信度低时，退回关键词规则；仍未命中则返回原始 subject。
    """
    import jieba  # 导入 jieba 模块

    title = title or ""  # 设置变量：title
    tags = tags or ""  # 设置变量：tags

    if ML_MODEL:  # 条件判断
        text = title + " " + str(tags)  # 设置变量：text
        cut_text = " ".join([w for w in jieba.cut(text) if len(w) > 1])  # 设置变量：cut_text
        try:  # 开始捕获异常
            probs = ML_MODEL.predict_proba([cut_text])[0]  # 设置变量：probs
            max_prob = max(probs)  # 设置变量：max_prob
            if max_prob > 0.6:  # 条件判断
                return ML_MODEL.predict([cut_text])[0]  # 返回结果
        except Exception:  # 异常分支处理
            pass  # 流程控制

    combined = (title + str(tags)).lower()  # 设置变量：combined
    if "线代" in combined or "线性代数" in combined or "矩阵" in combined:  # 条件判断
        return "线性代数"  # 返回结果
    if "高数" in combined or "高等数学" in combined or "微积分" in combined:  # 条件判断
        return "高等数学"  # 返回结果
    if "概率" in combined or "统计" in combined:  # 条件判断
        return "概率论与数理统计"  # 返回结果

    return original_subject  # 返回结果

def request_bili_data(  # 定义函数：request_bili_data
    session: requests.Session,  # 执行逻辑
    url: str,  # 执行逻辑
    params: Optional[Dict[str, Any]] = None,  # 变量赋值/配置
    *,  # 执行逻辑
    timeout: int = REQUEST_TIMEOUT,  # 变量赋值/配置
) -> Any:  # 执行逻辑
    resp = session.get(url, headers=HEADERS, params=params, timeout=timeout, verify=False)  # 设置变量：resp
    resp.raise_for_status()  # 执行逻辑
    payload = resp.json()  # 设置变量：payload
    code = payload.get("code")  # 设置变量：code
    if code != 0:  # 条件判断
        msg = payload.get("message")  # 设置变量：msg
        raise RuntimeError(f"bilibili api error: {code} {msg}")  # 抛出异常
    return payload.get("data")  # 返回结果


def get_wbi_keys(session: requests.Session) -> Tuple[str, str]:  # 定义函数：get_wbi_keys
    """
    获取 wbi_img 的 img_key/sub_key，用于 WBI 签名（搜索接口需要）。
    """
    data = request_bili_data(session, "https://api.bilibili.com/x/web-interface/nav")  # 设置变量：data
    if not isinstance(data, dict):  # 条件判断
        return "", ""  # 返回结果
    wbi_img = data.get("wbi_img") or {}  # 设置变量：wbi_img
    img_url = (wbi_img.get("img_url") or "").strip()  # 设置变量：img_url
    sub_url = (wbi_img.get("sub_url") or "").strip()  # 设置变量：sub_url
    if not img_url or not sub_url:  # 条件判断
        return "", ""  # 返回结果
    img_key = img_url.rsplit("/", 1)[-1].split(".", 1)[0]  # 设置变量：img_key
    sub_key = sub_url.rsplit("/", 1)[-1].split(".", 1)[0]  # 设置变量：sub_key
    return img_key, sub_key  # 返回结果


def build_wbi_mixin_key(img_key: str, sub_key: str) -> str:  # 定义函数：build_wbi_mixin_key
    """
    WBI mixinKey 计算：按固定表重排 img_key+sub_key，截取前 32 位。
    """
    mixin_key_enc_tab = [  # 设置变量：mixin_key_enc_tab
        46, 47, 18, 2, 53, 8, 23, 32,  # 执行逻辑
        15, 50, 10, 31, 58, 3, 45, 35,  # 执行逻辑
        27, 43, 5, 49, 33, 9, 42, 19,  # 执行逻辑
        29, 28, 14, 39, 12, 38, 41, 13,  # 执行逻辑
        37, 48, 7, 16, 24, 55, 40, 61,  # 执行逻辑
        26, 17, 0, 1, 60, 51, 30, 4,  # 执行逻辑
        22, 25, 54, 21, 56, 59, 6, 63,  # 执行逻辑
        57, 62, 11, 36, 20, 34, 44, 52,  # 执行逻辑
    ]  # 结构结束/分隔
    s = (img_key or "") + (sub_key or "")  # 设置变量：s
    if len(s) < 64:  # 条件判断
        return ""  # 返回结果
    return "".join([s[i] for i in mixin_key_enc_tab])[:32]  # 返回结果


def sign_wbi_params(params: Dict[str, Any], mixin_key: str) -> Dict[str, Any]:  # 定义函数：sign_wbi_params
    """
    给参数加上 wts 和 w_rid。
    - 参数值会过滤掉特殊字符 [!'()*]（B 站规则）
    - key 按字典序排序后 urlencode，再拼 mixin_key 做 md5
    """
    params = dict(params or {})  # 设置变量：params
    params["wts"] = int(time.time())  # 变量赋值/配置
    filtered: Dict[str, str] = {}  # 变量赋值/配置
    for k, v in params.items():  # 循环遍历
        s = re.sub(r"[!'()*]", "", str(v))  # 设置变量：s
        filtered[k] = s  # 变量赋值/配置
    query = urlencode(sorted(filtered.items()))  # 设置变量：query
    filtered["w_rid"] = md5((query + mixin_key).encode("utf-8")).hexdigest()  # 变量赋值/配置
    return filtered  # 返回结果


def search_video_by_keyword(  # 定义函数：search_video_by_keyword
    session: requests.Session,  # 执行逻辑
    *,  # 执行逻辑
    keyword: str,  # 执行逻辑
    page: int,  # 执行逻辑
    order: str,  # 执行逻辑
    page_size: int,  # 执行逻辑
    mixin_key: str,  # 执行逻辑
) -> List[Dict[str, Any]]:  # 执行逻辑
    """
    使用 WBI 搜索接口（更稳定，避免 request was banned）。
    """
    base_params = {  # 设置变量：base_params
        "search_type": "video",  # 设置字典字段：search_type
        "keyword": keyword,  # 设置字典字段：keyword
        "page": page,  # 设置字典字段：page
        "page_size": page_size,  # 设置字典字段：page_size
        "order": order,  # 设置字典字段：order
    }  # 结构结束/分隔
    signed = sign_wbi_params(base_params, mixin_key)  # 设置变量：signed
    data = request_bili_data(session, "https://api.bilibili.com/x/web-interface/wbi/search/type", params=signed)  # 设置变量：data
    if not isinstance(data, dict):  # 条件判断
        return []  # 返回结果
    items = data.get("result", [])  # 设置变量：items
    return items if isinstance(items, list) else []  # 返回结果


def fetch_video_detail(session: requests.Session, bvid: str) -> Dict[str, Any]:  # 定义函数：fetch_video_detail
    data = request_bili_data(session, "https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid})  # 设置变量：data
    return data if isinstance(data, dict) else {}  # 返回结果


def fetch_video_tags(session: requests.Session, bvid: str) -> List[Dict[str, Any]]:  # 定义函数：fetch_video_tags
    data = request_bili_data(session, "https://api.bilibili.com/x/web-interface/view/detail/tag", params={"bvid": bvid})  # 设置变量：data
    if isinstance(data, list):  # 条件判断
        return data  # 返回结果
    if isinstance(data, dict):  # 条件判断
        tag_list = data.get("data")  # 设置变量：tag_list
        if isinstance(tag_list, list):  # 条件判断
            return tag_list  # 返回结果
    return []  # 返回结果


def merge_tags(video_data: Dict[str, Any], tags: Iterable[Dict[str, Any]]) -> None:  # 定义函数：merge_tags
    tag_names: List[str] = []  # 变量赋值/配置
    for t in tags or []:  # 循环遍历
        name = (t.get("tag_name") or "").strip()  # 设置变量：name
        if name:  # 条件判断
            tag_names.append(name)  # 执行逻辑
    tag_text = ",".join(dict.fromkeys(tag_names))  # 去重且保序
    video_data["tag_names"] = tag_text  # 变量赋值/配置
    # 兼容旧逻辑：tags 字段优先存真实 tags，缺省时回退为 source_keyword
    video_data["tags"] = tag_text or (video_data.get("source_keyword") or "")  # 变量赋值/配置


def normalize_from_detail(  # 定义函数：normalize_from_detail
    detail: Dict[str, Any],  # 执行逻辑
    *,  # 执行逻辑
    fallback_title: str,  # 执行逻辑
    fallback_up_name: str,  # 执行逻辑
    fallback_up_mid: int,  # 执行逻辑
    fallback_up_face: str,  # 执行逻辑
    fallback_pic_url: str,  # 执行逻辑
    fallback_bili_tid: int = 0,  # 执行逻辑
    fallback_bili_tname: str = "",  # 执行逻辑
    source_keyword: str,  # 执行逻辑
    phase: str,  # 执行逻辑
    subject: str,  # 执行逻辑
) -> Dict[str, Any]:  # 执行逻辑
    stat = detail.get("stat") or {}  # 设置变量：stat
    owner = detail.get("owner") or {}  # 设置变量：owner
    bvid = detail.get("bvid") or ""  # 设置变量：bvid

    view = parse_count(stat.get("view", 0))  # 设置变量：view
    fav = parse_count(stat.get("favorite", 0))  # 设置变量：fav
    ratio = round((fav / view * 1000), 2) if view > 0 else 0  # 设置变量：ratio

    title = clean_html(detail.get("title") or fallback_title)  # 设置变量：title
    detail_tname = (detail.get("tname") or "").strip()  # 设置变量：detail_tname
    search_tname = (fallback_bili_tname or "").strip()  # 设置变量：search_tname
    bili_tname = detail_tname or search_tname  # 设置变量：bili_tname

    detail_tid = parse_count(detail.get("tid", 0))  # 设置变量：detail_tid
    search_tid = parse_count(fallback_bili_tid or 0)  # 设置变量：search_tid
    bili_tid = detail_tid or search_tid  # 设置变量：bili_tid

    return {  # 返回结果
        "bvid": bvid,  # 设置字典字段：bvid
        "aid": parse_count(detail.get("aid", 0)),  # 设置字典字段：aid
        "video_url": build_video_url(bvid),  # 设置字典字段：video_url
        "title": title,  # 设置字典字段：title
        "desc": (detail.get("desc") or "").strip(),  # 设置字典字段：desc
        "up_name": owner.get("name") or fallback_up_name,  # 设置字典字段：up_name
        "up_mid": parse_count(owner.get("mid") or fallback_up_mid),  # 设置字典字段：up_mid
        "up_face": owner.get("face") or fallback_up_face,  # 设置字典字段：up_face
        "pic_url": detail.get("pic") or fallback_pic_url,  # 设置字典字段：pic_url
        "view_count": view,  # 设置字典字段：view_count
        "danmaku_count": parse_count(stat.get("danmaku", 0)),  # 设置字典字段：danmaku_count
        "reply_count": parse_count(stat.get("reply", 0)),  # 设置字典字段：reply_count
        "favorite_count": fav,  # 设置字典字段：favorite_count
        "like_count": parse_count(stat.get("like", 0)),  # 设置字典字段：like_count
        "coin_count": parse_count(stat.get("coin", 0)),  # 设置字典字段：coin_count
        "share_count": parse_count(stat.get("share", 0)),  # 设置字典字段：share_count
        "duration": parse_count(detail.get("duration", 0)),  # 设置字典字段：duration
        "pubdate": parse_time(detail.get("pubdate", time.time())),  # 设置字典字段：pubdate
        "tags": "",  # 设置字典字段：tags
        "tag_names": "",  # 设置字典字段：tag_names
        "source_keyword": source_keyword,  # 设置字典字段：source_keyword
        "bili_tid": bili_tid,  # 设置字典字段：bili_tid
        "bili_tname": bili_tname,  # 设置字典字段：bili_tname
        "category": "",  # 设置字典字段：category
        "phase": phase,  # 设置字典字段：phase
        "subject": "",  # 设置字典字段：subject
        "dry_goods_ratio": ratio,  # 设置字典字段：dry_goods_ratio
        "crawl_time": datetime.now(),  # 设置字典字段：crawl_time
    }  # 结构结束/分隔


def get_table_columns(cursor, table_name: str) -> List[str]:  # 定义函数：get_table_columns
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`;")  # 执行逻辑
    return [row["Field"] for row in cursor.fetchall()]  # 返回结果


def ensure_video_table_schema(cursor) -> None:  # 定义函数：ensure_video_table_schema
    """可选的“自动迁移”：为 videos 表补齐新增字段（仅追加字段）。"""  # 执行逻辑
    existing = set(get_table_columns(cursor, "videos"))  # 设置变量：existing
    desired = {  # 设置变量：desired
        "aid": "BIGINT",  # 设置字典字段：aid
        "video_url": "VARCHAR(255)",  # 设置字典字段：video_url
        "bili_tid": "INT",  # 设置字典字段：bili_tid
        "bili_tname": "VARCHAR(100)",  # 设置字典字段：bili_tname
        "desc": "TEXT",  # 设置字典字段：desc
        "like_count": "INT",  # 设置字典字段：like_count
        "coin_count": "INT",  # 设置字典字段：coin_count
        "share_count": "INT",  # 设置字典字段：share_count
        "tag_names": "VARCHAR(1000)",  # 设置字典字段：tag_names
        "source_keyword": "VARCHAR(255)",  # 设置字典字段：source_keyword
        "crawl_time": "DATETIME",  # 设置字典字段：crawl_time
    }  # 结构结束/分隔
    alter_parts = []  # 设置变量：alter_parts
    for col, ddl in desired.items():  # 循环遍历
        if col not in existing:  # 条件判断
            alter_parts.append(f"ADD COLUMN `{col}` {ddl}")  # 执行逻辑
    if alter_parts:  # 条件判断
        cursor.execute(f"ALTER TABLE `videos` {', '.join(alter_parts)};")  # 执行逻辑


def save_to_mysql(data_list: Sequence[Dict[str, Any]], *, auto_migrate: bool = False) -> None:  # 定义函数：save_to_mysql
    """批量落库：按表字段动态拼 SQL，兼容旧表结构。"""  # 执行逻辑
    if not data_list:  # 条件判断
        return  # 返回结果
    connection = pymysql.connect(**DB_CONFIG)  # 设置变量：connection
    try:  # 开始捕获异常
        with connection.cursor() as cursor:  # 上下文管理（自动释放资源）
            if auto_migrate:  # 条件判断
                ensure_video_table_schema(cursor)  # 调用函数：ensure_video_table_schema
                connection.commit()  # 执行逻辑

            existing_cols = set(get_table_columns(cursor, "videos"))  # 设置变量：existing_cols
            desired_cols = [  # 设置变量：desired_cols
                "bvid",  # 执行逻辑
                "aid",  # 执行逻辑
                "video_url",  # 执行逻辑
                "title",  # 执行逻辑
                "desc",  # 执行逻辑
                "up_name",  # 执行逻辑
                "up_mid",  # 执行逻辑
                "up_face",  # 执行逻辑
                "pic_url",  # 执行逻辑
                "view_count",  # 执行逻辑
                "danmaku_count",  # 执行逻辑
                "reply_count",  # 执行逻辑
                "favorite_count",  # 执行逻辑
                "like_count",  # 执行逻辑
                "coin_count",  # 执行逻辑
                "share_count",  # 执行逻辑
                "duration",  # 执行逻辑
                "pubdate",  # 执行逻辑
                "tags",  # 执行逻辑
                "tag_names",  # 执行逻辑
                "source_keyword",  # 执行逻辑
                "bili_tid",  # 执行逻辑
                "bili_tname",  # 执行逻辑
                "category",  # 执行逻辑
                "phase",  # 执行逻辑
                "subject",  # 执行逻辑
                "dry_goods_ratio",  # 执行逻辑
                "crawl_time",  # 执行逻辑
            ]  # 结构结束/分隔
            insert_cols = [c for c in desired_cols if c in existing_cols]  # 设置变量：insert_cols
            if not insert_cols:  # 条件判断
                return  # 返回结果

            placeholders = ", ".join(["%s"] * len(insert_cols))  # 设置变量：placeholders
            col_sql = ", ".join(f"`{c}`" for c in insert_cols)  # 设置变量：col_sql
            update_cols = [c for c in insert_cols if c != "bvid"]  # 执行逻辑
            update_parts = []  # 设置变量：update_parts
            for c in update_cols:  # 循环遍历
                if c == "bili_tname":  # 条件判断
                    update_parts.append(f"`{c}`=COALESCE(NULLIF(VALUES(`{c}`), ''), `{c}`)")  # 执行逻辑
                else:  # 兜底分支
                    update_parts.append(f"`{c}`=VALUES(`{c}`)")  # 执行逻辑
            update_sql = ", ".join(update_parts)  # 设置变量：update_sql

            sql = f"""
            INSERT INTO `videos` ({col_sql})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_sql};
            """

            values = [tuple(item.get(c) for c in insert_cols) for item in data_list]  # 设置变量：values
            cursor.executemany(sql, values)  # 执行逻辑
            connection.commit()  # 执行逻辑
            print(f"  已保存 {len(data_list)} 条视频 -> [{data_list[0].get('phase', '')}] - [{data_list[0].get('subject', '')}]")  # 调用函数：print
    except Exception as e:  # 异常分支处理
        print(f"  数据库写入失败: {e}")  # 调用函数：print
    finally:  # 最终收尾处理
        connection.close()  # 执行逻辑


def crawl(params=None, progress_cb=None, stop_flag=None):  # 定义函数：crawl
    """前端可调用的抓取函数：支持进度回调和中断。"""  # 执行逻辑
    params = params or {}  # 设置变量：params
    task_list = params.get("tasks") or CRAWL_CONFIG  # 设置变量：task_list
    max_pages = params.get("max_pages", MAX_PAGES)  # 设置变量：max_pages
    try:  # 开始捕获异常
        max_pages = int(max_pages)  # 设置变量：max_pages
    except Exception:  # 异常分支处理
        max_pages = MAX_PAGES  # 设置变量：max_pages
    max_pages = max(1, min(max_pages, MAX_PAGES))  # 设置变量：max_pages

    save_to_db = parse_bool(params.get("save_to_db", params.get("save", True)), True)  # 设置变量：save_to_db
    fetch_detail = parse_bool(params.get("fetch_detail", True), True)  # 设置变量：fetch_detail
    fetch_tags = parse_bool(params.get("fetch_tags", True), True)  # 设置变量：fetch_tags
    auto_migrate = parse_bool(params.get("auto_migrate", False), False)  # 设置变量：auto_migrate

    if not task_list:  # 条件判断
        return []  # 返回结果

    session = requests.Session()  # 设置变量：session
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])  # 设置变量：retries
    session.mount("https://", HTTPAdapter(max_retries=retries))  # 变量赋值/配置

    img_key, sub_key = get_wbi_keys(session)  # 变量赋值/配置
    mixin_key = build_wbi_mixin_key(img_key, sub_key)  # 设置变量：mixin_key
    if not mixin_key and progress_cb:  # 条件判断
        progress_cb(0, 1, "WBI 初始化失败：搜索接口可能被风控（建议在 config.py 设置 BILI_COOKIE 后重试）")  # 调用函数：progress_cb

    total_steps = max(1, len(task_list) * max_pages)  # 设置变量：total_steps
    steps_done = 0  # 设置变量：steps_done
    all_results = []  # 设置变量：all_results

    detail_cache: Dict[str, Dict[str, Any]] = {}  # 变量赋值/配置
    tag_cache: Dict[str, List[Dict[str, Any]]] = {}  # 变量赋值/配置

    for config in task_list:  # 循环遍历
        keyword = config.get("q") or config.get("keyword") or ""  # 设置变量：keyword
        phase = config.get("phase") or ""  # 设置变量：phase
        subject = config.get("subject") or ""  # 设置变量：subject
        if not keyword:  # 条件判断
            continue  # 流程控制

        if progress_cb:  # 条件判断
            progress_cb(steps_done, total_steps, f"开始抓取: {keyword} -> [{phase} - {subject}]")  # 调用函数：progress_cb

        for page in range(1, max_pages + 1):  # 循环遍历
            if stop_flag and stop_flag.is_set():  # 条件判断
                break  # 流程控制
            try:  # 开始捕获异常
                time.sleep(random.uniform(*CRAWL_DELAY_RANGE))  # 执行逻辑
                if not mixin_key:  # 条件判断
                    if progress_cb:  # 条件判断
                        progress_cb(steps_done, total_steps, "  无 WBI mixin_key，跳过搜索（请先配置 BILI_COOKIE 或稍后重试）")  # 调用函数：progress_cb
                    break  # 流程控制

                items = search_video_by_keyword(  # 设置变量：items
                    session,  # 执行逻辑
                    keyword=keyword,  # 设置变量：keyword
                    page=page,  # 设置变量：page
                    order="click",  # 设置变量：order
                    page_size=20,  # 设置变量：page_size
                    mixin_key=mixin_key,  # 设置变量：mixin_key
                )  # 结构结束/分隔
                if not items:  # 条件判断
                    if progress_cb:  # 条件判断
                        progress_cb(steps_done, total_steps, "  无更多数据")  # 调用函数：progress_cb
                    break  # 流程控制

                batch_data = []  # 设置变量：batch_data
                for item in items:  # 循环遍历
                    bvid = item.get("bvid")  # 设置变量：bvid
                    if not bvid:  # 条件判断
                        continue  # 流程控制

                    fallback_title = clean_html(item.get("title") or "")  # 设置变量：fallback_title
                    fallback_up_name = (item.get("author") or "").strip()  # 设置变量：fallback_up_name
                    fallback_up_mid = parse_count(item.get("mid") or 0)  # 设置变量：fallback_up_mid
                    fallback_up_face = item.get("upic") or ""  # 设置变量：fallback_up_face
                    raw_pic = item.get("pic", "") or ""  # 设置变量：raw_pic
                    fallback_pic_url = ("https:" + raw_pic) if raw_pic.startswith("//") else raw_pic  # 设置变量：fallback_pic_url

                    detail = {}  # 设置变量：detail
                    if fetch_detail:  # 条件判断
                        if bvid not in detail_cache:  # 条件判断
                            time.sleep(random.uniform(*DETAIL_DELAY_RANGE))  # 执行逻辑
                            try:  # 开始捕获异常
                                detail_cache[bvid] = fetch_video_detail(session, bvid)  # 变量赋值/配置
                            except Exception as e:  # 异常分支处理
                                if progress_cb:  # 条件判断
                                    progress_cb(steps_done, total_steps, f"  详情获取失败 {bvid}: {e}")  # 调用函数：progress_cb
                                detail_cache[bvid] = {}  # 变量赋值/配置
                        detail = detail_cache.get(bvid) or {}  # 设置变量：detail

                    if detail:  # 条件判断
                        fallback_bili_tid = parse_count(item.get("typeid", item.get("tid", 0)))  # 设置变量：fallback_bili_tid
                        fallback_bili_tname = (item.get("typename") or item.get("tname") or "").strip()  # 设置变量：fallback_bili_tname
                        video_data = normalize_from_detail(  # 设置变量：video_data
                            detail,  # 执行逻辑
                            fallback_title=fallback_title,  # 设置变量：fallback_title
                            fallback_up_name=fallback_up_name,  # 设置变量：fallback_up_name
                            fallback_up_mid=fallback_up_mid,  # 设置变量：fallback_up_mid
                            fallback_up_face=fallback_up_face,  # 设置变量：fallback_up_face
                            fallback_pic_url=fallback_pic_url,  # 设置变量：fallback_pic_url
                            fallback_bili_tid=fallback_bili_tid,  # 设置变量：fallback_bili_tid
                            fallback_bili_tname=fallback_bili_tname,  # 设置变量：fallback_bili_tname
                            source_keyword=keyword,  # 设置变量：source_keyword
                            phase=phase,  # 设置变量：phase
                            subject=subject,  # 设置变量：subject
                        )  # 结构结束/分隔
                    else:  # 兜底分支
                        view = parse_count(item.get("play", 0))  # 设置变量：view
                        fav = parse_count(item.get("favorites", 0))  # 设置变量：fav
                        ratio = round((fav / view * 1000), 2) if view > 0 else 0  # 设置变量：ratio

                        video_data = {  # 设置变量：video_data
                            "bvid": bvid,  # 设置字典字段：bvid
                            "aid": parse_count(item.get("aid", 0)),  # 设置字典字段：aid
                            "video_url": build_video_url(bvid),  # 设置字典字段：video_url
                            "title": fallback_title,  # 设置字典字段：title
                            "desc": "",  # 设置字典字段：desc
                            "up_name": fallback_up_name,  # 设置字典字段：up_name
                            "up_mid": fallback_up_mid,  # 设置字典字段：up_mid
                            "up_face": fallback_up_face,  # 设置字典字段：up_face
                            "pic_url": fallback_pic_url,  # 设置字典字段：pic_url
                            "view_count": view,  # 设置字典字段：view_count
                            "danmaku_count": parse_count(item.get("video_review", 0)),  # 设置字典字段：danmaku_count
                            "reply_count": parse_count(item.get("review", 0)),  # 设置字典字段：reply_count
                            "favorite_count": fav,  # 设置字典字段：favorite_count
                            "like_count": 0,  # 设置字典字段：like_count
                            "coin_count": 0,  # 设置字典字段：coin_count
                            "share_count": 0,  # 设置字典字段：share_count
                            "duration": parse_duration(item.get("duration", "0")),  # 设置字典字段：duration
                            "pubdate": parse_time(item.get("pubdate", time.time())),  # 设置字典字段：pubdate
                            "tags": "",  # 设置字典字段：tags
                            "tag_names": "",  # 设置字典字段：tag_names
                            "source_keyword": keyword,  # 设置字典字段：source_keyword
                            "bili_tid": parse_count(item.get("typeid", item.get("tid", 0))),  # 设置字典字段：bili_tid
                            "bili_tname": (item.get("typename") or item.get("tname") or "").strip(),  # 设置字典字段：bili_tname
                            "category": "",  # 设置字典字段：category
                            "phase": phase,  # 设置字典字段：phase
                            "subject": "",  # 设置字典字段：subject
                            "dry_goods_ratio": ratio,  # 设置字典字段：dry_goods_ratio
                            "crawl_time": datetime.now(),  # 设置字典字段：crawl_time
                        }  # 结构结束/分隔

                    if fetch_tags:  # 条件判断
                        if bvid not in tag_cache:  # 条件判断
                            time.sleep(random.uniform(*DETAIL_DELAY_RANGE))  # 执行逻辑
                            try:  # 开始捕获异常
                                tag_cache[bvid] = fetch_video_tags(session, bvid)  # 变量赋值/配置
                            except Exception:  # 异常分支处理
                                tag_cache[bvid] = []  # 变量赋值/配置
                        merge_tags(video_data, tag_cache.get(bvid) or [])  # 调用函数：merge_tags
                    else:  # 兜底分支
                        video_data["tags"] = video_data.get("tags") or keyword  # 变量赋值/配置

                    classify_text = (video_data.get("tag_names") or "") + " " + keyword  # 设置变量：classify_text
                    final_subject = smart_classify(video_data.get("title") or "", classify_text, subject)  # 设置变量：final_subject
                    video_data["category"] = final_subject  # 变量赋值/配置
                    video_data["subject"] = final_subject  # 变量赋值/配置

                    view_val = parse_count(video_data.get("view_count") or 0)  # 设置变量：view_val
                    fav_val = parse_count(video_data.get("favorite_count") or 0)  # 设置变量：fav_val
                    video_data["dry_goods_ratio"] = round((fav_val / view_val * 1000), 2) if view_val > 0 else 0  # 变量赋值/配置

                    batch_data.append(video_data)  # 执行逻辑

                if save_to_db:  # 条件判断
                    save_to_mysql(batch_data, auto_migrate=auto_migrate)  # 变量赋值/配置

                all_results.extend(batch_data)  # 执行逻辑

            except Exception as e:  # 异常分支处理
                if progress_cb:  # 条件判断
                    progress_cb(steps_done, total_steps, f"  第{page}页异常: {e}")  # 调用函数：progress_cb
                time.sleep(5)  # 执行逻辑

            steps_done += 1  # 变量赋值/配置
            if progress_cb:  # 条件判断
                progress_cb(steps_done, total_steps, f"{keyword} - 第{page}页完成")  # 调用函数：progress_cb

        if stop_flag and stop_flag.is_set():  # 条件判断
            if progress_cb:  # 条件判断
                progress_cb(steps_done, total_steps, "任务已中断")  # 调用函数：progress_cb
            break  # 流程控制

    return all_results  # 返回结果


def run_spider():  # 定义函数：run_spider
    """命令行入口：完整跑一遍配置。"""  # 执行逻辑
    print("爬虫启动...")  # 调用函数：print

    def log_progress(done, total, log_line=None):  # 定义函数：log_progress
        if log_line:  # 条件判断
            print(log_line)  # 调用函数：print
        if total:  # 条件判断
            print(f"进度: {done}/{total}")  # 调用函数：print

    crawl({"tasks": CRAWL_CONFIG, "max_pages": MAX_PAGES}, progress_cb=log_progress)  # 变量赋值/配置
    print("爬虫结束")  # 调用函数：print


if __name__ == "__main__":  # 条件判断
    run_spider()  # 调用函数：run_spider

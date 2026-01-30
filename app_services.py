"""业务/工具函数集合（为了减少文件数量集中在一个模块里）。

阅读提示（可读性优先）：
1) 这个文件只放“可复用”的函数：参数清洗、序列化、简单校验、少量 DB 操作封装等。
2) 路由层（`app_routes.py`）只做 request/response/权限控制，不要塞复杂业务逻辑。
3) 本文件从上到下按“通用 -> 业务”的顺序排：
   - 常量与约定
   - API 响应 / DB 提交
   - 参数清洗与文本解析
   - 账号/密码
   - 视频相关（查询过滤/序列化/评分）
   - 头像处理
   - 用户行为（收藏/历史）
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from io import BytesIO
from typing import Iterable

from flask import jsonify
from PIL import Image
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, UserAction, Video, db

# ============================================================
# 1) 常量与约定（尽量集中，便于改动）
# ============================================================

UPLOAD_FOLDER = "static/avatars"
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
DEFAULT_AVATAR_STATIC_PATH = "img/default-avatar.svg"
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB per avatar

PASSWORD_HASH_METHOD = "pbkdf2:sha256:260000"
PASSWORD_SALT_LENGTH = 8  # keep hash length within DB column limits

SUPPORTED_ACTIONS = {"fav", "history"}
HISTORY_LIMIT = 200  # 返回给前端的学习足迹条数上限，避免过大响应


# ============================================================
# 2) 通用：API 响应 / DB 提交
# ============================================================


def api_ok(msg: str = "OK", *, code: int = 200, **extra):
    """统一成功返回结构：{code,msg,...}"""
    return jsonify({"code": code, "msg": msg, **extra})


def api_error(msg: str, *, code: int = 400, http_status: int = 400, **extra):
    """统一失败返回结构：({code,msg,...}, http_status)"""
    return jsonify({"code": code, "msg": msg, **extra}), http_status


def commit_or_rollback(session) -> bool:
    """提交事务；遇到 IntegrityError 自动回滚并返回 False。"""
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False


# ============================================================
# 3) 通用：参数清洗与文本解析
# ============================================================


def clamp_int(value: int, *, lo: int, hi: int) -> int:
    """把整数夹在 [lo, hi] 之间（防止前端乱传参数）。"""
    return max(lo, min(int(value), hi))


def clean_filter_value(value: str | None) -> str:
    """规范化筛选参数，把 all/全部/不限 统一转为空字符串。"""
    value = (value or "").strip()
    if value.lower() in {"all", "全部", "不限"}:
        return ""
    return value


def parse_pub_dt(value: str | None, *, end: bool) -> datetime | None:
    """尽量宽容地解析日期时间：支持 YYYY-MM-DD 或 ISO 字符串。"""
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if end and len(value) == 10:
        return dt.replace(hour=23, minute=59, second=59)
    return dt


def split_topics_text(value: str | None) -> list[str]:
    """把 enrichment 的“知识点”字段拆成 list，并尽量兼容旧数据（无分隔符拼接）。"""
    raw = (value or "").strip()
    if not raw:
        return []

    parts = [p for p in (x.strip() for x in re.split(r"[，,、;；/\\s]+", raw)) if p]
    if not parts:
        return []

    alias_map = {"考研真题": "考研刷题"}
    parts = [alias_map.get(p, p) for p in parts]

    try:
        from core.topic_classifier import TOPICS as KNOWN_TOPICS
    except Exception:
        KNOWN_TOPICS = []

    out: list[str] = []
    seen: set[str] = set()

    if KNOWN_TOPICS:
        for part in parts:
            if part in KNOWN_TOPICS:
                if part not in seen:
                    seen.add(part)
                    out.append(part)
                continue

            matched_any = False
            for old, new in alias_map.items():
                if old and old in part:
                    matched_any = True
                    if new not in seen:
                        seen.add(new)
                        out.append(new)
            for topic in KNOWN_TOPICS:
                if topic and topic in part:
                    matched_any = True
                    if topic not in seen:
                        seen.add(topic)
                        out.append(topic)

            if not matched_any and part not in seen:
                seen.add(part)
                out.append(part)

        return out

    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        out.append(part)

    return out


# ============================================================
# 4) 账号/密码（注册/登录用）
# ============================================================


def is_hashed_password(value: str) -> bool:
    """粗略判断字符串看起来是否像 Werkzeug 的密码哈希。"""
    return isinstance(value, str) and value.count("$") >= 2


def hash_password(password: str) -> str:
    """生成密码哈希；统一算法与 salt 长度。"""
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD, salt_length=PASSWORD_SALT_LENGTH)


def verify_password(stored: str, candidate: str) -> bool:
    """安全校验密码；遇到坏数据返回 False（不抛异常）。"""
    if not stored or not candidate or not is_hashed_password(stored):
        return False
    try:
        return check_password_hash(stored, candidate)
    except ValueError:
        return False


def default_nickname(account: str) -> str:
    """注册时兜底昵称生成：用户xxxx（取账号后 4 位）。"""
    account = (account or "").strip()
    if not account:
        return "用户"
    suffix = account[-4:] if len(account) >= 4 else account
    return f"用户{suffix}"


def account_exists(account: str, exclude_user_id: int | None = None) -> bool:
    """账号查重（账号作为唯一登录凭证）。"""
    if not account:
        return False
    query = User.query.filter_by(账号=account)
    if exclude_user_id:
        query = query.filter(User.用户ID != exclude_user_id)
    return db.session.query(query.exists()).scalar()


# ============================================================
# 5) 视频：查询过滤 / 序列化 / 评分
# ============================================================


def apply_video_fuzzy_filter(query, keyword: str):
    """统一的“模糊匹配”过滤：标题/标签/UP 主名称。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return query
    like_kw = f"%{keyword}%"
    return query.filter(
        or_(
            Video.标签.like(like_kw),
            Video.标题.like(like_kw),
            Video.UP主名称.like(like_kw),
        )
    )


def _normalize_media_url(url: str) -> str:
    """统一修正媒体 URL：//xx -> https://xx、http -> https。"""
    if not url:
        return ""
    u = str(url).strip()
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


def serialize_video(v) -> dict:
    """统一前端视频结构（多接口复用）。"""
    up_face = _normalize_media_url(getattr(v, "UP主头像", "") or "")
    duration = v.时长 or 0
    category = getattr(v, "分类", "") or ""

    return {
        "bvid": v.视频ID,
        "title": v.标题,
        "up_name": v.UP主名称,
        "up_face": up_face,
        "pic_url": _normalize_media_url(getattr(v, "封面图", "") or ""),
        "view_count": v.播放量 or 0,
        "category": category,
        "duration": duration,
        "pubdate": v.发布时间.isoformat() if v.发布时间 else None,
    }


def _video_to_scorer_dict(v) -> dict:
    """把 ORM 对象转为 QualityScorer 需要的字段字典。"""
    return {
        "view_count": v.播放量 or 0,
        "favorite_count": v.收藏数 or 0,
        "like_count": v.点赞数 or 0,
        "coin_count": v.投币数 or 0,
        "duration": v.时长 or 0,
        "pubdate": v.发布时间,
        "up_name": v.UP主名称 or "",
    }


def calc_quality_scores(videos) -> list[float]:
    """计算视频质量分（0-100），用于仪表盘/排序等。"""
    if not videos:
        return []

    from core.quality_scorer import QualityScorer

    scorer = QualityScorer()
    return [scorer.score(_video_to_scorer_dict(v)) for v in videos]


# ============================================================
# 6) 头像：校验 / 保存 / 删除
# ============================================================


def allowed_avatar(filename: str, allowed_extensions: Iterable[str] = ALLOWED_AVATAR_EXTENSIONS) -> bool:
    """头像后缀白名单校验。"""
    return bool(filename) and "." in filename and filename.rsplit(".", 1)[1].lower() in set(allowed_extensions)


def delete_avatar_file(filename: str, upload_folder: str, *, logger=None) -> None:
    """删除旧头像文件（限定在 upload_folder 内，避免路径穿越）。"""
    if not filename:
        return
    upload_root = os.path.abspath(upload_folder)
    avatar_path = os.path.abspath(os.path.join(upload_folder, filename))
    if not avatar_path.startswith(upload_root):
        return
    try:
        if os.path.exists(avatar_path):
            os.remove(avatar_path)
    except OSError:
        if logger is not None:
            logger.warning("Failed to remove old avatar: %s", avatar_path)


def save_avatar_upload(
    file_storage,
    *,
    user_id: int,
    upload_folder: str,
    max_size: int = MAX_AVATAR_SIZE,
    allowed_extensions=ALLOWED_AVATAR_EXTENSIONS,
):
    """校验并保存头像（统一转 JPEG + 缩略到 256）。

    返回：新头像文件名；若未上传则返回 None
    异常：ValueError（消息可直接返回给前端）
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    if not allowed_avatar(file_storage.filename, allowed_extensions):
        raise ValueError("头像格式不支持")
    if file_storage.mimetype and not file_storage.mimetype.startswith("image/"):
        raise ValueError("仅支持图片上传")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_size:
        raise ValueError("头像文件过大")

    try:
        img = Image.open(file_storage.stream).convert("RGB")
    except Exception as exc:
        raise ValueError("无效的图片文件") from exc

    img.thumbnail((256, 256))
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    filename = f"user_{user_id}_{int(time.time())}.jpg"
    with open(os.path.join(upload_folder, filename), "wb") as out:
        out.write(buffer.read())
    return filename


# ============================================================
# 7) 用户行为：收藏/历史
# ============================================================


def ensure_action_allowed(action_type: str) -> bool:
    return action_type in SUPPORTED_ACTIONS


def get_action_record(user_id: int, bvid: str, action_type: str):
    return UserAction.query.filter_by(用户ID=user_id, 视频ID=bvid, 行为类型=action_type).first()


def create_action(user_id: int, bvid: str, action_type: str) -> bool:
    if not ensure_action_allowed(action_type) or not bvid:
        return False
    if get_action_record(user_id, bvid, action_type):
        return False
    db.session.add(UserAction(用户ID=user_id, 视频ID=bvid, 行为类型=action_type))
    db.session.commit()
    return True


def delete_action(user_id: int, bvid: str, action_type: str) -> bool:
    action = get_action_record(user_id, bvid, action_type)
    if not action:
        return False
    db.session.delete(action)
    db.session.commit()
    return True


def bump_history(user_id: int, bvid: str) -> None:
    history = get_action_record(user_id, bvid, "history")
    if history:
        history.创建时间 = func.now()
    else:
        db.session.add(UserAction(用户ID=user_id, 视频ID=bvid, 行为类型="history"))
    db.session.commit()


def attach_user_fav_flags(videos: list[dict], *, user_id: int, bvids: list[str]) -> None:
    if not videos or not bvids:
        return

    actions = UserAction.query.filter(
        UserAction.用户ID == user_id,
        UserAction.视频ID.in_(bvids),
        UserAction.行为类型.in_(("fav",)),
    ).all()

    fav_bvids = {a.视频ID for a in actions if a.视频ID}
    for video in videos:
        video["is_fav"] = video.get("bvid") in fav_bvids


def get_videos_from_actions(actions) -> list[dict]:
    if not actions:
        return []

    bvids = [a.视频ID for a in actions]
    video_map = {v.视频ID: v for v in Video.query.filter(Video.视频ID.in_(bvids)).all()}

    result: list[dict] = []
    for action in actions:
        if action.视频ID in video_map:
            v_data = serialize_video(video_map[action.视频ID])
        else:
            v_data = {
                "bvid": action.视频ID,
                "title": "视频不存在或未收录",
                "pic_url": "https://placehold.co/320x200/eee/999?text=Missing",
                "link": f"https://www.bilibili.com/video/{action.视频ID}",
            }
        v_data["action_time"] = action.创建时间.strftime("%Y-%m-%d %H:%M")
        result.append(v_data)

    return result

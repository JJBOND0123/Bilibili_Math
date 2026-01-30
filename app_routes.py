"""路由层（Blueprint）全集（为了减少文件数量集中在一个模块里）。

阅读提示（可读性优先）：
1) 这个文件只做“薄路由”：取参数 -> 校验/登录态 -> 调用 `app_services.py` -> 返回。
2) 大块业务逻辑/重复逻辑尽量下沉到 `app_services.py`，避免路由越来越肥。
3) 从上到下按“用户访问路径”排序：
   - 认证（/login /register /logout）
   - 页面（/ /resources /recommend /profile /go/<bvid>）
   - API：仪表盘（/api/stats）
   - API：资源/检索（/api/personal_resources /api/videos）
   - API：推荐（/api/recommend /api/topics ...）
   - API：用户（/api/user_profile /api/update_profile ...）
"""

from __future__ import annotations

import math
import os
import random
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_

from models import User, UserAction, Video, VideoEnrichment, db

import app_services as svc


# 对外只暴露 3 个 Blueprint，`app.py` 会负责注册。
__all__ = ["auth_bp", "pages_bp", "api_bp"]


auth_bp = Blueprint("auth", __name__)
pages_bp = Blueprint("pages", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")


# ============================================================
# 1) 认证（Auth）
# ============================================================


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """登录页：GET 渲染；POST 验证并登录。"""
    if request.method == "POST":
        account = (request.form.get("account") or "").strip()
        password = request.form.get("password")
        if not account or not password:
            flash("请输入账号和密码", "danger")
            return render_template("login.html")
        user = User.query.filter_by(账号=account).first()
        if user:
            authenticated = False
            # 历史数据可能存明文；如果是明文且校验通过，会同步升级为哈希。
            if svc.is_hashed_password(user.密码):
                authenticated = svc.verify_password(user.密码, password)
            elif user.密码 == password:
                user.密码 = svc.hash_password(password)
                db.session.commit()
                authenticated = True
            if authenticated:
                session.permanent = True  # 启用持久化 session（7天有效）
                login_user(user)
                return redirect(url_for("pages.dashboard"))
        flash("账号或密码错误", "danger")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """注册页：GET 渲染；POST 创建用户。"""
    if request.method == "POST":
        account = (request.form.get("account") or "").strip()
        password = request.form.get("password")
        if not account or not password:
            flash("请输入账号和密码", "danger")
        elif svc.account_exists(account):
            flash("账号已存在", "danger")
        else:
            new_user = User(
                账号=account,
                昵称=svc.default_nickname(account),
                密码=svc.hash_password(password),
                简介="这个人很懒，还没有填写个人介绍",
                头像="",
            )
            db.session.add(new_user)
            if svc.commit_or_rollback(db.session):
                flash("注册成功，请登录", "success")
                return redirect(url_for("auth.login"))
            flash("账号已存在或昵称冲突，请检查数据库迁移", "danger")
    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """退出登录。"""
    logout_user()
    return redirect(url_for("auth.login"))


# ============================================================
# 2) 页面（Pages）
# ============================================================


@pages_bp.route("/")
@login_required
def dashboard():
    """仪表盘页面。"""
    return render_template("dashboard.html", active="dashboard")


@pages_bp.route("/resources")
@login_required
def resources():
    """资源检索页面。"""
    return render_template("resources.html", active="resources")


@pages_bp.route("/recommend")
@login_required
def recommend():
    """智能推荐页面。"""
    return render_template("recommend.html", active="recommend")


@pages_bp.route("/profile")
@login_required
def profile():
    """个人中心页面。"""
    return render_template("profile.html", active="profile")


@pages_bp.route("/go/<bvid>")
@login_required
def go_bvid(bvid):
    """站内跳转：先记录历史，再跳到 B 站。"""
    svc.bump_history(current_user.用户ID, bvid)
    return redirect(f"https://www.bilibili.com/video/{bvid}")


@pages_bp.get("/favicon.ico")
def favicon():
    """避免 /favicon.ico 404，复用默认 SVG 作为站点图标。"""
    return send_from_directory(
        os.path.join(current_app.root_path, "static", "img"),
        "default-avatar.svg",
        mimetype="image/svg+xml",
    )


# ============================================================
# 3) API：仪表盘（Dashboard）
# ============================================================


@api_bp.get("/stats")
def api_stats():
    """仪表盘统计数据：总量、TOP、分类分布、散点图。"""
    # 基础查询：只统计有科目的视频（过滤游戏等无关视频）
    valid_bvids_subq = (
        db.session.query(VideoEnrichment.视频ID)
        .filter(VideoEnrichment.科目.isnot(None))
        .subquery()
    )
    base_query = Video.query.filter(Video.视频ID.in_(db.session.query(valid_bvids_subq)))

    total_videos = base_query.count()
    total_teachers = (
        db.session.query(func.count(func.distinct(Video.UP主名称)))
        .filter(Video.视频ID.in_(db.session.query(valid_bvids_subq)))
        .scalar()
    )
    total_views = (
        db.session.query(func.sum(Video.播放量))
        .filter(Video.视频ID.in_(db.session.query(valid_bvids_subq)))
        .scalar() or 0
    )
    sample_videos = base_query.order_by(Video.播放量.desc()).limit(500).all()
    sample_scores = svc.calc_quality_scores(sample_videos)
    avg_score = sum(sample_scores) / len(sample_scores) if sample_scores else 0

    scored_sample = list(zip(sample_videos, sample_scores))
    scored_sample.sort(key=lambda x: x[1], reverse=True)
    top_scored = scored_sample[:8]
    top_list = [v for v, _ in top_scored]
    top_scores = [s for _, s in top_scored]

    rank_titles = [v.标题[:15] + "..." if len(v.标题) > 15 else v.标题 for v in top_list][::-1]
    rank_scores = top_scores[::-1]
    rank_bvids = [v.视频ID for v in top_list][::-1]

    from core.recommend_engine import COURSE_TOPICS

    topic_to_course: dict[str, str] = {}
    for course, topics in COURSE_TOPICS.items():
        for topic in topics:
            topic_to_course[topic] = course

    enrich_rows = (
        db.session.query(VideoEnrichment.视频ID, VideoEnrichment.知识点)
        .filter(VideoEnrichment.知识点.isnot(None), VideoEnrichment.知识点 != "")
        .filter(VideoEnrichment.科目.isnot(None))  # 过滤游戏等无关视频
        .all()
    )

    enriched_bvids: set[str] = set()
    exam_bvids: set[str] = set()  # 考研单独统计，不加入饼图
    category_bvids: dict[str, set[str]] = {
        "高数": set(),
        "线代": set(),
        "概率": set(),
        "竞赛": set(),
        "直观": set(),
    }

    course_order = list(COURSE_TOPICS.keys())

    for bvid, raw in enrich_rows:
        if not bvid:
            continue
        enriched_bvids.add(bvid)

        topics = svc.split_topics_text(raw)
        if not topics:
            continue

        # 统计考研（不加入饼图）
        if "考研相关" in topics or "考研真题" in topics:
            exam_bvids.add(bvid)

        # 优先分类：竞赛 > 直观 > 三大课程
        if "竞赛" in topics:
            category_bvids["竞赛"].add(bvid)
            continue
        if "直观" in topics:
            category_bvids["直观"].add(bvid)
            continue

        course_hits: Counter[str] = Counter()
        for t in topics:
            course = topic_to_course.get(t)
            if course:
                course_hits[course] += 1

        if not course_hits:
            continue

        best_count = max(course_hits.values())
        candidates = [c for c, cnt in course_hits.items() if cnt == best_count]
        best_course = sorted(candidates, key=lambda c: course_order.index(c) if c in course_order else 999)[0]
        category_bvids[best_course].add(bvid)

    course_counter: Counter = Counter({k: len(v) for k, v in category_bvids.items()})
    category_data = [{"name": k, "value": int(c)} for k, c in course_counter.most_common()]

    # 考研统计（徽章显示）
    exam_total = len(exam_bvids)
    enriched_total = len(enriched_bvids)
    exam_ratio = (exam_total / enriched_total) if enriched_total else 0.0

    scatter_data = []
    hot_videos = (
        base_query.filter(Video.时长 > 300, Video.时长 < 10800).order_by(Video.播放量.desc()).limit(300).all()
    )
    hot_scores = svc.calc_quality_scores(hot_videos)
    scored_hot = dict(zip([v.视频ID for v in hot_videos], hot_scores))
    for v in hot_videos:
        duration_min = round(v.时长 / 60, 1)
        scatter_data.append([duration_min, scored_hot.get(v.视频ID, 0.0), v.标题, v.UP主名称, v.视频ID])

    return jsonify(
        {
            "total_videos": total_videos,
            "total_teachers": total_teachers,
            "total_views": total_views,
            "avg_score": round(avg_score, 1),
            "rank_titles": rank_titles,
            "rank_scores": rank_scores,
            "rank_bvids": rank_bvids,
            "scatter_data": scatter_data,
            "category_data": category_data,
            "exam_total": exam_total,
            "exam_ratio": round(exam_ratio, 4),
        }
    )


# ============================================================
# 4) API：资源/检索（Videos/Search）
# ============================================================


@api_bp.get("/personal_resources")
@login_required
def api_personal_resources():
    """资源页个性化推荐：不分页，返回固定条数。"""
    limit = request.args.get("limit", 8, type=int)
    limit = svc.clamp_int(limit, lo=1, hi=8)
    keyword = (request.args.get("q") or "").strip()

    seed = request.args.get("seed", type=int)
    rng = random.Random(seed) if seed is not None else random

    user_id = current_user.用户ID
    actions = (
        UserAction.query.filter(
            UserAction.用户ID == user_id,
            UserAction.行为类型.in_(("fav", "history")),
        )
        .order_by(UserAction.创建时间.desc())
        .limit(200)
        .all()
    )

    excluded: set[str] = {a.视频ID for a in actions if a.视频ID}

    enrich_by_bvid: dict[str, VideoEnrichment] = {}
    if excluded:
        enrichments = VideoEnrichment.query.filter(VideoEnrichment.视频ID.in_(list(excluded))).all()
        enrich_by_bvid = {e.视频ID: e for e in enrichments}

    now = datetime.now()
    topic_weights: Counter[str] = Counter()
    for action in actions:
        enrich = enrich_by_bvid.get(action.视频ID)
        if not enrich:
            continue
        topics = svc.split_topics_text(getattr(enrich, "知识点", None))
        if not topics:
            continue

        base = 3.0 if action.行为类型 == "fav" else 1.0
        days = 0
        if getattr(action, "创建时间", None):
            days = max(0, (now - action.创建时间).days)
        decay = math.exp(-days / 30) if days else 1.0
        weight = base * decay
        for topic in topics:
            topic_weights[topic] += weight

    top_topics = [t for t, _ in topic_weights.most_common(5)]
    mode = "personalized" if top_topics else "fallback"

    # 提示：下面两个内部函数只服务本接口，避免把路由逻辑拆得太碎。
    def query_candidates(*, topics: list[str] | None, exclude_bvids: set[str]) -> list[Video]:
        q = (
            db.session.query(Video)
            .join(VideoEnrichment, VideoEnrichment.视频ID == Video.视频ID)
            .filter(VideoEnrichment.是否推荐.is_(True))
            .filter(VideoEnrichment.科目.isnot(None))  # 过滤无科目视频（游戏等）
        )
        if topics:
            q = q.filter(or_(*[VideoEnrichment.知识点.like(f"%{t}%") for t in topics]))
        q = svc.apply_video_fuzzy_filter(q, keyword)
        if exclude_bvids:
            q = q.filter(~Video.视频ID.in_(list(exclude_bvids)))

        q = q.order_by(
            VideoEnrichment.质量分.desc(),
            Video.收藏数.desc(),
            Video.播放量.desc(),
        )
        return q.limit(200).all()

    def add_random(videos: list[Video], out: list[Video], seen: set[str], *, take: int) -> None:
        if not videos or take <= 0:
            return
        pool = videos[: min(len(videos), 120)]
        pool = list(pool)
        rng.shuffle(pool)
        for v in pool:
            bvid = getattr(v, "视频ID", None)
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            out.append(v)
            if len(out) >= take:
                return

    picked: list[Video] = []
    seen: set[str] = set()

    candidates = query_candidates(topics=top_topics or None, exclude_bvids=excluded)
    add_random(candidates, picked, seen, take=limit)

    if len(picked) < limit:
        fallback_candidates = query_candidates(topics=None, exclude_bvids=excluded | seen)
        add_random(fallback_candidates, picked, seen, take=limit)

    if len(picked) < limit:
        q = svc.apply_video_fuzzy_filter(Video.query, keyword)
        if excluded or seen:
            q = q.filter(~Video.视频ID.in_(list(excluded | seen)))
        q = q.order_by(Video.收藏数.desc(), Video.播放量.desc())
        add_random(q.limit(200).all(), picked, seen, take=limit)

    payload = [svc.serialize_video(v) for v in picked[:limit]]
    svc.attach_user_fav_flags(
        payload,
        user_id=current_user.用户ID,
        bvids=[v.get("bvid") for v in payload if v.get("bvid")],
    )
    return jsonify({"videos": payload, "mode": mode, "topics": top_topics})


@api_bp.get("/videos")
def get_videos():
    """视频列表：关键词 + 基础过滤 + 排序 + 分页。"""
    page = request.args.get("page", 1, type=int)
    per_page = 12
    sort_by = (request.args.get("sort", "overall") or "").strip().lower()
    category = request.args.get("category", "all")
    keyword = request.args.get("q", "")

    phase = svc.clean_filter_value(request.args.get("phase"))
    subject = svc.clean_filter_value(request.args.get("subject"))
    min_duration = request.args.get("min_duration", type=int)
    max_duration = request.args.get("max_duration", type=int)
    min_views = request.args.get("min_views", type=int)
    max_views = request.args.get("max_views", type=int)
    pub_from = svc.clean_filter_value(request.args.get("pub_from"))
    pub_to = svc.clean_filter_value(request.args.get("pub_to"))

    # 基础查询：只查询有科目的视频（过滤游戏等无关视频）
    query = (
        db.session.query(Video)
        .join(VideoEnrichment, VideoEnrichment.视频ID == Video.视频ID)
        .filter(VideoEnrichment.科目.isnot(None))
    )
    query = svc.apply_video_fuzzy_filter(query, keyword)

    if phase:
        query = svc.apply_video_fuzzy_filter(query, phase)
    if subject:
        query = svc.apply_video_fuzzy_filter(query, subject)
    if not phase and not subject and category != "all":
        query = svc.apply_video_fuzzy_filter(query, category)

    if min_duration is not None:
        query = query.filter(Video.时长 >= max(0, int(min_duration)))
    if max_duration is not None:
        query = query.filter(Video.时长 <= max(0, int(max_duration)))
    if min_views is not None:
        query = query.filter(Video.播放量 >= max(0, int(min_views)))
    if max_views is not None:
        query = query.filter(Video.播放量 <= max(0, int(max_views)))

    start_dt = svc.parse_pub_dt(pub_from, end=False)
    end_dt = svc.parse_pub_dt(pub_to, end=True)
    if start_dt:
        query = query.filter(Video.发布时间 >= start_dt)
    if end_dt:
        query = query.filter(Video.发布时间 <= end_dt)

    if sort_by in {"views", "view"}:
        query = query.order_by(Video.播放量.desc())
    elif sort_by in {"favorites", "favorite", "fav"}:
        query = query.order_by(Video.收藏数.desc())
    elif sort_by in {"new", "pubdate", "time"}:
        query = query.order_by(Video.发布时间.desc())
    else:
        query = query.order_by(Video.收藏数.desc(), Video.播放量.desc())

    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    videos = pagination.items
    payload_videos = [svc.serialize_video(v) for v in videos]
    if current_user.is_authenticated:
        svc.attach_user_fav_flags(payload_videos, user_id=current_user.用户ID, bvids=[v.视频ID for v in videos])

    return jsonify(
        {
            "videos": payload_videos,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page,
        }
    )


@api_bp.get("/category_tree")
def get_category_tree():
    """分类树占位：保持接口形状。"""
    return jsonify({"phases": []})


# ============================================================
# 5) API：推荐（Recommend）
# ============================================================


@api_bp.get("/recommend")
def api_recommend():
    """推荐 API：多策略 + 多筛选。"""
    from core import RecommendEngine, RecommendStrategy

    engine = RecommendEngine(db, Video, VideoEnrichment)

    strategy_str = request.args.get("strategy", "hot").lower()
    course = svc.clean_filter_value(request.args.get("course"))
    topic = svc.clean_filter_value(request.args.get("topic"))
    difficulty = svc.clean_filter_value(request.args.get("difficulty"))
    up_name = svc.clean_filter_value(request.args.get("up_name"))
    search_query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 8, type=int)
    page_size = svc.clamp_int(page_size, lo=1, hi=8)
    only_recommended = request.args.get("only_recommended", "true").lower() == "true"

    strategy_map = {
        "hot": RecommendStrategy.HOT,
        "popular": RecommendStrategy.POPULAR,
        "latest": RecommendStrategy.LATEST,
        "easy": RecommendStrategy.EASY,
        "medium": RecommendStrategy.MEDIUM,
        "hard": RecommendStrategy.HARD,
    }
    strategy = strategy_map.get(strategy_str, RecommendStrategy.HOT)

    result = engine.recommend(
        strategy=strategy,
        course=course,
        topic=topic,
        difficulty=difficulty,
        up_name=up_name,
        search_query=search_query,
        page=page,
        page_size=page_size,
        only_recommended=only_recommended,
    )

    items = result.get("items", [])
    if items and current_user.is_authenticated:
        svc.attach_user_fav_flags(
            items,
            user_id=current_user.用户ID,
            bvids=[v.get("bvid") for v in items if v.get("bvid")],
        )

    return jsonify(result)


@api_bp.get("/topics")
def api_topics():
    """推荐页筛选项：课程->知识点->数量。"""
    from core import COURSE_TOPICS

    rows = (
        db.session.query(VideoEnrichment.视频ID, VideoEnrichment.知识点)
        .filter(VideoEnrichment.知识点.isnot(None), VideoEnrichment.知识点 != "")
        .filter(VideoEnrichment.是否推荐.is_(True))
        .filter(VideoEnrichment.科目.in_(["高等数学", "线性代数", "概率论与数理统计"]))
        .all()
    )

    topic_bvids: dict[str, set[str]] = {}
    for bvid, raw in rows:
        if not bvid:
            continue
        for topic in svc.split_topics_text(raw):
            topic_bvids.setdefault(topic, set()).add(bvid)

    known_topics: set[str] = {t for topics in COURSE_TOPICS.values() for t in topics}

    courses = []
    total_bvids: set[str] = set()

    for course, ordered_topics in COURSE_TOPICS.items():
        items = []
        course_bvids: set[str] = set()
        for topic in ordered_topics:
            bvids = topic_bvids.get(topic, set())
            items.append({"topic": topic, "count": len(bvids)})
            course_bvids |= bvids
        courses.append({"course": course, "count": len(course_bvids), "topics": items})
        total_bvids |= course_bvids

    other_topics = [(t, len(b)) for t, b in topic_bvids.items() if t not in known_topics]
    other_topics.sort(key=lambda x: x[1], reverse=True)
    if other_topics:
        other_bvids: set[str] = set()
        for t, _ in other_topics:
            other_bvids |= topic_bvids.get(t, set())
        courses.append(
            {
                "course": "其他",
                "count": len(other_bvids),
                "topics": [{"topic": t, "count": c} for t, c in other_topics],
            }
        )
        total_bvids |= other_bvids

    return jsonify({"courses": courses, "total": len(total_bvids)})


@api_bp.get("/difficulties")
def api_difficulties():
    """难度筛选项。"""
    from core import RecommendEngine

    engine = RecommendEngine(db, Video, VideoEnrichment)
    difficulties = engine.get_difficulties()
    return jsonify({"difficulties": difficulties})


@api_bp.get("/roadmap")
def api_roadmap():
    """学习路线占位接口。"""
    phase = svc.clean_filter_value(request.args.get("phase"))
    subject = svc.clean_filter_value(request.args.get("subject"))
    return jsonify({"subject": subject or "", "phase": phase or "", "milestones": []})


# ============================================================
# 6) API：用户（User/Profile/Actions）
# ============================================================


@api_bp.get("/user_profile")
@login_required
def get_user_profile():
    """个人中心数据：用户信息 + 收藏 + 历史（限条数）。"""
    user = current_user
    default_avatar = url_for("static", filename=svc.DEFAULT_AVATAR_STATIC_PATH)
    avatar_path = os.path.join(current_app.config["UPLOAD_FOLDER"], user.头像) if user.头像 else None
    has_avatar_file = avatar_path and os.path.exists(avatar_path)
    avatar_url = url_for("static", filename="avatars/" + user.头像) if has_avatar_file else default_avatar
    nickname = user.昵称 or svc.default_nickname(user.账号)

    fav_actions = (
        UserAction.query.filter_by(用户ID=user.用户ID, 行为类型="fav").order_by(UserAction.创建时间.desc()).all()
    )
    fav_videos = svc.get_videos_from_actions(fav_actions)

    history_query = UserAction.query.filter_by(用户ID=user.用户ID, 行为类型="history").order_by(UserAction.创建时间.desc())
    history_total = history_query.count()
    history_actions = history_query.limit(svc.HISTORY_LIMIT).all()
    history_videos = svc.get_videos_from_actions(history_actions)

    return jsonify(
        {
            "user_info": {
                "username": nickname,
                "account": user.账号,
                "description": user.简介 or "",
                "avatar": avatar_url,
            },
            "favorites": fav_videos,
            "history": history_videos,
            "history_total": history_total,
        }
    )


@api_bp.post("/update_profile")
@login_required
def update_user_profile():
    """更新个人资料：昵称/简介/头像。"""
    user = current_user
    old_avatar = user.头像
    new_avatar_filename = None

    username = request.form.get("username")
    description = request.form.get("description")
    if username is not None:
        cleaned_name = username.strip()
        user.昵称 = cleaned_name or svc.default_nickname(user.账号)
    if description is not None:
        user.简介 = description

    if "avatar" in request.files:
        file = request.files["avatar"]
        try:
            saved = svc.save_avatar_upload(
                file,
                user_id=user.用户ID,
                upload_folder=current_app.config["UPLOAD_FOLDER"],
                max_size=svc.MAX_AVATAR_SIZE,
                allowed_extensions=svc.ALLOWED_AVATAR_EXTENSIONS,
            )
        except ValueError as exc:
            return svc.api_error(str(exc), code=400, http_status=400)
        if saved:
            user.头像 = saved
            new_avatar_filename = saved

    if not svc.commit_or_rollback(db.session):
        return svc.api_error("昵称保存失败，请确认数据库已移除昵称唯一约束", code=400, http_status=400)

    if new_avatar_filename and old_avatar and old_avatar != new_avatar_filename:
        svc.delete_avatar_file(old_avatar, current_app.config["UPLOAD_FOLDER"], logger=current_app.logger)

    return svc.api_ok("更新成功")


@api_bp.post("/delete_account")
@login_required
def delete_account():
    """注销账号：删除用户数据（并尝试清理头像文件）。"""
    user_id = current_user.用户ID
    old_avatar = current_user.头像

    UserAction.query.filter_by(用户ID=user_id).delete()
    User.query.filter_by(用户ID=user_id).delete()
    db.session.commit()
    logout_user()

    if old_avatar:
        svc.delete_avatar_file(old_avatar, current_app.config["UPLOAD_FOLDER"], logger=current_app.logger)

    return svc.api_ok("账号已注销")


@api_bp.post("/log_history")
@login_required
def log_history():
    """记录观看历史（前端进入详情页时调用）。"""
    data = request.get_json(silent=True) or {}
    bvid = data.get("bvid") or request.form.get("bvid")
    if not bvid:
        return svc.api_error("缺少 bvid", http_status=400)
    svc.bump_history(current_user.用户ID, bvid)
    return svc.api_ok("记录成功")


@api_bp.post("/action")
@login_required
def user_action():
    """新增收藏/历史动作（目前前端只用 fav）。"""
    data = request.json or {}
    bvid = data.get("bvid")
    action_type = data.get("type")
    if not bvid or not action_type:
        return svc.api_error("缺少参数", http_status=400)
    if not svc.ensure_action_allowed(action_type):
        return svc.api_error("非法操作", http_status=400)
    created = svc.create_action(current_user.用户ID, bvid, action_type)
    if created:
        return svc.api_ok("操作成功")
    return svc.api_ok("已存在")


@api_bp.post("/remove_action")
@login_required
def remove_action():
    """删除收藏/历史动作。"""
    data = request.json or {}
    bvid = data.get("bvid")
    action_type = data.get("type")
    if not bvid or not action_type:
        return svc.api_error("缺少参数", http_status=400)
    if not svc.ensure_action_allowed(action_type):
        return svc.api_error("非法操作", http_status=400)
    if svc.delete_action(current_user.用户ID, bvid, action_type):
        return svc.api_ok("删除成功")
    return svc.api_error("失败", http_status=404, code=404)

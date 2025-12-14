"""数据模型定义：封装所有与数据库表对应的 SQLAlchemy ORM 类。"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import func

db = SQLAlchemy()


class Video(db.Model):
    """采集到的 B 站课程/题解视频：既存储播放互动数据，也存储分类结果与补充信息。"""

    __tablename__ = 'videos'

    # 主键使用 bvid，方便前后端直链跳转。
    bvid = db.Column(db.String(20), primary_key=True)

    # 基础标识与文本
    aid = db.Column(db.BigInteger)  # av 号（可选）
    video_url = db.Column(db.String(255))
    title = db.Column(db.String(255))
    desc = db.Column(db.Text)  # 详情页简介（用于 NLP 训练/分析）

    # UP 主信息
    up_name = db.Column(db.String(100), index=True)
    up_mid = db.Column(db.BigInteger)
    up_face = db.Column(db.String(500))

    # 封面
    pic_url = db.Column(db.String(500))

    # 播放互动数据
    view_count = db.Column(db.Integer)
    danmaku_count = db.Column(db.Integer)
    reply_count = db.Column(db.Integer)
    favorite_count = db.Column(db.Integer)
    like_count = db.Column(db.Integer)
    coin_count = db.Column(db.Integer)
    share_count = db.Column(db.Integer)

    duration = db.Column(db.Integer)  # 秒
    pubdate = db.Column(db.DateTime, index=True)

    # 标签：tags 保持兼容（优先存真实 tags，无则回退关键词）；tag_names/source_keyword 供分析更精细使用
    tags = db.Column(db.String(500))
    tag_names = db.Column(db.String(1000))
    source_keyword = db.Column(db.String(255))

    # B 站原始分区信息（不要与本项目的分类字段混用）
    bili_tid = db.Column(db.Integer)
    bili_tname = db.Column(db.String(100))

    # 本项目分类字段
    category = db.Column(db.String(50))
    phase = db.Column(db.String(50), index=True)
    subject = db.Column(db.String(50), index=True)

    dry_goods_ratio = db.Column(db.Float)
    crawl_time = db.Column(db.DateTime)


class User(UserMixin, db.Model):
    """用户账户表：仅存储基本资料和密码哈希。"""

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(50), unique=True, index=True, nullable=False)
    username = db.Column(db.String(50))
    password = db.Column(db.String(255))
    description = db.Column(db.String(255))
    avatar = db.Column(db.String(200))


class UserAction(db.Model):
    """用户行为表：收藏/待看/历史记录都落在这里。"""

    __tablename__ = 'user_actions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    bvid = db.Column(db.String(20))
    action_type = db.Column(db.String(20))
    status = db.Column(db.Integer, default=0)
    create_time = db.Column(db.DateTime, default=func.now())

    __table_args__ = (
        db.UniqueConstraint('user_id', 'bvid', 'action_type', name='uq_user_action'),
    )

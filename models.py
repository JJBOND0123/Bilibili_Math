"""数据模型定义：封装所有与数据库表对应的 SQLAlchemy ORM 类。"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.sql import func

db = SQLAlchemy()


class Video(db.Model):
    """视频表：存储 B 站视频元数据（爬虫原始字段）"""

    __tablename__ = "videos"

    # === 基础信息（视频ID 为主键） ===
    视频ID = db.Column(db.String(20), primary_key=True, comment="B站视频ID")
    AV号 = db.Column(db.BigInteger, comment="AV号")
    视频链接 = db.Column(db.String(200), comment="视频链接")
    标题 = db.Column(db.String(500), comment="视频标题")
    描述 = db.Column(db.Text, comment="视频描述")

    # === UP主信息 ===
    UP主名称 = db.Column(db.String(100), comment="UP主名称")
    UP主ID = db.Column(db.BigInteger, comment="UP主ID")
    UP主头像 = db.Column(db.String(300), comment="UP主头像")

    # === 封面与时长 ===
    封面图 = db.Column(db.String(300), comment="封面图链接")
    时长 = db.Column(db.Integer, default=0, comment="时长(秒)")
    发布时间 = db.Column(db.DateTime, comment="发布时间")

    # === 互动数据 ===
    播放量 = db.Column(db.BigInteger, default=0, comment="播放量")
    弹幕数 = db.Column(db.Integer, default=0, comment="弹幕数")
    评论数 = db.Column(db.Integer, default=0, comment="评论数")
    收藏数 = db.Column(db.Integer, default=0, comment="收藏数")
    点赞数 = db.Column(db.Integer, default=0, comment="点赞数")
    投币数 = db.Column(db.Integer, default=0, comment="投币数")
    分享数 = db.Column(db.Integer, default=0, comment="分享数")

    # === 标签 ===
    标签 = db.Column(db.Text, comment="视频标签(逗号分隔)")

    # === 爬取时间 ===
    爬取时间 = db.Column(db.DateTime, comment="爬虫抓取时间")

    enrichment = db.relationship(
        "VideoEnrichment",
        back_populates="video",
        uselist=False,
    )


class VideoEnrichment(db.Model):
    """视频衍生字段表：知识点/难度/质量分/是否推荐 等离线计算结果。"""

    __tablename__ = "video_enrichments"

    视频ID = db.Column(
        db.String(20),
        db.ForeignKey("videos.视频ID", ondelete="CASCADE"),
        primary_key=True,
        comment="B站视频ID",
    )

    # === 离线分类/评分结果 ===
    科目 = db.Column(
        db.String(20),
        nullable=True,
        comment="所属科目: 高等数学/线性代数/概率论与数理统计",
    )
    知识点 = db.Column(db.String(100), comment="知识点主题（离线预测，逗号分隔）")
    难度 = db.Column(db.String(20), comment="难度等级: 入门/进阶/高阶")
    质量分 = db.Column(db.Float, default=0, comment="综合评分 0-100")
    是否推荐 = db.Column(db.Boolean, default=False, comment="是否推荐")

    # === 时间戳 ===
    更新时间 = db.Column(
        db.DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    video = db.relationship("Video", back_populates="enrichment", uselist=False)

    __table_args__ = (
        db.Index("idx_video_enrich_subject", "科目"),
        db.Index("idx_video_enrich_topic", "知识点"),
        db.Index("idx_video_enrich_difficulty", "难度"),
        db.Index("idx_video_enrich_quality_score", "质量分"),
        db.Index("idx_video_enrich_is_recommended", "是否推荐"),
    )


class User(UserMixin, db.Model):
    """用户表：系统登录用户"""

    __tablename__ = "users"

    用户ID = db.Column(db.Integer, primary_key=True, comment="用户ID")
    账号 = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        comment="登录账号",
    )
    昵称 = db.Column(db.String(50), comment="昵称")
    密码 = db.Column(db.String(255), comment="密码哈希")
    简介 = db.Column(
        db.String(255),
        server_default="努力学习的高数人",
        comment="个人简介/收藏JSON",
    )
    头像 = db.Column(
        db.String(200),
        server_default="",
        comment="头像路径",
    )

    def get_id(self):
        """Flask-Login 需要的方法，返回用户ID字符串"""
        return str(self.用户ID)


class UserAction(db.Model):
    """用户行为表：收藏/历史记录都落在这里。"""

    __tablename__ = "user_actions"

    行为ID = db.Column(db.Integer, primary_key=True, comment="行为ID")
    用户ID = db.Column(db.Integer, comment="用户ID")
    视频ID = db.Column(db.String(20), comment="B站视频ID")
    行为类型 = db.Column(db.String(20), comment="行为类型(收藏/历史)")
    创建时间 = db.Column(db.DateTime, default=func.now(), comment="创建时间")

    __table_args__ = (
        db.UniqueConstraint("用户ID", "视频ID", "行为类型", name="uq_user_action"),
    )

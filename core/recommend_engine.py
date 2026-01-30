"""推荐引擎：多策略视频推荐"""

from enum import Enum
from typing import Dict, List, Optional, Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, desc, func




COURSE_TOPICS: dict[str, list[str]] = {
    # 高等数学
    "高数": [
        "极限与连续",
        "导数与微分",
        "积分",
        "微分方程",
        "级数",
        "多元函数",
    ],
    # 线性代数
    "线代": [
        "行列式",
        "矩阵",
        "向量",
        "线性方程组",
        "特征值",
    ],
    # 概率论
    "概率": [
        "概率基础",
        "随机变量",
        "数理统计",
    ],
}

COURSE_ALIASES: dict[str, str] = {
    "高等数学": "高数",
    "线性代数": "线代",
    "概率论": "概率",
    "概率论与数理统计": "概率",
}


def normalize_course(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    return COURSE_ALIASES.get(v, v)


def resolve_course_topics(course: str | None) -> list[str]:
    course = normalize_course(course)
    if not course:
        return []
    return list(COURSE_TOPICS.get(course, []))

class RecommendStrategy(Enum):
    """推荐策略枚举"""
    HOT = "hot"           # 热门（quality_score 排序）
    POPULAR = "popular"   # 高口碑（收藏率排序）
    LATEST = "latest"     # 最新（pubdate 排序）
    EASY = "easy"         # 入门难度
    MEDIUM = "medium"     # 进阶难度
    HARD = "hard"         # 高阶难度


class RecommendEngine:
    """推荐引擎"""

    def __init__(self, db: SQLAlchemy, video_model, enrichment_model=None):
        """初始化推荐引擎

        Args:
            db: SQLAlchemy 实例
            video_model: Video ORM 模型类
            enrichment_model: VideoEnrichment ORM 模型类（可选）
        """
        self.db = db
        self.Video = video_model
        self.Enrichment = enrichment_model

    def recommend(
        self,
        strategy: RecommendStrategy = RecommendStrategy.HOT,
        course: Optional[str] = None,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        up_name: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        only_recommended: bool = True,
    ) -> Dict[str, Any]:
        """获取推荐视频列表"""
        query = self._build_base_query(only_recommended)

        # EASY/MEDIUM/HARD 属于"难度预设"，统一在后端做一次解析，避免重复筛选
        strategy, difficulty = self._resolve_strategy_and_difficulty(strategy, difficulty)

        # 应用筛选条件
        query = self._apply_filters(query, course, topic, difficulty, up_name, search_query)

        # 应用策略特定的筛选和排序
        query = self._apply_strategy(query, strategy)

        # 分页
        total = query.count()
        pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size

        rows = query.offset(offset).limit(page_size).all()
        if self.Enrichment is None:
            items = [self._serialize_video(v, None) for v in rows]
        else:
            items = [self._serialize_video(v, enrich) for v, enrich in rows]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def _resolve_strategy_and_difficulty(
        self,
        strategy: RecommendStrategy,
        difficulty: Optional[str],
    ) -> tuple[RecommendStrategy, Optional[str]]:
        """将 EASY/MEDIUM/HARD 映射为 difficulty + HOT 排序，避免与 difficulty 叠加筛选。"""
        preset_map = {
            RecommendStrategy.EASY: "入门",
            RecommendStrategy.MEDIUM: "进阶",
            RecommendStrategy.HARD: "高阶",
        }

        preset = preset_map.get(strategy)
        if not preset:
            return strategy, difficulty

        # 如果前端显式传了 difficulty，就以 difficulty 为准；预设仅决定默认排序（等同 HOT）
        if difficulty:
            return RecommendStrategy.HOT, difficulty

        return RecommendStrategy.HOT, preset

    def _build_base_query(self, only_recommended: bool):
        """构建基础查询"""
        if self.Enrichment is None:
            query = self.Video.query
        else:
            query = (
                self.db.session.query(self.Video, self.Enrichment)
                .outerjoin(self.Enrichment, self.Enrichment.视频ID == self.Video.视频ID)
            )

        if only_recommended and self.Enrichment is not None:
            query = query.filter(self.Enrichment.是否推荐 == True)

        # 【核心过滤】在基础层就过滤出三科数据，确保所有推荐都排除未分类内容
        if self.Enrichment is not None:
            query = query.filter(
                self.Enrichment.科目.in_(["高等数学", "线性代数", "概率论与数理统计"])
            )

        # 过滤无效数据
        query = query.filter(
            self.Video.视频ID.isnot(None),
            self.Video.标题.isnot(None),
            self.Video.播放量 > 0,
        )

        return query

    def _apply_filters(
        self,
        query,
        course: Optional[str],
        topic: Optional[str],
        difficulty: Optional[str],
        up_name: Optional[str],
        search_query: Optional[str],
    ):
        """应用筛选条件"""
        if self.Enrichment is not None:
            # topic 字段现在是逗号分隔的多知识点，使用 LIKE 匹配
            if topic:
                query = query.filter(self.Enrichment.知识点.like(f"%{topic}%"))
            else:
                allowed_topics = resolve_course_topics(course)
                if allowed_topics:
                    # 任一知识点匹配即可
                    from sqlalchemy import or_
                    conditions = [self.Enrichment.知识点.like(f"%{t}%") for t in allowed_topics]
                    query = query.filter(or_(*conditions))

            if difficulty:
                query = query.filter(self.Enrichment.难度 == difficulty)

        if up_name:
            query = query.filter(self.Video.UP主名称.like(f"%{up_name}%"))

        if search_query:
            query = query.filter(self.Video.标题.like(f"%{search_query}%"))

        return query

    def _apply_strategy(self, query, strategy: RecommendStrategy):
        """应用推荐策略"""
        if strategy == RecommendStrategy.HOT:
            if self.Enrichment is not None:
                query = query.order_by(desc(self.Enrichment.质量分))
            else:
                query = query.order_by(desc(self.Video.播放量))

        elif strategy == RecommendStrategy.POPULAR:
            # 高口碑：按收藏率（收藏/播放）排序
            query = query.order_by(
                desc(
                    func.cast(self.Video.收藏数, self.db.Float)
                    / func.greatest(self.Video.播放量, 1)
                )
            )

        elif strategy == RecommendStrategy.LATEST:
            query = query.order_by(desc(self.Video.发布时间))

        elif strategy in {RecommendStrategy.EASY, RecommendStrategy.MEDIUM, RecommendStrategy.HARD}:
            # 难度筛选已由 `_resolve_strategy_and_difficulty` 处理
            if self.Enrichment is not None:
                query = query.order_by(desc(self.Enrichment.质量分))
            else:
                query = query.order_by(desc(self.Video.播放量))

        return query

    def _serialize_video(self, video, enrich) -> Dict:
        """序列化视频对象为字典"""
        return {
            "bvid": video.视频ID,
            "title": video.标题,
            "up_name": video.UP主名称,
            "up_mid": video.UP主ID,
            "up_face": video.UP主头像,
            "pic_url": video.封面图,
            "duration": video.时长,
            "pubdate": video.发布时间.isoformat() if video.发布时间 else None,
            "view_count": video.播放量,
            "quality_score": getattr(enrich, "质量分", None),
        }

    def get_topics(self) -> List[Dict]:
        """获取所有知识点及视频数量"""
        if self.Enrichment is None:
            return []

        result = (
            self.db.session.query(
                self.Enrichment.知识点,
                func.count(self.Enrichment.视频ID).label("count"),
            )
            .filter(self.Enrichment.知识点.isnot(None), self.Enrichment.知识点 != "")
            .group_by(self.Enrichment.知识点)
            .order_by(desc("count"))
            .all()
        )
        return [{"topic": row[0], "count": row[1]} for row in result]

    def get_difficulties(self) -> List[Dict]:
        """获取所有难度级别及视频数量"""
        if self.Enrichment is None:
            return []

        result = (
            self.db.session.query(
                self.Enrichment.难度,
                func.count(self.Enrichment.视频ID).label("count"),
            )
            .filter(
                self.Enrichment.难度.isnot(None),
                self.Enrichment.难度 != "",
            )
            .group_by(self.Enrichment.难度)
            .order_by(desc("count"))
            .all()
        )
        return [{"difficulty": row[0], "count": row[1]} for row in result]

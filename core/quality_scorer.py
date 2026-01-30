"""视频质量评分器

评分公式：
综合评分 = 互动分×0.4 + 时长分×0.2 + 新鲜度×0.2 + UP主分×0.2

评分维度说明：
- 互动分：基于收藏率、点赞率、投币率的加权平均
- 时长分：5-30分钟视频得高分，过短或过长扣分
- 新鲜度：近1年发布得高分，超过2年逐渐降低
- UP主分：基于 UP 主历史表现（播放量、粉丝等）
"""

import math
from datetime import datetime
from typing import Dict, List, Optional

# ============================================================================
# 权重配置
# ============================================================================

WEIGHT_ENGAGEMENT = 0.40  # 互动分权重
WEIGHT_DURATION = 0.20    # 时长分权重
WEIGHT_FRESHNESS = 0.20   # 新鲜度权重
WEIGHT_UPLOADER = 0.20    # UP主分权重

# 互动分内部权重
ENGAGEMENT_WEIGHTS = {
    "favorite_rate": 0.5,  # 收藏率
    "like_rate": 0.3,      # 点赞率
    "coin_rate": 0.2,      # 投币率
}

# 理想时长范围（秒）
IDEAL_DURATION_MIN = 5 * 60   # 5 分钟
IDEAL_DURATION_MAX = 30 * 60  # 30 分钟

# 推荐阈值
RECOMMEND_THRESHOLD = 60


class QualityScorer:
    """视频质量评分器"""

    def __init__(self, known_uploader_scores: Optional[Dict[str, float]] = None):
        """
        初始化评分器

        Args:
            known_uploader_scores: 已知 UP 主评分字典 {up_name: score}
        """
        self.uploader_scores = known_uploader_scores or self._default_uploader_scores()

    def _default_uploader_scores(self) -> Dict[str, float]:
        """默认的优质 UP 主评分表"""
        return {
            "宋浩老师官方": 95,
            "宋浩老师": 95,
            "张宇考研数学": 92,
            "汤家凤老师": 90,
            "武忠祥老师": 90,
            "武忠祥": 90,
            "李永乐老师": 88,
            "余丙森老师": 85,
            "3Blue1Brown": 98,
            "3Blue1Brown中国": 95,
            "妈咪说MommyTalk": 85,
        }

    def score(self, video: Dict) -> float:
        """
        计算视频综合评分

        Args:
            video: 视频字典，需包含以下字段：
                - view_count, favorite_count, like_count, coin_count
                - duration
                - pubdate (datetime 或 timestamp)
                - up_name

        Returns:
            综合评分 0-100
        """
        engagement = self._score_engagement(video)
        duration = self._score_duration(video)
        freshness = self._score_freshness(video)
        uploader = self._score_uploader(video)

        total = (
            engagement * WEIGHT_ENGAGEMENT +
            duration * WEIGHT_DURATION +
            freshness * WEIGHT_FRESHNESS +
            uploader * WEIGHT_UPLOADER
        )

        return round(min(100, max(0, total)), 2)

    def _score_engagement(self, video: Dict) -> float:
        """
        计算互动分 (0-100)

        公式：
        - 收藏率 = favorite_count / view_count
        - 点赞率 = like_count / view_count
        - 投币率 = coin_count / view_count
        """
        views = max(video.get("view_count", 0), 1)
        favorites = video.get("favorite_count", 0)
        likes = video.get("like_count", 0)
        coins = video.get("coin_count", 0)

        # 计算比率（防止除零）
        fav_rate = favorites / views
        like_rate = likes / views
        coin_rate = coins / views

        # 归一化（经验值：收藏率 2% = 100分，点赞率 5% = 100分，投币率 1% = 100分）
        fav_score = min(100, fav_rate / 0.02 * 100)
        like_score = min(100, like_rate / 0.05 * 100)
        coin_score = min(100, coin_rate / 0.01 * 100)

        # 加权平均
        return (
            fav_score * ENGAGEMENT_WEIGHTS["favorite_rate"] +
            like_score * ENGAGEMENT_WEIGHTS["like_rate"] +
            coin_score * ENGAGEMENT_WEIGHTS["coin_rate"]
        )

    def _score_duration(self, video: Dict) -> float:
        """
        计算时长分 (0-100)

        - 5-30 分钟：满分
        - 过短（<2分钟）：低分
        - 过长（>60分钟）：递减
        """
        duration = video.get("duration", 0)

        if duration < 60:  # 小于 1 分钟
            return 20
        elif duration < 2 * 60:  # 1-2 分钟
            return 40
        elif duration < IDEAL_DURATION_MIN:  # 2-5 分钟
            return 60
        elif duration <= IDEAL_DURATION_MAX:  # 5-30 分钟（理想）
            return 100
        elif duration <= 60 * 60:  # 30-60 分钟
            return 80
        else:  # 超过 60 分钟
            # 每多 30 分钟扣 10 分，最低 50 分
            penalty = (duration - 60 * 60) // (30 * 60) * 10
            return max(50, 80 - penalty)

    def _score_freshness(self, video: Dict) -> float:
        """
        计算新鲜度分 (0-100)

        - 近 6 个月：满分
        - 6-12 个月：90 分
        - 1-2 年：70 分
        - 2-3 年：50 分
        - 超过 3 年：30 分
        """
        pubdate = video.get("pubdate")
        if not pubdate:
            return 50  # 未知发布时间给中间分

        if isinstance(pubdate, (int, float)):
            pub_dt = datetime.fromtimestamp(pubdate)
        elif isinstance(pubdate, str):
            try:
                pub_dt = datetime.fromisoformat(pubdate.replace("Z", "+00:00"))
            except ValueError:
                return 50
        else:
            pub_dt = pubdate

        days_ago = (datetime.now() - pub_dt).days

        if days_ago < 180:  # 6 个月
            return 100
        elif days_ago < 365:  # 1 年
            return 90
        elif days_ago < 730:  # 2 年
            return 70
        elif days_ago < 1095:  # 3 年
            return 50
        else:
            return 30

    def _score_uploader(self, video: Dict) -> float:
        """
        计算 UP 主分 (0-100)

        基于已知优质 UP 主名单进行评分
        """
        up_name = video.get("up_name", "")

        # 检查是否为已知优质 UP 主
        for known_name, score in self.uploader_scores.items():
            if known_name in up_name or up_name in known_name:
                return score

        # 未知 UP 主给基准分
        return 60

    def batch_score(self, videos: List[Dict], set_recommend: bool = True) -> List[Dict]:
        """
        批量评分视频

        Args:
            videos: 视频字典列表
            set_recommend: 是否同时设置 is_recommended 字段

        Returns:
            更新后的视频列表，新增 quality_score 和 is_recommended 字段
        """
        for video in videos:
            score = self.score(video)
            video["quality_score"] = score
            if set_recommend:
                video["is_recommended"] = score >= RECOMMEND_THRESHOLD

        return videos

    def get_top_videos(
        self, videos: List[Dict], top_n: int = 50, min_score: float = 0
    ) -> List[Dict]:
        """
        获取评分最高的视频

        Args:
            videos: 视频列表
            top_n: 返回数量
            min_score: 最低评分阈值

        Returns:
            排序后的视频列表
        """
        scored = [v for v in videos if v.get("quality_score", 0) >= min_score]
        scored.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        return scored[:top_n]

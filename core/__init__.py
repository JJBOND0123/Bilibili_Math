"""核心业务模块

包含：
- TopicClassifier: 知识点分类器
- QualityScorer: 质量评分器
- RecommendEngine: 推荐引擎
- process_videos: 批处理脚本
"""

from .topic_classifier import (
    TopicClassifier,
    TOPICS,
    DIFFICULTY_LEVELS,
    TOPIC_KEYWORDS,
)
from .quality_scorer import QualityScorer, RECOMMEND_THRESHOLD
from .recommend_engine import RecommendEngine, RecommendStrategy, COURSE_TOPICS

__all__ = [
    "TopicClassifier",
    "TOPICS",
    "DIFFICULTY_LEVELS",
    "TOPIC_KEYWORDS",
    "QualityScorer",
    "RECOMMEND_THRESHOLD",
    "RecommendEngine",
    "RecommendStrategy",
    "COURSE_TOPICS",
]

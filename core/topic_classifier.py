"""知识点分类器：基于关键词规则的视频分类"""

import re
from typing import Dict, List, Tuple, Optional

# ============================================================================
# 知识点类别（按学科顺序排列）
# ============================================================================

TOPICS = [
    # 高等数学
    "极限与连续",
    "导数与微分",
    "积分",
    "微分方程",
    "级数",
    "多元函数",
    # 线性代数
    "行列式",
    "矩阵",
    "向量",
    "线性方程组",
    "特征值",
    # 概率论
    "概率基础",
    "随机变量",
    "数理统计",
    # 其他
    "考研相关",
    "竞赛",
    "直观",
]

DIFFICULTY_LEVELS = ["入门", "进阶", "高阶"]

# ============================================================================
# 三科范围定义
# ============================================================================

# 高等数学知识点
CALCULUS_TOPICS = {
    "极限与连续",
    "导数与微分",
    "积分",
    "微分方程",
    "级数",
    "多元函数",
}

# 线性代数知识点
LINEAR_ALGEBRA_TOPICS = {
    "行列式",
    "矩阵",
    "向量",
    "线性方程组",
    "特征值",
}

# 概率论知识点
PROBABILITY_TOPICS = {
    "概率基础",
    "随机变量",
    "数理统计",
}

# 讲师名字识别（由分类脚本识别）
LECTURER_KEYWORDS = {
    "高等数学": ["宋浩", "张宇", "汤家凤"],
    "线性代数": ["李永乐", "武忠祥"],
    "概率论与数理统计": ["宋浩"],  # 宋浩也讲概率论
}

# ============================================================================
# 关键词规则表（用于规则分类）
# ============================================================================

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    # 高等数学
    "极限与连续": ["极限", "连续", "无穷小", "无穷大", "夹逼", "洛必达", "等价无穷小"],
    "导数与微分": ["导数", "微分", "求导", "链式法则", "隐函数", "参数方程导数", "高阶导数"],
    "积分": ["积分", "定积分", "不定积分", "换元", "分部积分", "变限积分", "广义积分"],
    "微分方程": ["微分方程", "一阶", "二阶", "常微分", "偏微分", "通解", "特解"],
    "级数": ["级数", "幂级数", "泰勒", "麦克劳林", "傅里叶", "收敛", "发散"],
    "多元函数": ["多元函数", "偏导", "全微分", "重积分", "二重积分", "三重积分", "曲线积分", "曲面积分"],
    # 线性代数
    "行列式": ["行列式", "克拉默", "代数余子式"],
    "矩阵": ["矩阵", "逆矩阵", "伴随矩阵", "矩阵乘法", "初等变换"],
    "向量": ["向量", "向量空间", "线性相关", "线性无关", "基", "维数", "正交"],
    "线性方程组": ["线性方程组", "齐次", "非齐次", "解的结构", "基础解系"],
    "特征值": ["特征值", "特征向量", "相似", "对角化", "二次型"],
    # 概率论
    "概率基础": ["概率", "古典概型", "条件概率", "全概率", "贝叶斯"],
    "随机变量": ["随机变量", "分布", "期望", "方差", "协方差", "二维分布"],
    "数理统计": ["统计", "估计", "假设检验", "置信区间", "回归"],
    # 其他
    "考研相关": ["考研", "真题", "刷题", "数一", "数二", "数三", "历年"],
    "竞赛": ["竞赛", "数学竞赛", "建模"],
    "直观": ["本质", "直观", "可视化", "3Blue1Brown", "科普", "通俗"],
}

DIFFICULTY_KEYWORDS: Dict[str, List[str]] = {
    "入门": ["入门", "基础", "零基础", "小白", "初学", "通俗", "简单", "快速入门", "从零开始"],
    "进阶": ["进阶", "提高", "强化", "深入", "考研", "详解", "技巧"],
    "高阶": ["高阶", "难题", "拔高", "竞赛", "证明", "深度", "数学家"],
}

# ==========================================================================
# 负向过滤：检测到这些关键词则跳过分类（优先级高于正向匹配）
# ==========================================================================

NON_MATH_CONTEXT: List[str] = [
    # 游戏相关
    "游戏", "MC", "Minecraft", "我的世界", "收容", "模组", "挑战",
    "极限模式", "生存模式", "创造模式", "生存挑战",
    "原神", "王者荣耀", "英雄联盟", "LOL", "吃鸡", "PUBG",
    "steam", "主播", "直播", "游戏解说", "实况", "通关",
    # 生活/科技 vlog
    "vlog", "日常", "开箱", "装修", "改装", "汽车", "跑车", "超跑",
    "黑洞", "火箭", "航天", "飞机",
    # 娱乐
    "鬼畜", "搞笑", "恶搞", "整蛊", "整活",
    # 移除陆地等特定游戏内容
    "移除陆地", "一格物品栏", "加速100",
]


class TopicClassifier:
    """知识点分类器（纯关键词规则）"""

    def classify(self, title: str, tags: str = "", desc: str = "") -> Tuple[List[str], str]:
        """
        对视频进行分类

        Args:
            title: 视频标题
            tags: 视频标签（逗号分隔）
            desc: 视频描述

        Returns:
            (topics, difficulty) 元组，topics 为知识点列表（可能多个）
        """
        title = title or ""
        tags = tags or ""
        desc = desc or ""
        normalized_text = self._normalize_text(f"{title} {tags} {desc}")

        # 知识点分类（可返回多个）
        topics = self._classify_topics(normalized_text)

        # 难度分类
        difficulty = self._classify_difficulty(normalized_text)

        return topics, difficulty

    def classify_with_subject(
        self, title: str, tags: str = "", desc: str = ""
    ) -> Tuple[List[str], str, Optional[str]]:
        """
        对视频进行分类并推断所属科目

        Args:
            title: 视频标题
            tags: 视频标签（逗号分隔）
            desc: 视频描述

        Returns:
            (topics, difficulty, subject) 三元组
            subject: "高等数学" / "线性代数" / "概率论与数理统计" / None
        """
        # ⭐ 负向过滤：检测到非数学内容则跳过分类
        if self._is_non_math_content(title, tags, desc):
            return [], "进阶", None

        topics, difficulty = self.classify(title, tags, desc)
        subject = self._infer_subject(topics, title, tags, desc)
        return topics, difficulty, subject

    def _is_non_math_content(self, title: str, tags: str = "", desc: str = "") -> bool:
        """
        检测是否为非数学内容（游戏、vlog、娱乐等）
        
        Returns:
            True 表示是非数学内容，应跳过分类
        """
        # 合并标题和标签进行检测（描述通常太长，且噪音多）
        text = f"{title or ''} {tags or ''}".lower()
        
        for keyword in NON_MATH_CONTEXT:
            if keyword.lower() in text:
                return True
        return False

    def _normalize_text(self, value: str) -> str:
        """文本归一化：小写 + 去空白，提升匹配鲁棒性。"""
        value = (value or "").lower()
        return re.sub(r"\s+", "", value)

    def _classify_topics(self, normalized_text: str) -> List[str]:
        """根据 title+tags+desc 匹配知识点（一个视频可归类到多个知识点）"""
        matched: List[str] = []

        for topic in TOPICS:
            keywords = TOPIC_KEYWORDS.get(topic, [])
            if any(self._normalize_text(kw) in normalized_text for kw in keywords if kw):
                matched.append(topic)

        return matched

    def _classify_difficulty(self, normalized_text: str) -> str:
        """分类难度等级"""
        for difficulty in DIFFICULTY_LEVELS:
            keywords = DIFFICULTY_KEYWORDS.get(difficulty, [])
            if any(self._normalize_text(kw) in normalized_text for kw in keywords if kw):
                return difficulty

        # 默认返回「进阶」
        return "进阶"

    def _infer_subject(
        self, topics: List[str], title: str = "", tags: str = "", desc: str = ""
    ) -> Optional[str]:
        """
        根据知识点和讲师名字推断所属科目

        Args:
            topics: 分类得到的知识点列表
            title: 视频标题
            tags: 视频标签
            desc: 视频描述

        Returns:
            科目名称或 None
        """
        if not topics:
            return self._detect_lecturer_subject(title, tags, desc)

        # 统计各科的知识点数量
        calculus_count = sum(1 for t in topics if t in CALCULUS_TOPICS)
        linear_count = sum(1 for t in topics if t in LINEAR_ALGEBRA_TOPICS)
        prob_count = sum(1 for t in topics if t in PROBABILITY_TOPICS)

        # 如果有知识点匹配，返回匹配数最多的科目
        scores = {
            "高等数学": calculus_count,
            "线性代数": linear_count,
            "概率论与数理统计": prob_count,
        }

        max_score = max(scores.values())
        if max_score > 0:
            for subject, score in scores.items():
                if score == max_score:
                    return subject

        # 如果没有知识点匹配，尝试从讲师名字推断
        return self._detect_lecturer_subject(title, tags, desc)

    def _detect_lecturer_subject(self, title: str, tags: str, desc: str) -> Optional[str]:
        """
        从讲师名字推断科目

        Args:
            title: 视频标题
            tags: 视频标签
            desc: 视频描述

        Returns:
            科目名称或 None
        """
        normalized_text = self._normalize_text(f"{title} {tags} {desc}")

        for subject, lecturers in LECTURER_KEYWORDS.items():
            for lecturer in lecturers:
                if self._normalize_text(lecturer) in normalized_text:
                    return subject

        return None

    def batch_classify(self, videos: List[Dict]) -> List[Dict]:
        """
        批量分类视频

        Args:
            videos: 视频字典列表，需包含 title, tags, desc 字段

        Returns:
            更新后的视频列表，新增 topics（列表）, difficulty, subject 字段
        """
        for video in videos:
            title = video.get("title", "")
            tags = video.get("tags", "") or video.get("tag_names", "")
            desc = video.get("desc", "")

            topics, difficulty, subject = self.classify_with_subject(title, tags, desc)
            video["topics"] = topics
            video["difficulty"] = difficulty
            video["subject"] = subject

        return videos

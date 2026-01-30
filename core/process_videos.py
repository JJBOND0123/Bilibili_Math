"""批量处理脚本：对已有视频数据进行知识点分类和质量评分

使用方法：
    python -m core.process_videos

功能：
1. 从数据库读取所有视频
2. 使用 TopicClassifier 进行知识点分类
3. 使用 QualityScorer 进行质量评分
4. 将衍生字段写入 video_enrichments 表（知识点、难度、质量分、是否推荐）
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask
from config import Config
from models import db, Video, VideoEnrichment
from core.topic_classifier import TopicClassifier
from core.quality_scorer import QualityScorer

# 推荐阈值
RECOMMEND_THRESHOLD = 60


def create_app():
    """创建 Flask 应用上下文"""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


def process_videos(batch_size: int = 100, dry_run: bool = False):
    """
    批量处理视频数据：分类、评分、记录科目

    Args:
        batch_size: 每批处理数量
        dry_run: 如果为 True，只打印不写库
    """
    app = create_app()

    with app.app_context():
        # 确保衍生表存在
        db.create_all()

        # 初始化分类器和评分器
        classifier = TopicClassifier()
        scorer = QualityScorer()

        # 统计
        total = Video.query.count()
        processed = 0
        classified = 0
        recommended = 0
        
        # 按科目统计
        by_subject = {
            "高等数学": 0,
            "线性代数": 0,
            "概率论与数理统计": 0,
            "未分类": 0,
        }

        print(f"开始处理 {total} 条视频数据...")
        print(f"干预模式: {dry_run}")
        print("-" * 50)

        # 分批处理
        offset = 0
        while offset < total:
            videos = Video.query.offset(offset).limit(batch_size).all()
            if not videos:
                break

            for video in videos:
                # 1. 知识点分类 + 科目推断 ⭐ 改进
                topics, difficulty, subject = classifier.classify_with_subject(
                    video.标题 or "",
                    video.标签 or "",
                    video.描述 or "",
                )
                # 多个知识点用逗号连接存储
                topic_str = ",".join(topics) if topics else ""

                # 2. 质量评分
                video_dict = {
                    "view_count": video.播放量 or 0,
                    "favorite_count": video.收藏数 or 0,
                    "like_count": video.点赞数 or 0,
                    "coin_count": video.投币数 or 0,
                    "duration": video.时长 or 0,
                    "pubdate": video.发布时间,
                    "up_name": video.UP主名称 or "",
                }
                quality_score = scorer.score(video_dict)
                is_recommended = quality_score >= RECOMMEND_THRESHOLD

                # 3. 写入衍生表
                if not dry_run:
                    enrich = db.session.get(VideoEnrichment, video.视频ID)
                    if not enrich:
                        enrich = VideoEnrichment(视频ID=video.视频ID)
                        db.session.add(enrich)
                    enrich.科目 = subject  # ⭐ 新增：保存科目
                    enrich.知识点 = topic_str
                    enrich.难度 = difficulty
                    enrich.质量分 = quality_score
                    enrich.是否推荐 = is_recommended

                # 统计
                if topics:
                    classified += 1
                if is_recommended:
                    recommended += 1
                
                # 按科目统计
                if subject:
                    by_subject[subject] += 1
                else:
                    by_subject["未分类"] += 1
                    
                processed += 1

            # 提交这一批
            if not dry_run:
                db.session.commit()

            print(f"已处理: {processed}/{total} | 已分类: {classified} | 推荐: {recommended}")
            offset += batch_size

        print("-" * 50)
        print("处理完成！")
        print(f"  总数: {total}")
        print(f"  已分类: {classified} ({classified / total * 100:.1f}%)")
        print(f"  推荐数: {recommended} ({recommended / total * 100:.1f}%)")
        print(f"\n  科目分布:")
        print(f"    高等数学: {by_subject['高等数学']} ({by_subject['高等数学'] / total * 100:.1f}%)")
        print(f"    线性代数: {by_subject['线性代数']} ({by_subject['线性代数'] / total * 100:.1f}%)")
        print(f"    概率论与数理统计: {by_subject['概率论与数理统计']} ({by_subject['概率论与数理统计'] / total * 100:.1f}%)")
        print(f"    未分类: {by_subject['未分类']} ({by_subject['未分类'] / total * 100:.1f}%)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="批量处理视频数据")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="每批处理数量（默认 100）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印不写库",
    )
    args = parser.parse_args()

    process_videos(batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

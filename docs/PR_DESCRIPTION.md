# Pull Request: v7 Major Refactor

## 🏗️ 变更类型

- [x] **Refactor** - 代码重构（架构调整、模块合并）
- [x] **Database** - 数据库结构变更
- [x] **Feature** - 新增功能或模块
- [ ] Fix - Bug 修复

---

## 📝 变更摘要

**重构核心业务模块，采用双表分离设计；移除 ML 模型依赖，改用规则引擎；简化目录结构，提升可维护性。**

---

## ⚖️ 核心变更对比表

| 变更模块 | 变更前 (Before) | 变更后 (After) | 变更原因/优势 |
|----------|----------------|----------------|---------------|
| **数据库架构** | 单一 `videos` 表存储所有字段（原始字段 + 衍生字段混合） | 拆分为 `videos` + `video_enrichments` 两表 | ✅ 职责分离：爬虫原始数据 vs 离线计算结果<br/>✅ 支持衍生字段独立迭代<br/>✅ 降低表宽度，提升查询效率 |
| **分类系统** | 爬虫内嵌 TF-IDF + ComplementNB 模型分类 | 独立 `TopicClassifier` 基于关键词规则分类 | ✅ 消除 scikit-learn 依赖<br/>✅ 规则可读可调，便于业务迭代<br/>✅ 离线批处理，不阻塞爬虫 |
| **评分系统** | 依赖外部训练的 pkl 模型文件 | 纯规则 `QualityScorer` 多维加权评分 | ✅ 零模型依赖，开箱即用<br/>✅ 评分公式透明：互动分×0.4 + 时长分×0.2 + 新鲜度×0.2 + UP主分×0.2 |
| **代码结构** | 多目录分散：`classifier/`, `analyzer/`, `recommender/`, `scripts/` | 统一至 `core/` 目录 | ✅ 减少目录嵌套<br/>✅ 导入路径简化 |
| **路由架构** | 单一 `app.py` 包含所有逻辑 | 拆分为 `app.py` + `app_routes.py` + `app_services.py` | ✅ 薄路由层 + 厚服务层<br/>✅ 单一职责，便于测试 |
| **推荐页** | `/recommend` 与 `/resources` 功能重叠 | 功能分离：资源检索 vs 智能推荐 | ✅ URL 语义与页面内容一致 |
| **分类标签** | "科普" 分类 | 改为 "直观" 分类 | ✅ 更准确描述可视化/本质讲解类内容 |

---

## 🗄️ 数据库具体改动清单

### 🆕 新增表

| 表名 | 说明 |
|------|------|
| `video_enrichments` | 视频衍生字段表，存储离线计算结果 |

**表结构：**

```sql
CREATE TABLE IF NOT EXISTS `video_enrichments` (
  `视频ID` varchar(20) NOT NULL COMMENT 'B站视频ID',
  `科目` varchar(20) DEFAULT NULL COMMENT '所属科目: 高等数学/线性代数/概率论与数理统计',
  `知识点` varchar(100) DEFAULT NULL COMMENT '知识点主题（逗号分隔）',
  `难度` varchar(20) DEFAULT NULL COMMENT '难度等级: 入门/进阶/高阶',
  `质量分` float DEFAULT 0 COMMENT '综合评分 0-100',
  `是否推荐` tinyint(1) DEFAULT 0 COMMENT '是否推荐',
  `更新时间` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`视频ID`),
  CONSTRAINT `fk_video_enrichments_videos` FOREIGN KEY (`视频ID`) REFERENCES `videos`(`视频ID`) ON DELETE CASCADE,
  KEY `idx_video_enrich_subject` (`科目`),
  KEY `idx_video_enrich_topic` (`知识点`),
  KEY `idx_video_enrich_difficulty` (`难度`),
  KEY `idx_video_enrich_quality_score` (`质量分`),
  KEY `idx_video_enrich_is_recommended` (`是否推荐`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### ✏️ 修改字段

| 表 | 原字段 | 变更 |
|----|--------|------|
| `videos` | `category`, `phase`, `subject`, `dry_goods_ratio` | 🗑️ 移除（移至 `video_enrichments`） |
| `videos` | 所有中文字段名 | ✅ 统一使用中文列名（`视频ID`, `标题`, `播放量` 等） |

### 🗑️ 废弃

| 文件/目录 | 说明 |
|-----------|------|
| `classifier/` 目录 | 已合并至 `core/topic_classifier.py` |
| `analyzer/` 目录 | 已合并至 `core/quality_scorer.py` |
| `recommender/` 目录 | 已合并至 `core/recommend_engine.py` |
| `scripts/` 目录 | 已合并至 `core/process_videos.py` |
| `train_model.py` | ML 模型训练脚本已移除 |
| `subject_classifier.pkl` | ML 模型文件已移除 |

---

## 🔄 关键代码变更

### 1. ORM 模型重构 (`models.py`)

```diff
- # 旧版：单表存储所有字段
- class Video(db.Model):
-     category = db.Column(db.String(50))
-     phase = db.Column(db.String(50))
-     subject = db.Column(db.String(50))
-     dry_goods_ratio = db.Column(db.Float)

+ # 新版：双表分离
+ class Video(db.Model):
+     """视频表：存储 B 站视频元数据（爬虫原始字段）"""
+     视频ID = db.Column(db.String(20), primary_key=True)
+     # ... 原始字段
+     enrichment = db.relationship("VideoEnrichment", back_populates="video", uselist=False)
+
+ class VideoEnrichment(db.Model):
+     """视频衍生字段表：知识点/难度/质量分/是否推荐 等离线计算结果"""
+     视频ID = db.Column(db.String(20), db.ForeignKey("videos.视频ID"), primary_key=True)
+     科目 = db.Column(db.String(20))
+     知识点 = db.Column(db.String(100))
+     难度 = db.Column(db.String(20))
+     质量分 = db.Column(db.Float, default=0)
+     是否推荐 = db.Column(db.Boolean, default=False)
```

### 2. 分类器重构 (`core/topic_classifier.py`)

```diff
- # 旧版：TF-IDF + ML 模型
- from sklearn.feature_extraction.text import TfidfVectorizer
- from sklearn.naive_bayes import ComplementNB
- model = joblib.load("subject_classifier.pkl")
- predicted = model.predict([text])

+ # 新版：纯关键词规则
+ TOPIC_KEYWORDS = {
+     "极限与连续": ["极限", "连续", "无穷小", "洛必达"],
+     "导数与微分": ["导数", "微分", "求导", "链式法则"],
+     # ...
+ }
+ class TopicClassifier:
+     def classify(self, title, tags="", desc=""):
+         normalized = self._normalize_text(f"{title} {tags} {desc}")
+         topics = self._classify_topics(normalized)
+         difficulty = self._classify_difficulty(normalized)
+         return topics, difficulty
```

### 3. 评分器重构 (`core/quality_scorer.py`)

```diff
+ class QualityScorer:
+     """视频质量评分器"""
+     def score(self, video: Dict) -> float:
+         engagement = self._score_engagement(video)  # 互动分 (收藏率/点赞率/投币率)
+         duration = self._score_duration(video)      # 时长分 (5-30分钟最优)
+         freshness = self._score_freshness(video)    # 新鲜度 (近期发布加分)
+         uploader = self._score_uploader(video)      # UP主分 (知名讲师加分)
+         
+         return (engagement * 0.4 + duration * 0.2 + 
+                 freshness * 0.2 + uploader * 0.2)
```

---

## 🧪 测试与迁移建议

### 数据库迁移

**方式一：使用完整 SQL 初始化（推荐新环境）**

```bash
mysql -u root -p bilibili_math_db < docs/migrations/bilibili_math_db.sql
```

**方式二：增量迁移（已有数据）**

```sql
-- 1. 创建衍生表
CREATE TABLE video_enrichments (...);

-- 2. 运行离线处理脚本填充数据
python -m core.process_videos
```

### 功能验证清单

| 功能 | 验证方法 |
|------|----------|
| 数据采集 | `python spider/bilibili_api.py` 后检查 `videos` 表数据 |
| 离线处理 | `python -m core.process_videos` 后检查 `video_enrichments` 表 |
| 仪表盘 | 访问 `/dashboard`，验证统计数据和图表渲染 |
| 资源检索 | 访问 `/resources`，测试筛选/排序/分页 |
| 智能推荐 | 访问 `/recommend`，测试多策略推荐 |
| 用户功能 | 注册/登录/收藏/历史/个人资料编辑 |

### 回归测试

- [ ] 仪表盘统计数据正确
- [ ] 资源检索分页正常
- [ ] 推荐页策略切换正常
- [ ] 收藏/取消收藏功能正常
- [ ] 头像上传功能正常

---

## 📸 前端功能演示截图

### 仪表盘

![仪表盘](screenshots/仪表盘.png)

### 资源检索

![资源检索](screenshots/资源检索.png)

### 智能推荐

![智能推荐](screenshots/智能推荐.png)

### 个人中心

![个人中心](screenshots/个人中心.png)

---

## 📌 相关链接

- README: [README.md](../README.md)
- 数据库迁移: [docs/migrations/bilibili_math_db.sql](migrations/bilibili_math_db.sql)

---

## ✅ Checklist

- [x] 代码遵循项目规范
- [x] README 已更新
- [x] 数据库迁移脚本已提供
- [x] 功能验证通过
- [x] 截图已更新

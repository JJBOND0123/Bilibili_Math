# 仓库协作约定（Repository Guidelines）

## 项目结构与模块说明
- `app.py`：Flask 入口（路由、API、认证、推荐、数据可视化接口）。
- `models.py`：SQLAlchemy 模型与数据库访问。
- `config.py`：Flask/MySQL 配置（本地修改；不要提交真实 Cookie/凭据）。
- `spider/`：B 站爬虫模块（`spider/bilibili_api.py` 采集并写入 MySQL；`spider/utils.py` 为纯工具函数）。
- `templates/`：Jinja2 服务端渲染模板。
- `static/`：前端静态资源（CSS/JS/图片）；用户头像在 `static/avatars/`。
- `docs/`：项目文档与截图。
  - `docs/初始化与运行指南.md`：从零初始化、导入数据库、运行/训练/测试的操作步骤。
  - `docs/migrations/`：数据库 SQL 文件（例如整库转存 `docs/migrations/bilibili_math_db.sql`，用于新库初始化）。
- `train_model.py`：训练/导出 `subject_classifier.pkl`（可选）。
- `force_fix.py`：重新下载离线 ECharts/WordCloud 到 `static/js/`（需要网络）。

## 开发、测试、运行命令（Windows）
- 创建并激活虚拟环境：`python -m venv .venv`，然后 `.\.venv\Scripts\activate`
- 安装依赖：`pip install -r requirements.txt`
- 启动 Web：`flask --app app run --debug`（依赖 `config.py` 中可连接的 MySQL）
- 采集/导入数据：`python spider/bilibili_api.py`
- 训练分类模型（可选）：`python train_model.py`
- 刷新离线 JS（可选）：`python force_fix.py`

## 代码风格与命名
- Python：4 空格缩进；函数/变量 `snake_case`，类 `PascalCase`；文件保持 UTF-8。
- 尽量保持函数小而清晰；避免把业务逻辑塞进模板。
- 前端：JS/CSS 放在 `static/`；除非必要不要改动压缩过的 vendor 文件。

## 测试约定
- 项目已包含 `pytest`，并已有 `tests/` 目录。
- 新增测试建议放在 `tests/test_*.py`，保持确定性（文本解析、指标计算、爬虫工具函数等）。
- 运行测试：`pytest`

## 提交与 PR 约定
- Commit message 建议使用 Conventional Commits 前缀：`feat:`、`fix:`、`ui:`、`docs:`、`chore:`。
- 中文或英文均可，但一个 PR 内尽量统一。
- PR（或答辩前整理）建议包含：问题描述、方案、如何运行/验证、必要截图（更新 `docs/screenshots/`），以及数据库/表结构说明。

## 安全与本地配置
- 不要提交真实数据库凭据、B 站 Cookie、会话 token：尤其是 `config.py` 的 `BILI_COOKIE` 应保持为空值提交。
- 避免提交生成物：`__pycache__/`、`.venv/`、上传的 `static/avatars/`、大体积二进制文件（除非确有必要）。

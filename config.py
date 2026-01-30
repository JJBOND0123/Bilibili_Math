from __future__ import annotations

import os
import secrets

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


class Config:
    """Flask configuration with static defaults."""

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "mysql+pymysql://root:123456@localhost/bilibili_math_db?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    
    # 固定 SECRET_KEY（开发环境用，生产环境应设置环境变量）
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-bilibili-math-2024")
    
    # Session 持久化配置：7 天有效期
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 天（秒）


# 本地开发爬虫用：请在本机通过环境变量或 .env 填写，不要提交真实 Cookie（示例：'SESSDATA=...; bili_jct=...;'）
BILI_COOKIE = os.getenv("BILI_COOKIE", "")
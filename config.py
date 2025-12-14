import secrets


class Config:
    """Flask configuration with static defaults."""

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:123456@localhost/bilibili_math_db?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    SECRET_KEY = secrets.token_hex(32)

# 本地开发/爬虫用：请在本机填写，不要提交真实 Cookie（示例：'SESSDATA=...; bili_jct=...;'）
BILI_COOKIE = ""

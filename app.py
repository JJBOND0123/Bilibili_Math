"""Flask 入口：应用初始化、扩展注册与蓝图挂载。"""

from __future__ import annotations

import logging
import os
import sys

from flask import Flask
from flask_login import LoginManager

from app_services import UPLOAD_FOLDER
from config import Config
from models import User, db
from app_routes import api_bp, auth_bp, pages_bp


def configure_logging(flask_app: Flask) -> None:
    """配置统一日志输出到控制台，避免落盘文件。"""
    log_level = logging.DEBUG if flask_app.config.get("DEBUG") else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    flask_logger = flask_app.logger
    flask_logger.handlers.clear()
    flask_logger.setLevel(log_level)
    flask_logger.addHandler(handler)
    flask_logger.propagate = False

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.handlers.clear()
    werkzeug_logger.setLevel(log_level)
    werkzeug_logger.addHandler(handler)
    werkzeug_logger.propagate = False


app = Flask(__name__)
app.config.from_object(Config)
configure_logging(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db.init_app(app)

# Ensure core tables exist when running via `flask run` (tolerate missing DB in dev).
try:
    with app.app_context():
        db.create_all()
except Exception as exc:
    app.logger.warning("Skipping db.create_all during startup: %s", exc)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "请先登录，开启你的学习之旅"


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login 回调：根据 user_id 取出用户对象。"""
    return db.session.get(User, int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(pages_bp)
app.register_blueprint(api_bp)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)

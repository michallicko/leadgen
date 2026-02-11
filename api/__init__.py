from flask import Flask
from flask_cors import CORS

from .config import Config
from .models import db
from .routes import register_blueprints


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, origins=app.config["CORS_ORIGINS"])
    db.init_app(app)
    register_blueprints(app)

    return app

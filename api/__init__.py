import traceback

from flask import Flask, jsonify
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

    @app.errorhandler(500)
    def handle_500(e):
        app.logger.error("Unhandled 500:\n%s", traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Method not allowed"}), 405

    return app

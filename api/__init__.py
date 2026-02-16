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

    # Clean up orphaned pipeline/stage runs left by container restarts
    with app.app_context():
        try:
            from sqlalchemy import text

            db.session.execute(text("""
                UPDATE stage_runs SET status = 'failed',
                    error = 'Orphaned by container restart',
                    completed_at = CURRENT_TIMESTAMP
                WHERE status IN ('running', 'pending', 'stopping')
            """))
            db.session.execute(text("""
                UPDATE pipeline_runs SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP
                WHERE status IN ('running', 'stopping')
            """))
            db.session.commit()
            app.logger.info("Cleaned up orphaned pipeline/stage runs")
        except Exception:
            db.session.rollback()
            app.logger.warning("Could not clean orphaned runs (likely first boot)")

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

from .auth_routes import auth_bp
from .batch_routes import batch_bp
from .health import health_bp
from .message_routes import messages_bp
from .tenant_routes import tenants_bp
from .user_routes import users_bp


def register_blueprints(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(messages_bp)

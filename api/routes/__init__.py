from .auth_routes import auth_bp
from .bulk_routes import bulk_bp
from .tag_routes import tag_bp
from .campaign_routes import campaigns_bp
from .company_routes import companies_bp
from .contact_routes import contacts_bp
from .custom_field_routes import custom_fields_bp
from .enrich_routes import enrich_bp
from .enrichment_config_routes import enrichment_config_bp
from .extension_routes import extension_bp
from .gmail_routes import gmail_bp
from .health import health_bp
from .import_routes import imports_bp
from .llm_usage_routes import llm_usage_bp
from .message_routes import messages_bp
from .oauth_routes import oauth_bp
from .pipeline_routes import pipeline_bp
from .tenant_routes import tenants_bp
from .user_routes import users_bp


def register_blueprints(app):
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bulk_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(tag_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(pipeline_bp)
    app.register_blueprint(enrich_bp)
    app.register_blueprint(enrichment_config_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(custom_fields_bp)
    app.register_blueprint(llm_usage_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(gmail_bp)
    app.register_blueprint(extension_bp)

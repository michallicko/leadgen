from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB, UUID

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    email = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    display_name = db.Column(db.Text, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    owner_id = db.Column(UUID(as_uuid=False), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    roles = db.relationship("UserTenantRole", back_populates="user", cascade="all, delete-orphan",
                            foreign_keys="[UserTenantRole.user_id]")

    def to_dict(self, include_roles=False):
        d = {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "is_super_admin": self.is_super_admin,
            "is_active": self.is_active,
            "owner_id": str(self.owner_id) if self.owner_id else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_roles:
            d["roles"] = {r.tenant.slug: r.role for r in self.roles if r.tenant}
        return d


class UserTenantRole(db.Model):
    __tablename__ = "user_tenant_roles"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.Text, nullable=False, default="viewer")
    granted_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    granted_by = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"), nullable=True)

    user = db.relationship("User", back_populates="roles", foreign_keys=[user_id])
    tenant = db.relationship("Tenant", foreign_keys=[tenant_id])


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    name = db.Column(db.Text, nullable=False)
    slug = db.Column(db.Text, unique=True, nullable=False)
    domain = db.Column(db.Text)
    settings = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "domain": self.domain,
            "settings": self.settings or {},
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Owner(db.Model):
    __tablename__ = "owners"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Batch(db.Model):
    __tablename__ = "batches"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    domain = db.Column(db.Text)
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    status = db.Column(db.Text)
    tier = db.Column(db.Text)


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    company_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
    full_name = db.Column(db.Text, nullable=False)
    job_title = db.Column(db.Text)
    linkedin_url = db.Column(db.Text)
    contact_score = db.Column(db.SmallInteger)
    icp_fit = db.Column(db.Text)
    message_status = db.Column(db.Text)
    processed_enrich = db.Column(db.Boolean, default=False)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    contact_id = db.Column(UUID(as_uuid=False), db.ForeignKey("contacts.id"), nullable=False)
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    label = db.Column(db.Text)
    channel = db.Column(db.Text, nullable=False)
    sequence_step = db.Column(db.SmallInteger, default=1)
    variant = db.Column(db.Text, default="a")
    subject = db.Column(db.Text)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, default="draft")
    tone = db.Column(db.Text)
    language = db.Column(db.Text, default="en")
    generation_cost_usd = db.Column(db.Numeric(10, 4))
    approved_at = db.Column(db.DateTime(timezone=True))
    sent_at = db.Column(db.DateTime(timezone=True))
    review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

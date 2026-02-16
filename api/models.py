from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

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
    business_model = db.Column(db.Text)
    company_size = db.Column(db.Text)
    ownership_type = db.Column(db.Text)
    geo_region = db.Column(db.Text)
    industry = db.Column(db.Text)
    industry_category = db.Column(db.Text)
    revenue_range = db.Column(db.Text)
    buying_stage = db.Column(db.Text)
    engagement_status = db.Column(db.Text)
    crm_status = db.Column(db.Text)
    ai_adoption = db.Column(db.Text)
    news_confidence = db.Column(db.Text)
    business_type = db.Column(db.Text)
    cohort = db.Column(db.Text)
    summary = db.Column(db.Text)
    hq_city = db.Column(db.Text)
    hq_country = db.Column(db.Text)
    triage_notes = db.Column(db.Text)
    triage_score = db.Column(db.Numeric(4, 1))
    verified_revenue_eur_m = db.Column(db.Numeric(10, 1))
    verified_employees = db.Column(db.Numeric(10, 1))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    pre_score = db.Column(db.Numeric(4, 1))
    batch_number = db.Column(db.Numeric(4, 1))
    lemlist_synced = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text)
    notes = db.Column(db.Text)
    custom_fields = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    ico = db.Column(db.Text)
    import_job_id = db.Column(UUID(as_uuid=False), db.ForeignKey("import_jobs.id"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyEnrichmentL2(db.Model):
    __tablename__ = "company_enrichment_l2"

    company_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True)
    company_intel = db.Column(db.Text)
    recent_news = db.Column(db.Text)
    ai_opportunities = db.Column(db.Text)
    pain_hypothesis = db.Column(db.Text)
    relevant_case_study = db.Column(db.Text)
    digital_initiatives = db.Column(db.Text)
    leadership_changes = db.Column(db.Text)
    hiring_signals = db.Column(db.Text)
    key_products = db.Column(db.Text)
    customer_segments = db.Column(db.Text)
    competitors = db.Column(db.Text)
    tech_stack = db.Column(db.Text)
    funding_history = db.Column(db.Text)
    eu_grants = db.Column(db.Text)
    leadership_team = db.Column(db.Text)
    ai_hiring = db.Column(db.Text)
    tech_partnerships = db.Column(db.Text)
    certifications = db.Column(db.Text)
    quick_wins = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    industry_pain_points = db.Column(db.Text)
    cross_functional_pain = db.Column(db.Text)
    adoption_barriers = db.Column(db.Text)
    competitor_ai_moves = db.Column(db.Text)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyRegistryData(db.Model):
    __tablename__ = "company_registry_data"

    company_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True)
    ico = db.Column(db.Text)
    dic = db.Column(db.Text)
    official_name = db.Column(db.Text)
    legal_form = db.Column(db.Text)
    legal_form_name = db.Column(db.Text)
    date_established = db.Column(db.Date)
    date_dissolved = db.Column(db.Date)
    registered_address = db.Column(db.Text)
    address_city = db.Column(db.Text)
    address_postal_code = db.Column(db.Text)
    nace_codes = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    registration_court = db.Column(db.Text)
    registration_number = db.Column(db.Text)
    registered_capital = db.Column(db.Text)
    directors = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    registration_status = db.Column(db.Text)
    insolvency_flag = db.Column(db.Boolean, default=False)
    raw_response = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    raw_vr_response = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    match_confidence = db.Column(db.Numeric(3, 2))
    match_method = db.Column(db.Text)
    ares_updated_at = db.Column(db.Date)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyTag(db.Model):
    __tablename__ = "company_tags"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    company_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"), nullable=False)
    category = db.Column(db.Text, nullable=False)
    value = db.Column(db.Text, nullable=False)


class ContactEnrichment(db.Model):
    __tablename__ = "contact_enrichment"

    contact_id = db.Column(UUID(as_uuid=False), db.ForeignKey("contacts.id"), primary_key=True)
    person_summary = db.Column(db.Text)
    linkedin_profile_summary = db.Column(db.Text)
    relationship_synthesis = db.Column(db.Text)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    company_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
    first_name = db.Column(db.Text, nullable=False)
    last_name = db.Column(db.Text, nullable=False, default="")
    job_title = db.Column(db.Text)

    @property
    def full_name(self):
        if self.last_name:
            return self.first_name + " " + self.last_name
        return self.first_name
    email_address = db.Column(db.Text)
    linkedin_url = db.Column(db.Text)
    phone_number = db.Column(db.Text)
    profile_photo_url = db.Column(db.Text)
    seniority_level = db.Column(db.Text)
    department = db.Column(db.Text)
    location_city = db.Column(db.Text)
    location_country = db.Column(db.Text)
    icp_fit = db.Column(db.Text)
    relationship_status = db.Column(db.Text)
    contact_source = db.Column(db.Text)
    language = db.Column(db.Text)
    message_status = db.Column(db.Text)
    ai_champion = db.Column(db.Boolean, default=False)
    ai_champion_score = db.Column(db.SmallInteger)
    authority_score = db.Column(db.SmallInteger)
    contact_score = db.Column(db.SmallInteger)
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    processed_enrich = db.Column(db.Boolean, default=False)
    email_lookup = db.Column(db.Boolean, default=False)
    duplicity_check = db.Column(db.Boolean, default=False)
    duplicity_conflict = db.Column(db.Boolean, default=False)
    duplicity_detail = db.Column(db.Text)
    notes = db.Column(db.Text)
    error = db.Column(db.Text)
    custom_fields = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    import_job_id = db.Column(UUID(as_uuid=False), db.ForeignKey("import_jobs.id"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class ImportJob(db.Model):
    __tablename__ = "import_jobs"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"), nullable=False)
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    filename = db.Column(db.Text, nullable=False)
    file_size_bytes = db.Column(db.Integer)
    total_rows = db.Column(db.Integer, nullable=False, default=0)
    headers = db.Column(JSONB, nullable=False, server_default=db.text("'[]'::jsonb"))
    sample_rows = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    raw_csv = db.Column(db.Text)
    column_mapping = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    mapping_confidence = db.Column(db.Numeric(3, 2))
    contacts_created = db.Column(db.Integer, default=0)
    contacts_updated = db.Column(db.Integer, default=0)
    contacts_skipped = db.Column(db.Integer, default=0)
    companies_created = db.Column(db.Integer, default=0)
    companies_linked = db.Column(db.Integer, default=0)
    enrichment_depth = db.Column(db.Text)
    estimated_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    actual_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    source = db.Column(db.Text, default="csv")
    oauth_connection_id = db.Column(UUID(as_uuid=False), db.ForeignKey("oauth_connections.id"))
    scan_config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    scan_progress = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    dedup_strategy = db.Column(db.Text, default="skip")
    dedup_results = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    status = db.Column(db.Text, default="uploaded")
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    @staticmethod
    def _parse_jsonb(v):
        if v is None:
            return v
        if isinstance(v, str):
            import json
            return json.loads(v) if v else None
        return v

    def to_dict(self, include_data=False):
        d = {
            "id": str(self.id),
            "filename": self.filename,
            "total_rows": self.total_rows,
            "column_mapping": self._parse_jsonb(self.column_mapping),
            "mapping_confidence": float(self.mapping_confidence) if self.mapping_confidence else None,
            "contacts_created": self.contacts_created,
            "contacts_updated": self.contacts_updated,
            "contacts_skipped": self.contacts_skipped,
            "companies_created": self.companies_created,
            "companies_linked": self.companies_linked,
            "dedup_strategy": self.dedup_strategy,
            "dedup_results": self._parse_jsonb(self.dedup_results),
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_data:
            d["headers"] = self._parse_jsonb(self.headers)
            d["sample_rows"] = self._parse_jsonb(self.sample_rows)
        return d


class StageRun(db.Model):
    __tablename__ = "stage_runs"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    stage = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default="pending")
    total = db.Column(db.Integer, default=0)
    done = db.Column(db.Integer, default=0)
    failed = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Numeric(10, 4), default=0)
    config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    error = db.Column(db.Text)
    started_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    completed_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class PipelineRun(db.Model):
    __tablename__ = "pipeline_runs"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    execution_id = db.Column(db.Text)
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    total_companies = db.Column(db.Integer, default=0)
    total_contacts = db.Column(db.Integer, default=0)
    l1_total = db.Column(db.Integer, default=0)
    l1_done = db.Column(db.Integer, default=0)
    l2_total = db.Column(db.Integer, default=0)
    l2_done = db.Column(db.Integer, default=0)
    person_total = db.Column(db.Integer, default=0)
    person_done = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Numeric(10, 4), default=0)
    status = db.Column(db.Text, default="running")
    config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    stages = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    started_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    completed_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CustomFieldDefinition(db.Model):
    __tablename__ = "custom_field_definitions"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    entity_type = db.Column(db.Text, nullable=False)
    field_key = db.Column(db.Text, nullable=False)
    field_label = db.Column(db.Text, nullable=False)
    field_type = db.Column(db.Text, nullable=False, default="text")
    options = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "entity_type", "field_key", name="uq_cfd_tenant_entity_key"),
    )

    def to_dict(self):
        opts = self.options or []
        if isinstance(opts, str):
            import json
            opts = json.loads(opts)
        return {
            "id": str(self.id),
            "entity_type": self.entity_type,
            "field_key": self.field_key,
            "field_label": self.field_label,
            "field_type": self.field_type,
            "options": opts,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LlmUsageLog(db.Model):
    __tablename__ = "llm_usage_log"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"))
    operation = db.Column(db.Text, nullable=False)
    provider = db.Column(db.Text, nullable=False, server_default=db.text("'anthropic'"))
    model = db.Column(db.Text, nullable=False)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    cost_usd = db.Column(db.Numeric(10, 6), nullable=False, default=0)
    duration_ms = db.Column(db.Integer)
    extra = db.Column("metadata", JSONB, server_default=db.text("'{}'::jsonb"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    def to_dict(self):
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "operation": self.operation,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": float(self.cost_usd) if self.cost_usd else 0,
            "duration_ms": self.duration_ms,
            "metadata": self.extra or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OAuthConnection(db.Model):
    __tablename__ = "oauth_connections"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider = db.Column(db.Text, nullable=False)
    provider_account_id = db.Column(db.Text)
    provider_email = db.Column(db.Text)
    access_token_enc = db.Column(db.Text)
    refresh_token_enc = db.Column(db.Text)
    token_expiry = db.Column(db.DateTime(timezone=True))
    scopes = db.Column(ARRAY(db.Text))
    status = db.Column(db.Text, nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "tenant_id", "provider", "provider_account_id",
                            name="uq_oauth_user_provider_account"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "provider": self.provider,
            "provider_email": self.provider_email,
            "status": self.status,
            "scopes": self.scopes if isinstance(self.scopes, list) else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(UUID(as_uuid=False), primary_key=True, server_default=db.text("uuid_generate_v4()"))
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False)
    contact_id = db.Column(UUID(as_uuid=False), db.ForeignKey("contacts.id"), nullable=False)
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("batches.id"))
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

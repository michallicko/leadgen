from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    email = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    display_name = db.Column(db.Text, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    owner_id = db.Column(UUID(as_uuid=False), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    roles = db.relationship(
        "UserTenantRole",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[UserTenantRole.user_id]",
    )

    def to_dict(self, include_roles=False):
        d = {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "is_super_admin": self.is_super_admin,
            "is_active": self.is_active,
            "owner_id": str(self.owner_id) if self.owner_id else None,
            "last_login_at": self.last_login_at.isoformat()
            if self.last_login_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_roles:
            d["roles"] = {r.tenant.slug: r.role for r in self.roles if r.tenant}
        return d


class UserTenantRole(db.Model):
    __tablename__ = "user_tenant_roles"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    user_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = db.Column(db.Text, nullable=False, default="viewer")
    granted_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    granted_by = db.Column(
        UUID(as_uuid=False), db.ForeignKey("users.id"), nullable=True
    )

    user = db.relationship("User", back_populates="roles", foreign_keys=[user_id])
    tenant = db.relationship("Tenant", foreign_keys=[tenant_id])


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
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

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    name = db.Column(db.Text, nullable=False)
    domain = db.Column(db.Text)
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
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
    is_self = db.Column(
        db.Boolean, nullable=False, server_default=db.text("false"), default=False
    )
    lemlist_synced = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text)
    notes = db.Column(db.Text)
    custom_fields = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    ico = db.Column(db.Text)
    official_name = db.Column(db.Text)
    tax_id = db.Column(db.Text)
    legal_form = db.Column(db.Text)
    registration_status = db.Column(db.Text)
    date_established = db.Column(db.Date)
    has_insolvency = db.Column(db.Boolean, default=False)
    credibility_score = db.Column(db.SmallInteger)
    credibility_factors = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    website_url = db.Column(db.Text)
    linkedin_url = db.Column(db.Text)
    logo_url = db.Column(db.Text)
    last_enriched_at = db.Column(db.DateTime(timezone=True))
    data_quality_score = db.Column(db.SmallInteger)
    import_job_id = db.Column(UUID(as_uuid=False), db.ForeignKey("import_jobs.id"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyEnrichmentL2(db.Model):
    __tablename__ = "company_enrichment_l2"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
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


class CompanyEnrichmentL1(db.Model):
    __tablename__ = "company_enrichment_l1"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
    triage_notes = db.Column(db.Text)
    pre_score = db.Column(db.Numeric(4, 1))
    research_query = db.Column(db.Text)
    raw_response = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    confidence = db.Column(db.Numeric(3, 2))
    quality_score = db.Column(db.SmallInteger)
    qc_flags = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyEnrichmentProfile(db.Model):
    __tablename__ = "company_enrichment_profile"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
    company_intel = db.Column(db.Text)
    key_products = db.Column(db.Text)
    customer_segments = db.Column(db.Text)
    competitors = db.Column(db.Text)
    tech_stack = db.Column(db.Text)
    leadership_team = db.Column(db.Text)
    certifications = db.Column(db.Text)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyEnrichmentSignals(db.Model):
    __tablename__ = "company_enrichment_signals"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
    digital_initiatives = db.Column(db.Text)
    leadership_changes = db.Column(db.Text)
    hiring_signals = db.Column(db.Text)
    ai_hiring = db.Column(db.Text)
    tech_partnerships = db.Column(db.Text)
    competitor_ai_moves = db.Column(db.Text)
    ai_adoption_level = db.Column(db.Text)
    news_confidence = db.Column(db.Text)
    growth_indicators = db.Column(db.Text)
    job_posting_count = db.Column(db.Integer)
    hiring_departments = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyEnrichmentMarket(db.Model):
    __tablename__ = "company_enrichment_market"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
    recent_news = db.Column(db.Text)
    funding_history = db.Column(db.Text)
    eu_grants = db.Column(db.Text)
    media_sentiment = db.Column(db.Text)
    press_releases = db.Column(db.Text)
    thought_leadership = db.Column(db.Text)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyEnrichmentOpportunity(db.Model):
    __tablename__ = "company_enrichment_opportunity"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
    pain_hypothesis = db.Column(db.Text)
    relevant_case_study = db.Column(db.Text)
    ai_opportunities = db.Column(db.Text)
    quick_wins = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    industry_pain_points = db.Column(db.Text)
    cross_functional_pain = db.Column(db.Text)
    adoption_barriers = db.Column(db.Text)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyRegistryData(db.Model):
    __tablename__ = "company_registry_data"

    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), primary_key=True
    )
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
    registry_country = db.Column(db.Text, default="CZ")
    ares_updated_at = db.Column(db.Date)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyInsolvencyData(db.Model):
    __tablename__ = "company_insolvency_data"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), nullable=False
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    ico = db.Column(db.Text)
    has_insolvency = db.Column(db.Boolean, default=False)
    proceedings = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    total_proceedings = db.Column(db.Integer, default=0)
    active_proceedings = db.Column(db.Integer, default=0)
    last_checked_at = db.Column(db.DateTime(timezone=True))
    raw_response = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class CompanyLegalProfile(db.Model):
    __tablename__ = "company_legal_profile"

    company_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    registration_id = db.Column(db.Text)
    registration_country = db.Column(db.Text, nullable=False)
    tax_id = db.Column(db.Text)
    official_name = db.Column(db.Text)
    legal_form = db.Column(db.Text)
    legal_form_name = db.Column(db.Text)
    registration_status = db.Column(db.Text)
    date_established = db.Column(db.Date)
    date_dissolved = db.Column(db.Date)
    registered_address = db.Column(db.Text)
    address_city = db.Column(db.Text)
    address_postal_code = db.Column(db.Text)
    nace_codes = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    directors = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    registered_capital = db.Column(db.Text)
    registration_court = db.Column(db.Text)
    registration_number = db.Column(db.Text)
    insolvency_flag = db.Column(db.Boolean, default=False)
    insolvency_details = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    active_insolvency_count = db.Column(db.Integer, default=0)
    match_confidence = db.Column(db.Numeric(3, 2))
    match_method = db.Column(db.Text)
    credibility_score = db.Column(db.SmallInteger)
    credibility_factors = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    source_data = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    enriched_at = db.Column(db.DateTime(timezone=True))
    registry_updated_at = db.Column(db.Date)
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class ContactTagAssignment(db.Model):
    __tablename__ = "contact_tag_assignments"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    contact_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    __table_args__ = (db.UniqueConstraint("contact_id", "tag_id"),)


class CompanyTagAssignment(db.Model):
    __tablename__ = "company_tag_assignments"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    company_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    __table_args__ = (db.UniqueConstraint("company_id", "tag_id"),)


class CompanyTag(db.Model):
    __tablename__ = "company_tags"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    company_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("companies.id"), nullable=False
    )
    category = db.Column(db.Text, nullable=False)
    value = db.Column(db.Text, nullable=False)


class ContactEnrichment(db.Model):
    __tablename__ = "contact_enrichment"

    contact_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("contacts.id"), primary_key=True
    )
    person_summary = db.Column(db.Text)
    linkedin_profile_summary = db.Column(db.Text)
    relationship_synthesis = db.Column(db.Text)
    ai_champion = db.Column(db.Boolean, default=False)
    ai_champion_score = db.Column(db.SmallInteger)
    authority_score = db.Column(db.SmallInteger)
    career_trajectory = db.Column(db.Text)
    previous_companies = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    speaking_engagements = db.Column(db.Text)
    publications = db.Column(db.Text)
    twitter_handle = db.Column(db.Text)
    github_username = db.Column(db.Text)
    enriched_at = db.Column(db.DateTime(timezone=True))
    enrichment_cost_usd = db.Column(db.Numeric(10, 4), default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    company_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"))
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
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
    last_enriched_at = db.Column(db.DateTime(timezone=True))
    employment_verified_at = db.Column(db.DateTime(timezone=True))
    employment_status = db.Column(db.Text)
    linkedin_activity_level = db.Column(db.Text, default="unknown")
    import_job_id = db.Column(UUID(as_uuid=False), db.ForeignKey("import_jobs.id"))
    # Disqualification (migration 027)
    is_disqualified = db.Column(db.Boolean, default=False)
    disqualified_at = db.Column(db.DateTime(timezone=True))
    disqualified_reason = db.Column(db.Text)
    # Extension import (migration 028)
    is_stub = db.Column(db.Boolean, default=False)
    import_source = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class ImportJob(db.Model):
    __tablename__ = "import_jobs"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"), nullable=False)
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
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
    oauth_connection_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("oauth_connections.id")
    )
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
            "mapping_confidence": float(self.mapping_confidence)
            if self.mapping_confidence
            else None,
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

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
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

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    execution_id = db.Column(db.Text)
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
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

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    entity_type = db.Column(db.Text, nullable=False)
    field_key = db.Column(db.Text, nullable=False)
    field_label = db.Column(db.Text, nullable=False)
    field_type = db.Column(db.Text, nullable=False, default="text")
    options = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    __table_args__ = (
        db.UniqueConstraint(
            "tenant_id", "entity_type", "field_key", name="uq_cfd_tenant_entity_key"
        ),
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

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
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

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    user_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
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
        db.UniqueConstraint(
            "user_id",
            "tenant_id",
            "provider",
            "provider_account_id",
            name="uq_oauth_user_provider_account",
        ),
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


class ResearchAsset(db.Model):
    __tablename__ = "research_assets"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    entity_type = db.Column(db.Text, nullable=False)
    entity_id = db.Column(UUID(as_uuid=False), nullable=False)
    name = db.Column(db.Text, nullable=False)
    tool_name = db.Column(db.Text, nullable=False)
    cost_usd = db.Column(db.Numeric(10, 6), default=0)
    research_data = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    confidence_score = db.Column(db.Numeric(5, 2))
    quality_score = db.Column(db.Numeric(5, 2))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    contact_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("contacts.id"), nullable=False
    )
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
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
    campaign_contact_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("campaign_contacts.id")
    )
    # Version tracking + regeneration (migration 027)
    original_body = db.Column(db.Text)
    original_subject = db.Column(db.Text)
    edit_reason = db.Column(db.Text)
    edit_reason_text = db.Column(db.Text)
    regen_count = db.Column(db.Integer, default=0)
    regen_config = db.Column(JSONB)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


EDIT_REASONS = [
    "too_formal",
    "too_casual",
    "wrong_tone",
    "wrong_language",
    "too_long",
    "too_short",
    "factually_wrong",
    "off_topic",
    "generic",
    "other",
]


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"))
    name = db.Column(db.Text, nullable=False)
    lemlist_campaign_id = db.Column(db.Text)
    channel = db.Column(db.Text)
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
    is_active = db.Column(db.Boolean, default=True)
    # New campaign columns (migration 018)
    status = db.Column(db.Text, default="draft")
    description = db.Column(db.Text)
    template_config = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    generation_config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    total_contacts = db.Column(db.Integer, default=0)
    generated_count = db.Column(db.Integer, default=0)
    generation_cost = db.Column(db.Numeric(10, 4), default=0)
    generation_started_at = db.Column(db.DateTime(timezone=True))
    generation_completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    airtable_record_id = db.Column(db.Text)


class CampaignContact(db.Model):
    __tablename__ = "campaign_contacts"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    campaign_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id = db.Column(
        UUID(as_uuid=False),
        db.ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    status = db.Column(db.Text, default="pending")
    enrichment_gaps = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    generation_cost = db.Column(db.Numeric(10, 4), default=0)
    error = db.Column(db.Text)
    added_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    generated_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (db.UniqueConstraint("campaign_id", "contact_id"),)


class CampaignTemplate(db.Model):
    __tablename__ = "campaign_templates"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tenants.id"))
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    steps = db.Column(JSONB, server_default=db.text("'[]'::jsonb"))
    default_config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class EntityStageCompletion(db.Model):
    __tablename__ = "entity_stage_completions"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    tag_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"), nullable=False)
    pipeline_run_id = db.Column(UUID(as_uuid=False), db.ForeignKey("pipeline_runs.id"))
    entity_type = db.Column(db.Text, nullable=False)
    entity_id = db.Column(UUID(as_uuid=False), nullable=False)
    stage = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default="completed")
    cost_usd = db.Column(db.Numeric(10, 4), default=0)
    error = db.Column(db.Text)
    completed_at = db.Column(
        db.DateTime(timezone=True), server_default=db.text("now()")
    )


class EnrichmentConfig(db.Model):
    __tablename__ = "enrichment_configs"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, server_default=db.text("''"))
    config = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    is_default = db.Column(db.Boolean, default=False)
    created_by = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "name", name="uq_enrich_config_tenant_name"),
    )

    def to_dict(self):
        import json as _json

        cfg = self.config
        if isinstance(cfg, str):
            cfg = _json.loads(cfg)
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description or "",
            "config": cfg or {},
            "is_default": bool(self.is_default),
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EnrichmentSchedule(db.Model):
    __tablename__ = "enrichment_schedules"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    config_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("enrichment_configs.id"), nullable=False
    )
    schedule_type = db.Column(db.Text, nullable=False)  # "cron", "on_new_entity"
    cron_expression = db.Column(db.Text)  # e.g. "0 2 1 */3 *"
    tag_filter = db.Column(db.Text)  # optional: only run for specific tag
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime(timezone=True))
    next_run_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

    def to_dict(self):
        return {
            "id": str(self.id),
            "config_id": str(self.config_id),
            "schedule_type": self.schedule_type,
            "cron_expression": self.cron_expression,
            "tag_filter": self.tag_filter,
            "is_active": bool(self.is_active),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    contact_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("contacts.id"), nullable=True
    )
    owner_id = db.Column(UUID(as_uuid=False), db.ForeignKey("owners.id"), nullable=True)
    # Original columns (migration 001)
    activity_name = db.Column(db.Text)
    activity_detail = db.Column(db.Text)
    activity_type = db.Column(db.Text)  # legacy enum: 'message', 'event'
    source = db.Column(db.Text, nullable=False, default="linkedin_extension")
    external_id = db.Column(db.Text)
    occurred_at = db.Column(db.DateTime(timezone=True))
    processed = db.Column(db.Boolean, default=False)
    batch_id = db.Column(UUID(as_uuid=False), db.ForeignKey("tags.id"))
    cost_usd = db.Column(db.Numeric(10, 4))
    airtable_record_id = db.Column(db.Text)
    # Extension columns (migration 028)
    event_type = db.Column(db.Text, nullable=False, default="event")
    timestamp = db.Column(db.DateTime(timezone=True))
    payload = db.Column(JSONB, server_default=db.text("'{}'::jsonb"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))


class StrategyDocument(db.Model):
    __tablename__ = "strategy_documents"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False, unique=True
    )
    content = db.Column(db.Text, nullable=False, default="")
    extracted_data = db.Column(
        JSONB, server_default=db.text("'{}'::jsonb"), nullable=False, default=dict
    )
    status = db.Column(db.String(20), nullable=False, default="draft")
    version = db.Column(db.Integer, nullable=False, default=1)
    enrichment_id = db.Column(UUID(as_uuid=False), db.ForeignKey("companies.id"))
    objective = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    updated_by = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "content": self.content or "",
            "extracted_data": self.extracted_data or {},
            "status": self.status,
            "version": self.version,
            "enrichment_id": self.enrichment_id,
            "objective": self.objective,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }


class StrategyChatMessage(db.Model):
    __tablename__ = "strategy_chat_messages"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    document_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("strategy_documents.id"), nullable=False
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    extra = db.Column(
        "metadata",
        JSONB,
        server_default=db.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))
    created_by = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.extra or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


class PlaybookLog(db.Model):
    __tablename__ = "playbook_logs"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("tenants.id"), nullable=False
    )
    user_id = db.Column(UUID(as_uuid=False), db.ForeignKey("users.id"), nullable=False)
    doc_id = db.Column(
        UUID(as_uuid=False), db.ForeignKey("strategy_documents.id"), nullable=True
    )
    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.text("now()"))

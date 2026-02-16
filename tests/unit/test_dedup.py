"""Unit tests for dedup service."""
import pytest

from api.models import Batch, Company, Contact, Owner, db
from api.services.dedup import (
    COMPANY_UPDATABLE_FIELDS,
    CONTACT_UPDATABLE_FIELDS,
    dedup_preview,
    execute_import,
    find_existing_company,
    find_existing_contact,
    normalize_domain,
    update_empty_fields,
)


class TestNormalizeDomain:
    def test_full_url(self):
        assert normalize_domain("https://www.example.com/about") == "example.com"

    def test_http(self):
        assert normalize_domain("http://example.org") == "example.org"

    def test_www(self):
        assert normalize_domain("www.test.io") == "test.io"

    def test_plain(self):
        assert normalize_domain("acme.com") == "acme.com"

    def test_case(self):
        assert normalize_domain("HTTPS://WWW.ACME.COM") == "acme.com"

    def test_trailing_path(self):
        assert normalize_domain("example.com/path/to/page") == "example.com"

    def test_query(self):
        assert normalize_domain("example.com?foo=bar") == "example.com"

    def test_empty(self):
        assert normalize_domain(None) is None
        assert normalize_domain("") is None


class TestFindExistingCompany:
    def test_match_by_domain(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        co, match_type = find_existing_company(data["tenant"].id, domain="acme.com")
        assert co is not None
        assert co.name == "Acme Corp"
        assert match_type == "domain"

    def test_match_by_name(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        co, match_type = find_existing_company(data["tenant"].id, name="Beta Inc")
        assert co is not None
        assert co.domain == "beta.io"
        assert match_type == "name"

    def test_match_by_name_case_insensitive(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        co, match_type = find_existing_company(data["tenant"].id, name="ACME CORP")
        assert co is not None
        assert match_type == "name"

    def test_domain_priority_over_name(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        co, match_type = find_existing_company(data["tenant"].id, name="Wrong Name", domain="acme.com")
        assert co is not None
        assert co.name == "Acme Corp"
        assert match_type == "domain"

    def test_no_match(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        co, match_type = find_existing_company(data["tenant"].id, name="Nonexistent Corp", domain="nonexistent.xyz")
        assert co is None
        assert match_type is None


class TestFindExistingContact:
    def test_match_by_linkedin(self, app, db, seed_companies_contacts):
        """Seeded contacts don't have linkedin_url, so test with email."""
        data = seed_companies_contacts
        ct, match_type = find_existing_contact(data["tenant"].id, email="john@acme.com")
        assert ct is not None
        assert ct.first_name == "John"
        assert ct.last_name == "Doe"
        assert match_type == "email"

    def test_match_by_email_case_insensitive(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        ct, match_type = find_existing_contact(data["tenant"].id, email="JOHN@ACME.COM")
        assert ct is not None
        assert match_type == "email"

    def test_match_by_name_and_company(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        ct, match_type = find_existing_contact(
            data["tenant"].id,
            first_name="Dave",
            last_name="Brown",
            company_name="Gamma LLC",
        )
        assert ct is not None
        assert match_type == "name_company"

    def test_no_match(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        ct, match_type = find_existing_contact(
            data["tenant"].id,
            email="nobody@nowhere.com",
            first_name="Nobody",
        )
        assert ct is None
        assert match_type is None


class TestUpdateEmptyFields:
    def test_fills_empty_fields(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        # Dave Brown has no email
        ct = data["contacts"][4]
        assert ct.email_address is None
        updated, conflicts = update_empty_fields(ct, {"email_address": "dave@gamma.co"}, CONTACT_UPDATABLE_FIELDS)
        assert "email_address" in updated
        assert ct.email_address == "dave@gamma.co"
        assert conflicts == []

    def test_does_not_overwrite_existing(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        # John Doe already has email john@acme.com
        ct = data["contacts"][0]
        updated, conflicts = update_empty_fields(ct, {"email_address": "other@email.com"}, CONTACT_UPDATABLE_FIELDS)
        assert "email_address" not in updated
        assert ct.email_address == "john@acme.com"
        assert len(conflicts) == 1
        assert conflicts[0]["field"] == "email_address"
        assert conflicts[0]["existing"] == "john@acme.com"
        assert conflicts[0]["incoming"] == "other@email.com"

    def test_no_conflict_when_values_match(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        ct = data["contacts"][0]
        updated, conflicts = update_empty_fields(ct, {"email_address": "john@acme.com"}, CONTACT_UPDATABLE_FIELDS)
        assert conflicts == []
        assert "email_address" not in updated

    def test_conflict_case_insensitive_match(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        ct = data["contacts"][0]
        updated, conflicts = update_empty_fields(ct, {"email_address": "JOHN@ACME.COM"}, CONTACT_UPDATABLE_FIELDS)
        assert conflicts == []  # same value, different case = no conflict


class TestDedupPreview:
    def test_detects_existing_contact(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        parsed = [
            {"contact": {"first_name": "John", "last_name": "Doe", "email_address": "john@acme.com"}, "company": {"name": "Acme Corp"}},
            {"contact": {"first_name": "New", "last_name": "Person", "email_address": "new@new.com"}, "company": {"name": "New Co"}},
        ]
        results = dedup_preview(str(data["tenant"].id), parsed)
        assert len(results) == 2
        assert results[0]["contact_status"] == "duplicate"
        assert results[0]["contact_match_type"] == "email"
        assert results[1]["contact_status"] == "new"

    def test_detects_existing_company(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        parsed = [
            {"contact": {"first_name": "New", "last_name": "Person"}, "company": {"name": "Acme Corp", "domain": "acme.com"}},
        ]
        results = dedup_preview(str(data["tenant"].id), parsed)
        assert results[0]["company_status"] == "existing"
        assert results[0]["company_match_type"] == "domain"

    def test_detects_intra_file_dup(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        parsed = [
            {"contact": {"first_name": "New", "last_name": "A", "email_address": "same@email.com"}, "company": {"name": "NewCo"}},
            {"contact": {"first_name": "New", "last_name": "B", "email_address": "same@email.com"}, "company": {"name": "NewCo"}},
        ]
        results = dedup_preview(str(data["tenant"].id), parsed)
        assert results[0]["contact_status"] == "new"
        assert results[1]["contact_status"] == "duplicate"
        assert results[1]["contact_match_type"] == "email_intra"


class TestExecuteImport:
    def _make_job(self, db, tenant_id, user_id, batch_id):
        from api.models import ImportJob
        import json
        job = ImportJob(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            filename="test.csv",
            total_rows=2,
            headers=json.dumps(["Name", "Email"]),
            status="previewed",
        )
        db.session.add(job)
        db.session.flush()
        return job

    def test_creates_contacts_and_companies(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        parsed = [
            {"contact": {"first_name": "New", "last_name": "Guy", "email_address": "new@newco.com"}, "company": {"name": "Brand New Co", "domain": "newco.com"}},
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="skip",
        )
        assert result["counts"]["contacts_created"] == 1
        assert result["counts"]["companies_created"] == 1

    def test_skip_strategy_skips_duplicates(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        parsed = [
            {"contact": {"first_name": "John", "last_name": "Doe", "email_address": "john@acme.com"}, "company": {"name": "Acme Corp"}},
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="skip",
        )
        assert result["counts"]["contacts_skipped"] == 1
        assert result["counts"]["contacts_created"] == 0
        # Verify dedup_rows has skip detail
        rows = result["dedup_rows"]
        assert len(rows) == 1
        assert rows[0]["action"] == "skipped"
        assert rows[0]["match_type"] == "email"
        assert rows[0]["matched_contact_name"] == "John Doe"

    def test_update_strategy_fills_fields(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        # Dave Brown (contacts[4]) has no email
        parsed = [
            {"contact": {"first_name": "Dave", "last_name": "Brown", "email_address": "dave@gamma.co"}, "company": {"name": "Gamma LLC"}},
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="update",
        )
        assert result["counts"]["contacts_updated"] == 1
        assert data["contacts"][4].email_address == "dave@gamma.co"
        # Verify dedup_rows has update detail
        rows = result["dedup_rows"]
        assert len(rows) == 1
        assert rows[0]["action"] == "updated"
        assert "email_address" in rows[0]["fields_updated"]
        assert rows[0]["conflicts"] == []

    def test_update_strategy_detects_conflicts(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        # John Doe has job_title "CEO" — import with different title
        parsed = [
            {"contact": {"first_name": "John", "last_name": "Doe", "email_address": "john@acme.com", "job_title": "CRO"}, "company": {"name": "Acme Corp"}},
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="update",
        )
        assert result["counts"]["contacts_updated"] == 1
        rows = result["dedup_rows"]
        assert len(rows) == 1
        assert rows[0]["action"] == "updated"
        assert len(rows[0]["conflicts"]) == 1
        assert rows[0]["conflicts"][0]["field"] == "job_title"
        assert rows[0]["conflicts"][0]["existing"] == "CEO"
        assert rows[0]["conflicts"][0]["incoming"] == "CRO"

    def test_create_new_strategy(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        initial_count = Contact.query.filter_by(tenant_id=str(data["tenant"].id)).count()

        parsed = [
            {"contact": {"first_name": "John", "last_name": "Doe", "email_address": "john@acme.com"}, "company": {"name": "Acme Corp"}},
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="create_new",
        )
        assert result["counts"]["contacts_created"] == 1
        final_count = Contact.query.filter_by(tenant_id=str(data["tenant"].id)).count()
        assert final_count == initial_count + 1

    def test_links_existing_company(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        parsed = [
            {"contact": {"first_name": "Newcomer"}, "company": {"name": "Acme Corp", "domain": "acme.com"}},
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="skip",
        )
        assert result["counts"]["companies_linked"] == 1
        assert result["counts"]["companies_created"] == 0

    def test_skips_contacts_without_name(self, app, db, seed_companies_contacts):
        data = seed_companies_contacts
        batch = data["batches"][0]
        owner = data["owners"][0]
        from api.models import User
        user = User.query.first()
        job = self._make_job(db, data["tenant"].id, user.id, batch.id)

        parsed = [
            {"contact": {"email_address": "noname@test.com"}, "company": {"name": "SomeCo"}}  # no first_name,
        ]
        result = execute_import(
            str(data["tenant"].id), parsed, batch.id, owner.id, job.id, strategy="skip",
        )
        assert result["counts"]["contacts_skipped"] == 1
        # Verify dedup_rows has error detail
        rows = result["dedup_rows"]
        assert len(rows) == 1
        assert rows[0]["action"] == "error"
        assert rows[0]["reason"] == "no_name"

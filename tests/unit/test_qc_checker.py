"""Unit tests for the QC checker service."""
import uuid

import pytest

from api.services.qc_checker import (
    name_similarity,
    run_qc,
    _check_registry_name_mismatch,
    _check_hq_country_conflict,
    _check_active_insolvency,
    _check_dissolved,
    _check_data_completeness,
    _check_low_registry_confidence,
)


# ---------------------------------------------------------------------------
# name_similarity tests
# ---------------------------------------------------------------------------

class TestNameSimilarity:
    def test_identical_names(self):
        assert name_similarity("Acme Corp", "Acme Corp") == 1.0

    def test_case_insensitive(self):
        assert name_similarity("Acme Corp", "acme corp") == 1.0

    def test_strips_legal_suffixes(self):
        assert name_similarity("Acme GmbH", "Acme Ltd") == 1.0

    def test_strips_czech_suffixes(self):
        assert name_similarity("Firma s.r.o.", "Firma a.s.") == 1.0

    def test_completely_different(self):
        sim = name_similarity("Alpha Technologies", "Zebra Logistics")
        assert sim < 0.3

    def test_similar_names(self):
        sim = name_similarity("Acme Technologies", "Acme Technology")
        assert sim > 0.7

    def test_empty_string(self):
        assert name_similarity("", "Anything") == 0.0
        assert name_similarity("Anything", "") == 0.0

    def test_none_values(self):
        assert name_similarity(None, "Anything") == 0.0
        assert name_similarity("Anything", None) == 0.0


# ---------------------------------------------------------------------------
# Individual check function tests
# ---------------------------------------------------------------------------

class TestRegistryNameMismatch:
    def test_no_mismatch_good_match(self):
        flags = _check_registry_name_mismatch("Acme Corp", [
            {"official_name": "Acme Corporation", "registry_country": "CZ"},
        ])
        assert flags == []

    def test_mismatch_detected(self):
        flags = _check_registry_name_mismatch("Alpha Tech", [
            {"official_name": "Zebra Logistics", "registry_country": "CZ"},
        ])
        assert len(flags) == 1
        assert flags[0].startswith("registry_name_mismatch:CZ:")

    def test_no_registry_data(self):
        assert _check_registry_name_mismatch("Acme", []) == []

    def test_missing_official_name(self):
        flags = _check_registry_name_mismatch("Acme", [
            {"official_name": None, "registry_country": "CZ"},
        ])
        assert flags == []


class TestHqCountryConflict:
    def test_no_conflict_same_country(self):
        flags = _check_hq_country_conflict("Czech Republic", [
            {"registry_country": "CZ"},
        ])
        assert flags == []

    def test_conflict_detected(self):
        flags = _check_hq_country_conflict("Germany", [
            {"registry_country": "CZ"},
        ])
        assert len(flags) == 1
        assert "hq_country_conflict" in flags[0]

    def test_no_hq_country(self):
        flags = _check_hq_country_conflict(None, [
            {"registry_country": "CZ"},
        ])
        assert flags == []

    def test_iso_normalization(self):
        # "NO" and "Norway" should match
        flags = _check_hq_country_conflict("Norway", [
            {"registry_country": "NO"},
        ])
        assert flags == []

    def test_multiple_registries(self):
        # Company in Germany but registered in both CZ and NO
        flags = _check_hq_country_conflict("Germany", [
            {"registry_country": "CZ"},
            {"registry_country": "NO"},
        ])
        assert len(flags) == 2


class TestActiveInsolvency:
    def test_active_insolvency(self):
        flags = _check_active_insolvency([
            {"has_insolvency": True, "active_proceedings": 2, "total_proceedings": 3},
        ])
        assert len(flags) == 1
        assert "active_insolvency" in flags[0]
        assert "2_proceedings" in flags[0]

    def test_no_insolvency(self):
        flags = _check_active_insolvency([
            {"has_insolvency": False, "active_proceedings": 0, "total_proceedings": 0},
        ])
        assert flags == []

    def test_historical_only(self):
        flags = _check_active_insolvency([
            {"has_insolvency": True, "active_proceedings": 0, "total_proceedings": 2},
        ])
        assert flags == []

    def test_empty(self):
        assert _check_active_insolvency([]) == []


class TestDissolved:
    def test_dissolved_by_date(self):
        flags = _check_dissolved([
            {"registration_status": "AKTIVNI", "date_dissolved": "2024-01-15"},
        ])
        assert flags == ["company_dissolved"]

    def test_dissolved_by_status(self):
        flags = _check_dissolved([
            {"registration_status": "ZANIKLÝ", "date_dissolved": None},
        ])
        assert flags == ["company_dissolved"]

    def test_active(self):
        flags = _check_dissolved([
            {"registration_status": "AKTIVNI", "date_dissolved": None},
        ])
        assert flags == []


class TestDataCompleteness:
    def test_missing_summary_after_l1(self):
        company = {"summary": None, "hq_country": "CZ", "industry": "software_saas"}
        flags = _check_data_completeness(company, False, False, {"l1"})
        assert "missing_summary_after_l1" in flags

    def test_missing_hq_after_l1(self):
        company = {"summary": "A company", "hq_country": None, "industry": "software_saas"}
        flags = _check_data_completeness(company, False, False, {"l1"})
        assert "missing_hq_after_l1" in flags

    def test_l2_completed_but_no_data(self):
        company = {"summary": "A company", "hq_country": "CZ", "industry": "software_saas"}
        flags = _check_data_completeness(company, False, False, {"l1", "l2"})
        assert "l2_completed_but_no_data" in flags

    def test_all_present(self):
        company = {"summary": "A company", "hq_country": "CZ", "industry": "software_saas"}
        flags = _check_data_completeness(company, True, True, {"l1", "l2"})
        assert flags == []

    def test_no_l1_no_flags(self):
        company = {"summary": None, "hq_country": None, "industry": None}
        flags = _check_data_completeness(company, False, False, set())
        assert flags == []


class TestLowRegistryConfidence:
    def test_low_confidence_name_match(self):
        flags = _check_low_registry_confidence([
            {"match_confidence": 0.55, "match_method": "name_auto", "registry_country": "CZ"},
        ])
        assert len(flags) == 1
        assert "low_registry_confidence:CZ" in flags[0]

    def test_ico_direct_exempt(self):
        flags = _check_low_registry_confidence([
            {"match_confidence": 0.50, "match_method": "ico_direct", "registry_country": "CZ"},
        ])
        assert flags == []

    def test_high_confidence(self):
        flags = _check_low_registry_confidence([
            {"match_confidence": 0.95, "match_method": "name_auto", "registry_country": "CZ"},
        ])
        assert flags == []


# ---------------------------------------------------------------------------
# Integration test: run_qc with DB
# ---------------------------------------------------------------------------

class TestRunQc:
    def test_entity_not_found(self, app, db):
        """run_qc returns entity_not_found for nonexistent company."""
        with app.app_context():
            result = run_qc(str(uuid.uuid4()), str(uuid.uuid4()))
            assert result["enrichment_cost_usd"] == 0.0
            assert "entity_not_found" in result["qc_flags"]

    def test_clean_company_no_flags(self, app, db, seed_tenant):
        """Company with good data and no registry/insolvency → no QC flags."""
        from sqlalchemy import text as sa_text
        with app.app_context():
            company_id = str(uuid.uuid4())
            db.session.execute(sa_text("""
                INSERT INTO companies (id, tenant_id, name, domain, hq_country, industry, summary, status)
                VALUES (:id, :tid, :name, :domain, :hq, :ind, :sum, :status)
            """), {
                "id": company_id,
                "tid": str(seed_tenant.id),
                "name": "Acme Technologies",
                "domain": "acme.com",
                "hq": "Czech Republic",
                "ind": "software_saas",
                "sum": "A leading SaaS company in Prague.",
                "status": "enriched_l2",
            })
            db.session.commit()

            result = run_qc(company_id, str(seed_tenant.id))
            assert result["enrichment_cost_usd"] == 0.0
            assert result["qc_flags"] == []

    def test_registry_name_mismatch_flag(self, app, db, seed_tenant):
        """Company with mismatched registry name gets flagged."""
        from sqlalchemy import text as sa_text
        with app.app_context():
            company_id = str(uuid.uuid4())
            db.session.execute(sa_text("""
                INSERT INTO companies (id, tenant_id, name, domain, status)
                VALUES (:id, :tid, :name, :domain, :status)
            """), {
                "id": company_id,
                "tid": str(seed_tenant.id),
                "name": "Acme Technologies",
                "domain": "acme.com",
                "status": "new",
            })
            db.session.execute(sa_text("""
                INSERT INTO company_registry_data (company_id, official_name, registry_country)
                VALUES (:cid, :name, :country)
            """), {
                "cid": company_id,
                "name": "Totally Different Company",
                "country": "CZ",
            })
            db.session.commit()

            result = run_qc(company_id, str(seed_tenant.id))
            flags = result["qc_flags"]
            assert any("registry_name_mismatch" in f for f in flags)

    def test_insolvency_flag(self, app, db, seed_tenant):
        """Company with active insolvency gets flagged."""
        from sqlalchemy import text as sa_text
        with app.app_context():
            company_id = str(uuid.uuid4())
            db.session.execute(sa_text("""
                INSERT INTO companies (id, tenant_id, name, domain, status)
                VALUES (:id, :tid, :name, :domain, :status)
            """), {
                "id": company_id,
                "tid": str(seed_tenant.id),
                "name": "Troubled Corp",
                "domain": "troubled.com",
                "status": "new",
            })
            db.session.execute(sa_text("""
                INSERT INTO company_insolvency_data (id, tenant_id, company_id, ico, has_insolvency, active_proceedings, total_proceedings)
                VALUES (:id, :tid, :cid, :ico, :flag, :active, :total)
            """), {
                "id": str(uuid.uuid4()),
                "tid": str(seed_tenant.id),
                "cid": company_id,
                "ico": "12345678",
                "flag": 1,
                "active": 2,
                "total": 3,
            })
            db.session.commit()

            result = run_qc(company_id, str(seed_tenant.id))
            flags = result["qc_flags"]
            assert any("active_insolvency" in f for f in flags)

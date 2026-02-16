"""Tests for EntityStageCompletion model."""
import uuid

import pytest

from tests.conftest import auth_header


class TestEntityStageCompletionModel:
    def test_create_completion(self, db, seed_tenant):
        from api.models import Batch, Company, EntityStageCompletion

        batch = Batch(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        db.session.add(batch)
        db.session.flush()

        company = Company(
            tenant_id=seed_tenant.id, name="Test Co", batch_id=batch.id, status="new",
        )
        db.session.add(company)
        db.session.flush()

        esc = EntityStageCompletion(
            tenant_id=seed_tenant.id,
            batch_id=batch.id,
            entity_type="company",
            entity_id=company.id,
            stage="l1",
            status="completed",
            cost_usd=0.02,
        )
        db.session.add(esc)
        db.session.commit()

        # Verify it was persisted
        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=company.id, stage="l1",
        ).first()
        assert result is not None
        assert result.status == "completed"
        assert float(result.cost_usd) == 0.02
        assert result.entity_type == "company"

    def test_create_failed_completion(self, db, seed_tenant):
        from api.models import Batch, Company, EntityStageCompletion

        batch = Batch(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        db.session.add(batch)
        db.session.flush()

        company = Company(
            tenant_id=seed_tenant.id, name="Test Co", batch_id=batch.id, status="new",
        )
        db.session.add(company)
        db.session.flush()

        esc = EntityStageCompletion(
            tenant_id=seed_tenant.id,
            batch_id=batch.id,
            entity_type="company",
            entity_id=company.id,
            stage="l1",
            status="failed",
            error="API timeout",
        )
        db.session.add(esc)
        db.session.commit()

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=company.id, stage="l1",
        ).first()
        assert result.status == "failed"
        assert result.error == "API timeout"

    def test_create_skipped_completion(self, db, seed_tenant):
        from api.models import Batch, Company, EntityStageCompletion

        batch = Batch(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        db.session.add(batch)
        db.session.flush()

        company = Company(
            tenant_id=seed_tenant.id, name="Test Co", batch_id=batch.id, status="new",
        )
        db.session.add(company)
        db.session.flush()

        esc = EntityStageCompletion(
            tenant_id=seed_tenant.id,
            batch_id=batch.id,
            entity_type="company",
            entity_id=company.id,
            stage="ares",
            status="skipped",
        )
        db.session.add(esc)
        db.session.commit()

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=company.id, stage="ares",
        ).first()
        assert result.status == "skipped"

    def test_contact_completion(self, db, seed_tenant):
        from api.models import Batch, Company, Contact, EntityStageCompletion

        batch = Batch(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        db.session.add(batch)
        db.session.flush()

        company = Company(
            tenant_id=seed_tenant.id, name="Test Co", batch_id=batch.id, status="new",
        )
        db.session.add(company)
        db.session.flush()

        contact = Contact(
            tenant_id=seed_tenant.id, first_name="Jane", last_name="Doe",
            company_id=company.id, batch_id=batch.id,
        )
        db.session.add(contact)
        db.session.flush()

        esc = EntityStageCompletion(
            tenant_id=seed_tenant.id,
            batch_id=batch.id,
            entity_type="contact",
            entity_id=contact.id,
            stage="person",
            status="completed",
            cost_usd=0.04,
        )
        db.session.add(esc)
        db.session.commit()

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=contact.id, stage="person",
        ).first()
        assert result is not None
        assert result.entity_type == "contact"

    def test_multiple_stages_per_entity(self, db, seed_tenant):
        """An entity can have completions for multiple stages."""
        from api.models import Batch, Company, EntityStageCompletion

        batch = Batch(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        db.session.add(batch)
        db.session.flush()

        company = Company(
            tenant_id=seed_tenant.id, name="Test Co", batch_id=batch.id, status="new",
        )
        db.session.add(company)
        db.session.flush()

        for stage in ["l1", "l2", "ares"]:
            esc = EntityStageCompletion(
                tenant_id=seed_tenant.id,
                batch_id=batch.id,
                entity_type="company",
                entity_id=company.id,
                stage=stage,
                status="completed",
            )
            db.session.add(esc)
        db.session.commit()

        completions = db.session.query(EntityStageCompletion).filter_by(
            entity_id=company.id,
        ).all()
        assert len(completions) == 3
        stages = {c.stage for c in completions}
        assert stages == {"l1", "l2", "ares"}

    def test_pipeline_run_id_nullable(self, db, seed_tenant):
        """pipeline_run_id is nullable (backfill records won't have one)."""
        from api.models import Batch, Company, EntityStageCompletion

        batch = Batch(tenant_id=seed_tenant.id, name="test-batch", is_active=True)
        db.session.add(batch)
        db.session.flush()

        company = Company(
            tenant_id=seed_tenant.id, name="Test Co", batch_id=batch.id, status="new",
        )
        db.session.add(company)
        db.session.flush()

        esc = EntityStageCompletion(
            tenant_id=seed_tenant.id,
            batch_id=batch.id,
            pipeline_run_id=None,
            entity_type="company",
            entity_id=company.id,
            stage="l1",
            status="completed",
        )
        db.session.add(esc)
        db.session.commit()

        result = db.session.query(EntityStageCompletion).filter_by(
            entity_id=company.id,
        ).first()
        assert result.pipeline_run_id is None

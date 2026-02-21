"""Tests for StrategyDocument and StrategyChatMessage models."""
import pytest


class TestStrategyDocumentModel:
    def test_create_document(self, app, db, seed_tenant):
        from api.models import StrategyDocument
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# My Strategy\n\nSome content here.",
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()
        fetched = db.session.get(StrategyDocument, doc.id)
        assert fetched is not None
        assert fetched.tenant_id == seed_tenant.id
        assert fetched.status == "draft"
        assert fetched.version == 1
        assert fetched.content == "# My Strategy\n\nSome content here."

    def test_create_document_with_objective(self, app, db, seed_tenant):
        from api.models import StrategyDocument
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="",
            objective="Grow enterprise pipeline by 3x",
            status="draft",
        )
        db.session.add(doc)
        db.session.commit()
        fetched = db.session.get(StrategyDocument, doc.id)
        assert fetched.objective == "Grow enterprise pipeline by 3x"

    def test_one_document_per_tenant(self, app, db, seed_tenant):
        from api.models import StrategyDocument
        from sqlalchemy.exc import IntegrityError
        doc1 = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc1)
        db.session.commit()
        doc2 = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc2)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_to_dict(self, app, db, seed_tenant):
        from api.models import StrategyDocument
        doc = StrategyDocument(
            tenant_id=seed_tenant.id,
            content="# Strategy\n\nContent here.",
            extracted_data={"icp": {"industries": ["SaaS"]}},
            status="active",
            objective="Win more deals",
        )
        db.session.add(doc)
        db.session.commit()
        d = doc.to_dict()
        assert d["status"] == "active"
        assert d["version"] == 1
        assert "id" in d
        assert d["content"] == "# Strategy\n\nContent here."
        assert "extracted_data" in d
        assert d["objective"] == "Win more deals"


class TestStrategyChatMessageModel:
    def test_create_message(self, app, db, seed_tenant):
        from api.models import StrategyDocument, StrategyChatMessage
        doc = StrategyDocument(tenant_id=seed_tenant.id)
        db.session.add(doc)
        db.session.commit()
        msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=doc.id,
            role="user",
            content="Help me define my ICP",
        )
        db.session.add(msg)
        db.session.commit()
        fetched = db.session.get(StrategyChatMessage, msg.id)
        assert fetched is not None
        assert fetched.role == "user"
        assert fetched.content == "Help me define my ICP"
        assert fetched.document_id == doc.id

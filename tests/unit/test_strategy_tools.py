"""Tests for strategy document tool handlers (WRITE feature).

Tests cover:
- Section parsing (_find_section)
- Nested path setting (_set_nested)
- Tool handlers (get, update, set_extracted, append)
- Undo endpoint
- has_ai_edits flag on GET /api/playbook
- Error cases (invalid section, missing doc)
"""

import json
import uuid

import pytest

from api.models import StrategyDocument, StrategyVersion
from api.services.strategy_tools import (
    _find_section,
    _set_nested,
    append_to_section,
    get_strategy_document,
    set_extracted_field,
    update_strategy_section,
)
from api.services.tool_registry import ToolContext


SAMPLE_STRATEGY = """# My Strategy

## Executive Summary

This is the executive summary of our go-to-market strategy.

## Ideal Customer Profile (ICP)

We target mid-market SaaS companies with 50-500 employees.

## Buyer Personas

**CTO**: Technical decision maker who values innovation.

## Value Proposition & Messaging

We help companies automate their workflows.

## Competitive Positioning

Our main differentiator is AI-native architecture.

## Channel Strategy

LinkedIn outreach and cold email as primary channels.

## Messaging Framework

Problem-solution framework with social proof.

## Metrics & KPIs

Target 5% reply rate and 2% meeting rate.

## 90-Day Action Plan

Phase 1: Launch LinkedIn campaign.
Phase 2: Expand to email.
Phase 3: Evaluate and iterate.
"""


def auth_header(client, email="admin@test.com", password="testpass123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": "Bearer {}".format(token)}


@pytest.fixture
def strategy_doc(db, seed_tenant):
    """Create a strategy document with sample content."""
    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content=SAMPLE_STRATEGY,
        extracted_data=json.dumps({"icp": {"industries": ["saas"]}}),
        status="draft",
        version=1,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@pytest.fixture
def tool_ctx(seed_tenant, seed_super_admin):
    """Create a ToolContext for tool handler tests."""
    return ToolContext(
        tenant_id=str(seed_tenant.id),
        user_id=str(seed_super_admin.id),
        turn_id=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# _find_section tests
# ---------------------------------------------------------------------------

class TestFindSection:
    def test_finds_first_section(self):
        bounds = _find_section(SAMPLE_STRATEGY, "Executive Summary")
        assert bounds is not None
        start, end = bounds
        body = SAMPLE_STRATEGY[start:end]
        assert "executive summary of our go-to-market" in body

    def test_finds_middle_section(self):
        bounds = _find_section(SAMPLE_STRATEGY, "Buyer Personas")
        assert bounds is not None
        start, end = bounds
        body = SAMPLE_STRATEGY[start:end]
        assert "CTO" in body

    def test_finds_last_section(self):
        bounds = _find_section(SAMPLE_STRATEGY, "90-Day Action Plan")
        assert bounds is not None
        start, end = bounds
        body = SAMPLE_STRATEGY[start:end]
        assert "Phase 1" in body

    def test_returns_none_for_missing_section(self):
        assert _find_section(SAMPLE_STRATEGY, "Nonexistent Section") is None

    def test_section_with_special_chars(self):
        """Section name with parentheses and ampersand."""
        bounds = _find_section(SAMPLE_STRATEGY, "Ideal Customer Profile (ICP)")
        assert bounds is not None
        start, end = bounds
        body = SAMPLE_STRATEGY[start:end]
        assert "mid-market SaaS" in body

    def test_section_with_ampersand(self):
        bounds = _find_section(SAMPLE_STRATEGY, "Value Proposition & Messaging")
        assert bounds is not None
        start, end = bounds
        body = SAMPLE_STRATEGY[start:end]
        assert "automate their workflows" in body

    def test_section_body_does_not_include_heading(self):
        bounds = _find_section(SAMPLE_STRATEGY, "Executive Summary")
        assert bounds is not None
        start, _ = bounds
        assert not SAMPLE_STRATEGY[start:].startswith("## Executive Summary")

    def test_section_body_ends_before_next_heading(self):
        bounds = _find_section(SAMPLE_STRATEGY, "Executive Summary")
        assert bounds is not None
        _, end = bounds
        # The body should end before the next H2 heading
        remaining = SAMPLE_STRATEGY[end:]
        assert remaining.startswith("## ") or remaining.strip() == ""


# ---------------------------------------------------------------------------
# _set_nested tests
# ---------------------------------------------------------------------------

class TestSetNested:
    def test_simple_path(self):
        obj = {"icp": {}}
        _set_nested(obj, "icp.industries", ["fintech"])
        assert obj["icp"]["industries"] == ["fintech"]

    def test_deep_path(self):
        obj = {"icp": {"company_size": {}}}
        _set_nested(obj, "icp.company_size.min", 50)
        assert obj["icp"]["company_size"]["min"] == 50

    def test_creates_intermediate_dicts(self):
        obj = {}
        _set_nested(obj, "metrics.reply_rate_target", 0.15)
        assert obj["metrics"]["reply_rate_target"] == 0.15

    def test_array_index(self):
        obj = {"personas": [{"name": "CTO"}, {"name": "VP Eng"}]}
        _set_nested(obj, "personas[0].name", "CEO")
        assert obj["personas"][0]["name"] == "CEO"

    def test_invalid_array_index_raises(self):
        obj = {"personas": [{"name": "CTO"}]}
        with pytest.raises(KeyError):
            _set_nested(obj, "personas[5].name", "CEO")

    def test_top_level_key(self):
        obj = {"foo": "bar"}
        _set_nested(obj, "foo", "baz")
        assert obj["foo"] == "baz"


# ---------------------------------------------------------------------------
# get_strategy_document tests
# ---------------------------------------------------------------------------

class TestGetStrategyDocument:
    def test_returns_document(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = get_strategy_document({}, tool_ctx)
            assert "content" in result
            assert "Executive Summary" in result["content"]
            assert result["version"] == 1

    def test_returns_error_when_no_doc(self, app, db):
        ctx = ToolContext(tenant_id=str(uuid.uuid4()))
        with app.app_context():
            result = get_strategy_document({}, ctx)
            assert "error" in result


# ---------------------------------------------------------------------------
# update_strategy_section tests
# ---------------------------------------------------------------------------

class TestUpdateStrategySection:
    def test_updates_section_content(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = update_strategy_section(
                {"section": "Executive Summary", "content": "New summary content."},
                tool_ctx,
            )
            assert result.get("success") is True
            assert result["version"] == 2
            assert result["previous_version"] == 1

            doc = StrategyDocument.query.filter_by(
                tenant_id=tool_ctx.tenant_id
            ).first()
            assert "New summary content." in doc.content
            # Other sections should be unchanged
            assert "mid-market SaaS" in doc.content

    def test_creates_version_snapshot(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            update_strategy_section(
                {"section": "Executive Summary", "content": "Updated."},
                tool_ctx,
            )
            snap = StrategyVersion.query.filter_by(
                document_id=strategy_doc.id
            ).first()
            assert snap is not None
            assert snap.version == 1
            assert snap.edit_source == "ai_tool"
            assert "executive summary of our go-to-market" in snap.content

    def test_invalid_section_returns_error(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = update_strategy_section(
                {"section": "Nonexistent", "content": "Content"},
                tool_ctx,
            )
            assert "error" in result
            assert "not found" in result["error"]
            assert "Available sections" in result["error"]

    def test_preserves_other_sections(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            update_strategy_section(
                {"section": "Channel Strategy", "content": "Only Twitter."},
                tool_ctx,
            )
            doc = StrategyDocument.query.filter_by(
                tenant_id=tool_ctx.tenant_id
            ).first()
            assert "mid-market SaaS" in doc.content
            assert "Only Twitter." in doc.content

    def test_turn_id_set_on_snapshot(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            update_strategy_section(
                {"section": "Executive Summary", "content": "Updated."},
                tool_ctx,
            )
            snap = StrategyVersion.query.filter_by(
                document_id=strategy_doc.id
            ).first()
            assert snap.turn_id == tool_ctx.turn_id


# ---------------------------------------------------------------------------
# set_extracted_field tests
# ---------------------------------------------------------------------------

class TestSetExtractedField:
    def test_sets_simple_field(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = set_extracted_field(
                {"path": "metrics.reply_rate_target", "value": 0.15},
                tool_ctx,
            )
            assert result.get("success") is True
            doc = StrategyDocument.query.filter_by(
                tenant_id=tool_ctx.tenant_id
            ).first()
            extracted = doc.extracted_data
            if isinstance(extracted, str):
                extracted = json.loads(extracted)
            assert extracted["metrics"]["reply_rate_target"] == 0.15

    def test_sets_array_value(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = set_extracted_field(
                {"path": "icp.industries", "value": ["fintech", "insurtech"]},
                tool_ctx,
            )
            assert result.get("success") is True

    def test_creates_snapshot(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            set_extracted_field(
                {"path": "icp.industries", "value": ["fintech"]},
                tool_ctx,
            )
            snap = StrategyVersion.query.filter_by(
                document_id=strategy_doc.id
            ).first()
            assert snap is not None
            assert snap.edit_source == "ai_tool"


# ---------------------------------------------------------------------------
# append_to_section tests
# ---------------------------------------------------------------------------

class TestAppendToSection:
    def test_appends_content(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = append_to_section(
                {
                    "section": "Buyer Personas",
                    "content": "**VP Sales**: Revenue-focused buyer.",
                },
                tool_ctx,
            )
            assert result.get("success") is True
            assert result["action"] == "appended"

            doc = StrategyDocument.query.filter_by(
                tenant_id=tool_ctx.tenant_id
            ).first()
            assert "CTO" in doc.content
            assert "VP Sales" in doc.content

    def test_invalid_section_returns_error(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            result = append_to_section(
                {"section": "Nonexistent", "content": "Content"},
                tool_ctx,
            )
            assert "error" in result

    def test_creates_snapshot(self, app, strategy_doc, tool_ctx):
        with app.app_context():
            append_to_section(
                {"section": "Buyer Personas", "content": "More content."},
                tool_ctx,
            )
            snap = StrategyVersion.query.filter_by(
                document_id=strategy_doc.id
            ).first()
            assert snap is not None
            assert snap.version == 1


# ---------------------------------------------------------------------------
# Batch edits (multiple tool calls in one turn)
# ---------------------------------------------------------------------------

class TestBatchEdits:
    def test_multiple_edits_create_multiple_snapshots(
        self, app, strategy_doc, tool_ctx
    ):
        with app.app_context():
            update_strategy_section(
                {"section": "Executive Summary", "content": "Edit 1."},
                tool_ctx,
            )
            update_strategy_section(
                {"section": "Channel Strategy", "content": "Edit 2."},
                tool_ctx,
            )
            set_extracted_field(
                {"path": "metrics.reply_rate_target", "value": 0.1},
                tool_ctx,
            )

            snaps = StrategyVersion.query.filter_by(
                document_id=strategy_doc.id, turn_id=tool_ctx.turn_id
            ).all()
            assert len(snaps) == 3


# ---------------------------------------------------------------------------
# Undo endpoint tests
# ---------------------------------------------------------------------------

class TestUndoEndpoint:
    def test_undo_reverts_ai_edit(
        self, client, app, seed_tenant, seed_super_admin, strategy_doc, tool_ctx
    ):
        """POST /api/playbook/undo reverts the last AI edit."""
        with app.app_context():
            original_content = strategy_doc.content
            update_strategy_section(
                {"section": "Executive Summary", "content": "AI wrote this."},
                tool_ctx,
            )

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/undo", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["restored_version"] == 1

        with app.app_context():
            doc = StrategyDocument.query.filter_by(
                tenant_id=str(seed_tenant.id)
            ).first()
            assert doc.content == original_content

    def test_undo_with_no_edits_returns_404(
        self, client, seed_tenant, seed_super_admin, strategy_doc
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.post("/api/playbook/undo", headers=headers)
        assert resp.status_code == 404
        assert "No AI edits" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# GET /api/playbook includes has_ai_edits
# ---------------------------------------------------------------------------

class TestGetPlaybookHasAIEdits:
    def test_has_ai_edits_false_when_no_versions(
        self, client, seed_tenant, seed_super_admin, strategy_doc
    ):
        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["has_ai_edits"] is False

    def test_has_ai_edits_true_after_tool_edit(
        self, client, app, seed_tenant, seed_super_admin, strategy_doc, tool_ctx
    ):
        with app.app_context():
            update_strategy_section(
                {"section": "Executive Summary", "content": "AI edit."},
                tool_ctx,
            )

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["has_ai_edits"] is True

"""Tests for BL-119: Proactive AI analysis + suggestions.

Tests cover:
- build_proactive_analysis_prompt() returns a well-formed prompt
- Prompt includes strategy content references
- Prompt with enrichment data includes data-specific suggestions
- Prompt without enrichment data still produces useful prompt
- _extract_suggestion_chips() extracts numbered items correctly
- Proactive analysis message is stored as an assistant message
"""

import json

import pytest

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# build_proactive_analysis_prompt tests
# ---------------------------------------------------------------------------


class TestBuildProactiveAnalysisPrompt:
    """Tests for the prompt builder function."""

    def test_returns_string(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt("# Strategy\n\n## ICP\nSaaS companies")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_strategy_content(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        content = "## ICP\nMid-market SaaS in DACH region\n## Channel Strategy\nLinkedIn outreach"
        result = build_proactive_analysis_prompt(content)
        assert "Mid-market SaaS in DACH region" in result
        assert "LinkedIn outreach" in result

    def test_includes_rules(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt("# Strategy")
        assert "RULES:" in result
        assert "suggestion" in result.lower() or "suggest" in result.lower()
        assert "generic" in result.lower()

    def test_includes_numbered_list_instruction(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt("# Strategy")
        assert "numbered list" in result.lower()

    def test_includes_word_limit(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt("# Strategy")
        assert "120 words" in result

    def test_with_enrichment_data_includes_industry(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        enrichment = {
            "company": {"industry": "financial_services", "name": "Acme Corp"},
            "competitors": "Stripe, Adyen",
            "pain_hypothesis": "Legacy payment systems cause 2x processing time",
        }
        result = build_proactive_analysis_prompt("# Strategy", enrichment)
        assert "financial_services" in result
        assert "Stripe, Adyen" in result
        assert "Legacy payment systems" in result
        assert "RESEARCH DATA" in result

    def test_with_enrichment_includes_customer_segments(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        enrichment = {
            "company": {"industry": "saas"},
            "customer_segments": "Enterprise, Mid-market",
            "hiring_signals": "Hiring 3 ML engineers",
        }
        result = build_proactive_analysis_prompt("# Strategy", enrichment)
        assert "Enterprise, Mid-market" in result
        assert "Hiring 3 ML engineers" in result

    def test_with_enrichment_includes_cross_reference_instruction(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        enrichment = {
            "company": {"industry": "healthcare"},
            "pain_hypothesis": "Manual patient onboarding",
        }
        result = build_proactive_analysis_prompt("# Strategy", enrichment)
        assert "Cross-reference" in result

    def test_without_enrichment_no_research_section(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt("# Strategy")
        assert "RESEARCH DATA" not in result
        assert "Cross-reference" not in result

    def test_empty_strategy_shows_empty_marker(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt("")
        assert "(empty)" in result

    def test_none_strategy_shows_empty_marker(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        result = build_proactive_analysis_prompt(None)
        assert "(empty)" in result

    def test_long_strategy_is_truncated(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        # Create a strategy longer than 4000 chars
        long_content = "x" * 5000
        result = build_proactive_analysis_prompt(long_content)
        # Should contain truncated content (4000 chars) not the full 5000
        assert "x" * 4000 in result
        assert "x" * 5000 not in result

    def test_enrichment_with_ai_opportunities_truncated(self):
        from api.services.playbook_service import build_proactive_analysis_prompt

        enrichment = {
            "company": {"industry": "tech"},
            "ai_opportunities": "A" * 300,
        }
        result = build_proactive_analysis_prompt("# Strategy", enrichment)
        # Should contain truncated ai_opportunities (max 200 chars)
        assert "A" * 200 in result
        assert "A" * 300 not in result


# ---------------------------------------------------------------------------
# _extract_suggestion_chips tests
# ---------------------------------------------------------------------------


class TestExtractSuggestionChips:
    """Tests for the chip extraction helper."""

    def test_extracts_numbered_items(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = (
            "1. Your ICP targets SaaS broadly. Want me to narrow it to healthcare SaaS?\n"
            "2. The channel strategy lacks budget allocation. Should I estimate cost-per-lead?\n"
            "3. No competitive analysis section. Want me to add one?"
        )
        chips = _extract_suggestion_chips(text)
        assert len(chips) == 3

    def test_extracts_questions(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = (
            "1. Your ICP is broad. Want me to narrow it?\n"
            "2. Missing budget info. Should I estimate costs?\n"
        )
        chips = _extract_suggestion_chips(text)
        assert any("?" in c for c in chips)

    def test_max_three_suggestions(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = (
            "1. First suggestion?\n"
            "2. Second suggestion?\n"
            "3. Third suggestion?\n"
            "4. Fourth suggestion?\n"
            "5. Fifth suggestion?\n"
        )
        chips = _extract_suggestion_chips(text)
        assert len(chips) <= 3

    def test_handles_no_numbers(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = "Here are some thoughts about the strategy."
        chips = _extract_suggestion_chips(text)
        assert len(chips) == 0

    def test_handles_empty_text(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        chips = _extract_suggestion_chips("")
        assert chips == []

    def test_truncates_long_lines(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = "1. " + "A" * 100 + " no question here"
        chips = _extract_suggestion_chips(text)
        assert len(chips) == 1
        assert len(chips[0]) <= 83  # 80 + "..."

    def test_parenthesized_numbers(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = (
            "1) Your ICP targets SaaS. Want me to narrow it?\n"
            "2) Channel strategy needs work. Should I add budget?\n"
        )
        chips = _extract_suggestion_chips(text)
        assert len(chips) == 2

    def test_extracts_last_question_from_multi_sentence(self):
        from api.routes.playbook_routes import _extract_suggestion_chips

        text = "1. Your ICP mentions healthcare broadly. Based on research, you have strong positioning in digital health. Want me to narrow the ICP to digital health specifically?"
        chips = _extract_suggestion_chips(text)
        assert len(chips) == 1
        assert "?" in chips[0]


# ---------------------------------------------------------------------------
# Integration: proactive analysis message storage
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_strategy_doc_with_enrichment(db, seed_tenant, seed_super_admin):
    """Create a strategy document with enrichment data linked."""
    from api.models import (
        Company,
        StrategyDocument,
        UserTenantRole,
    )

    role = UserTenantRole(
        user_id=seed_super_admin.id,
        tenant_id=seed_tenant.id,
        role="admin",
        granted_by=seed_super_admin.id,
    )
    db.session.add(role)

    company = Company(
        tenant_id=seed_tenant.id,
        name="Test Company",
        domain="test.com",
        is_self=True,
        status="enriched_l2",
        industry="saas",
    )
    db.session.add(company)
    db.session.flush()

    doc = StrategyDocument(
        tenant_id=seed_tenant.id,
        content="# Test Strategy\n\n## ICP\nSaaS companies in DACH",
        status="draft",
        enrichment_id=company.id,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


class TestProactiveAnalysisStorage:
    """Test that proactive analysis messages are stored correctly."""

    def test_analysis_message_saved_as_assistant(
        self, client, db, seed_tenant, seed_super_admin, seed_strategy_doc_with_enrichment
    ):
        """Verify a manually created analysis message is stored as assistant role."""
        from api.models import StrategyChatMessage

        doc = seed_strategy_doc_with_enrichment

        # Simulate what the route does: save an analysis message
        msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=doc.id,
            role="assistant",
            content="1. Your ICP is broad. Want me to narrow it?",
            extra={"proactive_analysis": True},
        )
        db.session.add(msg)
        db.session.commit()

        # Verify it's stored correctly
        saved = StrategyChatMessage.query.filter_by(
            document_id=doc.id, role="assistant"
        ).all()
        assert len(saved) == 1
        assert saved[0].content == "1. Your ICP is broad. Want me to narrow it?"

        # Verify extra metadata
        extra = saved[0].extra
        if isinstance(extra, str):
            extra = json.loads(extra)
        assert extra.get("proactive_analysis") is True

    def test_analysis_message_visible_in_chat_history(
        self, client, db, seed_tenant, seed_super_admin, seed_strategy_doc_with_enrichment
    ):
        """Verify that the analysis message shows up in GET /api/playbook/chat."""
        from api.models import StrategyChatMessage

        doc = seed_strategy_doc_with_enrichment

        # Create a user message and an analysis message
        user_msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=doc.id,
            role="user",
            content="Generate my strategy",
            created_by=seed_super_admin.id,
        )
        db.session.add(user_msg)

        assistant_msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=doc.id,
            role="assistant",
            content="Here is your strategy...",
        )
        db.session.add(assistant_msg)

        analysis_msg = StrategyChatMessage(
            tenant_id=seed_tenant.id,
            document_id=doc.id,
            role="assistant",
            content="1. Your ICP is broad. Want me to narrow it?",
            extra={"proactive_analysis": True},
        )
        db.session.add(analysis_msg)
        db.session.commit()

        headers = auth_header(client)
        headers["X-Namespace"] = seed_tenant.slug
        resp = client.get("/api/playbook/chat", headers=headers)
        assert resp.status_code == 200

        msgs = resp.get_json()["messages"]
        # Should include the user msg + assistant msg + analysis msg
        assert len(msgs) == 3
        # Last message should be the analysis
        assert msgs[-1]["role"] == "assistant"
        assert "ICP is broad" in msgs[-1]["content"]


class TestBuildProactiveAnalysisPromptImport:
    """Verify the function is importable from playbook_routes."""

    def test_import_in_routes(self):
        """Verify build_proactive_analysis_prompt is imported in playbook_routes."""
        from api.routes.playbook_routes import build_proactive_analysis_prompt

        assert callable(build_proactive_analysis_prompt)

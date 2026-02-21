"""Tests for playbook service (system prompt builder and message formatting)."""
import pytest


class TestBuildSystemPrompt:
    def test_basic_prompt_contains_strategy_sections(self):
        """System prompt mentions the 8-section strategy structure."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme Corp"
        doc = MagicMock()
        doc.content = {}

        prompt = build_system_prompt(tenant, doc)

        assert isinstance(prompt, str)
        assert len(prompt) > 100
        # Must reference the 8 strategy sections
        assert "Executive Summary" in prompt
        assert "ICP" in prompt
        assert "Buyer Personas" in prompt
        assert "Value Proposition" in prompt
        assert "Competitive Positioning" in prompt
        assert "Channel Strategy" in prompt
        assert "Messaging Framework" in prompt
        assert "Success Metrics" in prompt

    def test_includes_tenant_name(self):
        """System prompt references the tenant/company name."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "VisionVolve"
        doc = MagicMock()
        doc.content = {}

        prompt = build_system_prompt(tenant, doc)
        assert "VisionVolve" in prompt

    def test_includes_document_content_when_present(self):
        """System prompt includes existing strategy document content."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = {"executive_summary": "We sell AI tools to SMBs."}

        prompt = build_system_prompt(tenant, doc)
        assert "We sell AI tools to SMBs" in prompt

    def test_includes_enrichment_data_when_provided(self):
        """System prompt includes company enrichment data as research context."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = {}

        enrichment = {
            "industry": "SaaS",
            "company_intel": "Series B funded, 50 employees",
        }

        prompt = build_system_prompt(tenant, doc, enrichment_data=enrichment)
        assert "SaaS" in prompt
        assert "Series B funded" in prompt

    def test_handles_empty_document_gracefully(self):
        """System prompt works even when document content is None or empty."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = None

        prompt = build_system_prompt(tenant, doc)
        assert isinstance(prompt, str)
        assert "GTM" in prompt or "go-to-market" in prompt.lower()

    def test_positions_ai_as_gtm_consultant(self):
        """System prompt positions the AI as a GTM strategy consultant."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = {}

        prompt = build_system_prompt(tenant, doc)
        # Should mention strategy/consultant/GTM role
        lower = prompt.lower()
        assert "strategy" in lower or "strategist" in lower
        assert "gtm" in lower or "go-to-market" in lower


class TestBuildMessages:
    def test_formats_correctly(self):
        """Converts chat history to Anthropic API format."""
        from api.services.playbook_service import build_messages
        from unittest.mock import MagicMock

        msg1 = MagicMock()
        msg1.role = "user"
        msg1.content = "What is our ICP?"

        msg2 = MagicMock()
        msg2.role = "assistant"
        msg2.content = "Your ICP should focus on..."

        result = build_messages([msg1, msg2], "Tell me more")

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == {"role": "user", "content": "What is our ICP?"}
        assert result[1] == {"role": "assistant", "content": "Your ICP should focus on..."}
        assert result[2] == {"role": "user", "content": "Tell me more"}

    def test_limits_history_to_20_messages(self):
        """Caps chat history at 20 messages for context window management."""
        from api.services.playbook_service import build_messages
        from unittest.mock import MagicMock

        history = []
        for i in range(30):
            msg = MagicMock()
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i}"
            history.append(msg)

        result = build_messages(history, "New question")

        # 20 from history + 1 new = 21
        assert len(result) == 21
        # Should keep the LAST 20 messages (indices 10-29)
        assert result[0]["content"] == "Message 10"
        assert result[19]["content"] == "Message 29"
        assert result[20] == {"role": "user", "content": "New question"}

    def test_appends_user_message_at_end(self):
        """New user message is always the last entry."""
        from api.services.playbook_service import build_messages
        from unittest.mock import MagicMock

        msg = MagicMock()
        msg.role = "user"
        msg.content = "First"

        result = build_messages([msg], "Second")

        assert result[-1] == {"role": "user", "content": "Second"}

    def test_empty_history(self):
        """Works with no prior chat history."""
        from api.services.playbook_service import build_messages

        result = build_messages([], "Hello!")

        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "Hello!"}


class TestBuildExtractionPrompt:
    def test_returns_system_and_user(self):
        """build_extraction_prompt returns a tuple of (system_prompt, user_message)."""
        from api.services.playbook_service import build_extraction_prompt

        system, user = build_extraction_prompt({"type": "doc", "content": []})

        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 50
        assert len(user) > 10

    def test_includes_schema_fields(self):
        """The system prompt contains all expected JSON schema fields."""
        from api.services.playbook_service import build_extraction_prompt

        system, _user = build_extraction_prompt({"type": "doc"})

        # Top-level keys
        for key in ["icp", "personas", "messaging", "channels", "metrics"]:
            assert key in system, f"Missing schema key: {key}"

        # Nested fields
        for field in [
            "industries", "company_size", "geographies", "tech_signals",
            "triggers", "disqualifiers", "title_patterns", "pain_points",
            "goals", "tone", "themes", "angles", "proof_points",
            "primary", "secondary", "cadence", "reply_rate_target",
            "meeting_rate_target", "pipeline_goal_eur", "timeline_months",
        ]:
            assert field in system, f"Missing schema field: {field}"

    def test_includes_document_content(self):
        """The user message includes the serialized document content."""
        from api.services.playbook_service import build_extraction_prompt

        content = {
            "executive_summary": "We sell AI tools to enterprise SaaS companies.",
            "icp": {"industries": ["SaaS", "FinTech"]},
        }

        _system, user = build_extraction_prompt(content)

        assert "We sell AI tools to enterprise SaaS companies" in user
        assert "SaaS" in user
        assert "FinTech" in user

    def test_instructs_json_only_output(self):
        """The system prompt instructs the LLM to output only valid JSON."""
        from api.services.playbook_service import build_extraction_prompt

        system, _user = build_extraction_prompt({})

        lower = system.lower()
        assert "json" in lower
        # Should instruct no markdown, no explanation
        assert "no" in lower or "only" in lower

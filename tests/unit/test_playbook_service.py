"""Tests for playbook service (system prompt builder and message formatting)."""


class TestBuildSystemPrompt:
    def test_basic_prompt_contains_strategy_sections(self):
        """System prompt mentions the 8-section strategy structure."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme Corp"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None

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
        doc.content = ""
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        assert "VisionVolve" in prompt

    def test_includes_document_content_when_present(self):
        """System prompt includes existing strategy document content (markdown)."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = "# Executive Summary\n\nWe sell AI tools to SMBs."
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        assert "We sell AI tools to SMBs" in prompt

    def test_includes_objective_when_present(self):
        """System prompt includes the user's stated objective."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = "Grow enterprise pipeline by 3x"

        prompt = build_system_prompt(tenant, doc)
        assert "Grow enterprise pipeline by 3x" in prompt

    def test_includes_enrichment_data_when_provided(self):
        """System prompt includes company enrichment data as research context."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None

        enrichment = {
            "company": {"name": "Acme", "industry": "SaaS"},
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
        doc.objective = None

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
        doc.content = ""
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        # Should mention strategy/consultant/GTM role
        lower = prompt.lower()
        assert "strategy" in lower or "strategist" in lower
        assert "gtm" in lower or "go-to-market" in lower

    def test_contains_tone_rules(self):
        """System prompt includes explicit tone rules forbidding harsh language."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        # Must contain the tone rules section
        assert "TONE RULES" in prompt
        # Must explicitly forbid harsh phrases
        assert "DISQUALIFY" in prompt
        assert "no verifiable business presence" in prompt
        assert "minimal digital footprint" in prompt
        assert "insufficient data" in prompt
        # Must instruct collaborative reframing
        assert "encouraging and collaborative" in prompt
        # Must position AI as strategist, not judge
        assert "strategist" in prompt.lower()

    def test_contains_sparse_data_instructions(self):
        """System prompt includes TODO/example instructions for sparse data."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        # Must instruct TODO markers for sparse sections
        assert "**TODO**" in prompt
        # Must instruct providing examples
        assert "concrete example" in prompt or "starting point" in prompt
        # Must mention never leaving sections empty
        assert "Never leave a section completely empty" in prompt

    def test_includes_conciseness_instructions(self):
        """System prompt contains rules for concise, actionable responses."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        lower = prompt.lower()
        # Must instruct conciseness
        assert "concise" in lower or "2-4 sentences" in lower
        # Must prohibit filler phrases
        assert "great question" in lower
        # Must instruct bullet points
        assert "bullet" in lower
        # Must instruct leading with insight
        assert "lead with" in lower
        # Must instruct referencing document content, never ask user to repeat
        assert "never ask the user to repeat" in lower
        assert "already written" in lower or "in the document" in lower

    def test_contains_document_awareness_instruction(self):
        """System prompt instructs AI to reference existing document content."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = "## ICP\n\nMid-market SaaS companies in DACH."
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        # Must contain document awareness section
        assert "DOCUMENT AWARENESS" in prompt
        # Must instruct not to re-ask for existing info
        assert "Never ask the user to repeat information" in prompt
        # Must also include the actual document content
        assert "Mid-market SaaS companies in DACH" in prompt

    def test_document_awareness_present_even_when_empty(self):
        """Document awareness instruction is present even with empty document."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Test"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None

        prompt = build_system_prompt(tenant, doc)
        assert "DOCUMENT AWARENESS" in prompt
        # When empty, should guide user to start filling sections
        assert "proactively guide" in prompt

    def test_no_harsh_language_in_any_prompt_template(self):
        """No prompt template in playbook_service contains harsh language patterns."""
        import inspect
        import api.services.playbook_service as module

        source = inspect.getsource(module)
        # These phrases should only appear inside forbidden-phrase lists (tone rules),
        # not as actual instructions to the AI
        # Check that phrases like "DISQUALIFY:" aren't used as instructions
        # (they appear in the tone rules as things to avoid, which is fine)
        harsh_instructions = [
            "DISQUALIFY:",  # as an instruction (colon = directive)
            "shows no verifiable",
            "has no verifiable",
            "has minimal digital",
            "shows minimal digital",
            "has insufficient",
        ]
        for phrase in harsh_instructions:
            assert phrase not in source, (
                "Found harsh instruction '{}' in playbook_service".format(phrase)
            )


class TestPhaseAwarePrompt:
    def test_default_phase_is_strategy(self):
        """When no phase is provided, uses strategy phase instructions."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None
        doc.phase = "strategy"

        prompt = build_system_prompt(tenant, doc)
        assert "STRATEGY phase" in prompt

    def test_explicit_phase_overrides_document(self):
        """Phase parameter overrides the document's stored phase."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None
        doc.phase = "strategy"

        prompt = build_system_prompt(tenant, doc, phase="contacts")
        assert "CONTACTS phase" in prompt
        assert "STRATEGY phase" not in prompt

    def test_contacts_phase_instructions(self):
        """Contacts phase includes ICP filter and contact selection guidance."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None
        doc.phase = "contacts"

        prompt = build_system_prompt(tenant, doc)
        assert "CONTACTS phase" in prompt
        assert "filter" in prompt.lower() or "select" in prompt.lower()

    def test_messages_phase_instructions(self):
        """Messages phase includes message review guidance."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None
        doc.phase = "messages"

        prompt = build_system_prompt(tenant, doc)
        assert "MESSAGES phase" in prompt

    def test_campaign_phase_instructions(self):
        """Campaign phase includes launch guidance."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None
        doc.phase = "campaign"

        prompt = build_system_prompt(tenant, doc)
        assert "CAMPAIGN phase" in prompt

    def test_all_phases_have_instructions(self):
        """Every phase in PHASE_INSTRUCTIONS produces a non-empty section."""
        from api.services.playbook_service import PHASE_INSTRUCTIONS

        for phase_name, text in PHASE_INSTRUCTIONS.items():
            assert len(text) > 50, f"Phase {phase_name} has insufficient instructions"

    def test_unknown_phase_omits_instructions(self):
        """An unknown phase value does not crash, just omits phase section."""
        from api.services.playbook_service import build_system_prompt
        from unittest.mock import MagicMock

        tenant = MagicMock()
        tenant.name = "Acme"
        doc = MagicMock()
        doc.content = ""
        doc.objective = None
        doc.phase = "nonexistent"

        prompt = build_system_prompt(tenant, doc)
        assert "Phase-Specific Instructions" not in prompt


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


class TestBuildSeededTemplate:
    def test_returns_markdown_string(self):
        """build_seeded_template returns a non-empty markdown string."""
        from api.services.playbook_service import build_seeded_template

        result = build_seeded_template()
        assert isinstance(result, str)
        assert len(result) > 100
        assert "Executive Summary" in result

    def test_includes_all_sections(self):
        """Template contains all strategy sections."""
        from api.services.playbook_service import build_seeded_template

        result = build_seeded_template()
        for section in [
            "Executive Summary",
            "Ideal Customer Profile",
            "Buyer Personas",
            "Value Proposition",
            "Competitive Positioning",
            "Channel Strategy",
            "Messaging Framework",
            "Metrics & KPIs",
            "90-Day Action Plan",
        ]:
            assert section in result, "Missing section: {}".format(section)

    def test_includes_objective(self):
        """Template includes the user's stated objective."""
        from api.services.playbook_service import build_seeded_template

        result = build_seeded_template(objective="Grow enterprise pipeline by 3x")
        assert "Grow enterprise pipeline by 3x" in result

    def test_includes_enrichment_data(self):
        """Template incorporates enrichment data into relevant sections."""
        from api.services.playbook_service import build_seeded_template

        enrichment = {
            "company": {
                "name": "HR Corp",
                "industry": "SaaS",
                "summary": "SaaS platform for HR",
            },
            "company_intel": "SaaS platform for HR",
            "key_products": "Payroll, Benefits, Time Tracking",
            "customer_segments": "Mid-market HR departments",
            "competitors": "Workday, BambooHR, Rippling",
        }

        result = build_seeded_template(
            objective="Win mid-market HR",
            enrichment_data=enrichment,
        )
        assert "SaaS platform for HR" in result
        assert "Payroll" in result
        assert "Mid-market HR departments" in result
        assert "Workday" in result

    def test_works_without_enrichment(self):
        """Template works with objective only (no enrichment data)."""
        from api.services.playbook_service import build_seeded_template

        result = build_seeded_template(objective="Scale outbound")
        assert "Scale outbound" in result
        assert "Executive Summary" in result

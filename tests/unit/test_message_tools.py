"""Tests for the message tools used by the Outreach Agent.

Tests all 5 message tools with mocked DB/LLM:
generate_message, list_messages, update_message,
get_message_templates, generate_variants.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


from api.services.tool_registry import ToolContext
from api.tools.message_tools import (
    MESSAGE_TEMPLATES,
    MESSAGE_TOOLS,
    generate_message,
    generate_variants,
    get_message_templates,
    list_messages,
    update_message,
)

TENANT_ID = "8f7d2027-3e09-4db7-b607-6c1424038a54"
USER_ID = "user-001"
CONTACT_ID = str(uuid.uuid4())
MESSAGE_ID = str(uuid.uuid4())


def _make_ctx() -> ToolContext:
    return ToolContext(tenant_id=TENANT_ID, user_id=USER_ID)


def _mock_contact(contact_id=CONTACT_ID, with_company=True):
    """Create a mock Contact object."""
    contact = MagicMock()
    contact.id = contact_id
    contact.first_name = "Jane"
    contact.last_name = "Smith"
    contact.full_name = "Jane Smith"
    contact.job_title = "VP of Engineering"
    contact.email_address = "jane@example.com"
    contact.linkedin_url = "https://linkedin.com/in/janesmith"
    contact.seniority_level = "VP"
    contact.department = "Engineering"
    contact.company_id = "comp-001" if with_company else None
    return contact


def _mock_company():
    """Create a mock Company object."""
    company = MagicMock()
    company.name = "Acme Corp"
    company.domain = "acme.com"
    company.industry = "SaaS"
    company.employee_count = 150
    company.description = "B2B SaaS platform"
    return company


def _mock_message(message_id=MESSAGE_ID, status="draft"):
    """Create a mock Message object."""
    msg = MagicMock()
    msg.id = message_id
    msg.tenant_id = TENANT_ID
    msg.contact_id = CONTACT_ID
    msg.channel = "linkedin"
    msg.subject = None
    msg.body = "Hi Jane — great work at Acme Corp."
    msg.status = status
    msg.tone = "professional"
    msg.variant = "a"
    msg.language = "en"
    msg.original_body = None
    msg.original_subject = None
    msg.owner_id = None
    msg.tag_id = None
    msg.sequence_step = 1
    msg.variant_group = None
    msg.variant_angle = None
    msg.approved_at = None
    msg.review_notes = None
    msg.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    msg.updated_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    return msg


# ---------------------------------------------------------------------------
# generate_message
# ---------------------------------------------------------------------------


class TestGenerateMessage:
    """Tests for generate_message tool."""

    def test_requires_contact_id(self):
        """Should return error when contact_id is missing."""
        result = generate_message({}, _make_ctx())
        assert "error" in result
        assert "contact_id" in result["error"]

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Company")
    @patch("api.tools.message_tools.Contact")
    def test_returns_error_for_missing_contact(
        self, mock_contact_cls, mock_company_cls, mock_db
    ):
        """Should return error when contact is not found."""
        mock_contact_cls.query.filter_by.return_value.first.return_value = None

        result = generate_message({"contact_id": "nonexistent"}, _make_ctx())
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Company")
    @patch("api.tools.message_tools.Contact")
    def test_generates_linkedin_message(
        self, mock_contact_cls, mock_company_cls, mock_db
    ):
        """Should generate a LinkedIn message for a valid contact."""
        mock_contact_cls.query.filter_by.return_value.first.return_value = (
            _mock_contact()
        )
        mock_company_cls.query.filter_by.return_value.first.return_value = (
            _mock_company()
        )

        result = generate_message(
            {"contact_id": CONTACT_ID, "channel": "linkedin"}, _make_ctx()
        )

        assert "error" not in result
        assert result["channel"] == "linkedin"
        assert result["status"] == "draft"
        assert result["contact_id"] == CONTACT_ID
        assert "Jane" in result["body"]
        assert "Acme Corp" in result["body"]
        assert result["id"] is not None
        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called_once()

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Company")
    @patch("api.tools.message_tools.Contact")
    def test_generates_email_message(self, mock_contact_cls, mock_company_cls, mock_db):
        """Should generate an email with subject line."""
        mock_contact_cls.query.filter_by.return_value.first.return_value = (
            _mock_contact()
        )
        mock_company_cls.query.filter_by.return_value.first.return_value = (
            _mock_company()
        )

        result = generate_message(
            {"contact_id": CONTACT_ID, "channel": "email"}, _make_ctx()
        )

        assert result["channel"] == "email"
        assert result["subject"] is not None
        assert "Acme Corp" in result["subject"]

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Company")
    @patch("api.tools.message_tools.Contact")
    def test_uses_template_framework(self, mock_contact_cls, mock_company_cls, mock_db):
        """Should incorporate template when specified."""
        mock_contact_cls.query.filter_by.return_value.first.return_value = (
            _mock_contact()
        )
        mock_company_cls.query.filter_by.return_value.first.return_value = (
            _mock_company()
        )

        result = generate_message(
            {
                "contact_id": CONTACT_ID,
                "channel": "email",
                "template": "pain_point",
            },
            _make_ctx(),
        )

        assert result["template_used"] == "pain_point"

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Company")
    @patch("api.tools.message_tools.Contact")
    def test_casual_tone(self, mock_contact_cls, mock_company_cls, mock_db):
        """Should adjust greeting for casual tone."""
        mock_contact_cls.query.filter_by.return_value.first.return_value = (
            _mock_contact()
        )
        mock_company_cls.query.filter_by.return_value.first.return_value = (
            _mock_company()
        )

        result = generate_message(
            {"contact_id": CONTACT_ID, "channel": "email", "tone": "casual"},
            _make_ctx(),
        )

        assert result["tone"] == "casual"
        assert "Hey Jane" in result["body"]

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Contact")
    def test_contact_without_company(self, mock_contact_cls, mock_db):
        """Should handle contacts without a linked company."""
        contact = _mock_contact(with_company=False)
        mock_contact_cls.query.filter_by.return_value.first.return_value = contact

        result = generate_message({"contact_id": CONTACT_ID}, _make_ctx())

        assert "error" not in result
        assert result["status"] == "draft"


# ---------------------------------------------------------------------------
# list_messages
# ---------------------------------------------------------------------------


class TestListMessages:
    """Tests for list_messages tool."""

    @patch("api.tools.message_tools.Message")
    def test_lists_messages_for_contact(self, mock_msg_cls):
        """Should filter by contact_id and tenant_id."""
        mock_msg = _mock_message()
        query = MagicMock()
        mock_msg_cls.query.filter_by.return_value = query
        query.filter_by.return_value = query
        query.order_by.return_value = query
        query.count.return_value = 1
        query.limit.return_value.all.return_value = [mock_msg]

        result = list_messages({"contact_id": CONTACT_ID}, _make_ctx())

        assert result["total"] == 1
        assert len(result["messages"]) == 1
        assert result["messages"][0]["id"] == MESSAGE_ID

    @patch("api.tools.message_tools.Message")
    def test_limits_results(self, mock_msg_cls):
        """Should respect the limit parameter (max 50)."""
        query = MagicMock()
        mock_msg_cls.query.filter_by.return_value = query
        query.order_by.return_value = query
        query.count.return_value = 0
        query.limit.return_value.all.return_value = []

        list_messages({"limit": 100}, _make_ctx())

        # Should cap at 50
        query.limit.assert_called_with(50)

    @patch("api.tools.message_tools.Message")
    def test_filters_by_status(self, mock_msg_cls):
        """Should filter by status when provided."""
        query = MagicMock()
        mock_msg_cls.query.filter_by.return_value = query
        query.filter_by.return_value = query
        query.order_by.return_value = query
        query.count.return_value = 0
        query.limit.return_value.all.return_value = []

        list_messages({"status": "approved"}, _make_ctx())

        # Should have called filter_by with status
        query.filter_by.assert_called_with(status="approved")

    @patch("api.tools.message_tools.Message")
    def test_truncates_long_bodies(self, mock_msg_cls):
        """Should truncate message bodies over 200 chars."""
        mock_msg = _mock_message()
        mock_msg.body = "x" * 300
        query = MagicMock()
        mock_msg_cls.query.filter_by.return_value = query
        query.order_by.return_value = query
        query.count.return_value = 1
        query.limit.return_value.all.return_value = [mock_msg]

        result = list_messages({}, _make_ctx())

        body = result["messages"][0]["body"]
        assert len(body) < 300
        assert body.endswith("...")


# ---------------------------------------------------------------------------
# update_message
# ---------------------------------------------------------------------------


class TestUpdateMessage:
    """Tests for update_message tool."""

    def test_requires_message_id(self):
        """Should return error when message_id is missing."""
        result = update_message({}, _make_ctx())
        assert "error" in result

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_returns_error_for_missing_message(self, mock_msg_cls, mock_db):
        """Should return error when message is not found."""
        mock_msg_cls.query.filter_by.return_value.first.return_value = None

        result = update_message({"message_id": "nonexistent"}, _make_ctx())
        assert "error" in result

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_updates_body(self, mock_msg_cls, mock_db):
        """Should update message body and track original."""
        mock_msg = _mock_message()
        mock_msg_cls.query.filter_by.return_value.first.return_value = mock_msg

        result = update_message(
            {"message_id": MESSAGE_ID, "body": "New body text"}, _make_ctx()
        )

        assert "body" in result["updated_fields"]
        assert mock_msg.body == "New body text"
        assert mock_msg.original_body == "Hi Jane — great work at Acme Corp."
        mock_db.session.commit.assert_called_once()

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_approves_message(self, mock_msg_cls, mock_db):
        """Should set status to approved and record timestamp."""
        mock_msg = _mock_message()
        mock_msg_cls.query.filter_by.return_value.first.return_value = mock_msg

        result = update_message(
            {"message_id": MESSAGE_ID, "status": "approved"}, _make_ctx()
        )

        assert "status" in result["updated_fields"]
        assert mock_msg.status == "approved"
        assert mock_msg.approved_at is not None

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_rejects_invalid_status(self, mock_msg_cls, mock_db):
        """Should ignore invalid status values."""
        mock_msg = _mock_message()
        mock_msg_cls.query.filter_by.return_value.first.return_value = mock_msg

        result = update_message(
            {"message_id": MESSAGE_ID, "status": "invalid_status"}, _make_ctx()
        )

        assert "status" not in result["updated_fields"]
        assert mock_msg.status == "draft"

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_updates_multiple_fields(self, mock_msg_cls, mock_db):
        """Should update multiple fields in one call."""
        mock_msg = _mock_message()
        mock_msg_cls.query.filter_by.return_value.first.return_value = mock_msg

        result = update_message(
            {
                "message_id": MESSAGE_ID,
                "body": "Updated body",
                "tone": "casual",
                "review_notes": "Looks good",
            },
            _make_ctx(),
        )

        assert set(result["updated_fields"]) == {"body", "tone", "review_notes"}


# ---------------------------------------------------------------------------
# get_message_templates
# ---------------------------------------------------------------------------


class TestGetMessageTemplates:
    """Tests for get_message_templates tool."""

    def test_returns_all_templates(self):
        """Should return the full list of message templates."""
        result = get_message_templates({}, _make_ctx())

        assert "templates" in result
        assert len(result["templates"]) == len(MESSAGE_TEMPLATES)

    def test_templates_have_required_fields(self):
        """Each template should have id, name, description, structure, best_for."""
        result = get_message_templates({}, _make_ctx())

        for template in result["templates"]:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "structure" in template
            assert "best_for" in template

    def test_known_templates_present(self):
        """Should include the standard template frameworks."""
        result = get_message_templates({}, _make_ctx())
        template_ids = {t["id"] for t in result["templates"]}

        assert "pain_point" in template_ids
        assert "mutual_connection" in template_ids
        assert "insight_led" in template_ids
        assert "trigger_event" in template_ids
        assert "value_first" in template_ids


# ---------------------------------------------------------------------------
# generate_variants
# ---------------------------------------------------------------------------


class TestGenerateVariants:
    """Tests for generate_variants tool."""

    def test_requires_message_id(self):
        """Should return error when message_id is missing."""
        result = generate_variants({}, _make_ctx())
        assert "error" in result

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_returns_error_for_missing_message(self, mock_msg_cls, mock_db):
        """Should return error when original message is not found."""
        mock_msg_cls.query.filter_by.return_value.first.return_value = None

        result = generate_variants({"message_id": "nonexistent"}, _make_ctx())
        assert "error" in result

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_creates_variant(self, mock_msg_cls, mock_db):
        """Should create a variant message linked to the original."""
        original = _mock_message()
        mock_msg_cls.query.filter_by.return_value.first.return_value = original

        # Mock count of existing variants
        variant_query = MagicMock()
        mock_msg_cls.query.filter_by.return_value.filter.return_value = variant_query
        variant_query.count.return_value = 1  # original is 'a', so variant will be 'b'

        result = generate_variants(
            {"message_id": MESSAGE_ID, "angle": "focus on ROI"}, _make_ctx()
        )

        assert "error" not in result
        assert result["variant"] == "b"
        assert result["angle"] == "focus on ROI"
        assert result["original_message_id"] == MESSAGE_ID
        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called_once()

    @patch("api.tools.message_tools.db")
    @patch("api.tools.message_tools.Message")
    def test_variant_preserves_channel(self, mock_msg_cls, mock_db):
        """Should preserve the original message's channel."""
        original = _mock_message()
        original.channel = "email"
        mock_msg_cls.query.filter_by.return_value.first.return_value = original

        variant_query = MagicMock()
        mock_msg_cls.query.filter_by.return_value.filter.return_value = variant_query
        variant_query.count.return_value = 1

        result = generate_variants(
            {"message_id": MESSAGE_ID, "angle": "social proof"}, _make_ctx()
        )

        assert result["channel"] == "email"


# ---------------------------------------------------------------------------
# Tool registry definitions
# ---------------------------------------------------------------------------


class TestMessageToolDefinitions:
    """Tests for MESSAGE_TOOLS registry list."""

    def test_five_tools_defined(self):
        """Should define exactly 5 tools."""
        assert len(MESSAGE_TOOLS) == 5

    def test_all_tools_have_handlers(self):
        """Every tool should have a callable handler."""
        for tool in MESSAGE_TOOLS:
            assert callable(tool.handler)

    def test_all_tools_have_input_schema(self):
        """Every tool should have a valid JSON schema."""
        for tool in MESSAGE_TOOLS:
            assert isinstance(tool.input_schema, dict)
            assert tool.input_schema.get("type") == "object"

    def test_tool_names_match_allowlist(self):
        """Tool names should match the OUTREACH_TOOL_NAMES allowlist."""
        tool_names = {t.name for t in MESSAGE_TOOLS}
        expected = {
            "generate_message",
            "list_messages",
            "update_message",
            "get_message_templates",
            "generate_variants",
        }
        assert tool_names == expected

    def test_generate_message_requires_contact_id(self):
        """generate_message should require contact_id."""
        tool = next(t for t in MESSAGE_TOOLS if t.name == "generate_message")
        assert "contact_id" in tool.input_schema.get("required", [])

    def test_update_message_requires_message_id(self):
        """update_message should require message_id."""
        tool = next(t for t in MESSAGE_TOOLS if t.name == "update_message")
        assert "message_id" in tool.input_schema.get("required", [])

    def test_generate_variants_requires_message_id(self):
        """generate_variants should require message_id."""
        tool = next(t for t in MESSAGE_TOOLS if t.name == "generate_variants")
        assert "message_id" in tool.input_schema.get("required", [])

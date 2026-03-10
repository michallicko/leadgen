"""Tests for AG-UI event extensions — halt gates, document edit, generative UI."""

import json

from api.agents.events import (
    CUSTOM_DOCUMENT_EDIT,
    CUSTOM_GENERATIVE_UI,
    CUSTOM_HALT_GATE_REQUEST,
    CUSTOM_HALT_GATE_RESPONSE,
    document_edit,
    generative_ui_component,
    halt_gate_request,
    halt_gate_response,
    sse_to_agui,
)


class TestHaltGateEvents:
    """Test halt gate AG-UI events."""

    def test_halt_gate_request(self):
        event = halt_gate_request(
            gate_id="g-123",
            gate_type="scope",
            question="Which product?",
            options=[
                {"label": "Product A", "value": "a", "description": "Main product"},
            ],
            context="Company has multiple products",
            metadata={"estimatedTokens": 5000},
        )

        assert event.type == CUSTOM_HALT_GATE_REQUEST
        assert event.data["gateId"] == "g-123"
        assert event.data["gateType"] == "scope"
        assert event.data["question"] == "Which product?"
        assert len(event.data["options"]) == 1
        assert event.data["metadata"]["estimatedTokens"] == 5000

    def test_halt_gate_request_sse_format(self):
        event = halt_gate_request(
            gate_id="g-1",
            gate_type="direction",
            question="Broad or narrow?",
            options=[{"label": "Broad", "value": "broad"}],
            context="Two segments found",
        )

        sse = event.to_sse()
        assert sse.startswith("data: ")
        parsed = json.loads(sse.replace("data: ", "").strip())
        assert parsed["type"] == "CUSTOM:halt_gate_request"
        assert parsed["gateId"] == "g-1"

    def test_halt_gate_response(self):
        event = halt_gate_response(
            gate_id="g-123",
            choice="approve",
            custom_input="focus on enterprise",
        )

        assert event.type == CUSTOM_HALT_GATE_RESPONSE
        assert event.data["gateId"] == "g-123"
        assert event.data["choice"] == "approve"
        assert event.data["customInput"] == "focus on enterprise"


class TestDocumentEditEvents:
    """Test document edit AG-UI events."""

    def test_document_edit_insert(self):
        event = document_edit(
            section="Executive Summary",
            operation="insert",
            content="New paragraph content",
            position="end",
            edit_id="edit-1",
        )

        assert event.type == CUSTOM_DOCUMENT_EDIT
        assert event.data["editId"] == "edit-1"
        assert event.data["section"] == "Executive Summary"
        assert event.data["operation"] == "insert"
        assert event.data["content"] == "New paragraph content"
        assert event.data["position"] == "end"

    def test_document_edit_auto_id(self):
        event = document_edit(
            section="ICP Tiers",
            operation="replace",
            content="Updated tiers",
        )

        assert event.data["editId"]  # Should have auto-generated ID
        assert len(event.data["editId"]) > 0

    def test_document_edit_delete(self):
        event = document_edit(
            section="Positioning",
            operation="delete",
        )

        assert event.data["operation"] == "delete"
        assert event.data["content"] == ""


class TestGenerativeUIEvents:
    """Test generative UI AG-UI events."""

    def test_add_component(self):
        event = generative_ui_component(
            component_type="data_table",
            component_id="table-1",
            props={
                "title": "Competitor Analysis",
                "columns": [{"key": "name", "label": "Name"}],
                "rows": [{"name": "Acme"}],
            },
            action="add",
        )

        assert event.type == CUSTOM_GENERATIVE_UI
        assert event.data["componentType"] == "data_table"
        assert event.data["componentId"] == "table-1"
        assert event.data["action"] == "add"
        assert event.data["props"]["title"] == "Competitor Analysis"

    def test_update_component(self):
        event = generative_ui_component(
            component_type="progress_card",
            component_id="pc-1",
            props={"progress": 75},
            action="update",
        )

        assert event.data["action"] == "update"

    def test_remove_component(self):
        event = generative_ui_component(
            component_type="progress_card",
            component_id="pc-1",
            props={},
            action="remove",
        )

        assert event.data["action"] == "remove"


class TestSseToAguiMapping:
    """Test sse_to_agui mapping for new event types."""

    def test_halt_gate_request_mapping(self):
        events = sse_to_agui(
            "halt_gate_request",
            {
                "gate_id": "g-1",
                "gate_type": "scope",
                "question": "Which product?",
                "options": [{"label": "A", "value": "a"}],
                "context": "Multiple products",
                "metadata": {},
            },
        )

        assert len(events) == 1
        assert events[0].type == CUSTOM_HALT_GATE_REQUEST
        assert events[0].data["gateId"] == "g-1"

    def test_document_edit_mapping(self):
        events = sse_to_agui(
            "document_edit",
            {
                "edit_id": "e-1",
                "section": "Summary",
                "operation": "insert",
                "content": "New content",
                "position": "end",
            },
        )

        assert len(events) == 1
        assert events[0].type == CUSTOM_DOCUMENT_EDIT
        assert events[0].data["editId"] == "e-1"

    def test_generative_ui_mapping(self):
        events = sse_to_agui(
            "generative_ui",
            {
                "component_type": "data_table",
                "component_id": "t-1",
                "props": {"title": "Test"},
                "action": "add",
            },
        )

        assert len(events) == 1
        assert events[0].type == CUSTOM_GENERATIVE_UI
        assert events[0].data["componentType"] == "data_table"

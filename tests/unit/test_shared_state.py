"""Tests for shared state module — snapshot/delta generation and JSON Patch."""

from api.agents.shared_state import (
    AgentSharedState,
    SharedStateManager,
    apply_json_patch,
    generate_json_patch,
)


class TestAgentSharedState:
    """Test AgentSharedState serialization."""

    def test_default_state(self):
        state = AgentSharedState()
        d = state.to_dict()
        assert d["currentPhase"] == "strategy"
        assert d["activeSection"] is None
        assert d["docCompleteness"] == {}
        assert d["enrichmentStatus"] == "idle"
        assert d["contextSummary"] == ""
        assert d["haltGatesPending"] == []
        assert d["components"] == []

    def test_custom_state(self):
        state = AgentSharedState(
            current_phase="contacts",
            active_section="ICP Tiers",
            doc_completeness={"executive_summary": 100, "icp_tiers": 50},
            enrichment_status="running",
            context_summary="Researching acme.com",
        )
        d = state.to_dict()
        assert d["currentPhase"] == "contacts"
        assert d["activeSection"] == "ICP Tiers"
        assert d["docCompleteness"]["executive_summary"] == 100

    def test_from_dict_roundtrip(self):
        original = AgentSharedState(
            current_phase="messages",
            active_section="Messaging",
            doc_completeness={"messaging": 75},
        )
        d = original.to_dict()
        restored = AgentSharedState.from_dict(d)
        assert restored.current_phase == "messages"
        assert restored.active_section == "Messaging"
        assert restored.doc_completeness["messaging"] == 75

    def test_from_dict_with_missing_keys(self):
        state = AgentSharedState.from_dict({})
        assert state.current_phase == "strategy"
        assert state.active_section is None


class TestGenerateJsonPatch:
    """Test RFC 6902 JSON Patch generation."""

    def test_no_changes(self):
        old = {"a": 1, "b": "hello"}
        new = {"a": 1, "b": "hello"}
        ops = generate_json_patch(old, new)
        assert ops == []

    def test_replace_value(self):
        old = {"a": 1}
        new = {"a": 2}
        ops = generate_json_patch(old, new)
        assert len(ops) == 1
        assert ops[0] == {"op": "replace", "path": "/a", "value": 2}

    def test_add_key(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        ops = generate_json_patch(old, new)
        assert len(ops) == 1
        assert ops[0] == {"op": "replace", "path": "/b", "value": 2}

    def test_remove_key(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        ops = generate_json_patch(old, new)
        assert len(ops) == 1
        assert ops[0] == {"op": "remove", "path": "/b"}

    def test_multiple_changes(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 10, "b": 2, "d": 4}
        ops = generate_json_patch(old, new)

        ops_by_path = {op["path"]: op for op in ops}

        assert ops_by_path["/a"] == {"op": "replace", "path": "/a", "value": 10}
        assert ops_by_path["/c"] == {"op": "remove", "path": "/c"}
        assert ops_by_path["/d"] == {"op": "replace", "path": "/d", "value": 4}

    def test_nested_object_change(self):
        old = {"nested": {"x": 1, "y": 2}}
        new = {"nested": {"x": 1, "y": 3}}
        ops = generate_json_patch(old, new)
        assert len(ops) == 1
        assert ops[0]["path"] == "/nested"
        assert ops[0]["value"] == {"x": 1, "y": 3}


class TestApplyJsonPatch:
    """Test JSON Patch application."""

    def test_replace(self):
        state = {"a": 1, "b": 2}
        ops = [{"op": "replace", "path": "/a", "value": 10}]
        result = apply_json_patch(state, ops)
        assert result["a"] == 10
        assert result["b"] == 2
        # Original not mutated
        assert state["a"] == 1

    def test_add(self):
        state = {"a": 1}
        ops = [{"op": "add", "path": "/b", "value": 2}]
        result = apply_json_patch(state, ops)
        assert result["b"] == 2

    def test_remove(self):
        state = {"a": 1, "b": 2}
        ops = [{"op": "remove", "path": "/b"}]
        result = apply_json_patch(state, ops)
        assert "b" not in result
        assert result["a"] == 1

    def test_multiple_operations(self):
        state = {"a": 1, "b": 2, "c": 3}
        ops = [
            {"op": "replace", "path": "/a", "value": 10},
            {"op": "remove", "path": "/c"},
            {"op": "add", "path": "/d", "value": 4},
        ]
        result = apply_json_patch(state, ops)
        assert result == {"a": 10, "b": 2, "d": 4}

    def test_empty_operations(self):
        state = {"a": 1}
        result = apply_json_patch(state, [])
        assert result == {"a": 1}

    def test_remove_nonexistent_key(self):
        state = {"a": 1}
        ops = [{"op": "remove", "path": "/b"}]
        result = apply_json_patch(state, ops)
        assert result == {"a": 1}


class TestSharedStateManager:
    """Test SharedStateManager lifecycle."""

    def test_initial_snapshot(self):
        mgr = SharedStateManager()
        snapshot = mgr.get_snapshot()
        assert snapshot["currentPhase"] == "strategy"
        assert snapshot["enrichmentStatus"] == "idle"

    def test_update_returns_delta(self):
        mgr = SharedStateManager()
        mgr.get_snapshot()  # Reset baseline

        delta = mgr.update(current_phase="contacts")
        assert len(delta) == 1
        assert delta[0]["path"] == "/currentPhase"
        assert delta[0]["value"] == "contacts"

    def test_update_no_changes_returns_empty(self):
        mgr = SharedStateManager()
        mgr.get_snapshot()

        delta = mgr.update(current_phase="strategy")  # Same as default
        assert delta == []

    def test_camel_case_keys(self):
        mgr = SharedStateManager()
        mgr.get_snapshot()

        delta = mgr.update(currentPhase="messages")
        assert len(delta) == 1
        assert delta[0]["value"] == "messages"

    def test_multiple_updates(self):
        mgr = SharedStateManager()
        mgr.get_snapshot()

        delta1 = mgr.update(current_phase="contacts")
        assert len(delta1) == 1

        delta2 = mgr.update(active_section="ICP Tiers")
        assert len(delta2) == 1
        assert delta2[0]["path"] == "/activeSection"

    def test_add_component(self):
        mgr = SharedStateManager()
        mgr.get_snapshot()

        delta = mgr.add_component(
            component_type="progress_card",
            component_id="pc-1",
            props={"title": "Research", "progress": 50, "status": "Running"},
        )
        assert len(delta) >= 1

        snapshot = mgr.get_snapshot()
        assert len(snapshot["components"]) == 1
        assert snapshot["components"][0]["id"] == "pc-1"
        assert snapshot["components"][0]["type"] == "progress_card"

    def test_update_component(self):
        mgr = SharedStateManager()
        mgr.add_component("progress_card", "pc-1", {"progress": 50})
        mgr.get_snapshot()

        delta = mgr.update_component("pc-1", {"progress": 75})
        assert len(delta) >= 1

        snapshot = mgr.get_snapshot()
        assert snapshot["components"][0]["props"]["progress"] == 75

    def test_remove_component(self):
        mgr = SharedStateManager()
        mgr.add_component("progress_card", "pc-1", {"progress": 50})
        mgr.get_snapshot()

        delta = mgr.remove_component("pc-1")
        assert len(delta) >= 1

        snapshot = mgr.get_snapshot()
        assert len(snapshot["components"]) == 0

    def test_snapshot_resets_baseline(self):
        mgr = SharedStateManager()
        mgr.update(current_phase="contacts")

        # Snapshot resets the baseline
        mgr.get_snapshot()

        # Same state, so no delta
        delta = mgr.update(current_phase="contacts")
        assert delta == []

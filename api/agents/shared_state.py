"""Shared state synchronization between agent and frontend.

Manages a per-thread state object that is synchronized via AG-UI events:
  - STATE_SNAPSHOT: Full state sent on connect/reconnect
  - STATE_DELTA: Incremental JSON Patch (RFC 6902) updates

The shared state contains:
  - current_phase: Active workflow phase (strategy, contacts, messages, campaign)
  - active_section: Which strategy section the agent is currently working on
  - doc_completeness: Per-section completion percentages
  - enrichment_status: Current enrichment pipeline state
  - context_summary: Brief text summary of what the agent knows/has done
  - halt_gates_pending: List of pending halt gate IDs
  - components: Active generative UI components
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentSharedState:
    """State synchronized between agent backend and frontend.

    All fields are serializable to JSON for AG-UI transport.
    """

    current_phase: str = "strategy"
    active_section: Optional[str] = None
    doc_completeness: dict[str, int] = field(default_factory=dict)
    enrichment_status: str = "idle"
    context_summary: str = ""
    halt_gates_pending: list[str] = field(default_factory=list)
    components: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for STATE_SNAPSHOT."""
        return {
            "currentPhase": self.current_phase,
            "activeSection": self.active_section,
            "docCompleteness": self.doc_completeness,
            "enrichmentStatus": self.enrichment_status,
            "contextSummary": self.context_summary,
            "haltGatesPending": self.halt_gates_pending,
            "components": self.components,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSharedState":
        """Deserialize from dict."""
        return cls(
            current_phase=data.get("currentPhase", "strategy"),
            active_section=data.get("activeSection"),
            doc_completeness=data.get("docCompleteness", {}),
            enrichment_status=data.get("enrichmentStatus", "idle"),
            context_summary=data.get("contextSummary", ""),
            halt_gates_pending=data.get("haltGatesPending", []),
            components=data.get("components", []),
        )


def generate_json_patch(
    old_state: dict[str, Any], new_state: dict[str, Any]
) -> list[dict[str, Any]]:
    """Generate RFC 6902 JSON Patch operations between two state dicts.

    Only generates top-level replace operations for simplicity.
    Nested diffs are handled by replacing the entire top-level key.

    Args:
        old_state: Previous state dict.
        new_state: Updated state dict.

    Returns:
        List of JSON Patch operations: [{op, path, value}, ...]
    """
    operations: list[dict[str, Any]] = []

    # Find changed or added keys
    for key, new_value in new_state.items():
        old_value = old_state.get(key)
        if old_value != new_value:
            operations.append(
                {
                    "op": "replace",
                    "path": "/{}".format(key),
                    "value": new_value,
                }
            )

    # Find removed keys
    for key in old_state:
        if key not in new_state:
            operations.append(
                {
                    "op": "remove",
                    "path": "/{}".format(key),
                }
            )

    return operations


def apply_json_patch(
    state: dict[str, Any], operations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply RFC 6902 JSON Patch operations to a state dict.

    Supports top-level operations: replace, remove, add.

    Args:
        state: Current state dict (will be deep-copied, not mutated).
        operations: List of JSON Patch operations.

    Returns:
        New state dict with operations applied.
    """
    result = copy.deepcopy(state)

    for op in operations:
        op_type = op.get("op", "")
        path = op.get("path", "")

        # Strip leading slash for top-level key
        key = path.lstrip("/")
        if not key:
            continue

        if op_type in ("replace", "add"):
            result[key] = op.get("value")
        elif op_type == "remove":
            result.pop(key, None)

    return result


class SharedStateManager:
    """Manages shared state per thread with snapshot/delta tracking.

    Maintains the current state and the last-emitted state, so deltas
    can be computed efficiently.
    """

    def __init__(self) -> None:
        self._state = AgentSharedState()
        self._last_emitted: dict[str, Any] = self._state.to_dict()

    @property
    def state(self) -> AgentSharedState:
        """Current shared state."""
        return self._state

    def get_snapshot(self) -> dict[str, Any]:
        """Get a full state snapshot for STATE_SNAPSHOT event.

        Also resets the delta tracking baseline.
        """
        snapshot = self._state.to_dict()
        self._last_emitted = copy.deepcopy(snapshot)
        return snapshot

    def update(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Update state fields and return JSON Patch delta operations.

        Only updates fields that are provided. Returns empty list if
        no changes were made.

        Args:
            **kwargs: Field names and values to update. Use camelCase keys
                matching AgentSharedState.to_dict() output, or snake_case
                matching the dataclass fields.

        Returns:
            List of JSON Patch operations (empty if no changes).
        """
        # Map camelCase to snake_case field names
        field_map = {
            "currentPhase": "current_phase",
            "activeSection": "active_section",
            "docCompleteness": "doc_completeness",
            "enrichmentStatus": "enrichment_status",
            "contextSummary": "context_summary",
            "haltGatesPending": "halt_gates_pending",
            "components": "components",
        }

        for key, value in kwargs.items():
            attr_name = field_map.get(key, key)
            if hasattr(self._state, attr_name):
                setattr(self._state, attr_name, value)

        new_state = self._state.to_dict()
        delta = generate_json_patch(self._last_emitted, new_state)

        if delta:
            self._last_emitted = copy.deepcopy(new_state)

        return delta

    def add_component(
        self, component_type: str, component_id: str, props: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Add a generative UI component to the shared state.

        Args:
            component_type: Type of component (data_table, progress_card, etc.).
            component_id: Unique ID for this component instance.
            props: Component props dict.

        Returns:
            JSON Patch delta operations.
        """
        component = {
            "id": component_id,
            "type": component_type,
            "props": props,
        }
        self._state.components.append(component)
        return self.update()

    def update_component(
        self, component_id: str, props: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Update props of an existing generative UI component.

        Args:
            component_id: ID of the component to update.
            props: New/updated props to merge into existing props.

        Returns:
            JSON Patch delta operations.
        """
        for comp in self._state.components:
            if comp["id"] == component_id:
                comp["props"].update(props)
                break

        return self.update()

    def remove_component(self, component_id: str) -> list[dict[str, Any]]:
        """Remove a generative UI component from the shared state.

        Args:
            component_id: ID of the component to remove.

        Returns:
            JSON Patch delta operations.
        """
        self._state.components = [
            c for c in self._state.components if c["id"] != component_id
        ]
        return self.update()

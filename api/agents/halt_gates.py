"""Adaptive halt gates for agent decision points.

Halt gates pause agent execution at critical decision points using
LangGraph interrupt(). The frontend renders approval UI with options,
and the agent resumes with the user's choice.

Gate types:
  - scope: Multiple valid scopes found (e.g., which product line)
  - direction: Mutually exclusive strategies (e.g., broad or narrow ICP)
  - assumption: AI made a guess it's unsure about
  - review: Major deliverable complete, needs user sign-off
  - resource: Expensive operation ahead, needs cost approval

Frequency levels:
  - always: Halt at every gate
  - major_only: Halt only for scope, direction, and resource gates
  - autonomous: Never halt (agent decides everything)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GateType(str, Enum):
    """Categories of halt gates."""

    SCOPE = "scope"
    DIRECTION = "direction"
    ASSUMPTION = "assumption"
    REVIEW = "review"
    RESOURCE = "resource"


class HaltFrequency(str, Enum):
    """User-configurable halt gate frequency."""

    ALWAYS = "always"
    MAJOR_ONLY = "major_only"
    AUTONOMOUS = "autonomous"


# Gate types considered "major" for the MAJOR_ONLY frequency
MAJOR_GATE_TYPES = {GateType.SCOPE, GateType.DIRECTION, GateType.RESOURCE}


@dataclass
class HaltGateOption:
    """A single option presented to the user at a halt gate."""

    label: str
    value: str
    description: str = ""


@dataclass
class HaltGate:
    """A halt gate definition — represents a pause point in agent execution.

    Attributes:
        gate_id: Unique identifier for this gate instance.
        gate_type: Category of halt gate (scope, direction, etc.).
        question: The question presented to the user.
        options: List of options the user can choose from.
        context: Brief explanation of why this gate matters.
        metadata: Additional data (e.g., token estimates for resource gates).
    """

    gate_type: GateType
    question: str
    options: list[HaltGateOption]
    context: str
    gate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for AG-UI event payload."""
        return {
            "gateId": self.gate_id,
            "gateType": self.gate_type.value,
            "question": self.question,
            "options": [
                {
                    "label": opt.label,
                    "value": opt.value,
                    "description": opt.description,
                }
                for opt in self.options
            ],
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class HaltGateResponse:
    """User's response to a halt gate.

    Attributes:
        gate_id: ID of the gate being responded to.
        choice: The value of the chosen option.
        custom_input: Optional free-text input from the user.
    """

    gate_id: str
    choice: str
    custom_input: Optional[str] = None


@dataclass
class HaltGateConfig:
    """Per-user halt gate configuration.

    Attributes:
        frequency: How often gates should fire.
        disabled_types: Specific gate types to skip regardless of frequency.
    """

    frequency: HaltFrequency = HaltFrequency.ALWAYS
    disabled_types: list[GateType] = field(default_factory=list)

    @classmethod
    def from_preferences(cls, preferences: Optional[dict] = None) -> "HaltGateConfig":
        """Build config from user preferences JSONB column.

        Args:
            preferences: User's preferences dict (may contain halt_gates key).

        Returns:
            HaltGateConfig with user's settings or defaults.
        """
        if not preferences:
            return cls()

        halt_prefs = preferences.get("halt_gates", {})
        frequency_str = halt_prefs.get("frequency", "always")
        disabled = halt_prefs.get("disabled_types", [])

        try:
            frequency = HaltFrequency(frequency_str)
        except ValueError:
            frequency = HaltFrequency.ALWAYS

        disabled_types = []
        for dt in disabled:
            try:
                disabled_types.append(GateType(dt))
            except ValueError:
                pass

        return cls(frequency=frequency, disabled_types=disabled_types)


def should_halt(gate: HaltGate, config: HaltGateConfig) -> bool:
    """Determine whether to fire a halt gate based on user config.

    Args:
        gate: The halt gate to evaluate.
        config: User's halt gate configuration.

    Returns:
        True if the gate should fire (pause execution), False to skip.
    """
    # Never halt in autonomous mode
    if config.frequency == HaltFrequency.AUTONOMOUS:
        return False

    # Skip if this gate type is explicitly disabled
    if gate.gate_type in config.disabled_types:
        return False

    # In major_only mode, only halt for major gate types
    if config.frequency == HaltFrequency.MAJOR_ONLY:
        return gate.gate_type in MAJOR_GATE_TYPES

    # ALWAYS mode — halt at every gate
    return True


# ---------------------------------------------------------------------------
# Gate factory functions — convenience builders for common gate scenarios
# ---------------------------------------------------------------------------


def scope_gate(
    question: str,
    options: list[dict[str, str]],
    context: str,
) -> HaltGate:
    """Create a scope gate (multiple products/business lines found).

    Args:
        question: What to ask the user.
        options: List of dicts with 'label', 'value', and optional 'description'.
        context: Why this choice matters.
    """
    return HaltGate(
        gate_type=GateType.SCOPE,
        question=question,
        options=[
            HaltGateOption(
                label=opt["label"],
                value=opt["value"],
                description=opt.get("description", ""),
            )
            for opt in options
        ],
        context=context,
    )


def direction_gate(
    question: str,
    options: list[dict[str, str]],
    context: str,
) -> HaltGate:
    """Create a direction gate (mutually exclusive strategy paths)."""
    return HaltGate(
        gate_type=GateType.DIRECTION,
        question=question,
        options=[
            HaltGateOption(
                label=opt["label"],
                value=opt["value"],
                description=opt.get("description", ""),
            )
            for opt in options
        ],
        context=context,
    )


def review_gate(
    question: str,
    context: str,
    options: Optional[list[dict[str, str]]] = None,
) -> HaltGate:
    """Create a review gate (major deliverable ready for review).

    Provides default approve/adjust options if none specified.
    """
    if options is None:
        options = [
            {"label": "Looks good, continue", "value": "approve"},
            {"label": "Needs adjustments", "value": "adjust"},
            {"label": "Review full draft", "value": "review_full"},
        ]

    return HaltGate(
        gate_type=GateType.REVIEW,
        question=question,
        options=[
            HaltGateOption(
                label=opt["label"],
                value=opt["value"],
                description=opt.get("description", ""),
            )
            for opt in options
        ],
        context=context,
    )


def resource_gate(
    question: str,
    estimated_tokens: int,
    estimated_cost_usd: str,
    context: str,
) -> HaltGate:
    """Create a resource gate (expensive operation ahead).

    Includes token/cost estimates in metadata for the frontend to display.
    """
    return HaltGate(
        gate_type=GateType.RESOURCE,
        question=question,
        options=[
            HaltGateOption(label="Approve", value="approve"),
            HaltGateOption(label="Skip this step", value="skip"),
            HaltGateOption(label="Cancel", value="cancel"),
        ],
        context=context,
        metadata={
            "estimatedTokens": estimated_tokens,
            "estimatedCostUsd": estimated_cost_usd,
        },
    )

"""Fixture loading and golden conversation format for agent testing.

Golden conversations are JSON files that define expected agent behavior:
- User messages (input)
- Expected tool calls (name, args patterns)
- Expected response patterns (contains, format)
- Assertion levels (strict, semantic, structural)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

# Default fixtures directory
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "fixtures"
    / "agent_conversations"
)

AssertionLevel = Literal["strict", "semantic", "structural"]


@dataclass
class ExpectedToolCall:
    """Expected tool call in a conversation turn."""

    name: str
    args_contains: dict[str, Any] = field(default_factory=dict)
    args_exact: Optional[dict[str, Any]] = None

    def matches(
        self, actual_name: str, actual_args: dict, level: AssertionLevel
    ) -> bool:
        """Check if an actual tool call matches this expectation."""
        if actual_name != self.name:
            return False

        if level == "strict":
            if self.args_exact is not None:
                return actual_args == self.args_exact
            return all(
                k in actual_args and actual_args[k] == v
                for k, v in self.args_contains.items()
            )

        if level == "semantic":
            # Check that key args are present with similar values
            for key, expected_val in self.args_contains.items():
                if key not in actual_args:
                    return False
                actual_val = str(actual_args[key]).lower()
                expected_str = str(expected_val).lower()
                if expected_str not in actual_val:
                    return False
            return True

        # structural: just check tool name matched (already done above)
        return True


@dataclass
class ExpectedResponse:
    """Expected response patterns for a conversation turn."""

    contains: list[str] = field(default_factory=list)
    not_contains: list[str] = field(default_factory=list)
    format: Optional[str] = None  # "markdown", "json", "plain"
    min_length: int = 0
    max_length: int = 0  # 0 = no limit

    def matches(
        self, actual_text: str, level: AssertionLevel
    ) -> tuple[bool, list[str]]:
        """Check if actual response matches expectations.

        Returns:
            Tuple of (passed, list of failure reasons).
        """
        failures: list[str] = []

        if level in ("strict", "semantic"):
            for keyword in self.contains:
                if level == "strict":
                    if keyword not in actual_text:
                        failures.append("Missing exact text: '{}'".format(keyword))
                else:
                    if keyword.lower() not in actual_text.lower():
                        failures.append(
                            "Missing keyword (case-insensitive): '{}'".format(keyword)
                        )

            for keyword in self.not_contains:
                if keyword.lower() in actual_text.lower():
                    failures.append("Contains forbidden text: '{}'".format(keyword))

        if self.format == "markdown" and level != "structural":
            # Basic markdown check: has headers, bullets, or bold
            has_markdown = any(
                marker in actual_text for marker in ["#", "- ", "* ", "**", "```"]
            )
            if not has_markdown:
                failures.append("Expected markdown formatting but none found")

        if self.min_length > 0 and len(actual_text) < self.min_length:
            failures.append(
                "Response too short: {} < {}".format(len(actual_text), self.min_length)
            )

        if self.max_length > 0 and len(actual_text) > self.max_length:
            failures.append(
                "Response too long: {} > {}".format(len(actual_text), self.max_length)
            )

        return (len(failures) == 0, failures)


@dataclass
class ConversationTurn:
    """A single turn in a golden conversation."""

    user_message: str
    expected_tool_calls: list[ExpectedToolCall] = field(default_factory=list)
    expected_response: Optional[ExpectedResponse] = None
    assertion_level: AssertionLevel = "structural"


@dataclass
class GoldenConversation:
    """A complete golden conversation fixture for testing."""

    name: str
    description: str
    model: str
    system_prompt: str
    turns: list[ConversationTurn]
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> GoldenConversation:
        """Parse a golden conversation from a dict (loaded from JSON)."""
        turns = []
        for turn_data in data.get("turns", []):
            tool_calls = [
                ExpectedToolCall(
                    name=tc.get("name", ""),
                    args_contains=tc.get("args_contains", {}),
                    args_exact=tc.get("args_exact"),
                )
                for tc in turn_data.get("expected_tool_calls", [])
            ]

            response_data = turn_data.get("expected_response")
            expected_response = None
            if response_data:
                expected_response = ExpectedResponse(
                    contains=response_data.get("contains", []),
                    not_contains=response_data.get("not_contains", []),
                    format=response_data.get("format"),
                    min_length=response_data.get("min_length", 0),
                    max_length=response_data.get("max_length", 0),
                )

            turns.append(
                ConversationTurn(
                    user_message=turn_data.get("user_message", ""),
                    expected_tool_calls=tool_calls,
                    expected_response=expected_response,
                    assertion_level=turn_data.get("assertion_level", "structural"),
                )
            )

        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            model=data.get("model", "claude-haiku-4-5-20251001"),
            system_prompt=data.get("system_prompt", ""),
            turns=turns,
            tags=data.get("tags", []),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> GoldenConversation:
        """Load a golden conversation from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


def load_fixtures(
    directory: str | Path | None = None,
    tags: list[str] | None = None,
) -> list[GoldenConversation]:
    """Load all golden conversation fixtures from a directory.

    Args:
        directory: Path to fixtures directory. Defaults to FIXTURES_DIR.
        tags: Optional tag filter. Only return fixtures matching any tag.

    Returns:
        List of GoldenConversation objects.
    """
    fixtures_dir = Path(directory) if directory else FIXTURES_DIR

    if not fixtures_dir.exists():
        return []

    conversations = []
    for json_file in sorted(fixtures_dir.glob("*.json")):
        try:
            conv = GoldenConversation.from_file(json_file)
            if tags:
                if any(t in conv.tags for t in tags):
                    conversations.append(conv)
            else:
                conversations.append(conv)
        except (json.JSONDecodeError, KeyError) as exc:
            # Skip malformed fixtures with a warning
            import logging

            logging.getLogger(__name__).warning(
                "Skipping malformed fixture %s: %s", json_file, exc
            )

    return conversations

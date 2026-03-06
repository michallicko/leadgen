"""Test runner, snapshot comparison, and quality scoring for agent testing.

Provides the core framework for replaying golden conversations against
the agent and generating regression reports.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .fixtures import (
    AssertionLevel,
    ConversationTurn,
    ExpectedToolCall,
    GoldenConversation,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolCallResult:
    """Result of comparing an expected tool call against actual calls."""

    expected_name: str
    matched: bool
    actual_name: Optional[str] = None
    actual_args: Optional[dict] = None
    reason: str = ""


@dataclass
class TurnResult:
    """Result of evaluating a single conversation turn."""

    turn_index: int
    user_message: str
    assertion_level: AssertionLevel
    tool_call_results: list[ToolCallResult] = field(default_factory=list)
    response_passed: bool = True
    response_failures: list[str] = field(default_factory=list)
    actual_response_text: str = ""
    actual_tool_calls: list[dict] = field(default_factory=list)
    quality_scores: dict[str, float] = field(default_factory=dict)
    duration_ms: int = 0

    @property
    def passed(self) -> bool:
        """Whether this turn passed all assertions."""
        tools_passed = all(tc.matched for tc in self.tool_call_results)
        return tools_passed and self.response_passed


@dataclass
class ConversationResult:
    """Result of replaying a complete golden conversation."""

    name: str
    description: str
    turn_results: list[TurnResult] = field(default_factory=list)
    total_duration_ms: int = 0
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        """Whether all turns passed."""
        if self.error:
            return False
        return all(tr.passed for tr in self.turn_results)

    @property
    def pass_rate(self) -> float:
        """Fraction of turns that passed."""
        if not self.turn_results:
            return 0.0
        passed = sum(1 for tr in self.turn_results if tr.passed)
        return passed / len(self.turn_results)


@dataclass
class TestReport:
    """Summary report across all conversations."""

    results: list[ConversationResult] = field(default_factory=list)
    total_conversations: int = 0
    passed_conversations: int = 0
    failed_conversations: int = 0
    total_turns: int = 0
    passed_turns: int = 0
    regressions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dict."""
        return {
            "summary": {
                "total_conversations": self.total_conversations,
                "passed_conversations": self.passed_conversations,
                "failed_conversations": self.failed_conversations,
                "total_turns": self.total_turns,
                "passed_turns": self.passed_turns,
                "pass_rate": (
                    self.passed_turns / self.total_turns if self.total_turns else 0
                ),
            },
            "regressions": self.regressions,
            "conversations": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "pass_rate": r.pass_rate,
                    "turns": [
                        {
                            "index": tr.turn_index,
                            "passed": tr.passed,
                            "tool_calls": [
                                {
                                    "expected": tc.expected_name,
                                    "matched": tc.matched,
                                    "reason": tc.reason,
                                }
                                for tc in tr.tool_call_results
                            ],
                            "response_failures": tr.response_failures,
                            "quality_scores": tr.quality_scores,
                        }
                        for tr in r.turn_results
                    ],
                    "error": r.error,
                }
                for r in self.results
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------


def compute_quality_scores(
    actual_text: str,
    expected_keywords: list[str] | None = None,
) -> dict[str, float]:
    """Compute quality metrics for an agent response.

    Scores are 0.0 to 1.0.

    Metrics:
        - relevance: fraction of expected keywords found in response
        - completeness: based on response length and structure
        - conciseness: penalizes overly long responses
    """
    scores: dict[str, float] = {}

    # Relevance: keyword coverage
    if expected_keywords:
        found = sum(1 for kw in expected_keywords if kw.lower() in actual_text.lower())
        scores["relevance"] = found / len(expected_keywords)
    else:
        scores["relevance"] = 1.0  # No keywords to check

    # Completeness: based on response having substance
    word_count = len(actual_text.split())
    if word_count == 0:
        scores["completeness"] = 0.0
    elif word_count < 5:
        scores["completeness"] = 0.3
    elif word_count < 20:
        scores["completeness"] = 0.6
    else:
        scores["completeness"] = 1.0

    # Conciseness: penalize very long responses (>500 words)
    if word_count <= 150:
        scores["conciseness"] = 1.0
    elif word_count <= 400:
        scores["conciseness"] = 0.7
    else:
        scores["conciseness"] = 0.4

    return scores


# ---------------------------------------------------------------------------
# Turn evaluation
# ---------------------------------------------------------------------------


def evaluate_tool_calls(
    expected: list[ExpectedToolCall],
    actual: list[dict],
    level: AssertionLevel,
) -> list[ToolCallResult]:
    """Compare expected tool calls against actual ones.

    Args:
        expected: List of expected tool call specs.
        actual: List of actual tool call dicts with 'name' and 'args' keys.
        level: Assertion strictness level.

    Returns:
        List of ToolCallResult for each expected tool call.
    """
    results = []
    used_indices: set[int] = set()

    for exp in expected:
        matched = False
        matched_actual = None

        for i, act in enumerate(actual):
            if i in used_indices:
                continue
            act_name = act.get("name", act.get("tool_name", ""))
            act_args = act.get("args", act.get("input", {}))
            if exp.matches(act_name, act_args, level):
                matched = True
                matched_actual = act
                used_indices.add(i)
                break

        if matched and matched_actual is not None:
            results.append(
                ToolCallResult(
                    expected_name=exp.name,
                    matched=True,
                    actual_name=matched_actual.get(
                        "name", matched_actual.get("tool_name")
                    ),
                    actual_args=matched_actual.get("args", matched_actual.get("input")),
                )
            )
        else:
            results.append(
                ToolCallResult(
                    expected_name=exp.name,
                    matched=False,
                    reason="No matching tool call found in actual calls",
                )
            )

    return results


def evaluate_turn(
    turn: ConversationTurn,
    turn_index: int,
    actual_response_text: str,
    actual_tool_calls: list[dict],
    duration_ms: int = 0,
) -> TurnResult:
    """Evaluate a single conversation turn against expectations.

    Args:
        turn: The expected turn specification.
        turn_index: Index of this turn in the conversation.
        actual_response_text: The agent's actual text response.
        actual_tool_calls: List of actual tool call dicts.
        duration_ms: Time taken for the turn.

    Returns:
        TurnResult with pass/fail details.
    """
    # Evaluate tool calls
    tool_results = evaluate_tool_calls(
        turn.expected_tool_calls,
        actual_tool_calls,
        turn.assertion_level,
    )

    # Evaluate response
    response_passed = True
    response_failures: list[str] = []

    if turn.expected_response:
        response_passed, response_failures = turn.expected_response.matches(
            actual_response_text, turn.assertion_level
        )

    # Compute quality scores
    keywords = turn.expected_response.contains if turn.expected_response else None
    quality_scores = compute_quality_scores(actual_response_text, keywords)

    return TurnResult(
        turn_index=turn_index,
        user_message=turn.user_message,
        assertion_level=turn.assertion_level,
        tool_call_results=tool_results,
        response_passed=response_passed,
        response_failures=response_failures,
        actual_response_text=actual_response_text,
        actual_tool_calls=actual_tool_calls,
        quality_scores=quality_scores,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


AgentCallable = Callable[
    [str, str, str],  # system_prompt, user_message, model
    tuple[str, list[dict]],  # (response_text, tool_calls)
]
"""Type for agent execution function.

Takes (system_prompt, user_message, model) and returns
(response_text, list_of_tool_call_dicts).
"""


def run_conversation(
    conversation: GoldenConversation,
    agent_fn: AgentCallable,
) -> ConversationResult:
    """Replay a golden conversation and evaluate each turn.

    Args:
        conversation: The golden conversation fixture.
        agent_fn: Callable that executes a single agent turn.
            Signature: (system_prompt, user_message, model) -> (text, tool_calls)

    Returns:
        ConversationResult with per-turn evaluation.
    """
    result = ConversationResult(
        name=conversation.name,
        description=conversation.description,
    )

    start = time.monotonic()

    try:
        for i, turn in enumerate(conversation.turns):
            turn_start = time.monotonic()

            response_text, tool_calls = agent_fn(
                conversation.system_prompt,
                turn.user_message,
                conversation.model,
            )

            turn_ms = int((time.monotonic() - turn_start) * 1000)

            turn_result = evaluate_turn(
                turn=turn,
                turn_index=i,
                actual_response_text=response_text,
                actual_tool_calls=tool_calls,
                duration_ms=turn_ms,
            )

            result.turn_results.append(turn_result)

    except Exception as exc:
        result.error = str(exc)
        logger.exception("Error running conversation '%s': %s", conversation.name, exc)

    result.total_duration_ms = int((time.monotonic() - start) * 1000)
    return result


def run_test_suite(
    conversations: list[GoldenConversation],
    agent_fn: AgentCallable,
    previous_results: Optional[dict] = None,
) -> TestReport:
    """Run all golden conversations and generate a test report.

    Args:
        conversations: List of golden conversation fixtures.
        agent_fn: Agent execution function.
        previous_results: Optional dict of previous results for regression detection.
            Keys are conversation names, values are dicts with 'passed' bool.

    Returns:
        TestReport with summary and regression information.
    """
    report = TestReport()
    report.total_conversations = len(conversations)

    for conv in conversations:
        conv_result = run_conversation(conv, agent_fn)
        report.results.append(conv_result)

        if conv_result.passed:
            report.passed_conversations += 1
        else:
            report.failed_conversations += 1

        report.total_turns += len(conv_result.turn_results)
        report.passed_turns += sum(1 for tr in conv_result.turn_results if tr.passed)

        # Regression detection
        if previous_results and conv.name in previous_results:
            prev = previous_results[conv.name]
            if prev.get("passed", False) and not conv_result.passed:
                report.regressions.append(
                    "REGRESSION: '{}' was passing, now failing".format(conv.name)
                )

    return report

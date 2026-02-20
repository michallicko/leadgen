"""LLM-as-judge quality scoring for enrichment outputs.

Uses Anthropic Claude (haiku for cost efficiency) to rate output quality
across multiple dimensions: completeness, specificity, accuracy, actionability.
"""

import json
import os
from datetime import datetime, timezone


QUALITY_PROMPT = """\
You are evaluating the quality of B2B sales enrichment data. Rate each dimension 0-10.

Dimensions:
- completeness: Are all expected fields populated with meaningful content? \
(not "Unknown", "None found", "N/A")
- specificity: Are answers specific to THIS company/person, or generic filler?
- accuracy_signals: Do the claims seem internally consistent? Any red flags?
- actionability: Would a sales rep find this useful for outreach preparation?

Input data provided to the enrichment node:
{input_json}

Output produced by the enrichment node ({node_name}):
{output_json}

Return JSON only, no markdown: \
{{"completeness": N, "specificity": N, "accuracy_signals": N, \
"actionability": N, "overall": N, "notes": "brief explanation"}}"""

COMPARE_PROMPT = """\
You are comparing two outputs from a B2B enrichment node. \
Both were produced from the same input. Rate each 0-10 on completeness, \
specificity, accuracy_signals, actionability.

Input data:
{input_json}

Output A ({label_a}):
{output_a_json}

Output B ({label_b}):
{output_b_json}

Return JSON only: \
{{"a_scores": {{"completeness": N, "specificity": N, "accuracy_signals": N, \
"actionability": N, "overall": N}}, \
"b_scores": {{"completeness": N, "specificity": N, "accuracy_signals": N, \
"actionability": N, "overall": N}}, \
"winner": "a"|"b"|"tie", "reason": "brief explanation"}}"""


class QualityScore:
    """Quality evaluation result."""

    def __init__(self, completeness, specificity, accuracy_signals,
                 actionability, overall, notes=""):
        self.completeness = completeness
        self.specificity = specificity
        self.accuracy_signals = accuracy_signals
        self.actionability = actionability
        self.overall = overall
        self.notes = notes

    def to_dict(self):
        return {
            "completeness": self.completeness,
            "specificity": self.specificity,
            "accuracy_signals": self.accuracy_signals,
            "actionability": self.actionability,
            "overall": self.overall,
            "notes": self.notes,
        }

    def __repr__(self):
        return (
            "QualityScore(overall={}, completeness={}, specificity={}, "
            "accuracy={}, actionability={})".format(
                self.overall, self.completeness, self.specificity,
                self.accuracy_signals, self.actionability))


class QualityScorer:
    """LLM-as-judge for enrichment output quality."""

    def __init__(self, anthropic_client, cost_tracker):
        self.client = anthropic_client
        self.cost_tracker = cost_tracker

    def score(self, node_name, input_data, output, test_name=None):
        """Score a single enrichment output.

        Args:
            node_name: Name of the enrichment node (e.g. "l1_research")
            input_data: Input dict provided to the node
            output: Output dict produced by the node
            test_name: Test name for cost tracking

        Returns:
            QualityScore instance
        """
        prompt = QUALITY_PROMPT.format(
            input_json=json.dumps(input_data, indent=2, default=str)[:2000],
            node_name=node_name,
            output_json=json.dumps(output, indent=2, default=str)[:3000],
        )

        resp = self.client.query(
            system_prompt="You are a B2B data quality evaluator. Return only JSON.",
            user_prompt=prompt,
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            temperature=0.1,
        )

        self.cost_tracker.log_call(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=resp.cost_usd,
            test_name=test_name or "quality_scoring",
            node_name="quality_judge_{}".format(node_name),
        )

        return self._parse_score(resp.content)

    def compare(self, node_name, input_data, output_a, output_b,
                label_a="A", label_b="B", test_name=None):
        """Compare two outputs for the same input. Returns (score_a, score_b, winner, reason)."""
        prompt = COMPARE_PROMPT.format(
            input_json=json.dumps(input_data, indent=2, default=str)[:1500],
            label_a=label_a,
            output_a_json=json.dumps(output_a, indent=2, default=str)[:2000],
            label_b=label_b,
            output_b_json=json.dumps(output_b, indent=2, default=str)[:2000],
        )

        resp = self.client.query(
            system_prompt="You are a B2B data quality evaluator. Return only JSON.",
            user_prompt=prompt,
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            temperature=0.1,
        )

        self.cost_tracker.log_call(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=resp.cost_usd,
            test_name=test_name or "quality_comparison",
            node_name="quality_compare_{}".format(node_name),
        )

        return self._parse_comparison(resp.content)

    def save_report(self, scores, path=None):
        """Save quality scores report to JSON file."""
        if path is None:
            reports_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = os.path.join(
                reports_dir, "quality_{}.json".format(timestamp))

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scores": [s.to_dict() if isinstance(s, QualityScore) else s
                       for s in scores],
        }
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        return path

    @staticmethod
    def _parse_score(content):
        """Parse quality score JSON from LLM response."""
        import re
        cleaned = re.sub(r"```(?:json)?\s*", "", content.strip())
        cleaned = cleaned.rstrip("`").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[^{}]*\}", cleaned)
            if match:
                data = json.loads(match.group(0))
            else:
                return QualityScore(0, 0, 0, 0, 0, "Failed to parse judge response")

        return QualityScore(
            completeness=data.get("completeness", 0),
            specificity=data.get("specificity", 0),
            accuracy_signals=data.get("accuracy_signals", 0),
            actionability=data.get("actionability", 0),
            overall=data.get("overall", 0),
            notes=data.get("notes", ""),
        )

    @staticmethod
    def _parse_comparison(content):
        """Parse comparison JSON from LLM response."""
        import re
        cleaned = re.sub(r"```(?:json)?\s*", "", content.strip())
        cleaned = cleaned.rstrip("`").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                data = json.loads(match.group(0))
            else:
                return None, None, "error", "Failed to parse comparison"

        a_data = data.get("a_scores", {})
        b_data = data.get("b_scores", {})

        score_a = QualityScore(
            a_data.get("completeness", 0), a_data.get("specificity", 0),
            a_data.get("accuracy_signals", 0), a_data.get("actionability", 0),
            a_data.get("overall", 0),
        )
        score_b = QualityScore(
            b_data.get("completeness", 0), b_data.get("specificity", 0),
            b_data.get("accuracy_signals", 0), b_data.get("actionability", 0),
            b_data.get("overall", 0),
        )

        return score_a, score_b, data.get("winner", "tie"), data.get("reason", "")

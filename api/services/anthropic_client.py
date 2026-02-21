"""Shared Anthropic API client with model selection, retry, and cost tracking.

Used by L2 Company and Person enrichers for synthesis tasks
(summarization, pain hypothesis generation, personalization).

Usage:
    from api.services.anthropic_client import AnthropicClient

    client = AnthropicClient(api_key="sk-ant-xxx")
    result = client.query(
        system_prompt="You are an analyst.",
        user_prompt="Synthesize these findings...",
        model="claude-sonnet-4-5-20241022",
    )
    print(result.content, result.cost_usd)
"""

import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

# Pricing per 1M tokens
MODEL_PRICING = {
    "claude-haiku-4-5-20251001":    {"input_per_m": 0.80, "output_per_m": 4.0},
    "claude-sonnet-4-5-20241022":   {"input_per_m": 3.0,  "output_per_m": 15.0},
    "claude-opus-4-6":              {"input_per_m": 15.0, "output_per_m": 75.0},
}

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicResponse:
    """Structured response from an Anthropic API call."""

    __slots__ = ("content", "model", "input_tokens", "output_tokens", "cost_usd")

    def __init__(self, content, model, input_tokens, output_tokens, cost_usd):
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


class AnthropicClient:
    """Shared Anthropic Messages API client."""

    def __init__(self, api_key, base_url="https://api.anthropic.com",
                 default_model="claude-haiku-4-5-20251001", timeout=90,
                 max_retries=2, retry_delay=1.0):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def query(self, system_prompt, user_prompt, model=None,
              max_tokens=1024, temperature=0.3):
        """Send a query to Anthropic Messages API.

        Args:
            system_prompt: System instruction (top-level 'system' field)
            user_prompt: User message content
            model: Model name (default: self.default_model)
            max_tokens: Max output tokens
            temperature: Sampling temperature

        Returns:
            AnthropicResponse with content, tokens, and cost

        Raises:
            requests.HTTPError: On non-retryable errors or after retries exhausted
        """
        model = model or self.default_model

        payload = {
            "model": model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(1 + self.max_retries):
            try:
                resp = requests.post(
                    "{}/v1/messages".format(self.base_url),
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()

                data = resp.json()
                # Extract text from content blocks
                content_blocks = data.get("content", [])
                content = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        content += block.get("text", "")

                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                cost_usd = self._estimate_cost(model, input_tokens, output_tokens)

                return AnthropicResponse(
                    content=content,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                )

            except requests.HTTPError as e:
                last_error = e
                status = getattr(resp, "status_code", 0)

                if status not in RETRYABLE_STATUS_CODES:
                    raise

                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "Anthropic API %s (attempt %d/%d), retrying in %.1fs",
                        status, attempt + 1, 1 + self.max_retries, delay,
                    )
                    time.sleep(delay)
                else:
                    raise

        raise last_error

    def stream_query(self, messages, system_prompt, max_tokens=4096,
                     model=None, temperature=0.3):
        """Stream a response from Anthropic Messages API via SSE.

        Yields text chunks as they arrive. Use this for real-time streaming
        in playbook generation and other long-form outputs.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system_prompt: System instruction (top-level 'system' field).
            max_tokens: Max output tokens (default 4096).
            model: Model name (default: self.default_model).
            temperature: Sampling temperature.

        Yields:
            str: Text chunks from content_block_delta events.

        Raises:
            requests.HTTPError: On non-200 API responses.
        """
        model = model or self.default_model

        payload = {
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        resp = requests.post(
            "{}/v1/messages".format(self.base_url),
            headers=headers,
            json=payload,
            timeout=self.timeout,
            stream=True,
        )
        resp.raise_for_status()

        current_event = None
        for line in resp.iter_lines():
            if not line:
                # Blank line = end of SSE event
                current_event = None
                continue

            decoded = line.decode("utf-8", errors="replace")

            if decoded.startswith("event: "):
                current_event = decoded[7:]
                continue

            if decoded.startswith("data: "):
                data_str = decoded[6:]

                if current_event == "message_stop":
                    return

                if current_event == "content_block_delta":
                    try:
                        data = json.loads(data_str)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Skipping malformed SSE data: %s", data_str[:100])
                        continue

                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield text

    @staticmethod
    def _estimate_cost(model, input_tokens, output_tokens):
        """Estimate USD cost based on model pricing."""
        # Default to haiku pricing if model not found
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-haiku-4-5-20251001"])
        input_cost = (input_tokens / 1_000_000) * pricing["input_per_m"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_per_m"]
        return round(input_cost + output_cost, 6)

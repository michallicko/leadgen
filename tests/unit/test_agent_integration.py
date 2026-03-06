"""Unit tests for api/agents/integration.py — feature flag and integration."""

import os
from unittest.mock import patch


from api.agents.integration import is_langgraph_enabled


class TestIsLangGraphEnabled:
    def test_default_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove LANGGRAPH_ENABLED if present
            os.environ.pop("LANGGRAPH_ENABLED", None)
            assert is_langgraph_enabled() is False

    def test_enabled_true(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "true"}):
            assert is_langgraph_enabled() is True

    def test_enabled_1(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "1"}):
            assert is_langgraph_enabled() is True

    def test_enabled_yes(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "yes"}):
            assert is_langgraph_enabled() is True

    def test_enabled_TRUE_case_insensitive(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "TRUE"}):
            assert is_langgraph_enabled() is True

    def test_disabled_false(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "false"}):
            assert is_langgraph_enabled() is False

    def test_disabled_0(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "0"}):
            assert is_langgraph_enabled() is False

    def test_disabled_empty(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": ""}):
            assert is_langgraph_enabled() is False

    def test_disabled_random_string(self):
        with patch.dict(os.environ, {"LANGGRAPH_ENABLED": "maybe"}):
            assert is_langgraph_enabled() is False

"""Tests for multimodal content summarizer."""

from unittest.mock import patch


from api.services.multimodal.summarizer import (
    _build_summary_prompt,
    _fallback_summary,
    generate_l0_mention,
    summarize_content,
)


class TestFallbackSummary:
    def test_basic_summary(self):
        text = "This is a test document with some content about business strategies."
        result = _fallback_summary(text, "report.pdf")
        assert "report.pdf" in result
        assert "words" in result

    def test_without_filename(self):
        text = "Some content here."
        result = _fallback_summary(text)
        assert "words" in result
        assert "Preview:" in result


class TestBuildSummaryPrompt:
    def test_includes_filename(self):
        prompt = _build_summary_prompt("content", "test.pdf", 500)
        assert "test.pdf" in prompt

    def test_includes_content(self):
        prompt = _build_summary_prompt("my unique text", "", 500)
        assert "my unique text" in prompt


class TestSummarizeContent:
    def test_short_text_returns_none(self):
        assert summarize_content("hi") is None
        assert summarize_content("") is None

    def test_fallback_when_no_api_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            result = summarize_content(
                "This is a long enough text to be summarized by the system.",
                "test.pdf",
            )
            assert result is not None  # Fallback summary
            assert "test.pdf" in result


class TestGenerateL0Mention:
    def test_small_file(self):
        mock_file = _make_mock_file(size_bytes=5000, filename="small.pdf")
        result = generate_l0_mention(mock_file)
        assert "small.pdf" in result
        assert "KB" in result

    def test_large_file(self):
        mock_file = _make_mock_file(size_bytes=5 * 1024 * 1024, filename="big.pdf")
        result = generate_l0_mention(mock_file)
        assert "big.pdf" in result
        assert "MB" in result

    def test_with_page_range(self):
        mock_content = type("Content", (), {"page_range": "1-10"})()
        mock_file = _make_mock_file(
            size_bytes=50000, filename="multi.pdf", contents=[mock_content]
        )
        result = generate_l0_mention(mock_file)
        assert "10" in result


def _make_mock_file(size_bytes=1000, filename="test.pdf", contents=None):
    """Create a mock FileUpload object."""
    mock = type(
        "FileUpload",
        (),
        {
            "original_filename": filename,
            "size_bytes": size_bytes,
            "contents": contents or [],
        },
    )()
    return mock

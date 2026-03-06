"""Tests for multimodal content extractors."""

from unittest.mock import MagicMock, patch


from api.services.multimodal.extractors import (
    _extract_html_basic,
    _table_to_markdown,
    extract_content,
)


class TestExtractContent:
    def test_unknown_type_returns_none(self):
        assert extract_content("/fake/path", "unknown", "application/x-unknown") is None

    def test_exception_returns_none(self):
        with patch(
            "api.services.multimodal.extractors.extract_pdf",
            side_effect=RuntimeError("test"),
        ):
            result = extract_content("/fake/path", "pdf", "application/pdf")
            assert result is None


class TestExtractHtmlBasic:
    def test_basic_html(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<html><body><h1>Title</h1><p>Content here</p></body></html>"
        )
        result = _extract_html_basic(str(html_file))
        assert result is not None
        assert "Title" in result["text"]
        assert "Content here" in result["text"]

    def test_strips_scripts(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<html><body><script>alert('xss')</script><p>Safe</p></body></html>"
        )
        result = _extract_html_basic(str(html_file))
        assert result is not None
        assert "alert" not in result["text"]
        assert "Safe" in result["text"]

    def test_strips_styles(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text(
            "<html><head><style>body{color:red}</style></head><body>Text</body></html>"
        )
        result = _extract_html_basic(str(html_file))
        assert result is not None
        assert "color:red" not in result["text"]
        assert "Text" in result["text"]

    def test_nonexistent_file_returns_none(self):
        result = _extract_html_basic("/nonexistent/file.html")
        assert result is None


class TestTableToMarkdown:
    def test_simple_table(self):
        """Test markdown conversion with a mock table."""
        # Create mock table
        mock_table = MagicMock()
        row1 = MagicMock()
        row1.cells = [MagicMock(text="Header1"), MagicMock(text="Header2")]
        row2 = MagicMock()
        row2.cells = [MagicMock(text="Val1"), MagicMock(text="Val2")]
        mock_table.rows = [row1, row2]

        result = _table_to_markdown(mock_table)
        assert "| Header1 | Header2 |" in result
        assert "| --- | --- |" in result
        assert "| Val1 | Val2 |" in result

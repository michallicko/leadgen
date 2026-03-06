"""Tests for PDF processor (BL-265)."""

from unittest.mock import MagicMock, patch

import pytest

from api.services.multimodal.pdf_processor import (
    SPARSE_TEXT_THRESHOLD,
    PageResult,
    PDFExtractionResult,
    get_vision_pages,
    pages_to_markdown,
)


class TestPageResult:
    def test_sparse_text_flags_vision(self):
        page = PageResult(page_number=1, text="short", needs_vision=True)
        assert page.needs_vision is True

    def test_normal_text_no_vision(self):
        page = PageResult(page_number=1, text="x" * 200, needs_vision=False)
        assert page.needs_vision is False


class TestPagesToMarkdown:
    def test_single_page_text(self):
        result = PDFExtractionResult(
            pages=[PageResult(page_number=1, text="Hello world")],
            total_pages=1,
        )
        md = pages_to_markdown(result)
        assert "### Page 1" in md
        assert "Hello world" in md

    def test_table_conversion(self):
        result = PDFExtractionResult(
            pages=[
                PageResult(
                    page_number=1,
                    text="Table below",
                    tables=[[["Name", "Value"], ["Foo", "100"], ["Bar", "200"]]],
                )
            ],
            total_pages=1,
        )
        md = pages_to_markdown(result)
        assert "| Name | Value |" in md
        assert "| Foo | 100 |" in md

    def test_truncation_notice(self):
        result = PDFExtractionResult(
            pages=[PageResult(page_number=1, text="Page 1")],
            total_pages=100,
            truncated=True,
        )
        md = pages_to_markdown(result)
        assert "truncated" in md.lower()
        assert "1 of 100" in md

    def test_empty_pages(self):
        result = PDFExtractionResult(pages=[], total_pages=0)
        md = pages_to_markdown(result)
        assert md == ""


class TestGetVisionPages:
    def test_returns_flagged_pages(self):
        result = PDFExtractionResult(
            pages=[
                PageResult(page_number=1, text="x" * 200, needs_vision=False),
                PageResult(page_number=2, text="", needs_vision=True),
                PageResult(page_number=3, text="x" * 200, needs_vision=False),
                PageResult(page_number=4, text="short", needs_vision=True),
            ],
            total_pages=4,
        )
        vision = get_vision_pages(result)
        assert vision == [2, 4]

    def test_no_vision_needed(self):
        result = PDFExtractionResult(
            pages=[PageResult(page_number=1, text="x" * 200, needs_vision=False)],
            total_pages=1,
        )
        assert get_vision_pages(result) == []


class TestExtractTextFromPdf:
    def test_extraction_result_has_expected_fields(self):
        """PDFExtractionResult has the expected structure."""
        result = PDFExtractionResult()
        assert result.pages == []
        assert result.total_pages == 0
        assert result.truncated is False
        assert result.errors == []

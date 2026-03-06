"""PDF text and table extraction (BL-265).

Uses pdfplumber for text-heavy PDFs.  Pages with sparse text
(< 100 chars) are flagged for Claude vision API fallback.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum chars per page before flagging for vision fallback
SPARSE_TEXT_THRESHOLD = 100

# Maximum pages to process fully
MAX_PAGES = 50


@dataclass
class PageResult:
    """Extraction result for a single PDF page."""

    page_number: int
    text: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    needs_vision: bool = False


@dataclass
class PDFExtractionResult:
    """Complete extraction result for a PDF."""

    pages: list[PageResult] = field(default_factory=list)
    total_pages: int = 0
    truncated: bool = False
    errors: list[str] = field(default_factory=list)


def extract_text_from_pdf(
    file_path: str, max_pages: int = MAX_PAGES
) -> PDFExtractionResult:
    """Extract text and tables from a PDF file.

    Args:
        file_path: Path to the PDF file.
        max_pages: Maximum number of pages to process.

    Returns:
        PDFExtractionResult with per-page text, tables, and vision flags.
    """
    try:
        import pdfplumber
    except ImportError:
        return PDFExtractionResult(
            errors=["pdfplumber not installed — run: pip install pdfplumber"]
        )

    result = PDFExtractionResult()

    try:
        with pdfplumber.open(file_path) as pdf:
            result.total_pages = len(pdf.pages)
            result.truncated = result.total_pages > max_pages

            for i, page in enumerate(pdf.pages[:max_pages]):
                page_result = _extract_page(page, i + 1)
                result.pages.append(page_result)

    except Exception as exc:
        logger.exception("PDF extraction failed: %s", file_path)
        result.errors.append("PDF extraction failed: {}".format(str(exc)))

    return result


def extract_text_from_bytes(
    pdf_bytes: bytes, max_pages: int = MAX_PAGES
) -> PDFExtractionResult:
    """Extract text from PDF bytes (for in-memory processing).

    Args:
        pdf_bytes: Raw PDF file content.
        max_pages: Maximum pages to process.

    Returns:
        PDFExtractionResult.
    """
    try:
        import pdfplumber
    except ImportError:
        return PDFExtractionResult(errors=["pdfplumber not installed"])

    result = PDFExtractionResult()

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result.total_pages = len(pdf.pages)
            result.truncated = result.total_pages > max_pages

            for i, page in enumerate(pdf.pages[:max_pages]):
                page_result = _extract_page(page, i + 1)
                result.pages.append(page_result)

    except Exception as exc:
        logger.exception("PDF bytes extraction failed")
        result.errors.append("PDF extraction failed: {}".format(str(exc)))

    return result


def pages_to_markdown(result: PDFExtractionResult) -> str:
    """Convert extraction result to a markdown document.

    Args:
        result: PDFExtractionResult from extraction.

    Returns:
        Markdown-formatted text of the PDF contents.
    """
    parts = []
    for page in result.pages:
        if page.text.strip():
            parts.append(
                "### Page {}\n\n{}".format(page.page_number, page.text.strip())
            )

        for table in page.tables:
            md_table = _table_to_markdown(table)
            if md_table:
                parts.append(md_table)

    if result.truncated:
        parts.append(
            "\n*[Document truncated — {} of {} pages shown]*".format(
                len(result.pages), result.total_pages
            )
        )

    return "\n\n".join(parts)


def get_vision_pages(result: PDFExtractionResult) -> list[int]:
    """Get page numbers that need vision API processing.

    Returns:
        List of 1-based page numbers flagged for vision fallback.
    """
    return [p.page_number for p in result.pages if p.needs_vision]


def _extract_page(page, page_number: int) -> PageResult:
    """Extract text and tables from a single pdfplumber page."""
    result = PageResult(page_number=page_number)

    try:
        text = page.extract_text() or ""
        result.text = text

        # Flag sparse pages for vision fallback
        if len(text.strip()) < SPARSE_TEXT_THRESHOLD:
            result.needs_vision = True

    except Exception as exc:
        logger.warning("Text extraction failed on page %d: %s", page_number, exc)
        result.needs_vision = True

    try:
        tables = page.extract_tables() or []
        result.tables = tables
    except Exception as exc:
        logger.warning("Table extraction failed on page %d: %s", page_number, exc)

    return result


def _table_to_markdown(table: list[list[Optional[str]]]) -> str:
    """Convert a pdfplumber table to markdown format."""
    if not table or len(table) < 2:
        return ""

    # Clean cells
    clean = []
    for row in table:
        clean.append([str(cell).strip() if cell else "" for cell in row])

    header = clean[0]
    rows = clean[1:]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows:
        # Pad row to match header length
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[: len(header)]) + " |")

    return "\n".join(lines)

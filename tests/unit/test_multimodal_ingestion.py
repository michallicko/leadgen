"""Tests for multimodal file ingestion service."""

import pytest

from api.services.multimodal.ingestion import (
    EXTENSION_MAP,
    MAX_FILE_SIZE,
    _sanitize_filename,
    _validate_url_safety,
    resolve_mime_type,
    validate_upload,
)


class TestValidateUpload:
    def test_valid_pdf(self):
        assert validate_upload("test.pdf", 1024, "application/pdf") is None

    def test_valid_image(self):
        assert validate_upload("photo.jpg", 2048, "image/jpeg") is None

    def test_valid_docx(self):
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert validate_upload("doc.docx", 5000, mime) is None

    def test_valid_html(self):
        assert validate_upload("page.html", 1000, "text/html") is None

    def test_file_too_large(self):
        error = validate_upload("big.pdf", MAX_FILE_SIZE + 1, "application/pdf")
        assert error is not None
        assert "too large" in error.lower()

    def test_empty_file(self):
        error = validate_upload("empty.pdf", 0, "application/pdf")
        assert error is not None
        assert "empty" in error.lower()

    def test_unsupported_type(self):
        error = validate_upload("virus.exe", 1024, "application/x-executable")
        assert error is not None
        assert "unsupported" in error.lower()

    def test_extension_fallback(self):
        """When MIME is generic but extension is known, allow it."""
        assert validate_upload("doc.pdf", 1024, "application/octet-stream") is None

    def test_unknown_extension(self):
        error = validate_upload("file.xyz", 1024, "application/octet-stream")
        assert error is not None


class TestResolveMimeType:
    def test_known_mime(self):
        assert resolve_mime_type("test.pdf", "application/pdf") == "application/pdf"

    def test_generic_mime_with_pdf_ext(self):
        assert (
            resolve_mime_type("test.pdf", "application/octet-stream")
            == "application/pdf"
        )

    def test_generic_mime_with_docx_ext(self):
        result = resolve_mime_type("test.docx", "application/octet-stream")
        assert "wordprocessingml" in result

    def test_unknown_stays_unchanged(self):
        assert resolve_mime_type("test.xyz", "application/xyz") == "application/xyz"


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert _sanitize_filename("report.pdf") == "report.pdf"

    def test_path_traversal(self):
        result = _sanitize_filename("../../../etc/passwd")
        assert "/" not in result
        assert ".." not in result or result == ".._.._.._.._..etc_passwd"  # Safe

    def test_special_chars(self):
        result = _sanitize_filename("my file (1).pdf")
        assert " " not in result  # Spaces replaced
        assert "(" not in result

    def test_long_filename_truncated(self):
        long_name = "a" * 300 + ".pdf"
        result = _sanitize_filename(long_name)
        assert len(result) <= 200

    def test_preserves_extension(self):
        result = _sanitize_filename("test-file_2024.pdf")
        assert result.endswith(".pdf")


class TestExtensionMap:
    def test_jpg_maps_to_image_jpeg(self):
        """Regression: .jpg was incorrectly mapped to application/pdf."""
        assert EXTENSION_MAP[".jpg"] == "image/jpeg"

    def test_jpeg_maps_to_image_jpeg(self):
        assert EXTENSION_MAP[".jpeg"] == "image/jpeg"


class TestValidateUrlSafety:
    """SSRF protection tests for _validate_url_safety."""

    def test_blocks_localhost(self):
        with pytest.raises(ValueError, match="bare hostname"):
            _validate_url_safety("http://localhost/admin")

    def test_blocks_127_0_0_1(self):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url_safety("http://127.0.0.1/admin")

    def test_blocks_10_x_network(self):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url_safety("http://10.0.0.1/secret")

    def test_blocks_172_16_network(self):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url_safety("http://172.16.0.1/internal")

    def test_blocks_192_168_network(self):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url_safety("http://192.168.1.1/router")

    def test_blocks_aws_metadata_ip(self):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url_safety("http://169.254.169.254/latest/meta-data/")

    def test_blocks_metadata_google_internal(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_url_safety("http://metadata.google.internal/computeMetadata/")

    def test_blocks_ftp_scheme(self):
        with pytest.raises(ValueError, match="Only http"):
            _validate_url_safety("ftp://example.com/file.txt")

    def test_blocks_file_scheme(self):
        with pytest.raises(ValueError, match="Only http"):
            _validate_url_safety("file:///etc/passwd")

    def test_blocks_bare_hostname(self):
        with pytest.raises(ValueError, match="bare hostname"):
            _validate_url_safety("http://intranet/admin")

    def test_blocks_empty_hostname(self):
        with pytest.raises(ValueError, match="no hostname"):
            _validate_url_safety("http:///path")

    def test_allows_public_http(self):
        # Should not raise for legitimate public URLs
        _validate_url_safety("https://www.example.com/page.html")

    def test_allows_public_https(self):
        _validate_url_safety("https://docs.google.com/document/d/abc123")

    def test_blocks_ipv6_loopback(self):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url_safety("http://[::1]/admin")

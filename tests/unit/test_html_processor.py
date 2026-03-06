"""Tests for HTML processor (BL-266)."""

from api.services.multimodal.html_processor import (
    validate_url,
    _cache_key,
    _get_cached,
    _set_cached,
    _url_cache,
)


class TestValidateUrl:
    def test_valid_https_url(self):
        assert validate_url("https://example.com/page") is None

    def test_valid_http_url(self):
        assert validate_url("http://example.com") is None

    def test_rejects_ftp(self):
        error = validate_url("ftp://files.example.com/doc")
        assert error is not None
        assert "http" in error.lower()

    def test_rejects_localhost(self):
        error = validate_url("http://localhost:8080/admin")
        assert error is not None

    def test_rejects_private_ip_10(self):
        error = validate_url("http://10.0.0.1/internal")
        assert error is not None
        assert "private" in error.lower()

    def test_rejects_private_ip_192(self):
        error = validate_url("http://192.168.1.1/admin")
        assert error is not None

    def test_rejects_private_ip_172(self):
        error = validate_url("http://172.16.0.1/")
        assert error is not None

    def test_rejects_loopback(self):
        error = validate_url("http://127.0.0.1/")
        assert error is not None

    def test_rejects_metadata_endpoint(self):
        error = validate_url("http://metadata.google.internal/")
        assert error is not None

    def test_rejects_no_dot_in_hostname(self):
        error = validate_url("http://intranet/secret")
        assert error is not None

    def test_rejects_empty_hostname(self):
        error = validate_url("http:///path")
        assert error is not None


class TestUrlCache:
    def setup_method(self):
        _url_cache.clear()

    def test_cache_miss(self):
        assert _get_cached("https://example.com") is None

    def test_cache_hit(self):
        data = {"url": "https://example.com", "content": "test"}
        _set_cached("https://example.com", data)
        result = _get_cached("https://example.com")
        assert result is not None
        assert result["content"] == "test"

    def test_cache_key_deterministic(self):
        k1 = _cache_key("https://example.com")
        k2 = _cache_key("https://example.com")
        assert k1 == k2

    def test_different_urls_different_keys(self):
        k1 = _cache_key("https://example.com/a")
        k2 = _cache_key("https://example.com/b")
        assert k1 != k2

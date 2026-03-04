"""Unit tests for SSRF domain validation (_is_safe_domain).

Ensures the domain validation helper in playbook_routes correctly rejects
domains that resolve to private, loopback, link-local, or reserved IPs,
and accepts domains that resolve to public IPs.
"""

from unittest.mock import patch

import pytest

from api.routes.playbook_routes import _is_safe_domain


class TestIsSafeDomain:
    """Test the _is_safe_domain helper used to block SSRF."""

    def test_rejects_empty_domain(self):
        assert not _is_safe_domain("")
        assert not _is_safe_domain(None)

    def test_rejects_localhost_literal(self):
        assert not _is_safe_domain("localhost")
        assert not _is_safe_domain("LOCALHOST")
        assert not _is_safe_domain("127.0.0.1")
        assert not _is_safe_domain("::1")

    def test_rejects_localhost_with_port(self):
        assert not _is_safe_domain("localhost:8080")
        assert not _is_safe_domain("127.0.0.1:5000")

    @patch("api.routes.playbook_routes.socket.gethostbyname")
    def test_rejects_private_ip_resolution(self, mock_resolve):
        """Domains that resolve to RFC-1918 private addresses are blocked."""
        mock_resolve.return_value = "10.0.0.1"
        assert not _is_safe_domain("internal.example.com")

        mock_resolve.return_value = "192.168.1.1"
        assert not _is_safe_domain("home.example.com")

        mock_resolve.return_value = "172.16.0.5"
        assert not _is_safe_domain("corp.example.com")

    @patch("api.routes.playbook_routes.socket.gethostbyname")
    def test_rejects_link_local_resolution(self, mock_resolve):
        """Cloud metadata endpoint (169.254.x.x) is blocked."""
        mock_resolve.return_value = "169.254.169.254"
        assert not _is_safe_domain("169.254.169.254.nip.io")

    @patch("api.routes.playbook_routes.socket.gethostbyname")
    def test_rejects_loopback_resolution(self, mock_resolve):
        mock_resolve.return_value = "127.0.0.1"
        assert not _is_safe_domain("loopback.example.com")

    @patch("api.routes.playbook_routes.socket.gethostbyname")
    def test_accepts_public_domain(self, mock_resolve):
        """Domains resolving to public IPs pass validation."""
        mock_resolve.return_value = "142.250.80.46"
        assert _is_safe_domain("google.com")

    @patch("api.routes.playbook_routes.socket.gethostbyname")
    def test_accepts_another_public_domain(self, mock_resolve):
        mock_resolve.return_value = "104.16.132.229"
        assert _is_safe_domain("stripe.com")

    @patch(
        "api.routes.playbook_routes.socket.gethostbyname",
        side_effect=Exception("DNS resolution failed"),
    )
    def test_rejects_unresolvable_domain(self, mock_resolve):
        """Domains that cannot be resolved are rejected."""
        assert not _is_safe_domain("nonexistent.invalid")

    def test_strips_trailing_slash(self):
        """Trailing slashes and whitespace are handled gracefully."""
        with patch("api.routes.playbook_routes.socket.gethostbyname") as mock_resolve:
            mock_resolve.return_value = "142.250.80.46"
            assert _is_safe_domain("google.com/")
            assert _is_safe_domain("  google.com  ")

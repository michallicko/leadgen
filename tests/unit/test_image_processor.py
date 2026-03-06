"""Tests for image processor (BL-265)."""

from unittest.mock import MagicMock, patch

import pytest

from api.services.multimodal.image_processor import (
    MAX_DIMENSION,
    SUPPORTED_TYPES,
    TOKENS_PER_IMAGE,
    build_vision_content_block,
    estimate_tokens,
    ImagePayload,
)


class TestSupportedTypes:
    def test_png_supported(self):
        assert "image/png" in SUPPORTED_TYPES

    def test_jpeg_supported(self):
        assert "image/jpeg" in SUPPORTED_TYPES

    def test_webp_supported(self):
        assert "image/webp" in SUPPORTED_TYPES

    def test_gif_supported(self):
        assert "image/gif" in SUPPORTED_TYPES

    def test_bmp_not_supported(self):
        assert "image/bmp" not in SUPPORTED_TYPES


class TestBuildVisionContentBlock:
    def test_returns_image_and_text_blocks(self):
        payload = ImagePayload(
            base64_data="dGVzdA==",
            media_type="image/png",
            width=100,
            height=100,
            original_size_bytes=1000,
        )
        blocks = build_vision_content_block(payload, "What is this?")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "image"
        assert blocks[0]["source"]["type"] == "base64"
        assert blocks[0]["source"]["media_type"] == "image/png"
        assert blocks[1]["type"] == "text"
        assert blocks[1]["text"] == "What is this?"


class TestEstimateTokens:
    def test_single_image(self):
        assert estimate_tokens(1) == TOKENS_PER_IMAGE

    def test_multiple_images(self):
        assert estimate_tokens(5) == 5 * TOKENS_PER_IMAGE

    def test_zero_images(self):
        assert estimate_tokens(0) == 0


class TestPrepareImage:
    @patch("api.services.multimodal.image_processor.Image", create=True)
    def test_unsupported_type_returns_none(self, mock_image):
        from api.services.multimodal.image_processor import prepare_image

        result = prepare_image(b"fake", "image/bmp")
        assert result is None

    def test_prepare_image_with_pillow(self):
        """Test image preparation with a real tiny PNG."""
        try:
            from PIL import Image
            import io

            # Create a tiny test image
            img = Image.new("RGB", (100, 100), color="red")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            from api.services.multimodal.image_processor import prepare_image

            result = prepare_image(png_bytes, "image/png")
            assert result is not None
            assert result.width == 100
            assert result.height == 100
            assert result.media_type == "image/png"
            assert len(result.base64_data) > 0
        except ImportError:
            pytest.skip("Pillow not installed")

    def test_resize_large_image(self):
        """Test that large images get resized."""
        try:
            from PIL import Image
            import io

            img = Image.new("RGB", (3000, 2000), color="blue")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            from api.services.multimodal.image_processor import prepare_image

            result = prepare_image(png_bytes, "image/png")
            assert result is not None
            assert max(result.width, result.height) <= MAX_DIMENSION
        except ImportError:
            pytest.skip("Pillow not installed")

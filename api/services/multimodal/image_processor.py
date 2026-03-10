"""Image processing for Claude vision API (BL-265).

Handles image resizing, base64 encoding, and preparation for the
Claude vision API.  Supports PNG, JPEG, WebP, and GIF.
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Claude vision max dimension
MAX_DIMENSION = 1568

# Supported MIME types
SUPPORTED_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/webp": "webp",
    "image/gif": "gif",
}

# Approximate tokens per image (Claude vision pricing)
TOKENS_PER_IMAGE = 1600


@dataclass
class ImagePayload:
    """Prepared image ready for Claude vision API."""

    base64_data: str
    media_type: str
    width: int
    height: int
    original_size_bytes: int
    estimated_tokens: int = TOKENS_PER_IMAGE


def prepare_image(
    image_bytes: bytes,
    mime_type: str,
    max_dimension: int = MAX_DIMENSION,
) -> Optional[ImagePayload]:
    """Resize and encode an image for Claude vision API.

    Args:
        image_bytes: Raw image file content.
        mime_type: MIME type of the image.
        max_dimension: Maximum pixels on the longest side.

    Returns:
        ImagePayload ready for API, or None on error.
    """
    if mime_type not in SUPPORTED_TYPES:
        logger.warning("Unsupported image type: %s", mime_type)
        return None

    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow not installed — run: pip install Pillow")
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes))
        original_size = len(image_bytes)

        # Resize if needed
        img = _resize_if_needed(img, max_dimension)

        # Convert to bytes
        output_format = SUPPORTED_TYPES[mime_type].upper()
        if output_format == "JPG":
            output_format = "JPEG"

        buf = io.BytesIO()
        img.save(buf, format=output_format)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

        return ImagePayload(
            base64_data=encoded,
            media_type=mime_type,
            width=img.width,
            height=img.height,
            original_size_bytes=original_size,
        )

    except Exception as exc:
        logger.exception("Image processing failed: %s", exc)
        return None


def prepare_image_from_path(
    file_path: str,
    mime_type: str,
    max_dimension: int = MAX_DIMENSION,
) -> Optional[ImagePayload]:
    """Load and prepare an image from a file path.

    Args:
        file_path: Path to the image file.
        mime_type: MIME type of the image.
        max_dimension: Maximum pixels on the longest side.

    Returns:
        ImagePayload or None on error.
    """
    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        return prepare_image(image_bytes, mime_type, max_dimension)
    except FileNotFoundError:
        logger.error("Image file not found: %s", file_path)
        return None
    except Exception as exc:
        logger.exception("Failed to read image: %s", exc)
        return None


def build_vision_content_block(payload: ImagePayload, query: str) -> list[dict]:
    """Build Claude API content blocks for a vision request.

    Args:
        payload: Prepared image payload.
        query: User's question about the image.

    Returns:
        List of content blocks for the Claude messages API.
    """
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": payload.media_type,
                "data": payload.base64_data,
            },
        },
        {
            "type": "text",
            "text": query,
        },
    ]


def estimate_tokens(image_count: int) -> int:
    """Estimate token cost for processing images.

    Args:
        image_count: Number of images to process.

    Returns:
        Estimated token count.
    """
    return image_count * TOKENS_PER_IMAGE


def _resize_if_needed(img, max_dim: int):
    """Resize image so longest side does not exceed max_dim."""
    w, h = img.size
    if max(w, h) <= max_dim:
        return img

    if w > h:
        new_w = max_dim
        new_h = int(h * (max_dim / w))
    else:
        new_h = max_dim
        new_w = int(w * (max_dim / h))

    from PIL import Image

    try:
        resample = Image.Resampling.LANCZOS  # Pillow 9.1+
    except AttributeError:
        resample = Image.LANCZOS  # Pillow < 9.1
    return img.resize((new_w, new_h), resample)

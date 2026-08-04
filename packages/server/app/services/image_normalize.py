"""Normalize uploaded images for Azure Foundry vision models."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image

HEIC_CONTENT_TYPES = {
    "image/heic",
    "image/heif",
    "image/heic-sequence",
    "image/heif-sequence",
}

HEIC_EXTENSIONS = {".heic", ".heif", ".heics", ".heifs"}


def register_heif_opener() -> None:
    """Register HEIF/HEIC support with Pillow when pillow-heif is installed."""
    try:
        from pillow_heif import register_heif_opener
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise HTTPException(
            status_code=500,
            detail="HEIC support is unavailable. Install pillow-heif.",
        ) from exc
    register_heif_opener()


def is_heic_upload(*, content_type: str, filename: str | None) -> bool:
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime in HEIC_CONTENT_TYPES:
        return True
    suffix = Path(filename or "").suffix.lower()
    return suffix in HEIC_EXTENSIONS


def normalize_image_for_foundry(
    *,
    image_bytes: bytes,
    content_type: str,
    filename: str | None = None,
) -> tuple[bytes, str]:
    """
    Return image bytes and MIME type accepted by Foundry vision.

    iPhone HEIC/HEIF uploads are converted to JPEG.
    """
    if not is_heic_upload(content_type=content_type, filename=filename):
        mime = (content_type or "image/jpeg").split(";")[0].strip().lower()
        if mime in {"image/jpg", "image/pjpeg"}:
            mime = "image/jpeg"
        return image_bytes, mime

    register_heif_opener()
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB")
            buffer = BytesIO()
            rgb.save(buffer, format="JPEG", quality=92)
            return buffer.getvalue(), "image/jpeg"
    except Exception as exc:  # noqa: BLE001 - surface conversion failures to API
        raise HTTPException(
            status_code=400,
            detail="Could not decode HEIC/HEIF image. Try exporting as JPEG or PNG.",
        ) from exc

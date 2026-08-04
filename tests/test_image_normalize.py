"""Tests for HEIC/HEIF image normalization."""

import sys
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pillow_heif import register_heif_opener

sys.path.append(str(Path(__file__).resolve().parents[1] / "packages" / "server" / "app"))

from api.v1.planner.router import planner_router
from services.image_normalize import is_heic_upload, normalize_image_for_foundry

register_heif_opener()


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _heic_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(10, 20, 30)).save(buffer, format="HEIF")
    return buffer.getvalue()


def test_is_heic_upload_detects_mime_and_extension():
    assert is_heic_upload(content_type="image/heic", filename="x.jpg") is True
    assert is_heic_upload(content_type="application/octet-stream", filename="IMG_001.HEIC") is True
    assert is_heic_upload(content_type="image/jpeg", filename="x.jpg") is False


def test_normalize_leaves_png_unchanged():
    raw = _png_bytes()
    out_bytes, out_type = normalize_image_for_foundry(
        image_bytes=raw, content_type="image/png", filename="planner.png"
    )
    assert out_bytes == raw
    assert out_type == "image/png"


def test_normalize_converts_heic_to_jpeg():
    out_bytes, out_type = normalize_image_for_foundry(
        image_bytes=_heic_bytes(),
        content_type="image/heic",
        filename="IMG_0779.HEIC",
    )
    assert out_type == "image/jpeg"
    assert out_bytes[:2] == b"\xff\xd8"
    with Image.open(BytesIO(out_bytes)) as image:
        assert image.format == "JPEG"
        assert image.size == (32, 32)


def test_extract_endpoint_accepts_heic_content_type(monkeypatch):
    app = FastAPI()
    app.include_router(planner_router, prefix="/planner")

    class FakeController:
        async def extract_from_upload(self, *, image):
            assert (image.content_type or "").lower() == "image/heic"
            return {"planner_title": None, "event_count": 0, "preview": [], "events": []}

    monkeypatch.setattr("api.v1.planner.router.PlannerController", FakeController)
    client = TestClient(app)
    response = client.post(
        "/planner/extract",
        files={"image": ("IMG_001.HEIC", b"fake", "image/heic")},
    )
    assert response.status_code == 200

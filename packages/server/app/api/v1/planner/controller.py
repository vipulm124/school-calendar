"""Controller for planner image extraction via Azure Foundry."""

from fastapi import HTTPException, UploadFile

from schemas.planner_ocr import PlannerParseResult
from services.azure_foundry_planner import AzureFoundryError
from services.image_normalize import HEIC_CONTENT_TYPES, normalize_image_for_foundry
from services.planner_ocr_pipeline import PlannerOcrPipeline

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    *HEIC_CONTENT_TYPES,
    # iOS sometimes uploads HEIC as generic binary with a .heic filename.
    "application/octet-stream",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
IMAGE_FILENAME_SUFFIXES = (
    ".heic",
    ".heif",
    ".heics",
    ".heifs",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
)


class PlannerController:
    """Handles planner image upload and Foundry vision extraction."""

    def __init__(self, pipeline: PlannerOcrPipeline | None = None) -> None:
        self.pipeline = pipeline or PlannerOcrPipeline()

    async def extract_from_upload(self, *, image: UploadFile) -> dict:
        content_type = (image.content_type or "").lower()
        filename = image.filename or ""
        image_bytes = await image.read()
        return await self.extract_from_bytes(
            image_bytes=image_bytes,
            content_type=content_type,
            filename=filename,
        )

    async def extract_from_bytes(
        self,
        *,
        image_bytes: bytes,
        content_type: str,
        filename: str = "",
    ) -> dict:
        content_type = (content_type or "").lower()
        filename = filename or ""

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported image type '{content_type}'. "
                    "Use JPEG, PNG, WEBP, GIF, or HEIC/HEIF."
                ),
            )

        # Reject bare octet-stream unless the filename looks like an image.
        if content_type == "application/octet-stream":
            lower_name = filename.lower()
            if not lower_name.endswith(IMAGE_FILENAME_SUFFIXES):
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported binary upload. Use an image file (JPEG/PNG/HEIC).",
                )

        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="Image exceeds 10 MB limit.")

        try:
            normalized_bytes, normalized_type = normalize_image_for_foundry(
                image_bytes=image_bytes,
                content_type=content_type,
                filename=filename,
            )
            result: PlannerParseResult = await self.pipeline.extract_events(
                normalized_bytes, content_type=normalized_type
            )
        except AzureFoundryError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
            "planner_title": result.planner_title,
            "event_count": len(result.events),
            "preview": self.pipeline.preview_lines(result),
            "events": [event.model_dump(mode="json") for event in result.events],
        }

"""Router for planner image extraction."""

from fastapi import APIRouter, File, UploadFile

from api.v1.planner.controller import PlannerController
from core import Response

planner_router = APIRouter(tags=["Planner OCR"])


@planner_router.post("/extract")
async def extract_planner_events(image: UploadFile = File(..., description="Planner calendar image")):
    """
    Upload a planner image and extract Holidays (green) and PTC (yellow) via Azure Foundry LLM.
    """
    body = await PlannerController().extract_from_upload(image=image)
    return Response.success(
        body=body,
        message="Planner events extracted successfully.",
        status_code=200,
    )

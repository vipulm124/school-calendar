from fastapi import APIRouter, Depends, Request
from core import get_db, Response
from sqlalchemy.orm import Session
from api.v1.holiday.controller import HolidayController
from schemas import HolidayCreateRequest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import datetime as datetime

telegram_router = APIRouter(prefix="/telegram", tags=["Telegram"])


# POST /telegram/webhook
@telegram_router.post("/webhook")
async def telegram_webhook(update: dict):
    # 1. parse update (message, photo, text, from.id)
    # 2. allowlist check
    # 3. handle photo / YES / commands
    # 4. return 200 quickly
    return {"ok": True}


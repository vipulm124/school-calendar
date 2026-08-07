"""
This module contains the FastAPI application for the server.
"""

import sys

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.v1 import student_class_router, holiday_type_router, holiday_router, planner_router, telegram_router


app = FastAPI(
    title="Student Calendar",
    version="1.0.0",
    license_info={
        "name": "MIT License",
        "url": "https://github.com/TeamShiksha/team.shiksha/blob/prod/docs/LICENSE",
    },
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redocs",
)


app.include_router(student_class_router)
app.include_router(holiday_type_router)
app.include_router(holiday_router)
app.include_router(planner_router)
app.include_router(telegram_router)


app.add_middleware(
    CORSMiddleware,
    # allow_origins=config.ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    RELOAD_FLAG = True if len(sys.argv) > 1 else False
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=RELOAD_FLAG)

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers.media import router as media_router
from app.routers.return_cases import router as return_cases_router
from app.schemas import HealthResponse
from app.services.storage_service import ensure_bucket_exists

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    ensure_bucket_exists()
    yield


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(return_cases_router)
app.include_router(media_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    return HealthResponse(status="ok", app_name=settings.app_name)

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, engine
from app.db_migrate import ensure_schema
from app.response import http_exception_handler, success, validation_exception_handler
from app.routers import auth, dashboard, user, video

UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
(UPLOAD_ROOT / "avatars").mkdir(parents=True, exist_ok=True)
(UPLOAD_ROOT / "videos").mkdir(parents=True, exist_ok=True)
(UPLOAD_ROOT / "covers").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    yield


app = FastAPI(title="jj_shop_service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(video.router)
app.include_router(user.router)


@app.get("/health")
def health() -> dict:
    return success({"status": "ok"})

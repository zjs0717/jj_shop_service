from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, engine
from app.response import http_exception_handler, success, validation_exception_handler
from app.routers import auth, dashboard, video
from app.services.video_crawler import video_crawler


def _warmup_videos() -> None:
    try:
        video_crawler.warmup()
    except Exception:
        # 启动预爬失败不影响服务；接口侧仍有兜底
        pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    # 后台预爬 10 条并入库内存，前端请求只读缓存
    Thread(target=_warmup_videos, name="video-warmup", daemon=True).start()
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

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(video.router)


@app.get("/health")
def health() -> dict:
    return success({"status": "ok"})

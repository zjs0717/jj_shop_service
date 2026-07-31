from fastapi import APIRouter

from app.response import success
from app.services.dashboard import predictor

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview() -> dict:
    """返回运营大屏数据；每次请求基于上一次快照递推生成。"""
    return success(predictor.next_snapshot())


@router.post("/reset")
def reset() -> dict:
    """重置预测基线（调试用）。"""
    return success(predictor.reset())

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Address, User, UserVideo
from app.response import success
from app.schemas import (
    AddressRequest,
    AddressResponse,
    ProfileUpdateRequest,
    UserResponse,
    UserVideoResponse,
    UserVideoUpdateRequest,
)

router = APIRouter(prefix="/api/user", tags=["user"])

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
AVATAR_DIR = UPLOAD_ROOT / "avatars"
VIDEO_DIR = UPLOAD_ROOT / "videos"
COVER_DIR = UPLOAD_ROOT / "covers"
for _dir in (AVATAR_DIR, VIDEO_DIR, COVER_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_VIDEO_BYTES = 120 * 1024 * 1024
MAX_COVER_BYTES = 5 * 1024 * 1024


def _normalize_tags(raw: str | None) -> str:
    if not raw:
        return ""
    parts = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
    return ",".join(parts[:12])


def _safe_ext(filename: str | None, allowed: set[str], fallback: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in allowed else fallback


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)) -> dict:
    return success(UserResponse.from_user(current_user).model_dump(mode="json"))


@router.patch("/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if payload.nickname is not None:
        current_user.nickname = payload.nickname
    if payload.gender is not None:
        current_user.gender = payload.gender
    if payload.bio is not None:
        current_user.bio = payload.bio
    if payload.avatarUrl is not None:
        current_user.avatar_url = payload.avatarUrl.strip()

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return success(UserResponse.from_user(current_user).model_dump(mode="json"))


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传图片文件")

    ext = _safe_ext(file.filename, IMAGE_EXTS, ".jpg")
    filename = f"u{current_user.id}_{uuid.uuid4().hex[:12]}{ext}"
    target = AVATAR_DIR / filename
    data = await file.read()
    if len(data) > MAX_COVER_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像不能超过 5MB")

    target.write_bytes(data)
    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return success(UserResponse.from_user(current_user).model_dump(mode="json"))


@router.get("/addresses")
def list_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    rows = (
        db.query(Address)
        .filter(Address.user_id == current_user.id)
        .order_by(Address.is_default.desc(), Address.id.desc())
        .all()
    )
    return success([AddressResponse.from_row(row).model_dump(mode="json") for row in rows])


@router.post("/addresses")
def create_address(
    payload: AddressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if payload.isDefault:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})

    row = Address(
        user_id=current_user.id,
        name=payload.name,
        phone=payload.phone,
        province=payload.province,
        city=payload.city,
        district=payload.district.strip(),
        detail=payload.detail,
        is_default=payload.isDefault,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(AddressResponse.from_row(row).model_dump(mode="json"))


@router.put("/addresses/{address_id}")
def update_address(
    address_id: int,
    payload: AddressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")

    if payload.isDefault:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": False})

    row.name = payload.name
    row.phone = payload.phone
    row.province = payload.province
    row.city = payload.city
    row.district = payload.district.strip()
    row.detail = payload.detail
    row.is_default = payload.isDefault
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(AddressResponse.from_row(row).model_dump(mode="json"))


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    db.delete(row)
    db.commit()
    return success({"message": "已删除"})


@router.get("/videos")
def list_videos(
    video_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    query = (
        db.query(UserVideo)
        .options(joinedload(UserVideo.user))
        .filter(UserVideo.user_id == current_user.id)
    )
    if video_status in {"library", "published"}:
        query = query.filter(UserVideo.status == video_status)
    rows = query.order_by(UserVideo.id.desc()).all()
    return success(
        {
            "total": len(rows),
            "list": [UserVideoResponse.from_row(row, current_user).model_dump(mode="json") for row in rows],
        }
    )


@router.post("/videos/upload")
async def upload_video(
    video: UploadFile = File(..., description="短视频文件"),
    cover: UploadFile | None = File(default=None, description="封面图，可选"),
    title: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    city: str = Form(""),
    status_value: str = Form("library", alias="status"),
    duration: float = Form(0),
    width: int = Form(0),
    height: int = Form(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """上传短视频并收集元数据。"""
    title_text = (title or "").strip()
    if not title_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空")
    if len(title_text) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题最多 120 字")

    if status_value not in {"library", "published"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="状态无效")

    content_type = (video.content_type or "").lower()
    if content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传视频文件")

    video_ext = _safe_ext(video.filename, VIDEO_EXTS, ".mp4")
    video_name = f"u{current_user.id}_{uuid.uuid4().hex}{video_ext}"
    video_bytes = await video.read()
    if not video_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频文件为空")
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频不能超过 120MB")

    (VIDEO_DIR / video_name).write_bytes(video_bytes)
    play_url = f"/uploads/videos/{video_name}"

    cover_url = ""
    if cover is not None and cover.filename:
        cover_type = (cover.content_type or "").lower()
        if cover_type and not cover_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="封面必须是图片")
        cover_ext = _safe_ext(cover.filename, IMAGE_EXTS, ".jpg")
        cover_name = f"u{current_user.id}_{uuid.uuid4().hex[:12]}{cover_ext}"
        cover_bytes = await cover.read()
        if len(cover_bytes) > MAX_COVER_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="封面不能超过 5MB")
        if cover_bytes:
            (COVER_DIR / cover_name).write_bytes(cover_bytes)
            cover_url = f"/uploads/covers/{cover_name}"

    now = datetime.now(timezone.utc) if status_value == "published" else None
    row = UserVideo(
        user_id=current_user.id,
        title=title_text,
        cover=cover_url,
        play_url=play_url,
        description=(description or "").strip()[:500],
        tags=_normalize_tags(tags),
        city=(city or "").strip()[:50],
        status=status_value,
        duration=max(0.0, float(duration or 0)),
        width=max(0, int(width or 0)),
        height=max(0, int(height or 0)),
        file_size=len(video_bytes),
        mime_type=content_type or f"video/{video_ext.lstrip('.')}",
        original_filename=(video.filename or "")[:255],
        published_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(UserVideoResponse.from_row(row, current_user).model_dump(mode="json"))


@router.patch("/videos/{video_id}")
def update_video(
    video_id: int,
    payload: UserVideoUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = (
        db.query(UserVideo)
        .filter(UserVideo.id == video_id, UserVideo.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频不存在")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空")
        row.title = title
    if payload.cover is not None:
        row.cover = payload.cover.strip()
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.tags is not None:
        row.tags = _normalize_tags(payload.tags)
    if payload.city is not None:
        row.city = payload.city.strip()[:50]
    if payload.status is not None:
        row.status = payload.status
        if payload.status == "published" and row.published_at is None:
            row.published_at = datetime.now(timezone.utc)
        if payload.status == "library":
            row.published_at = None

    db.add(row)
    db.commit()
    db.refresh(row)
    return success(UserVideoResponse.from_row(row, current_user).model_dump(mode="json"))


@router.delete("/videos/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = (
        db.query(UserVideo)
        .filter(UserVideo.id == video_id, UserVideo.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频不存在")

    for path_str in (row.play_url, row.cover):
        if path_str.startswith("/uploads/"):
            file_path = UPLOAD_ROOT / path_str.removeprefix("/uploads/")
            if file_path.exists() and file_path.is_file():
                try:
                    file_path.unlink()
                except OSError:
                    pass

    db.delete(row)
    db.commit()
    return success({"message": "已删除"})

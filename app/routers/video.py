from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, get_optional_user
from app.database import get_db
from app.models import User, UserVideo, VideoLike
from app.response import success
from app.schemas import FeedVideoItem, VideoLikeResponse, VideoPlayResponse, _split_tags

router = APIRouter(prefix="/api/video", tags=["video"])


def _to_feed_item(row: UserVideo, liked: bool = False) -> dict:
    return FeedVideoItem(
        id=str(row.id),
        title=row.title,
        cover=row.cover or "",
        author=(row.user.nickname or row.user.username) if row.user else "用户",
        authorId=row.user_id,
        authorAvatar=(row.user.avatar_url if row.user else "") or "",
        playCount=row.play_count,
        likeCount=row.like_count,
        duration=float(row.duration or 0),
        playUrl=row.play_url,
        description=row.description or "",
        tags=_split_tags(row.tags),
        city=row.city or "",
        liked=liked,
    ).model_dump()


def _get_published_video(db: Session, video_id: int) -> UserVideo:
    row = (
        db.query(UserVideo)
        .options(joinedload(UserVideo.user))
        .filter(UserVideo.id == video_id, UserVideo.status == "published")
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频不存在或未发布")
    return row


def _liked_ids(db: Session, user: User | None, video_ids: list[int]) -> set[int]:
    if not user or not video_ids:
        return set()
    rows = (
        db.query(VideoLike.video_id)
        .filter(VideoLike.user_id == user.id, VideoLike.video_id.in_(video_ids))
        .all()
    )
    return {int(r[0]) for r in rows}


@router.get("/feed")
def feed(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """推荐流：已发布的用户短视频（按发布时间倒序）。"""
    rows = (
        db.query(UserVideo)
        .options(joinedload(UserVideo.user))
        .filter(UserVideo.status == "published")
        .order_by(UserVideo.published_at.desc(), UserVideo.id.desc())
        .limit(limit)
        .all()
    )
    liked = _liked_ids(db, current_user, [row.id for row in rows])
    items = [_to_feed_item(row, liked=row.id in liked) for row in rows]
    return success(
        {
            "total": len(items),
            "list": items,
            "source": "user-upload",
        }
    )


@router.get("/search")
def search_videos(
    keyword: str = Query(default="", min_length=0, max_length=80),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """按标题 / 描述 / 标签 / 作者昵称搜索已发布短视频。"""
    q = keyword.strip()
    if not q:
        return success({"total": 0, "list": [], "keyword": ""})

    like = f"%{q}%"
    rows = (
        db.query(UserVideo)
        .options(joinedload(UserVideo.user))
        .join(User, UserVideo.user_id == User.id)
        .filter(
            UserVideo.status == "published",
            or_(
                UserVideo.title.ilike(like),
                UserVideo.description.ilike(like),
                UserVideo.tags.ilike(like),
                UserVideo.city.ilike(like),
                User.nickname.ilike(like),
                User.username.ilike(like),
            ),
        )
        .order_by(UserVideo.published_at.desc(), UserVideo.id.desc())
        .limit(limit)
        .all()
    )
    liked = _liked_ids(db, current_user, [row.id for row in rows])
    items = [_to_feed_item(row, liked=row.id in liked) for row in rows]
    return success({"total": len(items), "list": items, "keyword": q})


@router.get("/{video_id}/related")
def related_videos(
    video_id: int,
    limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """根据标签 / 标题关键词推荐相关短视频。"""
    source = _get_published_video(db, video_id)
    tags = _split_tags(source.tags)
    keywords = tags[:]
    title_bits = [part.strip() for part in source.title.replace("，", " ").replace(",", " ").split() if part.strip()]
    keywords.extend(title_bits[:4])
    keywords = list(dict.fromkeys([k for k in keywords if k]))

    query = (
        db.query(UserVideo)
        .options(joinedload(UserVideo.user))
        .filter(UserVideo.status == "published", UserVideo.id != source.id)
    )

    if keywords:
        conditions = []
        for key in keywords[:8]:
            like = f"%{key}%"
            conditions.extend(
                [
                    UserVideo.title.ilike(like),
                    UserVideo.description.ilike(like),
                    UserVideo.tags.ilike(like),
                ]
            )
        query = query.filter(or_(*conditions))
    else:
        query = query.filter(UserVideo.user_id == source.user_id)

    rows = query.order_by(UserVideo.published_at.desc(), UserVideo.id.desc()).limit(limit).all()
    if not rows and source.user_id:
        rows = (
            db.query(UserVideo)
            .options(joinedload(UserVideo.user))
            .filter(
                UserVideo.status == "published",
                UserVideo.id != source.id,
                UserVideo.user_id == source.user_id,
            )
            .order_by(UserVideo.published_at.desc(), UserVideo.id.desc())
            .limit(limit)
            .all()
        )

    liked = _liked_ids(db, current_user, [row.id for row in rows])
    items = [_to_feed_item(row, liked=row.id in liked) for row in rows]
    return success(
        {
            "total": len(items),
            "list": items,
            "videoId": str(source.id),
            "keywords": keywords[:8],
        }
    )


@router.post("/{video_id}/like")
def like_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """点赞 / 取消点赞（切换）。"""
    row = _get_published_video(db, video_id)
    existing = (
        db.query(VideoLike)
        .filter(VideoLike.user_id == current_user.id, VideoLike.video_id == row.id)
        .first()
    )

    if existing:
        db.delete(existing)
        row.like_count = max(0, int(row.like_count or 0) - 1)
        liked = False
    else:
        db.add(VideoLike(user_id=current_user.id, video_id=row.id))
        row.like_count = int(row.like_count or 0) + 1
        liked = True

    db.add(row)
    db.commit()
    db.refresh(row)
    return success(
        VideoLikeResponse(
            videoId=str(row.id),
            liked=liked,
            likeCount=int(row.like_count or 0),
        ).model_dump()
    )


@router.post("/{video_id}/play")
def record_play(
    video_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """记录一次播放（前端应对同一视频会话去重）。"""
    row = _get_published_video(db, video_id)
    row.play_count = int(row.play_count or 0) + 1
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(
        VideoPlayResponse(
            videoId=str(row.id),
            playCount=int(row.play_count or 0),
        ).model_dump()
    )

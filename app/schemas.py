from datetime import datetime

from pydantic import BaseModel, field_validator


class AuthRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = value.strip()
        if len(username) < 3:
            raise ValueError("用户名至少 3 位")
        if len(username) > 50:
            raise ValueError("用户名最多 50 位")
        return username

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码至少 6 位")
        if len(value) > 128:
            raise ValueError("密码最多 128 位")
        return value


class LoginResponse(BaseModel):
    token: str


class RegisterResponse(BaseModel):
    token: str
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    nickname: str = ""
    avatarUrl: str = ""
    gender: str = "unknown"
    bio: str = ""
    createdAt: datetime | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        return cls(
            id=user.id,
            username=user.username,
            nickname=user.nickname or user.username,
            avatarUrl=user.avatar_url or "",
            gender=user.gender or "unknown",
            bio=user.bio or "",
            createdAt=user.created_at,
        )


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    gender: str | None = None
    bio: str | None = None
    avatarUrl: str | None = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return value
        nickname = value.strip()
        if not nickname:
            raise ValueError("昵称不能为空")
        if len(nickname) > 50:
            raise ValueError("昵称最多 50 位")
        return nickname

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"male", "female", "other", "unknown"}:
            raise ValueError("性别取值无效")
        return value

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, value: str | None) -> str | None:
        if value is None:
            return value
        bio = value.strip()
        if len(bio) > 200:
            raise ValueError("简介最多 200 字")
        return bio


class AddressRequest(BaseModel):
    name: str
    phone: str
    province: str
    city: str
    district: str = ""
    detail: str
    isDefault: bool = False

    @field_validator("name", "province", "city", "detail")
    @classmethod
    def validate_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("必填项不能为空")
        return text

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        phone = value.strip()
        if len(phone) < 6 or len(phone) > 20:
            raise ValueError("手机号格式不正确")
        return phone


class AddressResponse(BaseModel):
    id: int
    name: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    isDefault: bool
    createdAt: datetime | None = None

    @classmethod
    def from_row(cls, row) -> "AddressResponse":
        return cls(
            id=row.id,
            name=row.name,
            phone=row.phone,
            province=row.province,
            city=row.city,
            district=row.district or "",
            detail=row.detail,
            isDefault=bool(row.is_default),
            createdAt=row.created_at,
        )


class UserVideoCreateRequest(BaseModel):
    title: str
    cover: str = ""
    playUrl: str
    description: str = ""
    status: str = "library"
    tags: str = ""
    city: str = ""
    duration: float = 0
    width: int = 0
    height: int = 0

    @field_validator("title", "playUrl")
    @classmethod
    def validate_required(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("必填项不能为空")
        return text

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"library", "published"}:
            raise ValueError("状态只能是 library 或 published")
        return value


class UserVideoUpdateRequest(BaseModel):
    title: str | None = None
    cover: str | None = None
    description: str | None = None
    status: str | None = None
    tags: str | None = None
    city: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"library", "published"}:
            raise ValueError("状态只能是 library 或 published")
        return value


def _split_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.replace("，", ",").split(",") if part.strip()]


class UserVideoResponse(BaseModel):
    id: int
    title: str
    cover: str
    playUrl: str
    status: str
    playCount: int
    likeCount: int
    description: str
    tags: list[str] = []
    duration: float = 0
    width: int = 0
    height: int = 0
    fileSize: int = 0
    mimeType: str = ""
    originalFilename: str = ""
    city: str = ""
    createdAt: datetime | None = None
    publishedAt: datetime | None = None
    authorId: int | None = None
    author: str = ""
    authorAvatar: str = ""

    @classmethod
    def from_row(cls, row, user=None) -> "UserVideoResponse":
        author = user
        if author is None:
            author = getattr(row, "user", None)
        return cls(
            id=row.id,
            title=row.title,
            cover=row.cover or "",
            playUrl=row.play_url,
            status=row.status,
            playCount=row.play_count,
            likeCount=row.like_count,
            description=row.description or "",
            tags=_split_tags(getattr(row, "tags", "") or ""),
            duration=float(getattr(row, "duration", 0) or 0),
            width=int(getattr(row, "width", 0) or 0),
            height=int(getattr(row, "height", 0) or 0),
            fileSize=int(getattr(row, "file_size", 0) or 0),
            mimeType=getattr(row, "mime_type", "") or "",
            originalFilename=getattr(row, "original_filename", "") or "",
            city=getattr(row, "city", "") or "",
            createdAt=row.created_at,
            publishedAt=row.published_at,
            authorId=author.id if author else row.user_id,
            author=(author.nickname or author.username) if author else "",
            authorAvatar=(author.avatar_url if author else "") or "",
        )


class FeedVideoItem(BaseModel):
    id: str
    title: str
    cover: str
    author: str
    authorId: int
    authorAvatar: str
    playCount: int
    likeCount: int
    duration: float
    playUrl: str
    description: str
    tags: list[str] = []
    city: str = ""
    liked: bool = False


class VideoLikeResponse(BaseModel):
    videoId: str
    liked: bool
    likeCount: int


class VideoPlayResponse(BaseModel):
    videoId: str
    playCount: int


class MessageResponse(BaseModel):
    message: str

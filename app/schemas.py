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

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str

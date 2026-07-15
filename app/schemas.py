from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


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

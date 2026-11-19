from datetime import datetime, timezone
from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: str


class TokenResponse(BaseModel):
    token: str
    user: UserResponse

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    date_of_birth: date
    phone: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        if not (3 <= len(v) <= 32):
            raise ValueError("Username must be 3-32 characters")
        if not v.replace("_", "").replace(".", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, '.' and '_'")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    is_age_verified: bool
    is_kyc_verified: bool
    kyc_status: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

"""Authentication-related Pydantic schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Registration request. Role is always 'patient'."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Plain-text password")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name")


class LoginRequest(BaseModel):
    """Login request with email and password."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str = Field(..., description="Refresh JWT")


class TokenPair(BaseModel):
    """Pair of access and refresh tokens returned after login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    """Logout request — client sends refresh token to revoke."""

    refresh_token: str = Field(..., description="Refresh JWT to revoke")

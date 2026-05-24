"""
Pydantic schemas for auth endpoints
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from models.user import UserRole


class LoginRequest(BaseModel):
    """Login request"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with token"""
    access_token: str
    token_type: str
    user: 'UserResponse'


class UserCreate(BaseModel):
    """User registration"""
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.ARTICLED_ASSISTANT


class UserResponse(BaseModel):
    """User response"""
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True

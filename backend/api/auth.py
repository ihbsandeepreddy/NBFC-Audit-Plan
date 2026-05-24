"""
Authentication API — login, register, JWT token handling
"""

from datetime import timedelta, datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from core.database import get_db
from core.security import create_access_token, verify_password, hash_password, decode_access_token
from core.config import settings
from models.user import User, UserRole

router = APIRouter()
security = HTTPBearer(auto_error=False)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.ARTICLED_ASSISTANT


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT and return current user"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def _serialize_user(u: User) -> UserResponse:
    return UserResponse(id=str(u.id), email=u.email, full_name=u.full_name,
                        role=u.role.value if u.role else "articled_assistant", is_active=u.is_active)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return LoginResponse(access_token=token, user=_serialize_user(user))


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(request: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        id=uuid.uuid4(), email=request.email, full_name=request.full_name,
        hashed_password=hash_password(request.password), role=request.role, is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _serialize_user(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return _serialize_user(current_user)


@router.post("/logout")
async def logout():
    """Logout — client should discard token"""
    return {"message": "Logged out successfully"}


@router.get("/users")
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users (manager+ only)"""
    if current_user.role not in [UserRole.MANAGER, UserRole.PARTNER]:
        raise HTTPException(403, "Insufficient permissions")
    result = await db.execute(select(User).where(User.is_active == True))
    return [_serialize_user(u) for u in result.scalars().all()]

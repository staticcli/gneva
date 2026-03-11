"""Auth endpoints: register, login, refresh."""

import re
import time
import uuid
from collections import defaultdict

from pydantic import BaseModel, EmailStr, field_validator
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import Organization, User
from gneva.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --------------- In-memory rate limiter ---------------
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(key: str, max_requests: int, window_seconds: int = 60) -> None:
    """Raise 429 if *key* has exceeded *max_requests* within *window_seconds*."""
    now = time.monotonic()
    timestamps = _rate_limit_store[key]
    # Prune expired entries
    _rate_limit_store[key] = [t for t in timestamps if now - t < window_seconds]
    if len(_rate_limit_store[key]) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    _rate_limit_store[key].append(now)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    org_name: str

    @field_validator("password")
    @classmethod
    def _validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    org_id: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    org_id: str
    org_name: str


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"register:{client_ip}", max_requests=3)
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create org with unique slug
    base_slug = req.org_name.lower().replace(" ", "-")[:50]
    slug = base_slug
    counter = 1
    while True:
        existing_slug = await db.execute(select(Organization).where(Organization.slug == slug))
        if not existing_slug.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    org = Organization(name=req.org_name, slug=slug)
    db.add(org)
    await db.flush()

    # Create user as admin
    user = User(
        org_id=org.id,
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user.id, org.id, user.role)
    return TokenResponse(access_token=token, user_id=str(user.id), org_id=str(org.id))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"login:{client_ip}", max_requests=5)
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.org_id, user.role)
    return TokenResponse(access_token=token, user_id=str(user.id), org_id=str(user.org_id))


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = result.scalar_one()
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        org_id=str(user.org_id),
        org_name=org.name,
    )

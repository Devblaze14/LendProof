from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
import httpx
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import AppUser, Profile
from app.schemas import LoginRequest, LoginResponse, SignupRequest
from app.config import get_settings
from app.security import create_access_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GUEST_EMAIL = "guest@local.loan-copilot.dev"
GUEST_NAME = "Guest viewer"
GUEST_PASSWORD = "guest-session-only"
settings = get_settings()


def _supabase_password_login(email: str, password: str, db: Session) -> LoginResponse:
    """Exchange credentials with Supabase Auth; the browser never receives a service key."""
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise AppError(500, "SUPABASE_CONFIG_MISSING", "SUPABASE_URL and SUPABASE_ANON_KEY are required")
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": password}, timeout=10.0,
    )
    if response.status_code >= 400:
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password")
    payload = response.json()
    claims = decode_token(payload["access_token"])
    profile = db.get(Profile, uuid.UUID(claims["sub"]))
    if profile is None:
        raise AppError(403, "PROFILE_MISSING", "This Supabase user has no LendProof role profile")
    return LoginResponse(
        access_token=payload["access_token"], role=profile.role,
        name=profile.name or claims.get("email"),
    )


@router.post("/guest", response_model=LoginResponse)
def guest_login(db: Session = Depends(get_db)):
    """Issue a read-only consumer session for the local/demo viewer."""
    if settings.database_mode == "supabase":
        raise AppError(400, "GUEST_DISABLED", "Create a Supabase consumer demo account instead of using local guest access")
    user = db.query(AppUser).filter(AppUser.email == GUEST_EMAIL).first()
    if user is None:
        user = AppUser(email=GUEST_EMAIL, password_hash=hash_password(GUEST_PASSWORD))
        db.add(user)
        db.flush()

    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(id=user.id, role="consumer", name=GUEST_NAME)
        db.add(profile)
        db.commit()

    return LoginResponse(
        access_token=create_access_token(user.id, "consumer"), role="consumer", name=GUEST_NAME,
    )


@router.post("/signup", response_model=LoginResponse, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if settings.database_mode == "supabase":
        raise AppError(400, "USE_SUPABASE_AUTH", "Create users through Supabase Auth or the Supabase dashboard")
    if payload.role not in ("operator", "reviewer", "consumer"):
        raise AppError(400, "INVALID_ROLE", "role must be operator, reviewer, or consumer", "role")
    if db.query(AppUser).filter(AppUser.email == payload.email).first():
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists", "email")
    user = AppUser(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    profile = Profile(id=user.id, role=payload.role, name=payload.name)
    db.add(profile)
    db.commit()
    token = create_access_token(user.id, payload.role)
    return LoginResponse(access_token=token, role=payload.role, name=payload.name)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    if settings.database_mode == "supabase":
        return _supabase_password_login(payload.email, payload.password, db)
    user = db.query(AppUser).filter(AppUser.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password")
    profile = db.get(Profile, user.id)
    token = create_access_token(user.id, profile.role)
    return LoginResponse(access_token=token, role=profile.role, name=profile.name)

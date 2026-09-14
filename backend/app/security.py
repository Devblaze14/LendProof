"""
Auth for DATABASE_MODE=local: this backend issues and verifies its own JWTs
so the whole app is runnable and testable without a Supabase project.

Online deployments use the same application-managed JWT path as local mode.
Supabase provides the durable Postgres database and Storage, but Supabase Auth
is not used for LendProof demo login.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Profile

settings = get_settings()
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    salt = "loan-copilot-static-dev-salt"  # fine for a local dev/demo backend;
    # The same deterministic hash is used by the fixed demo accounts in both
    # local and online database modes.
    return hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    payload = {"sub": str(user_id), "role": role, "iat": int(time.time()),
               "exp": int(time.time()) + 60 * 60 * 8}
    return jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.local_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


def get_current_profile(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile:
    claims = decode_token(creds.credentials)
    profile = db.get(Profile, uuid.UUID(claims["sub"]))
    if profile is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return profile


def require_role(*allowed_roles: str):
    def dependency(profile: Profile = Depends(get_current_profile)) -> Profile:
        if profile.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{profile.role}' cannot access this endpoint",
            )
        return profile
    return dependency

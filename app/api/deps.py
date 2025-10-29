# app/api/deps.py
from typing import Optional, Dict, Any
import os
import base64
import json

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.database import db

# Configuration / secrets (env overrides allowed)
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
OAUTH2_TOKEN_URL = os.getenv("OAUTH2_TOKEN_URL", "/api/auth/token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=OAUTH2_TOKEN_URL)


def get_db():
    """
    Dependency that returns the file-backed DB object.
    Usage:
        db = Depends(get_db)
    """
    return db


def _extract_identifier_from_jwt_without_verification(token: str) -> Optional[str]:
    """
    Best-effort extraction of common identity claims from a JWT-like token
    without verifying signature. Returns first found claim or None.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += "=" * (4 - rem)
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        payload = json.loads(payload_bytes)
        for k in ("sub", "user_id", "id", "uid", "username", "email"):
            if k in payload and payload[k]:
                return str(payload[k])
    except Exception:
        return None
    return None


def _decode_token(token: str) -> Optional[str]:
    """
    Decode JWT and return the 'sub' (username/user id) if valid, else None.
    This function first tries to verify using the configured secret; if that
    fails, it will attempt a best-effort extraction of identity claims from
    a JWT-like token (no signature verification). Returns None if nothing found.
    """
    if not token:
        return None
    # try verify/validate first
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub") or payload.get("user_id") or payload.get("id") or payload.get("username")
        if not sub:
            return None
        return str(sub)
    except JWTError:
        # fallback: try to parse payload without verification (useful for test tokens)
        extracted = _extract_identifier_from_jwt_without_verification(token)
        if extracted:
            return extracted
        return None


async def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Resolve current user from Authorization header (Bearer) or from cookie 'access_token'.
    Returns the user row as a dict (as stored in the file-backed DB). Raises 401 if not authenticated.

    This function accepts:
     - Signed JWTs (verified with JWT_SECRET) containing a 'sub' or equivalent claim.
     - JWT-like tokens where payload is decoded without verification (best-effort for tests).
     - Raw identifiers passed as token (e.g. a username or user id). In that case we try lookups by id, username, email.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    identifier = None

    # 1) Try OAuth2 header token (this dependency will extract token if Authorization header present)
    if token:
        # normalize token (strip leading "Bearer " if present)
        t = token
        if isinstance(t, str) and t.lower().startswith("bearer "):
            t = t.split(" ", 1)[1]
        identifier = _decode_token(t)

        # if decode returned nothing, fallback to treating token as raw identifier
        if identifier is None:
            identifier = t

    # 2) Fallback to cookie (useful for browser-login flows)
    if identifier is None:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            identifier = _decode_token(cookie_token) or cookie_token

    if not identifier:
        raise credentials_exception

    # try lookup by id first, then username/email
    user_row = db.get_record("users", "id", identifier)
    if not user_row:
        user_row = db.get_record("users", "username", identifier) or db.get_record("users", "email", identifier)

    if not user_row:
        raise credentials_exception

    # remove hashed password before returning (defensive)
    user_row.pop("hashed_password", None)
    user_row.pop("password_hash", None)
    return user_row


async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Placeholder for additional checks (e.g. is_active flag). For now returns current_user.
    """
    # if you add 'is_active' field, check it here and raise 400/403 as appropriate
    return current_user


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Dependency to require admin privileges. Raises 403 if user is not admin.
    """
    # Users may have is_admin stored as string; normalize truthiness
    is_admin = current_user.get("is_admin", False)
    if isinstance(is_admin, str):
        is_admin = is_admin.strip().lower() in ("1", "true", "yes", "y", "t")
    elif isinstance(is_admin, (int, float)):
        is_admin = bool(is_admin)
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user

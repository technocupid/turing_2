# app/api/deps.py
from typing import Optional, Dict, Any
import os

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


def _decode_token(token: str) -> Optional[str]:
    """
    Decode JWT and return the 'sub' (username/user id) if valid, else None.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            return None
        return str(sub)
    except JWTError:
        return None


async def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Resolve current user from Authorization header (Bearer) or from cookie 'access_token'.
    Returns the user row as a dict (as stored in the file-backed DB). Raises 401 if not authenticated.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    username = None

    # 1) Try OAuth2 header token (this dependency will extract token if Authorization header present)
    if token:
        username = _decode_token(token)

    # 2) Fallback to cookie (useful for browser-login flows)
    if username is None:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            username = _decode_token(cookie_token)

    if username is None:
        raise credentials_exception

    # fetch user row from DB (users table expected)
    # db.get_record(table, key, value)
    user_row = db.get_record("users", "username", username)
    if not user_row:
        raise credentials_exception

    # remove hashed password before returning (defensive)
    user_row.pop("hashed_password", None)
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

# app/api/routes/auth.py
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import hash_password, verify_password
from jose import jwt

import os

from app.api.deps import get_db, JWT_SECRET, JWT_ALGORITHM
from app.schemas.user import TokenResponse, UserOut
from app.database import FileBackedDB

router = APIRouter(prefix="/api/auth", tags=["auth"])

# token lifetime (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

db: FileBackedDB = get_db()  # module-level DB instance


def _create_access_token(subject: str, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = {"sub": subject, "exp": datetime.utcnow() + timedelta(minutes=expires_delta)}
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


@router.post("/token", response_model=TokenResponse)
def token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Token endpoint used by OAuth2PasswordRequestForm clients.
    Returns a signed JWT containing 'sub' == user id (or username).
    """
    # lookup user by username (form_data.username)
    user = db.get_record("users", "username", form_data.username) or db.get_record("users", "email", form_data.username) or db.get_record("users", "id", form_data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    stored_hash = user.get("password_hash") or user.get("hashed_password")
    if not stored_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        if not verify_password(form_data.password, stored_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except Exception:
        # treat verification errors as invalid credentials
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    subject = str(user.get("id") or user.get("username") or user.get("email"))
    access_token = _create_access_token(subject=subject)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login")
def login_form(response: Response, username: str = Form(...), password: str = Form(...)):
    """
    Simple form login used by UI tests: sets an 'access_token' cookie.
    """
    user = db.get_record("users", "username", username) or db.get_record("users", "email", username) or db.get_record("users", "id", username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    stored_hash = user.get("password_hash") or user.get("hashed_password")
    if not stored_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        if not verify_password(password, stored_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    subject = str(user.get("id") or user.get("username") or user.get("email"))
    access_token = _create_access_token(subject=subject)
    # set cookie for browser-style flows (tests expect this)
    response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="lax")
    # return user-shaped payload (consistent with register)
    user_out = {
        "id": user.get("id"),
        "username": user.get("username"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "is_admin": bool(user.get("is_admin", False)),
    }
    return user_out


# alias expected by tests
@router.post("/login-form")
def login_form_alias(response: Response, username: str = Form(...), password: str = Form(...)):
    return login_form(response=response, username=username, password=password)


@router.post("/register", response_model=UserOut, status_code=200)
def register(user: Dict[str, Any]):
    """
    Minimal register endpoint (used occasionally by tests). Expects a dict with username/email/password.
    Hashes the password and stores as 'password_hash'.
    """
    username = user.get("username")
    email = user.get("email")
    password = user.get("password")
    if not username or not password or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username, email and password required")
    hashed = hash_password(password)
    row = db.create_record("users", {"username": username, "email": email, "password_hash": hashed, "is_admin": user.get("is_admin", False), "full_name": user.get("full_name")}, id_field="id")
    # build a deterministic user output shape expected by tests/schemas
    user_out = {
        "id": row.get("id"),
        "username": row.get("username"),
        "email": row.get("email"),
        "full_name": row.get("full_name"),
        "is_admin": bool(row.get("is_admin", False)),
    }
    return user_out
# app/api/routes/auth.py
from datetime import datetime, timedelta
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt

from app.api.deps import get_db, JWT_SECRET, JWT_ALGORITHM
from app.schemas.user import UserCreate, TokenResponse, UserOut
from app.database import FileBackedDB

router = APIRouter(prefix="/api/auth", tags=["auth"])

# password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# token lifetime (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

db: FileBackedDB = get_db()  # not a call - returns the module-level object


def _create_access_token(*, subject: str, expires_delta: int | None = None) -> str:
    now = datetime.utcnow()
    if expires_delta is None:
        expires_delta = ACCESS_TOKEN_EXPIRE_MINUTES
    expire = now + timedelta(minutes=int(expires_delta))
    to_encode = {"sub": subject, "exp": int(expire.timestamp())}
    encoded = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded


@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate):
    """
    Register a new user. Returns user info (no hashed_password).
    """
    # ensure username/email not taken
    existing = db.get_record("users", "username", user_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="username already exists")
    existing_email = None
    # try search by email (simple linear scan)
    all_users = db.list_records("users")
    for u in all_users:
        if str(u.get("email")).lower() == user_in.email.lower():
            existing_email = u
            break
    if existing_email:
        raise HTTPException(status_code=400, detail="email already exists")

    hashed = pwd_context.hash(user_in.password)
    row = {
        "username": user_in.username,
        "email": user_in.email,
        "hashed_password": hashed,
        "is_admin": False,
        "full_name": user_in.full_name or "",
        "created_at": datetime.utcnow().isoformat(sep=" "),
    }
    saved = db.create_record("users", row, id_field="id")
    # remove hashed before returning
    saved.pop("hashed_password", None)
    return saved


@router.post("/token", response_model=TokenResponse)
def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 password grant style endpoint. Returns JWT access token.
    """
    username = form_data.username
    password = form_data.password
    user = db.get_record("users", "username", username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    hashed = user.get("hashed_password") or ""
    if not pwd_context.verify(password, hashed):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = _create_access_token(subject=username)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login-form")
async def login_form(request: Request, response: Response):
    """
    Accept either JSON body: {"username":"...","password":"..."}
    OR form-encoded body (application/x-www-form-urlencoded or multipart/form-data).
    Sets an HttpOnly 'access_token' cookie on successful auth.
    """
    username = None
    password = None

    # choose parsing strategy based on content type
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        # JSON body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        username = body.get("username")
        password = body.get("password")
    else:
        # Try form data (works for application/x-www-form-urlencoded and multipart/form-data)
        try:
            form = await request.form()
            username = form.get("username") or form.get("user") or None
            password = form.get("password") or form.get("pass") or None
        except Exception:
            # fallback: try to read raw body as JSON (best-effort)
            try:
                body = await request.json()
                username = body.get("username")
                password = body.get("password")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid request body")

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    user = db.get_record("users", "username", username)
    if not user or not pwd_context.verify(password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = _create_access_token(subject=username)

    # set cookie (HttpOnly). In production set secure=True and appropriate SameSite.
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24,
        samesite="lax",
    )
    return {"ok": True, "username": username}
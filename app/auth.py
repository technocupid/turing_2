from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt, JWTError
from app.core.config import settings
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Simple in-memory user store for demo. Replace with persistent store if needed.
USERS = {
    settings.ADMIN_USERNAME: {
        'username': settings.ADMIN_USERNAME,
        'hashed_password': pwd_context.hash(settings.ADMIN_PASSWORD),
        'is_admin': True
    }
}


def authenticate_user(username: str, password: str):
    user = USERS.get(username)
    if not user:
        return None
    if not pwd_context.verify(password, user['hashed_password']):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def _decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)):
    # oauth2_scheme will try to read header Authorization: Bearer <token>
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1) If token was provided via Authorization header (oauth2_scheme resolved it)
    if token:
        username = _decode_token(token)
        if not username:
            raise credentials_exception
        user = USERS.get(username)
        if not user:
            raise credentials_exception
        return user

    # 2) Fallback: try cookie
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        username = _decode_token(cookie_token)
        if not username:
            raise credentials_exception
        user = USERS.get(username)
        if not user:
            raise credentials_exception
        return user

    # no token anywhere → unauthorized
    raise credentials_exception
def require_admin(user: dict = Depends(get_current_user)):
    if not user.get('is_admin'):
        raise HTTPException(status_code=403, detail='Admin privileges required')
    return user

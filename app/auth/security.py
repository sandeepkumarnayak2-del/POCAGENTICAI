from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.config import settings
from app.database.db import SessionLocal
from app.database.models import User


password_hash = PasswordHash.recommended()
#OAuth2PasswordBearer does not validate the JWT itself.
#It primarily extracts the bearer token from the request and integrates with FastAPI’s OAuth2/OpenAPI #security scheme.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


def authenticate(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).first()
        if user and verify_password(password, user.password_hash):
            return user
    finally:
        db.close()

    return None


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256",
    )


def current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    db = SessionLocal()
    try:
        user = db.get(User, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return user
    finally:
        db.close()


def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return user

    return dependency
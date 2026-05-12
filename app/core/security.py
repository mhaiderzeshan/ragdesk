import jwt
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash

from app.core.config import settings


ph = PasswordHash.recommended()


import asyncio

def _get_password_hash_sync(password: str) -> str:
    return ph.hash(password)

def _verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    return ph.verify(plain_password, hashed_password)

async def get_password_hash(password: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_password_hash_sync, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _verify_password_sync, plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT token containing user and organization context.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM)
    return encoded_jwt

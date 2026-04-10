import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db import get_db
from app.repositories.auth import AuthRepository
from app.schemas.auth import UserContext
from uuid import UUID


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserContext:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Decode JWT
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM]
        )

        user_id_raw = payload.get("sub")
        org_id_raw = payload.get("org_id")
        email = payload.get("email")
        role = payload.get("role", "user")

        if user_id_raw is None or org_id_raw is None or email is None:
            raise credentials_exception

        user_id: UUID = UUID(str(user_id_raw))
        org_id: UUID = UUID(str(org_id_raw))

        # Return the context
        return UserContext(
            user_id=user_id,
            org_id=org_id,
            email=email,
            role=role,
        )

    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

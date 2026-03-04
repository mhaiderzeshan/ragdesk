from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.db import get_db
from app.schemas.auth import UserResponse, RegistrationRequest
from app.repositories.auth import AuthRepository
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    # Initialize Repo and Service
    auth_service = AuthService(AuthRepository(db))

    # Call the service
    try:
        user = await auth_service.register_new_org(payload)
        return user
    except IntegrityError as e:
        # Handle database unique constraint violations (email or org name)
        error_str = str(e.orig).lower()
        if "email" in error_str or "users_email_key" in error_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
        elif "name" in error_str or "orgs_name_key" in error_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Organization name already exists")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Resource already exists")

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.schemas.auth import UserResponse, RegistrationRequest
from app.repositories.auth import AuthRepository
from app.services.auth import AuthService
from app.schemas import Token

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


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(AuthRepository(db))

    user = await auth_service.authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_user_token(user)
    return {"access_token": access_token, "token_type": "bearer"}

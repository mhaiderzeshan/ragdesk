from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.schemas.auth import UserResponse, RegistrationRequest
from app.repositories.auth import AuthRepository
from app.services.auth import AuthService
from app.schemas import Token
from app.api.deps import get_current_user
from app.schemas.auth import UserContext

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
        error_str = str(e.orig).lower()
        print("INTEGRITY ERROR:", repr(e.orig))
        if "users_email_key" in error_str or "uq_users_email" in error_str:
            raise HTTPException(400, detail="Email already exists")
        elif "orgs_name_key" in error_str or "uq_orgs_name" in error_str:
            raise HTTPException(400, detail="Organization name already exists")
        else:
            raise HTTPException(400, detail=f"Resource already exists")


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


@router.get("/me", response_model=UserContext)
async def read_users_me(current_user: UserContext = Depends(get_current_user)):
    """
    Returns the current user's identity and organization context.
    If the token is missing or invalid, FastAPI returns 401 automatically.
    """
    return current_user

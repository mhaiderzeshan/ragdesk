from app.schemas import RegistrationRequest, OrganizationCreate, UserCreate
from app.repositories.auth import AuthRepository
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models import User
from app.core.config import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo

    async def register_new_org(self, payload: RegistrationRequest):
        payload.email = payload.email.strip().lower()

        # Hash the password here (Service handles business logic)
        hashed_password = await get_password_hash(payload.password)

        # Prepare the schemas for the Repository
        org_data = OrganizationCreate(name=payload.org_name)
        user_data = UserCreate(email=payload.email, password=hashed_password)

        return await self.repo.create_org_and_user(
            org_in=org_data,
            user_in=user_data,
            hashed_password=hashed_password
        )

    async def authenticate_user(self, email: str, password: str):
        email = email.strip().lower()
        user = await self.repo.get_user_by_email(email)
        if not user:
            return None
        
        is_valid = await verify_password(password, user.hashed_password)
        if not is_valid:
            return None
            
        return user

    def create_user_token(self, user: User) -> str:
        # Create the JWT token with the user data.
        # Pass the configured TTL — without this the token silently falls back
        # to the hardcoded 15-minute default in create_access_token.
        token_data = {
            "sub": str(user.id),
            "org_id": str(user.org_id),
            "email": user.email,
            "role": user.role,
        }
        return create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
